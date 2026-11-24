#!/usr/bin/env bash

# shellcheck disable=SC2034
VERSION="2026.11.1"

SCRIPT_NAME="$(basename "$0")"

##################
## This script is a modified version of the publicly available script:
## https://raw.githubusercontent.com/moby/moby/master/contrib/download-frozen-image-v2.sh
##
## ref: https://github.com/schnatterer/docker-image-size/blob/master/scripts/docker-image-size-curl.sh
## ref: https://gitlab.com/-/snippets/2483762/raw/main/download-gitlab-frozen-docker-image.sh
##################

set -eo pipefail

if [[ -n "${DEBUG}" ]]; then set -x; fi
GOARCH=${GOARCH-"amd64"}
GOOS=${GOOS-"linux"}

# hacky workarounds for Bash 3 support (no associative arrays)
images=()
manifestJsonEntries=()
doNotGenerateManifestJson=
# repositories[busybox]='"latest": "...", "ubuntu-14.04": "..."'

# bash v4 on Windows CI requires CRLF separator... and linux doesn't seem to care either way
newlineIFS=$'\n'
major=$(echo "${BASH_VERSION%%[^0.9]}" | cut -d. -f1)
if [ "$major" -ge 4 ]; then
    newlineIFS=$'\r\n'
fi

DOCKER_HUB_HOST=index.docker.io
#DOCKER_HUB_HOST='registry-1.docker.io'
#DOCKER_HUB_HOST="registry.hub.docker.com"
#DOCKER_HUB_HOST="registry.docker.io"
#DOCKER_HUB_HOST="hub.docker.com"

authBase='https://auth.docker.io'
authService='registry.docker.io'

## ref: https://stackoverflow.com/questions/69335984/problems-calling-dockers-v2-name-manifest-tag-api
declare -a DOCKER_HTTP_HEADER_ARRAY
DOCKER_HTTP_HEADER_ARRAY+=("application/vnd.docker.distribution.manifest.v2+json")
DOCKER_HTTP_HEADER_ARRAY+=("application/vnd.docker.distribution.manifest.list.v2+json")
DOCKER_HTTP_HEADER_ARRAY+=("application/vnd.oci.image.manifest.v1+json")
DOCKER_HTTP_HEADER_ARRAY+=("application/vnd.oci.image.index.v1+json")

###################
## we substitute the minus sign in `-H` with the respective octal code (\055H)
## ref: https://superuser.com/questions/1371834/escaping-hyphens-with-printf-in-bash
#DELIM='-H Accept:'
DELIM='\055H Accept:'
printf -v DOCKER_HTTP_CURL_HEADERS "${DELIM}%s " "${DOCKER_HTTP_HEADER_ARRAY[@]}"
DOCKER_HTTP_CURL_HEADERS="${DOCKER_HTTP_CURL_HEADERS% }"

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

function checkRequiredCommands() {
    missingCommands=""
    for currentCommand in "$@"; do
        isInstalled "${currentCommand}" || missingCommands="${missingCommands} ${currentCommand}"
    done

    if [[ -n "${missingCommands}" ]]; then
        fail "checkRequiredCommands(): Please install the following commands required by this script:${missingCommands}"
    fi
}

function isInstalled() {
    command -v "${1}" >/dev/null 2>&1 || return 1
}

usage() {
    echo "Usage: $(basename "${SCRIPT_NAME}") [options] image[:tag][@digest] ..."
    echo ""
    echo "  Options:"
    echo "     -f image_tar_file.tgz : Image tar (tgz) file to be created from downloaded image(s)."
    echo "                             Default will create a temporary file for $(docker load) and removed after complete."
    echo ""
    echo "  Required:"
    echo "     image[:tag][@digest]"
    echo ""
    echo "  Examples:"
    echo "       $(basename "${SCRIPT_NAME}") alpine:latest"
    echo "       $(basename "${SCRIPT_NAME}") -f testimage.tgz build alpine:latest"
    echo "       $(basename "${SCRIPT_NAME}") nginx/nginx-ingress:latest"
    echo "       $(basename "${SCRIPT_NAME}") hello-world:latest"
    echo "       $(basename "${SCRIPT_NAME}") hello-world:latest@sha256:8be990ef2aeb16dbcb9271ddfe2610fa6658d13f6dfb8bc72074cc1ca36966a7"
    [ -z "$1" ] || exit "$1"
}

# https://github.com/moby/moby/issues/33700
function fetch_blob() {
    local token="$1"
    shift
    local image="$1"
    shift
    local digest="$1"
    shift
    local targetFile="$1"
    shift
    local curlArgs=("$@")

    local curlHeaders
    curlHeaders="$(
        curl -S "${curlArgs[@]}" \
            -H "Authorization: Bearer $token" \
            "$DOCKER_HUB_HOST/v2/$image/blobs/$digest" \
            -o "$targetFile" \
            -D-
    )"
    curlHeaders="$(echo "$curlHeaders" | tr -d '\r')"
    if grep -qE "^HTTP/[0-9].[0-9] 3" <<<"$curlHeaders"; then
        rm -f "$targetFile"

        local blobRedirect
        blobRedirect="$(echo "$curlHeaders" | awk -F ': ' 'tolower($1) == "location" { print $2; exit }')"
        if [ -z "$blobRedirect" ]; then
            echo >&2 "error: failed fetching '$image' blob '$digest'"
            echo "$curlHeaders" | head -1 >&2
            return 1
        fi

        curl -fSL "${curlArgs[@]}" \
            "$blobRedirect" \
            -o "$targetFile"
    fi
}

# shellcheck disable=SC2329
function fetchDockerApiAuthHeader() {
    url="${1}"
    response=$(curl -sLi "${DOCKER_HTTP_CURL_HEADERS}" "${url}")
    httpResponseCode=$(echo "${response}" | head -n 1 | cut -d$' ' -f2)
    header_auth=""

    if [[ "${httpResponseCode}" == "401" ]]; then
        # e.g. Www-Authenticate: Bearer realm="https://auth.docker.io/token",service="registry.docker.io",scope="repository:library/debian:pull"
        # to: https://auth.docker.io/token?service=registry.docker.io&scope=repository:library/debian:pull
        # e.g. www-authenticate: Bearer realm="https://r.j3ss.co/auth",service="Docker registry",scope="repository:reg:pull"
        # to https://r.j3ss.co/auth?service=Docker%20registry&scope=repository:reg:pull'
        # URL encode any blanks such as service="Docker registry"
        # Remove all remaining spaces at the end to avoid quoting issues
        # shellcheck disable=SC2001
        authUrl=$(echo "${response}" | grep -i www-Authenticate |
            sed 's|.*Bearer realm="\(.*\)"|\1|' | sed 's|",service|?service|' | sed 's|",scope|\&scope|' |
            tr -d '"' | sed 's| |%20|' | tr -d '[:space:]')
        token="$(curl -sSL "${authUrl}" | jq -e --raw-output .token)"
        header_auth="Authorization: Bearer ${token}"
    elif [[ "${httpResponseCode}" == "200" ]]; then
        response=$(echo "${response}" | awk 'END{print}')
    else
        fail "queryManifest(): Request failed. Response: ${response}"
        echo "after fail"
    fi
    echo "${header_auth}"
}

# handle 'application/vnd.docker.distribution.manifest.v2+json' manifest
function handle_single_manifest_v2() {
    local manifestJson="$1"
    local imageIdentifier="${2:-}"
    local tag="${3:-latest}"
    shift 3

    local configDigest
    configDigest="$(echo "$manifestJson" | jq --raw-output '.config.digest')"
    local imageId="${configDigest#*:}" # strip off "sha256:"

    local configFile="$imageId.json"
    fetch_blob "$token" "$image" "$configDigest" "${TMP_DIR}/$configFile" -s

    local layersFs
    layersFs="$(echo "$manifestJson" | jq --raw-output --compact-output '.layers[]')"
    local IFS="$newlineIFS"
    local layers
    mapfile -t layers <<<"$layersFs"
    unset IFS

    echo "Downloading ${imageIdentifier} (${#layers[@]} layers)..."
    local layerId=
    local layerFiles=()
    for i in "${!layers[@]}"; do
        local layerMeta="${layers[$i]}"

        local layerMediaType
        layerMediaType="$(echo "$layerMeta" | jq --raw-output '.mediaType')"
        local layerDigest
        layerDigest="$(echo "$layerMeta" | jq --raw-output '.digest')"

        # save the previous layer's ID
        local parentId="$layerId"
        # create a new fake layer ID based on this layer's digest and the previous layer's fake ID
        layerId="$(echo "$parentId"$'\n'"$layerDigest" | sha256sum | cut -d' ' -f1)"
        # this accounts for the possibility that an image contains the same layer twice (and thus has a duplicate digest value)

        mkdir -p "${TMP_DIR}/$layerId"
        echo '1.0' >"${TMP_DIR}/$layerId/VERSION"

        if [ ! -s "${TMP_DIR}/$layerId/json" ]; then
            local parentJson
            parentJson="$(printf ', parent: "%s"' "$parentId")"
            local addJson
            addJson="$(printf '{ id: "%s"%s }' "$layerId" "${parentId:+$parentJson}")"
            # this starter JSON is taken directly from Docker's own "docker save" output for unimportant layers
            jq "$addJson + ." >"${TMP_DIR}/$layerId/json" <<-'EOJSON'
				{
					"created": "0001-01-01T00:00:00Z",
					"container_config": {
						"Hostname": "",
						"Domainname": "",
						"User": "",
						"AttachStdin": false,
						"AttachStdout": false,
						"AttachStderr": false,
						"Tty": false,
						"OpenStdin": false,
						"StdinOnce": false,
						"Env": null,
						"Cmd": null,
						"Image": "",
						"Volumes": null,
						"WorkingDir": "",
						"Entrypoint": null,
						"OnBuild": null,
						"Labels": null
					}
				}
			EOJSON
        fi

        case "$layerMediaType" in
        *"application/vnd.docker.image.rootfs.diff.tar.gzip"* | *"application/vnd.oci.image.layer.v1.tar+gzip"*)
            local layerTar="$layerId/layer.tar"
            layerFiles=("${layerFiles[@]}" "$layerTar")
            # TODO figure out why "-C -" doesn't work here
            # "curl: (33) HTTP server doesn't seem to support byte ranges. Cannot resume."
            # "HTTP/1.1 416 Requested Range Not Satisfiable"
            if [ -f "${TMP_DIR}/$layerTar" ]; then
                # TODO hackpatch for no -C support :'(
                echo "skipping existing ${layerId:0:12}"
                continue
            fi
            local token
            token="$(curl -fsSL "$authBase/token?service=$authService&scope=repository:$image:pull" | jq --raw-output '.token')"
            fetch_blob "$token" "$image" "$layerDigest" "${TMP_DIR}/$layerTar" --progress-bar
            ;;

        *)
            echo >&2 "error: unknown layer mediaType ($imageIdentifier, $layerDigest): '$layerMediaType'"
            exit 1
            ;;
        esac
    done

    # change "$imageId" to be the ID of the last layer we added (needed for old-style "repositories" file which is created later -- specifically for older Docker daemons)
    imageId="$layerId"

    # munge the top layer image manifest to have the appropriate image configuration for older daemons
    local imageOldConfig
    imageOldConfig="$(jq --raw-output --compact-output '{ id: .id } + if .parent then { parent: .parent } else {} end' "${TMP_DIR}/$imageId/json")"
    jq --raw-output "$imageOldConfig + del(.history, .rootfs)" "${TMP_DIR}/$configFile" >"${TMP_DIR}/$imageId/json"

    local manifestJsonEntry
    manifestJsonEntry="$(
        echo '{}' | jq --raw-output '. + {
			Config: "'"$configFile"'",
			RepoTags: ["'"${image#library\/}:$tag"'"],
			Layers: '"$(echo '[]' | jq --raw-output ".$(for layerFile in "${layerFiles[@]}"; do echo " + [ \"$layerFile\" ]"; done)")"'
		}'
    )"
    manifestJsonEntries=("${manifestJsonEntries[@]}" "$manifestJsonEntry")
}

function get_target_arch() {
    if [ -n "${TARGETARCH:-}" ]; then
        echo "${TARGETARCH}"
        return 0
    fi

    if type "go" >/dev/null 2>&1; then
        go env GOARCH
        return 0
    fi

    if type "dpkg" >/dev/null 2>&1; then
        debArch="$(dpkg --print-architecture)"
        case "${debArch}" in
        armel | armhf)
            echo "arm"
            return 0
            ;;
        *64el)
            echo "${debArch%el}le"
            return 0
            ;;
        *)
            echo "${debArch}"
            return 0
            ;;
        esac
    fi

    if type "uname" >/dev/null 2>&1; then
        uArch="$(uname -m)"
        case "${uArch}" in
        x86_64)
            echo amd64
            return 0
            ;;
        arm | armv[0-9]*)
            echo arm
            return 0
            ;;
        aarch64)
            echo arm64
            return 0
            ;;
        mips*)
            echo >&2 "I see you are running on mips but I don't know how to determine endianness yet, so I cannot select a correct arch to fetch."
            echo >&2 "Consider installing \"go\" on the system which I can use to determine the correct arch or specify it explicitly by setting TARGETARCH"
            exit 1
            ;;
        *)
            echo "${uArch}"
            return 0
            ;;
        esac

    fi

    # default value
    echo >&2 "Unable to determine CPU arch, falling back to amd64. You can specify a target arch by setting TARGETARCH"
    echo amd64
}

function get_target_variant() {
    echo "${TARGETVARIANT:-}"
}

function determineUrl() {

    DOCKER_IMAGE="${1}"
    URL_TYPE=${2-"manifest"}
    HOST=""
    EFFECTIVE_HOST=${HOST}

    if [[ ! "${DOCKER_IMAGE}" == *"/"* ]]; then
        EFFECTIVE_HOST=${DOCKER_HUB_HOST}
    else
        HOST="$(parseHost "${DOCKER_IMAGE}")"
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

    IMAGE="$(parseImage "${DOCKER_IMAGE}" "${HOST}")"
    if [[ ! "${IMAGE}" == *"/"* ]] && [[ "${EFFECTIVE_HOST}" == "${DOCKER_HUB_HOST}" ]]; then
        EFFECTIVE_IMAGE="library/${IMAGE}"
    fi

    TAG="$(parseTag "${IMAGE}" "${DOCKER_IMAGE}")"
    if [[ -z "${TAG}" ]]; then
        TAG="latest"
    fi

    URL=""
    if [[ "${URL_TYPE}" == "manifest" ]]; then
        URL="https://${EFFECTIVE_HOST:-$HOST}/v2/${EFFECTIVE_IMAGE:-$IMAGE}/manifests/${TAG}"
    elif [[ "${URL_TYPE}" == "digest" ]]; then
        URL="https://${EFFECTIVE_HOST:-$HOST}/v2/${EFFECTIVE_IMAGE:-$IMAGE}/blobs"
    fi
    echo "${URL}"
}

function queryManifest() {
    url="${1}"
    header_auth=$(fetchDockerApiAuthHeader "${url}")

    # If trying to simplify this into a variable "-H $header_auth" you enter quoting hell
    if [[ -z "${header_auth}" ]]; then
        # shellcheck disable=SC2086
        response=$(curl -sL ${DOCKER_HTTP_CURL_HEADERS} "${url}")
        rc="$?"
    else
        # shellcheck disable=SC2086
        response=$(curl -sL -H "${header_auth}" ${DOCKER_HTTP_CURL_HEADERS} "${url}")
        rc="$?"
    fi

    if [[ "${rc}" -ne 0 ]] || [[ -z ${response} ]]; then fail "queryManifest(): response empty"; fi
    echo "${response}"
}

function fetchDockerApiAuthHeader() {
    url="${1}"
    response=$(curl -sLi "${DOCKER_HTTP_CURL_HEADERS}" "${url}")
    httpResponseCode=$(echo "${response}" | head -n 1 | cut -d$' ' -f2)
    header_auth=""

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
        header_auth="Authorization: Bearer ${token}"
    elif [[ "${httpResponseCode}" == "200" ]]; then
        response=$(echo "${response}" | awk 'END{print}')
    else
        fail "queryManifest(): Request failed. Response: ${response}"
    fi
    echo "${header_auth}"
}

function downloadDigests() {
    docker_image="${1}"
    digests="${2}"

    digestBaseUrl="$(determineUrl "${docker_image}" "digest")"
    log_debug "digestBaseUrl=${digestBaseUrl}"

    for digest in ${digests}; do
        #    log_debug "downloadDigests(): digest[0]=${digest}"

        digest="${digest%\"}"
        digest="${digest#\"}"

        log_debug "downloadDigests(): digest=${digest}"

        digestUrl="${digestBaseUrl}/${digest}"
        #    printf -v digestUrl "%s/%s" "${digestBaseUrl}" "${digest}"

        log_debug "downloadDigests(): digestUrl=${digestUrl}"

        header_auth=$(fetchDockerApiAuthHeader "${digestUrl}")
        rc=0
        # If trying to simplify this into a variable "-H $header_auth" you enter quoting hell
        if [[ -z "${header_auth}" ]]; then
            response=$(curl -sL --output "${TMP_DIR}/${digest}" "${digestUrl}")
            rc="$?"
        else
            response=$(curl -sL -H "Accept-Encoding: identity" -H "${header_auth}" --output "${TMP_DIR}/${digest}" "${digestUrl}")
            rc="$?"
        fi

        if [[ "${rc}" -ne 0 ]]; then fail "downloadDigests(): download failed"; fi
    done

    log_info "downloadDigests(): all image layers downloaded successfully to ${TMP_DIR}"

}

function downloadLayers() {
    local docker_image="${1}"
    local imageIdentifier="${2}"
    local tag="${3}"
    shift 3
    local layers=("${@}")

    digestBaseUrl="$(determineUrl "${docker_image}" "digest")"
    log_debug "digestBaseUrl=${digestBaseUrl}"

    for i in "${!layers[@]}"; do
        local layerMeta="${layers[$i]}"

        local digest
        digest="$(echo "$layerMeta" | jq --raw-output '.digest')"
        # get second level single manifest
        local submanifestJson
        # shellcheck disable=SC2086
        submanifestJson="$(
            curl -fsSL \
                -H "Authorization: Bearer $token" \
                ${DOCKER_HTTP_CURL_HEADERS} \
                "$DOCKER_HUB_HOST/v2/$image/manifests/$digest"
        )"
        handle_single_manifest_v2 "$submanifestJson" "$imageIdentifier" "$tag"
        found=1
    done
    if [ -z "$found" ]; then
        echo >&2 "error: manifest for ${targetArch}${targetVariant:+/${targetVariant}} is not found"
        exit 1
    fi

    echo

    if [ -s "${TMP_DIR}/tags-$imageFile.tmp" ]; then
        echo -n ', ' >>"${TMP_DIR}/tags-$imageFile.tmp"
    else
        images=("${images[@]}" "$image")
    fi
    echo -n '"'"$tag"'": "'"$imageId"'"' >>"${TMP_DIR}/tags-$imageFile.tmp"

}

function parseHost() {
    local ref="${1}"
    local host

    # Strip everything from the first '/' onward
    host="${ref%%/*}"
    failIfEmpty "${host}" "Unable to find repo Host in parameter: ${ref}"
    echo "${host}"
}

function parseImage() {
    local ref="${1}"
    local host="${2:-}" # Might be empty
    local image

    if [[ -n "${host}" ]]; then
        image="${ref#"${host}"/}"
    else
        image="${ref}"
    fi

    # Strip tag (:...) or digest (@...) if present
    image="${image%%[:@]*}"

    failIfEmpty "${image}" "Unable to find image name in parameter: ${ref}"
    echo "${image}"
}

function parseTag() {
    local image="${1}"
    local ref="${2}"
    local remainder

    # Remove everything up to and including the image name
    remainder="${ref#*"${image}"}"

    # Strip leading ':' or '@' (returns full ref if image wasn't matched)
    echo "${remainder#[:@]}"
}

function getManifestList() {
    manifestJson="${1}"
    url="${2}"

    targetArch="$(get_target_arch)"
    targetVariant="$(get_target_variant)"

    mediaType=$(echo "${manifestJson}" | jq -er '.mediaType' 2>/dev/null)
    ## ref: https://askubuntu.com/questions/459402/how-to-know-if-the-running-platform-is-ubuntu-or-centos-with-help-of-a-bash-scri
    case "${mediaType}" in
    *"application/vnd.docker.distribution.manifest.list.v2+json"* | *"application/vnd.oci.image.index.v1+json"*)
        newDigest=$(echo "${manifestJson}" | jq -er ".manifests[] | select(.platform.architecture == \"${targetArch}\" and .platform.os == \"${GOOS}\") | .digest")
        rc="$?"
        if [[ "${rc}" -eq 0 ]]; then
            newUrl="${url%/*}/${newDigest}"
            manifestJson=$(queryManifest "${newUrl}")
        else
            fail "getManifestList(): manifestJson: ${manifestJson}"
        fi
        ;;
    esac
    echo "${manifestJson}"
}

function createAndPrintSum() {
    echo $((($(echo "${1}" | paste -sd+ | bc) + 500000) / 1000 / 1000)) MB
}

function failIfEmpty() {
    if [[ -z "${1}" ]]; then
        fail "failIfEmpty(): ${2}"
    fi
}

function main() {

    checkRequiredCommands curl jq sed awk paste bc

    while getopts "f:hx" opt; do
        case "${opt}" in
        f)
            IMAGE_TAR_FILE="${OPTARG}"
            # shellcheck disable=SC2034
            IMAGE_TAR_FILE_SAVE=1
            ;;
        x)
            # shellcheck disable=SC2034
            LOG_LEVEL=$LOG_DEBUG ;;
        h) usage 1 ;;
        \?) usage 2 ;;
        :)
            log_error "Option -$OPTARG requires an argument." >&2
            usage
            ;;
        *)
            usage
            ;;
        esac
    done
    shift $((OPTIND - 1))

    if [ $# -lt 1 ]; then
        log_error "required image[:tag][@digest] argument(s) not specified" >&2
        usage
    fi

    while [ $# -gt 0 ]; do
        IMAGE_NAME="${1}"
        url="$(determineUrl "${IMAGE_NAME}")"
        log_debug "url=${url}"

        response=$(queryManifest "${url}")
        rc="$?"
        log_debug "response[0]=${response}"

        if [[ "${rc}" -ne 0 ]]; then exit 1; fi

        response=$(getManifestList "${response}" "${url}")
        log_debug "response[1]=${response}"

        sizes=$(echo "${response}" | jq -e '.layers[].size' 2>/dev/null)
        rc="$?"
        log_debug "sizes=${sizes}"

        if [[ "${rc}" -eq 0 ]]; then
            log_info "${1}: $(createAndPrintSum "${sizes}")"
        else
            fail "main(): Response: ${response}"
        fi

        local imageIdentifier="${1}"
        local parsed_image
        parsed_image="$(parseImage "${imageIdentifier}" "$(parseHost "${imageIdentifier}" 2>/dev/null || true)")"
        local tag
        tag="$(parseTag "${parsed_image}" "${imageIdentifier}")"
        : "${tag:=latest}"

        local layers=()
        mapfile -t layers < <(echo "${response}" | jq -e -c '.layers[]' 2>/dev/null)
        rc="$?"
        if [[ "${rc}" -ne 0 ]]; then
            fail "main(): failed to extract layers from response: ${response}"
        fi
        log_info "layers=${layers[*]}"
        downloadLayers "${1}" "${imageIdentifier}" "${tag}" "${layers[@]}"

        #    digests=$(echo ${response} | jq -e '.layers[].digest' 2>/dev/null)
        #    log_info "digests=${digests}"
        #    downloadDigests "${1}" "${digests}"
        shift
    done

    echo -n '{' >"${TMP_DIR}/repositories"
    firstImage=1
    for image in "${images[@]}"; do
        imageFile="${image//\//_}" # "/" can't be in filenames :)
        image="${image#library\/}"

        [ "$firstImage" ] || echo -n ',' >>"${TMP_DIR}/repositories"
        firstImage=
        echo -n $'\n\t' >>"${TMP_DIR}/repositories"
        echo -n '"'"$image"'": { '"$(cat "${TMP_DIR}/tags-$imageFile.tmp")"' }' >>"${TMP_DIR}/repositories"
    done
    echo -n $'\n}\n' >>"${TMP_DIR}/repositories"

    rm -f "${TMP_DIR}"/tags-*.tmp

    if [ -z "$doNotGenerateManifestJson" ] && [ "${#manifestJsonEntries[@]}" -gt 0 ]; then
        echo '[]' | jq --raw-output ".$(for entry in "${manifestJsonEntries[@]}"; do echo " + [ $entry ]"; done)" >"${TMP_DIR}/manifest.json"
    else
        rm -f "${TMP_DIR}/manifest.json"
    fi

    #echo "Download of images into '${TMP_DIR}' complete."
    #echo "Use something like the following to load the result into a Docker daemon:"
    #echo "  tar -cC '${TMP_DIR}' . | docker load"

    log_info "Creating tar file [${IMAGE_TAR_FILE}] for docker load"
    tar -c -C "${TMP_DIR}" -f "${IMAGE_TAR_FILE}" .

    log_info "Loading image into docker"
    docker load <"${IMAGE_TAR_FILE}"

}

main "$@"
