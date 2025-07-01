#!/usr/bin/env bash

VERSION="2025.6.12"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLATFORM_OS=$(uname -s | tr "[:upper:]" "[:lower:]")

# Python 3
#PYTHON_VERSION_DEFAULT="3.9.7"
#PYTHON_VERSION_DEFAULT=3.10.9
#PYTHON_VERSION_DEFAULT=3.11.9
PYTHON_VERSION_DEFAULT=3.12.9

## source: https://gist.github.com/simonkuang/14abf618f631ba3f0c7fee7b4ea3f214
#PYTHON3_RH_LIBS=epel-release
#PYTHON3_RH_LIBS="gcc gcc-c++ glibc glibc-devel curl git libffi-devel sqlite-devel bzip2-devel bzip2 readline-devel"
#PYTHON3_RH_LIBS="zlib-devel bzip2-devel openssl-devel ncurses-devel sqlite-devel readline-devel tk-devel gdbm-devel db4-devel libpcap-devel xz-devel"
##PYTHON3_RH_LIBS="zlib-devel bzip2-devel sqlite sqlite-devel openssl-devel"
#PYTHON3_RH_LIBS="python3-devel readline-devel bzip2-devel libffi-devel ncurses-devel sqlite-devel"
PYTHON3_RH_LIBS="readline-devel bzip2-devel libffi-devel ncurses-devel sqlite-devel openssl-devel"
PYTHON3_DEB_LIBS="libreadline-dev libbz2-dev libffi-dev libncurses-dev libsqlite3-dev liblzma-dev libssl-dev"

PYTHON_VERSION=${1-"${PYTHON_VERSION_DEFAULT}"}

PYENV_INSTALL_URL="https://github.com/pyenv/pyenv-installer/raw/master/bin/pyenv-installer"

#### LOGGING RELATED
LOG_ERROR=0
LOG_WARN=1
LOG_INFO=2
LOG_TRACE=3
LOG_DEBUG=4

declare -A LOGLEVEL_TO_STR
LOGLEVEL_TO_STR["${LOG_ERROR}"]="ERROR"
LOGLEVEL_TO_STR["${LOG_WARN}"]="WARN"
LOGLEVEL_TO_STR["${LOG_INFO}"]="INFO"
LOGLEVEL_TO_STR["${LOG_TRACE}"]="TRACE"
LOGLEVEL_TO_STR["${LOG_DEBUG}"]="DEBUG"

# string formatters
if [[ -t 1 ]]
then
  tty_escape() { printf "\033[%sm" "$1"; }
else
  tty_escape() { :; }
fi
tty_mkbold() { tty_escape "1;$1"; }
tty_underline="$(tty_escape "4;39")"
tty_blue="$(tty_mkbold 34)"
tty_red="$(tty_mkbold 31)"
tty_orange="$(tty_mkbold 33)"
tty_bold="$(tty_mkbold 39)"
tty_reset="$(tty_escape 0)"

function reverse_array() {
  local -n ARRAY_SOURCE_REF=$1
  local -n REVERSED_ARRAY_REF=$2
  # Iterate over the keys of the LOGLEVEL_TO_STR array
  for KEY in "${!ARRAY_SOURCE_REF[@]}"; do
    # Get the value associated with the current key
    VALUE="${ARRAY_SOURCE_REF[$KEY]}"
    # Add the reversed key-value pair to the REVERSED_ARRAY_REF array
    REVERSED_ARRAY_REF[$VALUE]="$KEY"
  done
}

declare -A LOGLEVELSTR_TO_LEVEL
reverse_array LOGLEVEL_TO_STR LOGLEVELSTR_TO_LEVEL

#LOG_LEVEL=${LOG_DEBUG}
LOG_LEVEL=${LOG_INFO}

function logError() {
  if [ $LOG_LEVEL -ge $LOG_ERROR ]; then
  	logMessage "${LOG_ERROR}" "${1}"
  fi
}

function logWarn() {
  if [ $LOG_LEVEL -ge $LOG_WARN ]; then
  	logMessage "${LOG_WARN}" "${1}"
  fi
}

function logInfo() {
  if [ $LOG_LEVEL -ge $LOG_INFO ]; then
  	logMessage "${LOG_INFO}" "${1}"
  fi
}

function logTrace() {
  if [ $LOG_LEVEL -ge $LOG_TRACE ]; then
  	logMessage "${LOG_TRACE}" "${1}"
  fi
}

function logDebug() {
  if [ $LOG_LEVEL -ge $LOG_DEBUG ]; then
  	logMessage "${LOG_DEBUG}" "${1}"
  fi
}

function shell_join() {
  local arg
  printf "%s" "$1"
  shift
  for arg in "$@"
  do
    printf " "
    printf "%s" "${arg// /\ }"
  done
}

function chomp() {
  printf "%s" "${1/"$'\n'"/}"
}

function ohai() {
  printf "${tty_blue}==>${tty_bold} %s${tty_reset}\n" "$(shell_join "$@")"
}

function abort() {
  logError "$@"
  exit 1
}

function warn() {
  logWarn "$@"
#  logWarn "$(chomp "$1")"
#  printf "${tty_red}Warning${tty_reset}: %s\n" "$(chomp "$1")" >&2
}

#function abort() {
#  printf "%s\n" "$@" >&2
#  exit 1
#}

function error() {
  logError "$@"
#  printf "%s\n" "$@" >&2
##  echo "$@" 1>&2;
}

function fail() {
  error "$@"
  exit 1
}

function logMessage() {
  local LOG_MESSAGE_LEVEL="${1}"
  local LOG_MESSAGE="${2}"
  ## remove first item from FUNCNAME array
#  local CALLING_FUNCTION_ARRAY=("${FUNCNAME[@]:2}")
  ## Get the length of the array
  local CALLING_FUNCTION_ARRAY_LENGTH=${#FUNCNAME[@]}
  local CALLING_FUNCTION_ARRAY=("${FUNCNAME[@]:2:$((CALLING_FUNCTION_ARRAY_LENGTH - 3))}")
#  echo "CALLING_FUNCTION_ARRAY[@]=${CALLING_FUNCTION_ARRAY[@]}"

  local CALL_ARRAY_LENGTH=${#CALLING_FUNCTION_ARRAY[@]}
  local REVERSED_CALL_ARRAY=()
  for (( i = CALL_ARRAY_LENGTH - 1; i >= 0; i-- )); do
    REVERSED_CALL_ARRAY+=( "${CALLING_FUNCTION_ARRAY[i]}" )
  done
#  echo "REVERSED_CALL_ARRAY[@]=${REVERSED_CALL_ARRAY[@]}"

#  local CALLING_FUNCTION_STR="${CALLING_FUNCTION_ARRAY[*]}"
  ## ref: https://stackoverflow.com/questions/1527049/how-can-i-join-elements-of-a-bash-array-into-a-delimited-string#17841619
  local SEPARATOR=":"
  local CALLING_FUNCTION_STR
  CALLING_FUNCTION_STR=$(printf "${SEPARATOR}%s" "${REVERSED_CALL_ARRAY[@]}")
  CALLING_FUNCTION_STR=${CALLING_FUNCTION_STR:${#SEPARATOR}}

  ## ref: https://stackoverflow.com/a/13221491
  if [ "${LOGLEVEL_TO_STR[${LOG_MESSAGE_LEVEL}]+abc}" ]; then
    LOG_LEVEL_STR="${LOGLEVEL_TO_STR[${LOG_MESSAGE_LEVEL}]}"
  else
    abort "Unknown log level of [${LOG_MESSAGE_LEVEL}]"
  fi

  local LOG_LEVEL_PADDING_LENGTH=5

  local PADDED_LOG_LEVEL
  PADDED_LOG_LEVEL=$(printf "%-${LOG_LEVEL_PADDING_LENGTH}s" "${LOG_LEVEL_STR}")

  local LOG_PREFIX="${CALLING_FUNCTION_STR}():"
  local __LOG_MESSAGE="${LOG_PREFIX} ${LOG_MESSAGE}"
#  echo -e "[${PADDED_LOG_LEVEL}]: ==> ${__LOG_MESSAGE}"
  if [ "${LOG_MESSAGE_LEVEL}" -eq $LOG_INFO ]; then
    printf "${tty_blue}[${PADDED_LOG_LEVEL}]: ==> ${LOG_PREFIX}${tty_reset} %s\n" "${LOG_MESSAGE}" >&2
#    printf "${tty_blue}[${PADDED_LOG_LEVEL}]: ==>${tty_reset} %s\n" "${__LOG_MESSAGE}" >&2
#    printf "${tty_blue}[${PADDED_LOG_LEVEL}]: ==>${tty_bold} %s${tty_reset}\n" "${__LOG_MESSAGE}"
  elif [ "${LOG_MESSAGE_LEVEL}" -eq $LOG_WARN ]; then
    printf "${tty_orange}[${PADDED_LOG_LEVEL}]: ==> ${LOG_PREFIX}${tty_bold} %s${tty_reset}\n" "${LOG_MESSAGE}" >&2
#    printf "${tty_orange}[${PADDED_LOG_LEVEL}]: ==>${tty_bold} %s${tty_reset}\n" "${__LOG_MESSAGE}" >&2
#    printf "${tty_red}Warning${tty_reset}: %s\n" "$(chomp "$1")" >&2
  elif [ "${LOG_MESSAGE_LEVEL}" -le $LOG_ERROR ]; then
    printf "${tty_red}[${PADDED_LOG_LEVEL}]: ==> ${LOG_PREFIX}${tty_bold} %s${tty_reset}\n" "${LOG_MESSAGE}" >&2
#    printf "${tty_red}[${PADDED_LOG_LEVEL}]: ==>${tty_bold} %s${tty_reset}\n" "${__LOG_MESSAGE}" >&2
#    printf "${tty_red}Warning${tty_reset}: %s\n" "$(chomp "$1")" >&2
  else
    printf "${tty_bold}[${PADDED_LOG_LEVEL}]: ==> ${LOG_PREFIX}${tty_reset} %s\n" "${LOG_MESSAGE}" >&2
#    printf "[${PADDED_LOG_LEVEL}]: ==> %s\n" "${LOG_PREFIX} ${LOG_MESSAGE}"
  fi
}

function setLogLevel() {
  LOG_LEVEL_STR=$1

  ## ref: https://stackoverflow.com/a/13221491
  if [ "${LOGLEVELSTR_TO_LEVEL[${LOG_LEVEL_STR}]+abc}" ]; then
    LOG_LEVEL="${LOGLEVELSTR_TO_LEVEL[${LOG_LEVEL_STR}]}"
  else
    abort "Unknown log level of [${LOG_LEVEL_STR}]"
  fi

}

function execute() {
  logInfo "${*}"
  if ! "$@"
  then
    abort "$(printf "Failed during: %s" "$(shell_join "$@")")"
  fi
}

function execute_eval_command() {
  local RUN_COMMAND=${*}

  logInfo "${RUN_COMMAND}"
  COMMAND_RESULT=$(eval "${RUN_COMMAND}")
#  COMMAND_RESULT=$(eval "${RUN_COMMAND} > /dev/null 2>&1")
  local RETURN_STATUS=$?

  if [[ $RETURN_STATUS -eq 0 ]]; then
    logDebug "${COMMAND_RESULT}"
    logDebug "SUCCESS!"
  else
    logError "ERROR (${RETURN_STATUS})"
#    echo "${COMMAND_RESULT}"
    abort "$(printf "Failed during: %s" "${COMMAND_RESULT}")"
  fi

}

function setup_pyenv_linux() {

  logInfo "installing pyenv"

  if [[ -n "$(command -v dnf)" ]]; then
    sudo dnf install -y ${PYTHON3_RH_LIBS} && \
      sudo yum group install "Development Tools"
  elif [[ -n "$(command -v yum)" ]]; then
    sudo yum install -y ${PYTHON3_RH_LIBS} && \
      sudo yum group install "Development Tools"
  elif [[ -n "$(command -v apt-get)" ]]; then
    sudo apt-get install -y ${PYTHON3_DEB_LIBS}
  fi

  export PYENV_ROOT="${HOME}/.pyenv"
  PYENV_BIN_DIR="${PYENV_ROOT}/bin"
  PYENV_BIN="${PYENV_BIN_DIR}/pyenv"

  if [[ -z "$(command -v ${PYENV_BIN})" ]]; then
    logInfo "installing pyenv using [${PYENV_INSTALL_URL}]"
#    curl -L "${PYENV_INSTALL_URL}" | /bin/bash
    curl -L "${PYENV_INSTALL_URL}" | bash -s --
  fi

  export PATH="${PYENV_BIN_DIR}:${PATH}"
  eval "${PYENV_BIN} init - bash"
  eval "${PYENV_BIN} virtualenv-init -"
  mkdir -p "${PYENV_ROOT}/cache"

  if [[ -z "$(command -v ${PYENV_BIN})" ]]; then
    abort "PYENV_BIN => ${PYENV_BIN} not found"
  fi
  if ! command -v pyenv &> /dev/null; then
    fail "pyenv not found"
  fi
  logInfo "pyenv setup correctly"

}

function setup_pyenv_msys2() {
#  # ref: https://dev.to/taijidude/execute-a-powershell-script-from-inside-the-git-bash-1enj
#  powershell -File files\\scripts\\python\\pyenv-install.ps1
  PYENV_INSTALL_SCRIPT="${SCRIPT_DIR}/pyenv-install.ps1"
  eval "powershell.exe -noprofile -executionpolicy bypass -file ${PYENV_INSTALL_SCRIPT}"

  PYENV_ROOT="${HOME}/.pyenv/pyenv-win"
  PYENV_BIN_DIR="${PYENV_ROOT}/bin"

#  PYENV_IN_BASHENV=$(grep -c "pyenv init" ${HOME}/.bashrc)

  export PATH="${PYENV_BIN_DIR}:${PATH}"

}

function install_python_version() {
  logInfo "installing python version ${PYTHON_VERSION}"

  logInfo "PYENV_BIN=${PYENV_BIN}"
  if [[ -z "$(command -v ${PYENV_BIN})" ]]; then
    abort "PYENV_BIN => ${PYENV_BIN} not found"
  fi
  if ! command -v pyenv &> /dev/null; then
    fail "pyenv not found"
  fi
  logInfo "pyenv setup correctly"

  PYENV_VERSION_EXISTS="$(${PYENV_BIN} versions | grep -c "${PYTHON_VERSION}")"
  logInfo "PYENV_VERSION_EXISTS=${PYENV_VERSION_EXISTS}"

#  if [ -d "$(pyenv root)/versions/${PYTHON_VERSION}" ]; then
#    logInfo "python version ${PYTHON_VERSION} already exists at [$(pyenv root)/versions/${PYTHON_VERSION}]"
  if [ "${PYENV_VERSION_EXISTS}" -ne 0 ]; then
    logInfo "python version ${PYTHON_VERSION} already exists"
    exit 0
  fi

  local INSTALL_PYTHON_CMD_ARRAY=()

  ## ref: https://github.com/pyenv/pyenv/issues/2760#issuecomment-1868608898
  ## ref: https://github.com/pyenv/pyenv/issues/2416
  #    curl -Lo "$HOME/.pyenv/cache/Python-${PYTHON_VERSION}.tar.xz" \
  #        "https://registry.npmmirror.com/-/binary/python/$PYTHON_VERSION/Python-${PYTHON_VERSION}.tar.xz"
  #    #    "https://npm.taobao.org/mirrors/python/$PYTHON_VERSION/Python-$PYTHON_VERSION.tar.xz"
  #env pyenv install "${PYTHON_VERSION}"
  #env CFLAGS=-fPIC pyenv install $PYTHON_VERSION
  #env CFLAGS="-I/usr/local/openssl/include" LDFLAGS="-L/usr/local/openssl/lib" pyenv install "${PYTHON_VERSION}"
  #env CPPFLAGS="-I/usr/local/include" LDFLAGS="-L/usr/local/lib -lssl -lcrypto" CFLAGS=-fPIC pyenv install "${PYTHON_VERSION}"
  if [[ -n "${INSTALL_ON_LINUX-}" ]]; then
    INSTALL_PYTHON_CMD_ARRAY+=("env CPPFLAGS=\"-I/usr/include/openssl\"")
    INSTALL_PYTHON_CMD_ARRAY+=("LDFLAGS=\"-L/usr/lib64/openssl -lssl -lcrypto\"")
    INSTALL_PYTHON_CMD_ARRAY+=("CFLAGS=-fPIC ${PYENV_BIN} install -s ${PYTHON_VERSION}")
  elif [[ -n "${INSTALL_ON_MACOS-}" ]]; then
    ## ref: https://stackoverflow.com/questions/41430706/pyvenv-returns-non-zero-exit-status-1-during-the-installation-of-pip-stage#41430707
    ## ref: https://github.com/pyenv/pyenv/issues/2143#issuecomment-1069223994
    ## ref: https://stackoverflow.com/a/54142474/2791368
#    INSTALL_PYTHON_CMD_ARRAY+=("env CC=/usr/local/bin/gcc-13 pyenv install ${PYTHON_VERSION}")
    ## NOTE: make sure to remove the gnu gcc env from the PATH by setting it to system PATH
    ##       GNU Coreutils and Binutils on PATH are also known to break build in MacOS
    ## ref: https://github.com/pyenv/pyenv/issues/2862#issuecomment-1849198741
    ## ref: https://github.com/pyenv/pyenv/wiki/Common-build-problems#keg-only-homebrew-packages-are-forcibly-linked--added-to-path
    INSTALL_PYTHON_CMD_ARRAY+=("env PATH=/usr/local/sbin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin")
    INSTALL_PYTHON_CMD_ARRAY+=("CFLAGS=\"-I$(brew --prefix readline)/include -I$(brew --prefix openssl)/include -I$(xcrun --show-sdk-path)/usr/include\"")
    INSTALL_PYTHON_CMD_ARRAY+=("LDFLAGS=\"-L$(brew --prefix readline)/lib -L$(brew --prefix openssl)/lib\"")
    INSTALL_PYTHON_CMD_ARRAY+=("PYTHON_CONFIGURE_OPTS=--enable-unicode=ucs2")
    INSTALL_PYTHON_CMD_ARRAY+=("${PYENV_BIN} install -s ${PYTHON_VERSION}")
  else
    INSTALL_PYTHON_CMD_ARRAY+=("${PYENV_BIN} install -s ${PYTHON_VERSION}")
  fi

  execute_eval_command "${INSTALL_PYTHON_CMD_ARRAY[*]}"
#  execute "${INSTALL_PYTHON_CMD_ARRAY[*]}"
#  eval "${INSTALL_PYTHON_CMD_ARRAY[*]}"

  mkdir -p "$HOME/.config/pip"
  [ -f "$HOME/.config/pip/pip.conf" ] && mv "$HOME/.config/pip/pip.conf" "$HOME/.config/pip/pip.conf.bak"

  logInfo "Ensure pip.conf setup correctly"
  cat <<EOF >> "${HOME}/.config/pip/pip.conf"
# pip.ini (Windows)
# pip.conf (Unix, macOS)

[global]
trusted-host = pypi.org
               files.pythonhosted.org
EOF

}

function main() {

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
      abort "Install script is only supported on macOS, Linux and msys2."
      ;;
  esac

  ## ref: https://www.pythonpool.com/fixed-modulenotfounderror-no-module-named-_bz2/
  ## ref: https://stackoverflow.com/questions/27022373/python3-importerror-no-module-named-ctypes-when-using-value-from-module-mul#48045929
  if [[ -n "${INSTALL_ON_LINUX-}" ]]; then
    setup_pyenv_linux
    logInfo "update pyenv to get most recent python dist info"
    pyenv update
  fi
  if [[ -n "${INSTALL_ON_MACOS-}" ]]; then
    ## ref: https://webinstall.dev/pyenv/
    xcode-select --install
    ## ref: https://github.com/pyenv/pyenv-installer/issues/50#issuecomment-275295469
    brew update
    brew upgrade    ## ref: https://github.com/pyenv/pyenv/issues/2143
    brew install gcc make
    brew install pyenv
  fi
  if [[ -n "${INSTALL_ON_MSYS-}" ]]; then
    setup_pyenv_msys2
    logInfo "update pyenv to get most recent python dist info"
    pyenv update
  fi

  install_python_version

}

main "$@"
