#!/usr/bin/env python3
"""
TLS Certificate & SAN Validation Tool
Connects to an endpoint via TLS, inspects certificate chains, checks expiration,
validates trust chains, and verifies hostnames against Subject Alternative Names (SAN).
"""

import os
import sys
import ssl
import socket
import argparse
import fnmatch
import logging
from datetime import datetime, timezone
from urllib.parse import urlparse
from argparse import RawTextHelpFormatter

# Script metadata matching template structure
__scriptName__ = os.path.basename(sys.argv[0])
__version__ = "2026.10.29"
__updated__ = "29 October 2026"

log = logging.getLogger(__scriptName__)


def setup_logging(loglevel_str="INFO"):
    """Sets up the script logger and applies the requested logging level."""
    loglevel = getattr(logging, loglevel_str.upper(), logging.INFO)
    log.setLevel(loglevel)

    # Avoid duplicate handlers if setup_logging is called multiple times
    if not log.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter("%(levelname)s: %(message)s")
        handler.setFormatter(formatter)
        log.addHandler(handler)
    else:
        log.handlers[0].setLevel(loglevel)


def parse_endpoint(endpoint_str):
    """Parses HOST:PORT, HOST, or https://HOST:PORT strings."""
    if "://" not in endpoint_str:
        endpoint_str = "//" + endpoint_str

    parsed = urlparse(endpoint_str)
    host = parsed.hostname
    port = parsed.port

    if not host:
        raise ValueError(f"Invalid endpoint format: '{endpoint_str}'")

    if not port:
        port = 443 if parsed.scheme == "https" or not parsed.scheme else 443

    return host, port


def get_certificate_details(host, port, timeout=5):
    """Connects to the endpoint via TLS and retrieves the peer certificate dict."""
    log.debug(f"Creating SSL context and loading default system CAs...")
    context = ssl.create_default_context()
    context.load_default_certs()

    # Use CERT_OPTIONAL so Python populates getpeercert() even if the CA trust chain fails
    context.check_hostname = False
    context.verify_mode = ssl.CERT_OPTIONAL

    try:
        log.debug(f"Establishing TCP connection to {host}:{port}...")
        with socket.create_connection((host, port), timeout=timeout) as sock:
            with context.wrap_socket(sock, server_hostname=host) as ssock:
                cert_dict = ssock.getpeercert()

                log.debug("Performing separate strict trust verification check...")
                verify_context = ssl.create_default_context()
                verify_context.load_default_certs()
                verify_error = None
                try:
                    with socket.create_connection(
                        (host, port), timeout=timeout
                    ) as vsock:
                        with verify_context.wrap_socket(
                            vsock, server_hostname=host
                        ) as _:
                            pass
                except ssl.SSLCertVerificationError as ve:
                    verify_error = f"CA/Trust Validation Failed: {ve.verify_message}"
                except Exception as ve:
                    verify_error = f"Validation Error: {str(ve)}"

                return cert_dict, verify_error
    except Exception as e:
        return None, str(e)


def extract_sans(cert_dict):
    """Extracts DNS names and IP addresses from the certificate Subject Alternative Name (SAN)."""
    san_list = []
    if not cert_dict or "subjectAltName" not in cert_dict:
        return san_list

    for entry in cert_dict["subjectAltName"]:
        if entry[0] in ("DNS", "IP Address"):
            san_list.append(entry[1])
    return san_list


def match_hostname_custom(cert_dict, target_hostname):
    """
    Robust custom hostname matcher supporting exact matches, IP addresses,
    and standard wildcard certificates (e.g., *.admin.johnson.int).
    """
    sans = extract_sans(cert_dict)

    # Also check Common Name (CN) from subject if no SAN matches or as backup
    cn_list = []
    for rdn in cert_dict.get("subject", []):
        for k, v in rdn:
            if k == "commonName":
                cn_list.append(v)

    all_allowed_names = sans + cn_list
    target_lower = target_hostname.lower()

    log.debug(
        f"Evaluating target hostname '{target_hostname}' against allowed SAN/CN list: {all_allowed_names}"
    )

    for name in all_allowed_names:
        name_lower = name.lower()
        # 1. Exact match
        if target_lower == name_lower:
            return True
        # 2. Wildcard match (e.g., *.admin.johnson.int matches kanban.admin.johnson.int)
        if name_lower.startswith("*."):
            domain_suffix = name_lower[1:]  # e.g., ".admin.johnson.int"
            parts = target_lower.split(".")
            if len(parts) > 2 and target_lower.endswith(domain_suffix):
                return True
            if fnmatch.fnmatch(target_lower, name_lower):
                return True

    raise ValueError(
        f"hostname '{target_hostname}' doesn't match any allowed SAN/CN entries: {all_allowed_names}"
    )


def validate_certificate(endpoint, target_hostname=None):
    """Core workflow to parse endpoint, pull cert, check expiry, and validate SANs."""
    try:
        host, port = parse_endpoint(endpoint)
    except Exception as e:
        log.error(f"Failed to parse endpoint '{endpoint}': {e}")
        return False

    validate_host = target_hostname if target_hostname else host

    log.info(
        f"Connecting to {host}:{port} (Validating for hostname: '{validate_host}')..."
    )

    cert_dict, verification_error = get_certificate_details(host, port)

    if not cert_dict:
        log.error(
            f"Could not retrieve certificate from {host}:{port}. Error: {verification_error or 'Unknown connection error'}"
        )
        return False

    # 1. Extract SANs
    sans = extract_sans(cert_dict)

    # 2. Check Expiration
    not_after_str = cert_dict.get("notAfter")
    not_before_str = cert_dict.get("notBefore")

    date_format = "%b %d %H:%M:%S %Y %Z"
    now = datetime.now(timezone.utc)

    expired = False
    not_yet_valid = False

    try:
        not_after = datetime.strptime(not_after_str, date_format).replace(
            tzinfo=timezone.utc
        )
        not_before = datetime.strptime(not_before_str, date_format).replace(
            tzinfo=timezone.utc
        )
        if now > not_after:
            expired = True
        if now < not_before:
            not_yet_valid = True
    except Exception as e:
        log.debug(f"Date parsing warning: {e}")

    # 3. Check Hostname / SAN Match using our built-in robust matcher
    hostname_matched = True
    match_error = None
    try:
        match_hostname_custom(cert_dict, validate_host)
    except Exception as e:
        hostname_matched = False
        match_error = str(e)

    # --- Print Inspection Report ---
    print("\n--- Certificate Validation Report ---")
    sub_dict = {k: v for rdn in cert_dict.get("subject", []) for k, v in rdn}
    iss_dict = {k: v for rdn in cert_dict.get("issuer", []) for k, v in rdn}
    print(f"Subject Common Name (CN): {sub_dict.get('commonName', 'N/A')}")
    print(f"Issuer: {iss_dict.get('commonName', 'N/A')}")
    print(f"Valid From: {not_before_str}")
    print(f"Valid Until: {not_after_str}")
    print("\nCert Extension SAN:")
    print("  Not Critical")
    for san in sans:
        prefix = (
            "IP Address"
            if any(char.isdigit() for char in san) and "." in san
            else "DNS Name"
        )
        print(f"  {prefix}: {san}")
    print("-" * 37)

    # --- Evaluate Results & Failures ---
    failures = []

    if verification_error:
        failures.append(verification_error)
    if expired:
        failures.append(f"Certificate has expired on {not_after_str}")
    if not_yet_valid:
        failures.append(f"Certificate is not valid yet (starts {not_before_str})")
    if not hostname_matched:
        failures.append(
            f"Hostname mismatch: Cert SAN does not match specified host '{validate_host}'. Details: {match_error}"
        )

    if failures:
        log.error(f"Validation failed for '{validate_host}':")
        for fail in failures:
            log.error(f"  - {fail}")
        return False
    else:
        log.info(
            f"SUCCESS: Certificate for '{validate_host}' is valid, trusted, unexpired, and matches SANs!"
        )
        return True


def main():
    prog_usage = f"""
Examples of use:
  {__scriptName__} kanban.admin.johnson.int
  {__scriptName__} https://kanban.admin.johnson.int:443 --hostname kanban.admin.johnson.int
  {__scriptName__} kanban.admin.johnson.int -L DEBUG
  {__scriptName__} --version
"""

    parser = argparse.ArgumentParser(
        formatter_class=RawTextHelpFormatter,
        description="TLS Certificate & SAN Validation Tool\nValidates site certificates, trust paths, expiration dates, and hostname SAN mappings.",
        epilog=prog_usage,
    )

    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"%(prog)s {__version__} ({__updated__})",
    )
    parser.add_argument(
        "-L",
        "--loglevel",
        choices=["DEBUG", "INFO", "WARN", "ERROR"],
        default="INFO",
        help="Set log level (default: INFO)",
    )
    parser.add_argument(
        "--hostname",
        "-H",
        help="Optional specific hostname to validate against SAN (defaults to host in endpoint)",
        default=None,
    )

    parser.add_argument(
        "endpoint", help="Target endpoint as HOST, HOST:PORT, or https://HOST:PORT"
    )

    args = parser.parse_args()

    setup_logging(args.loglevel)

    log.debug("Started certificate validation run")

    success = validate_certificate(args.endpoint, args.hostname)

    if success:
        log.debug("Finished validation run successfully")
        sys.exit(0)
    else:
        log.debug("Finished validation run with failures")
        sys.exit(1)


if __name__ == "__main__":
    main()
