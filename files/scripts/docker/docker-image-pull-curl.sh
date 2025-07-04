#!/usr/bin/env bash

VERSION="2025.6.12"

SCRIPT_NAME="$(basename "$0")"

##################
## This script is a modified version of the publicly available script:
## https://raw.githubusercontent.com/moby/moby/master/contrib/download-frozen-image-v2.sh
##
## ref: https://github.com/schnatterer/docker-image-size/blob/master/scripts/docker-image-size-curl.sh
## ref: https://gitlab.com/-/snippets/2483762/raw/main/download-gitlab-frozen-docker-image.sh
##################

set -eo pipefail

if [[ ! -z "${DEBUG}" ]]; then set -x; fi
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

LOG_ERROR=0
LOG_WARN=1
LOG_INFO=2
LOG_TRACE=3
LOG_DEBUG=4

logLevel=${LOG_DEBUG}
#logLevel=${LOG_INFO}

## https://www.pixelstech.net/article/1577768087-Create-temp-file-in-Bash-using-mktemp-and-trap
TMP_DIR=$(mktemp -d -p ~)

## ref: https://stackoverflow.com/questions/10982911/creating-temporary-files-in-bash
IMAGE_TAR_FILE=$(mktemp -u --suffix ".tgz")
IMAGE_TAR_FILE_SAVE=0

## keep track of the last executed command
#trap 'last_command=$current_command; current_command=$BASH_COMMAND' DEBUG
## echo an error message before exiting
#trap 'echo "\"${last_command}\" command filed with exit code $?."' EXIT
#trap 'rm -fr "${TMP_DIR}"' EXIT
#trap '[ "${IMAGE_TAR_FILE_SAVE}" ] || rm -fr "${IMAGE_TAR_FILE}"' EXIT'

function main() {

  checkRequiredCommands curl jq sed awk paste bc

  while getopts "f:hx" opt; do
      case "${opt}" in
          f)
              IMAGE_TAR_FILE="${OPTARG}"
              IMAGE_TAR_FILE_SAVE=1
              ;;
          x) LOG_LEVEL=$LOG_DEBUG ;;
          h) usage 1 ;;
          \?) usage 2 ;;
          :)
              echo "Option -$OPTARG requires an argument." >&2
              usage
              ;;
          *)
              usage
              ;;
      esac
  done
  shift $((OPTIND-1))

  if [ $# -lt 1 ]; then
      echo "required image[:tag][@digest] argument(s) not specified" >&2
      usage
  fi

  while [ $# -gt 0 ]; do
    IMAGE_NAME="${1}"
    url="$(determineUrl "${IMAGE_NAME}")"
    logDebug "url=${url}"

    response=$(queryManifest "${url}")
    logDebug "response[0]=${response}"

    if [[ "${?}" != "0" ]]; then exit 1; fi
  
    response=$(getManifestList "${response}" "${url}")
    logDebug "response[1]=${response}"

    sizes=$(echo ${response} | jq -e '.layers[].size' 2>/dev/null)
    logDebug "sizes=${sizes}"

    if [[ "${?}" = "0" ]]; then
        echo "${1}:" $(createAndPrintSum "${sizes}")
    else
        fail "main(): Response: ${response}"
    fi

    layers=$(echo ${response} | jq -e '.layers' 2>/dev/null)
    logInfo "layers=${layers}"
    downloadLayers "${1}" "${layers}"

#    digests=$(echo ${response} | jq -e '.layers[].digest' 2>/dev/null)
#    logInfo "digests=${digests}"
#    downloadDigests "${1}" "${digests}"
    shift
  done

  echo -n '{' > "${TMP_DIR}/repositories"
  firstImage=1
  for image in "${images[@]}"; do
    imageFile="${image//\//_}" # "/" can't be in filenames :)
    image="${image#library\/}"

    [ "$firstImage" ] || echo -n ',' >> "${TMP_DIR}/repositories"
    firstImage=
    echo -n $'\n\t' >> "${TMP_DIR}/repositories"
    echo -n '"'"$image"'": { '"$(cat "${TMP_DIR}/tags-$imageFile.tmp")"' }' >> "${TMP_DIR}/repositories"
  done
  echo -n $'\n}\n' >> "${TMP_DIR}/repositories"

  rm -f "${TMP_DIR}"/tags-*.tmp

  if [ -z "$doNotGenerateManifestJson" ] && [ "${#manifestJsonEntries[@]}" -gt 0 ]; then
    echo '[]' | jq --raw-output ".$(for entry in "${manifestJsonEntries[@]}"; do echo " + [ $entry ]"; done)" > "${TMP_DIR}/manifest.json"
  else
    rm -f "${TMP_DIR}/manifest.json"
  fi

  #echo "Download of images into '${TMP_DIR}' complete."
  #echo "Use something like the following to load the result into a Docker daemon:"
  #echo "  tar -cC '${TMP_DIR}' . | docker load"

  echo "Creating tar file [${IMAGE_TAR_FILE}] for docker load"
  tar -c -C "${TMP_DIR}" -f "${IMAGE_TAR_FILE}" .

  echo "Loading image into docker"
  docker load < "${IMAGE_TAR_FILE}"

}

logError() {
  if [ $logLevel -ge $LOG_ERROR ]; then
  	echo -e "[ERROR]: ${1}"
  fi
}
logWarn() {
  if [ $logLevel -ge $LOG_WARN ]; then
  	echo -e "[WARN]: ${1}"
  fi
}
logInfo() {
  if [ $logLevel -ge $LOG_INFO ]; then
  	echo -e "[INFO]: ${1}"
  fi
}
logTrace() {
  if [ $logLevel -ge $LOG_TRACE ]; then
  	echo -e "[TRACE]: ${1}"
  fi
}
logDebug() {
  if [ $logLevel -ge $LOG_DEBUG ]; then
  	echo -e "[DEBUG]: ${1}"
  fi
}

function checkRequiredCommands() {
    missingCommands=""
    for currentCommand in "$@"
    do
        isInstalled "${currentCommand}" || missingCommands="${missingCommands} ${currentCommand}"
    done

    if [[ ! -z "${missingCommands}" ]]; then
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
  echo "                             Default will create a temporary file for `docker load` and removed after complete."
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
	if grep -qE "^HTTP/[0-9].[0-9] 3" <<< "$curlHeaders"; then
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
      authUrl=$(echo "${response}" | grep -i www-Authenticate \
                | sed 's|.*Bearer realm="\(.*\)"|\1|' | sed 's|",service|?service|' | sed 's|",scope|\&scope|' \
                | tr -d '"' | sed 's| |%20|' |  tr -d '[:space:]' )
      token="$(curl -sSL "${authUrl}" | jq -e --raw-output .token)"
      header_auth="Authorization: Bearer ${token}"
    elif [[ "${httpResponseCode}" == "200" ]]; then
      response=$(echo ${response} | awk 'END{print}')
    else
      fail "queryManifest(): Request failed. Response: ${response}"
      echo "after fail"
    fi
    echo "${header_auth}"
}

# handle 'application/vnd.docker.distribution.manifest.v2+json' manifest
function handle_single_manifest_v2() {
	local manifestJson="$1"
	shift

	local configDigest
	configDigest="$(echo "$manifestJson" | jq --raw-output '.config.digest')"
	local imageId="${configDigest#*:}" # strip off "sha256:"

	local configFile="$imageId.json"
	fetch_blob "$token" "$image" "$configDigest" "${TMP_DIR}/$configFile" -s

	local layersFs
	layersFs="$(echo "$manifestJson" | jq --raw-output --compact-output '.layers[]')"
	local IFS="$newlineIFS"
	local layers
	mapfile -t layers <<< "$layersFs"
	unset IFS

	echo "Downloading '$imageIdentifier' (${#layers[@]} layers)..."
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
		echo '1.0' > "${TMP_DIR}/$layerId/VERSION"

		if [ ! -s "${TMP_DIR}/$layerId/json" ]; then
			local parentJson
			parentJson="$(printf ', parent: "%s"' "$parentId")"
			local addJson
			addJson="$(printf '{ id: "%s"%s }' "$layerId" "${parentId:+$parentJson}")"
			# this starter JSON is taken directly from Docker's own "docker save" output for unimportant layers
			jq "$addJson + ." > "${TMP_DIR}/$layerId/json" <<- 'EOJSON'
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
	jq --raw-output "$imageOldConfig + del(.history, .rootfs)" "${TMP_DIR}/$configFile" > "${TMP_DIR}/$imageId/json"

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

	if type "go" > /dev/null 2>&1; then
		go env GOARCH
		return 0
	fi

	if type "dpkg" > /dev/null 2>&1; then
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

	if type "uname" > /dev/null 2>&1; then
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
        HOST="$(parseHost ${DOCKER_IMAGE})"
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

    IMAGE="$(parseImage ${DOCKER_IMAGE} ${HOST})"
    if [[ ! "${IMAGE}" == *"/"* ]] && [[ ${EFFECTIVE_HOST} == ${DOCKER_HUB_HOST} ]]; then
        EFFECTIVE_IMAGE="library/${IMAGE}"
    fi

    TAG="$(parseTag ${IMAGE} ${DOCKER_IMAGE})"
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
        response=$(curl -sL ${DOCKER_HTTP_CURL_HEADERS} "${url}")
    else
        response=$(curl -sL -H "${header_auth}" ${DOCKER_HTTP_CURL_HEADERS} "${url}")
    fi

    if [[ "${?}" != "0" ]] ||  [[ -z ${response} ]]; then fail "queryManifest(): response empty"; fi
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
      authUrl=$(echo "${response}" | grep -i www-Authenticate \
                | sed 's|.*Bearer realm="\(.*\)"|\1|' | sed 's|",service|?service|' | sed 's|",scope|\&scope|' | tr -d '"' \
                | sed 's| |%20|' |  tr -d '[:space:]' )
      token="$(curl -sSL "${authUrl}" | jq -e --raw-output .token)"
      header_auth="Authorization: Bearer ${token}"
    elif [[ "${httpResponseCode}" == "200" ]]; then
      response=$(echo ${response} | awk 'END{print}')
    else
      fail "queryManifest(): Request failed. Response: ${response}"
      echo "after fail"
    fi
    echo "${header_auth}"
}

function downloadDigests() {
  docker_image="${1}"
  digests="${2}"

  digestBaseUrl="$(determineUrl "${docker_image}" "digest")"
  logDebug "digestBaseUrl=${digestBaseUrl}"

  for digest in ${digests}
  do
#    logDebug "downloadDigests(): digest[0]=${digest}"

    digest="${digest%\"}"
    digest="${digest#\"}"

    logDebug "downloadDigests(): digest=${digest}"

    digestUrl="${digestBaseUrl}/${digest}"
#    printf -v digestUrl "%s/%s" "${digestBaseUrl}" "${digest}"

    logDebug "downloadDigests(): digestUrl=${digestUrl}"

    header_auth=$(fetchDockerApiAuthHeader "${digestUrl}")

    # If trying to simplify this into a variable "-H $header_auth" you enter quoting hell
    if [[ -z "${header_auth}" ]]; then
        response=$(curl -sL --output "${TMP_DIR}/${digest}" "${digestUrl}")
    else
        response=$(curl -sL -H "Accept-Encoding: identity" -H "${header_auth}" --output "${TMP_DIR}/${digest}" "${digestUrl}")
    fi

    if [[ "${?}" != "0" ]]; then fail "downloadDigests(): download failed"; fi
  done

  logInfo "downloadDigests(): all image layers downloaded successfully to ${TMP_DIR}"

}

function downloadLayers() {
  docker_image="${1}"
  layers="${2}"

  digestBaseUrl="$(determineUrl "${docker_image}" "digest")"
  logDebug "digestBaseUrl=${digestBaseUrl}"

  for i in "${!layers[@]}"; do
    layerMeta="${layers[$i]}"

    digest="$(echo "$layerMeta" | jq --raw-output '.digest')"
    # get second level single manifest
    submanifestJson="$(
      curl -fsSL \
        -H "Authorization: Bearer $token" \
        ${DOCKER_HTTP_CURL_HEADERS} \
        "$DOCKER_HUB_HOST/v2/$image/manifests/$digest"
    )"
    handle_single_manifest_v2 "$submanifestJson"
    found=1
  done
  if [ -z "$found" ]; then
    echo >&2 "error: manifest for ${targetArch}${targetVariant:+/${targetVariant}} is not found"
    exit 1
  fi

	echo

	if [ -s "${TMP_DIR}/tags-$imageFile.tmp" ]; then
		echo -n ', ' >> "${TMP_DIR}/tags-$imageFile.tmp"
	else
		images=("${images[@]}" "$image")
	fi
	echo -n '"'"$tag"'": "'"$imageId"'"' >> "${TMP_DIR}/tags-$imageFile.tmp"

}

function parseHost() {
    HOST="$(echo ${1} | sed 's@^\([^/]*\)/.*@\1@')"
    failIfEmpty ${HOST} "Unable to find repo Host in parameter: ${1}"
    echo "${HOST}"
}

function parseImage() {
    HOST="${2-}" # Might be empty
    if [[ ! -z "$HOST" ]]; then HOST="${HOST}/"; fi
    IMAGE=$(echo "${1}" | sed "s|^${HOST}\([^@:]*\):*.*|\1|")
    failIfEmpty ${IMAGE} "Unable to find image name in parameter: ${1}"
    echo ${IMAGE}
}

function parseTag() {
    IMAGE="${1}"
    echo "${2}" | sed "s|.*${IMAGE}[:@]*\(.*\)|\1|"
}

function getManifestList() {
  manifestJson="${1}"
  url="${2}"

  targetArch="$(get_target_arch)"
  targetVariant="$(get_target_variant)"

  mediaType=$(echo ${manifestJson} | jq -er '.mediaType' 2>/dev/null)
  ## ref: https://askubuntu.com/questions/459402/how-to-know-if-the-running-platform-is-ubuntu-or-centos-with-help-of-a-bash-scri
  case "${mediaType}" in
    *"application/vnd.docker.distribution.manifest.list.v2+json"* | *"application/vnd.oci.image.index.v1+json"*)
      newDigest=$(echo ${manifestJson} | jq -er  ".manifests[] | select(.platform.architecture == \"${targetArch}\" and .platform.os == \"${GOOS}\") | .digest")
      if [[ "${?}" = "0" ]]; then
          newUrl="$(echo ${url} | sed 's|\(.*\)/.*$|\1|')/${newDigest}"
          manifestJson=$(queryManifest "${newUrl}")
      else
        fail "getManifestList(): manifestJson: ${manifestJson}"
      fi
      ;;
  esac
  echo "${manifestJson}"
}

function createAndPrintSum() {
    echo $(( ($(echo "${1}" | paste -sd+ | bc) + 500000) / 1000 / 1000)) MB
}

function failIfEmpty() {
    if [[ -z "${1}" ]]; then
        fail "failIfEmpty(): ${2}"
    fi
}

function fail() {
    error "$@"
    error Image pull failed for ${NAME}
    exit 1
}

function error() {
    echo "$@" 1>&2;
}

main "$@"
