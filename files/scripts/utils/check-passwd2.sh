#!/usr/bin/env bash

## ref: https://askubuntu.com/questions/611580/how-to-check-the-password-entered-is-a-valid-password-for-this-user

read -rp "Username >" username
IFS= read -rp "Password >" password
# shellcheck disable=SC2034
salt=$(sudo getent shadow "$username" | cut -d$ -f3)
stored_hashed_password=$(sudo getent shadow "$username" | cut -d: -f2)
match=$(python3 -c 'import bcrypt; print(bcrypt.hashpw("'"${password}"'", bcrypt.gensalt()))')
[ "${match}" == "${stored_hashed_password}" ] && echo "Password matches" || echo "Password doesn't match"
