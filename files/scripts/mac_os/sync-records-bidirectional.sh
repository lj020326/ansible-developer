#!/usr/bin/env bash

########
# deprecated by same name python script "sync-records-bidirectional.py"
########

set -euo pipefail

# --- Configuration ---
LOCAL_DIR="/Users/ljohnson/Documents/records/"
REMOTE_DIR="/Users/ljohnson/data/Records/"

RSYNC="/usr/bin/rsync"
EXCLUDES=("--exclude=.DS_Store" "--exclude=*.tmp" "--exclude=Thumbs.db")
COMMON_OPTS=("-avzu" "--inplace" "--no-perms" "--no-owner" "--no-group" "--no-times")

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# Safety check — abort if SMB mount is missing or not writable
if [[ ! -d "$REMOTE_DIR" ]] || [[ ! -w "$REMOTE_DIR" ]]; then
    log "ERROR: SMB mount not available or not writable at $REMOTE_DIR — skipping sync"
    exit 1
fi

log "=== Starting bidirectional records sync ==="

log "Step 1: Pulling newer/changed files from network share → local..."
if ! "${RSYNC}" "${COMMON_OPTS[@]}" "${EXCLUDES[@]}" "${REMOTE_DIR}" "${LOCAL_DIR}"; then
    log "Pull failed"
    exit 1
fi

log "Step 2: Pushing local changes → network share..."
if ! "${RSYNC}" "${COMMON_OPTS[@]}" "${EXCLUDES[@]}" "${LOCAL_DIR}" "${REMOTE_DIR}"; then
    log "Push failed"
    exit 1
fi

log "=== Bidirectional sync completed successfully ==="
