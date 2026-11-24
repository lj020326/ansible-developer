#!/usr/bin/env python3
"""
htpasswd Credential Verification Tool
Verifies that a password hash matches the given username inside a .htpasswd file
using the native bcrypt engine directly, eliminating unmaintained passlib issues.
"""

import os
import sys
import argparse
import getpass
from argparse import RawTextHelpFormatter
import logging
import bcrypt

# Script metadata matching template structure
__scriptName__ = os.path.basename(sys.argv[0])
__version__ = '2026.09.22'
__updated__ = '22 September 2026'

log = logging.getLogger(__scriptName__)


def setup_logging(loglevel_str="INFO"):
    """Sets up the script logger and applies the requested logging level."""
    loglevel = getattr(logging, loglevel_str.upper(), logging.INFO)
    log.setLevel(loglevel)

    # Avoid duplicate handlers if setup_logging is called multiple times
    if not log.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(levelname)s: %(message)s')
        handler.setFormatter(formatter)
        log.addHandler(handler)
    else:
        log.handlers[0].setLevel(loglevel)


def verify_htpasswd_credential(filepath, username, password):
    """Verifies credentials against a specified htpasswd file using native bcrypt."""
    log.info(f"Loading htpasswd file: {filepath}")
    if not os.path.exists(filepath):
        log.error(f"File not found: {filepath}")
        return False

    stored_hash = None
    try:
        # 1. Parse the htpasswd file manually to locate target user
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if ':' in line:
                    file_user, file_hash = line.split(':', 1)
                    if file_user == username:
                        stored_hash = file_hash
                        break
    except Exception as e:
        log.error(f"Failed to read htpasswd file: {e}")
        return False

    if not stored_hash:
        log.warning(f"User '{username}' not found in file.")
        return False

    log.debug("Verifying password hash compatibility...")
    try:
        # 2. Standardize modern Apache/Nginx bcrypt variant identifiers ($2y$ -> $2b$)
        # Python's bcrypt module natively expects $2a$ or $2b$ prefixes.
        if stored_hash.startswith('$2y$'):
            log.debug("Converting Apache $2y$ prefix to standard $2b$ format for verification.")
            stored_hash = '$2b$' + stored_hash[4:]

        # 3. Safely truncate input password string to 72 bytes to align with bcrypt standard rules
        encoded_password = password.encode('utf-8')
        if len(encoded_password) > 72:
            log.debug("Password exceeds 72 bytes; truncating safely to mitigate backend engine limit.")
            encoded_password = encoded_password[:72]

        # 4. Execute check against the raw bytes directly
        if bcrypt.checkpw(encoded_password, stored_hash.encode('utf-8')):
            log.info(f"Success: Password is correct for user '{username}'.")
            return True
        else:
            log.warning(f"Failure: Invalid password for user '{username}'.")
            return False

    except Exception as e:
        log.error(f"Verification error encountered: {e}")
        return False


def main():
    prog_usage = f"""
Examples of use:
  {__scriptName__} .htpasswd admin SuperSecurePassword123
  {__scriptName__} .htpasswd admin
  {__scriptName__} .htpasswd -L DEBUG
  {__scriptName__} --version
"""

    parser = argparse.ArgumentParser(
        formatter_class=RawTextHelpFormatter,
        description="htpasswd Credential Verification Tool\nValidates user passwords against secure Apache/Nginx htpasswd files.",
        epilog=prog_usage
    )

    parser.add_argument("-v", "--version", action="version", version=f"%(prog)s {__version__} ({__updated__})")
    parser.add_argument("-L", "--loglevel", choices=['DEBUG', 'INFO', 'WARN', 'ERROR'], default='INFO',
                        help="Set log level (default: INFO)")

    parser.add_argument('filepath', help="Path to the .htpasswd target file")
    parser.add_argument('username', nargs='?', default=None, help="Optional: Target account username")
    parser.add_argument('password', nargs='?', default=None, help="Optional: Plaintext password string")

    args = parser.parse_args()

    setup_logging(args.loglevel)

    log.debug("Started verification run")

    # Fallback interactive terminal prompts if arguments are absent
    username = args.username
    if not username:
        try:
            username = input("Enter username: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nAborted.")
            sys.exit(1)
        if not username:
            log.error("Username cannot be empty.")
            sys.exit(1)

    password = args.password
    if not password:
        try:
            password = getpass.getpass(f"Enter password for '{username}': ")
        except (KeyboardInterrupt, EOFError):
            print("\nAborted.")
            sys.exit(1)

    # Perform verification step
    success = verify_htpasswd_credential(args.filepath, username, password)

    if success:
        log.debug("Finished verification run successfully")
        sys.exit(0)
    else:
        log.debug("Finished verification run with credential mismatches")
        sys.exit(1)


if __name__ == '__main__':
    main()
