#!/usr/bin/env bash

## ref: http://www.cubicrace.com/2016/03/log-tracing-mechnism-for-shell-scripts.html

source ./logger.sh

SCRIPT_LOG="./log/demo.log"

SCRIPTENTRY
updateUserDetails(){
    ENTRY
    logDebug "Username: $1, Key: $2"
    logInfo "User details updated for $1"
    EXIT
}

logInfo "Updating user details..."
updateUserDetails "cubicrace" "3445"

rc=2

if [ ! "$rc" = "0" ]
then
    ERROR "Failed to update user details. RC=$rc"
fi
SCRIPTEXIT
