#!/usr/bin/env python3
"""
Goodreads OAuth 1.0a Token Retrieval Tool
Executes the OAuth 1.0a handshake via rauth to obtain a Goodreads
access token and access token secret.
"""

import os
import sys
import argparse
import getpass
from argparse import RawTextHelpFormatter
import logging
from rauth import OAuth1Service

# Script metadata matching template structure
__scriptName__ = os.path.basename(sys.argv[0])
__version__ = '2026.11.18'
__updated__ = '18 November 2026'

log = logging.getLogger(__scriptName__)

DEFAULT_REQUEST_TOKEN_URL = 'https://www.goodreads.com/oauth/request_token'
DEFAULT_AUTHORIZE_URL = 'https://www.goodreads.com/oauth/authorize'
DEFAULT_ACCESS_TOKEN_URL = 'https://www.goodreads.com/oauth/access_token'
DEFAULT_BASE_URL = 'https://www.goodreads.com/'


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


def resolve_credential(cli_value, env_names):
    """Resolves a credential from CLI arg, then ordered environment variables."""
    if cli_value:
        return cli_value
    for env_name in env_names:
        val = os.environ.get(env_name)
        if val:
            log.debug(f"Using credential from environment variable {env_name}.")
            return val
    return None


def fetch_goodreads_tokens(
    consumer_key,
    consumer_secret,
    request_token_url=DEFAULT_REQUEST_TOKEN_URL,
    authorize_url_base=DEFAULT_AUTHORIZE_URL,
    access_token_url=DEFAULT_ACCESS_TOKEN_URL,
    base_url=DEFAULT_BASE_URL,
    show_request_token=False,
):
    """Performs the OAuth 1.0a flow and returns (access_token, access_token_secret)."""
    log.debug("Initializing Goodreads OAuth1Service client...")
    goodreads = OAuth1Service(
        consumer_key=consumer_key,
        consumer_secret=consumer_secret,
        name='goodreads',
        request_token_url=request_token_url,
        authorize_url=authorize_url_base,
        access_token_url=access_token_url,
        base_url=base_url,
    )

    # header_auth=True is required by Goodreads' OAuth 1.0a implementation
    log.info("Requesting OAuth request token...")
    request_token, request_token_secret = goodreads.get_request_token(header_auth=True)
    log.debug("Successfully retrieved temporary request token.")

    if show_request_token:
        log.info(f"Request Token:        {request_token}")
        log.info(f"Request Token Secret: {request_token_secret}")

    authorize_url = goodreads.get_authorize_url(request_token)
    print("\n1. Open the following URL in your browser and authorize access:\n")
    print(f"   {authorize_url}\n")

    while True:
        try:
            confirmed = input("2. Have you authorized the application in your browser? [y/N]: ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            print("\nAborted.")
            return None, None

        if confirmed in ('y', 'yes'):
            break
        if confirmed in ('', 'n', 'no'):
            log.info("Waiting for authorization confirmation...")
        else:
            log.warning("Please enter 'y' or 'n'.")

    log.info("Exchanging authorized request token for access token and secret...")
    session = goodreads.get_auth_session(request_token, request_token_secret)

    access_token = getattr(session, 'access_token', None)
    access_token_secret = getattr(session, 'access_token_secret', None)

    if not access_token or not access_token_secret:
        log.error("Failed to retrieve access_token or access_token_secret from session.")
        return None, None

    log.info("Successfully obtained Goodreads OAuth access token and secret.")
    return access_token, access_token_secret


def prompt_if_missing(value, prompt_text, secret=False):
    """Returns value if provided, otherwise prompts interactively."""
    if value:
        return value
    try:
        entered = getpass.getpass(prompt_text) if secret else input(prompt_text)
        return entered.strip()
    except (KeyboardInterrupt, EOFError):
        print("\nAborted.")
        sys.exit(1)


def main():
    prog_usage = f"""
Examples of use:
  {__scriptName__} -k YOUR_CONSUMER_KEY -s YOUR_CONSUMER_SECRET
  GOODREADS_API_KEY=... GOODREADS_API_SECRET=... {__scriptName__}
  {__scriptName__} -L DEBUG
  {__scriptName__} --version
"""

    parser = argparse.ArgumentParser(
        formatter_class=RawTextHelpFormatter,
        description="Goodreads OAuth 1.0a Token Retrieval Tool\nFetches an OAuth access token and secret for the Goodreads API.",
        epilog=prog_usage,
    )

    parser.add_argument(
        "-v", "--version",
        action="version",
        version=f"%(prog)s {__version__} ({__updated__})",
    )
    parser.add_argument(
        "-L", "--loglevel",
        choices=['DEBUG', 'INFO', 'WARN', 'ERROR'],
        default='INFO',
        help="Set log level (default: INFO)",
    )
    parser.add_argument(
        "-k", "--consumer-key",
        default=None,
        help="Goodreads OAuth consumer key (falls back to GOODREADS_API_KEY)",
    )
    parser.add_argument(
        "-s", "--consumer-secret",
        default=None,
        help="Goodreads OAuth consumer secret (falls back to GOODREADS_API_SECRET)",
    )
    parser.add_argument(
        "--show-request-token",
        action="store_true",
        help="Also display the intermediate request token and secret",
    )

    args = parser.parse_args()
    setup_logging(args.loglevel)

    log.debug("Started Goodreads OAuth token retrieval run")

    resolved_key = resolve_credential(
        args.consumer_key,
        ("GOODREADS_API_KEY", "GOODREADS_CONSUMER_KEY"),
    )
    resolved_secret = resolve_credential(
        args.consumer_secret,
        ("GOODREADS_API_SECRET", "GOODREADS_CONSUMER_SECRET"),
    )

    consumer_key = prompt_if_missing(resolved_key, "Enter Goodreads Consumer Key: ", secret=False)
    if not consumer_key:
        log.error("Consumer key cannot be empty.")
        sys.exit(1)

    consumer_secret = prompt_if_missing(resolved_secret, "Enter Goodreads Consumer Secret: ", secret=True)
    if not consumer_secret:
        log.error("Consumer secret cannot be empty.")
        sys.exit(1)

    try:
        access_token, access_token_secret = fetch_goodreads_tokens(
            consumer_key=consumer_key,
            consumer_secret=consumer_secret,
            show_request_token=args.show_request_token,
        )
    except Exception as e:
        log.error(f"OAuth token retrieval failed: {e}")
        log.debug("Exception details:", exc_info=True)
        sys.exit(1)

    if not access_token or not access_token_secret:
        log.debug("Finished OAuth token retrieval without obtaining access credentials")
        sys.exit(1)

    print("\nAccess Credentials (save these securely):")
    print(f"  GOODREADS_ACCESS_TOKEN={access_token}")
    print(f"  GOODREADS_ACCESS_TOKEN_SECRET={access_token_secret}")

    log.debug("Finished Goodreads OAuth token retrieval successfully")
    sys.exit(0)


if __name__ == '__main__':
    main()
