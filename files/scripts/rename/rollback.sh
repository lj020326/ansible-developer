#!/usr/bin/env bash

#DATE=20170208131334
DATE=$1

echo "**********************************"
echo "*** Rolling back changes for DATE=$DATE"
echo "**********************************"

## to rollback changes
find . -iname "*.save.$DATE" -exec sh -c '
  for f do
    dst="${f%.save."$1"}"
    printf "mv %s %s\n" "$f" "$dst"
    mv -- "$f" "$dst"
  done
' _ "$DATE" \;
