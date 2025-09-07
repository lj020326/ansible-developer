#!/bin/bash

# Function to display usage information
usage() {
    echo "Usage: $0 <role_path> <output_file>"
    echo "Concatenates all files in an Ansible role path into a single output file."
    echo "Each file's content is preceded by a header comment indicating its relative path."
    exit 1
}

# Check if correct number of arguments are provided
if [ "$#" -ne 2 ]; then
    usage
fi

ROLE_PATH="$1"
# Derive the role name and output file name
ROLE_NAME=$(basename "$ROLE_PATH")
OUTPUT_FILE="${ROLE_NAME}.txt"

# Check if the role path exists and is a directory
if [ ! -d "$ROLE_PATH" ]; then
    echo "Error: Role path '$ROLE_PATH' does not exist or is not a directory."
    exit 1
fi

# Create or clear the output file
> "$OUTPUT_FILE"

echo "Concatenating files from role: $ROLE_PATH"
echo "Output will be saved to: $OUTPUT_FILE"
echo ""

# Find all regular files in the role path and its subdirectories
# Loop through each found file
find "$ROLE_PATH" -type f | while read -r FILE_PATH; do
    # Get the relative path of the file from the role_path
    RELATIVE_PATH="${FILE_PATH#$ROLE_PATH/}"

    # Add a header comment to the output file
    echo "### FILE: $RELATIVE_PATH ###" >> "$OUTPUT_FILE"
    echo "" >> "$OUTPUT_FILE" # Add an empty line for readability

    # Concatenate the file's content
    cat "$FILE_PATH" >> "$OUTPUT_FILE"

    echo "" >> "$OUTPUT_FILE" # Add an empty line after file content
    echo "### END FILE: $RELATIVE_PATH ###" >> "$OUTPUT_FILE"
    echo "" >> "$OUTPUT_FILE" # Add an empty line before the next file
done

echo "Concatenation complete! All files from '$ROLE_PATH' are saved in '$OUTPUT_FILE'."
