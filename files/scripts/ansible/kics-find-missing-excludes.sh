#!/usr/bin/env bash
#
# Script: kics-find-missing-excludes.sh
# Purpose: Finds missing exclude-paths by running a live 'find' on specified directories.
# Usage: ./kics-find-missing-excludes.sh ".kics-config.yml" "inventory,playbooks,roles,molecule,tests,vars"

set -euo pipefail

# Parameters
KICS_CONFIG="${1:-.kics-config.yml}"
# Default search directories if none provided
SEARCH_DIRS="${2:-inventory,playbooks,roles,molecule,tests,vars}"

# -----------------------------------------------------------------------------
# Check dependencies and files
# -----------------------------------------------------------------------------
command -v yq >/dev/null 2>&1 || {
    echo "Error: 'yq' is required. Install it: https://github.com/mikefarah/yq" >&2
    exit 1
}

if [[ ! -f "$KICS_CONFIG" ]]; then
    echo "Error: KICS config file not found: $KICS_CONFIG" >&2
    exit 1
fi

echo "Using KICS config   : $KICS_CONFIG"
echo "Searching in        : {$SEARCH_DIRS}/"
echo ""

# -----------------------------------------------------------------------------
# Step 1: Extract file-like exclude paths using yq
# -----------------------------------------------------------------------------
# Extract items from exclude-paths that are not glob patterns
mapfile -t exclude_files < <(yq eval '.["exclude-paths"][] | select(test("\*") == false)' "$KICS_CONFIG")

if [[ ${#exclude_files[@]} -eq 0 ]]; then
    echo "No file-specific exclude paths found in $KICS_CONFIG"
    exit 0
fi

# -----------------------------------------------------------------------------
# Step 2: Load "Runtime" find results into associative array
# -----------------------------------------------------------------------------
declare -A seen
count=0

# The '|| true' ensures that when 'read' hits EOF (exit code 1),
# the script doesn't exit due to 'set -e'
while IFS= read -r path; do
    [[ -z "$path" ]] && continue
    # Strip trailing slashes from find output to match config format
    clean_find_path="${path%/}"
    seen["$clean_find_path"]=1
    ((count++))
done < <(eval "find {${SEARCH_DIRS}}/ 2>/dev/null") || true

echo "Loaded $count paths from live search."
echo "Checking ${#exclude_files[@]} exclude entries..."

# -----------------------------------------------------------------------------
# Step 3: Compare and find missing
# -----------------------------------------------------------------------------
missing=()
found_count=0

for path in "${exclude_files[@]}"; do
    # Clean the path (strip whitespace/CR)
    clean_path=$(echo "$path" | tr -d '\r' | xargs)
    [[ -z "$clean_path" ]] && continue

    if [[ ${seen[$clean_path]+isset} == "isset" ]]; then
        found_count=$((found_count + 1))
    else
        missing+=("$clean_path")
    fi
done

# -----------------------------------------------------------------------------
# Step 4: Report summary
# -----------------------------------------------------------------------------
total_checked=${#exclude_files[@]}
missing_count=${#missing[@]}

echo "Summary:"
echo "  - Checked       : $total_checked"
echo "  - Still exist   : $found_count"
echo "  - Missing       : $missing_count"
echo ""

if [[ $missing_count -eq 0 ]]; then
    echo "All file-specific excluded paths still exist. Nothing to clean up."
else
  echo "The following $missing_count paths are listed in exclude-paths but no longer exist:"
  echo "----------------------------------------------------------------------------"
  echo "exclude-paths:"
  for path in "${missing[@]}"; do
      echo "  - $path"
  done
  echo "----------------------------------------------------------------------------"
  echo "# ^ Remove the above items from the existing exclude-paths section."
fi

exit 0
