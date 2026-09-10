#!/bin/bash

DATE=`date +%Y%m%d%H%M%S`

echo "**********************************"
echo "*** installing bashrc         ****"
echo "**********************************"

# --- Platform Detection ---
PLATFORM_OS=$(uname -s | tr "[:upper:]" "[:lower:]")

INSTALL_ON_LINUX=0
INSTALL_ON_MACOS=0
INSTALL_ON_MSYS=0

case "${PLATFORM_OS}" in
  linux*)
    INSTALL_ON_LINUX=1
    ;;
  darwin*)
    INSTALL_ON_MACOS=1
    ;;
  cygwin* | mingw64* | mingw32* | msys*)
    INSTALL_ON_MSYS=1
    ;;
  *)
    echo "Install script is only supported on macOS, Linux and msys2."
    exit 1
    ;;
esac

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

## expect to be run from any non-project location/directory
PROJECT_DIR=$(cd "${SCRIPT_DIR}" && git rev-parse --show-toplevel)

SCRIPT_BASE_DIR="${PROJECT_DIR}/files/scripts"
ENV_CONFIGS_DIR="${PROJECT_DIR}/files/env/dev"

BASHENV_DIR="${SCRIPT_BASE_DIR}/bashenv"
LOCAL_BIN_DIR="${HOME}/bin"

PRIVATE_DIR="${PROJECT_DIR}/files/private"
PRIVATE_ENV_DIR="${PRIVATE_DIR}/env"

export ANSIBLE_VAULT_PASSWORD_FILE=$HOME/.vault_pass

BACKUP_HOME_DIR="${HOME}/.bash-backups"

echo "==> SCRIPT_DIR=${SCRIPT_DIR}"
echo "==> SCRIPT_BASE_DIR=${SCRIPT_BASE_DIR}"
echo "==> ENV_CONFIGS_DIR=${ENV_CONFIGS_DIR}"
echo "==> BASHENV_DIR=${BASHENV_DIR}"
echo "==> HOME=${HOME}"
echo "==> LOCAL_BIN_DIR=${LOCAL_BIN_DIR}"
echo "==> PROJECT_DIR=${PROJECT_DIR}"
echo "==> PLATFORM_OS=${PLATFORM_OS}"

UPDATE_REPO_CMD="cd ${PROJECT_DIR} && git pull origin main"
eval "${UPDATE_REPO_CMD}"

## rsync can backup and sync
EXCLUDES=(
  "--exclude=.idea"
  "--exclude=.git"
  "--exclude=venv"
  "--exclude=save"
)

RSYNC_UPDATE_OPTIONS=(
  "-rog"
  "--update"
  "${EXCLUDES[@]}"
  "--backup"
  "--backup-dir=$BACKUP_HOME_DIR"
)
RSYNC_OVERWRITE_OPTIONS=(
  "-rog"
  "${EXCLUDES[@]}"
  "--backup"
  "--backup-dir=$BACKUP_HOME_DIR"
)

function execute() {
  echo "Running: ${*}"
  eval "${*}"
  local RETURN_STATUS=$?

  if [[ $RETURN_STATUS -ne 0 ]]; then
    echo "ERROR (${RETURN_STATUS})"
    echo "Failed during: ${*}"
  fi
}

execute "rsync ${RSYNC_OVERWRITE_OPTIONS[*]} ${BASHENV_DIR}/ ${HOME}/"

mkdir -p "${LOCAL_BIN_DIR}"
echo "==> rsync env scripts"
execute "rsync ${RSYNC_UPDATE_OPTIONS[*]} ${SCRIPT_BASE_DIR}/git/*.sh ${LOCAL_BIN_DIR}/"
execute "rsync ${RSYNC_UPDATE_OPTIONS[*]} ${SCRIPT_BASE_DIR}/llm/*.sh ${LOCAL_BIN_DIR}/"
execute "rsync ${RSYNC_UPDATE_OPTIONS[*]} ${SCRIPT_BASE_DIR}/pfsense/*.{sh,py} ${LOCAL_BIN_DIR}/"
execute "rsync ${RSYNC_UPDATE_OPTIONS[*]} ${SCRIPT_BASE_DIR}/python/*.py ${LOCAL_BIN_DIR}/"
execute "rsync ${RSYNC_UPDATE_OPTIONS[*]} ${SCRIPT_BASE_DIR}/ansible/*.sh ${LOCAL_BIN_DIR}/"
execute "rsync ${RSYNC_UPDATE_OPTIONS[*]} ${SCRIPT_BASE_DIR}/utils/*.sh ${LOCAL_BIN_DIR}/"
execute "rsync ${RSYNC_UPDATE_OPTIONS[*]} ${SCRIPT_BASE_DIR}/media/*.{sh,py} ${LOCAL_BIN_DIR}/"
execute "rsync ${RSYNC_UPDATE_OPTIONS[*]} ${SCRIPT_BASE_DIR}/certs/*.sh ${LOCAL_BIN_DIR}/"
execute "rsync ${RSYNC_UPDATE_OPTIONS[*]} ${ENV_CONFIGS_DIR}/flyline/*.sh ${LOCAL_BIN_DIR}/"

# Conditionally sync macOS specific scripts
if [[ ${INSTALL_ON_MACOS} -eq 1 ]]; then
  echo "==> rsync mac_os scripts"
  if [[ -d "${SCRIPT_BASE_DIR}/mac_os" ]]; then
    execute "rsync ${RSYNC_UPDATE_OPTIONS[*]} ${SCRIPT_BASE_DIR}/mac_os/*.sh ${LOCAL_BIN_DIR}/"
  fi
fi

chmod +x "${LOCAL_BIN_DIR}/"*.{sh,py} || true

#echo "==> rsync .continue/config.yaml"
#mkdir -p "${HOME}/.continue"
#execute "rsync ${RSYNC_UPDATE_OPTIONS[*]} ${ENV_CONFIGS_DIR}/continue/config.yaml ${HOME}/.continue/"

if [[ -f "${PRIVATE_ENV_DIR}/sync-ansibledev.sh" ]]; then
  echo "==> sync ${PRIVATE_ENV_DIR} scripts"
  "${PRIVATE_ENV_DIR}/sync-ansibledev.sh"
fi

if [[ -e "${HOME}/.vault_pass" ]]; then
  chmod 600 "${HOME}/.vault_pass"
fi
