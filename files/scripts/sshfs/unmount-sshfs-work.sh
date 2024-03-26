#!/usr/bin/env bash

#SSH_DEST="/Volumes/work-sshfs"
SSH_DEST="${HOME}/mnt/work_sshfs_mount"

diskutil umount force "${SSH_DEST}"
