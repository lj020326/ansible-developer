#!/bin/bash

# Function to create an Ansible role from a single combined file
#
# Arguments:
#   $1: Path to the downloaded role file (e.g., ~/the_role_file_you_provided.txt)
#       This file is expected to contain content for tasks/main.yml,
#       defaults/main.yml, meta/main.yml, and handlers/main.yml,
#       delimited by lines like '^# FILE: <path>'.
#   $2: Path to the specified role target location (e.g., roles/prepare_kubernetes)
#       This is the directory where the new role will be created.
#
# Usage Example:
#   explode_ansible_role /path/to/my_combined_role_file.txt /path/to/ansible/roles/prepare_kubernetes
explode_ansible_role() {
    local input_file="$1"
    local full_role_path="$2" # This is the full path including the role name

    # Validate arguments
    if [ -z "$input_file" ] || [ -z "$full_role_path" ]; then
        echo "Usage: explode_ansible_role <path_to_combined_role_file> <path_to_role_target_location>"
        echo "Example: explode_ansible_role ~/bootstrap_kubernetes.yml roles/bootstrap_kubernetes"
        return 1
    fi

    if [ ! -f "$input_file" ]; then
        echo "Error: Input file '$input_file' not found."
        return 1
    fi

    # Determine role name from the full_role_path
    local role_name=$(basename "$full_role_path")

    # Define paths for the new role's components
    local tasks_dir="${full_role_path}/tasks"
    local defaults_dir="${full_role_path}/defaults"
    local meta_dir="${full_role_path}/meta"
    local handlers_dir="${full_role_path}/handlers"

    echo "Creating Ansible role '${role_name}' structure at: ${full_role_path}"

    # Create directories
    mkdir -p "$tasks_dir" || { echo "Failed to create ${tasks_dir}"; return 1; }
    mkdir -p "$defaults_dir" || { echo "Failed to create ${defaults_dir}"; return 1; }
    mkdir -p "$meta_dir" || { echo "Failed to create ${meta_dir}"; return 1; }
    mkdir -p "$handlers_dir" || { echo "Failed to create ${handlers_dir}"; return 1; }

    echo "Extracting content from '$input_file' and writing to role files..."

    local current_output_file=""
    local current_file_descriptor=""

    # Read the input file line by line
    while IFS= read -r line || [[ -n "$line" ]]; do
        # Check for start markers
        if [[ "$line" =~ ^#\ FILE:\ (.*)$ ]]; then
            # Close previous file if open
            if [ -n "$current_file_descriptor" ]; then
                exec {current_file_descriptor}>&-
                current_file_descriptor=""
            fi

            local relative_path="${BASH_REMATCH[1]}"
            # Determine the full path for the current output file
            case "$relative_path" in
                "prepare_kubernetes/tasks/main.yml")
                    current_output_file="${tasks_dir}/main.yml"
                    ;;
                "prepare_kubernetes/defaults/main.yml")
                    current_output_file="${defaults_dir}/main.yml"
                    ;;
                "prepare_kubernetes/meta/main.yml")
                    current_output_file="${meta_dir}/main.yml"
                    ;;
                "prepare_kubernetes/handlers/main.yml")
                    current_output_file="${handlers_dir}/main.yml"
                    ;;
                *)
                    echo "Warning: Unrecognized file path marker: '$relative_path'. Skipping content."
                    current_output_file="" # Reset to ignore content until next recognized marker
                    continue
                    ;;
            esac
            # Open new file for writing (redirect stdout for subsequent echoes)
            exec {current_file_descriptor}>"$current_output_file"
            echo "  --> Writing to: ${current_output_file}"
            continue # Skip the marker line itself
        fi

        # If we have an open file descriptor, write the line to it
        if [ -n "$current_file_descriptor" ]; then
            echo "$line" >&"$current_file_descriptor"
        fi
    done < "$input_file"

    # Close the last file if it was open
    if [ -n "$current_file_descriptor" ]; then
        exec {current_file_descriptor}>&-
    fi

    echo "Ansible role '${role_name}' created successfully at ${full_role_path}."
}

explode_ansible_role "${@}"
