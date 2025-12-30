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


## Installation

1. Clone or download this repository
2. Ensure `run_command.py` is in the same directory as `git_sync_to_remote.py`
3. Make sure Python 3 is installed and accessible via `python3` or `py -3`

## git_sync_to_remote.py

### Description

This script pushes git commits in batches to avoid server limits such as pack size limits or timeout issues when pushing many commits. If you encounter errors like **[unpacker error]**, this is the right tool.

### Features

- **Batch Processing**: Splits commits into configurable batches (default: 50 commits per batch)
- **Safe Force Push**: Uses `--force-with-lease` by default to safely overwrite remote changes
- **Verification**: Automatically verifies each batch after pushing to ensure integrity
- **Debug Mode**: Preview commits before pushing each batch
- **Merge Commit Support**: Properly handles merged revisions that the shell script version cannot
- **Chronological Order**: Pushes commits in chronological order (oldest first)

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
2. Fetches the latest state from destination remote (source remote should be fetched manually beforehand)
3. Prompts for confirmation if pushing to origin (safety feature)
4. Finds commits in origin that are not in destination (`origin..destination`)
5. Splits commits into batches of `BATCH_SIZE`
6. Pushes each batch from origin to destination remote in chronological order
7. Uses `--force-with-lease` for safe force pushing (if enabled)
8. Verifies each batch after pushing (if verification is enabled)
9. Adds a 1-second delay between batches to reduce server load

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

- Make sure you have set up your git folder and **ready to push**
- Fetch the source remote manually before running the script (the script only fetches the destination remote automatically)
- You may want to create the branch at your server first to avoid unnecessary errors
- Ensure your remote URL has proper authentication embedded (e.g., token in URL)
- Both source and destination remotes must be configured
- The script will prompt for confirmation if you attempt to push to origin (as a safety measure)

### Troubleshooting

**Error: Remote 'destination' not found**
- Make sure you've added the destination remote: `git remote add destination <URL>`
- Check available remotes: `git remote -v`

**Error: Branch not found on remote**
- Create the branch on the destination remote first
- Or ensure the branch exists on both origin and destination remotes

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

## License

See [LICENSE](LICENSE) file for details.

## Contributing

Contributions are welcome! Please ensure your code follows the existing style and includes appropriate documentation.
