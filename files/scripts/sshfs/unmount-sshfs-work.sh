#!/usr/bin/env bash

#SSH_DEST="/Volumes/alsac-sshfs"
SSH_DEST="${HOME}/mnt/alsac_sshfs_mount"

diskutil umount force "${SSH_DEST}"
