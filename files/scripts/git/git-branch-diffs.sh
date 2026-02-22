#!/bin/bash

# 1. Check if a branch was provided
if [ -z "$1" ]; then
    echo "Usage: $0 <compare-branch> [output-directory]"
    echo "Example: $0 develop save/"
    exit 1
fi

TARGET_BRANCH=$1
OUT_DIR=${2:-"save/"} # Default to save/ if 2nd arg is missing
FILE_NAME="git-branch-diffs.txt"
FULL_PATH="${OUT_DIR%/}/$FILE_NAME"

# 2. Ensure the output directory exists
mkdir -p "$OUT_DIR"

# 3. Check if the branch exists
if ! git rev-parse --verify "$TARGET_BRANCH" >/dev/null 2>&1; then
    echo "Error: Branch '$TARGET_BRANCH' does not exist."
    exit 1
fi

echo "Comparing current branch to: $TARGET_BRANCH"
echo "Excluding files defined in .gitignore..."

# 4. Generate the diff
# --color=never ensures the text file is clean for reading/applying
# We compare the target branch against the current HEAD
git diff "$TARGET_BRANCH"..HEAD > "$FULL_PATH"

# 5. Final Report
if [ -s "$FULL_PATH" ]; then
    echo "Success! Difference file created at: $FULL_PATH"
    echo "Summary of changes:"
    git diff "$TARGET_BRANCH"..HEAD --stat
else
    echo "No differences found between current branch and $TARGET_BRANCH."
    rm "$FULL_PATH"
fi
