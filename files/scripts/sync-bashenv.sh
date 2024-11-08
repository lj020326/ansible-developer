#!/bin/bash

DATE=`date +%Y%m%d%H%M%S`

echo "**********************************"
echo "*** installing bashrc         ****"
echo "**********************************"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
#SCRIPT_DIR="$( cd "$( dirname "$0" )" && pwd )"

## expect to be run from any non-project location/directory
PROJECT_DIR=$(cd "${SCRIPT_DIR}" && git rev-parse --show-toplevel)

SCRIPT_BASE_DIR="${PROJECT_DIR}/files/scripts"

BASHENV_DIR="${SCRIPT_BASE_DIR}/bashenv"

PRIVATE_DIR="${PROJECT_DIR}/files/private"
PRIVATE_ENV_DIR="${PRIVATE_DIR}/env"
VAULT_DIR="${PRIVATE_DIR}/vault"
VAULT_BASHENV_DIR="${VAULT_DIR}/bashenv"

export ANSIBLE_VAULT_PASSWORD_FILE=$HOME/.vault_pass

BACKUP_HOME_DIR="${HOME}/.bash-backups"
BACKUP_REPO_DIR1="${REPO_DIR1}/save"

echo "==> SCRIPT_DIR=${SCRIPT_DIR}"
echo "==> SCRIPT_BASE_DIR=${SCRIPT_BASE_DIR}"
echo "==> BASHENV_DIR=${BASHENV_DIR}"
echo "==> HOME=${HOME}"
echo "==> PROJECT_DIR=${PROJECT_DIR}"
echo "==> VAULT_DIR=${VAULT_DIR}"

UPDATE_REPO_CMD="cd ${PROJECT_DIR} && git pull origin main"
eval "${UPDATE_REPO_CMD}"

## rsync can backup and sync
## ref: https://www.digitalocean.com/community/tutorials/how-to-use-rsync-to-sync-local-and-remote-directories-on-a-vps

## REF: http://stackoverflow.com/questions/4585929/how-to-use-cp-command-to-exclude-a-specific-directory
EXCLUDES="--exclude=.idea"
EXCLUDES+=" --exclude=.git"
EXCLUDES+=" --exclude=venv"
EXCLUDES+=" --exclude=save"

RSYNC_OPTIONS_HOME=(
    -rog
    --update
    ${EXCLUDES}
    --backup
    --backup-dir=$BACKUP_HOME_DIR
)

RSYNC_OPTIONS_REPO1=(
    -rog
    --update
    ${EXCLUDES}
    --backup
    --backup-dir=$BACKUP_REPO_DIR1
)

echo "==> rsync ${RSYNC_OPTIONS_HOME[@]} ${BASHENV_DIR}/ ${HOME}/"
rsync "${RSYNC_OPTIONS_HOME[@]}" "${BASHENV_DIR}/" "${HOME}/"

echo "==> rsync env scripts"
rsync "${RSYNC_OPTIONS_HOME[@]}" "${SCRIPT_BASE_DIR}/git/"*.sh "${HOME}/bin/"
rsync "${RSYNC_OPTIONS_HOME[@]}" "${SCRIPT_BASE_DIR}/pfsense/"*.py "${HOME}/bin/"
rsync "${RSYNC_OPTIONS_HOME[@]}" "${SCRIPT_BASE_DIR}/ansible/"*.sh "${HOME}/bin/"
if [[ -d "${SCRIPT_BASE_DIR}/certs" ]]; then
  rsync "${RSYNC_OPTIONS_HOME[@]}" "${SCRIPT_BASE_DIR}/certs/"*.sh "${HOME}/bin/"
fi
chmod +x "${HOME}/bin/"*.sh || true
chmod +x "${HOME}/bin/"*.py || true

#chmod +x ${PRIVATE_ENV_DIR}/scripts/*.sh
#chmod +x ${PRIVATE_ENV_DIR}/git/*.sh

if [[ -d "${PRIVATE_ENV_DIR}/scripts" ]]; then
  echo "==> rsync private env scripts"
  rsync "${RSYNC_OPTIONS_HOME[@]}" "${PRIVATE_ENV_DIR}/scripts/"*.sh "${HOME}/bin/"
fi
if [[ -d "${PRIVATE_ENV_DIR}/.config" ]]; then
  echo "==> rsync private env configs"
  rsync "${RSYNC_OPTIONS_HOME[@]}" "${PRIVATE_ENV_DIR}/.config/pfsense-api.json" "${HOME}/.config/"
fi
if [[ -d "${PRIVATE_ENV_DIR}/git" ]]; then
  echo "==> rsync private env git configs"
  rsync "${RSYNC_OPTIONS_HOME[@]}" "${PRIVATE_ENV_DIR}/git/"*.sh "${HOME}/bin/"
fi

if [[ -e "${VAULT_BASHENV_DIR}/.bash_secrets" ]]; then
  echo "==> deploying secrets ${VAULT_BASHENV_DIR}/.bash_secrets"
  rsync -rog --update "${VAULT_BASHENV_DIR}/.bash_secrets" "${HOME}/"
  chmod 600 "${HOME}/.bash_secrets"
fi

if [[ -e "${HOME}/.vault_pass" ]]; then
  chmod 600 "${HOME}/.vault_pass"
fi

