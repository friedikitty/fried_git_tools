#!/usr/bin/env python3
# -*- coding: utf-8 -*- 
"""
Git Remote Branch Change Detection Script

This script detects if branches on a git remote have changed by comparing
current branch commit hashes with previously stored values.

Usage:
    python check_remote_change.py <workspace_directory> --remote <remote_name>
    
Examples:
    # Check if branches on 'origin' remote have changed
    python check_remote_change.py /path/to/repo --remote origin
    
    # Check branches on 'destination' remote
    python check_remote_change.py /path/to/repo --remote destination
"""

import os
import sys
import argparse
import subprocess
import json
from dataclasses import dataclass, asdict
from typing import Dict, Optional, List

# Import utility functions
from run_command import run_command_and_get_return_info
from git_sync_util import deep_merge


@dataclass
class BranchComparison:
    """Represents a branch comparison with two commit hashes."""

    local: str
    remote: str


@dataclass
class RemoteBranchComparison:
    """Represents a branch comparison between two remotes."""

    remote1: str
    remote2: str


@dataclass
class ComparisonResult:
    """Result of comparing local branches against a remote.

    Attributes:
        changed: Dictionary mapping branch names to BranchComparison objects
        no_remote: Dictionary mapping branch names to local commit hashes (branches not on remote)
        unchanged: Dictionary mapping branch names to commit hashes (branches that match)
    """

    changed: Dict[str, BranchComparison]
    no_remote: Dict[str, str]
    unchanged: Dict[str, str]

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "changed": {
                branch: {"local": comp.local, "remote": comp.remote}
                for branch, comp in self.changed.items()
            },
            "no_remote": self.no_remote,
            "unchanged": self.unchanged,
        }


@dataclass
class RemoteToRemoteComparisonResult:
    """Result of comparing two remotes.

    Attributes:
        changed: Dictionary mapping branch names to RemoteBranchComparison objects
        no_remote1: Dictionary mapping branch names to remote2 commit hashes (branches only on remote2)
        no_remote2: Dictionary mapping branch names to remote1 commit hashes (branches only on remote1)
        unchanged: Dictionary mapping branch names to commit hashes (branches that match on both remotes)
    """

    changed: Dict[str, RemoteBranchComparison]
    no_remote1: Dict[str, str]
    no_remote2: Dict[str, str]
    unchanged: Dict[str, str]

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "changed": {
                branch: {"remote1": comp.remote1, "remote2": comp.remote2}
                for branch, comp in self.changed.items()
            },
            "no_remote1": self.no_remote1,
            "no_remote2": self.no_remote2,
            "unchanged": self.unchanged,
        }


def get_local_branches(workspace_dir: str, remote_name: str) -> List[str]:
    """Get all remote branch names for a given remote.

    Args:
        workspace_dir: Path to the git repository
        remote_name: Name of the remote (e.g. 'origin')

    Returns:
        List of local branch names
    """
    branches: List[str] = []
    try:
        # Use -r to list remote branches, then filter by the given remote
        cmd = ["git", "branch", "-r"]
        output = run_command_and_get_return_info(cmd, cwd=workspace_dir, shell=False)

        # Typical lines:
        #   origin/HEAD -> origin/main
        #   origin/main
        #   origin/develop
        for line in output.strip().splitlines():
            line = line.strip()
            if not line:
                continue
            # Skip symbolic refs like "origin/HEAD -> origin/main"
            if "->" in line:
                continue
            # Only keep branches that belong to the specified remote
            if line.startswith(f"{remote_name}/"):
                branch_name = line[len(remote_name) + 1 :].strip()
                if branch_name:
                    branches.append(branch_name)
    except subprocess.CalledProcessError:
        pass

    return sorted(branches)


def get_local_branch_commit(
    workspace_dir: str, remote_name: str, branch_name: str
) -> Optional[str]:
    """Get the commit hash for a local branch.

    Args:
        workspace_dir: Path to the git repository
        branch_name: Name of the local branch

    Returns:
        Commit hash or None if branch doesn't exist
    """
    try:
        cmd = ["git", "rev-parse", f"{remote_name}/{branch_name}"]
        output = run_command_and_get_return_info(cmd, cwd=workspace_dir, shell=False)
        return output.strip()
    except subprocess.CalledProcessError:
        return None


def get_remote_branch_commit(
    workspace_dir: str, remote_name: str, branch_name: str
) -> Optional[str]:
    """Get the commit hash for a branch on a remote using ls-remote.

    Args:
        workspace_dir: Path to the git repository
        remote_name: Name of the remote
        branch_name: Name of the branch

    Returns:
        Commit hash or None if branch doesn't exist on remote
    """
    try:
        ref = f"refs/heads/{branch_name}"
        cmd = ["git", "ls-remote", remote_name, ref]
        output = run_command_and_get_return_info(cmd, cwd=workspace_dir, shell=False)

        # Parse output: "abc123...    refs/heads/branch_name"
        for line in output.strip().splitlines():
            parts = line.split()
            if len(parts) >= 2 and parts[1] == ref:
                return parts[0]
    except subprocess.CalledProcessError:
        pass

    return None


def get_all_branch_hashes(
    workspace_dir: str, remote_name: str, limit_branches: Optional[set] = None
) -> Dict[str, Dict[str, Optional[str]]]:
    """Get commit hashes for all local branches (local and remote).

    Args:
        workspace_dir: Path to the git repository
        remote_name: Name of the remote
        limit_branches: Optional set of branch names to limit checking to

    Returns:
        Dictionary mapping branch names to {'local': hash, 'remote': hash}
    """
    # Use remote branches for the specified remote
    local_branches = get_local_branches(workspace_dir, remote_name)
    
    # Filter branches if limit_branches is specified
    if limit_branches:
        local_branches = [b for b in local_branches if b in limit_branches]
    
    branch_hashes = {}

    for branch_name in local_branches:
        local_hash = get_local_branch_commit(workspace_dir, remote_name, branch_name)
        remote_hash = get_remote_branch_commit(workspace_dir, remote_name, branch_name)

        branch_hashes[branch_name] = {
            "local": local_hash,
            "remote": remote_hash,
        }

    return branch_hashes


def get_all_branch_hashes_two_remotes(
    workspace_dir: str,
    remote1_name: str,
    remote2_name: str,
    limit_branches: Optional[set] = None,
) -> Dict[str, Dict[str, Optional[str]]]:
    """Get commit hashes for all branches comparing two remotes.

    Args:
        workspace_dir: Path to the git repository
        remote1_name: Name of the first remote
        remote2_name: Name of the second remote
        limit_branches: Optional set of branch names to limit checking to

    Returns:
        Dictionary mapping branch names to {'remote1': hash, 'remote2': hash}
    """
    # Get all branches from both remotes
    remote1_branches = get_local_branches(workspace_dir, remote1_name)
    remote2_branches = get_local_branches(workspace_dir, remote2_name)
    all_branches = sorted(set(remote1_branches + remote2_branches))
    
    # Filter branches if limit_branches is specified
    if limit_branches:
        all_branches = [b for b in all_branches if b in limit_branches]
    
    branch_hashes = {}

    for branch_name in all_branches:
        remote1_hash = get_remote_branch_commit(workspace_dir, remote1_name, branch_name)
        remote2_hash = get_remote_branch_commit(workspace_dir, remote2_name, branch_name)

        branch_hashes[branch_name] = {
            "remote1": remote1_hash,
            "remote2": remote2_hash,
        }

    return branch_hashes


def compare_branches(
    branches: Dict[str, Dict[str, Optional[str]]]
) -> ComparisonResult:
    """Compare local and remote branch commit hashes.

    Args:
        branches: Dictionary mapping branch names to {'local': hash, 'remote': hash}

    Returns:
        ComparisonResult with changed, no_remote, and unchanged branches
    """
    changed: Dict[str, BranchComparison] = {}
    no_remote: Dict[str, str] = {}
    unchanged: Dict[str, str] = {}

    for branch_name, data in branches.items():
        local_hash = data.get("local")
        remote_hash = data.get("remote")

        if remote_hash is None:
            # Branch doesn't exist on remote
            if local_hash is not None:
                no_remote[branch_name] = local_hash
        elif local_hash != remote_hash:
            # Local and remote are different - branch has changed
            changed[branch_name] = BranchComparison(
                local=local_hash, remote=remote_hash
            )
        else:
            # Local and remote match - unchanged
            if local_hash is not None:
                unchanged[branch_name] = local_hash

    return ComparisonResult(
        changed=changed, no_remote=no_remote, unchanged=unchanged
    )


def compare_two_remotes(
    branches: Dict[str, Dict[str, Optional[str]]]
) -> RemoteToRemoteComparisonResult:
    """Compare two remotes' branch commit hashes.

    Args:
        branches: Dictionary mapping branch names to {'remote1': hash, 'remote2': hash}

    Returns:
        RemoteToRemoteComparisonResult with changed, no_remote1, no_remote2, and unchanged branches
    """
    changed: Dict[str, RemoteBranchComparison] = {}
    no_remote1: Dict[str, str] = {}
    no_remote2: Dict[str, str] = {}
    unchanged: Dict[str, str] = {}

    for branch_name, data in branches.items():
        remote1_hash = data.get("remote1")
        remote2_hash = data.get("remote2")

        if remote1_hash is None and remote2_hash is None:
            # Branch doesn't exist on either remote (shouldn't happen, but handle it)
            continue
        elif remote1_hash is None:
            # Branch only exists on remote2
            if remote2_hash is not None:
                no_remote1[branch_name] = remote2_hash
        elif remote2_hash is None:
            # Branch only exists on remote1
            if remote1_hash is not None:
                no_remote2[branch_name] = remote1_hash
        elif remote1_hash != remote2_hash:
            # Remotes are different - branch has changed
            changed[branch_name] = RemoteBranchComparison(
                remote1=remote1_hash, remote2=remote2_hash
            )
        else:
            # Both remotes match - unchanged
            unchanged[branch_name] = remote1_hash

    return RemoteToRemoteComparisonResult(
        changed=changed,
        no_remote1=no_remote1,
        no_remote2=no_remote2,
        unchanged=unchanged,
    )


def set_teamcity_parameter(name: str, value: str) -> None:
    """Emit a TeamCity service message to set a build parameter."""
    # Simple implementation – caller is responsible for passing already-escaped value
    print(f"##teamcity[setParameter name='{name}' value='{value}']")


def print_comparison_result(result: ComparisonResult, remote_name: str):
    """Print the comparison results.

    Args:
        result: ComparisonResult object
        remote_name: Name of the remote
    """
    has_changes = False

    if result.changed:
        has_changes = True
        print("\n" + "=" * 80)
        print(f"WARNING: BRANCHES CHANGED on remote '{remote_name}':")
        print("=" * 80)
        for branch_name, comp in result.changed.items():
            print(f"\n  Branch: {branch_name}")
            print(f"    Local commit:  {comp.local}")
            print(f"    Remote commit: {comp.remote}")

    if result.no_remote:
        print("\n" + "=" * 80)
        print(f"INFO: BRANCHES NOT ON REMOTE '{remote_name}':")
        print("=" * 80)
        for branch_name, local_hash in result.no_remote.items():
            print(f"  {branch_name}: {local_hash[:12]}... (local only)")

    if not has_changes:
        print("\n" + "=" * 80)
        print(f"OK: NO CHANGES DETECTED on remote '{remote_name}'")
        print("=" * 80)
        if result.unchanged:
            print("\nBranches (local matches remote):")
            for branch_name, commit_hash in result.unchanged.items():
                print(f"  {branch_name}: {commit_hash[:12]}...")
    else:
        if result.unchanged:
            print("\n" + "=" * 80)
            print(f"OK: UNCHANGED BRANCHES on remote '{remote_name}':")
            print("=" * 80)
            for branch_name, commit_hash in result.unchanged.items():
                print(f"  {branch_name}: {commit_hash[:12]}...")


def print_remote_comparison_result(
    result: RemoteToRemoteComparisonResult, remote1_name: str, remote2_name: str
):
    """Print the comparison results between two remotes.

    Args:
        result: RemoteToRemoteComparisonResult object
        remote1_name: Name of the first remote
        remote2_name: Name of the second remote
    """
    has_changes = False

    if result.changed:
        has_changes = True
        print("\n" + "=" * 80)
        print(f"WARNING: BRANCHES DIFFER between '{remote1_name}' and '{remote2_name}':")
        print("=" * 80)
        for branch_name, comp in result.changed.items():
            print(f"\n  Branch: {branch_name}")
            print(f"    {remote1_name} commit: {comp.remote1}")
            print(f"    {remote2_name} commit: {comp.remote2}")

    if result.no_remote1:
        print("\n" + "=" * 80)
        print(f"INFO: BRANCHES ONLY ON '{remote2_name}' (not on '{remote1_name}'):")
        print("=" * 80)
        for branch_name, remote2_hash in result.no_remote1.items():
            print(f"  {branch_name}: {remote2_hash[:12]}...")

    if result.no_remote2:
        print("\n" + "=" * 80)
        print(f"INFO: BRANCHES ONLY ON '{remote1_name}' (not on '{remote2_name}'):")
        print("=" * 80)
        for branch_name, remote1_hash in result.no_remote2.items():
            print(f"  {branch_name}: {remote1_hash[:12]}...")

    if not has_changes:
        print("\n" + "=" * 80)
        print(f"OK: NO DIFFERENCES DETECTED between '{remote1_name}' and '{remote2_name}'")
        print("=" * 80)
        if result.unchanged:
            print("\nBranches (both remotes match):")
            for branch_name, commit_hash in result.unchanged.items():
                print(f"  {branch_name}: {commit_hash[:12]}...")
    else:
        if result.unchanged:
            print("\n" + "=" * 80)
            print(f"OK: UNCHANGED BRANCHES (match on both remotes):")
            print("=" * 80)
            for branch_name, commit_hash in result.unchanged.items():
                print(f"  {branch_name}: {commit_hash[:12]}...")


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Detect if branches on a git remote have changed",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s /path/to/repo --remote origin
  %(prog)s /path/to/repo --remote destination
        """,
    )

    parser.add_argument(
        "workspace_directory",
        help="Path to the git repository",
    )

    parser.add_argument(
        "--remote",
        required=True,
        help="Name of the remote to check (e.g., 'origin', 'destination')",
    )

    parser.add_argument(
        "--second_remote",
        required=False,
        help="If this is set, also check the second remote instead of the first remote",
    )

    parser.add_argument(
        "--hint_teamcity",
        action="store_true",
        help="When set, emit TeamCity parameters describing whether remote changed "
        "and a JSON with branch hashes.",
    )

    parser.add_argument(
        "--limit_to_branch",
        default="",
        help="Limit branch checking to specified branches, separated by semicolon (e.g., 'master;develop'). "
        "Default is empty, which checks all branches.",
    )

    args = parser.parse_args()

    workspace_dir = os.path.normpath(args.workspace_directory)
    remote_name = args.remote

    # Parse limit_to_branch parameter
    limit_branches = None
    if args.limit_to_branch:
        limit_branches = {
            branch.strip()
            for branch in args.limit_to_branch.split(";")
            if branch.strip()
        }
        if limit_branches:
            print(f"Limiting branch check to: {', '.join(sorted(limit_branches))}")

    # Validate workspace directory
    if not os.path.isdir(workspace_dir):
        print(f"Error: Workspace directory '{workspace_dir}' does not exist")
        sys.exit(1)

    # Validate remote exists
    try:
        cmd = ["git", "remote", "get-url", remote_name]
        subprocess.run(cmd, cwd=workspace_dir, capture_output=True, check=True)
    except subprocess.CalledProcessError:
        print(f"Error: Remote '{remote_name}' not found")
        print("Available remotes:")
        try:
            cmd = ["git", "remote", "-v"]
            output = run_command_and_get_return_info(
                cmd, cwd=workspace_dir, shell=False
            )
            for line in output.strip().splitlines():
                if line.strip():
                    print(f"  - {line.split()[0]}")
        except:
            pass
        sys.exit(1)

    # Get local branches and compare with remote
    print(f"Checking local branches against remote '{remote_name}'...")
    branches = get_all_branch_hashes(workspace_dir, remote_name, limit_branches)

    if not branches:
        print(f"Error: No local branches found")
        sys.exit(1)

    # Compare local vs remote
    result = compare_branches(branches)
    print_comparison_result(result, remote_name)

    # If second_remote is specified, also compare remote vs second_remote
    remote_to_remote_result = None
    if args.second_remote:
        second_remote_name = args.second_remote
        
        # Validate second remote exists
        try:
            cmd = ["git", "remote", "get-url", second_remote_name]
            subprocess.run(cmd, cwd=workspace_dir, capture_output=True, check=True)
        except subprocess.CalledProcessError:
            print(f"\nError: Second remote '{second_remote_name}' not found")
            print("Available remotes:")
            try:
                cmd = ["git", "remote", "-v"]
                output = run_command_and_get_return_info(
                    cmd, cwd=workspace_dir, shell=False
                )
                for line in output.strip().splitlines():
                    if line.strip():
                        print(f"  - {line.split()[0]}")
            except:
                pass
            sys.exit(1)

        # Get branch hashes for both remotes and compare
        print(f"\nChecking remote '{remote_name}' against remote '{second_remote_name}'...")
        remote_branches = get_all_branch_hashes_two_remotes(
            workspace_dir, remote_name, second_remote_name, limit_branches
        )

        if not remote_branches:
            print(f"Error: No branches found on either remote")
        else:
            remote_to_remote_result = compare_two_remotes(remote_branches)
            print_remote_comparison_result(
                remote_to_remote_result, remote_name, second_remote_name
            )

    print("env.git.remoteChanged: \n", result.changed)
    print("env.git.remoteBranchesJson: \n", result.to_dict())
    if remote_to_remote_result:
        print("env.git.remoteToRemoteChanged: \n", remote_to_remote_result.changed)
        print("env.git.remoteToRemoteBranchesJson: \n", remote_to_remote_result.to_dict())

    # Optional TeamCity hints
    if True:
        # change_detected: true if any branch has changed on remote
        change_detected = bool(result.changed or (remote_to_remote_result and remote_to_remote_result.changed))
        if args.hint_teamcity:
            set_teamcity_parameter(
                "env.git.remoteChanged", "true" if change_detected else "false"
            )

        merged_dict = deep_merge(result.to_dict(), remote_to_remote_result.to_dict())
        
        result_json = json.dumps(merged_dict, ensure_ascii=False)
        print("result_json: \n", result_json)
        if args.hint_teamcity:

            # Encode JSON as Base64URL so it can be safely passed through HTTP/CLI parameters
            import base64

            encoded_json = base64.urlsafe_b64encode(
                result_json.encode("utf-8")
            ).decode("ascii").rstrip("=")
            set_teamcity_parameter("env.git.remoteBranchesJson", encoded_json)

            print("encoded_json: \n", encoded_json)


if __name__ == "__main__":
    main()
