#!/usr/bin/env bash

# Exit immediately if a pipeline returns a non-zero status
set -o pipefail

# --- Usage Function ---
usage() {
    cat << EOF
Usage: $(basename "$0") [OPTIONS] <directory_path> [ignore_dir1] [ignore_dir2] ...

Packages text files within a directory into a single text file, skipping binaries
and excluded directories.

Options:
  -o <file_path>  Specify a custom output file path.
                  (Default: <directory_path>/save/directory.<dir_name>.txt)
  -h              Show this help message and exit.

Examples:
  $(basename "$0") my_project
  $(basename "$0") -o /tmp/dump.txt my_project node_modules .venv
EOF
    exit 1
}

function main() {
    # --- Parse Options ---
    OUTPUT_FILE_CUSTOM=""

    while getopts "o:h" opt; do
        case " ${opt} " in
            o) OUTPUT_FILE_CUSTOM="$OPTARG" ;;
            h) usage ;;
            *) usage ;;
        esac
    done

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

    # Base exclude patterns
    BASE_EXCLUDES="\.git|\.idea|\.DS_Store|\.test|\.tmp|__pycache__|output|save|releases|archive|old"

    # Capture all trailing arguments as custom ignores
    shift
    CUSTOM_EXCLUDES=""
    for arg in "$@"; do
        # Escape any dots or special regex characters in user input
        escaped_arg=$(echo "$arg" | sed 's/\./\\./g')
        if [ -z "$CUSTOM_EXCLUDES" ]; then
            CUSTOM_EXCLUDES="$escaped_arg"
        else
            CUSTOM_EXCLUDES="${CUSTOM_EXCLUDES}|${escaped_arg}"
        fi
    done

    # Combine base and custom excludes into the final regex
    if [ -n "$CUSTOM_EXCLUDES" ]; then
        EXCLUDE_REGEX=".*/(${BASE_EXCLUDES}|${CUSTOM_EXCLUDES})$"
    else
        EXCLUDE_REGEX=".*/(${BASE_EXCLUDES})$"
    fi

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
    echo "Excluding patterns matching: ${EXCLUDE_REGEX}"
    echo "Filtering out non-text files..."
    echo "---"

    # Use the EXCLUDE_REGEX variable in the find command
    # -L: Follow symlinks
    # -regextype posix-extended: Ensures the variable is interpreted correctly
    find -L "$DIR_PATH" \
      -regextype posix-extended -regex "$EXCLUDE_REGEX" -prune \
      -o \( -type f -o -type l \) -print | while read -r FILE_PATH; do

        # Prevent the script from reading its own output file
        [[ "$FILE_PATH" == "$OUTPUT_FILE" ]] && continue

        # Check for binary content (dereferencing symlinks with -L)
        IS_BINARY=$(file -L -b --mime "$FILE_PATH" | grep "charset=binary")

        if [ -z "$IS_BINARY" ] && [ -f "$FILE_PATH" ]; then
            RELATIVE_PATH="${FILE_PATH#$DIR_PATH/}"

            # SC2129: Grouping redirects for efficiency and readability
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

    echo "---"
    echo "Packaging complete! Saved in '$OUTPUT_FILE'."
}

main "$@"
