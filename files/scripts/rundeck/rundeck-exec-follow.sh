#!/bin/bash

## ref: https://github.com/fabiojose/platform-as-code-example/blob/master/Jenkinsfile
## source: https://gist.github.com/fabiojose/997102b18b31123373598d0550c51ea2

######
# Shell script to trigger and follow the rundeck job execution.
# Necessary environment variables
#   RUNDECK_USERNAME
#   RUNDECK_PASSWORD
#   RUNDECK_URL
#   JOB_NAME
#   BUILD_NUMBER
######

######
# Arguments
#   $1: The job argument's Name
#   $2: The job argument's Value
#   $3: Rundeck Job ID
######

######
# Necessary installed linux tools
#   sed
#   jq
#   cut
#   grep
#   curl
######

COOKIES=cookies.txt
LOGFILE=rdkexec.log

curl -X POST \
    -d "j_username=$RUNDECK_USERNAME" \
    -d "j_password=$RUNDECK_PASSWORD" \
    -b "$COOKIES" \
    -c "$COOKIES" \
    "$RUNDECK_URL/j_security_check"
rc="$?"

if [ "${rc}" -eq 0 ]; then

    ######
    # Trigger the job with one custom argument, 'ci-name' with Jenkins JOB_NAME and 'ci-id' with Jenkins BUILD_NUMBER
    #####
    http=$(curl -s -X POST \
        -b "$COOKIES" \
        -c "$COOKIES" \
        -d "argString=-$1 $2 -ci-name $JOB_NAME -ci-id $BUILD_NUMBER" \
        "$RUNDECK_URL/api/1/job/$3/run" \
        -o $LOGFILE \
        -w '%{http_code}')

    rc="$?"

    if [ "${rc}" -eq 0 ] && [ "$http" = "200" ]; then
        # Get execution ID
        run_id=$(grep -oh "execution id='[0-9]*'" "$LOGFILE" | cut -d '=' -f2 | sed "s|'||g")

        echo " - - - - - - START - RUNDECK EXECUTION ID: $run_id"
        offset=0
        lastmod=0

        # Get execution state and logs
        while :; do

            if [ -z "$offset" ]; then
                offset=0
            fi

            if [ -z "$lastmod" ] || [ "$lastmod" = "null" ]; then
                lastmod=0
            fi

            curl -s -X GET \
                -b "$COOKIES" \
                -c "$COOKIES" \
                "$RUNDECK_URL/api/5/execution/$run_id/output.json?offset=$offset&lastmod=$lastmod" \
                -o $LOGFILE

            rc="$?"

            if [ "${rc}" -eq 0 ]; then

                # Get the offset
                offset=$(jq -r '.offset' $LOGFILE)

                # Get the lastmod
                lastmod=$(jq -r '.lastModified' $LOGFILE)

                # Get the completed
                completed=$(jq -r '.completed' $LOGFILE)

                # Get the unmodified
                unmodified=$(jq -r '.unmodified' $LOGFILE)

                # Show log lines
                jq -r '.entries[] | .log?' $LOGFILE

                if [ "$completed" = "true" ]; then
                    while :; do
                        # Check the execution status
                        curl -s -X GET \
                            -b "$COOKIES" \
                            -c "$COOKIES" \
                            "$RUNDECK_URL/api/1/execution/$run_id" \
                            -o $LOGFILE

                        result=$(grep -oh "status='[a-z]*'" "$LOGFILE" | cut -d '=' -f2 | sed "s|'||g")

                        if [ "$result" = "succeeded" ]; then
                            echo " - - - - - - - END - RUNDECK EXECUTION ID: $run_id"
                            rm $COOKIES
                            rm $LOGFILE
                            exit 0
                        elif [ "$result" = "running" ]; then
                            sleep 2
                        else
                            echo " - - - - - -FAILED - RUNDECK EXECUTION ID: $run_id >>> STATUS: $result"
                            rm $COOKIES
                            rm $LOGFILE
                            exit 5
                        fi
                    done
                fi

                if [ "$unmodified" = "true" ]; then
                    sleep 5
                else
                    sleep 2
                fi
            else
                echo "Failed to get rundeck log."
                exit 4
            fi
        done

    else
        echo "Failed to trigger rundeck job."
        exit 3
    fi
else
    echo "Rundeck configuration is not valid!"
    exit 2
fi
