# shellcheck shell=bash

log_profile=".bash_profile:"

# User dependent .bash_profile file
echo "${log_profile} configuring shell env..."

# source the users bashrc if it exists
if [ -f "${HOME}/.bashrc" ]; then
    # shellcheck source=/dev/null
    source "${HOME}/.bashrc"
fi

# Set PATH so it includes user's private bin if it exists
# if [ -d "${HOME}/bin" ] ; then
#   PATH="${HOME}/bin:${PATH}"
# fi

# Set MANPATH so it includes users' private man if it exists
# if [ -d "${HOME}/man" ]; then
#   MANPATH="${HOME}/man:${MANPATH}"
# fi

# Set INFOPATH so it includes users' private info if it exists
# if [ -d "${HOME}/info" ]; then
#   INFOPATH="${HOME}/info:${INFOPATH}"
# fi

# Added by Toolbox App
#export PATH="$PATH:/usr/local/bin"
