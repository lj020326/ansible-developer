#!/usr/bin/bash

function abort() {
    echo "$1"
    exit 1
}

###############
## ref: https://gist.github.com/DaveB93/db94a6b310e08c928c0778f766562ab0
###############

which ansible >/dev/null 2>&1
rc="$?"
if [ "${rc}" -ne 0 ]; then
    echo "Installing Ansible..."
    sleep 5
    pushd .
    cd "${HOME}" || abort "unable to cd to ~"
    pacman -S libyaml-devel python2 tar libffi libffi-devel gcc pkg-config make openssl-devel openssh libcrypt-devel --noconfirm --needed
    curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py
    python2 get-pip.py
    wget -c https://download.libsodium.org/libsodium/releases/libsodium-1.0.16-mingw.tar.gz
    tar xvzf libsodium-1.0.16-mingw.tar.gz
    SODIUM_INSTALL=system CFLAGS=$(pkg-config --cflags libffi) LDFLAGS=$(pkg-config --libs libffi) C_INCLUDE_PATH=${HOME}/libsodium-win64/include LIBRARY_PATH=${HOME}/libsodium-win64/lib python2 -m pip install cffi --no-binary :all:
    SODIUM_INSTALL=system CFLAGS=$(pkg-config --cflags libffi) LDFLAGS=$(pkg-config --libs libffi) C_INCLUDE_PATH=${HOME}/libsodium-win64/include LIBRARY_PATH=${HOME}/libsodium-win64/lib python2 -m pip install pynacl
    python2 -m pip install ansible --no-binary :all:
    popd || abort "unable to popd"
fi

which ansible >/dev/null 2>&1
rc="$?"
if [ "${rc}" -ne 0 ]; then
    echo "Ansible installed."
else
    echo "Ansible not installed."
fi
