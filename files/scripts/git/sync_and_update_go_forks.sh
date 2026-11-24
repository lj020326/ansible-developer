#!/usr/bin/env bash
set -euo pipefail

function abort() {
    echo "$1"
    exit 1
}

UPSTREAM_ORG="soulteary"
FORK_ORG="lj020326"
BASE_URL="github.com"

# List of repository names to process
REPOS=(
    "cli-kit"
    "health-kit"
    "http-kit"
    "httpcache-kit"
    "logger-kit"
    "metrics-kit"
    "middleware-kit"
    "tracing-kit"
    "version-kit"
    "vfs-kit"
)

# Temporary working directory for clones
#WORK_DIR=$(mktemp -d -t go-fork-sync-XXXXXX)
WORK_DIR="${HOME}/repos/github/soulteary"
echo "==> Working directory: ${WORK_DIR}"
mkdir -p "${WORK_DIR}"
echo ""

#cleanup() {
#    echo "==> Cleaning up temporary workspace..."
#    rm -rf "${WORK_DIR}"
#}
#trap cleanup EXIT

for REPO in "${REPOS[@]}"; do
    echo "========================================================================"
    echo "Processing repository: ${REPO}"
    echo "========================================================================"

    REPO_DIR="${WORK_DIR}/${REPO}"
    FORK_URL="git@${BASE_URL}:${FORK_ORG}/${REPO}.git"
    UPSTREAM_URL="git@${BASE_URL}:${UPSTREAM_ORG}/${REPO}.git"

    # 1. Clone or pull the forked repository
    if [ -d "${REPO_DIR}/.git" ]; then
        echo "==> [1/6] Directory ${REPO_DIR} exists, fetching latest origin..."
        cd "${REPO_DIR}" || abort "unable to cd to ${REPO_DIR}"
        git fetch origin
    else
        echo "==> [1/6] Cloning fork from ${FORK_URL}..."
        git clone "${FORK_URL}" "${REPO_DIR}"
        cd "${REPO_DIR}" || abort "unable to cd to ${REPO_DIR}"
    fi

    # 2. Add/configure upstream remote
    echo "==> [2/6] Configuring upstream remote..."
    if ! git remote | grep -q "^upstream$"; then
        git remote add upstream "${UPSTREAM_URL}"
    else
        git remote set-url upstream "${UPSTREAM_URL}"
    fi

    # 3. Sync tags from upstream
    echo "==> [3/6] Fetching and syncing tags from upstream..."
    git fetch upstream --tags
    git push origin --tags || true

    # 4. Update go.mod module declaration
    echo "==> [4/6] Updating go.mod module declaration..."
    if [ -f "go.mod" ]; then
        OLD_MOD="${BASE_URL}/${UPSTREAM_ORG}/${REPO}"
        NEW_MOD="${BASE_URL}/${FORK_ORG}/${REPO}"

        # Use perl for cross-platform in-place replacement
        perl -pi -e "s|\bmodule ${OLD_MOD}\b|module ${NEW_MOD}|g" go.mod
    else
        echo "Warning: go.mod not found in ${REPO}!"
    fi

    # 5. Update internal imports in .go files
    echo "==> [5/6] Updating internal package imports in .go files..."
    OLD_IMPORT="${BASE_URL}/${UPSTREAM_ORG}"
    NEW_IMPORT="${BASE_URL}/${FORK_ORG}"

    # Find all .go files and replace upstream path with fork path
    find . -type f -name "*.go" -not -path "*/.*" | while read -r go_file; do
        perl -pi -e "s|${OLD_IMPORT}|${NEW_IMPORT}|g" "${go_file}"
    done

    # Run go mod tidy directly against VCS (bypassing cached proxy responses)
    if command -v go &>/dev/null && [ -f "go.mod" ]; then
        echo "==> Running go mod tidy with direct proxy..."
        GOPROXY=direct go mod tidy || true
    fi

    # 6. Status, stage, commit, and prompt push
    echo "==> [6/6] Reviewing Git Status:"
    echo "------------------------------------------------------------------------"
    git status --short
    echo "------------------------------------------------------------------------"

    if [ -z "$(git status --porcelain)" ]; then
        echo "No changes detected for ${REPO}."
    else
        git add .
        git commit -m "refactor: update module path and imports to ${FORK_ORG}/${REPO}"

        echo ""
        read -rp "Push commit and updated tags for '${REPO}' to origin? (y/N): " -n 1 -r REPLY </dev/tty
        echo ""
        if [[ "${REPLY}" =~ ^[Yy]$ ]]; then
            echo "==> Pushing branch and tags to origin..."
            git push origin HEAD
            echo "Successfully pushed ${REPO}."
        else
            echo "Skipped push for ${REPO}."
        fi
    fi

    cd "${WORK_DIR}" || abort "unable to cd to ${WORK_DIR}"
    echo ""
done

echo "==> All repositories processed successfully."
