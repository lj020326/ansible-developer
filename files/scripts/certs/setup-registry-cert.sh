#!/usr/bin/env bash

SITE_LIST=("media.johnson.int:5000")

# ref: https://stackoverflow.com/questions/50768317/docker-pull-certificate-signed-by-unknown-authority
# ref: https://docs.docker.com/desktop/faqs/macfaqs/#how-do-i-add-tls-certificates
# ref: https://stackoverflow.com/questions/50768317/docker-pull-certificate-signed-by-unknown-authority
install-cacerts.sh -d "$@" ${SITE_LIST[@]}
