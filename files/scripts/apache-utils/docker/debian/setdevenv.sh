#!/usr/bin/env bash

function abort() {
    echo "$1"
    exit 1
}

alias ll='ls -Fla'
alias la='ls -alrt'

cd "/opt" || abort "unable to cd to /opt"
