#!/bin/bash

# Python 3
#PYTHON_VERSION_DEFAULT="3.9.7"
#PYTHON_VERSION_DEFAULT=3.10.9
PYTHON_VERSION_DEFAULT=3.11.7
#PYTHON_VERSION_DEFAULT=3.12.1

#PYTHON3_RH_LIBS="python3-devel readline-devel bzip2-devel libffi-devel ncurses-devel sqlite-devel"
PYTHON3_RH_LIBS="readline-devel bzip2-devel libffi-devel ncurses-devel sqlite-devel"
PYTHON3_DEB_LIBS="libreadline-dev libbz2-dev libffi-dev libncurses-dev libsqlite3-dev"

PYTHON_VERSION=${1-"${PYTHON_VERSION_DEFAULT}"}

## source: https://gist.github.com/simonkuang/14abf618f631ba3f0c7fee7b4ea3f214

#sudo yum install -y epel-release
#sudo yum install -y gcc gcc-c++ glibc glibc-devel curl git \
#    libffi-devel sqlite-devel bzip2-devel bzip2 readline-devel
#
#sudo yum install -y zlib-devel bzip2-devel openssl-devel ncurses-devel sqlite-devel readline-devel tk-devel gdbm-devel db4-devel libpcap-devel xz-devel
##sudo yum install -y zlib-devel bzip2-devel sqlite sqlite-devel openssl-devel

PYENV_ROOT="${HOME}/.pyenv"
PYENV_BIN="${PYENV_ROOT}/bin/pyenv"

if [[ -z "$(command -v ${PYENV_BIN})" ]]; then
  curl -L https://github.com/pyenv/pyenv-installer/raw/master/bin/pyenv-installer | /bin/bash
fi

PYENV_IN_BASHENV=$(grep -c "pyenv init" ${HOME}/.bashrc)

export PATH="${HOME}/.pyenv/bin:${PATH}"
eval "$(pyenv init -)"
eval "$(pyenv virtualenv-init -)"

mkdir -p $HOME/.pyenv/cache

if [ -d "$(pyenv root)/versions/${PYTHON_VERSION}" ]; then
  echo "python version ${PYTHON_VERSION} already exists at [$(pyenv root)/versions/${PYTHON_VERSION}]"
  exit 0
fi

curl -Lo "$HOME/.pyenv/cache/Python-$PYTHON_VERSION.tar.xz" \
    "https://registry.npmmirror.com/-/binary/python/$PYTHON_VERSION/Python-$PYTHON_VERSION.tar.xz"
#    "https://npm.taobao.org/mirrors/python/$PYTHON_VERSION/Python-$PYTHON_VERSION.tar.xz"

OS=$(uname -s | tr "[:upper:]" "[:lower:]")

case "${OS}" in
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
if [[ -n "${INSTALL_ON_LINUX-}" ]]
then
  if [[ -n "$(command -v dnf)" ]]; then
    sudo dnf install -y ${PYTHON3_RH_LIBS}
  elif [[ -n "$(command -v yum)" ]]; then
    sudo yum install -y ${PYTHON3_RH_LIBS}
  elif [[ -n "$(command -v apt-get)" ]]; then
    sudo apt-get install -y ${PYTHON3_DEB_LIBS}
  fi
fi

## ref: https://github.com/pyenv/pyenv/issues/2416
#env CFLAGS=-fPIC pyenv install $PYTHON_VERSION
env CPPFLAGS="-I/usr/include/openssl" LDFLAGS="-L/usr/lib64/openssl -lssl -lcrypto" CFLAGS=-fPIC pyenv install "${PYTHON_VERSION}"
#env CPPFLAGS="-I/usr/local/include" LDFLAGS="-L/usr/local/lib -lssl -lcrypto" CFLAGS=-fPIC pyenv install "${PYTHON_VERSION}"

mkdir -p $HOME/.config/pip
[ -f $HOME/.config/pip/pip.conf ] && mv $HOME/.config/pip/pip.conf $HOME/.config/pip/pip.conf.bak

cat <<EOF >> "${HOME}/.config/pip/pip.conf"
# pip.ini (Windows)
# pip.conf (Unix, macOS)

[global]
trusted-host = pypi.org
               files.pythonhosted.org
EOF
