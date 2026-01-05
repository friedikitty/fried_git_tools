#!/usr/bin/env python3
# -*- coding: utf-8 -*-

###############################################################################
# Git Batch Push Script
###############################################################################
#
# DESCRIPTION:
#   This script syncs git commits from origin remote to destination remote in batches
#   to avoid server limits, such as pack size limits or timeout issues when pushing many commits.
#
# USAGE:
#   ./git_sync_to_remote.py <workspace_directory> [remote] [branch] [--debug] [--no-verify]
#
# PARAMETERS:
#   workspace_directory (required) - Path to the git repository
#   remote (optional)              - Destination remote name (default: destination)
#   branch (optional)              - Branch name to sync (default: develop)
#   --debug (optional)             - Enable debug mode (list commits per batch and require confirmation before each batch)
#   --no-verify (optional)         - Disable verification after each batch (default: verification enabled)
#
# NOTE: Source remote is always 'origin'. Script syncs: origin -> destination
#
# EXAMPLES:
#   # Sync from origin to default destination remote (destination) and branch (develop)
#   ./git_sync_to_remote.py /path/to/repo
#
#   # Sync from origin to specific destination remote and branch
#   ./git_sync_to_remote.py /path/to/repo destination 2025.1-lts
#
#   # Sync with debug mode enabled
#   ./git_sync_to_remote.py /path/to/repo destination 2025.1-lts --debug
#
# CONFIGURATION:
#   BATCH_SIZE  - Number of commits per batch (default: 50)
#   FORCE_PUSH  - Enable force push with lease protection (default: true)
#
# HOW IT WORKS:
#   1. Check if the workspace is a valid git repository
#   2. Fetch the latest state from both origin and destination remotes
#   3. Find commits in origin that are not in destination (origin..destination)
#   4. Split commits into batches of BATCH_SIZE
#   5. Push each batch from origin to destination remote in chronological order
#   6. Use --force-with-lease for safe force pushing (if enabled)
#
# FORCE PUSH BEHAVIOR:
#   - FORCE_PUSH=true:  Use --force-with-lease to safely overwrite remote
#     (only works if remote hasn't changed since last fetch)
#   - FORCE_PUSH=false: Use normal push (fails if remote has diverged)
#
# ERROR HANDLING:
#   - Checks all required parameters and git repository status
#   - Shows detailed error messages with suggested solutions
#   - Exits immediately on push failure with helpful diagnostics
#
# REQUIREMENTS:
#   - Git must be installed and available in PATH
#   - Remote must be configured with correct authentication
#   - User must have push permissions to the target remote/branch
#
# NOTES:
#   - Authentication tokens should be embedded in the remote URL
#   - A 1-second delay is added between batches to reduce server load
#   - Useful for pushing large commit histories or fixing pack size errors
#
###############################################################################

import os
import sys
import re
import time
import argparse
import subprocess
from pathlib import Path

# Import command runner
from run_command import (
    run_command,
    run_command_and_get_return_info,
    run_command_and_ensure_zero,
    ConsoleCommandLogger,
)

# Configuration
SOURCE_REMOTE = "origin"  # Always sync from origin
BATCH_SIZE = 50
FORCE_PUSH = True
REGEX_PUSH_ERROR = "ERROR"

# Get script directory for temp folder
SCRIPT_DIR = Path(__file__).parent.absolute()

# Global command logger for functions that don't have context access
_global_cmd_logger = ConsoleCommandLogger(prefix="[CMD]")


# Regex pattern to match lines that are solid with graph symbols: |, \, //, etc.
# This matches lines that are entirely composed of |, /, \, spaces, tabs, and *
GIT_GRAPH_SYMBOL_REGEX = r"^[|/\\\s*]+"
GIT_GRAPH_SYMBOL_REGEX_PATTERN = re.compile(GIT_GRAPH_SYMBOL_REGEX + "$", re.IGNORECASE)
GIT_GRAPH_SYMBOL_REGEX_PATTERN_LEADING = re.compile(
    GIT_GRAPH_SYMBOL_REGEX, re.IGNORECASE
)


class CommitInfo:
    """Commit info class to hold commit hash and message."""

    def __init__(self, hash: str, message: str, is_sub_line_of_merge_commit: bool):
        self.hash = hash
        self.message = message
        self.is_sub_line_of_merge_commit = is_sub_line_of_merge_commit

    def __str__(self):
        return f"{self.hash} - {self.message}{'(sub-commit)' if self.is_sub_line_of_merge_commit else ''}"

    def __eq__(self, other):
        """Two commits are equal if they have the same hash and message."""
        if not isinstance(other, CommitInfo):
            return False
        return self.hash == other.hash

    def __ne__(self, other):
        """Two commits are not equal if they differ in hash or message."""
        return not self.__eq__(other)


class Context:
    """Context class to hold all common parameters and state."""

    def __init__(self):
        # Basic configuration
        self.workspace_dir = None
        self.source_remote = SOURCE_REMOTE
        self.dest_remote = None
        self.branch = None
        self.debug_mode = False
        self.verify = True

        # Push configuration
        self.push_options = []

        # Verification state
        self.temp_dir = None
        self.origin_log_file = None
        self.origin_log_lines = None  # Cached origin branch log lines

        # Commit information
        self.commits: list[CommitInfo] = []
        self.total_commits = 0
        self.total_batches = 0

        # LFS state
        self.is_using_lfs = False

        # Destination branch state (for LFS range calculation)
        self.dest_head_hash = None

        # Command logger for separating command output from main process logs
        self.cmd_logger = ConsoleCommandLogger(prefix="[SUBCMD]")


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Sync git commits from origin remote to destination remote in batches",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s /path/to/repo
  %(prog)s /path/to/repo destination 2025.1-lts
  %(prog)s /path/to/repo destination develop --debug
  %(prog)s /path/to/repo destination develop --no-verify
        """,
    )

    parser.add_argument("workspace_directory", help="Path to the git repository")
    parser.add_argument(
        "remote",
        nargs="?",
        default="destination",
        help="Destination remote name (default: destination)",
    )
    parser.add_argument(
        "branch",
        nargs="?",
        default="develop",
        help="Branch name to sync (default: develop)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode (list commits per batch and require confirmation before each batch)",
    )
    parser.add_argument(
        "--no-verify",
        action="store_true",
        help="Disable verification after each batch (default: verification enabled)",
    )

    return parser.parse_args()


def validate_workspace_directory(workspace_dir):
    """Validate that workspace directory exists."""
    if not os.path.isdir(workspace_dir):
        print(f"Error: Workspace directory '{workspace_dir}' does not exist")
        sys.exit(1)


def validate_remote(workspace_dir, remote_name):
    """Validate that remote exists and return its URL."""
    cmd = ["git", "remote", "get-url", remote_name]
    result = run_command(cmd, cwd=workspace_dir)

    if result != 0:
        print(f"Error: Remote '{remote_name}' not found")
        print("Available remotes:")
        run_command(
            ["git", "remote", "-v"], cwd=workspace_dir, logger=_global_cmd_logger
        )
        sys.exit(1)

    # Get remote URL
    try:
        output = run_command_and_get_return_info(cmd, cwd=workspace_dir, shell=False)
        remote_url = output.strip()
        return remote_url
    except subprocess.CalledProcessError as e:
        print(f"Error: Failed to get remote URL for '{remote_name}': {e}")
        sys.exit(1)


def confirm_origin_push(remote_name):
    """Ask for confirmation if pushing to origin."""
    if remote_name == "origin":
        print("")
        print("WARNING: Push to origin, which seems dangerous!")
        print("    Git sync usually syncs to a second remote.")
        confirmation = input("Are you sure? [yes/no]: ")
        if confirmation != "yes":
            print("Operation cancelled.")
            sys.exit(0)
        print("")


def validate_branch_exists(workspace_dir, remote_name, branch_name):
    """Validate that branch exists on the specified remote."""
    ref = f"refs/remotes/{remote_name}/{branch_name}"
    cmd = ["git", "show-ref", "--quiet", "--verify", ref]
    result = run_command(cmd, cwd=workspace_dir)

    if result != 0:
        print(f"Error: Branch '{branch_name}' not found on remote '{remote_name}'")
        print(f"Available branches on {remote_name}:")
        # Filter branches to show only the relevant remote
        run_command(
            ["git", "branch", "-r"], cwd=workspace_dir, logger=_global_cmd_logger
        )
        # Also show filtered output for clarity
        try:
            output = run_command_and_get_return_info(
                ["git", "branch", "-r"], cwd=workspace_dir, shell=False
            )
            filtered = [
                line.strip()
                for line in output.strip().splitlines()
                if line.strip().startswith(f"{remote_name}/")
            ]
            if filtered:
                print("Filtered branches:")
                for branch in filtered:
                    print(f"  {branch}")
        except subprocess.CalledProcessError:
            pass  # Already showed all branches above
        sys.exit(1)


def filter_valid_commits(lines: list[str], debug_mode: bool) -> list[CommitInfo]:
    """Filter out commits that are not valid."""
    # Parse lines to extract commit hash and message, and create CommitInfo objects
    # Format with --graph: graph_symbols commit_hash commit_message
    # Commit hash is always 40 hex characters
    commits = []
    # Compile regex once for performance
    hash_pattern = re.compile(r"\b([0-9a-f]{40})\b", re.IGNORECASE)

    for line in lines:
        line_stripped = line.strip()
        if not line_stripped:
            continue
        # Skip lines that are entirely graph symbols (same approach as verify_logs)
        if GIT_GRAPH_SYMBOL_REGEX_PATTERN.match(line_stripped):
            continue

        # Remove leading graph symbols from lines that have content (same approach as verify_logs)
        cleaned_line = GIT_GRAPH_SYMBOL_REGEX_PATTERN_LEADING.sub("", line).strip()

        is_sub_line_of_merge_commit = False
        if line_stripped.startswith("|"):  # It's a sub line of a merge commit
            is_sub_line_of_merge_commit = True

        # Find the 40-character hex string (commit hash) in the cleaned line
        hash_match = hash_pattern.search(cleaned_line)
        if hash_match:
            commit_hash = hash_match.group(1)
            # Get everything after the hash as the message
            hash_pos = hash_match.end()
            commit_msg = cleaned_line[hash_pos:].strip()
            # Create CommitInfo object
            commits.append(
                CommitInfo(commit_hash, commit_msg, is_sub_line_of_merge_commit)
            )
        else:
            # Fallback: if no hash found, skip this line (shouldn't happen)
            if debug_mode:
                print(f"Warning: Could not parse commit hash from line: {line[:80]}")

    # Reverse to get chronological order (oldest first)
    # commits = list(reversed(commits))
    print(f"Found {len(commits)} commits to push (including merge commits)")
    return commits


def get_commits_to_push(ctx: Context) -> list:
    """Get list of commits to push in chronological order.

    Gets the HEAD commit of destination branch, finds it in the cached origin log,
    and returns all commits after that point. This preserves graph structure.
    """
    if ctx.origin_log_lines is None:
        print("Error: Origin log not cached. setup_verification must be called first.")
        sys.exit(1)

    # Get destination branch HEAD commit hash and commit count
    # Get both upfront to avoid conditional second call
    print(f"Getting destination branch info: {ctx.dest_remote}/{ctx.branch}")

    # Get commit count
    cmd_count = ["git", "rev-list", "--count", f"{ctx.dest_remote}/{ctx.branch}"]
    try:
        count_output = run_command_and_get_return_info(
            cmd_count, cwd=ctx.workspace_dir, shell=False
        )
        dest_commit_count = int(count_output.strip())
    except subprocess.CalledProcessError as e:
        print(f"Error: Failed to get destination branch commit count: {e}")
        sys.exit(1)

    # Get HEAD hash
    cmd_head = ["git", "rev-parse", f"{ctx.dest_remote}/{ctx.branch}"]
    try:
        dest_head_output = run_command_and_get_return_info(
            cmd_head, cwd=ctx.workspace_dir, shell=False
        )
        dest_head_hash = dest_head_output.strip()
        ctx.dest_head_hash = (
            dest_head_hash  # Store in context for LFS range calculation
        )
        print(
            f"Destination HEAD: {dest_head_hash} (branch has {dest_commit_count} commit(s))"
        )
    except subprocess.CalledProcessError as e:
        print(f"Error: Failed to get destination branch HEAD: {e}")
        sys.exit(1)

    # Parse origin log into CommitInfo objects
    origin_commits = filter_valid_commits(
        reversed(ctx.origin_log_lines), ctx.debug_mode
    )

    # Find the destination HEAD in the origin log
    dest_head_idx = None
    for idx, commit in enumerate(origin_commits):
        if commit.hash == dest_head_hash:
            dest_head_idx = idx
            break

    if dest_head_idx is None:
        # Destination HEAD not found in origin log
        print(f"Warning: Destination HEAD {dest_head_hash} not found in origin log.")
        print(f"Destination branch has {dest_commit_count} commit(s)")

        if dest_commit_count > 1:
            print(
                f"Error: Destination branch has {dest_commit_count} commits but HEAD not found in origin log."
            )
            print(
                "This indicates the branches have diverged. Cannot safely push all commits."
            )
            sys.exit(1)
        else:
            # Destination branch has 0 or 1 commit, safe to push all
            print(
                f"Destination branch has {dest_commit_count} commit(s), pushing all origin commits."
            )
            commits_to_push = origin_commits
    else:
        # Get all commits after the destination HEAD
        commits_to_push = origin_commits[dest_head_idx + 1 :]
        print(f"Found destination HEAD at position {dest_head_idx + 1} in origin log")

    print(
        f"Found {len(commits_to_push)} commits to push (origin has {len(origin_commits)} total)"
    )

    # In debug mode, write comparison to temp file
    if ctx.debug_mode:
        if ctx.temp_dir is None:
            ctx.temp_dir = Path(ctx.workspace_dir) / "temp"
        ctx.temp_dir.mkdir(parents=True, exist_ok=True)

        comparison_file = ctx.temp_dir / f"commits_comparison_{ctx.branch}.txt"
        with open(comparison_file, "w", encoding="utf-8", newline="\n") as f:
            f.write(f"Destination HEAD: {dest_head_hash}\n")
            f.write(
                f"Destination HEAD position in origin log: {dest_head_idx + 1 if dest_head_idx is not None else 'NOT FOUND'}\n"
            )
            f.write(f"Origin commits: {len(origin_commits)}\n")
            f.write(f"Commits to push: {len(commits_to_push)}\n")
            f.write("\n" + "=" * 80 + "\n")
            f.write("Commits to push:\n")
            for commit in commits_to_push:
                f.write(f"{commit}\n")
        print(f"[DEBUG] Wrote commits comparison to: {comparison_file}")

    return commits_to_push


def verify_logs(ctx: Context) -> bool:
    """Verify logs by comparing origin and destination branch logs."""
    if not ctx.verify:
        return True

    # Fetch latest state from destination remote
    # git fetch outputs info to stderr, so use stderr_to_stdout=True to treat it as normal output
    # error_regex will catch actual error messages
    run_command(
        ["git", "fetch", "--force", ctx.dest_remote],
        cwd=ctx.workspace_dir,
        logger=ctx.cmd_logger,
        stderr_to_stdout=True,
        error_regex=".*error.*",
    )

    # Get destination's branch log
    dest_log_file = ctx.temp_dir / f"{ctx.dest_remote}_{ctx.branch}.txt"
    cmd = [
        "git",
        "log",
        f"{ctx.dest_remote}/{ctx.branch}",
        "--graph",
        "--oneline",
        "--pretty=format:%H %s",
    ]
    try:
        output = run_command_and_get_return_info(
            cmd, cwd=ctx.workspace_dir, shell=False
        )
        # Reverse the output (equivalent to tac)
        lines = output.strip().splitlines()
        reversed_lines = list(reversed(lines))
        # Use newline='\n' to ensure consistent LF line endings on Windows/MINGW
        with open(dest_log_file, "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(reversed_lines))
            if reversed_lines:
                f.write("\n")
    except subprocess.CalledProcessError as e:
        print(f"Error: Failed to get destination log: {e}")
        return False

    # Read and clean both logs
    # Use newline='\n' to ensure consistent LF line endings when reading on Windows/MINGW
    with open(ctx.origin_log_file, "r", encoding="utf-8", newline="\n") as f:
        origin_lines = f.readlines()

    with open(dest_log_file, "r", encoding="utf-8", newline="\n") as f:
        dest_lines = f.readlines()

    # Remove lines that are solid with graph symbols (|, \, //) and clean lines
    # Pattern 1: Match lines that are entirely graph symbols (to skip them)
    #
    #  Pattern 2: Remove leading graph symbols from lines that have content

    origin_clean = filter_valid_commits(origin_lines, ctx.debug_mode)

    dest_clean = filter_valid_commits(dest_lines, ctx.debug_mode)

    # Count lines
    origin_lines_count = len(origin_clean)
    dest_lines_count = len(dest_clean)
    min_lines = min(origin_lines_count, dest_lines_count)

    if min_lines == 0:
        print("[VERIFY] Warning: No lines to compare")
        return True

    # Compare first min_lines lines
    origin_compare = origin_clean[:min_lines]
    dest_compare = dest_clean[:min_lines]

    if origin_compare == dest_compare:
        print(f"[VERIFY] equal - logs match (compared first {min_lines} lines)")
        return True
    else:
        print("[VERIFY] FAILED - logs do not match!")

        # Find first mismatched line and its line number (1-indexed)
        first_mismatch_line_num = None
        first_mismatch_origin = None
        first_mismatch_dest = None
        for idx in range(min_lines):
            if origin_compare[idx] != dest_compare[idx]:
                first_mismatch_line_num = idx + 1  # 1-indexed
                first_mismatch_origin = origin_compare[idx]
                first_mismatch_dest = dest_compare[idx]
                break

        # Print first mismatch information
        if first_mismatch_line_num is not None:
            print(f"First mismatch at line {first_mismatch_line_num}:")
            print(f"  Origin:   {first_mismatch_origin}, file: {ctx.origin_log_file}")
            print(f"  Dest:     {first_mismatch_dest}, file: {dest_log_file}")
            print("")

        # Print 10 lines from both sides starting from the mismatch line
        mismatch_idx = first_mismatch_line_num - 1 if first_mismatch_line_num else 0
        start_idx = max(0, mismatch_idx)
        end_idx = min(len(origin_compare), mismatch_idx + 10)

        print(
            f"Origin log (lines {start_idx + 1} to {end_idx} of {min_lines} compared lines):"
        )
        if start_idx > 0:
            print("...")
        for i in range(start_idx, end_idx):
            print(f"  {i + 1}: {origin_compare[i]}")
        if end_idx < len(origin_compare):
            print("...")
        print("")

        print(
            f"Destination log (lines {start_idx + 1} to {end_idx} of {min_lines} compared lines):"
        )
        if start_idx > 0:
            print("...")
        for i in range(start_idx, end_idx):
            print(f"  {i + 1}: {dest_compare[i]}")
        if end_idx < len(dest_compare):
            print("...")
        print("")
        print("Stopping sync due to verification failure")
        return False


def setup_verification(ctx: Context):
    """Setup verification and cache origin branch log.

    This must be called before get_commits_to_push to cache the origin log.
    """
    # Create temp directory under script's folder if it doesn't exist
    ctx.temp_dir = Path(ctx.workspace_dir) / "temp"
    ctx.temp_dir.mkdir(parents=True, exist_ok=True)

    # Get origin's branch log and cache it
    ctx.origin_log_file = ctx.temp_dir / f"{ctx.source_remote}_{ctx.branch}.txt"
    print(f"Capturing origin branch log: {ctx.origin_log_file}")

    cmd = [
        "git",
        "log",
        f"{ctx.source_remote}/{ctx.branch}",
        "--graph",
        "--oneline",
        "--format=%H %s",
    ]
    try:
        output = run_command_and_get_return_info(
            cmd, cwd=ctx.workspace_dir, shell=False
        )
        # Store the lines (not reversed) - we'll reverse when processing
        ctx.origin_log_lines = output.strip().splitlines()

        # Reverse the output for saving to file (equivalent to tac)
        reversed_lines = list(reversed(ctx.origin_log_lines))
        # Use newline='\n' to ensure consistent LF line endings on Windows/MINGW
        with open(ctx.origin_log_file, "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(reversed_lines))
            if reversed_lines:
                f.write("\n")

        print(f"Cached {len(ctx.origin_log_lines)} lines from origin branch log")

        if ctx.verify:
            print("Verification enabled - will compare logs after each batch")
        else:
            print("Verification disabled (--no-verify)")
    except subprocess.CalledProcessError as e:
        print(f"Error: Failed to capture origin log: {e}")
        sys.exit(1)


def is_lfs_enabled(workspace_dir: str) -> bool:
    """Check if Git LFS is enabled in the repository."""
    try:
        # Check if .gitattributes exists and contains filter=lfs
        gitattributes_path = os.path.join(workspace_dir, ".gitattributes")
        if os.path.exists(gitattributes_path):
            with open(gitattributes_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
                if "filter=lfs" in content:
                    return True

        # Also check if git lfs is installed and repo has LFS tracked files
        result = subprocess.run(
            ["git", "lfs", "ls-files"],
            cwd=workspace_dir,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        # If command succeeds and has output, LFS is likely enabled
        if result.returncode == 0 and result.stdout.strip():
            return True

        return False
    except (subprocess.CalledProcessError, FileNotFoundError):
        # Git LFS not installed or not enabled
        return False


def find_commits_with_lfs_in_range(
    ctx: Context, start_commit: str, end_commit: str
) -> list[str]:
    """Find all commits in a range that contain LFS files.

    Uses git log with -G "oid sha256:" to find commits that contain LFS file references.

    Args:
        ctx: Context object
        start_commit: Starting commit SHA (exclusive, not included in range)
        end_commit: Ending commit SHA (inclusive, included in range)

    Returns:
        list[str]: List of commit SHAs that contain LFS files, in chronological order
    """
    try:
        # Use git log to find commits with LFS files in the range
        # Range format: start..end means commits reachable from end but not from start
        cmd = [
            "git",
            "log",
            f"{start_commit}..{end_commit}",
            "-G",
            "oid sha256:",
            "--name-only",
            "--pretty=format:%H %s",
        ]

        output = run_command_and_get_return_info(
            cmd, cwd=ctx.workspace_dir, shell=False
        )

        # Parse output to extract unique commit SHAs
        # Format: commit_hash commit_message\nfile1\nfile2\n\ncommit_hash2...
        # git log returns commits in reverse chronological order (newest first)
        commit_shas = []
        seen_commits = set()

        for line in output.splitlines():
            line = line.strip()
            if not line:
                continue

            # Check if line starts with a 40-character hex string (commit hash)
            if len(line) >= 40:
                # Try to extract commit hash (first 40 chars should be hex)
                potential_hash = line[:40]
                if all(c in "0123456789abcdefABCDEF" for c in potential_hash):
                    if potential_hash not in seen_commits:
                        commit_shas.append(potential_hash)
                        seen_commits.add(potential_hash)

        # Reverse to get chronological order (oldest first) for consistency
        commit_shas.reverse()

        return commit_shas

    except subprocess.CalledProcessError as e:
        print(f"Warning: Failed to find commits with LFS files: {e}")
        return []
    except Exception as e:
        print(f"Warning: Error finding commits with LFS files: {e}")
        return []


def fetch_lfs_objects_for_commit(ctx: Context, commit_sha: str) -> bool:
    """Fetch Git LFS objects for a specific commit by creating a temp branch.

    Creates a temporary local branch at the commit, fetches LFS objects
    for that branch, then cleans up the temporary branch.

    Args:
        ctx: Context object
        commit_sha: Commit SHA to fetch LFS objects for

    Returns:
        bool: True if successful, False on error
    """
    temp_branch_name = f"temp_lfs_fetch_{commit_sha[:8]}"

    try:
        # Create temporary branch at commit
        result = run_command(
            ["git", "branch", temp_branch_name, commit_sha],
            cwd=ctx.workspace_dir,
            logger=ctx.cmd_logger,
        )

        if result != 0:
            print(
                f"Warning: Failed to create temporary branch for commit {commit_sha[:8]} (return code: {result})"
            )
            return False

        try:
            # Fetch LFS objects for the temporary branch
            lfs_result = run_command(
                ["git", "lfs", "fetch", ctx.source_remote, temp_branch_name],
                cwd=ctx.workspace_dir,
                logger=ctx.cmd_logger,
                stderr_to_stdout=True,
            )

            if lfs_result == 0:
                return True
            else:
                print(
                    f"Warning: LFS fetch returned non-zero exit code {lfs_result} for commit {commit_sha[:8]}"
                )
                return False

        finally:
            # Always clean up the temporary branch
            cleanup_result = run_command(
                ["git", "branch", "-D", temp_branch_name],
                cwd=ctx.workspace_dir,
                logger=ctx.cmd_logger,
            )

            if cleanup_result != 0:
                # Non-fatal, just warn
                print(
                    f"Warning: Failed to delete temporary branch '{temp_branch_name}' (return code: {cleanup_result})"
                )

        return True

    except FileNotFoundError:
        print("Warning: git-lfs command not found. Skipping LFS fetch.")
        return False
    except Exception as e:
        print(f"Warning: Error fetching LFS objects for commit {commit_sha[:8]}: {e}")
        return False


def fetch_lfs_objects_for_batch(
    ctx: Context, start_commit: str, end_commit: str, batch_num: int
) -> bool:
    """Fetch Git LFS objects for all commits in a batch that contain LFS files.

    Finds all commits in the batch range that contain LFS files, then fetches
    LFS objects for each of those commits individually.

    Args:
        ctx: Context object
        start_commit: Starting commit SHA of the batch (exclusive)
        end_commit: Ending commit SHA of the batch (inclusive)
        batch_num: Batch number for logging

    Returns:
        bool: True if successful or LFS not needed, False on error
    """
    if not ctx.is_using_lfs:
        return True  # LFS not enabled, nothing to do

    print(
        f"Finding commits with LFS files in batch {batch_num} (range: {start_commit[:8]}..{end_commit[:8]})..."
    )

    # Find all commits in the batch that contain LFS files
    commits_with_lfs = find_commits_with_lfs_in_range(ctx, start_commit, end_commit)

    if not commits_with_lfs:
        print(f"No commits with LFS files found in batch {batch_num}")
        return True

    print(
        f"Found {len(commits_with_lfs)} commit(s) with LFS files in batch {batch_num}"
    )

    # Fetch LFS objects for each commit
    success_count = 0
    for commit_sha in commits_with_lfs:
        print(f"Fetching LFS objects for commit {commit_sha[:8]}...")
        if fetch_lfs_objects_for_commit(ctx, commit_sha):
            success_count += 1
        else:
            print(f"Warning: Failed to fetch LFS objects for commit {commit_sha[:8]}")
            # Continue with other commits

    if success_count == len(commits_with_lfs):
        print(
            f"LFS objects fetched successfully for all {success_count} commit(s) in batch {batch_num}"
        )
        return True
    else:
        print(
            f"Warning: Only {success_count}/{len(commits_with_lfs)} commits had LFS objects fetched successfully"
        )
        # Continue anyway - the push will fail if LFS objects are actually missing
        return True


def get_push_command(ctx: Context, target_commit: str) -> tuple:
    """Get the push command as a list and string representation."""
    cmd = (
        ["git", "push"]
        + ctx.push_options
        + [ctx.dest_remote, f"{target_commit}:refs/heads/{ctx.branch}"]
    )
    cmd_str = " ".join(cmd)
    return cmd, cmd_str


def push_batch(ctx: Context, target_commit: str, batch_num: int) -> bool:
    """Push a single batch of commits."""
    cmd, cmd_str = get_push_command(ctx, target_commit)
    print(f"Executing: {cmd_str}")
    print(
        f"  (This updates refs/heads/{ctx.branch} to point to {target_commit} from {ctx.source_remote}/{ctx.branch})"
    )

    from run_command import OutputCaptureLogger

    # Use run_command to execute and log sub-command output
    # Git push outputs to stderr, so use stderr_to_stdout=True to treat it as normal output
    # error_regex will catch actual error messages matching REGEX_PUSH_ERROR pattern
    try:
        capture_logger = OutputCaptureLogger(ctx.cmd_logger)
        return_code = run_command(
            cmd,
            cwd=ctx.workspace_dir,
            logger=capture_logger,
            stderr_to_stdout=True,
            error_regex=REGEX_PUSH_ERROR,
        )

        # Get captured output for error checking
        output = capture_logger.get_output()

        # Check if output contains error keywords matching REGEX_PUSH_ERROR pattern
        if re.search(REGEX_PUSH_ERROR, output, re.IGNORECASE):
            print(f"Error detected in output: found pattern '{REGEX_PUSH_ERROR}'")
            print(f"========================================================")
            print(f"{output}")
            print(f"========================================================")
            print(f"Return code: {return_code}")
            return False

        # Also check return code
        return return_code == 0
    except Exception as e:
        if ctx.cmd_logger:
            ctx.cmd_logger.error(f"Error executing push command: {e}")
        else:
            print(f"Error executing push command: {e}")
        return False


def show_batch_commits(
    ctx: Context, start_idx: int, end_idx: int, batch_num: int, target_commit: str
):
    """Show commits in a batch for debug mode using cached commit info."""
    print("")
    print(f"========== DEBUG MODE: Commits in batch {batch_num} ==========")

    # Show the push command that will be executed
    _, cmd_str = get_push_command(ctx, target_commit)

    print("========================================================")
    for j in range(start_idx, end_idx + 1):
        commit_info = ctx.commits[j]
        # Format as short hash - message (matching git log -1 --format=%h - %s)
        # short_hash = commit_info.hash[:7]
        if commit_info.is_sub_line_of_merge_commit:
            print(
                f"{j}. sub-commit, skipped: {commit_info.hash} - {commit_info.message}"
            )
            continue
        print(f"{j}. {commit_info.hash} - {commit_info.message}")
    print("========================================================")
    print(f"Push command: {cmd_str}")
    print(
        f"  (This will update refs/heads/{ctx.branch} to point to {target_commit} from {ctx.source_remote}/{ctx.branch})"
    )
    print("========================================================")
    print("")


def main():
    """Main function."""
    args = parse_arguments()

    # Create context and populate it
    ctx = Context()
    # Normalize workspace directory path for MINGW/Windows compatibility
    ctx.workspace_dir = os.path.normpath(args.workspace_directory)
    ctx.dest_remote = args.remote
    ctx.branch = args.branch
    ctx.debug_mode = args.debug
    ctx.verify = not args.no_verify

    # Validate workspace directory
    validate_workspace_directory(ctx.workspace_dir)

    print(f"Switching to workspace: {ctx.workspace_dir}")
    print(f"Syncing from: {ctx.source_remote} -> {ctx.dest_remote}")
    print(f"Using branch: {ctx.branch}")

    # Validate source remote exists
    validate_remote(ctx.workspace_dir, ctx.source_remote)

    # Check if remote is 'origin' and ask for confirmation
    confirm_origin_push(ctx.dest_remote)

    # Get remote URL
    remote_url = validate_remote(ctx.workspace_dir, ctx.dest_remote)
    print(f"Remote URL: {remote_url}")

    # Fetch latest state from destination remote
    print(
        f"Fetching latest remote state from {ctx.source_remote} and {ctx.dest_remote}..."
    )
    # Don't automatically fetch the source remote, you need to fetch it manually or with other scripts
    # run_command(["git", "fetch", "--force", ctx.source_remote], cwd=ctx.workspace_dir, logger=ctx.cmd_logger)
    # git fetch outputs info to stderr, so use stderr_to_stdout=True to treat it as normal output
    # error_regex will catch actual error messages
    run_command(
        ["git", "fetch", "--force", ctx.dest_remote],
        cwd=ctx.workspace_dir,
        logger=ctx.cmd_logger,
        stderr_to_stdout=True,
        error_regex=".*error.*",
    )

    # Validate branches exist
    validate_branch_exists(ctx.workspace_dir, ctx.source_remote, ctx.branch)
    validate_branch_exists(ctx.workspace_dir, ctx.dest_remote, ctx.branch)

    # Check if LFS is enabled and store in context
    ctx.is_using_lfs = is_lfs_enabled(ctx.workspace_dir)
    if ctx.is_using_lfs:
        print("Git LFS detected - will fetch LFS objects for each batch before pushing")
    else:
        print("Git LFS not detected - skipping LFS operations")

    # Setup verification and cache origin branch log (must be before get_commits_to_push)
    setup_verification(ctx)

    # Get commits to push (uses cached origin log)
    ctx.commits = get_commits_to_push(ctx)
    ctx.total_commits = len(ctx.commits)
    ctx.total_batches = (ctx.total_commits + BATCH_SIZE - 1) // BATCH_SIZE

    print(
        f"Total commits to push: {ctx.total_commits} (in {ctx.total_batches} batches)"
    )

    if ctx.total_commits == 0:
        print("No commits to push")
        sys.exit(0)

    # Determine push options
    if FORCE_PUSH:
        ctx.push_options = ["--force-with-lease"]
        print("⚠️  Force push enabled - will overwrite remote changes")
    else:
        ctx.push_options = []
        print("Using safe push (will fail on conflicts)")

    # Verify logs before starting batch pushes
    if ctx.verify:
        print("Verifying initial state before batch pushes...")
        if not verify_logs(ctx):
            print("Initial verification failed. Exiting.")
            sys.exit(1)

    # Push commits in batches
    for i in range(0, ctx.total_commits, BATCH_SIZE):
        # Calculate end index for this batch
        end = min(i + BATCH_SIZE - 1, ctx.total_commits - 1)

        # Get the commit hashes for the start and end of this batch
        first_commit = ctx.commits[i].hash

        # Find target_commit, skipping sub-commits of merge commits
        target_idx = end
        while target_idx >= i and ctx.commits[target_idx].is_sub_line_of_merge_commit:
            if ctx.debug_mode:
                print(f"Skipping sub-commit of merge commit: {ctx.commits[target_idx]}")
            target_idx -= 1

        # If we went back too far, use the first commit in the batch
        if target_idx < i + 1:  # find next
            target_idx = end
            while (
                target_idx < len(ctx.commits)
                and ctx.commits[target_idx].is_sub_line_of_merge_commit
            ):
                if ctx.debug_mode:
                    print(
                        f"Skipping sub-commit of merge commit: {ctx.commits[target_idx]}"
                    )
                target_idx += 1

        target_commit = ctx.commits[target_idx].hash
        batch_num = (i // BATCH_SIZE) + 1

        print(
            f"Pushing batch {batch_num}/{ctx.total_batches}: commits {i+1} to {end+1}"
        )
        print(f"  Range: {first_commit} (first) -> {target_commit} (last)")

        # Debug mode: list commits in this batch and ask for confirmation
        if ctx.debug_mode:
            show_batch_commits(ctx, i, target_idx, batch_num, target_commit)
            batch_confirmation = input(
                f"Do you want to proceed with pushing batch {batch_num}? [yes/no]: "
            )
            if batch_confirmation != "yes":
                print(f"Operation cancelled for batch {batch_num}.")
                sys.exit(0)
            print("")

        # Fetch LFS objects for this batch if LFS is enabled
        if ctx.is_using_lfs:
            # Determine start commit for git log range
            # Range format: start..end means commits reachable from end but not from start
            if i == 0:
                # First batch: use destination HEAD as start (commits before first commit to push)
                start_commit = ctx.dest_head_hash
            else:
                # Subsequent batches: use the commit before the first commit in this batch
                start_commit = ctx.commits[i - 1].hash

            fetch_lfs_objects_for_batch(ctx, start_commit, target_commit, batch_num)

        # Push this batch
        if push_batch(ctx, target_commit, batch_num):
            print(f"[SUCCEEDED] Batch {batch_num} pushed successfully")

            # Fetch from destination remote to get the newest pushed result
            print(f"Fetching from {ctx.dest_remote} to update local references...")
            # git fetch outputs info to stderr, so use stderr_to_stdout=True to treat it as normal output
            # error_regex will catch actual error messages
            run_command(
                ["git", "fetch", "--force", ctx.dest_remote, ctx.branch],
                cwd=ctx.workspace_dir,
                logger=ctx.cmd_logger,
                stderr_to_stdout=True,
                error_regex=".*error.*",
            )

            # Verification: compare logs after each batch
            if not verify_logs(ctx):
                sys.exit(1)
        else:
            print(f"[FAILED] Failed to push batch {batch_num}")
            if not FORCE_PUSH:
                print("The remote branch has diverged. You can:")
                print(f"1. Set FORCE_PUSH=true to overwrite remote changes")
                print(
                    f"2. Fetch and merge remote changes first: git fetch {ctx.dest_remote} && git merge {ctx.dest_remote}/{ctx.branch}"
                )
                print(
                    f"3. Use git pull to integrate changes: git pull {ctx.dest_remote} {ctx.branch}"
                )
            else:
                print("Force push failed. You may need to:")
                print("1. Reduce BATCH_SIZE further (try 20 or 10)")
                print("2. Check for large files in recent commits")
                print("3. Contact your git administrator about pack size limits")
                print(
                    "4. Verify your remote URL has the correct authentication embedded"
                )
            sys.exit(1)

        # Small delay to be nice to the server
        time.sleep(1)

    print("[SUCCEEDED] All commits pushed successfully!")


if __name__ == "__main__":
    main()
