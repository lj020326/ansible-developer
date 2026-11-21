#!/usr/bin/env python3

# -*- coding: utf-8 -*-
#
# This script validates a TLS/SSL connection to a host.
# It uses both the standard library (http.client) and the requests library.
#
# Requires:
#   - python3-requests
#

import os
import sys
import ssl
import http.client
import urllib.parse
# import os
# import certifi
from pathlib import Path

# Check if requests is available
try:
    import requests

    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


def _resolve_ca_bundle() -> str | bool:
    """Resolves a valid CA bundle path from environment variables or standard system paths."""
    # Check if user already provided an environment override
    env_bundle = os.getenv("REQUESTS_CA_BUNDLE") or os.getenv("SSL_CERT_FILE")
    if env_bundle and os.path.exists(env_bundle):
        return env_bundle

    # Common system certificate paths across various distributions
    candidate_paths = [
        "/etc/ssl/certs/ca-certificates.crt",  # Ubuntu / Debian / Gentoo
        "/etc/pki/tls/certs/ca-bundle.crt",  # RHEL / CentOS / Fedora / AlmaLinux
        "/etc/ssl/cert.pem",  # Alpine / macOS / FreeBSD
    ]
    for path in candidate_paths:
        if os.path.exists(path):
            # Setting these ensures both requests and underlying libraries use the system bundle
            os.environ.setdefault("REQUESTS_CA_BUNDLE", path)
            os.environ.setdefault("SSL_CERT_FILE", path)
            return path

    return True  # Fallback to default (certifi)


def get_executable_name() -> str:
    return Path(sys.executable).name


def get_script_name() -> str:
    return sys.argv[0]


def validate_with_http_client(url):
    """Validate SSL connection using http.client (standard library)."""
    parsed_url = urllib.parse.urlparse(url)
    conn = None
    try:
        conn = http.client.HTTPSConnection(parsed_url.netloc, context=ssl.create_default_context())
        conn.request("GET", parsed_url.path or '/')
        response = conn.getresponse()
        print(f"Success with http.client: Status Code {response.status}")
        return True
    except ssl.SSLCertVerificationError as e:
        print(f"SSL Verification Error with http.client: {e}")
    except Exception as e:
        print(f"Connection Error with http.client: {e}")
    finally:
        if conn:
            conn.close()
    return False


def validate_with_requests(url):
    """Validate SSL connection using the requests library."""
    if not HAS_REQUESTS:
        print("requests library not found. Skipping validation with requests.")
        return True

    # Resolve the system CA bundle path
    verify_cert = _resolve_ca_bundle()

    try:
        # Pass verify_cert (which will be a string path or True) to requests
        response = requests.get(url, timeout=10, verify=verify_cert)
        # Allow 404 (or other server response codes) as a successful SSL/TLS handshake indicator
        if response.status_code in (200, 401, 403, 404):
            print(
                f"Success with requests: Status Code {response.status_code} (SSL handshake verified)"
            )
            return True

        response.raise_for_status()
        print(f"Success with requests: Status Code {response.status_code}")
        return True
    except requests.exceptions.SSLError as e:
        print(f"SSL Verification Error with requests: {e}")
        if 'CERTIFICATE_VERIFY_FAILED' in str(e):
            print("Hint: Check if the certificate is in the system's trust store or a Java keystore.")
    except requests.exceptions.RequestException as e:
        print(f"Connection Error with requests: {e}")
    return False


if __name__ == "__main__":

    execname = get_executable_name()
    scriptname = get_script_name()
    argv = sys.argv[1:]

    if len(argv) < 1 or argv[0] in ["--help", "-h"]:
        print(f"({scriptname}) is a very simple python ssl connection validator.")
        print()
        print("\033[1mUsage:")
        print(f"{execname} {scriptname} <validation_url>")
        print("\033[0m")
        print("\033[1mArguments:")
        print("Positional; Purpose; Example")
        print("<validation_url>; SSL endpoint url; https://example.com, https://192.168.1.8:8443, etc")
        print("\033[0m")
        print("\033[1mOptions:")
        print("[--help/-h]; Show this help;")
        print("\033[0m")
        print(f"Example: {execname} {scriptname} https://google.com")
        print(f"On Unix-like systems, this script can be ran via the Shebang: {scriptname} https://10.0.1.10")
        sys.exit(1)

    validation_url = argv[0]
    if not validation_url.startswith(('http://', 'https://')):
        validation_url = 'https://' + validation_url

    print(f"Attempting to validate SSL connection to {validation_url}...")

    success = validate_with_http_client(validation_url)

    if HAS_REQUESTS:
        print("---")
        success &= validate_with_requests(validation_url)

    if not success:
        sys.exit(1)

    print("\nAll SSL validation checks passed successfully!")
    sys.exit(0)
