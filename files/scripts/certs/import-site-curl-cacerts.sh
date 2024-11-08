#!/usr/bin/env bash


function get_site_cacerts() {
    local host=$1
    local port=$2
    local certs_dir=$3

    cd ${certs_dir}

    ## ref: https://unix.stackexchange.com/questions/368123/how-to-extract-the-root-ca-and-subordinate-ca-from-a-certificate-chain-in-linux
    openssl s_client -showcerts -verify 5 -connect ${ENDPOINT} < /dev/null \
        | awk '/BEGIN/,/END/{ if(/BEGIN/){a++}; out="cert"a".crt"; print >out}' && \
        for cert in *.crt;
        do
            newname=$(echo "${cert}" | cut -f 1 -d '.')-$(openssl x509 -noout -subject -in ${cert} | sed -n 's/, /,/g; s/ = /=/g; s/^.*CN=\(.*\)$/\1/; s/[ ,.*]/_/g; s/__/_/g; s/^_//g;p').pem
            mv $cert $newname;
        done

}


function import_curl_cacert() {

    local alias=$1
    local curl_capath=$2
    local cacerts_src=$3

    echo "--- Adding certs to keystore at [${curl_capath}]"

    ## ref: https://stackoverflow.com/questions/24675167/ca-certificates-mac-os-x
    ## ref: https://discourse.brew.sh/t/openssl-and-update-ca-certificates/3260
    ## ref: https://curl.haxx.se/docs/sslcerts.html
    mkdir -p ${curl_capath}/certs
    cp ${cacerts_src}/*.pem ${curl_capath}/certs/
    /usr/local/opt/openssl/bin/c_rehash

    if [ $? ]
    then
        echo "SUCCESS: imported certificates for ${alias} to ${curl_capath} ($?)"
    else
        echo "ERROR: Unable to import the certificates for ${alias} to ${curl_capath} ($?)"
        exit 1
    fi

}


#DATE=`date +&%%m%d%H%M%S`
DATE=`date +%Y%m%d`

ENDPOINT="cd.dettonville.int:443"
IFS=':' read -r -a array <<< "${ENDPOINT}"
host=${array[0]}
port=${array[1]}

alias="${host}_${port}"
curl_capath="/usr/local/etc/openssl"

certs_dir=${HOME}/.certs/${alias}/${DATE}

if [ ! -d ${certs_dir} ]; then
    mkdir -p ${certs_dir}
fi

get_site_cacerts ${host} ${port} ${certs_dir}

import_curl_cacert ${alias} ${curl_capath} ${certs_dir}

