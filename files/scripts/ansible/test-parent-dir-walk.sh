#!/usr/bin/env bash

function abort() {
    echo "$1"
    exit 1
}

CONTENT_DIR=$(dirname "${PWD}")

IFS="/" read -ra CONTENT_DIR_ARRAY <<<"${CONTENT_DIR}"

SECRET_FILE=".vault_pass"

for ((idx = ${#CONTENT_DIR_ARRAY[@]} - 1; idx >= 0; idx--)); do
    SECRET_PATH="${PWD}/${SECRET_FILE}"
    echo "==> Checking idx=$idx SECRET_PATH=${SECRET_PATH}"
    if [ -f "${SECRET_PATH}" ]; then
        echo "==> Found SECRET_PATH=${SECRET_PATH}"
        SECRET=$(cat "${SECRET_PATH}")
        break
    else
        cd "../" || abort "unable to cd to ../"
    fi
done

if [ -z "$SECRET" ]; then
    SECRET_PATH="${HOME}/${SECRET_FILE}"
    echo "==> Checking idx=$idx SECRET_PATH=${SECRET_PATH}"
    if [ -f "${SECRET_PATH}" ]; then
        echo "==> Found SECRET_PATH=${SECRET_PATH}"
        SECRET=$(cat "${SECRET_PATH}")
    fi
fi

if [ -n "$SECRET" ]; then
    echo "${SECRET}"
else
    #    env_info=$(export -p | grep -i linux_middleware_playbooks | sed 's/declare -x //')
    #    env_info=$(export -p | grep -i -e pwd -e idea | sed 's/declare -x //')
    #    log_error "**** env_info: ${env_info}"
    log_error "Secret file '${SECRET_FILE}' not found"
fi
