#!/bin/bash

###############################################################################
# Git Batch Push Script
###############################################################################
#
# DESCRIPTION:
#   This script syncs git commits from origin remote to destination remote in batches
#   to avoid server limits, such as pack size limits or timeout issues when pushing many commits.
#
# USAGE:
#   ./git_sync_to_remote.sh <workspace_directory> [remote] [branch] [--debug] [--no-verify]
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
#   ./git_sync_to_remote.sh /path/to/repo
#
#   # Sync from origin to specific destination remote and branch
#   ./git_sync_to_remote.sh /path/to/repo destination 2025.1-lts
#
#   # Sync with debug mode enabled
#   ./git_sync_to_remote.sh /path/to/repo destination 2025.1-lts --debug
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

# Check if required parameters are provided
if [ $# -lt 1 ]; then
    echo "Usage: $0 <workspace_directory> [destination_remote] [branch] [--debug] [--no-verify]"
    echo "Note: Always syncs from 'origin' remote to destination remote"
    echo ""
    echo "Examples:"
    echo "  $0 /path/to/repo destination 2025.1-lts"
    echo "  $0 /path/to/repo destination develop --debug"
    echo "  $0 /path/to/repo destination develop --no-verify"
    exit 1
fi

# Parse parameters and check for --debug and --no-verify flags
DEBUG_MODE=false
VERIFY=true
POSITIONAL_ARGS=()

for arg in "$@"; do
    if [ "$arg" = "--debug" ]; then
        DEBUG_MODE=true
    elif [ "$arg" = "--no-verify" ]; then
        VERIFY=false
    else
        POSITIONAL_ARGS+=("$arg")
    fi
done

# Set positional parameters
WORKSPACE_DIR="${POSITIONAL_ARGS[0]}"
REMOTE="${POSITIONAL_ARGS[1]:-destination}"  # Default to 'destination' if not provided
BRANCH="${POSITIONAL_ARGS[2]:-develop}"      # Default to 'develop' if not provided

# Configuration
SOURCE_REMOTE="origin"  # Always sync from origin
BATCH_SIZE=50
FORCE_PUSH=true

# Get script directory for temp folder
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Function to sanitize remote URL by masking authentication tokens
sanitize_remote_url() {
    local url="$1"
    if [ -z "$url" ]; then
        echo "$url"
        return
    fi
    
    # Handle SSH URLs (git@host.com:user/repo.git) - typically no tokens
    if [[ "$url" == git@* ]] || [[ "$url" == ssh://git@* ]]; then
        # Check for token patterns in SSH URLs
        if [[ "$url" == *"://"*"@"* ]]; then
            # Pattern: ssh://token@host or ssh://user:token@host
            local scheme="${url%%://*}"
            local rest="${url#*://}"
            if [[ "$rest" == *":"*"@"* ]]; then
                # Has user:token format
                local user_pass="${rest%%@*}"
                local user="${user_pass%%:*}"
                local host_path="${rest#*@}"
                echo "${scheme}://${user}:***@${host_path}"
                return
            elif [[ "$rest" == *"@"* ]]; then
                # Has token@ format
                local host_path="${rest#*@}"
                echo "${scheme}://***@${host_path}"
                return
            fi
        fi
        echo "$url"
        return
    fi
    
    # Handle standard URLs (http, https, etc.)
    # Match patterns like ://token@ or ://user:token@
    # Replace user:token@ with user:***@
    local sanitized=$(echo "$url" | sed -E 's|://([^:@]+):[^@]+@|://\1:***@|g')
    # Replace remaining token@ with ***@
    sanitized=$(echo "$sanitized" | sed -E 's|://[^@]+@|://***@|g')
    echo "$sanitized"
}

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

echo "Syncing from: $SOURCE_REMOTE -> $REMOTE"
echo "Using branch: $BRANCH"

# Validate source remote exists
if ! git remote get-url $SOURCE_REMOTE > /dev/null 2>&1; then
    echo "Error: Source remote '$SOURCE_REMOTE' not found"
    echo "Available remotes:"
    git remote -v
    exit 1
fi

# Check if remote is 'origin' and ask for confirmation
if [ "$REMOTE" = "origin" ]; then
    echo ""
    echo "WARNING: Push to origin, which seems dangerous!"
    echo "    Git sync usually syncs to a second remote."
    read -p "Are you sure? [yes/no]: " confirmation
    if [ "$confirmation" != "yes" ]; then
        echo "Operation cancelled."
        exit 0
    fi
    echo ""
fi

# Get remote URL
REMOTE_URL=$(git remote get-url $REMOTE)
if [ $? -ne 0 ]; then
    echo "Error: Remote '$REMOTE' not found"
    exit 1
fi

echo "Remote URL: $(sanitize_remote_url "$REMOTE_URL")"

# Fetch latest state from both remotes
echo "Fetching latest remote state from $SOURCE_REMOTE and $REMOTE..."
# dont automatically fetch the source remote, you need to fetch it manually or with other scripts
# git fetch --force $SOURCE_REMOTE
git fetch --force $REMOTE

# Validate source branch exists on origin
if ! git show-ref --quiet --verify refs/remotes/$SOURCE_REMOTE/$BRANCH; then
    echo "Error: Branch '$BRANCH' not found on source remote '$SOURCE_REMOTE'"
    echo "Available branches on $SOURCE_REMOTE:"
    git branch -r | grep "$SOURCE_REMOTE/"
    exit 1
fi

# Validate destination branch exists
if ! git show-ref --quiet --verify refs/remotes/$REMOTE/$BRANCH; then
    echo "Error: Branch '$BRANCH' not found on destination remote '$REMOTE'"
    echo "Available branches on $REMOTE:"
    git branch -r | grep "$REMOTE/"
    exit 1
fi

# Compare origin branch to destination branch (not local)
range=$REMOTE/$BRANCH..$SOURCE_REMOTE/$BRANCH

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

# Debug mode will show commits per batch and ask for confirmation before each batch

# Function to verify logs by comparing origin and destination branch logs
verify_logs() {
    if [ "$VERIFY" != true ]; then
        return 0
    fi
    
    # Fetch latest state from destination remote
    git fetch --force $REMOTE > /dev/null 2>&1
    
    # Get destination's branch log
    DEST_LOG_FILE="$TEMP_DIR/${REMOTE}_${BRANCH}.txt"
    git log ${REMOTE}/${BRANCH} --graph --oneline --pretty=format:"%H %s" | tac > "$DEST_LOG_FILE"
    
    # Remove graph symbols from both logs and compare
    # Remove graph symbols at the start of each line, then trim whitespace
    # Use @ as delimiter since pattern contains both | and /
    ORIGIN_CLEAN=$(sed "s@$GRAPH_SYMBOL_REGEX@@g" "$ORIGIN_LOG_FILE" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//' | grep -v '^$')
    DEST_CLEAN=$(sed "s@$GRAPH_SYMBOL_REGEX@@g" "$DEST_LOG_FILE" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//' | grep -v '^$')
    
    # Count lines in both cleaned logs
    ORIGIN_LINES=$(echo "$ORIGIN_CLEAN" | grep -c . || echo "0")
    DEST_LINES=$(echo "$DEST_CLEAN" | grep -c . || echo "0")
    
    # Use minimum line count for comparison
    MIN_LINES=$((ORIGIN_LINES < DEST_LINES ? ORIGIN_LINES : DEST_LINES))
    
    if [ $MIN_LINES -eq 0 ]; then
        echo "[VERIFY] Warning: No lines to compare"
        return 0
    else
        # Compare first MIN_LINES lines
        ORIGIN_COMPARE=$(echo "$ORIGIN_CLEAN" | head -n $MIN_LINES)
        DEST_COMPARE=$(echo "$DEST_CLEAN" | head -n $MIN_LINES)
        
        if [ "$ORIGIN_COMPARE" = "$DEST_COMPARE" ]; then
            echo "[VERIFY] equal - logs match (compared first $MIN_LINES lines)"
            return 0
        else
            echo "[VERIFY] FAILED - logs do not match!"
            echo "Origin log (first $MIN_LINES lines):"
            echo "$ORIGIN_COMPARE" | head -n 10
            echo "..."
            echo "Destination log (first $MIN_LINES lines):"
            echo "$DEST_COMPARE" | head -n 10
            echo "..."
            echo "Stopping sync due to verification failure"
            return 1
        fi
    fi
}

# Setup verification if enabled
if [ "$VERIFY" = true ]; then
    # Create temp directory under script's folder if it doesn't exist
    TEMP_DIR="$SCRIPT_DIR/temp"
    if [ ! -d "$TEMP_DIR" ]; then
        mkdir -p "$TEMP_DIR"
    fi
    
    # Get origin's branch log and save to temp file
    ORIGIN_LOG_FILE="$TEMP_DIR/${SOURCE_REMOTE}_${BRANCH}.txt"
    echo "Capturing origin branch log for verification: $ORIGIN_LOG_FILE"
    git log ${SOURCE_REMOTE}/${BRANCH} --graph --oneline --pretty=format:"%H %s" | tac > "$ORIGIN_LOG_FILE"
    
    # Regex pattern to remove git graph symbols: |, |\, |\ , |/, |/, etc.
    # This matches any combination of |, /, \, spaces, and * at the start of lines
    GRAPH_SYMBOL_REGEX='^[[:space:]]*[|/\\_*[:space:]]+'
    
    echo "Verification enabled - will compare logs after each batch"
else
    echo "Verification disabled (--no-verify)"
fi

# Determine push options
if [ "$FORCE_PUSH" = true ]; then
    PUSH_OPTIONS="--force-with-lease"
    echo "⚠️  Force push enabled - will overwrite remote changes"
else
    PUSH_OPTIONS=""
    echo "Using safe push (will fail on conflicts)"
fi

# Verify logs before starting batch pushes
if [ "$VERIFY" = true ]; then
    echo "Verifying initial state before batch pushes..."
    if ! verify_logs; then
        echo "Initial verification failed. Exiting."
        exit 1
    fi
fi

# Push commits in batches
for ((i=0; i<total_commits; i+=BATCH_SIZE)); do
    # Calculate end index for this batch
    end=$((i + BATCH_SIZE - 1))
    if [ $end -ge $total_commits ]; then
        end=$((total_commits - 1))
    fi
    
    # Get the commit hashes for the start and end of this batch
    first_commit=${commits[$i]}
    target_commit=${commits[$end]}
    batch_num=$((i / BATCH_SIZE + 1))
    
    echo "Pushing batch $batch_num/$total_batches: commits $((i+1)) to $((end+1))"
    echo "  Range: $first_commit (first) -> $target_commit (last)"
    
    # Debug mode: list commits in this batch and ask for confirmation
    if [ "$DEBUG_MODE" = true ]; then
        echo ""
        echo "========== DEBUG MODE: Commits in batch $batch_num =========="
        for ((j=i; j<=end; j++)); do
            commit_hash=${commits[$j]}
            commit_info=$(git log -1 --format="%h - %s" $commit_hash)
            echo "$((j+1)). $commit_info"
        done
        echo "========================================================"
        echo ""
        read -p "Do you want to proceed with pushing batch $batch_num? [yes/no]: " batch_confirmation
        if [ "$batch_confirmation" != "yes" ]; then
            echo "Operation cancelled for batch $batch_num."
            exit 0
        fi
        echo ""
    fi
    
    # Push this batch using explicit refspecs
    # Push commits from origin's branch to destination's branch head
    # Pushing target_commit will include all parent commits (first_commit..target_commit range)
    echo "Executing: git push $PUSH_OPTIONS $REMOTE ${target_commit}:refs/heads/$BRANCH"
    echo "  (This updates refs/heads/$BRANCH to point to $target_commit from $SOURCE_REMOTE/$BRANCH)"
    if git push $PUSH_OPTIONS "$REMOTE" ${target_commit}:refs/heads/$BRANCH; then
        echo "[SUCCEEDED] Batch $batch_num pushed successfully"
        
        # Verification: compare logs after each batch
        if ! verify_logs; then
            exit 1
        fi
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