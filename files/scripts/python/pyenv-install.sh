#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLATFORM_OS=$(uname -s | tr "[:upper:]" "[:lower:]")

# Python 3
#PYTHON_VERSION_DEFAULT="3.9.7"
#PYTHON_VERSION_DEFAULT=3.10.9
PYTHON_VERSION_DEFAULT=3.11.7
#PYTHON_VERSION_DEFAULT=3.12.1

## source: https://gist.github.com/simonkuang/14abf618f631ba3f0c7fee7b4ea3f214
#PYTHON3_RH_LIBS=epel-release
#PYTHON3_RH_LIBS="gcc gcc-c++ glibc glibc-devel curl git libffi-devel sqlite-devel bzip2-devel bzip2 readline-devel"
#PYTHON3_RH_LIBS="zlib-devel bzip2-devel openssl-devel ncurses-devel sqlite-devel readline-devel tk-devel gdbm-devel db4-devel libpcap-devel xz-devel"
##PYTHON3_RH_LIBS="zlib-devel bzip2-devel sqlite sqlite-devel openssl-devel"
#PYTHON3_RH_LIBS="python3-devel readline-devel bzip2-devel libffi-devel ncurses-devel sqlite-devel"
PYTHON3_RH_LIBS="readline-devel bzip2-devel libffi-devel ncurses-devel sqlite-devel openssl-devel"
PYTHON3_DEB_LIBS="libreadline-dev libbz2-dev libffi-dev libncurses-dev libsqlite3-dev liblzma-dev libssl-dev"

PYTHON_VERSION=${1-"${PYTHON_VERSION_DEFAULT}"}


function setup_pyenv_linux() {

  if [[ -n "$(command -v dnf)" ]]; then
    sudo dnf install -y ${PYTHON3_RH_LIBS} && \
      sudo yum group install "Development Tools"
  elif [[ -n "$(command -v yum)" ]]; then
    sudo yum install -y ${PYTHON3_RH_LIBS} && \
      sudo yum group install "Development Tools"
  elif [[ -n "$(command -v apt-get)" ]]; then
    sudo apt-get install -y ${PYTHON3_DEB_LIBS}
  fi

  PYENV_ROOT="${HOME}/.pyenv"
  PYENV_BIN_DIR="${PYENV_ROOT}/bin"
  PYENV_BIN="${PYENV_BIN_DIR}/pyenv"

  if [[ -z "$(command -v ${PYENV_BIN})" ]]; then
    curl -L https://github.com/pyenv/pyenv-installer/raw/master/bin/pyenv-installer | /bin/bash
  fi

#  PYENV_IN_BASHENV=$(grep -c "pyenv init" ${HOME}/.bashrc)

  export PATH="${PYENV_BIN_DIR}:${PATH}"
  eval "${PYENV_BIN} init -"
  eval "${PYENV_BIN} virtualenv-init -"

  mkdir -p "${PYENV_ROOT}/cache"

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
  fi
  if [[ -n "${INSTALL_ON_MACOS-}" ]]; then
    ## ref: https://github.com/pyenv/pyenv/issues/2143
    brew install gcc make
    brew install pyenv
  fi
  if [[ -n "${INSTALL_ON_MSYS-}" ]]; then
    setup_pyenv_msys2
  fi

  PYENV_VERSION_EXISTS=$(pyenv version | grep -c "${PYTHON_VERSION}")

#  if [ -d "$(pyenv root)/versions/${PYTHON_VERSION}" ]; then
#    echo "python version ${PYTHON_VERSION} already exists at [$(pyenv root)/versions/${PYTHON_VERSION}]"
  if [ "${PYENV_VERSION_EXISTS}" -ne 0 ]; then
    echo "python version ${PYTHON_VERSION} already exists"
    exit 0
  fi

  ## ref: https://github.com/pyenv/pyenv/issues/2760#issuecomment-1868608898
  ## ref: https://github.com/pyenv/pyenv/issues/2416
  #env pyenv install "${PYTHON_VERSION}"
  #env CFLAGS=-fPIC pyenv install $PYTHON_VERSION
  #env CFLAGS="-I/usr/local/openssl/include" LDFLAGS="-L/usr/local/openssl/lib" pyenv install "${PYTHON_VERSION}"
  #env CPPFLAGS="-I/usr/local/include" LDFLAGS="-L/usr/local/lib -lssl -lcrypto" CFLAGS=-fPIC pyenv install "${PYTHON_VERSION}"
  if [[ -n "${INSTALL_ON_LINUX-}" ]]; then
#    curl -Lo "$HOME/.pyenv/cache/Python-${PYTHON_VERSION}.tar.xz" \
#        "https://registry.npmmirror.com/-/binary/python/$PYTHON_VERSION/Python-${PYTHON_VERSION}.tar.xz"
#    #    "https://npm.taobao.org/mirrors/python/$PYTHON_VERSION/Python-$PYTHON_VERSION.tar.xz"
    env CPPFLAGS="-I/usr/include/openssl" LDFLAGS="-L/usr/lib64/openssl -lssl -lcrypto" CFLAGS=-fPIC pyenv install "${PYTHON_VERSION}"
  elif [[ -n "${INSTALL_ON_MACOS-}" ]]; then
    ## ref: https://stackoverflow.com/questions/41430706/pyvenv-returns-non-zero-exit-status-1-during-the-installation-of-pip-stage#41430707
    ## ref: https://github.com/pyenv/pyenv/issues/2143#issuecomment-1069223994
    ## ref: https://stackoverflow.com/a/54142474/2791368
#    env CC=/usr/local/bin/gcc-13 pyenv install "${PYTHON_VERSION}"
    CFLAGS="-I$(brew --prefix readline)/include -I$(brew --prefix openssl)/include -I$(xcrun --show-sdk-path)/usr/include" \
      LDFLAGS="-L$(brew --prefix readline)/lib -L$(brew --prefix openssl)/lib" \
      PYTHON_CONFIGURE_OPTS=--enable-unicode=ucs2 \
      pyenv install "${PYTHON_VERSION}"
  else
    pyenv install "${PYTHON_VERSION}"
  fi

  mkdir -p $HOME/.config/pip
  [ -f $HOME/.config/pip/pip.conf ] && mv $HOME/.config/pip/pip.conf $HOME/.config/pip/pip.conf.bak

  cat <<EOF >> "${HOME}/.config/pip/pip.conf"
# pip.ini (Windows)
# pip.conf (Unix, macOS)

[global]
trusted-host = pypi.org
               files.pythonhosted.org
EOF

}

main "$@"
