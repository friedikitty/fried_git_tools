#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Git Bare Repository Initialization Script with Branch Sync Configuration

This script initializes a bare Git repository and configures it to fetch
specific branches from a remote repository. It's useful for creating mirror
repositories or syncing specific branches.

Features:
- Creates a bare Git repository
- Configures remote with custom branch fetch specifications
- Supports multiple branches with explicit refspecs
- Can be re-run safely (skips existing configurations)

Usage:
    python init_git_sync_folder.py
    python init_git_sync_folder.py --repo-path /custom/path
    python init_git_sync_folder.py --remote-url ssh://git@example.com/repo.git
    python init_git_sync_folder.py --branches master develop release
"""

import os
import subprocess
import argparse
import sys
from pathlib import Path

# Import run_command from the external module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "unreal_build_script"))
from run_command import run_command


def init_bare_repository(repo_path):
    """
    Initialize a bare Git repository.

    Args:
        repo_path: Path where the bare repository should be created

    Returns:
        bool: True if successful, False otherwise
    """
    print(f"\n{'='*80}")
    print(f"Initializing bare repository at: {repo_path}")
    print(f"{'='*80}\n")

    # Create directory if it doesn't exist
    repo_path_obj = Path(repo_path)
    repo_path_obj.mkdir(parents=True, exist_ok=True)

    # Check if already initialized
    if (repo_path_obj / "HEAD").exists():
        print(f"[WARNING]  Repository already exists at {repo_path}")
        response = input("Continue with existing repository? (y/n): ").strip().lower()
        if response != "y":
            print("Aborted by user")
            return False
        print("[SUCEEEDED] Using existing repository")
        return True

    # Initialize bare repository
    result = run_command("git init --bare", cwd=repo_path, check=False)

    if result.returncode == 0:
        print(f"[SUCEEEDED] Bare repository initialized at {repo_path}")
        return True
    else:
        print(f"[FAILED] Failed to initialize repository")
        return False


def configure_remote(repo_path, remote_name, remote_url):
    """
    Configure a remote for the repository.

    Args:
        repo_path: Path to the repository
        remote_name: Name of the remote (e.g., 'origin')
        remote_url: URL of the remote repository

    Returns:
        bool: True if successful, False otherwise
    """
    print(f"\n{'='*80}")
    print(f"Configuring remote: {remote_name}")
    print(f"URL: {remote_url}")
    print(f"{'='*80}\n")

    # Check if remote already exists
    result = run_command(
        f"git remote get-url {remote_name}",
        cwd=repo_path,
        check=False,
        capture_output=True,
    )

    if result.returncode == 0:
        existing_url = result.stdout.strip()
        print(
            f"[WARNING]  Remote '{remote_name}' already exists with URL: {existing_url}"
        )

        if existing_url == remote_url:
            print(f"[SUCEEEDED] Remote URL matches, no changes needed")
            return True
        else:
            print(f"Updating remote URL to: {remote_url}")
            result = run_command(
                f"git remote set-url {remote_name} {remote_url}",
                cwd=repo_path,
                check=False,
            )
            if result.returncode == 0:
                print(f"[SUCEEEDED] Remote URL updated")
                return True
            else:
                print(f"[FAILED] Failed to update remote URL")
                return False

    # Add new remote
    result = run_command(
        f"git remote add {remote_name} {remote_url}", cwd=repo_path, check=False
    )

    if result.returncode == 0:
        print(f"[SUCEEEDED] Remote '{remote_name}' added successfully")
        return True
    else:
        print(f"[FAILED] Failed to add remote '{remote_name}'")
        return False


def configure_branch_fetch(repo_path, remote_name, branches, replace_first=True):
    """
    Configure branch-specific fetch refspecs for a remote.

    Args:
        repo_path: Path to the repository
        remote_name: Name of the remote
        branches: List of branch names to configure
        replace_first: If True, replace the first refspec; otherwise add all

    Returns:
        bool: True if all configurations successful, False otherwise
    """
    print(f"\n{'='*80}")
    print(f"Configuring fetch refspecs for branches: {', '.join(branches)}")
    print(f"{'='*80}\n")

    success = True

    for i, branch in enumerate(branches):
        refspec = f"+refs/heads/{branch}:refs/heads/{branch}"

        if i == 0 and replace_first:
            # First branch: use 'git config' to replace default refspec
            cmd = f'git config remote.{remote_name}.fetch "{refspec}"'
            action = "Setting"
        else:
            # Subsequent branches: use 'git config --add' to add additional refspecs
            cmd = f'git config --add remote.{remote_name}.fetch "{refspec}"'
            action = "Adding"

        print(f"{action} refspec for branch '{branch}': {refspec}")
        result = run_command(cmd, cwd=repo_path, check=False)

        if result.returncode == 0:
            print(f"[SUCEEEDED] Refspec configured for '{branch}'")
        else:
            print(f"[FAILED] Failed to configure refspec for '{branch}'")
            success = False

    return success


def fetch_from_remote(repo_path, remote_name):
    """
    Fetch branches from the configured remote.

    Args:
        repo_path: Path to the repository
        remote_name: Name of the remote to fetch from

    Returns:
        bool: True if successful, False otherwise
    """
    print(f"\n{'='*80}")
    print(f"Fetching from remote: {remote_name}")
    print(f"{'='*80}\n")

    result = run_command(f"git fetch {remote_name}", cwd=repo_path, check=False)

    if result.returncode == 0:
        print(f"[SUCEEEDED] Successfully fetched from '{remote_name}'")
        return True
    else:
        print(f"[FAILED] Failed to fetch from '{remote_name}'")
        return False


def verify_configuration(repo_path, remote_name, branches):
    """
    Verify the repository configuration.

    Args:
        repo_path: Path to the repository
        remote_name: Name of the remote
        branches: List of expected branches
    """
    print(f"\n{'='*80}")
    print(f"Verification Report")
    print(f"{'='*80}\n")

    # Check remote configuration
    print(f"Remote Configuration for '{remote_name}':")
    result = run_command(
        f"git config --get-all remote.{remote_name}.fetch", cwd=repo_path, check=False
    )

    if result.returncode == 0:
        configured_refspecs = result.stdout.strip().split("\n")
        print(f"[SUCEEEDED] Configured refspecs ({len(configured_refspecs)}):")
        for refspec in configured_refspecs:
            print(f"  - {refspec}")
    else:
        print(f"[FAILED] No fetch refspecs configured")

    # Check available branches
    print(f"\nAvailable Branches:")
    result = run_command("git branch -a", cwd=repo_path, check=False)

    if result.returncode == 0 and result.stdout.strip():
        available_branches = [
            line.strip().replace("* ", "").replace("remotes/", "")
            for line in result.stdout.strip().split("\n")
        ]
        print(f"[SUCEEEDED] Found {len(available_branches)} branches:")
        for branch in available_branches:
            print(f"  - {branch}")

        # Check if expected branches are present
        print(f"\nExpected Branches Status:")
        for branch in branches:
            if any(branch in b for b in available_branches):
                print(f"  [SUCEEEDED] {branch} - Found")
            else:
                print(f"  [FAILED] {branch} - Not found")
    else:
        print(f"[WARNING]  No branches found (this is normal before first fetch)")


def main():
    """Main function to orchestrate repository initialization and configuration."""

    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="Initialize a bare Git repository with branch sync configuration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Use default settings
  %(prog)s
  
  # Custom repository path
  %(prog)s --repo-path /path/to/repo
  
  # Custom remote URL
  %(prog)s --remote-url ssh://git@github.com/user/repo.git
  
  # Custom branches
  %(prog)s --branches main develop staging
  
  # All custom settings
  %(prog)s --repo-path /custom/path \\
           --remote-url ssh://git@example.com/repo.git \\
           --remote-name upstream \\
           --branches main feature-1 feature-2 \\
           --no-fetch
        """,
    )

    parser.add_argument(
        "--repo-path", type=str, required=True, help="Path to the bare repository"
    )

    parser.add_argument(
        "--remote-url",
        type=str,
        required=True,
        help="URL of the remote repository (like: ssh://git@xxxx.com)",
    )

    parser.add_argument(
        "--remote-name",
        type=str,
        default="origin",
        help="Name of the remote (default: origin)",
    )

    parser.add_argument(
        "--branches",
        nargs="+",
        default=["master"],
        help="List of branches to sync (like: master develop 2025-lts)",
    )

    parser.add_argument(
        "--no-fetch", action="store_true", help="Skip the initial fetch operation"
    )

    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Only verify existing configuration without making changes",
    )

    args = parser.parse_args()

    # Convert to absolute path
    repo_path = os.path.abspath(args.repo_path)

    # Print configuration
    print("\n" + "=" * 80)
    print("Git Bare Repository Initialization")
    print("=" * 80)
    print(f"\nConfiguration:")
    print(f"  Repository Path: {repo_path}")
    print(f"  Remote Name:     {args.remote_name}")
    print(f"  Remote URL:      {args.remote_url}")
    print(f"  Branches:        {', '.join(args.branches)}")
    print(f"  Fetch After:     {'No' if args.no_fetch else 'Yes'}")
    print(f"  Mode:            {'Verify Only' if args.verify_only else 'Initialize'}")
    print("=" * 80 + "\n")

    # Verify-only mode
    if args.verify_only:
        verify_configuration(repo_path, args.remote_name, args.branches)
        return 0

    # Confirmation prompt
    response = input("Proceed with the above configuration? (y/n): ").strip().lower()
    if response != "y":
        print("\nAborted by user")
        return 1

    # Step 1: Initialize bare repository
    if not init_bare_repository(repo_path):
        print("\n[FAILED] Failed to initialize repository")
        return 1

    # Step 2: Configure remote
    if not configure_remote(repo_path, args.remote_name, args.remote_url):
        print("\n[FAILED] Failed to configure remote")
        return 1

    # Step 3: Configure branch fetch refspecs
    if not configure_branch_fetch(repo_path, args.remote_name, args.branches):
        print("\n[WARNING]  Some branch configurations failed, but continuing...")

    # Step 4: Fetch from remote (if not skipped)
    if not args.no_fetch:
        if not fetch_from_remote(repo_path, args.remote_name):
            print("\n[WARNING]  Fetch failed, but configuration is complete")
    else:
        print("\n[WARNING]  Skipping fetch (--no-fetch specified)")

    # Step 5: Verify configuration
    verify_configuration(repo_path, args.remote_name, args.branches)

    # Summary
    print(f"\n{'='*80}")
    print(f"[SUCEEEDED] Repository initialization complete!")
    print(f"{'='*80}")
    print(f"\nRepository location: {repo_path}")
    print(f"\nTo manually fetch updates:")
    print(f"  cd {repo_path}")
    print(f"  git fetch {args.remote_name}")
    print(f"\nTo view all branches:")
    print(f"  git branch -a")
    print(f"\nTo re-run verification:")
    print(f"  python {sys.argv[0]} --verify-only")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
