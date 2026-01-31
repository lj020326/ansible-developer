#!/bin/bash

# Usage: ./add_root_certs.sh "example.com,google.com:8443,another.site"
# Fetches root/CA certificates from the SSL chain for each site,
# deduplicates them, and adds to macOS System Keychain and Firefox trust store.
# Requires: openssl (built-in), brew install nss for Firefox support.
# Run with one sudo prompt for system keychain.

set -euo pipefail

if [ $# -eq 0 ]; then
  echo "Usage: $0 \"site1.com,site2.com:port,site3.com\""
  exit 1
fi

SITES_LIST="$1"
TEMP_DIR=$(mktemp -d)
declare -A seen_fingerprints
declare -a all_ca_certs=()

# Function to fetch chain and extract CA certs
fetch_ca_certs() {
  local host="$1"
  local port="$2"
  local chain_file="${TEMP_DIR}/chain_${host//./_}.pem"

  echo "" | openssl s_client -connect "${host}:${port}" -servername "${host}" -showcerts 2>/dev/null \
    | sed -ne '/-----BEGIN CERTIFICATE-----/,/-----END CERTIFICATE-----/p' > "${chain_file}"

  if [ ! -s "${chain_file}" ]; then
    echo "Warning: No certificate chain fetched for ${host}:${port}"
    return
  fi

  # Split chain into individual cert files using awk (robust PEM splitter)
  awk -v certdir="$TEMP_DIR" '
    BEGIN { certnum = 0; printing = 0 }
    /-----BEGIN CERTIFICATE-----/ {
      certnum++
      filename = certdir "/cert" certnum ".pem"
      printing = 1
      print > filename
      next
    }
    /-----END CERTIFICATE-----/ {
      if (printing) {
        print > filename
        close(filename)
        printing = 0
      }
      next
    }
    {
      if (printing) print > filename
    }
  ' "$chain_file"

  # Process each extracted cert
  for cert_file in "$TEMP_DIR"/cert*.pem; do
    if [ -f "$cert_file" ]; then
      process_cert "$cert_file"
    fi
  done

  rm -f "${chain_file}"
}

# Process a single cert: check if CA, dedup, add if new
process_cert() {
  local cert_file="$1"
  if ! openssl x509 -in "$cert_file" -noout -text 2>/dev/null | grep -q "CA:TRUE"; then
    rm -f "$cert_file"
    return
  fi

  local fingerprint=$(openssl x509 -in "$cert_file" -noout -fingerprint -sha256 2>/dev/null | cut -d= -f2 | tr -d ': ')
  if [ -n "$fingerprint" ] && [ -z "${seen_fingerprints[$fingerprint]:-}" ]; then
    seen_fingerprints[$fingerprint]=1
    all_ca_certs+=("$cert_file")
    echo "Added new CA cert: $(openssl x509 -in "$cert_file" -noout -subject -nameopt oneline | cut -d= -f2-)"
  else
    rm -f "$cert_file"
  fi
}

# Parse sites
IFS=',' read -ra SITES <<< "$SITES_LIST"
for site in "${SITES[@]}"; do
  site=$(echo "$site" | xargs)  # Trim whitespace
  IFS=':' read -r host port <<< "$site"
  if [ -z "$port" ]; then
    port=443
  fi
  echo "Fetching certs for ${host}:${port}..."
  fetch_ca_certs "$host" "$port"
done

if [ ${#all_ca_certs[@]} -eq 0 ]; then
  echo "No CA certificates found to add."
  rm -rf "$TEMP_DIR"
  exit 0
fi

echo "Found ${#all_ca_certs[@]} unique CA certificates."

# Add to System Keychain (requires sudo, one prompt)
echo "Creating temporary script for system keychain addition..."
add_script="${TEMP_DIR}/add_to_system.sh"
cat > "$add_script" << EOF
#!/bin/bash
set -e
EOF
for cert in "${all_ca_certs[@]}"; do
  echo "security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain '$cert'" >> "$add_script"
done
chmod +x "$add_script"

echo "Adding to System Keychain (sudo required)..."
sudo "$add_script"
echo "Added to System Keychain."

# Add to Firefox (no sudo)
if ! command -v certutil &> /dev/null; then
  echo "certutil not found. Install with: brew install nss"
  echo "Skipping Firefox."
else
  PROFILES_DIR="$HOME/Library/Application Support/Firefox/Profiles"
  if [ ! -d "$PROFILES_DIR" ]; then
    echo "Firefox profiles directory not found. Skipping Firefox."
  else
    PROFILE=$(ls "$PROFILES_DIR" 2>/dev/null | grep -E '\.(default-release|default)$' | head -1)
    if [ -z "$PROFILE" ]; then
      echo "No default Firefox profile found. Skipping Firefox."
    else
      FULL_PROFILE="$PROFILES_DIR/$PROFILE"
      echo "Adding to Firefox profile: $PROFILE"
      for cert in "${all_ca_certs[@]}"; do
        CN=$(openssl x509 -in "$cert" -noout -subject 2>/dev/null | sed -n 's/.*CN[[:space:]]*=[[:space:]]*\([^/]*\).*/\1/p' | sed 's/ /_/g')
        if [ -z "$CN" ]; then
          CN="UnknownCA_$(basename "$cert")"
        fi
        # Check if already exists
        if certutil -L -d "sql:$FULL_PROFILE" -n "$CN" &>/dev/null; then
          echo "CA '$CN' already in Firefox."
        else
          certutil -A -n "$CN" -t "C,," -d "sql:$FULL_PROFILE" -i "$cert"
          echo "Added '$CN' to Firefox."
        fi
      done
    fi
  fi
fi

# Cleanup
rm -rf "$TEMP_DIR"
echo "Done!"
