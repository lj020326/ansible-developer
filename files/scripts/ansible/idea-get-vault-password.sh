#!/usr/bin/env bash

## ref: https://plugins.jetbrains.com/plugin/14353-ansible-vault-integration/tutorials/vault-file-as-script

function abort() {
    echo "$1"
    exit 1
}

# Helper to show error message
function log_error() {
    echo >&2 "$1"
    exit 2
}

## no-op when not debugging
function log_info() {
    #   >&2 echo "$1"
    true
}

#env_info=$(export -p | grep -i -e linux | sed 's/declare -x //')
#log_info "**** env_info: ${env_info}"

# Check script is not called directly
if [ -z "$IDEA_ANSIBLE_VAULT_CONTEXT_DIRECTORY" ]; then
    log_error "Call is not coming from IntelliJ Plugin"
fi

CONTENT_DIR=$(dirname "${IDEA_ANSIBLE_VAULT_CONTEXT_FILE}")
log_info "==> CONTENT_DIR=${CONTENT_DIR}"
cd "${CONTENT_DIR}" || abort "unable to cd to ${CONTENT_DIR}"

IFS="/" read -ra CONTENT_DIR_ARRAY <<<"${CONTENT_DIR}"

SECRET_FILE=".vault_pass"

for ((idx = ${#CONTENT_DIR_ARRAY[@]} - 1; idx >= 0; idx--)); do
    SECRET_PATH="${PWD}/${SECRET_FILE}"
    log_info "==> Checking idx=$idx SECRET_PATH=${SECRET_PATH}"
    if [ -f "${SECRET_PATH}" ]; then
        log_info "==> Found SECRET_PATH=${SECRET_PATH}"
        SECRET=$(cat "${SECRET_PATH}")
        break
    else
        cd "../" || abort "unable to cd to ../"
    fi
done

if [ -z "$SECRET" ]; then
    SECRET_PATH="${HOME}/${SECRET_FILE}"
    log_info "==> Checking idx=$idx SECRET_PATH=${SECRET_PATH}"
    if [ -f "${SECRET_PATH}" ]; then
        log_info "==> Found SECRET_PATH=${SECRET_PATH}"
        SECRET=$(cat "${SECRET_PATH}")
    fi
fi

if [ -n "$SECRET" ]; then
    log_info "==> SECRET_PATH=${SECRET_PATH}"
    ##  log_info "==> SECRET=${SECRET}"
    #  echo -n "${SECRET}"
    #  echo "${SECRET_PATH}"
    cat "${SECRET_PATH}"
else
    log_error "Secret file '${SECRET_FILE}' not found"
fi
