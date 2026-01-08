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
# sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "unreal_build_script"))
from run_command import run_command

# Import OutputCaptureLogger from local run_command module (same directory)
# Temporarily remove the sys.path entry to import from local module
# sys.path.pop(0)
from run_command import OutputCaptureLogger

# sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "unreal_build_script"))

# Import utility functions
from git_sync_util import sanitize_remote_url


def hint(ui_callback, level, message):
    """
    Unified method to display messages with different levels.

    Args:
        ui_callback: Optional UI callback object for user interactions
        level: Message level - "info", "warning", "error", "success"
        message: Message to display
    """
    if ui_callback:
        if level == "info":
            ui_callback.info(message)
        elif level == "warning":
            ui_callback.warning(message)
        elif level == "error":
            ui_callback.error(message)
        elif level == "success":
            ui_callback.success(message)
    else:
        # CLI mode - format message with appropriate prefix
        if level == "info":
            print(message)
        elif level == "warning":
            # Add [WARNING] prefix if not already present
            if "[WARNING]" not in message:
                print(f"[WARNING]  {message}")
            else:
                print(message)
        elif level == "error":
            # Add [ERROR] or [FAILED] prefix if not already present
            if "[ERROR]" not in message and "[FAILED]" not in message:
                print(f"[ERROR] {message}")
            else:
                print(message)
        elif level == "success":
            # Add [SUCEEEDED] prefix if not already present
            if "[SUCEEEDED]" not in message:
                print(f"[SUCEEEDED] {message}")
            else:
                print(message)


def ask_yesno(ui_callback, message):
    """
    Unified method to ask a yes/no question.

    Args:
        ui_callback: Optional UI callback object for user interactions
        message: Question to ask the user

    Returns:
        bool: True for yes, False for no
    """
    if ui_callback:
        return bool(ui_callback.ask_yesno(message))
    else:
        while True:
            resp = input(f"{message} (y/n): ").strip().lower()
            if resp in ("y", "yes"):
                return True
            if resp in ("n", "no"):
                return False
            print("Please enter 'y' or 'n'.")


def init_bare_repository(repo_path, ui_callback=None):
    """
    Initialize a bare Git repository.

    Args:
        repo_path: Path where the bare repository should be created
        ui_callback: Optional UI callback object for user interactions

    Returns:
        bool: True if successful, False otherwise
    """
    hint(
        ui_callback,
        "info",
        f"\n{'='*80}\nInitializing bare repository at: {repo_path}\n{'='*80}\n",
    )

    # Create directory if it doesn't exist
    repo_path_obj = Path(repo_path)
    repo_path_obj.mkdir(parents=True, exist_ok=True)

    # Check if already initialized
    if (repo_path_obj / "HEAD").exists():
        hint(ui_callback, "warning", f"Repository already exists at {repo_path}")
        if not ask_yesno(ui_callback, "Continue with existing repository?"):
            hint(ui_callback, "info", "Aborted by user")
            return False
        hint(ui_callback, "success", "Using existing repository")
        return True

    # Initialize bare repository
    result = run_command("git init --bare", cwd=repo_path)

    if result == 0:
        hint(ui_callback, "success", f"Bare repository initialized at {repo_path}")
        return True
    else:
        hint(ui_callback, "error", "Failed to initialize repository")
        return False


def configure_remote(repo_path, remote_name, remote_url, ui_callback=None):
    """
    Configure a remote for the repository.

    Args:
        repo_path: Path to the repository
        remote_name: Name of the remote (e.g., 'origin')
        remote_url: URL of the remote repository
        ui_callback: Optional UI callback object for user interactions

    Returns:
        bool: True if successful, False otherwise
    """
    hint(
        ui_callback,
        "info",
        f"\n{'='*80}\nConfiguring remote: {remote_name}\nURL: {sanitize_remote_url(remote_url)}\n{'='*80}\n",
    )

    # Check if remote already exists
    capture_logger = OutputCaptureLogger(None)
    result = run_command(
        f"git remote get-url {remote_name}", cwd=repo_path, logger=capture_logger
    )

    if result == 0:
        existing_url = capture_logger.get_output().strip()
        warning_msg = f"Remote '{remote_name}' already exists with URL: {sanitize_remote_url(existing_url)}"
        hint(ui_callback, "warning", warning_msg)

        if existing_url == remote_url:
            hint(ui_callback, "success", "Remote URL matches, no changes needed")
            return True
        else:
            hint(
                ui_callback,
                "info",
                f"Updating remote URL to: {sanitize_remote_url(remote_url)}",
            )
            result = run_command(
                f"git remote set-url {remote_name} {remote_url}",
                cwd=repo_path,
            )
            if result == 0:
                hint(ui_callback, "success", "Remote URL updated")
                return True
            else:
                hint(ui_callback, "error", "Failed to update remote URL")
                return False

    # Add new remote
    result = run_command(f"git remote add {remote_name} {remote_url}", cwd=repo_path)

    if result == 0:
        hint(ui_callback, "success", f"Remote '{remote_name}' added successfully")
        return True
    else:
        hint(ui_callback, "error", f"Failed to add remote '{remote_name}'")
        return False


def configure_branch_fetch(
    repo_path, remote_name, branches, replace_first=True, ui_callback=None
):
    """
    Configure branch-specific fetch refspecs for a remote.

    Args:
        repo_path: Path to the repository
        remote_name: Name of the remote
        branches: List of branch names to configure
        replace_first: If True, replace the first refspec; otherwise add all
        ui_callback: Optional UI callback object for user interactions

    Returns:
        bool: True if all configurations successful, False otherwise
    """
    hint(
        ui_callback,
        "info",
        f"\n{'='*80}\nConfiguring fetch refspecs for branches: {', '.join(branches)}\n{'='*80}\n",
    )

    success = True

    for i, branch in enumerate(branches):
        refspec = f"+refs/heads/{branch}:refs/remotes/{remote_name}/{branch}"

        if i == 0 and replace_first:
            # First branch: use 'git config' to replace default refspec
            cmd = f'git config remote.{remote_name}.fetch "{refspec}"'
            action = "Setting"
        else:
            # Subsequent branches: use 'git config --add' to add additional refspecs
            cmd = f'git config --add remote.{remote_name}.fetch "{refspec}"'
            action = "Adding"

        hint(ui_callback, "info", f"{action} refspec for branch '{branch}': {refspec}")
        result = run_command(cmd, cwd=repo_path)

        if result == 0:
            hint(ui_callback, "success", f"Refspec configured for '{branch}'")
        else:
            hint(ui_callback, "error", f"Failed to configure refspec for '{branch}'")
            success = False

    return success


def fetch_from_remote(repo_path, remote_name, ui_callback=None):
    """
    Fetch branches from the configured remote.

    Args:
        repo_path: Path to the repository
        remote_name: Name of the remote to fetch from
        ui_callback: Optional UI callback object for user interactions

    Returns:
        bool: True if successful, False otherwise
    """
    hint(
        ui_callback,
        "info",
        f"\n{'='*80}\nFetching from remote: {remote_name}\n{'='*80}\n",
    )

    result = run_command(f"git fetch {remote_name}", cwd=repo_path)

    if result == 0:
        hint(ui_callback, "success", f"Successfully fetched from '{remote_name}'")
        return True
    else:
        hint(ui_callback, "error", f"Failed to fetch from '{remote_name}'")
        return False


def verify_configuration(
    repo_path, remote_name, branches, destination_remote_name=None, ui_callback=None
):
    """
    Verify the repository configuration.

    Args:
        repo_path: Path to the repository
        remote_name: Name of the remote
        branches: List of expected branches
        destination_remote_name: Optional name of the destination remote
        ui_callback: Optional UI callback object for user interactions
    """
    hint(ui_callback, "info", f"\n{'='*80}\nVerification Report\n{'='*80}\n")

    # Check remote configuration
    hint(ui_callback, "info", f"Remote Configuration for '{remote_name}':")
    capture_logger = OutputCaptureLogger(None)
    result = run_command(
        f"git config --get-all remote.{remote_name}.fetch",
        cwd=repo_path,
        logger=capture_logger,
    )

    if result == 0:
        output = capture_logger.get_output().strip()
        configured_refspecs = output.split("\n") if output else []
        hint(
            ui_callback, "success", f"Configured refspecs ({len(configured_refspecs)}):"
        )
        for refspec in configured_refspecs:
            hint(ui_callback, "info", f"  - {refspec}")
    else:
        hint(ui_callback, "error", "No fetch refspecs configured")

    # Check destination remote configuration (if provided)
    if destination_remote_name:
        hint(
            ui_callback,
            "info",
            f"\nDestination Remote Configuration for '{destination_remote_name}':",
        )
        capture_logger = OutputCaptureLogger(None)
        result = run_command(
            f"git remote get-url {destination_remote_name}",
            cwd=repo_path,
            logger=capture_logger,
        )
        if result == 0:
            dest_url = capture_logger.get_output().strip()
            hint(
                ui_callback,
                "success",
                f"Destination remote URL: {sanitize_remote_url(dest_url)}",
            )
        else:
            hint(
                ui_callback,
                "error",
                f"Destination remote '{destination_remote_name}' not found",
            )

    # Check available branches
    hint(ui_callback, "info", f"\nAvailable Branches:")
    capture_logger = OutputCaptureLogger(None)
    result = run_command("git branch -a", cwd=repo_path, logger=capture_logger)

    if result == 0:
        output = capture_logger.get_output().strip()
        if output:
            available_branches = [
                line.strip().replace("* ", "").replace("remotes/", "")
                for line in output.split("\n")
            ]
            hint(ui_callback, "success", f"Found {len(available_branches)} branches:")
            for branch in available_branches:
                hint(ui_callback, "info", f"  - {branch}")

            # Check if expected branches are present
            hint(ui_callback, "info", f"\nExpected Branches Status:")
            for branch in branches:
                if any(branch in b for b in available_branches):
                    hint(ui_callback, "success", f"  {branch} - Found")
                else:
                    hint(ui_callback, "error", f"  {branch} - Not found")
        else:
            hint(
                ui_callback,
                "warning",
                "No branches found (this is normal before first fetch)",
            )
    else:
        hint(
            ui_callback,
            "warning",
            "No branches found (this is normal before first fetch)",
        )


EPILOG = """
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
  
  # With destination remote
  %(prog)s --repo-path /custom/path \\
           --remote-url ssh://git@source.com/repo.git \\
           --destination-remote-url ssh://git@dest.com/repo.git \\
           --destination-remote-name destination \\
           --branches main develop
        """

DESCRIPTION = "Initialize a bare Git repository with branch sync configuration"


def argument_pars(parser, use_gooey=False):

    parser.add_argument(
        "--repo-path", type=str, required=True, help="Path to the bare repository"
    )

    parser.add_argument(
        "--remote-name",
        type=str,
        default="origin",
        help="Name of the remote (default: origin)",
    )

    parser.add_argument(
        "--remote-url",
        type=str,
        required=True,
        help="URL of the remote repository (like: ssh://git@xxxx.com)",
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

    parser.add_argument(
        "--destination-remote-url",
        "--dru",
        type=str,
        dest="destination_remote_url",
        help="URL of the destination remote repository (optional)",
    )

    parser.add_argument(
        "--destination-remote-name",
        "--drn",
        type=str,
        dest="destination_remote_name",
        default="destination",
        help="Name of the destination remote (default: destination)",
    )

    return parser.parse_args()


def main():
    """Main function to orchestrate repository initialization and configuration."""

    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description=DESCRIPTION,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=EPILOG,
    )
    args = argument_pars(parser)
    main_core(args)


def main_core(args, ui_callback=None):
    # Validate required arguments (needed when using Gooey)
    if not args.repo_path:
        hint(ui_callback, "error", "--repo-path is required")
        return 1

    if not args.remote_url:
        hint(ui_callback, "error", "--remote-url is required")
        return 1

    # Convert to absolute path
    repo_path = os.path.abspath(args.repo_path)
    if repo_path.endswith("/") or repo_path.endswith("\\"):
        repo_path = repo_path[:-1]

    # Print configuration
    config_msg = (
        f"\n{'='*80}\n"
        f"Git Bare Repository Initialization\n"
        f"{'='*80}\n\n"
        f"Configuration:\n"
        f"  Repository Path: {repo_path}\n"
        f"  Remote Name:     {args.remote_name}\n"
        f"  Remote URL:      {sanitize_remote_url(args.remote_url)}\n"
    )
    if args.destination_remote_url:
        config_msg += (
            f"  Destination Remote Name: {args.destination_remote_name}\n"
            f"  Destination Remote URL:  {sanitize_remote_url(args.destination_remote_url)}\n"
        )
    config_msg += (
        f"  Branches:        {', '.join(args.branches)}\n"
        f"  Fetch After:     {'No' if args.no_fetch else 'Yes'}\n"
        f"  Mode:            {'Verify Only' if args.verify_only else 'Initialize'}\n"
        f"{'='*80}\n"
    )

    hint(ui_callback, "info", config_msg)

    # Verify-only mode
    if args.verify_only:
        verify_configuration(
            repo_path,
            args.remote_name,
            args.branches,
            args.destination_remote_name if args.destination_remote_url else None,
            ui_callback,
        )
        return 0

    # Confirmation prompt
    if not ask_yesno(
        ui_callback, f"{config_msg}\nProceed with the above configuration?"
    ):
        hint(ui_callback, "info", "\nAborted by user")
        return 1

    if not os.path.exists(repo_path):
        if not ask_yesno(
            ui_callback, f"Repository path '{repo_path}' does not exist. Create it?"
        ):
            hint(ui_callback, "info", "\nAborted by user")
            return 1
        os.makedirs(repo_path)
        hint(ui_callback, "success", f"Repository path '{repo_path}' created")

    # Step 1: Initialize bare repository
    if not init_bare_repository(repo_path, ui_callback):
        hint(ui_callback, "error", "\nFailed to initialize repository")
        return 1

    # Step 2: Configure remote
    if not configure_remote(repo_path, args.remote_name, args.remote_url, ui_callback):
        hint(ui_callback, "error", "\nFailed to configure remote")
        return 1

    # Step 3: Configure branch fetch refspecs
    if not configure_branch_fetch(
        repo_path, args.remote_name, args.branches, ui_callback=ui_callback
    ):
        hint(
            ui_callback,
            "warning",
            "\nSome branch configurations failed, but continuing...",
        )

    # Step 3.5: Configure destination remote (if provided)
    if args.destination_remote_url:
        if not configure_remote(
            repo_path,
            args.destination_remote_name,
            args.destination_remote_url,
            ui_callback,
        ):
            hint(
                ui_callback,
                "warning",
                "\nFailed to configure destination remote, but continuing...",
            )

    # Step 4: Fetch from remote (if not skipped)
    if not args.no_fetch:
        if not fetch_from_remote(repo_path, "--all", ui_callback):
            hint(
                ui_callback, "warning", "\nFetch failed, but configuration is complete"
            )
    else:
        hint(ui_callback, "warning", "\nSkipping fetch (--no-fetch specified)")

    # Step 5: Verify configuration
    verify_configuration(
        repo_path,
        args.remote_name,
        args.branches,
        args.destination_remote_name if args.destination_remote_url else None,
        ui_callback,
    )

    # Summary
    summary_msg = (
        f"\n{'='*80}\n"
        f"[SUCEEEDED] Repository initialization complete!\n"
        f"{'='*80}\n"
        f"\nRepository location: {repo_path}\n"
        f"\nTo manually fetch updates:\n"
        f"  cd {repo_path}\n"
        f"  git fetch {args.remote_name}\n"
        f"\nTo view all branches:\n"
        f"  git branch -a\n"
        f"\nTo re-run verification:\n"
        f"  python {sys.argv[0]} --verify-only\n"
    )

    hint(ui_callback, "success", summary_msg)

    return 0


if __name__ == "__main__":
    sys.exit(main())
