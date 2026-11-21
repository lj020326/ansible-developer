#!/usr/bin/env bash

##########
## ref: https://github.com/schnatterer/docker-image-size/blob/master/scripts/docker-image-size-curl.sh
##########

if [[ -n "${DEBUG}" ]]; then set -x; fi
GOARCH=${GOARCH-"amd64"}
GOOS=${GOOS-"linux"}
DOCKER_HUB_HOST=index.docker.io
# shellcheck disable=SC2034
NAME="${1}"
set -o nounset -o pipefail
#Not setting "-o errexit", because script checks errors and returns custom error messages

#### LOGGING RELATED
LOG_ERROR=0
LOG_WARN=1
LOG_FAILED=2
LOG_SUCCESS=3
LOG_INFO=4
LOG_TRACE=5
LOG_DEBUG=6

declare -A LOGLEVEL_TO_STR
LOGLEVEL_TO_STR["${LOG_ERROR}"]="ERROR"
LOGLEVEL_TO_STR["${LOG_WARN}"]="WARN"
LOGLEVEL_TO_STR["${LOG_FAILED}"]="FAILED"
LOGLEVEL_TO_STR["${LOG_SUCCESS}"]="SUCCESS"
LOGLEVEL_TO_STR["${LOG_INFO}"]="INFO"
LOGLEVEL_TO_STR["${LOG_TRACE}"]="TRACE"
LOGLEVEL_TO_STR["${LOG_DEBUG}"]="DEBUG"

# string formatters
# Force color if FORCE_COLOR is set, otherwise auto-detect TTY
if [[ -n "${FORCE_COLOR:-}" ]] || [[ -t 1 ]]; then
    tty_escape() { printf "\033[%sm" "$1"; }
else
    tty_escape() { :; }
fi
tty_mkbold() { tty_escape "1;$1"; }
# shellcheck disable=SC2034
tty_underline="$(tty_escape "4;39")"
tty_dim_grey="$(tty_escape "2;39")"
tty_red="$(tty_mkbold 31)"
tty_green="$(tty_mkbold 32)"
tty_yellow="$(tty_mkbold 33)"
tty_blue="$(tty_mkbold 34)"
# shellcheck disable=SC2034
tty_magenta="$(tty_mkbold 35)"
# shellcheck disable=SC2034
tty_cyan="$(tty_mkbold 36)"
tty_bold="$(tty_mkbold 39)"
tty_reset="$(tty_escape 0)"

function reverse_array() {
    local -n array_source_ref=$1
    local -n reversed_array_ref=$2
    # iterate over the keys of the array_source_ref array
    for key in "${!array_source_ref[@]}"; do
        # get the value associated with the current key
        value="${array_source_ref[$key]}"
        # add the reversed key-value pair to the reversed_array_ref array
        # shellcheck disable=SC2034
        reversed_array_ref["$value"]="$key"
    done
}

declare -A LOGLEVELSTR_TO_LEVEL
reverse_array LOGLEVEL_TO_STR LOGLEVELSTR_TO_LEVEL

#LOG_LEVEL_IDX=${LOG_DEBUG}
LOG_LEVEL_IDX=${LOG_INFO}
LOG_LEVEL_PADDING_LENGTH=7
#LOG_INCLUDE_INVOKER=true
LOG_PAD_LEVEL=true

# --- Logging Functions ---

function _log_message() {
    local log_message_level="${1}"
    local log_message="${2}"
    local log_prefix="${3:-}"

    if ((log_message_level > LOG_LEVEL_IDX)); then
        return 0
    fi

    local log_level_str="${LOGLEVEL_TO_STR[$log_message_level]}"
    [[ -z "$log_level_str" ]] && {
        echo "Unknown level: $log_message_level" >&2
        return 1
    }

    local log_level_display="${log_level_str}"
    if [[ "${LOG_PAD_LEVEL:-false}" = "true" ]] || [[ "${LOG_PAD_LEVEL:-0}" = "1" ]]; then
        printf -v log_level_display "%-${LOG_LEVEL_PADDING_LENGTH}s" "${log_level_str}"
    fi

    local log_context=""
    local _log_tty_color="${tty_reset}"

    if [ -n "${BASH_VERSION:-}" ]; then
        local script_path="${BASH_SOURCE[2]##*/}"

        # Build Call Stack: skip _log_message (0) and wrapper (1)
        local stack_parts=("${FUNCNAME[@]:2}")
        local call_stack=""

        for ((i = ${#stack_parts[@]} - 1; i >= 0; i--)); do
            local func="${stack_parts[i]}"

            # Normalize 'source' to 'main' or keep existing 'main'
            if [[ "$func" == "main" || "$func" == "source" ]]; then
                # Only add 'main' if it's the first thing in our built stack
                if [[ -z "$call_stack" ]]; then
                    call_stack="main"
                fi
            else
                # Add real function names, separated by colons
                [[ -n "$call_stack" ]] && call_stack+=":"
                call_stack+="$func"
            fi
        done

        # If call_stack is empty (called from top-level), just use the script name
        # Otherwise, append the stack with parentheses
        local func_context=""
        if [[ -n "$call_stack" ]]; then
            func_context="${call_stack%:}()"
        fi

        local line_no="${BASH_LINENO[1]}"

        case "${log_message_level}" in
        "$LOG_DEBUG")
            _log_tty_color="${tty_dim_grey}"
            log_context="${func_context}[${line_no}]"
            ;;
        "$LOG_TRACE")
            _log_tty_color="${tty_blue}"
            log_context="${func_context}[${line_no}]"
            ;;
        "$LOG_SUCCESS")
            _log_tty_color="${tty_green}"
            log_context="${func_context}"
            ;;
        "$LOG_FAILED")
            _log_tty_color="${tty_red}"
            log_context="${func_context}"
            ;;
        "$LOG_WARN")
            _log_tty_color="${tty_yellow}"
            log_context="${func_context}"
            ;;
        "$LOG_ERROR")
            _log_tty_color="${tty_red}"
            log_context="${func_context}[${line_no}]"
            ;;
        *)
            _log_tty_color="${tty_reset}"
            log_context="${func_context}"
            ;;
        esac
    else
        log_context="$(basename "$0")"
    fi

    [[ "${LOG_INCLUDE_INVOKER:-false}" = "true" ]] || [[ "${LOG_INCLUDE_INVOKER:-0}" = "1" ]] && log_context="${script_path}=>${log_context}"
    [[ -n "${log_prefix}" ]] && log_context="${log_prefix}::${log_context}"

    # Standardized Output
    #    printf "${_log_tty_color}%s [%s] %s:${tty_reset} %s\n" "$(date '+%Y-%m-%d %H:%M:%S')" "$log_message_level" "$log_context" "$log_message"
    printf "[%s] ${_log_tty_color}%s %s${tty_reset}\n" "$log_level_display" "$log_context" "$log_message"
}

# Wrapper Functions with Prefix Support
log() { _log_message "${LOG_INFO}" "$1" "${2:-}"; }
log_debug() { _log_message "${LOG_DEBUG}" "$1" "${2:-}"; }
log_trace() { _log_message "${LOG_TRACE}" "$1" "${2:-}"; }
log_info() { _log_message "${LOG_INFO}" "$1" "${2:-}"; }
log_success() { _log_message "${LOG_SUCCESS}" "$1" "${2:-}"; }
log_failed() { _log_message "${LOG_FAILED}" "$1" "${2:-}"; }
log_warn() { _log_message "${LOG_WARN}" "$1" "${2:-}"; }
log_error() { _log_message "${LOG_ERROR}" "$1" "${2:-}"; }

function ohai() { printf "${tty_blue}==>${tty_bold} %s${tty_reset}\n" "$*"; }
function abort() {
    log_error "$1"
    exit 1
}
function warn() { log_warn "$1"; }
function error() { log_error "$1"; }
function fail() {
    error "$1"
    exit 1
}

function set_log_level() {
    local level_idx="${LOGLEVELSTR_TO_LEVEL[${1^^}]}" # ^^ makes it case-insensitive
    if [[ -n "$level_idx" ]]; then
        LOG_LEVEL_IDX="$level_idx"
    else
        abort "Unknown log level: [$1]"
    fi
}

# --- Core Logic Functions ---

function checkArgs() {

    if [[ $# != 1 ]]; then
        echo "Usage: $(basename "$0") NAME[:TAG|@DIGEST]"
        exit 1
    fi
}

function checkRequiredCommands() {
    missingCommands=""
    for currentCommand in "$@"; do
        isInstalled "${currentCommand}" || missingCommands="${missingCommands} ${currentCommand}"
    done

    if [[ -n "${missingCommands}" ]]; then
        fail "Please install the following commands required by this script:${missingCommands}"
    fi
}

function isInstalled() {
    command -v "${1}" >/dev/null 2>&1 || return 1
}

function determineUrl() {

    HOST=""
    EFFECTIVE_HOST=${HOST}

    if [[ ! "${1}" == *"/"* ]]; then
        EFFECTIVE_HOST=${DOCKER_HUB_HOST}
    else
        HOST="$(parseHost "${1}")"
        if [[ "${HOST}" == "docker.io" ]]; then
            EFFECTIVE_HOST=${DOCKER_HUB_HOST}
        else
            if [[ ! "${HOST}" == *"."* ]]; then
                EFFECTIVE_HOST=${DOCKER_HUB_HOST}
                # First part was no host
                HOST=""
            fi
        fi
    fi

    IMAGE="$(parseImage "${1}" "${HOST}")"
    if [[ ! "${IMAGE}" == *"/"* ]] && [[ "${EFFECTIVE_HOST}" == "${DOCKER_HUB_HOST}" ]]; then
        EFFECTIVE_IMAGE="library/${IMAGE}"
    fi

    TAG="$(parseTag "${IMAGE}" "${1}")"
    if [[ -z "${TAG}" ]]; then
        TAG="latest"
    fi

    echo "https://${EFFECTIVE_HOST:-$HOST}/v2/${EFFECTIVE_IMAGE:-$IMAGE}/manifests/${TAG}"
}

function queryManifest() {
    url="${1}"
    response=$(curl -sLi -H "Accept:application/vnd.docker.distribution.manifest.v2+json" "${url}")
    httpResponseCode=$(echo "${response}" | head -n 1 | cut -d$' ' -f2)
    header=""

    if [[ "${httpResponseCode}" == "401" ]]; then
        # e.g. Www-Authenticate: Bearer realm="https://auth.docker.io/token",service="registry.docker.io",scope="repository:library/debian:pull"
        # to: https://auth.docker.io/token?service=registry.docker.io&scope=repository:library/debian:pull
        # e.g. www-authenticate: Bearer realm="https://r.j3ss.co/auth",service="Docker registry",scope="repository:reg:pull"
        # to https://r.j3ss.co/auth?service=Docker%20registry&scope=repository:reg:pull'
        # URL encode any blanks such as service="Docker registry"
        # Remove all remaining spaces at the end to avoid quoting issues
        # shellcheck disable=SC2001
        authUrl=$(echo "${response}" | grep -i www-Authenticate |
            sed 's|.*Bearer realm="\(.*\)"|\1|' | sed 's|",service|?service|' | sed 's|",scope|\&scope|' | tr -d '"' |
            sed 's| |%20|' | tr -d '[:space:]')
        token="$(curl -sSL "${authUrl}" | jq -e --raw-output .token)"
        header="Authorization: Bearer ${token}"
    elif [[ "${httpResponseCode}" == "200" ]]; then
        response=$(echo "${response}" | awk 'END{print}')
    else
        fail "Request failed. Response: ${response}"
    fi

    # If trying to simplify this into a variable "-H $header" you enter quoting hell
    rc=0
    if [[ -z "${header}" ]]; then
        response=$(curl -sL -H "Accept:application/vnd.docker.distribution.manifest.v2+json" "${url}")
        rc="$?"
    else
        response=$(curl -sL -H "${header}" -H "Accept:application/vnd.docker.distribution.manifest.v2+json" "${url}")
        rc="$?"
    fi

    if [[ "${rc}" -ne 0 ]] || [[ -z ${response} ]]; then fail "response empty"; fi
    echo "${response}"
}

function parseHost() {
    # shellcheck disable=SC2001
    HOST="$(echo "${1}" | sed 's@^\([^/]*\)/.*@\1@')"
    failIfEmpty "${HOST}" "Unable to find repo Host in parameter: ${1}"
    echo "${HOST}"
}

function parseImage() {
    HOST="${2-}" # Might be empty
    if [[ -n "$HOST" ]]; then HOST="${HOST}/"; fi
    # shellcheck disable=SC2001
    IMAGE=$(echo "${1}" | sed "s|^${HOST}\([^@:]*\):*.*|\1|")
    failIfEmpty "${IMAGE}" "Unable to find image name in parameter: ${1}"
    echo "${IMAGE}"
}

function parseTag() {
    IMAGE="${1}"
    # shellcheck disable=SC2001
    echo "${2}" | sed "s|.*${IMAGE}[:@]*\(.*\)|\1|"
}

function checkManifestList() {
    response="${1}"
    url="${2}"

    mediaType=$(echo "${response}" | jq -er '.mediaType' 2>/dev/null)
    if [[ "${mediaType}" == "application/vnd.docker.distribution.manifest.list.v2+json" ]]; then
        newDigest=$(echo "${response}" | jq -er ".manifests[] | select(.platform.architecture == \"${GOARCH}\" and .platform.os == \"${GOOS}\") | .digest")
        rc="$?"
        if [[ "${rc}" -eq 0 ]]; then
            newUrl="${url%/*}/${newDigest}"
            response=$(queryManifest "${newUrl}")
        else
            fail "Response: ${response}"
        fi
    fi
    echo "${response}"
}

function createAndPrintSum() {
    echo $((($(echo "${1}" | paste -sd+ | bc) + 500000) / 1000 / 1000)) MB
}

function failIfEmpty() {
    if [[ -z "${1}" ]]; then
        fail "${2}"
    fi
}

function main() {

    checkArgs "$@"
    checkRequiredCommands curl jq sed awk paste bc

    url="$(determineUrl "${1}")"
    log_debug "url=${url}"

    response=$(queryManifest "${url}")
    rc="$?"

    log_debug "response[0]=${response}"

    if [[ "${rc}" -ne 0 ]]; then exit 1; fi

    response=$(checkManifestList "${response}" "${url}")
    log_debug "response[1]=${response}"

    sizes=$(echo "${response}" | jq -e '.layers[].size' 2>/dev/null)
    rc="$?"
    log_debug "sizes=${sizes}"

    if [[ "${rc}" -eq 0 ]]; then
        log_info "${1}:" "$(createAndPrintSum "${sizes}")"
    else
        fail "Response: ${response}"
    fi
}

main "$@"
