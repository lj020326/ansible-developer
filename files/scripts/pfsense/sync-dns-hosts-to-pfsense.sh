#!/usr/bin/env bash

VERSION="2025.5.5"

#SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT_DIR="$( cd "$( dirname "$0" )" && pwd )"
SCRIPT_NAME=$(basename "$0")

INTERNAL_DNS_NAMESERVER=dns.example.int
EXTERNAL_DNS_NAMESERVER=8.8.8.8

HOSTNAME_CONFIG_LIST_DEFAULT=("media.example.int:${INTERNAL_DNS_NAMESERVER}")
HOSTNAME_CONFIG_LIST_DEFAULT+=("apps.example.int:${INTERNAL_DNS_NAMESERVER}")
HOSTNAME_CONFIG_LIST_DEFAULT+=("git.example.int:${INTERNAL_DNS_NAMESERVER}")
HOSTNAME_CONFIG_LIST_DEFAULT+=("jira.example.int:${INTERNAL_DNS_NAMESERVER}")
HOSTNAME_CONFIG_LIST_DEFAULT+=("example.org:${EXTERNAL_DNS_NAMESERVER}")


API_CLIENT_REPO_DIR="~/repos/ansible/api-client"

#TEST_MODE=1
TEST_MODE=0

#### LOGGING RELATED
LOG_ERROR=0
LOG_WARN=1
LOG_INFO=2
LOG_TRACE=3
LOG_DEBUG=4

declare -A LOGLEVEL_TO_STR
LOGLEVEL_TO_STR["${LOG_ERROR}"]="ERROR"
LOGLEVEL_TO_STR["${LOG_WARN}"]="WARN"
LOGLEVEL_TO_STR["${LOG_INFO}"]="INFO"
LOGLEVEL_TO_STR["${LOG_TRACE}"]="TRACE"
LOGLEVEL_TO_STR["${LOG_DEBUG}"]="DEBUG"

function reverse_array() {
  local -n ARRAY_SOURCE_REF=$1
  local -n REVERSED_ARRAY_REF=$2
  # Iterate over the keys of the LOGLEVEL_TO_STR array
  for KEY in "${!ARRAY_SOURCE_REF[@]}"; do
    # Get the value associated with the current key
    VALUE="${ARRAY_SOURCE_REF[$KEY]}"
    # Add the reversed key-value pair to the REVERSED_ARRAY_REF array
    REVERSED_ARRAY_REF[$VALUE]="$KEY"
  done
}

declare -A LOGLEVELSTR_TO_LEVEL
reverse_array LOGLEVEL_TO_STR LOGLEVELSTR_TO_LEVEL

#LOG_LEVEL=${LOG_DEBUG}
LOG_LEVEL=${LOG_INFO}

function logError() {
  if [ $LOG_LEVEL -ge $LOG_ERROR ]; then
  	logMessage "${LOG_ERROR}" "${1}"
  fi
}
function logWarn() {
  if [ $LOG_LEVEL -ge $LOG_WARN ]; then
  	logMessage "${LOG_WARN}" "${1}"
  fi
}
function logInfo() {
  if [ $LOG_LEVEL -ge $LOG_INFO ]; then
  	logMessage "${LOG_INFO}" "${1}"
  fi
}
function logTrace() {
  if [ $LOG_LEVEL -ge $LOG_TRACE ]; then
  	logMessage "${LOG_TRACE}" "${1}"
  fi
}
function logDebug() {
  if [ $LOG_LEVEL -ge $LOG_DEBUG ]; then
  	logMessage "${LOG_DEBUG}" "${1}"
  fi
}
function abort() {
  logError "$@"
  exit 1
}
function fail() {
  logError "$@"
  exit 1
}

function logMessage() {
  local LOG_MESSAGE_LEVEL="${1}"
  local LOG_MESSAGE="${2}"
  ## remove first item from FUNCNAME array
#  local CALLING_FUNCTION_ARRAY=("${FUNCNAME[@]:2}")
  ## Get the length of the array
  local CALLING_FUNCTION_ARRAY_LENGTH=${#FUNCNAME[@]}
  local CALLING_FUNCTION_ARRAY=("${FUNCNAME[@]:2:$((CALLING_FUNCTION_ARRAY_LENGTH - 3))}")
#  echo "CALLING_FUNCTION_ARRAY[@]=${CALLING_FUNCTION_ARRAY[@]}"

  local CALL_ARRAY_LENGTH=${#CALLING_FUNCTION_ARRAY[@]}
  local REVERSED_CALL_ARRAY=()
  for (( i = CALL_ARRAY_LENGTH - 1; i >= 0; i-- )); do
    REVERSED_CALL_ARRAY+=( "${CALLING_FUNCTION_ARRAY[i]}" )
  done
#  echo "REVERSED_CALL_ARRAY[@]=${REVERSED_CALL_ARRAY[@]}"

#  local CALLING_FUNCTION_STR="${CALLING_FUNCTION_ARRAY[*]}"
  ## ref: https://stackoverflow.com/questions/1527049/how-can-i-join-elements-of-a-bash-array-into-a-delimited-string#17841619
  local SEPARATOR=":"
  local CALLING_FUNCTION_STR
  CALLING_FUNCTION_STR=$(printf "${SEPARATOR}%s" "${REVERSED_CALL_ARRAY[@]}")
  CALLING_FUNCTION_STR=${CALLING_FUNCTION_STR:${#SEPARATOR}}

  ## ref: https://stackoverflow.com/a/13221491
  if [ "${LOGLEVEL_TO_STR[${LOG_MESSAGE_LEVEL}]+abc}" ]; then
    LOG_LEVEL_STR="${LOGLEVEL_TO_STR[${LOG_MESSAGE_LEVEL}]}"
  else
    abort "Unknown log level of [${LOG_MESSAGE_LEVEL}]"
  fi

  local LOG_LEVEL_PADDING_LENGTH=5

  local PADDED_LOG_LEVEL
  PADDED_LOG_LEVEL=$(printf "%-${LOG_LEVEL_PADDING_LENGTH}s" "${LOG_LEVEL_STR}")

  local LOG_PREFIX="${CALLING_FUNCTION_STR}():"
  echo -e "[${PADDED_LOG_LEVEL}]: ==> ${LOG_PREFIX} ${LOG_MESSAGE}"
}

function setLogLevel() {
  LOG_LEVEL_STR=$1

  ## ref: https://stackoverflow.com/a/13221491
  if [ "${LOGLEVELSTR_TO_LEVEL[${LOG_LEVEL_STR}]+abc}" ]; then
    LOG_LEVEL="${LOGLEVELSTR_TO_LEVEL[${LOG_LEVEL_STR}]}"
  else
    abort "Unknown log level of [${LOG_LEVEL_STR}]"
  fi

}

function install_api_client() {
  ## ref: https://github.com/MikeWooster/api-client/blob/master/README.md#extended-example
  #pip install loguru api-client

  #######################
  ## must install api-client from local source
  ## since there are issues when installing from pypi
  cd "${API_CLIENT_REPO_DIR}"
  pip install .
}

function sync_dns_to_pfsense() {
  local LOG_PREFIX="sync_dns_to_pfsense():"
  local HOSTNAME_CONFIG_LIST=("$@")

  for HOSTNAME_CONFIG in "${HOSTNAME_CONFIG_LIST[@]}"; do

    IFS=":" read -a HOSTNAME_CONFIG_ARRAY <<< "${HOSTNAME_CONFIG}"
    local HOSTNAME=${HOSTNAME_CONFIG_ARRAY[0]}
    local DNS_NAMESERVER=${HOSTNAME_CONFIG_ARRAY[1]}

    logDebug "${LOG_PREFIX} HOSTNAME=[$HOSTNAME], DNS_NAMESERVER=[$DNS_NAMESERVER]"

    SYNC_DNS_CMD="python ${HOME}/bin/pfsense_api_client.py sync-host-ip-list ${HOSTNAME} ${DNS_NAMESERVER} --apply"

    if [ $TEST_MODE -eq 0 ]; then
      logInfo "${LOG_PREFIX} ${SYNC_DNS_CMD}"
      eval "${SYNC_DNS_CMD}"
    else
      logInfo "${LOG_PREFIX} TEST_MODE=$TEST_MODE: skipping [${SYNC_DNS_CMD}]"
    fi

  done

}

function reset_local_dns() {
  local LOG_PREFIX="reset_local_dns():"

  RESET_DNS_CACHE="sudo dscacheutil -flushcache && sudo killall -HUP mDNSResponder"

  if [ $TEST_MODE -eq 0 ]; then
    logInfo "${LOG_PREFIX} ${RESET_DNS_CACHE}"
    eval "${RESET_DNS_CACHE}"
  else
    logInfo "${LOG_PREFIX} TEST_MODE=$TEST_MODE: skipping [${RESET_DNS_CACHE}]"
  fi

  logInfo "${LOG_PREFIX} Restart eaacloop"

  ## ref: https://serverfault.com/questions/194832/how-to-start-stop-restart-launchd-services-from-the-command-line#194886
  RESTART_EAACLOOP="sudo launchctl kickstart -k system/net.eaacloop.wapptunneld"

  if [ $TEST_MODE -eq 0 ]; then
    logInfo "${LOG_PREFIX} ${RESTART_EAACLOOP}"
    eval "${RESTART_EAACLOOP}"
  else
    logInfo "${LOG_PREFIX} TEST_MODE=$TEST_MODE: skipping [${RESTART_EAACLOOP}]"
  fi

}

function usage() {
  echo "Usage: ${SCRIPT_NAME} [options] [[endpoint:dns_lookup_endpoint] [endpoint:dns_lookup_endpoint]...]"
  echo ""
  echo "  Options:"
  echo "       -L [ERROR|WARN|INFO|TRACE|DEBUG] : run with specified log level (default: '${LOGLEVEL_TO_STR[${LOG_LEVEL}]}')"
  echo "       -v : show script version"
  echo "       -h : help"
  echo ""
  echo "  Examples:"
	echo "       ${SCRIPT_NAME} "
	echo "       ${SCRIPT_NAME} -l DEBUG"
  echo "       ${SCRIPT_NAME} -v"
	echo "       ${SCRIPT_NAME} apps.example.org:8.8.8.8"
	echo "       ${SCRIPT_NAME} apps.example.org:8.8.8.8 jira.example.org:1.1.1.1"
	echo "       ${SCRIPT_NAME} apps.example.int:10.0.0.1 jira.example.int:dns.example.int"
	[ -z "$1" ] || exit "$1"
}

function main() {

  while getopts "L:r:vh" opt; do
      case "${opt}" in
          L) setLogLevel "${OPTARG}" ;;
          v) echo "${VERSION}" && exit ;;
          h) usage 1 ;;
          \?) usage 2 ;;
          *) usage ;;
      esac
  done
  shift $((OPTIND-1))

  HOSTNAME_CONFIG_LIST=("${HOSTNAME_CONFIG_LIST_DEFAULT[@]}")
  if [ $# -gt 0 ]; then
    HOSTNAME_CONFIG_LIST=("$@")
  fi
  logInfo "HOSTNAME_CONFIG_LIST[@]=${HOSTNAME_CONFIG_LIST[@]}"

#  install_api_client

  sync_dns_to_pfsense "${HOSTNAME_CONFIG_LIST[@]}"

  reset_local_dns

}

main "$@"
