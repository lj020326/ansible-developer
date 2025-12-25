#!/usr/bin/env bash
#
# install-registry-cert.sh
# Automates the installation of a private Docker registry's Root CA certificate
# into the Docker daemon's trust store on macOS.
#
# Usage: sudo ./install-registry-cert.sh media.johnson.int:5000

# --- Configuration & Utility Functions ---

# Basic logging utilities
log_info() {
  printf "\033[1;34m[INFO]\033[0m %s\n" "$1" >&2
}

log_error() {
  printf "\033[1;31m[ERROR]\033[0m %s\n" "$1" >&2
  exit 1
}

log_success() {
  printf "\033[1;32m[SUCCESS]\033[0m %s\n" "$1" >&2
}

# Check for required commands
check_prerequisites() {
  command -v openssl >/dev/null 2>&1 || log_error "The 'openssl' command is required but not found."
  command -v awk >/dev/null 2>&1 || log_error "The 'awk' command is required but not found."
  command -v date >/dev/null 2>&1 || log_error "The 'date' command is required but not found."
}

# --- Core Logic Functions ---

# 1. Check for root privileges and OS
preliminary_checks() {
  if [[ "$(uname -s)" != "Darwin" ]]; then
    log_info "WARNING: This script is designed for macOS (Darwin). Current OS: $(uname -s). Proceeding, but results may vary."
  fi

  if [ "$EUID" -ne 0 ]; then
    log_error "This script MUST be run with root privileges (using 'sudo')."
  fi
}

# 2. Fetch the certificate chain and isolate the root CA
fetch_root_ca() {
  local HOST="$1"
  local PORT="$2"
  local TEMP_DIR="$3"
  local ENDPOINT="${HOST}:${PORT}"

  log_info "Attempting to fetch certificate chain for ${ENDPOINT}..."

  # 1. Fetch the entire chain in PEM format (kept for inspection purposes)
  openssl s_client -showcerts -verify 5 -connect "${HOST}:${PORT}" -servername "${HOST}" </dev/null 2>/dev/null | \
    openssl x509 -outform PEM > "${TEMP_DIR}/full_chain.pem"

  if [[ ! -s "${TEMP_DIR}/full_chain.pem" ]]; then
    log_error "Failed to fetch certificate chain from ${ENDPOINT}. Check hostname, port, and network connectivity."
  fi

  # 2. Split the chain into cert1.crt, cert2.crt, etc.
  # This relies on the BEGIN/END CERTIFICATE markers.
  openssl s_client -showcerts -verify 5 -connect "${HOST}:${PORT}" -servername "${HOST}" </dev/null 2>/dev/null \
    | awk -v certdir="${TEMP_DIR}" '/BEGIN/,/END/{ if(/BEGIN/){a++}; out="cert"a".crt"; print >(certdir "/" out)}'

  # --- FIX: Select the Root CA (The highest-numbered certificate in the chain) ---
  local ROOT_CA_SRC_PATH
  # Find all cert*.crt files, sort them by name, and take the LAST one (e.g., cert3.crt)
  # This reliably selects the Root/Signing CA, assuming the server sends the chain correctly.
  ROOT_CA_SRC_PATH=$(find "${TEMP_DIR}" -name "cert*.crt" | sort | tail -n 1)

  if [[ ! -f "${ROOT_CA_SRC_PATH}" ]]; then
    log_error "Could not isolate the Root CA certificate from the fetched chain. Found 0 certificates."
  fi

  # Optional sanity check: print the subject/issuer of the selected cert
  local SUBJECT=$(openssl x509 -in "${ROOT_CA_SRC_PATH}" -noout -subject | sed 's/subject=//')
  local ISSUER=$(openssl x509 -in "${ROOT_CA_SRC_PATH}" -noout -issuer | sed 's/issuer=//')
  log_info "Certificate chain fetched. Root/Signing CA selected from: ${ROOT_CA_SRC_PATH}"
  log_info "  Subject: ${SUBJECT}"
  log_info "  Issuer: ${ISSUER}"

  # Rename the root CA file to 'ca.crt' as expected by the Docker daemon
  ROOT_CA_FINAL_PATH="${TEMP_DIR}/ca.crt"
  cp "${ROOT_CA_SRC_PATH}" "${ROOT_CA_FINAL_PATH}"

  log_success "Root CA certificate successfully extracted and staged."
  echo "${ROOT_CA_FINAL_PATH}" # Return the final path
}

# 3. Install the root CA certificate to the Docker trust location
install_docker_cert() {
  local ENDPOINT="$1"
  local ROOT_CA_PATH="$2"

  # The required installation directory for the Docker daemon on macOS/Linux
  local DOCKER_CERT_DIR="/etc/docker/certs.d/${ENDPOINT}"
  local DOCKER_CA_FILE="${DOCKER_CERT_DIR}/ca.crt"
  local TIMESTAMP=$(date +%Y%m%d%H%M%S)

  log_info "Creating Docker certificate directory: ${DOCKER_CERT_DIR}"
  mkdir -p "${DOCKER_CERT_DIR}"

  # --- Backup Existing Certificate ---
  if [ -f "${DOCKER_CA_FILE}" ] || [ -L "${DOCKER_CA_FILE}" ]; then # Check for file OR symlink
    local BACKUP_FILE="${DOCKER_CA_FILE}.bak.${TIMESTAMP}"
    log_info "Existing certificate found. Creating backup: ${BACKUP_FILE}"
    # Use -fP to force overwrite and prevent following symbolic links
    cp -fP "${DOCKER_CA_FILE}" "${BACKUP_FILE}"
    if [ $? -ne 0 ]; then
      log_error "Failed to create backup of existing certificate."
    fi
  else
    log_info "No existing certificate found to back up."
  fi
  # -----------------------------------

  log_info "Copying new Root CA to Docker trust store..."
  # Use -fP to force overwrite and ensure we replace any symbolic links with a file.
  cp -fP "${ROOT_CA_PATH}" "${DOCKER_CA_FILE}"

  if [ $? -ne 0 ]; then
    log_error "Failed to copy certificate to ${DOCKER_CA_FILE}. Check permissions."
  fi

  log_success "Certificate successfully installed to: ${DOCKER_CA_FILE}"
}

# --- Main Execution ---

main() {
  preliminary_checks
  check_prerequisites

  if [ -z "$1" ]; then
    log_error "Usage: sudo $0 <host:port> (e.g., media.johnson.int:5000)"
  fi

  local ENDPOINT="$1"
  IFS=':' read -r HOST PORT <<< "${ENDPOINT}"
  PORT="${PORT:-443}" # Default to 443 if port is not specified

  log_info "Starting certificate installation for Docker registry: ${HOST}:${PORT}"

  # Fixed mktemp usage for macOS/BSD compatibility
  TEMP_DIR=$(mktemp -d -t docker-cert-install-XXX)
  trap "rm -rf '$TEMP_DIR'" EXIT

  # Step 1: Fetch and locate the Root CA
  ROOT_CA_FILE=$(fetch_root_ca "${HOST}" "${PORT}" "${TEMP_DIR}")

  # Step 2: Install the certificate (with backup)
  install_docker_cert "${ENDPOINT}" "${ROOT_CA_FILE}"

  # Final Step: Instruction to the user
  printf "\n"
  printf "\033[1;33m*** IMPORTANT FINAL STEP ***\033[0m\n"
  printf "The certificate has been installed, but the Docker daemon must be restarted.\n"
  printf "Please restart Docker Desktop (Click the Docker icon in the menu bar -> Quit/Restart) or run the appropriate daemon restart command for your OS.\n"
  printf "The 'docker login' command should now succeed.\n"
  printf "\n"
}

main "$@"
