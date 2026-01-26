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


def init_repository(repo_path, bare=False, ui_callback=None):
    """
    Initialize a Git repository (bare or non-bare).

    Args:
        repo_path: Path where the repository should be created
        bare: If True, create a bare repository; if False, create a regular repository
        ui_callback: Optional UI callback object for user interactions

    Returns:
        bool: True if successful, False otherwise
    """
    repo_type = "bare" if bare else "regular"
    hint(
        ui_callback,
        "info",
        f"\n{'='*80}\nInitializing {repo_type} repository at: {repo_path}\n{'='*80}\n",
    )

    # Create directory if it doesn't exist
    repo_path_obj = Path(repo_path)
    repo_path_obj.mkdir(parents=True, exist_ok=True)

    # Check if already initialized
    if bare:
        check_path = repo_path_obj / "HEAD"
    else:
        check_path = repo_path_obj / ".git" / "HEAD"

    if check_path.exists():
        hint(ui_callback, "warning", f"Repository already exists at {repo_path}")
        if not ask_yesno(ui_callback, "Continue with existing repository?"):
            hint(ui_callback, "info", "Aborted by user")
            return False
        hint(ui_callback, "success", "Using existing repository")
        return True

    # Initialize repository
    if bare:
        result = run_command("git init --bare", cwd=repo_path)
    else:
        result = run_command("git init", cwd=repo_path)

    if result == 0:
        hint(
            ui_callback,
            "success",
            f"{repo_type.capitalize()} repository initialized at {repo_path}",
        )
        return True
    else:
        hint(ui_callback, "error", "Failed to initialize repository")
        return False


def init_git_lfs(repo_path, ui_callback=None):
    """
    Initialize Git LFS for the bare repository (if available).

    This ensures LFS configuration is present so that LFS objects can be
    fetched/pushed correctly when this bare repo is used as a mirror.

    Args:
        repo_path: Path to the (bare) repository
        ui_callback: Optional UI callback object for user interactions

    Returns:
        bool: True if LFS is initialized or not needed, False if initialization failed
    """
    hint(
        ui_callback,
        "info",
        f"\n{'='*80}\nInitializing Git LFS in repository\n{'='*80}\n",
    )

    # First, check if git-lfs is installed
    check_cmd = "git lfs version"
    result = run_command(check_cmd, cwd=repo_path)
    if result != 0:
        hint(
            ui_callback,
            "warning",
            "Git LFS does not appear to be installed or available in PATH. "
            "Skipping LFS initialization.",
        )
        return False

    # Initialize LFS configuration in this repo (local only, no global changes)
    init_cmd = "git lfs install --local"
    result = run_command(init_cmd, cwd=repo_path)

    if result == 0:
        # Configure LFS filter settings
        filter_configs = [
            ("filter.lfs.smudge", "git-lfs smudge -- %f"),
            ("filter.lfs.process", "git-lfs filter-process"),
            ("filter.lfs.required", "true"),
            ("filter.lfs.clean", "git-lfs clean -- %f"),
        ]

        for config_key, config_value in filter_configs:
            config_cmd = f'git config --local {config_key} "{config_value}"'
            config_result = run_command(config_cmd, cwd=repo_path)
            if config_result != 0:
                hint(
                    ui_callback,
                    "warning",
                    f"Failed to set LFS config {config_key}. LFS may not work correctly.",
                )

        hint(ui_callback, "success", "Git LFS initialized for this repository")
        return True

    hint(
        ui_callback,
        "warning",
        "Failed to initialize Git LFS for this repository. LFS objects may not sync correctly.",
    )
    return False


def create_default_gitignore(repo_path, ui_callback=None):
    """
    Create a default .gitignore file and add it to the repository.

    Args:
        repo_path: Path to the (bare) repository
        ui_callback: Optional UI callback object for user interactions

    Returns:
        str: Blob hash of the created file, or None if failed
    """
    default_gitignore = """# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
venv/
env/
ENV/
*.egg-info/
dist/
build/

# IDE
.vscode/
.idea/
*.swp
*.swo
*.sublime-*

# OS
.DS_Store
Thumbs.db
desktop.ini

# Temporary files
*.tmp
*.temp
*.log
*.bak
*.swp
*~

# User-specific files
*.user
*.suo
*.userosscache
*.sln.docstates

# Build artifacts
*.o
*.obj
*.exe
*.dll
*.lib
*.a
*.so
*.dylib
"""

    try:
        import subprocess
        import tempfile

        with tempfile.NamedTemporaryFile(mode="wb", delete=False) as f:
            f.write(default_gitignore.encode("utf-8"))
            temp_path = f.name

        try:
            # Use git hash-object to create the blob
            with open(temp_path, "rb") as f:
                proc = subprocess.Popen(
                    ["git", "hash-object", "-w", "--stdin"],
                    cwd=repo_path,
                    stdin=f,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                stdout, stderr = proc.communicate()
                if proc.returncode == 0:
                    blob_hash = stdout.decode("utf-8").strip()
                    hint(ui_callback, "success", f"Created default .gitignore file")
                    return blob_hash
                else:
                    hint(
                        ui_callback,
                        "warning",
                        f"Failed to create .gitignore blob: {stderr.decode('utf-8', errors='replace')}",
                    )
                    return None
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)
    except Exception as e:
        hint(ui_callback, "warning", f"Failed to create .gitignore: {str(e)}")
        return None


def create_default_gitattributes(repo_path, ui_callback=None):
    """
    Create a default .gitattributes file for Git LFS and add it to the repository.

    Args:
        repo_path: Path to the (bare) repository
        ui_callback: Optional UI callback object for user interactions

    Returns:
        str: Blob hash of the created file, or None if failed
    """
    default_gitattributes = """# Git LFS attributes
# Common binary and large file patterns

# Images
*.png filter=lfs diff=lfs merge=lfs -text
*.jpg filter=lfs diff=lfs merge=lfs -text
*.jpeg filter=lfs diff=lfs merge=lfs -text
*.gif filter=lfs diff=lfs merge=lfs -text
*.bmp filter=lfs diff=lfs merge=lfs -text
*.tiff filter=lfs diff=lfs merge=lfs -text
*.ico filter=lfs diff=lfs merge=lfs -text
*.psd filter=lfs diff=lfs merge=lfs -text

# Audio/Video
*.mp3 filter=lfs diff=lfs merge=lfs -text
*.mp4 filter=lfs diff=lfs merge=lfs -text
*.avi filter=lfs diff=lfs merge=lfs -text
*.mov filter=lfs diff=lfs merge=lfs -text
*.wav filter=lfs diff=lfs merge=lfs -text
*.flv filter=lfs diff=lfs merge=lfs -text

# Archives
*.zip filter=lfs diff=lfs merge=lfs -text
*.tar filter=lfs diff=lfs merge=lfs -text
*.gz filter=lfs diff=lfs merge=lfs -text
*.7z filter=lfs diff=lfs merge=lfs -text
*.rar filter=lfs diff=lfs merge=lfs -text

# Binaries
*.exe filter=lfs diff=lfs merge=lfs -text
*.dll filter=lfs diff=lfs merge=lfs -text
*.so filter=lfs diff=lfs merge=lfs -text
*.dylib filter=lfs diff=lfs merge=lfs -text
*.bin filter=lfs diff=lfs merge=lfs -text

# Large data files
*.db filter=lfs diff=lfs merge=lfs -text
*.sqlite filter=lfs diff=lfs merge=lfs -text
*.dump filter=lfs diff=lfs merge=lfs -text
"""

    try:
        import subprocess
        import tempfile

        with tempfile.NamedTemporaryFile(mode="wb", delete=False) as f:
            f.write(default_gitattributes.encode("utf-8"))
            temp_path = f.name

        try:
            # Use git hash-object to create the blob
            with open(temp_path, "rb") as f:
                proc = subprocess.Popen(
                    ["git", "hash-object", "-w", "--stdin"],
                    cwd=repo_path,
                    stdin=f,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                stdout, stderr = proc.communicate()
                if proc.returncode == 0:
                    blob_hash = stdout.decode("utf-8").strip()
                    hint(ui_callback, "success", f"Created default .gitattributes file")
                    return blob_hash
                else:
                    hint(
                        ui_callback,
                        "warning",
                        f"Failed to create .gitattributes blob: {stderr.decode('utf-8', errors='replace')}",
                    )
                    return None
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)
    except Exception as e:
        hint(ui_callback, "warning", f"Failed to create .gitattributes: {str(e)}")
        return None


def add_default_files_to_repository(
    repo_path,
    default_branch,
    create_gitignore=True,
    create_gitattributes=True,
    ui_callback=None,
):
    """
    Create default .gitignore and .gitattributes files in a non-bare repository.
    The files are created in the working directory but NOT committed.

    Args:
        repo_path: Path to the repository (must be non-bare)
        default_branch: Branch name (for reference)
        create_gitignore: Whether to create .gitignore
        create_gitattributes: Whether to create .gitattributes
        ui_callback: Optional UI callback object for user interactions

    Returns:
        bool: True if successful, False otherwise
    """
    hint(
        ui_callback,
        "info",
        f"\n{'='*80}\nCreating default files in repository (not committing)\n{'='*80}\n",
    )

    success = True

    # Create .gitignore file if requested
    if create_gitignore:
        default_gitignore = """# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
venv/
env/
ENV/
*.egg-info/
dist/
build/

# IDE
.vscode/
.idea/
*.swp
*.swo
*.sublime-*

# OS
.DS_Store
Thumbs.db
desktop.ini

# Temporary files
*.tmp
*.temp
*.log
*.bak
*.swp
*~

# User-specific files
*.user
*.suo
*.userosscache
*.sln.docstates

# Build artifacts
*.o
*.obj
*.exe
*.dll
*.lib
*.a
*.so
*.dylib
"""
        gitignore_path = os.path.join(repo_path, ".gitignore")
        try:
            with open(gitignore_path, "w", encoding="utf-8") as f:
                f.write(default_gitignore)
            hint(ui_callback, "success", "Created .gitignore file")
        except Exception as e:
            hint(ui_callback, "warning", f"Failed to create .gitignore: {str(e)}")
            success = False

    # Create .gitattributes file if requested
    if create_gitattributes:
        default_gitattributes = """# Git LFS attributes
# Common binary and large file patterns

# Images
*.png filter=lfs diff=lfs merge=lfs -text
*.jpg filter=lfs diff=lfs merge=lfs -text
*.jpeg filter=lfs diff=lfs merge=lfs -text
*.gif filter=lfs diff=lfs merge=lfs -text
*.bmp filter=lfs diff=lfs merge=lfs -text
*.tiff filter=lfs diff=lfs merge=lfs -text
*.ico filter=lfs diff=lfs merge=lfs -text
*.psd filter=lfs diff=lfs merge=lfs -text

# Audio/Video
*.mp3 filter=lfs diff=lfs merge=lfs -text
*.mp4 filter=lfs diff=lfs merge=lfs -text
*.avi filter=lfs diff=lfs merge=lfs -text
*.mov filter=lfs diff=lfs merge=lfs -text
*.wav filter=lfs diff=lfs merge=lfs -text
*.flv filter=lfs diff=lfs merge=lfs -text

# Archives
*.zip filter=lfs diff=lfs merge=lfs -text
*.tar filter=lfs diff=lfs merge=lfs -text
*.gz filter=lfs diff=lfs merge=lfs -text
*.7z filter=lfs diff=lfs merge=lfs -text
*.rar filter=lfs diff=lfs merge=lfs -text

# Binaries
*.exe filter=lfs diff=lfs merge=lfs -text
*.dll filter=lfs diff=lfs merge=lfs -text
*.so filter=lfs diff=lfs merge=lfs -text
*.dylib filter=lfs diff=lfs merge=lfs -text
*.bin filter=lfs diff=lfs merge=lfs -text

# Large data files
*.db filter=lfs diff=lfs merge=lfs -text
*.sqlite filter=lfs diff=lfs merge=lfs -text
*.dump filter=lfs diff=lfs merge=lfs -text
"""
        gitattributes_path = os.path.join(repo_path, ".gitattributes")
        try:
            with open(gitattributes_path, "w", encoding="utf-8") as f:
                f.write(default_gitattributes)
            hint(ui_callback, "success", "Created .gitattributes file")
        except Exception as e:
            hint(ui_callback, "warning", f"Failed to create .gitattributes: {str(e)}")
            success = False

    if success:
        hint(
            ui_callback,
            "info",
            "\nNote: Default files have been created in the working directory. "
            "They are not automatically committed. "
            "You can add them to your next commit using:\n"
            "  git add .gitignore .gitattributes\n"
            "  git commit -m 'Add default files'\n",
        )

    return success


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

    # First, verify the remote exists
    check_remote_cmd = f"git remote get-url {remote_name}"
    check_result = run_command(check_remote_cmd, cwd=repo_path)
    if check_result != 0:
        hint(
            ui_callback,
            "error",
            f"Remote '{remote_name}' does not exist. Cannot configure refspecs.",
        )
        return False

    # Get existing fetch refspecs to avoid duplicates
    capture_logger = OutputCaptureLogger(None)
    result = run_command(
        f"git config --get-all remote.{remote_name}.fetch",
        cwd=repo_path,
        logger=capture_logger,
    )
    existing_refspecs = set()
    if result == 0:
        output = capture_logger.get_output().strip()
        if output:
            existing_refspecs = set(line.strip() for line in output.split("\n") if line.strip())

    success = True

    for i, branch in enumerate(branches):
        refspec = f"+refs/heads/{branch}:refs/remotes/{remote_name}/{branch}"

        # Check if refspec already exists
        if refspec in existing_refspecs:
            hint(
                ui_callback,
                "info",
                f"Refspec for branch '{branch}' already exists, skipping: {refspec}",
            )
            continue

        if i == 0 and replace_first:
            # First branch: use 'git config' to replace default refspec
            cmd = f'git config remote.{remote_name}.fetch "{refspec}"'
            action = "Setting"
        else:
            # Subsequent branches: use 'git config --add' to add additional refspecs
            cmd = f'git config --add remote.{remote_name}.fetch "{refspec}"'
            action = "Adding"

        hint(ui_callback, "info", f"{action} refspec for branch '{branch}': {refspec}")

        # Capture command output to get error details
        capture_logger = OutputCaptureLogger(None)
        result = run_command(cmd, cwd=repo_path, logger=capture_logger)

        if result == 0:
            hint(ui_callback, "success", f"Refspec configured for '{branch}'")
            # Add to existing_refspecs to avoid duplicates in the same run
            existing_refspecs.add(refspec)
        else:
            # Get error details from captured output
            error_output = capture_logger.get_output()
            error_msg = f"Failed to configure refspec for '{branch}'"
            if error_output:
                error_msg += f": {error_output.strip()}"
            hint(ui_callback, "error", error_msg)
            success = False

    return success


def validate_branches_on_remote(repo_path, remote_name, branches, ui_callback=None):
    """
    Validate that the specified branches exist on the remote before proceeding.

    Args:
        repo_path: Path to the repository
        remote_name: Name of the remote to check
        branches: List of branch names to validate
        ui_callback: Optional UI callback object for user interactions

    Returns:
        bool: True if all branches exist, False otherwise
    """
    hint(
        ui_callback,
        "info",
        f"\n{'='*80}\nValidating branches on remote: {remote_name}\n{'='*80}\n",
    )

    missing_branches = []
    for branch in branches:
        # Use ls-remote to check if branch exists on remote
        capture_logger = OutputCaptureLogger(None)
        result = run_command(
            f"git ls-remote --heads {remote_name} {branch}",
            cwd=repo_path,
            logger=capture_logger,
        )

        if result != 0:
            missing_branches.append(branch)
            hint(
                ui_callback,
                "error",
                f"Branch '{branch}' not found on remote '{remote_name}'",
            )
        else:
            output = capture_logger.get_output().strip()
            if not output:
                missing_branches.append(branch)
                hint(
                    ui_callback,
                    "error",
                    f"Branch '{branch}' not found on remote '{remote_name}'",
                )
            else:
                hint(
                    ui_callback,
                    "success",
                    f"Branch '{branch}' found on remote '{remote_name}'",
                )

    if missing_branches:
        hint(
            ui_callback,
            "error",
            f"Missing branches on '{remote_name}': {', '.join(missing_branches)}",
        )
        return False

    return True


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

    # git fetch can be painfully slow, use streaming output and no timeout
    # Use --progress to force git to output progress even when stdout/stderr are pipes
    result = run_command(
        ["git", "fetch", "--progress", remote_name],
        cwd=repo_path,
        stream_output=True,
        stderr_to_stdout=True,
    )

    if result == 0:
        hint(ui_callback, "success", f"Successfully fetched from '{remote_name}'")
        return True
    else:
        hint(ui_callback, "error", f"Failed to fetch from '{remote_name}'")
        return False


def create_local_branches_from_remote(
    repo_path, remote_name, default_branch=None, ui_callback=None
):
    """
    Create local branches for all remote branches from the specified remote.
    Also sets HEAD to point to the default_branch if provided.

    Args:
        repo_path: Path to the repository
        remote_name: Name of the remote (e.g., 'origin')
        default_branch: Branch name to set as HEAD (first branch in branches list)
        ui_callback: Optional UI callback object for user interactions

    Returns:
        bool: True if successful, False otherwise
    """
    hint(
        ui_callback,
        "info",
        f"\n{'='*80}\nCreating local branches from remote: {remote_name}\n{'='*80}\n",
    )

    # Get list of remote branches
    capture_logger = OutputCaptureLogger(None)
    result = run_command(f"git branch -r", cwd=repo_path, logger=capture_logger)

    if result != 0:
        hint(ui_callback, "error", "Failed to list remote branches")
        return False

    output = capture_logger.get_output().strip()
    if not output:
        hint(
            ui_callback,
            "warning",
            "No remote branches found. Skipping branch creation.",
        )
        return True

    # Parse remote branches for the specified remote
    remote_branches = []
    for line in output.split("\n"):
        line = line.strip()
        if not line:
            continue
        # Remove leading * if present (current branch indicator)
        line = line.lstrip("*").strip()
        # Handle "HEAD -> branch" format (e.g., "origin/HEAD -> origin/master")
        if " -> " in line:
            # Skip HEAD symbolic refs
            continue
        # Format: origin/branch-name or remotes/origin/branch-name
        if line.startswith(f"{remote_name}/"):
            branch_name = line.replace(f"{remote_name}/", "").strip()
            if branch_name and branch_name != "HEAD":
                remote_branches.append(branch_name)
        elif line.startswith(f"remotes/{remote_name}/"):
            branch_name = line.replace(f"remotes/{remote_name}/", "").strip()
            if branch_name and branch_name != "HEAD":
                remote_branches.append(branch_name)

    if not remote_branches:
        hint(ui_callback, "warning", f"No branches found for remote '{remote_name}'")
        return True

    hint(
        ui_callback,
        "info",
        f"Found {len(remote_branches)} remote branch(es) to create locally",
    )

    # Create local branches for each remote branch
    success_count = 0
    for branch_name in remote_branches:
        remote_ref = f"refs/remotes/{remote_name}/{branch_name}"
        local_ref = f"refs/heads/{branch_name}"

        # Check if local branch already exists
        check_cmd = f"git show-ref --verify --quiet {local_ref}"
        check_result = run_command(check_cmd, cwd=repo_path)

        if check_result == 0:
            hint(
                ui_callback,
                "info",
                f"Local branch '{branch_name}' already exists, skipping",
            )
            success_count += 1
            continue

        # Create local branch pointing to the remote branch
        # In bare repo, we use: git branch <branch-name> <remote-ref>
        create_cmd = f"git branch {branch_name} {remote_ref}"
        create_result = run_command(create_cmd, cwd=repo_path)

        if create_result == 0:
            hint(
                ui_callback,
                "success",
                f"Created local branch '{branch_name}' from {remote_name}/{branch_name}",
            )
            success_count += 1
        else:
            hint(
                ui_callback, "warning", f"Failed to create local branch '{branch_name}'"
            )

    hint(
        ui_callback,
        "info",
        f"Created {success_count}/{len(remote_branches)} local branch(es)",
    )

    # Set HEAD to the default branch if provided
    if default_branch:
        # Check if the default branch exists locally
        check_cmd = f"git show-ref --verify --quiet refs/heads/{default_branch}"
        check_result = run_command(check_cmd, cwd=repo_path)

        if check_result == 0:
            # Set HEAD to point to the default branch
            set_head_cmd = f"git symbolic-ref HEAD refs/heads/{default_branch}"
            head_result = run_command(set_head_cmd, cwd=repo_path)

            if head_result == 0:
                hint(ui_callback, "success", f"Set HEAD to branch '{default_branch}'")
            else:
                hint(
                    ui_callback,
                    "warning",
                    f"Failed to set HEAD to branch '{default_branch}'",
                )
        else:
            hint(
                ui_callback,
                "warning",
                f"Default branch '{default_branch}' does not exist locally. Cannot set HEAD.",
            )

    return success_count > 0


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

    parser.add_argument(
        "--no-default-ignore",
        action="store_true",
        help="Skip creating default .gitignore file",
    )

    parser.add_argument(
        "--no-default-lfs",
        action="store_true",
        help="Skip creating default .gitattributes file for LFS",
    )

    parser.add_argument(
        "--bare",
        action="store_true",
        default=False,
        help="Create a bare repository (default: False)",
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
        f"Git Repository Initialization\n"
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
    is_bare = getattr(args, "bare", False)
    config_msg += (
        f"  Branches:        {', '.join(args.branches)}\n"
        f"  Repository Type: {'Bare' if is_bare else 'Regular (non-bare)'}\n"
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

    # Step 1: Initialize repository (bare or non-bare)
    is_bare = getattr(args, "bare", False)  # Default to False
    if not init_repository(repo_path, bare=is_bare, ui_callback=ui_callback):
        hint(ui_callback, "error", "\nFailed to initialize repository")
        return 1

    # Step 1.1: Initialize Git LFS for this repository (best-effort)
    # Do not hard-fail on LFS; just warn if it is missing or fails.
    if not init_git_lfs(repo_path, ui_callback):
        hint(
            ui_callback,
            "warning",
            "Git LFS was not initialized successfully. "
            "If this repository needs to mirror LFS content, please ensure "
            "git-lfs is installed and re-run initialization.",
        )

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

    # Step 3.6: Validate branches exist on remotes before fetching
    if not args.no_fetch:
        hint(
            ui_callback,
            "info",
            "\nValidating that specified branches exist on remotes...",
        )
        # Validate branches on source remote
        if not validate_branches_on_remote(
            repo_path, args.remote_name, args.branches, ui_callback
        ):
            hint(
                ui_callback,
                "error",
                f"\nValidation failed: Some branches are missing on '{args.remote_name}'. Aborting.",
            )
            return 1

        # Validate branches on destination remote (if provided)
        if args.destination_remote_url:
            if not validate_branches_on_remote(
                repo_path,
                args.destination_remote_name,
                args.branches,
                ui_callback,
            ):
                hint(
                    ui_callback,
                    "error",
                    f"\nValidation failed: Some branches are missing on '{args.destination_remote_name}'. Aborting.",
                )
                return 1

    # Step 4: Fetch from remote (if not skipped)
    # Fetch one by one, stop on failure
    if not args.no_fetch:
        # Fetch from source remote first
        if not fetch_from_remote(repo_path, args.remote_name, ui_callback):
            hint(
                ui_callback,
                "error",
                f"\nFailed to fetch from '{args.remote_name}'. Aborting.",
            )
            return 1

        # Fetch from destination remote (if provided)
        if args.destination_remote_url:
            if not fetch_from_remote(
                repo_path, args.destination_remote_name, ui_callback
            ):
                hint(
                    ui_callback,
                    "error",
                    f"\nFailed to fetch from '{args.destination_remote_name}'. Aborting.",
                )
                return 1
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

    # Step 6: Create local branches from remote branches and set HEAD
    if not args.no_fetch:
        # Create local branches first, then determine default branch
        if not create_local_branches_from_remote(
            repo_path, args.remote_name, None, ui_callback
        ):
            hint(
                ui_callback,
                "warning",
                "\nSome local branches may not have been created, but continuing...",
            )

        # Determine default branch: prefer master, then main, then first branch with confirmation
        default_branch = None
        if args.branches:
            has_master = "master" in args.branches
            has_main = "main" in args.branches

            # Check if both master and main exist - this is an error
            if has_master and has_main:
                hint(
                    ui_callback,
                    "error",
                    "Both 'master' and 'main' are specified in branches list. "
                    "Please specify only one default branch.",
                )
                return 1

            # Prefer master, then main
            if has_master:
                candidate_branch = "master"
            elif has_main:
                candidate_branch = "main"
            else:
                # Use first branch, but ask for confirmation
                candidate_branch = args.branches[0]
                confirmation_msg = (
                    f"\nNeither 'master' nor 'main' found in branches list. "
                    f"Will use '{candidate_branch}' as default branch.\n"
                    f"Proceed with '{candidate_branch}' as the default branch?"
                )
                if not ask_yesno(ui_callback, confirmation_msg):
                    hint(ui_callback, "info", "\nAborted by user")
                    return 1

            # Verify the candidate branch exists locally
            check_cmd = f"git show-ref --verify --quiet refs/heads/{candidate_branch}"
            check_result = run_command(check_cmd, cwd=repo_path)
            if check_result == 0:
                default_branch = candidate_branch
            else:
                # Try to find the branch from remote branches
                capture_logger = OutputCaptureLogger(None)
                result = run_command(
                    f"git branch -r", cwd=repo_path, logger=capture_logger
                )
                if result == 0:
                    output = capture_logger.get_output().strip()
                    found_branch = False
                    for line in output.split("\n"):
                        line = line.strip().lstrip("*").strip()
                        if " -> " in line:
                            continue
                        if line.startswith(f"{args.remote_name}/"):
                            branch_name = line.replace(
                                f"{args.remote_name}/", ""
                            ).strip()
                            if (
                                branch_name == candidate_branch
                                and branch_name != "HEAD"
                            ):
                                # Check if this branch exists locally
                                check_cmd = f"git show-ref --verify --quiet refs/heads/{branch_name}"
                                if run_command(check_cmd, cwd=repo_path) == 0:
                                    default_branch = branch_name
                                    found_branch = True
                                    break

                    if not found_branch:
                        hint(
                            ui_callback,
                            "warning",
                            f"Default branch '{candidate_branch}' not found locally. "
                            f"Will try to use first available branch.",
                        )
                        # Fallback: use first available branch from remote
                        for line in output.split("\n"):
                            line = line.strip().lstrip("*").strip()
                            if " -> " in line:
                                continue
                            if line.startswith(f"{args.remote_name}/"):
                                branch_name = line.replace(
                                    f"{args.remote_name}/", ""
                                ).strip()
                                if branch_name and branch_name != "HEAD":
                                    check_cmd = f"git show-ref --verify --quiet refs/heads/{branch_name}"
                                    if run_command(check_cmd, cwd=repo_path) == 0:
                                        default_branch = branch_name
                                        hint(
                                            ui_callback,
                                            "info",
                                            f"Using '{branch_name}' as default branch instead.",
                                        )
                                        break
                else:
                    hint(
                        ui_callback,
                        "warning",
                        f"Default branch '{candidate_branch}' not found locally and could not list remote branches.",
                    )

        # Set HEAD to the default branch if we found one
        if default_branch:
            set_head_cmd = f"git symbolic-ref HEAD refs/heads/{default_branch}"
            head_result = run_command(set_head_cmd, cwd=repo_path)
            if head_result == 0:
                hint(ui_callback, "success", f"Set HEAD to branch '{default_branch}'")
            else:
                hint(
                    ui_callback,
                    "warning",
                    f"Failed to set HEAD to branch '{default_branch}'",
                )
        else:
            hint(
                ui_callback,
                "warning",
                f"Could not determine default branch to set HEAD. First branch '{args.branches[0] if args.branches else 'N/A'}' does not exist locally.",
            )

        # Step 7: Add default .gitignore and .gitattributes files if requested
        if default_branch and not is_bare:
            # Check if we should create default files (default is True unless flags are set)
            # argparse converts --no-default-ignore to no_default_ignore
            no_default_ignore = getattr(args, "no_default_ignore", False)
            no_default_lfs = getattr(args, "no_default_lfs", False)
            create_gitignore = not no_default_ignore
            create_gitattributes = not no_default_lfs

            if create_gitignore or create_gitattributes:
                add_default_files_to_repository(
                    repo_path,
                    default_branch,
                    create_gitignore=create_gitignore,
                    create_gitattributes=create_gitattributes,
                    ui_callback=ui_callback,
                )
    else:
        hint(
            ui_callback,
            "info",
            "\nSkipping local branch creation (--no-fetch specified, no remote branches available)",
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
