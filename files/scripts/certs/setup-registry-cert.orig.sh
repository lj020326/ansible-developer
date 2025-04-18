#!/usr/bin/env bash

#############
## ref: https://github.com/moby/moby/issues/39869#issuecomment-967376507
#############
set -e

#DOCKER_REGISTRY_HOST="registry.docker.io:443"
DOCKER_REGISTRY_HOST="media.johnson.int:5000"

DOCKER_REGISTRY_CERT_DIR="/etc/docker/certs.d/${DOCKER_REGISTRY_HOST}"

SCRIPT_DIR="$(dirname "$0")"
#source ${SCRIPT_DIR}/get-curl-ca-opts.sh
#!/usr/bin/env bash

## https://stackoverflow.com/questions/26988262/best-way-to-find-the-os-name-and-version-on-a-unix-linux-platform#26988390
UNAME=$(uname -s | tr "[:upper:]" "[:lower:]")
PLATFORM=""
DISTRO=""

if [[ "$UNAME" != "cygwin" && "$UNAME" != "msys" ]]; then
  if [ "$EUID" -ne 0 ]; then
    echo "Must run this script as root. run 'sudo $SCRIPT_NAME'"
    exit
  fi
fi

CACERT_TRUST_DIR=/etc/pki/ca-trust/extracted
CACERT_TRUST_IMPORT_DIR=/etc/pki/ca-trust/source/anchors
CACERT_BUNDLE=${CACERT_TRUST_DIR}/openssl/ca-bundle.trust.crt
CACERT_TRUST_FORMAT="pem"

## ref: https://askubuntu.com/questions/459402/how-to-know-if-the-running-platform-is-ubuntu-or-centos-with-help-of-a-bash-scri
case "${UNAME}" in
    linux*)
      if type "lsb_release" > /dev/null 2>&1; then
        LINUX_OS_DIST=$(lsb_release -a | tr "[:upper:]" "[:lower:]")
      else
        LINUX_OS_DIST=$(awk -F= '/^NAME/{print $2}' /etc/os-release | tr "[:upper:]" "[:lower:]")
      fi
      PLATFORM=Linux
      case "${LINUX_OS_DIST}" in
        *ubuntu* | *debian*)
          # Debian Family
          #CACERT_TRUST_DIR=/usr/ssl/certs
          CACERT_TRUST_DIR=/etc/ssl/certs
          CACERT_TRUST_IMPORT_DIR=/usr/local/share/ca-certificates
          CACERT_BUNDLE=${CACERT_TRUST_DIR}/ca-certificates.crt
          DISTRO=$(lsb_release -i | cut -d: -f2 | sed s/'^\t'//)
          CACERT_TRUST_COMMAND="update-ca-certificates"
          CACERT_TRUST_FORMAT="crt"
          ;;
        *redhat* | *"red hat"* | *centos* | *fedora* )
          # RedHat Family
          CACERT_TRUST_DIR=/etc/pki/tls/certs
          #CACERT_TRUST_IMPORT_DIR=/etc/pki/ca-trust/extracted/openssl
          #CACERT_BUNDLE=${CACERT_TRUST_DIR}/ca-bundle.trust.crt
          #CACERT_TRUST_DIR=/etc/pki/ca-trust/extracted/pem
          CACERT_TRUST_IMPORT_DIR=/etc/pki/ca-trust/source/anchors
          #CACERT_BUNDLE=${CACERT_TRUST_DIR}/tls-ca-bundle.pem
          CACERT_BUNDLE=${CACERT_TRUST_DIR}/ca-bundle.trust.crt
          DISTRO=$(cat /etc/system-release)
          CACERT_TRUST_COMMAND="update-ca-trust extract"
          CACERT_TRUST_FORMAT="pem"
          ;;
        *)
          # Otherwise, use release info file
          CACERT_TRUST_DIR=/usr/ssl/certs
          CACERT_TRUST_IMPORT_DIR=/etc/pki/ca-trust/source/anchors
          CACERT_BUNDLE=${CACERT_TRUST_DIR}/ca-bundle.crt
          DISTRO=$(ls -d /etc/[A-Za-z]*[_-][rv]e[lr]* | grep -v "lsb" | cut -d'/' -f3 | cut -d'-' -f1 | cut -d'_' -f1)
          CACERT_TRUST_COMMAND="update-ca-certificates"
          CACERT_TRUST_FORMAT="pem"
      esac
      ;;
    darwin*)
      PLATFORM=DARWIN
      CACERT_TRUST_DIR=/etc/ssl
      CACERT_TRUST_IMPORT_DIR=/usr/local/share/ca-certificates
      CACERT_BUNDLE=${CACERT_TRUST_DIR}/cert.pem
      ;;
    cygwin* | mingw64* | mingw32* | msys*)
      PLATFORM=MSYS
      ## https://packages.msys2.org/package/ca-certificates?repo=msys&variant=x86_64
      CACERT_TRUST_DIR=/etc/pki/ca-trust/extracted
      CACERT_TRUST_IMPORT_DIR=/etc/pki/ca-trust/source/anchors
      CACERT_BUNDLE=${CACERT_TRUST_DIR}/openssl/ca-bundle.trust.crt
      ;;
    *)
      PLATFORM="UNKNOWN:${UNAME}"
esac

echo "==> UNAME=${UNAME}"
echo "==> LINUX_OS_DIST=${OS_DIST}"
echo "==> PLATFORM=[${PLATFORM}]"
echo "==> DISTRO=[${DISTRO}]"
echo "==> CACERT_TRUST_DIR=${CACERT_TRUST_DIR}"
echo "==> CACERT_TRUST_IMPORT_DIR=${CACERT_TRUST_IMPORT_DIR}"
echo "==> CACERT_BUNDLE=${CACERT_BUNDLE}"
echo "==> CACERT_TRUST_COMMAND=${CACERT_TRUST_COMMAND}"

CURL_CA_OPTS="--capath ${CACERT_TRUST_DIR} --cacert ${CACERT_BUNDLE}"
echo "==> CURL_CA_OPTS=${CURL_CA_OPTS}"

echo "==> UNAME=${UNAME}: PLATFORM=[${PLATFORM}] DISTRO=[${DISTRO}]"

echo "==> Setup docker registry cert dir at "
mkdir -p "${DOCKER_REGISTRY_CERT_DIR}"

if [[ "$PLATFORM" == "LINUX" ]]; then
  echo "==> Setup symlink for docker registry cert to system ca cert bundle"
  #ln -s /etc/ssl/certs/ca-certificates.crt ${DOCKER_REGISTRY_CERT_DIR}/ca.crt
  ln -s ${CACERT_BUNDLE} ${DOCKER_REGISTRY_CERT_DIR}/ca.crt
fi
if [[ "$UNAME" == "darwin"* ]]; then
  ## ref: https://stackoverflow.com/questions/40684543/how-to-make-python-use-ca-certificates-from-mac-os-truststore
  MACOS_CACERT_EXPORT_COMMAND="sudo security export -t certs -f pemseq -k /Library/Keychains/System.keychain -o ${PYTHON_SSL_CERT_DIR}/systemBundleCA.pem"
  logInfo "${LOG_PREFIX} Running [${MACOS_CACERT_EXPORT_COMMAND}]"
  eval "${MACOS_CACERT_EXPORT_COMMAND}"
fi
