#!/bin/bash

INSTALL_REPO_URL="git@bitbucket.org:lj020326/ansible-developer.git"
INSTALL_REPO_BRANCH="main"

#INSTALL_SCRIPT="https://bitbucket.org/lj020326/ansible-developer/raw/main/files/private/install-ansibledev.sh"
#INSTALL_SCRIPT="https://raw.githubusercontent.com/lj020326/ansible-developer/main/install-ansibledev.sh"
#INSTALL_SCRIPT="files/private/install-ansibledev.sh"
INSTALL_SCRIPT="install-ansibledev.sh"

LOCAL_INSTALL_SCRIPT="${HOME}/bin/${INSTALL_SCRIPT}"

mkdir -p "${HOME}/bin"

## ref: https://stackoverflow.com/questions/160608/do-a-git-export-like-svn-export
#git archive --format=tar --remote="${INSTALL_REPO_URL}" "${INSTALL_REPO_BRANCH}" "${INSTALL_SCRIPT}" | \
#  tar --strip-components 2 -xC "${HOME}/bin/"
git archive --format=tar --remote="${INSTALL_REPO_URL}" "${INSTALL_REPO_BRANCH}" "${INSTALL_SCRIPT}" | \
  tar -xC "${HOME}/bin/"

bash "${LOCAL_INSTALL_SCRIPT}" -r "${INSTALL_REPO_URL}"
#bash -x "${LOCAL_INSTALL_SCRIPT}" -r "${INSTALL_REPO_URL}"
