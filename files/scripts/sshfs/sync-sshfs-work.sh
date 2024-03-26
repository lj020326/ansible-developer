#!/usr/bin/env bash

USERDIR="${HOME:="/Users/ljohnson"}"

SOURCE_DIR="${USERDIR}/repos/work"
DEST_DIR="${USERDIR}/mnt/work_sshfs_mount"
SSH_ID_FILE="${USERDIR}/.ssh/${SSH_KEY_WORK2}"
SSH_HOST="atrup1s4.${WORK_DOMAIN}"
SSH_SOURCE="${WORK_USER_ID}@${SSH_HOST}:/home/${WORK_USER_ID}/repos/ansible/"

## https://www.pixelstech.net/article/1577768087-Create-temp-file-in-Bash-using-mktemp-and-trap
#TMP_DIR=$(mktemp -d -p ~)
#TMP_DIR=$(/usr/local/bin/gmktemp -d -p ~)
TMP_DIR=$(mktemp -d)
echo "TMP_DIR=${TMP_DIR}"

# keep track of the last executed command
trap 'last_command=$current_command; current_command=$BASH_COMMAND' DEBUG
# echo an error message before exiting
trap 'echo "\"${last_command}\" command filed with exit code $?."' EXIT
trap 'rm -fr "$TMP_DIR"' EXIT
trap 'unmount_share "${DEST_DIR}"' EXIT

## ref: https://stackoverflow.com/questions/71522478/macfuse-giving-mount-macfuse-mount-point-is-itself-on-a-macfuse-volume-ap
## ref: https://github.com/osxfuse/osxfuse/issues/384
remount_share() {

  SSH_ID_FILE=${1}
  SSH_SOURCE=${2}
  SSH_DEST=${3}

  #SSH_DEBUG_OPTS=",debug,sshfs_debug,loglevel=debug"
  SSH_OPTS="kill_on_unmount,reconnect,allow_other,defer_permissions,direct_io,volname=work_sshfs_mount"
  SSH_OPTS+=",IdentityFile=${SSH_ID_FILE}"
  if [[ ! -z ${SSH_DEBUG_OPTS} ]]; then
    SSH_OPTS+=",${SSH_DEBUG_OPTS}"
  fi

  SSHFS_EXEC="/usr/local/bin/sshfs"
  diskutil umount force "${SSH_DEST}"

  mountCmd="${SSHFS_EXEC} -o ${SSH_OPTS} ${SSH_SOURCE} ${SSH_DEST}"
  echo ${mountCmd}
  ${mountCmd}

}

unmount_share() {
  SSH_DEST=${3}
  diskutil umount force "${SSH_DEST}"
}

sync_folder() {
  SOURCE_DIR=${1}
  DEST_DIR=${2}
  TMP_DIR=${3}

  log_prefix="sync_folder():"

  echo "${log_prefix} SOURCE_DIR=${SOURCE_DIR}"
  echo "${log_prefix} DEST_DIR=${DEST_DIR}"
  echo "${log_prefix} TMP_DIR=${TMP_DIR}"

  ## ref: https://stackoverflow.com/questions/53839253/how-can-i-convert-an-array-into-a-comma-separated-string
  declare -a PRIVATE_CONTENT_ARRAY
  PRIVATE_CONTENT_ARRAY+=('**/private/***')
  PRIVATE_CONTENT_ARRAY+=('**/save/***')
  PRIVATE_CONTENT_ARRAY+=('.vault_pass')
#  PRIVATE_CONTENT_ARRAY+=('**/secrets.yml')
#  PRIVATE_CONTENT_ARRAY+=('**/*secrets.yml')
#  PRIVATE_CONTENT_ARRAY+=('***/*vault*')
  PRIVATE_CONTENT_ARRAY+=('integration_config.yml')
  PRIVATE_CONTENT_ARRAY+=('*.log')

  printf -v EXCLUDE_AND_REMOVE '%s,' "${PRIVATE_CONTENT_ARRAY[@]}"
  EXCLUDE_AND_REMOVE="${EXCLUDE_AND_REMOVE%,}"
  echo "${log_prefix} EXCLUDE_AND_REMOVE=${EXCLUDE_AND_REMOVE}"

  declare -a EXCLUDES_ARRAY
#  EXCLUDES_ARRAY+=('.idea')
#  EXCLUDES_ARRAY+=('.vscode')
  EXCLUDES_ARRAY+=('**/.DS_Store')
  EXCLUDES_ARRAY+=('venv')
  EXCLUDES_ARRAY+=('save')
  EXCLUDES_ARRAY+=('output')
  EXCLUDES_ARRAY+=('*.log')

  printf -v EXCLUDES '%s,' "${EXCLUDES_ARRAY[@]}"
  EXCLUDES="${EXCLUDES%,}"
  echo "${log_prefix} EXCLUDES=${EXCLUDES}"

  ## https://serverfault.com/questions/219013/showing-total-progress-in-rsync-is-it-possible
  ## https://www.studytonight.com/linux-guide/how-to-exclude-files-and-directory-using-rsync
  RSYNC_OPTS_GIT_MIRROR=(
      -dar
      --progress
      --links
      --delete-excluded
      --exclude={"${EXCLUDES},${EXCLUDE_AND_REMOVE}"}
  )

  rsync_cmd="rsync --temp-dir=${TMP_DIR} ${RSYNC_OPTS_GIT_MIRROR[@]} ${SOURCE_DIR}/ ${DEST_DIR}/"
  echo "${log_prefix} ${rsync_cmd}"
  eval $rsync_cmd

}


MOUNT_EXISTS=0
if mount | grep ${DEST_DIR} > /dev/null; then
  MOUNT_EXISTS=1
fi

## While the mount may be defined, it may not be active
## Test to see if a subdirectory that would only be available if mounted exists
MOUNT_ACTIVE=0
if [ ${MOUNT_EXISTS} -eq 1 ] && [[ -d ${DEST_DIR}/ansible-test-automation ]]; then
  MOUNT_ACTIVE=1
fi

if [ ${MOUNT_EXISTS} -ne 1 ] && [[ ${MOUNT_ACTIVE} -ne 1 ]]; then
  echo "mount not found for ${DEST_DIR}, remounting..."
  remount_share "${SSH_ID_FILE}" "${SSH_SOURCE}" "${DEST_DIR}"
fi

echo "SOURCE_DIR=${SOURCE_DIR}"
echo "DEST_DIR=${DEST_DIR}"
echo "TMP_DIR=${TMP_DIR}"

PING_RESULT=$(ping -t 5 -c 1 ${SSH_HOST} &> /dev/null)
if [[ ${PING_RESULT} -eq 0 ]]; then
  echo "running sync_folder()"
  sync_folder "${SOURCE_DIR}" "${DEST_DIR}" "${TMP_DIR}"
else
  echo "ping test for HOST=${SSH_HOST} failed with error=${PING_RESULT}, skipping sync..."
fi

unmount_share "${DEST_DIR}"
