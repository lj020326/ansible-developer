#!/usr/bin/env bash

## ref: https://intoli.com/blog/exit-on-errors-in-bash-scripts/
# exit when any command fails
set -e

VERSION="2025.6.12"

SCRIPT_NAME="$(basename "$0")"
SCRIPT_NAME_PREFIX="${SCRIPT_NAME%.*}"

QUIET_MODE=0
ADD_PAYLOAD_MODE=0

FREEDOS_DISK_PATH="/dev/disk2"
FREEDOS_DISK_NAME="FreeDOS"
FREEDOS_IMAGE_PATH="${HOME}/Downloads/software/boot-utils/FD14-LiteUSB/FD14LITE.img"

FREEDOS_DISK_PARTITION1="${FREEDOS_DISK_PATH}s1"
FREEDOS_DISK_NAME1="freedos"
#FREEDOS_DISK_SIZE1="1G"
FREEDOS_DISK_SIZE1="100M"
FREEDOS_DISK_FS_TYPE1=FAT32

FREEDOS_DISK_PARTITION2="${FREEDOS_DISK_PATH}s2"
FREEDOS_DISK_NAME2="data"
#FREEDOS_DISK_FS_TYPE2=ExFAT
FREEDOS_DISK_FS_TYPE2=FAT32

FREEDOS_DISK_FS_TYPE=FAT32
## ref: https://gist.github.com/bmatcuk/fda5ab0fb127e9fd62eaf43e845a51c3?permalink_comment_id=3590154#gistcomment-3590154
#FREEDOS_DISK_FS_TYPE=ExFAT

declare -a FIRMWARE_PAYLOAD
FIRMWARE_PAYLOAD+=("${HOME}/Downloads/software/firmware/supermicro/bios/X10SDVF4.205")

## ref: https://www.pixelstech.net/article/1577768087-Create-temp-file-in-Bash-using-mktemp-and-trap
## ref: https://stackoverflow.com/questions/4632028/how-to-create-a-temporary-directory
TEMP_DIR=$(mktemp -d -t "${SCRIPT_NAME_PREFIX}_XXXXXX" -p "${HOME}/tmp")

# keep track of the last executed command
trap 'last_command=$current_command; current_command=$BASH_COMMAND' DEBUG
# echo an error message before exiting
trap 'echo "\"${last_command}\" command filed with exit code $?."' EXIT
trap 'rm -fr "$TEMP_DIR"' EXIT

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


function add_freedos_payload() {

  ## ref: https://youtu.be/lcNsvIXI2iM?si=YNbwwps4WDFYBFX0
  logInfo "Adding image payload (firmware, etc)"

#  PARTITION2_MOUNT_POINT=$(diskutil info ${FREEDOS_DISK_PARTITION2} | grep 'Mount Point' | cut -d ':' -f 2 | sed 's/^ *//g' | sed 's/ *$//g')
#  logInfo "PARTITION2_MOUNT_POINT => ${FREEDOS_DISK_PARTITION2_MOUNT_POINT}"

  declare -a PAYLOAD_COMMAND_ARRAY

#  PAYLOAD_COMMAND_ARRAY+=("diskutil mount ${FREEDOS_DISK_PARTITION2}")
  ## mount FREEDOS_DISK_PARTITION2 with specified target as TEMP_DIR
  ## ref: https://apple.stackexchange.com/questions/147697/is-there-a-way-to-mount-a-disk-directly-to-a-specific-folder
  PAYLOAD_COMMAND_ARRAY+=("mount -t ${FREEDOS_DISK_FS_TYPE2} ${FREEDOS_DISK_PARTITION2} ${TEMP_DIR}")

  for FIRMWARE_PAYLOAD_ITEM in "${FIRMWARE_PAYLOAD[@]}"; do
    PAYLOAD_COMMAND_ARRAY+=("cp -pr ${FIRMWARE_PAYLOAD_ITEM} ${TEMP_DIR}")
    logDebug "${PAYLOAD_CMD}"
  done

  for PAYLOAD_COMMAND in "${PAYLOAD_COMMAND_ARRAY[@]}"; do

    logInfo "PAYLOAD_COMMAND => ${PAYLOAD_COMMAND}"
    if [ $QUIET_MODE -eq 1 ]; then
      eval "${PAYLOAD_COMMAND} > /dev/null 2>&1"
    else
      eval "${PAYLOAD_COMMAND}"
    fi
    local RETURN_STATUS=$?

    if [[ $RETURN_STATUS -eq 0 ]]; then
      if [ $QUIET_MODE -eq 0 ]; then
        logInfo "SUCCESS => [${PAYLOAD_COMMAND}]"
      fi
    else
      fail "FAILED => [${PAYLOAD_COMMAND}] returned [${RETURN_STATUS}]"
    fi
  done

  #UNMOUNT_CMD="umount ${TEMP_DIR}"
  UNMOUNT_CMD="diskutil unmount ${TEMP_DIR}"
  logInfo "${UNMOUNT_CMD}"
  eval "${UNMOUNT_CMD}"
}

function create_freedos_usb() {

  declare -a COMMAND_ARRAY

  ## ref: https://www.scivision.dev/freedos-flash-bios-linux/
  ## ref: https://superuser.com/a/1750028/1252419
  ## ref: https://superuser.com/questions/1388931/how-to-install-freedos-onto-a-usb-flash-drive
  ## ref: https://gist.github.com/bmatcuk/fda5ab0fb127e9fd62eaf43e845a51c3
  COMMAND_ARRAY+=("diskutil eraseDisk ${FREEDOS_DISK_FS_TYPE} ${FREEDOS_DISK_NAME} MBR ${FREEDOS_DISK_PATH}")

  ## ref: https://discussions.apple.com/thread/251607590?answerId=253102865022#253102865022
  ## ref: https://www.savagetaylor.com/2018/05/28/setting-up-your-vintage-classic-68k-macintosh-creating-your-own-boot-able-disk-image/
  ## ref: https://apple.stackexchange.com/questions/445719/how-to-partition-a-hard-drive-in-macos
  ## ref: https://apple.stackexchange.com/questions/10017/how-do-i-format-a-disk-partition-from-the-command-line-on-os-x
  COMMAND_ARRAY+=("diskutil unmountDisk ${FREEDOS_DISK_PATH}")

  if [ $ADD_PAYLOAD_MODE -eq 0 ]; then
    COMMAND_ARRAY+=("dd if=/dev/zero of=${FREEDOS_DISK_PATH} bs=4M count=10")
  #  COMMAND_ARRAY+=("dd if=${FREEDOS_IMAGE_PATH} of=${FREEDOS_DISK_PATH} bs=4M status=progress")

    COMMAND_ARRAY+=("dd if=${FREEDOS_IMAGE_PATH} of=${FREEDOS_DISK_PATH} bs=4M status=progress")
    COMMAND_ARRAY+=("diskutil unmountDisk ${FREEDOS_DISK_PATH}")

  elif [ $ADD_PAYLOAD_MODE -eq 1 ]; then
    declare -a PARTITION_COMMAND
    PARTITION_COMMAND+=("diskutil partitionDisk ${FREEDOS_DISK_PATH} 2 MBR")
    PARTITION_COMMAND+=("${FREEDOS_DISK_FS_TYPE1} ${FREEDOS_DISK_NAME1} ${FREEDOS_DISK_SIZE1}")
    PARTITION_COMMAND+=("${FREEDOS_DISK_FS_TYPE2} ${FREEDOS_DISK_NAME2} R")
    COMMAND_ARRAY+=("${PARTITION_COMMAND[*]}")

    COMMAND_ARRAY+=("dd if=/dev/zero of=${FREEDOS_DISK_PARTITION1} bs=4M count=10")

    ## ref: https://discussions.apple.com/thread/251607590?answerId=253102865022#253102865022
    ## ref: https://www.savagetaylor.com/2018/05/28/setting-up-your-vintage-classic-68k-macintosh-creating-your-own-boot-able-disk-image/
    ## ref: https://apple.stackexchange.com/questions/445719/how-to-partition-a-hard-drive-in-macos
    ## ref: https://apple.stackexchange.com/questions/10017/how-do-i-format-a-disk-partition-from-the-command-line-on-os-x
    COMMAND_ARRAY+=("diskutil unmountDisk ${FREEDOS_DISK_PARTITION1}")

    COMMAND_ARRAY+=("dd if=${FREEDOS_IMAGE_PATH} of=${FREEDOS_DISK_PARTITION1} bs=4M status=progress")
    COMMAND_ARRAY+=("diskutil unmountDisk ${FREEDOS_DISK_PARTITION1}")
  fi

  if [ $QUIET_MODE -eq 0 ]; then
    logInfo "About to run:"
    logInfo "==================================="

    IFS=$'\n'
    echo "${COMMAND_ARRAY[*]}"

    ## https://www.shellhacks.com/yes-no-bash-script-prompt-confirmation/
    read -p "Confirm write image ${FREEDOS_IMAGE_PATH} to ${FREEDOS_DISK_PATH}? " -n 1 -r
    echo    # (optional) move to a new line
    if [[ ! $REPLY =~ ^[Yy]$ ]]
    then
      exit 1
    fi
  fi

  for COMMAND in "${COMMAND_ARRAY[@]}"; do

    logInfo "COMMAND => ${COMMAND}"

    if [ $QUIET_MODE -eq 1 ]; then
      eval "${COMMAND} > /dev/null 2>&1"
    else
      eval "${COMMAND}"
    fi
    local RETURN_STATUS=$?

    if [[ $RETURN_STATUS -eq 0 ]]; then
      if [ $QUIET_MODE -eq 0 ]; then
        logInfo "SUCCESS => [${COMMAND}]"
      fi
    else
      fail "FAILED => [${COMMAND}] returned [${RETURN_STATUS}]"
    fi
  done

  if [ $ADD_PAYLOAD_MODE -eq 1 ]; then
    add_freedos_payload
  fi

}

function usage() {
  echo "Usage: sudo ${SCRIPT_NAME} [options]"
  echo ""
  echo "  Options:"
  echo "       -L [ERROR|WARN|INFO|TRACE|DEBUG] : run with specified log level (default: '${LOGLEVEL_TO_STR[${LOG_LEVEL}]}')"
  echo "       -d [DISK PATH] : disk path to write image *CAREFUL!!* (default: '${FREEDOS_DISK_PATH}')"
  echo "       -n [DISK NAME] : name of disk to write image (default: '${FREEDOS_DISK_NAME}')"
  echo "       -i [IMAGE PATH] : source path of freedos image to write (default: '${FREEDOS_IMAGE_PATH}')"
  echo "       -q : quiet mode - Be careful and certain arguments are correct! (default: off)"
  echo "       -v : show script version"
  echo "       -h : help"
  echo ""
  echo "  Examples:"
	echo "       sudo ${SCRIPT_NAME} "
	echo "       sudo ${SCRIPT_NAME} -d /dev/disk3"
	echo "       sudo ${SCRIPT_NAME} -d /dev/disk3 -n FD14 -i ~/software/boot-utils/freedos/fd14.iso"
	echo "       sudo ${SCRIPT_NAME} -p"
	echo "       sudo ${SCRIPT_NAME} -L DEBUG"
  echo "       sudo ${SCRIPT_NAME} -v"
	[ -z "$1" ] || exit "$1"
}


function main() {

  while getopts "L:d:i:n:pqvh" opt; do
      case "${opt}" in
          L) setLogLevel "${OPTARG}" ;;
          d) FREEDOS_DISK_PATH="${OPTARG}" ;;
          i) FREEDOS_IMAGE_PATH="${OPTARG}" ;;
          n) FREEDOS_DISK_NAME="${OPTARG}" ;;
          p) ADD_PAYLOAD_MODE=1 ;;
          q) QUIET_MODE=1 ;;
          v) echo "${VERSION}" && exit ;;
          h) usage 1 ;;
          \?) usage 2 ;;
          *) usage ;;
      esac
  done
  shift $((OPTIND-1))

  if [[ "$EUID" = 0 ]]; then
    logDebug "(1) set to root"
  else
    logError "****************************"
    logError "** user is not root!"
    logError "**   This script must be run as root or with sudo, see usage below:"
    logError ""
    usage 2
  fi

  create_freedos_usb

}

main "$@"
