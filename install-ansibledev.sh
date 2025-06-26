#!/usr/bin/env bash

## ref: https://intoli.com/blog/exit-on-errors-in-bash-scripts/
# exit when any command fails
set -e

VERSION="2025.6.12"

#SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT_DIR="$(dirname "$0")"
SCRIPT_NAME="$(basename "$0")"

INSTALL_BASEDIR="${HOME}/repos/ansible"
INSTALL_REPOSITORY="${INSTALL_BASEDIR}/ansible-developer"

INSTALL_GIT_REPO=1

INSTALL_GIT_REMOTE_DEFAULT="https://github.com/lj020326/ansible-developer.git"

CHMOD=("/bin/chmod")
MKDIR=("/bin/mkdir" "-p")

#REQUIRED_SYSTEM_PYTHON3_VERSION=3.9.1
REQUIRED_SYSTEM_PYTHON3_VERSION=3.6.1

REQUIRED_GIT_VERSION=1.8.3
#REQUIRED_GIT_VERSION=2.7.0

#REQUIRED_VENV_PYTHON_VERSION="3.10.9"
#REQUIRED_VENV_PYTHON_VERSION="3.11.9"
#REQUIRED_VENV_PYTHON_VERSION="3.12.3"
REQUIRED_VENV_PYTHON_VERSION="3.12.9"

REQUIRED_PYTHON_LIBS="ansible certifi"

SYSTEM_PATH=/usr/local/sbin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin

# We don't need return codes for "$(command)", only stdout is needed.
# Allow `[[ -n "$(command)" ]]`, `func "$(command)"`, pipes, etc.
# shellcheck disable=SC2312

#set -u


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
    printf "${tty_blue}[${PADDED_LOG_LEVEL}]: ==>${tty_reset} %s\n" "${__LOG_MESSAGE}" >&2
#    printf "${tty_blue}[${PADDED_LOG_LEVEL}]: ==>${tty_bold} %s${tty_reset}\n" "${__LOG_MESSAGE}"
  elif [ "${LOG_MESSAGE_LEVEL}" -eq $LOG_WARN ]; then
    printf "${tty_orange}[${PADDED_LOG_LEVEL}]: ==>${tty_bold} %s${tty_reset}\n" "${__LOG_MESSAGE}" >&2
#    printf "${tty_red}Warning${tty_reset}: %s\n" "$(chomp "$1")" >&2
  elif [ "${LOG_MESSAGE_LEVEL}" -le $LOG_ERROR ]; then
    printf "${tty_red}[${PADDED_LOG_LEVEL}]: ==>${tty_bold} %s${tty_reset}\n" "${__LOG_MESSAGE}" >&2
#    printf "${tty_red}Warning${tty_reset}: %s\n" "$(chomp "$1")" >&2
  else
    printf "[${PADDED_LOG_LEVEL}]: ==> %s\n" "${LOG_PREFIX} ${LOG_MESSAGE}"
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

function handle_cmd_return_code() {
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
    echo "${COMMAND_RESULT}"
    exit 1
  fi

}

function isInstalled() {
  command -v "${1}" >/dev/null 2>&1 || return 1
}

function checkRequiredCommands() {
  missingCommands=""
  for currentCommand in "$@"
  do
    isInstalled "${currentCommand}" || missingCommands="${missingCommands} ${currentCommand}"
  done

  if [[ -n "${missingCommands}" ]]; then
    fail "checkRequiredCommands(): Please install the following commands required by this script:${missingCommands}"
  fi
}

function test_git() {
  if [[ ! -x "$1" ]]
  then
    return 1
  fi

  local git_version_output
  git_version_output="$("$1" --version 2>/dev/null)"
  if [[ "${git_version_output}" =~ "git version "([^ ]*).* ]]
  then
    version_ge "$(major_minor "${BASH_REMATCH[1]}")" "$(major_minor "${REQUIRED_GIT_VERSION}")"
  else
    abort "Unexpected Git version: '${git_version_output}'!"
  fi
}

function test_python3() {
  if [[ ! -x "$1" ]]
  then
    return 1
  fi

  local python3_version_output python3_name_and_version
  python3_version_output="$("$1" --version 2>/dev/null)"
  python3_name_and_version="${python3_version_output%% (*}"
  version_ge "$(major_minor "${python3_name_and_version##* }")" "$(major_minor "${REQUIRED_SYSTEM_PYTHON3_VERSION}")"
}

# Search for the given executable in PATH (avoids a dependency on the `which` command)
function which() {
  # Alias to Bash built-in command `type -P`
  type -P "$@"
}

# Search PATH for the specified program that satisfies requirements
# function which is set above
# shellcheck disable=SC2230
function find_tool() {
  if [[ $# -ne 1 ]]
  then
    return 1
  fi

  local executable
  while read -r executable
  do
    if [[ "${executable}" != /* ]]
    then
      warn "Ignoring ${executable} (relative paths don't work)"
    elif "test_${1}" "${executable}"
    then
      echo "${executable}"
      break
    fi
  done < <(which -a "$1")
}

function major_minor() {
  echo "${1%%.*}.$(
    x="${1#*.}"
    echo "${x%%.*}"
  )"
}

function version_gt() {
  [[ "${1%.*}" -gt "${2%.*}" ]] || [[ "${1%.*}" -eq "${2%.*}" && "${1#*.}" -gt "${2#*.}" ]]
}
function version_ge() {
  [[ "${1%.*}" -gt "${2%.*}" ]] || [[ "${1%.*}" -eq "${2%.*}" && "${1#*.}" -ge "${2#*.}" ]]
}
function version_lt() {
  [[ "${1%.*}" -lt "${2%.*}" ]] || [[ "${1%.*}" -eq "${2%.*}" && "${1#*.}" -lt "${2#*.}" ]]
}

function install_git_repo() {

  logInfo "This script will install:"
  echo "${INSTALL_REPOSITORY}"

  if ! [[ -d "${INSTALL_REPOSITORY}" ]]
  then
    execute "${MKDIR[@]}" "${INSTALL_REPOSITORY}"
  fi

  logInfo "Downloading and installing ansible-developer repo..."
  (
    cd "${INSTALL_REPOSITORY}" >/dev/null || return

    # we do it in four steps to avoid merge errors when reinstalling
    execute "${USABLE_GIT}" "-c" "init.defaultBranch=main" "init" "--quiet"

    # "git remote add" will fail if the remote is defined in the global config
    execute "${USABLE_GIT}" "config" "remote.origin.url" "${INSTALL_GIT_REMOTE}"
    execute "${USABLE_GIT}" "config" "remote.origin.fetch" "+refs/heads/*:refs/remotes/origin/*"

    # ensure we don't munge line endings on checkout
    execute "${USABLE_GIT}" "config" "--bool" "core.autocrlf" "false"

    # make sure symlinks are saved as-is
    execute "${USABLE_GIT}" "config" "--bool" "core.symlinks" "true"

  #  execute ssh-keyscan -p "${GIT_REMOTE_PORT}" "${GIT_REMOTE_HOST}" >> "${HOME}/.ssh/known_hosts"

    execute "${USABLE_GIT}" "fetch" "--force" "origin"
    execute "${USABLE_GIT}" "fetch" "--force" "--tags" "origin"

    execute "${USABLE_GIT}" "reset" "--hard" "origin/main"
    execute "${USABLE_GIT}" "branch" "--set-upstream-to=origin/main"

  ) || exit 1

}

function setup_python_env() {

  logInfo "Setup pyenv and user python environment..."
  (
    PYENV_INSTALL_CMD_ARRAY=("bash")
    if [[ "${LOG_LEVEL-}" -ge $LOG_DEBUG ]]; then
      PYENV_INSTALL_CMD_ARRAY+=("-x")
    fi
    PYENV_INSTALL_CMD_ARRAY+=("${INSTALL_REPOSITORY}/files/scripts/python/pyenv-install.sh")
    PYENV_INSTALL_CMD_ARRAY+=("${REQUIRED_VENV_PYTHON_VERSION}")

    execute "${PYENV_INSTALL_CMD_ARRAY[@]}"

    export PYENV_ROOT="${HOME}/.pyenv"
    [ -d "${PYENV_ROOT}/bin" ] && PYENV_BIN_DIR="${PYENV_ROOT}/bin"
    [ -f "${PYENV_ROOT}/shims/pyenv" ] && PYENV_BIN_DIR="${PYENV_ROOT}/shims"

    [[ -v PYENV_BIN_DIR ]] && export PATH="${PYENV_BIN_DIR}:${PATH}" \
     && PYENV_BIN="${PYENV_BIN_DIR}/pyenv"
#    local PYENV_BIN="$(which pyenv)"

    logInfo "PYENV_BIN=${PYENV_BIN}"
    if [[ -z "$(command -v ${PYENV_BIN})" ]]; then
      abort "PYENV_BIN => ${PYENV_BIN} not found"
    fi
    if ! command -v pyenv &> /dev/null; then
      fail "pyenv not found"
    fi
    logInfo "pyenv setup correctly"

#  	if ! command -v pyenv &> /dev/null; then
##    if [[ -n "$(env PATH=${SYSTEM_PATH} command -v pyenv)" ]]; then
#      fail "pyenv not found"
#    fi

    local PYTHON_VENV_BINDIR="${PYENV_ROOT}/versions/${REQUIRED_VENV_PYTHON_VERSION}/bin"
    local PYTHON_BIN="${PYTHON_VENV_BINDIR}/python3"
    local PIP_BIN="${PYTHON_VENV_BINDIR}/pip3"
    local ANSIBLE_BIN="${PYTHON_VENV_BINDIR}/ansible"

    ## ref: https://stackoverflow.com/questions/58679742/set-default-python-with-pyenv
    echo "pyenv global ${REQUIRED_VENV_PYTHON_VERSION}"
    eval "pyenv global ${REQUIRED_VENV_PYTHON_VERSION}"
    export PATH="${PYTHON_VENV_BINDIR}:${PATH}"

    echo "${PIP_BIN} --version"
    ${PIP_BIN} --version

#    echo "${PIP_BIN} install --upgrade pip"
#    eval "${PIP_BIN} install --upgrade pip"
    echo "${PYTHON_BIN} -m pip install --upgrade pip"
    eval "${PYTHON_BIN} -m pip install --upgrade pip"

    echo "${PIP_BIN} install --upgrade ${REQUIRED_PYTHON_LIBS}"
    eval "${PIP_BIN} install --upgrade ${REQUIRED_PYTHON_LIBS}"

    eval "${ANSIBLE_BIN} --version"
  ) || exit 1

}

function setup_cacerts() {

  logInfo "Setup CA certs..."
  (
    eval "sudo ${INSTALL_REPOSITORY}/files/scripts/certs/install-cacerts.sh"
  ) || exit 1

  echo
}

function setup_user_env() {

  logInfo "Setup user bash environment..."
  (
    eval "${INSTALL_REPOSITORY}/sync-bashenv.sh"
  ) || exit 1

  echo
}

## ref: https://medium.com/@michael.schladt/bringing-gnu-linux-tools-to-windows-w-msys2-f663f89d8d08
function setup_windows() {
  logInfo "Setup windows environment..."
  (
#    yes | pacman -Syu && \
    pacman --noconfirm -Syu && \
    pacman --noconfirm -S --needed base-devel \
      mingw-w64-i686-toolchain \
      mingw-w64-x86_64-toolchain \
      git \
      mingw-w64-i686-cmake \
      mingw-w64-x86_64-cmake
  ) || exit 1

  echo
}

function setup_macos() {

  ## ref: https://brew.sh/
  ## ref: https://docs.brew.sh/Installation#unattended-installation
  ## ref: https://github.com/Homebrew/install/issues/714
  yes "" | NONINTERACTIVE=1 /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

  ## homebrew/dupes deprecated
  ## ref: https://github.com/Homebrew/brew/issues/7628
#  brew tap homebrew/dupes
  brew untap homebrew/dupes >/dev/null 2>&1 || true

  ## ref: https://apple.stackexchange.com/questions/69223/how-to-replace-mac-os-x-utilities-with-gnu-core-utilities#69332
  ## ref: https://gist.githubusercontent.com/clayfreeman/2a5e54577bcc033e2f00/raw/gnuize.sh
  brew install coreutils binutils diffutils ed findutils gawk gnutls gnu-indent gnu-getopt gnu-sed \
    gnu-tar gnu-which gnutls grep gzip screen watch wdiff wget bash gpatch \
    m4 make nano file-formula git less openssh rsync unzip vim
}

function setup_linux_packages() {

  PACKAGE_CMD=""
  PACKAGES_LIST=""

  ## ref: https://www.pythonpool.com/fixed-modulenotfounderror-no-module-named-_bz2/
  ## ref: https://stackoverflow.com/questions/27022373/python3-importerror-no-module-named-ctypes-when-using-value-from-module-mul#48045929
  if [[ -n "$(command -v dnf)" ]]; then
    PACKAGE_CMD="sudo dnf install -y"
    PACKAGES_LIST="openssl-devel"
  elif [[ -n "$(command -v yum)" ]]; then
    PACKAGE_CMD="sudo yum install -y"
    PACKAGES_LIST="openssl-devel"
  elif [[ -n "$(command -v apt-get)" ]]; then
    PACKAGE_CMD="sudo apt-get install -y"
    PACKAGES_LIST="libssl-dev"
  fi

  PACKAGE_CMD_PACKAGES="${PACKAGE_CMD} ${PACKAGES_LIST}"
  eval "${PACKAGE_CMD_PACKAGES}"

}

function usage() {
  cat <<EOS
Ansible Developer Environment Installer
Usage: [NONINTERACTIVE=1] [CI=1] ${SCRIPT_NAME} [options]
    Options:
    -L [ERROR|WARN|INFO|TRACE|DEBUG] : run with specified log level (default: '${LOGLEVEL_TO_STR[${LOG_LEVEL}]}')
    -r [GIT_REMOTE_URL] : use specified git remote url
    -h, --help       Display this message.
    NONINTERACTIVE   Install without prompting for user input
    CI               Install in CI mode (e.g. do not prompt for user input)
EOS
  exit "${1:-0}"
}

function main() {
  # Fail fast with a concise message when not using bash
  # Single brackets are needed here for POSIX compatibility
  # shellcheck disable=SC2292
  if [ -z "${BASH_VERSION:-}" ]
  then
    abort "Bash is required to interpret this script."
  fi

  # Check if script is run with force-interactive mode in CI
  if [[ -n "${CI-}" && -n "${INTERACTIVE-}" ]]
  then
    abort "Cannot run force-interactive mode in CI."
  fi

  # Check if both `INTERACTIVE` and `NONINTERACTIVE` are set
  # Always use single-quoted strings with `exp` expressions
  # shellcheck disable=SC2016
  if [[ -n "${INTERACTIVE-}" && -n "${NONINTERACTIVE-}" ]]
  then
    abort 'Both `$INTERACTIVE` and `$NONINTERACTIVE` are set. Please unset at least one variable and try again.'
  fi

  # Check if script is run in POSIX mode
  if [[ -n "${POSIXLY_CORRECT+1}" ]]
  then
    abort 'Bash must not run in POSIX mode. Please unset POSIXLY_CORRECT and try again.'
  fi

  while getopts "L:r:vh" opt; do
    case "${opt}" in
      L) setLogLevel "${OPTARG}" ;;
      r) GIT_REMOTE_URL="${OPTARG}" ;;
      v) echo "${VERSION}" && exit ;;
      h | help | \?) usage ;;
      *)
        warn "Unrecognized option: ${opt}"
        usage 1
        ;;
    esac
  done

  INSTALL_GIT_REMOTE="${GIT_REMOTE_URL-$INSTALL_GIT_REMOTE_DEFAULT}"

  checkRequiredCommands python3 rsync

  # Check if script is run non-interactively (e.g. CI)
  # If it is run non-interactively we should not prompt for passwords.
  # Always use single-quoted strings with `exp` expressions
  # shellcheck disable=SC2016
  if [[ -z "${NONINTERACTIVE-}" ]]
  then
    if [[ -n "${CI-}" ]]
    then
      warn 'Running in non-interactive mode because `$CI` is set.'
      NONINTERACTIVE=1
    elif [[ ! -t 0 ]]
    then
      if [[ -z "${INTERACTIVE-}" ]]
      then
        warn 'Running in non-interactive mode because `stdin` is not a TTY.'
        NONINTERACTIVE=1
      else
        warn 'Running in interactive mode despite `stdin` not being a TTY because `$INTERACTIVE` is set.'
      fi
    fi
  else
    ohai 'Running in non-interactive mode because `$NONINTERACTIVE` is set.'
  fi

  if [[ "${LOG_LEVEL-}" -ge $LOG_INFO ]]; then
    logInfo "LOG_LEVEL=${LOGLEVEL_TO_STR[${LOG_LEVEL}]}"
  fi

  # USER isn't always set so provide a fall back for the installer and subprocesses.
  if [[ -z "${USER-}" ]]
  then
    USER="$(chomp "$(id -un)")"
    export USER
  fi

  echo "Initialize PLATFORM_OS"
  #PLATFORM_OS="$(uname)"
  PLATFORM_OS=$(uname -s | tr "[:upper:]" "[:lower:]")

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

  USABLE_GIT=/usr/bin/git
  if [[ -n "${INSTALL_ON_LINUX-}" ]]; then
    USABLE_GIT="$(find_tool git)"
    if [[ -z "$(command -v git)" ]]; then
      abort "You must install Git before installing ansible-developer."
    fi
    if [[ -z "${USABLE_GIT}" ]]; then
      abort "The version of Git that was found does not satisfy requirements for install.\n
Please install Git ${REQUIRED_GIT_VERSION} or newer and add it to your PATH."
    fi
    if [[ "${USABLE_GIT}" != /usr/bin/git ]]
    then
      export GIT_PATH="${USABLE_GIT}"
      logInfo "Found Git: ${GIT_PATH}"
    fi
  fi

  USABLE_PYTHON3=/usr/bin/python3
  if [[ -n "${INSTALL_ON_LINUX-}" ]]
  then
    USABLE_PYTHON3="$(find_tool python3)"
    if [[ -z "$(command -v python3)" ]]; then
      abort $(
        cat <<EOABORT
    You must install python3 before installing ansible-developer.
EOABORT
      )
    fi
    if [[ -z "${USABLE_PYTHON3}" ]]; then
      abort $(
        cat <<EOABORT
    The version of python3 that was found does not satisfy requirements for install.
    Please install python3 ${REQUIRED_SYSTEM_PYTHON3_VERSION} or newer and add it to your PATH.
EOABORT
      )
    fi
    if [[ "${USABLE_PYTHON3}" != /usr/bin/python3 ]]
    then
      export PYTHON3_PATH="${USABLE_PYTHON3}"
      logInfo "Found Git: ${PYTHON3_PATH}"
    fi
  fi

  if [[ -n "${INSTALL_ON_MACOS-}" ]]
  then
    setup_macos
  fi

  if [[ -n "${INSTALL_ON_MSYS-}" ]]
  then
    setup_windows
  fi

  if [[ "${INSTALL_GIT_REPO-}" -eq 1 ]]; then
    install_git_repo
  fi

  setup_python_env

  setup_cacerts

  setup_user_env

  logInfo "Installation successful!"
  echo
}

main "$@"
