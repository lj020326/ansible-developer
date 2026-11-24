#!/usr/bin/env bash

## ref: https://askubuntu.com/questions/611580/how-to-check-the-password-entered-is-a-valid-password-for-this-user

xcorrect=0
xwrong=1
enouser=2
enodata=3
esyntax=4
ehash=5

IFS=$'\n'
die() {
    printf '%s: %s\n' "$0" "$2" >&2
    exit "$1"
}
report() {
    if (($1 == xcorrect))
        then echo 'Correct password.'
        else echo 'Wrong password.'
    fi
    exit "$1"
}

(($# == 1)) || die $esyntax "Usage: $(basename "$0") <username>"
case "$(getent passwd "$1" | awk -F: '{print $2}')" in
    x)  ;;
    '') die $enouser "error: user '$1' not found";;
    *)  die $enodata "error: $1's password appears unshadowed!";;
esac

if [ -t 0 ]; then
    IFS= read -rsp "[$(basename "$0")] password for $1: " pass
    printf '\n'
else
    IFS= read -r pass
fi

echo "pass=${pass}"

set -f; IFS=':' read -r -a ent <<< "$(getent shadow "$1" | awk -F: '{print $2}')"; set +f
case "${ent[1]}" in
    1) hash_type=md5;;
    5) hash_type=sha-256;;
    6) hash_type=sha-512;;
    '') case "${ent[0]}" in
            \*|!)   report $xwrong;;
            '')     die $enodata "error: no shadow entry (are you root?)";;
            *)      die $enodata 'error: failure parsing shadow entry';;
        esac;;
    *)  die $ehash "error: password hash type is unsupported";;
esac

salt=${ent[2]}
echo "salt=${salt}"

if [[ "${ent[*]}" = "$(mkpasswd -sm "$hash_type" -S "${salt}" <<<"$pass")" ]]
    then report $xcorrect
    else report $xwrong
fi
