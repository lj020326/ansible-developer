#!/usr/bin/env bash

#set -x

VERSION="2025.6.12"

#SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT_DIR="$(dirname "$0")"
SCRIPT_NAME="$(basename "$0")"
SCRIPT_NAME_PREFIX="${SCRIPT_NAME%.*}"

GALAXY_API_KEY="${ANSIBLE_GALAXY_TOKEN}"
GALAXY_BUILD_PATH="./releases"

DEPLOY_GALAXY_COLLECTION=1
INSTALL_COLLECTION_LOCALLY=0
FORCE_BUILD_COLLECTION=0
VERIFY_GALAXY_COLLECTION=1

INSTALL_COLLECTION_PATH=""

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

# string formatters
if [[ -t 1 ]]
then
  tty_escape() { printf "\033[%sm" "$1"; }
else
  tty_escape() { :; }
fi
tty_mkbold() { tty_escape "1;$1"; }
tty_underline="$(tty_escape "4;39")"
tty_blue="$(tty_mkbold 34)"
tty_red="$(tty_mkbold 31)"
tty_orange="$(tty_mkbold 33)"
tty_bold="$(tty_mkbold 39)"
tty_reset="$(tty_escape 0)"

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

function log_error() {
  if [ $LOG_LEVEL -ge $LOG_ERROR ]; then
  	log_message "${LOG_ERROR}" "${1}"
  fi
}

function log_warn() {
  if [ $LOG_LEVEL -ge $LOG_WARN ]; then
  	log_message "${LOG_WARN}" "${1}"
  fi
}

function log_info() {
  if [ $LOG_LEVEL -ge $LOG_INFO ]; then
  	log_message "${LOG_INFO}" "${1}"
  fi
}

function log_trace() {
  if [ $LOG_LEVEL -ge $LOG_TRACE ]; then
  	log_message "${LOG_TRACE}" "${1}"
  fi
}

function log_debug() {
  if [ $LOG_LEVEL -ge $LOG_DEBUG ]; then
  	log_message "${LOG_DEBUG}" "${1}"
  fi
}

function shell_join() {
  local arg
  printf "%s" "$1"
  shift
  for arg in "$@"
  do
    printf " "
    printf "%s" "${arg// /\ }"
  done
}

function chomp() {
  printf "%s" "${1/"$'\n'"/}"
}

function ohai() {
  printf "${tty_blue}==>${tty_bold} %s${tty_reset}\n" "$(shell_join "$@")"
}

function abort() {
  log_error "$@"
  exit 1
}

function warn() {
  log_warn "$@"
#  log_warn "$(chomp "$1")"
#  printf "${tty_red}Warning${tty_reset}: %s\n" "$(chomp "$1")" >&2
}

#function abort() {
#  printf "%s\n" "$@" >&2
#  exit 1
#}

function error() {
  log_error "$@"
#  printf "%s\n" "$@" >&2
##  echo "$@" 1>&2;
}

function fail() {
  error "$@"
  exit 1
}

function log_message() {
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
  local __LOG_MESSAGE="${LOG_PREFIX} ${LOG_MESSAGE}"
#  echo -e "[${PADDED_LOG_LEVEL}]: ==> ${__LOG_MESSAGE}"
  if [ "${LOG_MESSAGE_LEVEL}" -eq $LOG_INFO ]; then
    printf "${tty_blue}[${PADDED_LOG_LEVEL}]: ==> ${LOG_PREFIX}${tty_reset} %s\n" "${LOG_MESSAGE}" >&2
#    printf "${tty_blue}[${PADDED_LOG_LEVEL}]: ==>${tty_reset} %s\n" "${__LOG_MESSAGE}" >&2
#    printf "${tty_blue}[${PADDED_LOG_LEVEL}]: ==>${tty_bold} %s${tty_reset}\n" "${__LOG_MESSAGE}"
  elif [ "${LOG_MESSAGE_LEVEL}" -eq $LOG_WARN ]; then
    printf "${tty_orange}[${PADDED_LOG_LEVEL}]: ==> ${LOG_PREFIX}${tty_bold} %s${tty_reset}\n" "${LOG_MESSAGE}" >&2
#    printf "${tty_orange}[${PADDED_LOG_LEVEL}]: ==>${tty_bold} %s${tty_reset}\n" "${__LOG_MESSAGE}" >&2
#    printf "${tty_red}Warning${tty_reset}: %s\n" "$(chomp "$1")" >&2
  elif [ "${LOG_MESSAGE_LEVEL}" -le $LOG_ERROR ]; then
    printf "${tty_red}[${PADDED_LOG_LEVEL}]: ==> ${LOG_PREFIX}${tty_bold} %s${tty_reset}\n" "${LOG_MESSAGE}" >&2
#    printf "${tty_red}[${PADDED_LOG_LEVEL}]: ==>${tty_bold} %s${tty_reset}\n" "${__LOG_MESSAGE}" >&2
#    printf "${tty_red}Warning${tty_reset}: %s\n" "$(chomp "$1")" >&2
  else
    printf "${tty_bold}[${PADDED_LOG_LEVEL}]: ==> ${LOG_PREFIX}${tty_reset} %s\n" "${LOG_MESSAGE}" >&2
#    printf "[${PADDED_LOG_LEVEL}]: ==> %s\n" "${LOG_PREFIX} ${LOG_MESSAGE}"
  fi
}

function set_log_level() {
  LOG_LEVEL_STR=$1

  ## ref: https://stackoverflow.com/a/13221491
  if [ "${LOGLEVELSTR_TO_LEVEL[${LOG_LEVEL_STR}]+abc}" ]; then
    LOG_LEVEL="${LOGLEVELSTR_TO_LEVEL[${LOG_LEVEL_STR}]}"
  else
    abort "Unknown log level of [${LOG_LEVEL_STR}]"
  fi

}

function execute() {
  log_info "${*}"
  if ! "$@"
  then
    abort "$(printf "Failed during: %s" "$(shell_join "$@")")"
  fi
}

function execute_eval_command() {
  local RUN_COMMAND="${*}"

  log_debug "${RUN_COMMAND}"
  COMMAND_RESULT=$(eval "${RUN_COMMAND}")
#  COMMAND_RESULT=$(eval "${RUN_COMMAND} > /dev/null 2>&1")
  local RETURN_STATUS=$?

  if [[ $RETURN_STATUS -eq 0 ]]; then
    if [[ $COMMAND_RESULT != "" ]]; then
      log_debug "${COMMAND_RESULT}"
    fi
    log_debug "SUCCESS!"
  else
    log_error "ERROR (${RETURN_STATUS})"
#    echo "${COMMAND_RESULT}"
    abort "$(printf "Failed during: %s" "${COMMAND_RESULT}")"
  fi

}

function is_installed() {
  command -v "${1}" >/dev/null 2>&1 || return 1
}

function check_required_commands() {
  missingCommands=""
  for currentCommand in "$@"
  do
    is_installed "${currentCommand}" || missingCommands="${missingCommands} ${currentCommand}"
  done

  if [[ -n "${missingCommands}" ]]; then
    fail "Please install the following commands required by this script:${missingCommands}"
  fi
}

function deploy_ansible_collection() {
  local COLLECTION_PATH="${1-""}"

  cd "$COLLECTION_PATH" || {
    abort "Error: Could not change to collection directory. Exiting."
  }

  COLLECTION_NAMESPACE=$(yq -r '.namespace' galaxy.yml)
  COLLECTION_NAME=$(yq -r '.name' galaxy.yml)
  COLLECTION_VERSION=$(yq -r '.version' galaxy.yml)

  log_info "Ansible collection => ${COLLECTION_NAMESPACE}.${COLLECTION_NAME} version: ${COLLECTION_VERSION}"

  log_debug "Building Ansible collection..."
  BUILD_GALAXY_COLLECTION_CMD_ARRAY=("ansible-galaxy collection build")
  if [ "${FORCE_BUILD_COLLECTION}" -eq 1 ]; then
    BUILD_GALAXY_COLLECTION_CMD_ARRAY+=("--force")
  fi
  BUILD_GALAXY_COLLECTION_CMD_ARRAY+=("--output-path ${GALAXY_BUILD_PATH}")
  execute_eval_command "${BUILD_GALAXY_COLLECTION_CMD_ARRAY[*]}"
  log_debug "Collection built successfully."

  # Find the generated tarball file name.
  # The format is typically <namespace>-<collection_name>-<version>.tar.gz.
#  COLLECTION_TARBALL=$(ls *.tar.gz 2>/dev/null | head -n 1)
#  COLLECTION_TARBALL=$(find . -type f -name ${COLLECTION_NAMESPACE}-${COLLECTION_NAME}-*.tar.gz 2>/dev/null | head -n 1)
  COLLECTION_TARBALL=$(find . -type f -name ${COLLECTION_NAMESPACE}-${COLLECTION_NAME}-${COLLECTION_VERSION}.tar.gz 2>/dev/null)
#  COLLECTION_TARBALL=$(find . -type f -name ${COLLECTION_NAMESPACE}-${COLLECTION_NAME}-${COLLECTION_VERSION}.tar.gz -exec realpath {} \; 2>/dev/null)

  log_info "COLLECTION_TARBALL=${COLLECTION_TARBALL}"

  if [ ! -e "${COLLECTION_TARBALL}" ]; then
    abort "Error: Collection tarball ${COLLECTION_TARBALL} not found. Exiting."
  fi

  if [ "${INSTALL_COLLECTION_LOCALLY}" -eq 1 ]; then
    INSTALL_COLLECTION_CMD_ARRAY=("ansible-galaxy collection install ${COLLECTION_TARBALL}")
    if [ -n "${INSTALL_COLLECTION_PATH}" ]; then
      INSTALL_COLLECTION_CMD_ARRAY+=("-p ${INSTALL_COLLECTION_PATH}")
    fi
    execute_eval_command "${INSTALL_COLLECTION_CMD_ARRAY[*]}"
  fi

  if [ "${DEPLOY_GALAXY_COLLECTION}" -eq 1 ]; then
    log_info "Publishing collection artifact: ${COLLECTION_TARBALL} to Ansible Galaxy..."

    # Publish the collection to Ansible Galaxy.
    # Note: It's more secure to configure your API token as ANSIBLE_GALAXY_TOKEN environment variable or in ansible.cfg.
    # If using environment variable ANSIBLE_GALAXY_TOKEN, no --api-key is needed here.
    DEPLOY_GALAXY_CMD_ARRAY=()
    if [ -n "$GALAXY_API_KEY" ]; then
      DEPLOY_GALAXY_CMD_ARRAY=("ansible-galaxy collection publish $COLLECTION_TARBALL --api-key=$GALAXY_API_KEY")
    else
      # Assuming token is configured in ansible.cfg or environment variable.
      DEPLOY_GALAXY_CMD_ARRAY=("ansible-galaxy collection publish $COLLECTION_TARBALL")
    fi
    execute_eval_command "${DEPLOY_GALAXY_CMD_ARRAY[*]}"

    log_debug "Collection published successfully."

    if [ "${VERIFY_GALAXY_COLLECTION}" -eq 1 ]; then
      ansible-galaxy collection verify "${ANSIBLE_COLLECTION_NAME}" || {
        abort "Error: Verify Galaxy Collection failed. Exiting."
      }
    fi
  fi

  # Optional: Clean up the built tarball after publishing.
  # log_debug "Removing collection tarball..."
  # rm "$COLLECTION_TARBALL"

}


function usage() {
  echo "Usage: ${SCRIPT_NAME} [options] COLLECTION_PATH"
  echo ""
  echo "       COLLECTION_PATH=/path/to/your/ansible_collections/<namespace>/<collection_name>"
  echo "       * Set the path to your collection's root directory (where galaxy.yml is located)."
  echo ""
  echo "  Options:"
  echo "       -L [ERROR|WARN|INFO|TRACE|DEBUG] : run with specified log level (default: '${LOGLEVEL_TO_STR[${LOG_LEVEL}]}')"
  echo "       -b : specify GALAXY_BUILD_PATH where the tar.gz is created (default: ./releases)"
  echo "       -g : specify GALAXY_API_KEY (default sourced from 'ANSIBLE_GALAXY_TOKEN' environment variable if set)"
  echo "       -f : force build to re-create the collection artifact if necessary (default: no)"
  echo "       -l : install collection locally"
  echo "       -p : local collection install path"
  echo "       -s : skip collection deployment (default does not skip)"
  echo "       -v : show script version"
  echo "       -h : help"
  echo ""
  echo "  Examples:"
	echo "       ${SCRIPT_NAME} /home/user123/repos/ansible_collections/test-namespace/test-collection"
  echo "       ${SCRIPT_NAME} -v"
	echo "       ${SCRIPT_NAME} -L DEBUG"
	echo "       ${SCRIPT_NAME} -L DEBUG ~/repos/ansible_collections/test-namespace/test-collection"
	echo "       ${SCRIPT_NAME} -s ~/repos/ansible_collections/demo-ns/utils"
	echo "       ${SCRIPT_NAME} -l -s ~/repos/ansible_collections/demo-ns/utils"
	echo "       ${SCRIPT_NAME} -fls -p ~/.ansible/collections ~/repos/ansible_collections/demo-ns/utils"
	echo "       ${SCRIPT_NAME} -g <galaxy_api_token> ~/repos/ansible_collections/demo-ns/utils"
	[ -z "$1" ] || exit "$1"
}

function main() {

  check_required_commands ansible-galaxy yq

  while getopts "L:g:p:flshv" opt; do
      case "${opt}" in
          L) set_log_level "${OPTARG}" ;;
          g) GALAXY_API_KEY="${OPTARG}" ;;
          p) INSTALL_COLLECTION_PATH="${OPTARG}" ;;
          f) FORCE_BUILD_COLLECTION=1 ;;
          l) INSTALL_COLLECTION_LOCALLY=1 ;;
          s) DEPLOY_GALAXY_COLLECTION=0 ;;
          h) usage 1 ;;
          v) echo "${VERSION}" && exit ;;
          \?) usage 2 ;;
          *) usage ;;
      esac
  done
  shift $((OPTIND-1))

  if [ $# -ne 1 ]; then
    usage 1
  fi
  local COLLECTION_PATH="${1}"

  log_info "COLLECTION_PATH=${COLLECTION_PATH}"
  log_debug "GALAXY_API_KEY=${GALAXY_API_KEY}"

  deploy_ansible_collection "${COLLECTION_PATH}"
}

main "$@"
