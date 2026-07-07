#!/usr/bin/env bash

VERSION="2025.5.5"

#SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT_DIR="$( cd "$( dirname "$0" )" && pwd )"
#SCRIPT_NAME="${0%.*}"
SCRIPT_NAME=$(basename "$0")

LOG_FILE="${SCRIPT_NAME}.log"

BASE_DIR=$HOME/repos
PROJECT_CONFIG_FILE=$BASE_DIR/configs/projects.conf

DELIM='|'

cd $BASE_DIR

#mkdir -p $BASE_DIR/config/projects.conf
if [ ! -f $PROJECT_CONFIG_FILE ]; then
    touch $PROJECT_CONFIG_FILE
fi

if [ -f $LOG_FILE ]; then
    rm $LOG_FILE
fi

writeToLog() {
    echo -e "${1}" | tee -a "${LOG_FILE}"
#    echo -e "${1}" >> "${LOG_FILE}"
}

usage () {
  cat <<__EOF__
Usage:
  $SCRIPT_NAME [COMMANDS] [argument ...]

COMMANDS:
  help                            -- Show this help.
  fold                            -- Print information the page having given PAGE_ID.
  unfold                          -- Print html of the page having given PAGE_ID.

__EOF__
}


fold () {
    DIR_LIST=$(grep -r --include 'config' -le "bitbucket" ./ | sed 's/\/\.git\/config//g')

    for REPO_DIR in ${DIR_LIST}
    do
        cd "$BASE_DIR/$REPO_DIR"
        GIT_REMOTE_NAME=$(git remote -v | cut -d' ' -f1 | grep bitbucket | uniq | sed 's/\t/\'${DELIM}'/g')
        PROJECT_DIR="${REPO_DIR}${DELIM}${GIT_REMOTE_NAME}"
        GIT_REMOTE_NAME=$(echo "${PROJECT_DIR}" | cut -f2 -d"${DELIM}")

#        echo "PROJECT_DIR=${PROJECT_DIR}"
        grep -q -F "${PROJECT_DIR}" $PROJECT_CONFIG_FILE || echo "${PROJECT_DIR}" >> $PROJECT_CONFIG_FILE
        echo "git remote remove ${GIT_REMOTE_NAME}"
        git remote remove "${GIT_REMOTE_NAME}"
    done

    echo "*** PROJECT_CONFIG_FILE ${PROJECT_CONFIG_FILE} ***"
    cat "$PROJECT_CONFIG_FILE"
}

unfold () {

    PROJECT_LIST=$(cat $PROJECT_CONFIG_FILE)

    for PROJECT_DIR in ${PROJECT_LIST}
    do
        REPO_DIR=$(echo "$PROJECT_DIR" | cut -f1 -d"${DELIM}")
        GIT_REMOTE_NAME=$(echo "$PROJECT_DIR" | cut -f2 -d"${DELIM}")
        GIT_REMOTE_URL=$(echo "$PROJECT_DIR" | cut -f3 -d"${DELIM}")

        cd "$BASE_DIR/$REPO_DIR"
        echo "git remote add ${GIT_REMOTE_NAME} ${GIT_REMOTE_URL}"
        git remote add ${GIT_REMOTE_NAME} ${GIT_REMOTE_URL}
    done

}


CMD="${1:-}"
shift
case "$CMD" in
  fold)
    fold "$@"
    ;;
  unfold)
    unfold "$@"
    ;;
  --help|help)
    usage
    exit 0
    ;;
  *)
    usage
    exit 1
esac

