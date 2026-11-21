#!/usr/bin/env bash

## ref: http://www.cubicrace.com/2016/03/log-tracing-mechnism-for-shell-scripts.html

SCRIPT_DIR="$(dirname "$0")"

# shellcheck source=/dev/null
source "${SCRIPT_DIR}/logger.sh"

# shellcheck disable=SC2034
SCRIPT_LOG="./log/demo.log"

SCRIPTENTRY
updateUserDetails(){
    ENTRY
    log_debug "Username: $1, Key: $2"
    log_info "User details updated for $1"
    EXIT
}

log_info "Updating user details..."
updateUserDetails "cubicrace" "3445"
rc="$?"

if [ "${rc}" -ne 0 ]
then
    ERROR "Failed to update user details. RC=$rc"
fi
SCRIPTEXIT
