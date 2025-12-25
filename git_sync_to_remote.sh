#!/bin/bash

###############################################################################
# Git Batch Push Script
###############################################################################
#
# DESCRIPTION:
#   This script pushes git commits in batches to avoid server limits,
#   such as pack size limits or timeout issues when pushing many commits.
#
# USAGE:
#   ./git_sync_to_remote.sh <workspace_directory> [remote] [branch]
#
# PARAMETERS:
#   workspace_directory (required) - Path to the git repository
#   remote (optional)              - Remote name 
#   branch (optional)              - Target branch name
#
# EXAMPLES:
#   # Push to default remote and branch
#   ./git_sync_to_remote.sh /path/to/repo
#
#   # Push to specific remote and branch
#   ./git_sync_to_remote.sh /path/to/repo origin develop
#
#   # Push to custom remote with default branch
#   ./git_sync_to_remote.sh /path/to/repo upstream
#
# CONFIGURATION:
#   BATCH_SIZE  - Number of commits per batch (default: 50)
#   FORCE_PUSH  - Enable force push with lease protection (default: true)
#
# HOW IT WORKS:
#   1. Check if the workspace is a valid git repository
#   2. Fetch the latest state from remote repository
#   3. Find commits that need to be pushed (local only)
#   4. Split commits into batches of BATCH_SIZE
#   5. Push each batch one by one to the remote branch
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

# Check if required parameters are provided
if [ $# -lt 1 ]; then
    echo "Usage: $0 <workspace_directory> [remote] [branch]"
    echo "Example: $0 /path/to/repo  origin develop"
    exit 1
fi

# Parameters
WORKSPACE_DIR="$1"
REMOTE="${2:-origin}"  # Default to 'origin' if not provided
BRANCH="${3:-develop}"      # Default to '5.4' if not provided

# Configuration
BATCH_SIZE=50
FORCE_PUSH=true

# Validate workspace directory
if [ ! -d "$WORKSPACE_DIR" ]; then
    echo "Error: Workspace directory '$WORKSPACE_DIR' does not exist"
    exit 1
fi

#if [ ! -d "$WORKSPACE_DIR/.git" ]; then
 #   echo "Error: '$WORKSPACE_DIR' is not a git repository"
#    exit 1
#fi

# Change to workspace directory
echo "Switching to workspace: $WORKSPACE_DIR"
cd "$WORKSPACE_DIR" || exit 1

echo "Using remote: $REMOTE"
echo "Using branch: $BRANCH"

# Get remote URL
REMOTE_URL=$(git remote get-url $REMOTE)
if [ $? -ne 0 ]; then
    echo "Error: Remote '$REMOTE' not found"
    exit 1
fi

echo "Remote URL: $REMOTE_URL"

# Fetch latest remote state to avoid stale info errors
echo "Fetching latest remote state..."
git fetch --force $REMOTE

# check if the branch exists on the remote
if git show-ref --quiet --verify refs/remotes/$REMOTE/$BRANCH; then
    # if so, only push the commits that are not on the remote already
    range=$REMOTE/$BRANCH..HEAD
else
    # else push all the commits
    range=HEAD
fi

echo "range: $range"

# Get list of commits in chronological order (oldest first)
commits=($(git rev-list --reverse $range))
total_commits=${#commits[@]}
# Calculate total number of batches
total_batches=$(((total_commits + BATCH_SIZE - 1) / BATCH_SIZE))

echo "Total commits to push: $total_commits (in $total_batches batches)"

if [ $total_commits -eq 0 ]; then
    echo "No commits to push"
    exit 0
fi

# Determine push options
if [ "$FORCE_PUSH" = true ]; then
    PUSH_OPTIONS="--force-with-lease"
    echo "⚠️  Force push enabled - will overwrite remote changes"
else
    PUSH_OPTIONS=""
    echo "Using safe push (will fail on conflicts)"
fi

# Push commits in batches
for ((i=0; i<total_commits; i+=BATCH_SIZE)); do
    # Calculate end index for this batch
    end=$((i + BATCH_SIZE - 1))
    if [ $end -ge $total_commits ]; then
        end=$((total_commits - 1))
    fi
    
    # Get the commit hash for the end of this batch
    target_commit=${commits[$end]}
    batch_num=$((i / BATCH_SIZE + 1))
    
    echo "Pushing batch $batch_num/$total_batches: commits $((i+1)) to $((end+1)) (target: $target_commit)"
    
    # Push this batch using the remote URL (token should be embedded)
    echo "Executing: git push $PUSH_OPTIONS $REMOTE ${target_commit}:refs/heads/$BRANCH"
    if git push $PUSH_OPTIONS "$REMOTE" ${target_commit}:refs/heads/$BRANCH; then
        echo "[SUCCEEDED] Batch $batch_num pushed successfully"
    else
        echo "[FAILED] Failed to push batch $batch_num"
        if [ "$FORCE_PUSH" != true ]; then
            echo "The remote branch has diverged. You can:"
            echo "1. Set FORCE_PUSH=true to overwrite remote changes"
            echo "2. Fetch and merge remote changes first: git fetch $REMOTE && git merge $REMOTE/$BRANCH"
            echo "3. Use git pull to integrate changes: git pull $REMOTE $BRANCH"
        else
            echo "Force push failed. You may need to:"
            echo "1. Reduce BATCH_SIZE further (try 20 or 10)"
            echo "2. Check for large files in recent commits"
            echo "3. Contact your git administrator about pack size limits"
            echo "4. Verify your remote URL has the correct authentication embedded"
        fi
        exit 1
    fi
    
    # Small delay to be nice to the server
    sleep 1
done

echo "[SUCCEEDED] All commits pushed successfully!"