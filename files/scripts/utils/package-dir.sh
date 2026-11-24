#!/usr/bin/env bash

# Exit immediately if a pipeline returns a non-zero status
set -o pipefail

# --- Usage Function ---
usage() {
    cat << EOF
Usage: $(basename "$0") [OPTIONS] <directory_path> [ignore_dir1] [ignore_dir2] ...

Packages text files within a directory into a single text file, skipping binaries,
images, and excluded directories.

Options:
  -o <file_path>  Specify a custom output file path.
                  (Default: <directory_path>/save/directory.<dir_name>.txt)
  -s <size_mb>    Specify file size threshold warning in megabytes (MB).
                  (Default: 10)
  -n              Disable Git integration. Forces standard 'find' search even
                  if target directory is inside a Git repository.
  -h              Show this help message and exit.

Examples:
  $(basename "$0") my_project
  $(basename "$0") -s 15 my_project
  $(basename "$0") -n my_project node_modules .venv
  $(basename "$0") -o /tmp/dump.txt my_project
EOF
    exit 1
}

function main() {
    # --- Parse Options ---
    OUTPUT_FILE_CUSTOM=""
    SIZE_THRESHOLD_MB=10
    USE_GIT=true

    while getopts "o:s:nh" opt; do
        case "${opt}" in
            o) OUTPUT_FILE_CUSTOM="$OPTARG" ;;
            s) SIZE_THRESHOLD_MB="$OPTARG" ;;
            n) USE_GIT=false ;;
            h) usage ;;
            *) usage ;;
        esac
    done

    # Validate that size threshold is a positive integer
    if ! [[ "$SIZE_THRESHOLD_MB" =~ ^[0-9]+$ ]]; then
        echo "Error: Size threshold (-s) must be a positive integer in MB." >&2
        exit 1
    fi

    # Shift away the parsed options ($OPTIND is the index of the next argument)
    shift $((OPTIND - 1))

    # Check for the mandatory directory argument
    if [ -z "$1" ]; then
        echo "Error: Missing required directory path." >&2
        usage
    fi

    # --- Configuration & Paths ---
    DIR_PATH="${1%/}"

    if [ ! -d "$DIR_PATH" ]; then
        echo "Error: Directory path '$DIR_PATH' does not exist." >&2
        exit 1
    fi

    # Base folder exclusions
    BASE_EXCLUDE_DIRS="\.git|\.idea|\.DS_Store|\.test|\.tmp|vault|\.vault|__pycache__"
    BASE_EXCLUDE_DIRS+="|output|save|assets|build|releases|archive|old"

    # Image / non-code media extensions to exclude
    FILE_EXT_EXCLUDES="\.(svg|png|jpg|jpeg|gif|ico|webp|pdf|zip|tar|gz|7z)$"

    # Capture all trailing arguments as custom ignores
    shift
    CUSTOM_EXCLUDES=""
    for arg in "$@"; do
        # Escape any dots or special regex characters in user input
        # shellcheck disable=SC2001
        escaped_arg=$(echo "$arg" | sed 's/\./\\./g')
        if [ -z "$CUSTOM_EXCLUDES" ]; then
            CUSTOM_EXCLUDES="$escaped_arg"
        else
            CUSTOM_EXCLUDES="${CUSTOM_EXCLUDES}|${escaped_arg}"
        fi
    done

    # Combine directory excludes
    if [ -n "$CUSTOM_EXCLUDES" ]; then
        ALL_DIR_EXCLUDES="${BASE_EXCLUDE_DIRS}|${CUSTOM_EXCLUDES}"
    else
        ALL_DIR_EXCLUDES="${BASE_EXCLUDE_DIRS}"
    fi

    # Regex for standard 'find' command
    EXCLUDE_REGEX=".*/(${ALL_DIR_EXCLUDES})|.*${FILE_EXT_EXCLUDES}"

    # Extended Regex for Bash regex operator (=~) when testing Git paths
    GIT_DIR_EXCLUDE_REGEX="(^|/)(${ALL_DIR_EXCLUDES})(/|$)"

    # Resolve absolute path
    ABS_DIR_PATH=$(cd "$DIR_PATH" && pwd)
    DIRECTORY_NAME=$(basename "${ABS_DIR_PATH}")

    # Determine final output file location
    if [ -n "$OUTPUT_FILE_CUSTOM" ]; then
        OUTPUT_FILE="$OUTPUT_FILE_CUSTOM"
    else
        OUTPUT_FILE="${DIR_PATH}/save/directory.${DIRECTORY_NAME}.txt"
    fi

    OUTPUT_DIR=$(dirname "${OUTPUT_FILE}")

    echo "Ensuring output dir exists: ${OUTPUT_DIR}"
    mkdir -p "${OUTPUT_DIR}"
    # shellcheck disable=SC2188
    > "${OUTPUT_FILE}"

    echo "Packaging directory: ${DIRECTORY_NAME}"

    # Determine execution strategy (Git vs Find)
    IS_GIT_REPO=false
    if [ "$USE_GIT" = true ] && git -C "$DIR_PATH" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
        IS_GIT_REPO=true
    fi

    if [ "$IS_GIT_REPO" = true ]; then
        echo "Strategy: Git tracking (observing .gitignore rules)"
        echo "Excluding directory patterns matching: ${GIT_DIR_EXCLUDE_REGEX}"
        echo "Excluding file extensions matching: ${FILE_EXT_EXCLUDES}"
        echo "Filtering out non-text files..."
        echo "---"

        git -C "$DIR_PATH" ls-files --cached --others --exclude-standard | while read -r RELATIVE_PATH; do
            FILE_PATH="${DIR_PATH}/${RELATIVE_PATH}"

            # Skip directory ignore patterns
            if [[ "$RELATIVE_PATH" =~ $GIT_DIR_EXCLUDE_REGEX ]]; then
                continue
            fi

            # Skip image and excluded file extensions
            if [[ "$RELATIVE_PATH" =~ $FILE_EXT_EXCLUDES ]]; then
                continue
            fi

            # Skip output file if saved inside the target path
            [[ "$FILE_PATH" == "$OUTPUT_FILE" ]] && continue

            # Determine binary status: empty files (0 bytes) are treated as text
            IS_BINARY=""
            if [ -s "$FILE_PATH" ]; then
                IS_BINARY=$(file -L -b --mime "$FILE_PATH" 2>/dev/null | grep "charset=binary")
            fi

            if [ -z "$IS_BINARY" ] && [ -f "$FILE_PATH" ]; then
                {
                    echo "### FILE: $RELATIVE_PATH ###"
                    echo ""
                    cat "$FILE_PATH"
                    echo ""
                    echo "### END FILE: $RELATIVE_PATH ###"
                    echo ""
                } >> "$OUTPUT_FILE"
            elif [ -n "$IS_BINARY" ]; then
                echo "Skipping binary: $RELATIVE_PATH" >&2
            fi
        done
    else
        echo "Strategy: Standard find (ignoring Git tracking)"
        echo "Excluding patterns matching: ${EXCLUDE_REGEX}"
        echo "Filtering out non-text files..."
        echo "---"

        # Use the EXCLUDE_REGEX variable in the find command
        # -regextype posix-extended: Ensures the variable is interpreted correctly
        find -L "$DIR_PATH" \
          -regextype posix-extended -regex "$EXCLUDE_REGEX" -prune \
          -o \( -type f -o -type l \) -print | while read -r FILE_PATH; do

            # Prevent the script from reading its own output file
            [[ "$FILE_PATH" == "$OUTPUT_FILE" ]] && continue

            # Determine binary status: empty files (0 bytes) are treated as text
            IS_BINARY=""
            if [ -s "$FILE_PATH" ]; then
                IS_BINARY=$(file -L -b --mime "$FILE_PATH" 2>/dev/null | grep "charset=binary")
            fi

            if [ -z "$IS_BINARY" ] && [ -f "$FILE_PATH" ]; then
                RELATIVE_PATH="${FILE_PATH#"${DIR_PATH}"/}"

                {
                    echo "### FILE: $RELATIVE_PATH ###"
                    echo ""
                    cat "$FILE_PATH"
                    echo ""
                    echo "### END FILE: $RELATIVE_PATH ###"
                    echo ""
                } >> "$OUTPUT_FILE"
            elif [ -n "$IS_BINARY" ]; then
                echo "Skipping binary: $FILE_PATH" >&2
            fi
        done
    fi

    echo "---"
    echo "Packaging complete! Saved in '$OUTPUT_FILE'."

    # --- File Size Check ---
    FILE_SIZE_BYTES=$(wc -c < "$OUTPUT_FILE" | tr -d ' ')
    THRESHOLD_BYTES=$((SIZE_THRESHOLD_MB * 1024 * 1024))

    # Format human-readable output size
    FILE_SIZE_MB=$(awk -v bytes="$FILE_SIZE_BYTES" 'BEGIN { printf "%.2f", bytes / (1024 * 1024) }')

    if [ "$FILE_SIZE_BYTES" -gt "$THRESHOLD_BYTES" ]; then
        echo ""
        echo "WARNING: Output file size (${FILE_SIZE_MB} MB) exceeds the threshold limit of ${SIZE_THRESHOLD_MB} MB!" >&2
    fi
}

main "$@"
