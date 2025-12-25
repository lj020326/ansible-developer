#!/usr/bin/env bash
#
# Robust Clean Sync: Fetch fresh public, append Keychain (no dedupe to avoid mangling).
# Usage: sudo ./sync_python_certs_fixed_v5.sh
# Requires: sudo for Keychain export.

set -e

log_info() { echo "[INFO] $(date '+%Y-%m-%d %H:%M:%S'): $1"; }
log_error() { echo "[ERROR] $(date '+%Y-%m-%d %H:%M:%S'): $1" >&2; }

if [[ "$(uname)" != "Darwin" ]]; then log_error "macOS only."; exit 1; fi

TIMESTAMP=$(date +%s)
TEMP_PUBLIC="/tmp/public_roots.pem"
TEMP_TRUSTED="/tmp/trusted_certs.pem"
TEMP_COMBINED="/tmp/combined_ca.pem"

OPENSSL_CAFILE=$(python3 -c 'import ssl; print(ssl.get_default_verify_paths().openssl_cafile)' 2>/dev/null || echo "")
CERTIFI_CAFILE=$(python3 -m certifi 2>/dev/null || echo "")

log_info "Paths: OpenSSL=${OPENSSL_CAFILE}, certifi=${CERTIFI_CAFILE}"

# Step 1: Fetch fresh public roots
log_info "Fetching fresh public roots from curl.se..."
curl -s https://curl.se/ca/cacert.pem > "$TEMP_PUBLIC"
cert_count=$(grep -c '^-----BEGIN CERTIFICATE-----' "$TEMP_PUBLIC" || echo "0")
log_info "Fetched public roots: $cert_count certs."

if [[ $cert_count -lt 100 ]]; then
  log_error "Fetched too few public certs ($cert_count)—network issue?"
  exit 1
fi

# Step 2: Export trusted certs from System Keychain
log_info "Exporting trusted certs from Keychain..."
sudo security export -k /Library/Keychains/System.keychain -t certs -f pemseq -o "$TEMP_TRUSTED"
if [[ ! -s "$TEMP_TRUSTED" ]]; then
  log_error "Export failed—check sudo/Keychain access."
  exit 1
fi
trusted_count=$(grep -c '^-----BEGIN CERTIFICATE-----' "$TEMP_TRUSTED" || echo "0")
log_info "Exported Keychain trusted certs: $trusted_count certs."

# Step 3: Combine (simple cat; duplicates harmless for OpenSSL)
log_info "Combining (no dedupe)..."
cat "$TEMP_PUBLIC" "$TEMP_TRUSTED" > "$TEMP_COMBINED"
total_count=$(grep -c '^-----BEGIN CERTIFICATE-----' "$TEMP_COMBINED" || echo "0")
log_info "Combined total certs: $total_count."

if [[ $total_count -lt 100 ]]; then
  log_error "Too few total certs ($total_count)—check exports."
  exit 1
fi

# Step 4: Backup & Update
log_info "Updating bundles..."
for BUNDLE in "$OPENSSL_CAFILE" "$CERTIFI_CAFILE"; do
  if [[ -n "$BUNDLE" ]]; then
    cp -p "$BUNDLE" "${BUNDLE}.bak.${TIMESTAMP}" 2>/dev/null || true
    cp "$TEMP_COMBINED" "$BUNDLE"
    log_info "Updated $BUNDLE (backup: ${BUNDLE}.bak.${TIMESTAMP})."
  fi
done

# Step 5: Validation
log_info "Validating bundle..."
if openssl crl2pkcs7 -nocrl -certfile "$OPENSSL_CAFILE" >/dev/null 2>&1; then
  log_info "Bundle parses OK with OpenSSL."
else
  log_error "Bundle parse failed—check for malformed PEM."
  exit 1
fi

# Cleanup
rm -f "$TEMP_PUBLIC" "$TEMP_TRUSTED" "$TEMP_COMBINED"

log_info "Sync complete! Run: pyenv rehash && hash -r"
log_info "Test Galaxy: python3 -c \"import urllib.request; print(urllib.request.urlopen('https://galaxy.ansible.com/api/', timeout=5).getcode())\"  # Expect 200"
