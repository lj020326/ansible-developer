#!/usr/bin/env bash
# ==============================================================================
# Script Name: fix-chrome-dns.sh
# Description: Configures macOS system-level enterprise policies for Chrome to:
#              1. Disable Chrome's built-in async DNS (force native macOS resolver)
#              2. Apply URL allowlists for internal .int domains
#              3. Clear DNS cache / socket pools via graceful browser reset
# ==============================================================================

set -euo pipefail

PLIST_PATH="/Library/Preferences/com.google.Chrome.plist"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Chrome Homelab & Resolver Fixer ===${NC}"

# 1. Ensure script is run with sudo for system-level preference plist writes
if [[ $EUID -ne 0 ]]; then
   echo -e "${RED}[ERROR] This script must be run with sudo privileges to update /Library/Preferences/.${NC}"
   echo "Usage: sudo $0"
   exit 1
fi

echo -e "\n${YELLOW}[1/3] Applying System-Level Chrome Enterprise Policies...${NC}"

# Disable built-in async DNS client (Forces Chrome to use macOS getaddrinfo / scutil)
defaults write "$PLIST_PATH" BuiltInDnsClientEnabled -bool false
echo "  ✔ Disabled Chrome Built-In Async DNS Client"

# Apply URL Allowlist for internal domains to bypass intranet sandboxing barriers
defaults write "$PLIST_PATH" URLAllowlist -array \
  "*.admin.johnson.int" \
  "*.media.johnson.int" \
  "*.johnson.int"
echo "  ✔ Configured URLAllowlist for *.johnson.int domains"

# Flush macOS preference cache
killall cfprefsd 2>/dev/null || true
echo "  ✔ Flushed macOS preference daemon cache"


echo -e "\n${YELLOW}[2/3] Handling DNS Cache & Socket Reset...${NC}"

# Check if Google Chrome is currently running
if pgrep -xq "Google Chrome"; then
    echo -e "  ℹ Google Chrome is currently running."
    read -rp "Do you want to gracefully restart Chrome now to clear DNS/socket pools? (y/N) " response
    if [[ "$response" =~ ^([yY][eS]|[yY])$ ]]; then
        echo "  → Quitting Google Chrome gracefully..."
        osascript -e 'quit app "Google Chrome"'

        # Wait for process to terminate
        while pgrep -xq "Google Chrome"; do
            sleep 0.5
        done

        echo "  → Launching Google Chrome..."
        open -a "Google Chrome"
        echo "  ✔ Chrome restarted successfully with fresh DNS/socket pools."
    else
        echo "  ℹ Skipped restart. Remember to visit chrome://net-internals/#dns to clear host cache manually if needed."
    fi
else
    echo "  ✔ Chrome is not running. Next launch will use fresh DNS cache."
fi


echo -e "\n${YELLOW}[3/3] Verification Instructions${NC}"
echo -e "  • Open Chrome and navigate to: ${BLUE}chrome://policy${NC}"
echo -e "  • Click ${BLUE}'Reload policies'${NC} to confirm 'BuiltInDnsClientEnabled' is false."
echo -e "  • Navigate to your internal endpoint: ${GREEN}https://kanban.admin.johnson.int${NC}"

echo -e "\n${GREEN}=== Chrome fix configuration complete! ===${NC}"
