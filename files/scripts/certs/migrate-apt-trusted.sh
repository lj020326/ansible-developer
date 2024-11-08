#!/usr/bin/env bash

## ref: https://askubuntu.com/questions/1407632/key-is-stored-in-legacy-trusted-gpg-keyring-etc-apt-trusted-gpg
for KEY in $( \
    apt-key --keyring /etc/apt/trusted.gpg list \
    | grep -E "(([ ]{1,2}(([0-9A-F]{4}))){10})" \
    | tr -d " " \
    | grep -E "([0-9A-F]){8}\b" \
); do
    K=${KEY:(-8)}
    apt-key export $K \
    | sudo gpg --yes --dearmour -o /etc/apt/trusted.gpg.d/imported-from-trusted-gpg-$K.gpg
done

chmod 644 /etc/apt/trusted.gpg.d/imported-from-trusted-gpg-*
