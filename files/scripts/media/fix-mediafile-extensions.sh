#!/usr/bin/env bash

MEDIA_DIR_DEFAULT="~/data/media/pictures/"
GIF_EXTENSION="gif"
JPEG_EXTENSION="jpg"
PNG_EXTENSION="png"

JPEG_MIMETYPE="image/jpeg"
PNG_MIMETYPE="image/png"
GIF_MIMETYPE="image/gif"

#### LOGGING RELATED
LOG_ERROR=0
LOG_WARN=1
LOG_INFO=2
LOG_TRACE=3
LOG_DEBUG=4

#LOG_LEVEL=${LOG_DEBUG}
LOG_LEVEL=${LOG_INFO}

function logError() {
  if [ $LOG_LEVEL -ge $LOG_ERROR ]; then
#  	echo -e "[ERROR]: ==> ${1}"
  	logMessage "${LOG_ERROR}" "${1}"
  fi
}
function logWarn() {
  if [ $LOG_LEVEL -ge $LOG_WARN ]; then
#  	echo -e "[WARN ]: ==> ${1}"
  	logMessage "${LOG_WARN}" "${1}"
  fi
}
function logInfo() {
  if [ $LOG_LEVEL -ge $LOG_INFO ]; then
#  	echo -e "[INFO ]: ==> ${1}"
  	logMessage "${LOG_INFO}" "${1}"
  fi
}
function logTrace() {
  if [ $LOG_LEVEL -ge $LOG_TRACE ]; then
#  	echo -e "[TRACE]: ==> ${1}"
  	logMessage "${LOG_TRACE}" "${1}"
  fi
}
function logDebug() {
  if [ $LOG_LEVEL -ge $LOG_DEBUG ]; then
#  	echo -e "[DEBUG]: ==> ${1}"
  	logMessage "${LOG_DEBUG}" "${1}"
  fi
}
function abort() {
  logError "%s\n" "$@"
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
  local CALLING_FUNCTION_STR=$(printf "${SEPARATOR}%s" "${REVERSED_CALL_ARRAY[@]}")
  local CALLING_FUNCTION_STR=${CALLING_FUNCTION_STR:${#SEPARATOR}}

  case "${LOG_MESSAGE_LEVEL}" in
    $LOG_ERROR*)
      LOG_LEVEL_STR="ERROR"
      ;;
    $LOG_WARN*)
      LOG_LEVEL_STR="WARN"
      ;;
    $LOG_INFO*)
      LOG_LEVEL_STR="INFO"
      ;;
    $LOG_TRACE*)
      LOG_LEVEL_STR="TRACE"
      ;;
    $LOG_DEBUG*)
      LOG_LEVEL_STR="DEBUG"
      ;;
    *)
      abort "Unknown LOG_MESSAGE_LEVEL of [${LOG_MESSAGE_LEVEL}] specified"
  esac

  local LOG_LEVEL_PADDING_LENGTH=5
  local PADDED_LOG_LEVEL=$(printf "%-${LOG_LEVEL_PADDING_LENGTH}s" "${LOG_LEVEL_STR}")

  local LOG_PREFIX="${CALLING_FUNCTION_STR}():"
  echo -e "[${PADDED_LOG_LEVEL}]: ==> ${LOG_PREFIX} ${LOG_MESSAGE}"
}

function setLogLevel() {
  LOG_LEVEL_STR=$1

  case "${LOG_LEVEL_STR}" in
    ERROR*)
      LOG_LEVEL=$LOG_ERROR
      ;;
    WARN*)
      LOG_LEVEL=$LOG_WARN
      ;;
    INFO*)
      LOG_LEVEL=$LOG_INFO
      ;;
    TRACE*)
      LOG_LEVEL=$LOG_TRACE
      ;;
    DEBUG*)
      LOG_LEVEL=$LOG_DEBUG
      DISPLAY_TEST_RESULTS=1
      ;;
    *)
      abort "Unknown LOG_LEVEL_STR of [${LOG_LEVEL_STR}] specified"
  esac

}

function rename_file_extension() {
  MEDIA_DIR="${1}"
  FROM_EXTENSION="${2}"
  TO_EXTENSION="${3}"
  TO_MIMETYPE="unknown"

  case "${TO_EXTENSION}" in
    ${JPEG_EXTENSION}*) TO_MIMETYPE="${JPEG_MIMETYPE}" ;;
    ${PNG_EXTENSION}*) TO_MIMETYPE="${PNG_MIMETYPE}" ;;
    ${GIF_EXTENSION}*) TO_MIMETYPE="${GIF_MIMETYPE}" ;;
    *) abort "Unknown TO_EXTENSION of [${TO_EXTENSION}] specified" ;;
  esac

  logInfo "Repair incorrect ${FROM_EXTENSION} media file extensions for media type ${TO_MIMETYPE}"

  logInfo "Renaming ${FROM_EXTENSION} files in ${MEDIA_DIR} with mime type => ${TO_MIMETYPE} to *.${TO_EXTENSION}"
  ## ref: https://unix.stackexchange.com/questions/483871/how-to-find-files-by-file-type
  ## ref: https://stackoverflow.com/questions/39421969/how-can-i-change-the-extension-of-files-of-a-type-using-find-with-bash
  ## ref: https://stackoverflow.com/questions/23356779/how-can-i-store-the-find-command-results-as-an-array-in-bash
#  FILES_WITH_INCORRECT_EXTENSION=$(find "${MEDIA_DIR}" -type f -iname "*.${FROM_EXTENSION}" -exec bash -c '[[ "$( file -bi "$1" )" == *${TO_MIMETYPE}* ]]' bash {} \; -print)
#  FIND_CMD="find ${MEDIA_DIR} -type f -iname *."${FROM_EXTENSION}" -exec bash -c '[[ \$( file -bi \"\$1\" )\" == *"${TO_MIMETYPE}"* ]]' bash {} \; -print"
  FIND_CMD="find ${MEDIA_DIR} -type f -iname \"*.${FROM_EXTENSION}\" -exec bash -c '[[ \"\$( file -bi \"\$1\" )\" == *${TO_MIMETYPE}* ]]' bash {} \; -print0"
  logInfo "${FIND_CMD}"
  readarray -d '' FILES_WITH_INCORRECT_EXTENSION < <(eval "${FIND_CMD}")
  printf -v FILES_WITH_INCORRECT_EXTENSION_STR "%s\n" "${FILES_WITH_INCORRECT_EXTENSION[@]}"
  logInfo "FILES_WITH_INCORRECT_EXTENSION => [${FILES_WITH_INCORRECT_EXTENSION_STR}]"

  for FILE in "${FILES_WITH_INCORRECT_EXTENSION[@]}"; do
    logDebug "FILE=${FILE}"
    ## ref: https://stackoverflow.com/questions/12806987/unix-command-to-escape-spaces
    FILENAME_WITH_ESCAPE=$(printf %q "$FILE")
    MV_CMD="mv -- $FILENAME_WITH_ESCAPE ${FILENAME_WITH_ESCAPE%.*}.${TO_EXTENSION}"
    logInfo "${MV_CMD}"
#    eval "${MV_CMD}"
  done

}


function usage() {
  echo "Usage: ${0} [options] [media_directory]"
  echo ""
  echo "  Options:"
  echo "       -L [ERROR|WARN|INFO|TRACE|DEBUG] : run with specified log level (default INFO)"
  echo "       -v : show script version"
  echo "       -h : help"
  echo ""
  echo "  Examples:"
	echo "       ${0} "
	echo "       ${0} -L DEBUG"
  echo "       ${0} -v"
	echo "       ${0} ~/data/media/pictures/2020/2020-selfies/"
	echo "       ${0} -L DEBUG ~/data/media/pictures/2020/2020-selfies/"
	[ -z "$1" ] || exit "$1"
}

function main() {

  while getopts "L:vh" opt; do
      case "${opt}" in
          L) setLogLevel "${OPTARG}" ;;
          v) echo "${VERSION}" && exit ;;
          h) usage 1 ;;
          \?) usage 2 ;;
          *) usage ;;
      esac
  done
  shift $((OPTIND-1))

  MEDIA_DIR=${1:-"${MEDIA_DIR_DEFAULT}"}
  logInfo "MEDIA_DIR => ${MEDIA_DIR}"

  rename_file_extension "${MEDIA_DIR}" "${GIF_EXTENSION}" "${JPEG_EXTENSION}"
  rename_file_extension "${MEDIA_DIR}" "${PNG_EXTENSION}" "${JPEG_EXTENSION}"
  rename_file_extension "${MEDIA_DIR}" "${JPEG_EXTENSION}" "${GIF_EXTENSION}"
  rename_file_extension "${MEDIA_DIR}" "${JPEG_EXTENSION}" "${PNG_EXTENSION}"

  logInfo "Finished repair of media file extensions"

}

main "$@"
