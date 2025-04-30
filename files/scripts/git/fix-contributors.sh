#!/usr/bin/env bash

## ref: https://stackoverflow.com/a/44566384/2791368
## ref: https://stackoverflow.com/questions/9597410/list-all-developers-on-a-project-in-git
set -e

#git shortlog --summary --numbered --email

git filter-branch --env-filter '
if [ "$GIT_AUTHOR_NAME" = "ansible" ]; then \
    export GIT_AUTHOR_NAME="ansible" GIT_AUTHOR_EMAIL="ansible@dettonville.com"; \
fi
'
