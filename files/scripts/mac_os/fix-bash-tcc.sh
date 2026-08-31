#!/usr/bin/env bash
set -euo pipefail

# 1. Locate the target binary and resolve its real path
SYMLINK_PATH="/usr/local/bin/bash"

if [[ ! -e "$SYMLINK_PATH" ]]; then
    echo "[-] Error: $SYMLINK_PATH does not exist."
    exit 1
fi

REAL_BASH_PATH=$(realpath "$SYMLINK_PATH")

echo "=================================================="
echo "[+] Target Symlink : $SYMLINK_PATH"
echo "[+] Real Binary    : $REAL_BASH_PATH"
echo "=================================================="

# 2. Reset existing TCC records for the current execution context
echo "[+] Resetting stale TCC permissions..."
tccutil reset SystemPolicyAllFiles com.apple.Terminal 2>/dev/null || true

# 3. Copy the exact real path to macOS clipboard
echo "$REAL_BASH_PATH" | pbcopy
echo "[+] Copied real binary path to clipboard!"

# 4. Reveal the exact binary in Finder
echo "[+] Opening Finder with binary selected..."
open -R "$REAL_BASH_PATH"

# 5. Open macOS System Settings directly to Full Disk Access
echo "[+] Launching System Settings -> Full Disk Access..."
open "x-apple.systempreferences:com.apple.preference.security?Privacy_AllFiles"

echo "=================================================="
echo "NEXT STEPS:"
echo " 1. Click '+' in Full Disk Access (or remove old bash entries)."
echo " 2. Press 'Cmd + Shift + G' in the file picker."
echo " 3. Press 'Cmd + V' (the exact binary path is on your clipboard)."
echo " 4. Hit Enter, select the binary, and toggle ON."
echo " 5. Restart your Terminal app (Cmd + Q)."
echo "=================================================="
