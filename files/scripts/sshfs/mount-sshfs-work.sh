#!/usr/bin/env bash

DEST_DIR="${HOME}/mnt/work_sshfs_mount"
SSH_ID_FILE="${HOME}/.ssh/work-ljohnson.id_rsa"
SSH_SOURCE="${WORK_USER_ID}@atrup1s4.${WORK_DOMAIN}:/home/${WORK_USER_ID}/repos/ansible/"

## ref: https://stackoverflow.com/questions/71522478/macfuse-giving-mount-macfuse-mount-point-is-itself-on-a-macfuse-volume-ap
## ref: https://github.com/osxfuse/osxfuse/issues/384
mount_share() {

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
  mountCmd="${SSHFS_EXEC} -o ${SSH_OPTS} ${SSH_SOURCE} ${SSH_DEST}"
  echo ${mountCmd}
  ${mountCmd}

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

if [ ${MOUNT_EXISTS} -ne 1 ] || [[ ${MOUNT_ACTIVE} -ne 1 ]]; then
  echo "already mounted ${SSH_DEST}"
  mount_share "${SSH_ID_FILE}" "${SSH_SOURCE}" "${DEST_DIR}"
fi
