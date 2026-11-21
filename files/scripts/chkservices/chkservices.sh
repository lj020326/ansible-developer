#!/bin/bash
# Script to check services and start when something stops
# hflautert@gmail.com

set -x

host=$(hostname -s)
FILE_PID="/var/run/chkservices.pid"
#CONFIG_FILE="/etc/chkservices/chkservices.conf"
CONFIG_FILE="/opt/pyutils/scripts/chkservices/chkservices.${host}.conf"

# Load conf
# shellcheck source=/dev/null
source "$CONFIG_FILE"

# Log function
LOG() {
    logger -t chkservices[$$] "$1"
}

# Try to recover - start services function
START_SERVICE() {
    local SERVICE=$1
    systemctl start "$SERVICE" >/dev/null 2>&1
    # Some services like httpd could return status error if test just after start
    # So lets sleep a little bit
    sleep 3
    systemctl status "$SERVICE" >/dev/null 2>&1
    rc="$?"
    local MAIL_BODY
    local SUBJECT
    if [ "${rc}" -eq 0 ]; then
        LOG "The service $SERVICE was started successfully."
        MAIL_BODY="The service $SERVICE has stopped, and was started successfully by chkservices. Take a look on $HOSTNAME logs, and try to figure out what happened."
        SUBJECT="Service $SERVICE has restarted on $HOSTNAME"
    else
        LOG "The service $SERVICE is stopped and need mantaince to get start."
        MAIL_BODY="The service $SERVICE is stopped and need maintenance to get started. Access $HOSTNAME and check it out!"
        SUBJECT="Service $SERVICE is stopped on $HOSTNAME"
        #XXX - Develop kill -9, remove pid, something like a powerfull restart
    fi
    echo "$MAIL_BODY" | mail -r "$MAIL_FROM" -s "$SUBJECT" "$MAIL_TO"
}

CHECK_FOR_PID() {
    if [ -e "$FILE_PID" ]; then
        LOG "The Pid File $FILE_PID already exists! See how program was stopped, remove it and start again!"
        exit 1
    fi
}

TEST_SERVICE() {

    for i in ${SERVICES:-}; do

        # If service exists, get status
        #test -e /etc/init.d/$i > /dev/null 2>&1
        # shellcheck disable=SC2065
        test -e "/etc/systemd/system/$i.service" >/dev/null 2>&1
        rc="$?"
        if [ "${rc}" -eq 0 ]; then
            systemctl status "$i" 1>/dev/null 2>/dev/null
            rc="$?"
            # If is not running, try to start
            if [ "${rc}" != 0 ]; then
                LOG "The service $i is stopped, chkservices is going to restart it."
                START_SERVICE "$i"
            fi
        else
            LOG "The declared service $i, was not found."
        fi
    done

    sleep "$INTERVAL"

}

## Main
#
START_CHKSERVICES() {
    LOG "Starting up chkservices."
    while true; do
        TEST_SERVICE
    done
}

CHECK_FOR_PID
START_CHKSERVICES &
echo "$!" >"$FILE_PID"
#
##
