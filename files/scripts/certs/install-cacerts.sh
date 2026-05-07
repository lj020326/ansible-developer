#!/usr/bin/env bash

# ==============================================================================
# Script: install-cacerts.sh
# Version: 2026.4.17-final-optimized
# Description: Deduplicates Roots by fingerprint merging to minimize macOS prompts.
# ==============================================================================

VERSION="2026.4.17-optimized"
CONFIG_FILE="$HOME/.install-cacerts"
STAGING_DIR="/tmp/cacerts_staging"
UNIQUE_DIR="$STAGING_DIR/unique_roots"

# Default configuration format: host[:port]|jdk|system|docker|python
SITE_LIST_DEFAULT=(
    "repo.maven.apache.org|1|1|0|1"
    "repo.jenkins-ci.org|1|1|0|1"
)

# Global Toggle Overrides
INSTALL_JDK_CACERTS=1
INSTALL_SYSTEM_CACERTS=1
INSTALL_DOCKER_CACERTS=0
INSTALL_PYTHON_CACERTS=1
DEBUG=false

# ------------------------------------------------------------------------------
# Logging & Utilities
# ------------------------------------------------------------------------------
log_info()  { echo -e "\033[0;32m[INFO ]:\033[0m ==> $1"; }
log_warn()  { echo -e "\033[0;33m[WARN ]:\033[0m ==> $1"; }
log_error() { echo -e "\033[0;31m[ERROR]:\033[0m ==> $1" >&2; }
log_debug() { [[ "$DEBUG" == "true" ]] && echo -e "[DEBUG]: ==> $1"; }

usage() {
    cat <<EOF
Usage: sudo ./$SCRIPT_NAME [options] [host1:port host2:port ...]

Pipeline: Collect (Root Only) -> Deduplicate (Fingerprint) -> Commit -> Verify

Options:
  -c FILE   Path to config file (Default: $CONFIG_FILE)
  -d        Enable Docker trust store installation
  -v        Show version and exit
  -x        Enable debug logging
  -h        Show help

Config File Format ($CONFIG_FILE):
  The file should be pipe-delimited (|). Comments (#) are allowed.
  Format: host[:port]|jdk_flag|system_flag|docker_flag|python_flag

Example Config (~/.install-cacerts):
  # Internal services - trust in everything
  pfsense.johnson.int|1|1|0|1

  # Private Docker Registry - requires docker flag
  media.johnson.int:5000|1|1|1|1

EOF
    exit "${1:-0}"
}

# ------------------------------------------------------------------------------
# Discovery & OS Helpers
# ------------------------------------------------------------------------------
function find_java_cacerts() {
    local path=""
    if [ -n "$JAVA_HOME" ] && [ -f "$JAVA_HOME/lib/security/cacerts" ]; then
        path="$JAVA_HOME/lib/security/cacerts"
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        path=$(/usr/libexec/java_home 2>/dev/null)/lib/security/cacerts
    else
        path=$(readlink -f "$(which java)" | sed "s:bin/java::")lib/security/cacerts
    fi
    echo "$path"
}

function get_site_config() {
    if [ $# -gt 0 ]; then
        for s in "$@"; do echo "$s|1|1|0|1"; done
    elif [ -f "$CONFIG_FILE" ]; then
        grep -v '^#' "$CONFIG_FILE" | grep '[^\s]' | sed 's/\s//g'
    else
        for s in "${SITE_LIST_DEFAULT[@]}"; do echo "$s"; done
    fi
}

# ------------------------------------------------------------------------------
# STAGE 1: COLLECT (Enhanced for Self-Signed & Bit-Merging)
# ------------------------------------------------------------------------------
function collect_all_certs() {
    local config_entries=("$@")
    rm -rf "$STAGING_DIR" && mkdir -p "$UNIQUE_DIR"
    log_info "STAGE 1: Collecting and Deduplicating Root CAs..."

    for entry in "${config_entries[@]}"; do
        IFS='|' read -r site jdk sys doc py <<< "$entry"
        local host="${site%%:*}"
        local port="${site##*:}"
        [[ "$host" == "$port" ]] && port="443"

        local raw_file="$STAGING_DIR/${host}_${port}_raw.txt"

        # Fetch the certificate chain from the server
        if ! timeout 5 openssl s_client -showcerts -connect "${host}:${port}" -servername "${host}" </dev/null > "$raw_file" 2>/dev/null; then
            log_warn "Unreachable: $host:$port"
            continue
        fi

        local root_tmp="$STAGING_DIR/${host}_${port}_root.pem"

        # Count certificates in the response to identify self-signed/single-cert setups
        local cert_count=$(grep -c "BEGIN CERTIFICATE" "$raw_file")

        if [ "$cert_count" -eq 1 ]; then
            # ENHANCEMENT: If only one cert is present, it is either self-signed
            # or the only anchor provided. We must trust it directly.
            openssl x509 -in "$raw_file" -out "$root_tmp" 2>/dev/null
        elif [ "$cert_count" -gt 1 ]; then
            # Extract the LAST certificate in the chain (The Root/Anchor)
            awk '
                /-----BEGIN CERTIFICATE-----/ { i=0; delete lines; }
                { lines[i++] = $0 }
                /-----END CERTIFICATE-----/ {
                    for (j=0; j<i; j++) cert_lines[j] = lines[j];
                    cert_len = i;
                }
                END { for (k=0; k<cert_len; k++) print cert_lines[k] }
            ' "$raw_file" > "$root_tmp"
        fi

        if [ -s "$root_tmp" ]; then
            # Generate SHA1 fingerprint for deduplication and filename
            local fp=$(openssl x509 -noout -fingerprint -sha1 -in "$root_tmp" | cut -d'=' -f2 | sed 's/://g')
            local subject=$(openssl x509 -noout -subject -in "$root_tmp")
            local final_name="$UNIQUE_DIR/${fp}.pem"
            local flag_file="$UNIQUE_DIR/${fp}.flags"

            # Save the unique certificate file
            [ ! -f "$final_name" ] && cp "$root_tmp" "$final_name"

            # Bit-merge flags (Logical OR) to ensure we do not duplicate prompts for the same cert
            local existing_jdk=0; local existing_sys=0; local existing_doc=0; local existing_py=0
            if [ -f "$flag_file" ]; then
                IFS='|' read -r existing_jdk existing_sys existing_doc existing_py < "$flag_file"
            fi

            # Update flag file with merged values
            echo "$((jdk | existing_jdk))|$((sys | existing_sys))|$((doc | existing_doc))|$((py | existing_py))" > "$flag_file"

            log_debug "Staged certificate for $host: subject=[$subject] FP=[${fp:0:12}]"
        fi
    done
}

# ------------------------------------------------------------------------------
# STAGE 2: COMMIT (Deduplicated execution + Updated with Physical JDK Keystore Import)
# ------------------------------------------------------------------------------
function commit_certs() {
    log_info "STAGE 2: Committing $(ls "$UNIQUE_DIR"/*.pem 2>/dev/null | wc -l | xargs) unique roots to trust stores..."

    for cert_file in "$UNIQUE_DIR"/*.pem; do
        [[ ! -e "$cert_file" ]] && continue

        local fp_ext=$(basename "$cert_file" .pem)
        local fp_short="${fp_ext:0:12}"
        local flag_file="$UNIQUE_DIR/${fp_ext}.flags"
        local subject=$(openssl x509 -noout -subject -in "$cert_file")

        # Read the merged flags
        IFS='|' read -r jdk sys doc py < "$flag_file"

        log_info "Installing: subject=[$subject] FP=[$fp_short]"

        # 1. SYSTEM STORE (macOS Keychain)
        if [[ "$sys" -eq 1 && "$INSTALL_SYSTEM_CACERTS" -eq 1 ]]; then
            if [[ "$OSTYPE" == "darwin"* ]]; then
                # Use -d to add to Admin trust settings (requires sudo)
                # Adding specific policies (-p) to resolve "parameter not valid" errors
                sudo security add-trusted-cert -d -r trustAsRoot -p ssl -p basic -k /Library/Keychains/System.keychain "$cert_file"
                #sudo security add-trusted-cert -d -r trustAsRoot -k /Library/Keychains/System.keychain "$cert_file"
                #sudo security add-trusted-cert -d -r trustRoot -k "${HOME}/Library/Keychains/login.keychain" ${cert_file}
            else
                # Linux System Trust (Ubuntu/Debian/RHEL)
                cp "$cert_file" "$CACERT_TRUST_DIR/${fp_ext}.crt"
            fi
        fi

        # 2. JAVA JDK STORE (Physical Import for Maven/Jenkins reliability)
        if [[ "$jdk" -eq 1 && "$INSTALL_JDK_CACERTS" -eq 1 ]]; then
            # Determine cacerts path based on JAVA_HOME
            local java_cacerts=""
            if [ -n "$JAVA_HOME" ]; then
                if [ -f "$JAVA_HOME/lib/security/cacerts" ]; then
                    java_cacerts="$JAVA_HOME/lib/security/cacerts"
                elif [ -f "$JAVA_HOME/jre/lib/security/cacerts" ]; then
                    java_cacerts="$JAVA_HOME/jre/lib/security/cacerts"
                fi
            fi

            if [ -n "$java_cacerts" ]; then
                log_debug "Adding to Java KeyStore: $java_cacerts"
                # Remove old alias if present to prevent "already exists" errors
                keytool -delete -alias "$fp_ext" -keystore "$java_cacerts" -storepass changeit >/dev/null 2>&1
                # Import the new root
                keytool -importcert -noprompt \
                    -keystore "$java_cacerts" \
                    -storepass changeit \
                    -alias "$fp_ext" \
                    -file "$cert_file" >/dev/null 2>&1
            else
                log_warn "JDK flag set but JAVA_HOME not found. Skipping JDK import for $fp_short."
            fi
        fi

        # 3. PYTHON STORE (certifi)
        if [[ "$py" -eq 1 && "$INSTALL_PYTHON_CACERTS" -eq 1 ]]; then
            local certifi_path=$(python3 -m certifi 2>/dev/null)
            if [ -f "$certifi_path" ]; then
                # Append if not already present
                if ! grep -q "$fp_ext" "$certifi_path"; then
                    echo -e "\n# Fingerprint: $fp_ext" >> "$certifi_path"
                    cat "$cert_file" >> "$certifi_path"
                fi
            fi
        fi
    done

    # Run Linux trust updates once
    [[ "$OSTYPE" == "linux"* ]] && command -v update-ca-trust >/dev/null && sudo update-ca-trust extract
    [[ "$OSTYPE" == "linux"* ]] && command -v update-ca-certificates >/dev/null && sudo update-ca-certificates
}

# ------------------------------------------------------------------------------
# STAGE 3: VERIFY
# ------------------------------------------------------------------------------
function verify_trust() {
    log_info "STAGE 3: Verifying full site list..."
    local config_entries=("$@")
    for entry in "${config_entries[@]}"; do
        IFS='|' read -r site rest <<< "$entry"
        if curl -Is --connect-timeout 2 "https://$site" > /dev/null 2>&1; then
            echo -e "  \033[0;32m[PASS]\033[0m $site"
        else
            echo -e "  \033[0;31m[FAIL]\033[0m $site"
        fi
    done
}

# ------------------------------------------------------------------------------
# Main
# ------------------------------------------------------------------------------
main() {
    while getopts "c:dvxh" opt; do
        case "${opt}" in
            c) CONFIG_FILE="${OPTARG}" ;;
            d) INSTALL_DOCKER_CACERTS=1 ;;
            v) echo "$VERSION" && exit ;;
            x) DEBUG=true ;;
            h) usage 0 ;;
            *) usage 1 ;;
        esac
    done
    shift $((OPTIND-1))

    [[ "$OSTYPE" != "msys" && "$EUID" -ne 0 ]] && { log_error "Run with sudo"; exit 1; }

    local __CONFIG_LIST
    IFS=$'\n' read -d '' -r -a __CONFIG_LIST <<< "$(get_site_config "$@")"

    collect_all_certs "${__CONFIG_LIST[@]}"
    commit_certs "${__CONFIG_LIST[@]}"
    verify_trust "${__CONFIG_LIST[@]}"
    log_info "Batch installation complete."
}

main "$@"
