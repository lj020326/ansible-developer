#!/usr/bin/env bash

TARGET_HOST=${1:-stepca.admin.johnson.int}
TARGET_PORT=${2:-443}
FETCH_CERT_DIR=${3:-"${HOME}/.certs"}

#ENDPOINT_NAME="${TARGET_HOST}_${TARGET_PORT}"
ENDPOINT_NAME="ca-root"
ENDPOINT="${TARGET_HOST}:${TARGET_PORT}"

STEPCA_CAROOT_CERT="ca-root.crt"

STEPCA_HOST_URL="https://${TARGET_HOST}/"

echo "Ensure FETCH_CERT_DIR directory exists at ${FETCH_CERT_DIR}"
mkdir -p "${FETCH_CERT_DIR}"

curl -k -s https://${TARGET_HOST}/1.0/roots | jq -r '.crts[0]' \
  | sed -r '/^\s*$/d' > ${FETCH_CERT_DIR}/stepca_fingerprint_encoded.txt

STEPCA_FINGERPRINT_DECODED=$(step certificate fingerprint ${FETCH_CERT_DIR}/stepca_fingerprint_encoded.txt)

echo "STEPCA_FINGERPRINT_DECODED => ${STEPCA_FINGERPRINT_DECODED}"
echo "${STEPCA_FINGERPRINT_DECODED}" > ${FETCH_CERT_DIR}/stepca_fingerprint_decoded.txt

echo "Bootstrap step cli configuration"
step ca bootstrap --force --ca-url "${STEPCA_HOST_URL}" --fingerprint "${STEPCA_FINGERPRINT_DECODED}"

echo "Fetch root cert/key from stepca to ${FETCH_CERT_DIR}/${STEPCA_CAROOT_CERT}"
step ca root "${FETCH_CERT_DIR}/${STEPCA_CAROOT_CERT}"

### ref: https://stackoverflow.com/questions/9450120/openssl-hangs-and-does-not-exit
#echo QUIT | openssl s_client -showcerts -servername ${TARGET_HOST} -connect ${ENDPOINT} | \
#  openssl x509 -outform PEM > ${FETCH_CERT_DIR}/${ENDPOINT_NAME}.crt
