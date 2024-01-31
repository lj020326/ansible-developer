#!/bin/bash

DATE=`date +%Y%m%d%H%M%S`

echo "**********************************"
echo "*** installing bashrc         ****"
echo "**********************************"

## expect to be run at the project root
PROJECT_DIR=$(git rev-parse --show-toplevel)

SCRIPTS_DIR="${PROJECT_DIR}/files/scripts"
BASHENV_DIR="${SCRIPTS_DIR}/bashenv"

SECRETS_DIR="${PROJECT_DIR}/files/private/vault/bashenv"
export ANSIBLE_VAULT_PASSWORD_FILE=$HOME/.vault_pass

BACKUP_HOME_DIR="${HOME}/.bash-backups"
BACKUP_REPO_DIR1="${REPO_DIR1}/save"

echo "SCRIPTS_DIR=${SCRIPTS_DIR}"
echo "BASHENV_DIR=${BASHENV_DIR}"
echo "HOME=${HOME}"
echo "PROJECT_DIR=${PROJECT_DIR}"
echo "SECRETS_DIR=${SECRETS_DIR}"

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
    -arv
    --update
    ${EXCLUDES}
    --backup
    --backup-dir=$BACKUP_HOME_DIR
)

RSYNC_OPTIONS_REPO1=(
    -arv
    --update
    ${EXCLUDES}
    --backup
    --backup-dir=$BACKUP_REPO_DIR1
)

echo "rsync ${RSYNC_OPTIONS_HOME[@]} ${BASHENV_DIR}/ ${HOME}/"
rsync ${RSYNC_OPTIONS_HOME[@]} ${BASHENV_DIR}/ "${HOME}/"

#chmod +x ${SECRETS_DIR}/scripts/*.sh
#chmod +x ${SECRETS_DIR}/git/*.sh

echo "rsync env scripts"
#rsync ${RSYNC_OPTIONS_HOME[@]} ${SECRETS_DIR}/scripts/*.sh ${HOME}/bin/
#rsync ${RSYNC_OPTIONS_HOME[@]} ${SECRETS_DIR}/git/*.sh ${HOME}/bin/
rsync ${RSYNC_OPTIONS_HOME[@]} ${SCRIPTS_DIR}/ansible/*.sh ${HOME}/bin/
rsync ${RSYNC_OPTIONS_HOME[@]} ${SCRIPTS_DIR}/certs/*.sh ${HOME}/bin/
rsync ${RSYNC_OPTIONS_HOME[@]} ${SCRIPT_BASE_DIR}/pfsense/*.sh ${HOME_DIR}/bin/
rsync ${RSYNC_OPTIONS_HOME[@]} ${SCRIPT_BASE_DIR}/pfsense/*.py ${HOME_DIR}/bin/
chmod +x ${HOME}/bin/*.sh || true
#chmod +x ${HOME}/bin/*.py || true

echo "deploying secrets ${SECRETS_DIR}/.bash_secrets"
rsync -arv --update "${SECRETS_DIR}/.bash_secrets" "${HOME}/"
chmod 600 "${HOME}/.bash_secrets"
