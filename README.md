# fried_git_tools

Git scripts to solve real engineering problems. Tools to push large amounts of commits that would otherwise trigger **[unpacker error]** or other server-side limitations.

## Overview

When pushing a large number of commits to a Git server, you may encounter errors like:
- `[unpacker error]` - Server cannot unpack the large pack file
- Timeout errors - Push operation exceeds server timeout limits
- Pack size limits - Total pack size exceeds server configuration

This tool solves these problems by splitting commits into smaller batches and pushing them incrementally.

## Requirements

- **Python 3.x** (Python 3.6 or higher recommended)
- **Git** installed and available in your PATH
- **Git LFS** (optional, but recommended if your repository uses Large File Storage)

## Installation

1. Clone or download this repository
2. Ensure `run_command.py` is in the same directory as `git_sync_to_remote.py`
3. Make sure Python 3 is installed and accessible via `python3` or `py -3`
4. If your repository uses Git LFS, ensure Git LFS is installed and configured

## git_sync_to_remote.py

### Description

This script pushes git commits in batches to avoid server limits such as pack size limits or timeout issues when pushing many commits. If you encounter errors like **[unpacker error]**, this is the right tool.

### Features

- **Batch Processing**: Splits commits into configurable batches (default: 50 commits per batch)
- **Safe Force Push**: Uses `--force-with-lease` by default to safely overwrite remote changes
- **Verification**: Automatically verifies each batch after pushing to ensure integrity by comparing commit logs
- **Debug Mode**: Preview commits before pushing each batch with interactive confirmation
- **Merge Commit Support**: Properly handles merged revisions and sub-commits that the shell script version cannot
- **Chronological Order**: Pushes commits in chronological order (oldest first)
- **Git LFS Support**: Automatically detects and fetches LFS objects for each batch before pushing
- **Log Caching**: Caches origin branch logs for efficient verification and comparison
- **Error Detection**: Advanced error detection with regex patterns to catch push failures early

### Usage

```bash
python3 git_sync_to_remote.py <workspace_directory> [remote] [branch] [--debug] [--no-verify]
```

Or on Windows:

```bash
py -3 git_sync_to_remote.py <workspace_directory> [remote] [branch] [--debug] [--no-verify]
```

#### Parameters

- `workspace_directory` (required) - Path to the git repository
- `remote` (optional) - Destination remote name (default: `destination`)
- `branch` (optional) - Branch name to sync (default: `develop`)
- `--debug` (optional) - Enable debug mode (list commits per batch and require confirmation before each batch)
- `--no-verify` (optional) - Disable verification after each batch (default: verification enabled)

#### Examples

**Basic usage (default remote and branch):**
```bash
py -3 git_sync_to_remote.py /path/to/repo
```

**Specify remote and branch:**
```bash
py -3 git_sync_to_remote.py /path/to/repo destination 5.4
```

**With debug mode (preview commits before pushing):**
```bash
py -3 git_sync_to_remote.py /path/to/repo destination 5.4 --debug
```

**Disable verification (faster, but less safe):**
```bash
py -3 git_sync_to_remote.py /path/to/repo destination 5.4 --no-verify
```

### Configuration

You can modify these constants in the script:

- `BATCH_SIZE` (default: 50) - Number of commits per batch
- `FORCE_PUSH` (default: True) - Enable force push with lease protection
- `SOURCE_REMOTE` (default: "origin") - Source remote name (always syncs from origin)

**⚠️ WARNING: FORCE_PUSH is set to true by default** - Make sure you **don't get the branch wrong** as it will overwrite the remote branch.

### How It Works

1. Validates that the workspace is a valid git repository
2. Validates that both source and destination remotes exist and are configured
3. Prompts for confirmation if pushing to origin (safety feature)
4. Fetches the latest state from destination remote (source remote should be fetched manually beforehand)
5. Detects if Git LFS is enabled in the repository
6. Caches the origin branch log for verification purposes
7. Finds commits in origin that are not in destination (`origin..destination`)
8. Filters out graph symbols and sub-commits from merge commits
9. Splits commits into batches of `BATCH_SIZE`
10. For each batch:
    - If LFS is enabled, fetches LFS objects for commits in the batch range
    - Pushes the batch from origin to destination remote in chronological order
    - Uses `--force-with-lease` for safe force pushing (if enabled)
    - Fetches from destination to update local references
    - Verifies logs by comparing origin and destination commit logs (if verification is enabled)
11. Adds a 1-second delay between batches to reduce server load
12. Creates temporary log files in `workspace/temp/` for verification and debugging

### Detailed Example: Mirroring Unreal Engine 5.4 Branch

If you want to mirror Unreal Engine 5.4 branch into your own git repository:

1. **Download the 5.4 branch into a folder:**
   ```sh
   git init --bare
   git remote add origin <SOURCE_REPO_URL>
   git config remote.origin.fetch "+refs/heads/5.4:refs/heads/5.4"
   # Optionally add other branches:
   # git config remote.origin.fetch "+refs/heads/master:refs/heads/master"
   ```

2. **Add your destination remote:**
   ```sh
   git remote add destination <DESTINATION_REPO_URL>
   ```

3. **Try a direct push (will likely fail with unpacker error):**
   ```sh
   git push destination +5.4:5.4
   ```
   This will likely fail with `[unpacker error]` if there are too many commits.

4. **Use the batch push tool instead:**
   ```sh
   py -3 ./git_sync_to_remote.py <workspace_directory> destination 5.4
   ```
   The script will split the commits into batches and push them incrementally.

### Command-Line Options

- **--debug**: Enable debug mode
  - Lists all commits in each batch before pushing
  - Requires confirmation before pushing each batch
  - Useful for reviewing what will be pushed

- **--no-verify**: Disable per-batch verification
  - Skips the log comparison verification after each batch
  - Faster execution, but less safe
  - Verification compares origin and destination logs to ensure consistency

### Prerequisites

- Make sure you have set up your git folder and it is **ready to push**
- Fetch the source remote manually before running the script (the script only fetches the destination remote automatically)
- You may want to create the branch on your server first to avoid unnecessary errors
- Ensure your remote URL has proper authentication embedded (e.g., token in URL)
- Both source and destination remotes must be configured
- The script will prompt for confirmation if you attempt to push to origin (as a safety measure)

### Example: Setting Up a Branch to Sync

This example shows how to set up syncing when your destination server already has a branch with different content (e.g., a main branch with a README file).

Taking the master branch as an example, if your destination server already contains a main branch with a README, you need to align them first:

1. **Create a dual-remote structure** (similar to the Unreal Engine example above):
   - The source repo's remote is `origin`
   - The destination repo's remote is `destination`
   - For example, let's say the workspace is `/t/sync_workspace`

2. **Create a branch pointing to the first commit** of `refs/remotes/origin/master`:
   ```sh
   # Find the first commit hash
   git log --reverse --format="%H" refs/remotes/origin/master | head -1
   # Create a branch named origin_master_1 pointing to that commit
   git branch origin_master_1 <first_commit_hash>
   ```
   Replace `<first_commit_hash>` with the hash from the first command.

3. **Optional: Use a worktree for the initial force push** (recommended):
   ```sh
   git worktree add ../some_dir origin_master_1
   cd ../some_dir
   ```
   This step is optional, but it's better to perform the force push in a separate folder to ensure there are files and correct states for force pushing.

4. **Disable branch protection** in your GitLab/GitHub settings for the master branch (required for force push).

5. **Perform the initial force push** to align the branches:
   ```sh
   git push destination origin_master_1:master -f
   ```

6. **Return to the original folder** - it is now fully prepared for syncing:
   ```sh
   cd /t/sync_workspace
   ```

7. **Run the sync script**:
   ```sh
   py -3 git_sync_to_remote.py /t/sync_workspace destination master
   ```
   Now you can have a coffee and watch it do the work!

### Troubleshooting

**Error: Remote 'destination' not found**
- Make sure you've added the destination remote: `git remote add destination <URL>`
- Check available remotes: `git remote -v`

**Error: Branch not found on remote**
- Create the branch on the destination remote first
- Or ensure the branch exists on both origin and destination remotes
- Note: If the destination branch is empty (0 commits) or has only 1 commit, the script will push all origin commits automatically

**Push fails with unpacker error even with batching**
- Reduce `BATCH_SIZE` further (try 20 or 10)
- Check for large files in recent commits
- Contact your git administrator about pack size limits

**Force push fails**
- The remote branch may have been updated by someone else
- Fetch and check: `git fetch destination`
- Consider using `--no-verify` if verification is causing issues (not recommended)

**Verification fails**
- This indicates the logs don't match between origin and destination
- Check if someone else pushed to the destination branch
- Review the mismatch details shown in the error output

## git_sync_to_remote.sh

### Description

This is the legacy shell script version of `git_sync_to_remote.py`.

### Limitations

- It can work in some repositories, but **fails to handle merged revisions** that `git_sync_to_remote.py` can handle properly
- The Python version is recommended for all use cases

### When to Use

- Only use if you cannot run Python 3
- For simple linear histories without merge commits
- The Python version should be preferred in all cases


## init_git_sync_folder.py

### Description

A utility script to initialize a bare Git repository and configure it for branch synchronization. This is useful for setting up mirror repositories or preparing a workspace for syncing specific branches.

### Features

- Creates a bare Git repository
- Configures remote with custom branch fetch specifications
- Supports multiple branches with explicit refspecs
- Can be re-run safely (skips existing configurations)
- Verification mode to check existing configurations

### Usage

```bash
python init_git_sync_folder.py --repo-path <path> --remote-url <url> [options]
```

#### Parameters

- `--repo-path` (required) - Path where the bare repository should be created
- `--remote-url` (required) - URL of the remote repository (e.g., `ssh://git@example.com/repo.git`)
- `--remote-name` (optional) - Name of the remote (default: `origin`)
- `--branches` (optional) - List of branches to sync (default: `master`)
- `--no-fetch` (optional) - Skip the initial fetch operation
- `--verify-only` (optional) - Only verify existing configuration without making changes

#### Examples

**Basic usage:**
```bash
python init_git_sync_folder.py --repo-path /path/to/repo --remote-url ssh://git@example.com/repo.git
```

**Multiple branches:**
```bash
python init_git_sync_folder.py --repo-path /path/to/repo \
  --remote-url ssh://git@example.com/repo.git \
  --branches master develop release
```

- **Fetch LFS files manually**: You need to fetch LFS files from the origin remote before syncing:
  ```sh
  git lfs fetch origin <branch_name>
  ```
  This ensures all LFS files are available locally before pushing.

- **Configure LFS on destination**: Your destination remote needs to have Git LFS configured separately. The script cannot configure LFS for you.

- **Monitor for errors**: While the script attempts to handle LFS files during the sync process, you should watch for any LFS-related errors and resolve them manually if needed.

## License

See [LICENSE](LICENSE) file for details.

## Contributing

Contributions are welcome! Please ensure your code follows the existing style and includes appropriate documentation.
