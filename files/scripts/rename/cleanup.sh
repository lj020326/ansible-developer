#!/usr/bin/env bash

#DATE=20170208131334

for DATE in "$@"
do
    echo "**********************************"
    echo "*** Rolling back changes for DATE=$DATE"
    echo "**********************************"
    find . -name -iname "*.save.$DATE" -exec rm -rf {} \;
done
