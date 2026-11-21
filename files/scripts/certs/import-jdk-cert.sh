#!/usr/bin/env bash

## ref: https://stackoverflow.com/questions/3685548/java-keytool-easy-way-to-add-server-cert-from-url-port
## ref: https://superuser.com/questions/97201/how-to-save-a-remote-server-ssl-certificate-locally-as-a-file
## ref: https://serverfault.com/questions/661978/displaying-a-remote-ssl-certificate-details-using-cli-tools

#set -x

# shellcheck disable=SC2034
VERSION="2025.6.12"

#SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC2034
SCRIPT_DIR="$(dirname "$0")"
SCRIPT_NAME="$(basename "$0")"
SCRIPT_NAME_PREFIX="${SCRIPT_NAME%.*}"

## ref: https://stackoverflow.com/questions/3685548/java-keytool-easy-way-to-add-server-cert-from-url-port
##

LOG_FILE="${SCRIPT_NAME_PREFIX}.log"

SITE_LIST_DEFAULT=()
#SITE_LIST_DEFAULT+=("artifactory.dettonville.int")
SITE_LIST_DEFAULT+=("archiva.admin.dettonville.int")
SITE_LIST_DEFAULT+=("www.jetbrains.com")

KEYTOOL=keytool
# shellcheck disable=SC2034
USER_KEYSTORE="${HOME}/.keystore"

KEYSTORE_PASS=${3:-"changeit"}

#DATE=$(date +&%%m%d%H%M%S)
# shellcheck disable=SC2034
DATE=$(date +%Y%m%d)

ALIAS="${HOST}:${PORT}"

if [[ "$OSTYPE" == "cygwin" || "$OSTYPE" == "msys" ]]; then
    ALIAS="${HOST}_${PORT}"
fi

## ref: https://knowledgebase.garapost.com/index.php/2020/06/05/how-to-get-ssl-certificate-fingerprint-and-serial-number-using-openssl-command/
## ref: https://stackoverflow.com/questions/13823706/capture-multiline-output-as-array-in-bash
#CERT_INFO=($(openssl s_client -connect $HOST:$PORT </dev/null 2>/dev/null | openssl x509 -serial -fingerprint -sha256 -noout | cut -d"=" -f2 | sed s/://g))
mapfile -t CERT_INFO < <(openssl s_client -connect "$HOST:$PORT" </dev/null 2>/dev/null | openssl x509 -serial -fingerprint -sha256 -noout | cut -d"=" -f2 | sed 's/://g')
CERT_SERIAL=${CERT_INFO[0]}
CERT_FINGERPRINT=${CERT_INFO[1]}

#CACERTS_SRC=${HOME}/.cacerts/$ALIAS/$DATE
CACERTS_SRC=${HOME}/.cacerts/$ALIAS/$CERT_SERIAL/$CERT_FINGERPRINT

if [ ! -d "$CACERTS_SRC" ]; then
    mkdir -p "$CACERTS_SRC"
fi

TMP_OUT=/tmp/${SCRIPT_NAME}.output

### functions followed by main

writeToLog() {
    echo -e "${1}" | tee -a "${LOG_FILE}"
    #    echo -e "${1}" >> "${LOG_FILE}"
}

function get_java_keystore() {
    ## default jdk location
    if [ -z "$JAVA_HOME" ]; then
        ## ref: https://stackoverflow.com/questions/394230/how-to-detect-the-os-from-a-bash-script
        if [[ "$OSTYPE" == "darwin"* ]]; then
            JAVA_HOME=$(/usr/libexec/java_home)
        elif [[ "$OSTYPE" == "cygwin" || "$OSTYPE" == "msys" ]]; then
            JAVA_HOME=$(/usr/libexec/java_home)
            #        else
            #                # Unknown.
        fi
    fi
    CERT_DIR=${JAVA_HOME}/lib/security
    if [ ! -d "$CERT_DIR" ]; then
        CERT_DIR=${JAVA_HOME}/jre/lib/security
    fi

    #    writeToLog "CERT_DIR=[$CERT_DIR]"

    writeToLog "$CERT_DIR"/cacerts
}

function get_host_cert() {
    local HOST=$1
    local PORT=$2

    writeToLog "retrieving certs from host:port ${HOST}:${PORT}"

    if [ -z "$HOST" ]; then
        writeToLog "ERROR: Please specify the server name to import the certificate in from, eventually followed by the port number, if other than 443."
        exit 1
    fi

    set -e

    if [ -e "$CACERTS_SRC/$ALIAS.pem" ]; then
        rm -f "$CACERTS_SRC"/"$ALIAS".pem
    fi

    if openssl s_client -connect "$HOST":"$PORT" 1>"$CACERTS_SRC"/"$ALIAS".crt 2>"$TMP_OUT" </dev/null; then
        :
    else
        cat "$CACERTS_SRC"/"$ALIAS".crt
        cat "$TMP_OUT"
        exit 1
    fi

    if sed -ne '/-BEGIN CERTIFICATE-/,/-END CERTIFICATE-/p' <"$CACERTS_SRC"/"$ALIAS".crt >"$CACERTS_SRC"/"$ALIAS".pem; then
        :
    else
        writeToLog "ERROR: Unable to extract the certificate from $CACERTS_SRC/$ALIAS.crt ($?)"
        cat "$TMP_OUT"
        exit 1
    fi

    writeToLog "extracting certs from cert chain for ${HOST}:${PORT}"
    ## ref: https://unix.stackexchange.com/questions/368123/how-to-extract-the-root-ca-and-subordinate-ca-from-a-certificate-chain-in-linux
    openssl s_client -showcerts -verify 5 -connect "$HOST":"$PORT" </dev/null | awk -v cert_dir="$CACERTS_SRC" '/BEGIN/,/END/{ if(/BEGIN/){a++}; out="cert"a".crt"; print >(cert_dir "/" out)}' &&
        for cert in "${CACERTS_SRC}"/cert*.crt; do
            #    name_prefix=$(echo "${cert%.*}")
            name_prefix="${cert%.*}"
            new_name="${name_prefix}".$(openssl x509 -noout -subject -in "$cert" | sed -n 's/\s//g; s/^.*CN=\(.*\)$/\1/; s/[ ,.*]/_/g; s/__/_/g; s/^_//g;p').pem
            #    mv $cert $CACERTS_SRC/$new_name
            mv "$cert" "$new_name"
        done

}

function import_jdk_cert() {
    KEYSTORE=$1
    rc=0

    writeToLog --- Adding certs to keystore at ["$KEYSTORE"]

    if "$KEYTOOL" -list -keystore "$KEYSTORE" -storepass "${KEYSTORE_PASS}" -alias "$ALIAS" >/dev/null; then
        writeToLog "Key of $HOST already found, removing old one..."
        if "$KEYTOOL" -delete -alias "$ALIAS" -keystore "$KEYSTORE" -storepass "${KEYSTORE_PASS}" >"$TMP_OUT"; then
            :
        else
            writeToLog "ERROR: Unable to remove the existing certificate for $ALIAS ($?)"
            cat "$TMP_OUT"
            exit 1
        fi
    fi
    {
        writeToLog "importing pem"
        "${KEYTOOL}" -import -trustcacerts -noprompt -keystore "${KEYSTORE}" -storepass "${KEYSTORE_PASS}" -alias "${ALIAS}" -file "${CACERTS_SRC}"/"${ALIAS}".pem >"$TMP_OUT"
    } || { # catch
        writeToLog "*** failed to import pem - so lets try to import the crt instead..."
        "${KEYTOOL}" -import -trustcacerts -noprompt -keystore "${KEYSTORE}" -storepass "${KEYSTORE_PASS}" -alias "${ALIAS}" -file "${CACERTS_SRC}"/"${ALIAS}".pem >"$TMP_OUT" && "${KEYTOOL}" -import -trustcacerts -noprompt -keystore "${KEYSTORE}" -storepass "${KEYSTORE_PASS}" -alias "${ALIAS}" -file "${CACERTS_SRC}"/"${ALIAS}".crt >"$TMP_OUT"
        rc="$?"
    }
    if [ "${rc}" -ne 0 ]; then
        :
    else
        writeToLog "ERROR: Unable to import the certificate for $ALIAS ($rc)"
        cat "$TMP_OUT"
        exit 1
    fi
}

main() {

    writeToLog "Running for HOST=[$HOST] PORT=[$PORT] KEYSTORE_PASS=[$KEYSTORE_PASS]..."

    writeToLog "Get default java JDK cacert location"
    #JDK_KEYSTORE=$CERT_DIR/cacerts
    JDK_KEYSTORE=$(get_java_keystore)

    if [ ! -e "$JDK_KEYSTORE" ]; then
        writeToLog "JDK_KEYSTORE [$JDK_KEYSTORE] not found!"
        exit 1
    else
        writeToLog "JDK_KEYSTORE found at [$JDK_KEYSTORE]"
    fi

    writeToLog "Get host cert"
    get_host_cert "${HOST}" "${PORT}"

    ### Now build list of cacert targets to update
    writeToLog "updating JDK certs at [$JDK_KEYSTORE]..."
    import_jdk_cert "$JDK_KEYSTORE"

    # FYI: the default keystore is located in ~/.keystore
    DEFAULT_KEYSTORE="${HOME}/.keystore"
    if [ -f "$DEFAULT_KEYSTORE" ]; then
        writeToLog "updating default certs at [$DEFAULT_KEYSTORE]..."
        import_jdk_cert "$DEFAULT_KEYSTORE"
    fi

    writeToLog "Adding cert to the system keychain.."
    shopt -s nullglob
    files=( "${CACERTS_SRC}"/cert*.pem )
    shopt -u nullglob

    if (( ${#files[@]} > 0 )); then
        ROOT_CERT=$(printf '%s\n' "${files[@]}" | sort -nr | head -1)
    else
        ROOT_CERT=""
    fi

    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo "Add the site root cert to the current user's trust cert chain ==> [${ROOT_CERT}]"
        sudo security add-trusted-cert -d -r trustRoot -k "${HOME}/Library/Keychains/login.keychain" "${ROOT_CERT}"
    elif [[ "$OSTYPE" == "cygwin" || "$OSTYPE" == "msys" ]]; then
        ## ref: https://docs.microsoft.com/en-us/troubleshoot/windows-server/identity/valid-root-ca-certificates-untrusted
        certutil -addstore root "${ROOT_CERT}"
    fi

    writeToLog "**** Finished ****"
}

main
