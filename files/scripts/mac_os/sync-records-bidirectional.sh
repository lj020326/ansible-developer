#!/usr/bin/env bash
set -euo pipefail

LOCAL_DIR="/Users/ljohnson/Documents/records/"
REMOTE_DIR="/Users/ljohnson/data/Records/"

RSYNC="/usr/bin/rsync"
EXCLUDES="--exclude=.DS_Store --exclude=*.tmp --exclude=Thumbs.db"
COMMON_OPTS="-avzu --inplace --no-perms --no-owner --no-group --no-times"

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
$RSYNC $COMMON_OPTS $EXCLUDES "$REMOTE_DIR" "$LOCAL_DIR"

log "Step 2: Pushing local changes → network share..."
$RSYNC $COMMON_OPTS $EXCLUDES "$LOCAL_DIR" "$REMOTE_DIR"

log "=== Bidirectional sync completed successfully ==="
