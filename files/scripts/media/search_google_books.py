#!/usr/bin/env python3
"""
Google Books API Search Tool
Queries the Google Books Volumes API using an API key (via CLI, environment
variable, or interactive prompt) and prints formatted volume results.
"""

import os
import sys
import json
import argparse
import getpass
from argparse import RawTextHelpFormatter
import logging
import urllib.parse
import urllib.request
import urllib.error

# Script metadata matching template structure
__scriptName__ = os.path.basename(sys.argv[0])
__version__ = '2026.11.18'
__updated__ = '18 November 2026'

log = logging.getLogger(__scriptName__)

GOOGLE_BOOKS_VOLUMES_URL = 'https://www.googleapis.com/books/v1/volumes'


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


def query_google_books(query, api_key=None, max_results=10, timeout=15):
    """Queries the Google Books volumes endpoint and returns parsed JSON data."""
    params = {
        'q': query,
        'maxResults': max_results,
    }
    if api_key:
        params['key'] = api_key

    url = f"{GOOGLE_BOOKS_VOLUMES_URL}?{urllib.parse.urlencode(params)}"
    log.debug(f"Requesting Google Books URL with query={query!r}, maxResults={max_results}")

    req = urllib.request.Request(
        url,
        headers={
            'User-Agent': f'{__scriptName__}/{__version__}',
            'Accept': 'application/json',
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = getattr(resp, 'status', resp.getcode())
            log.debug(f"Received HTTP {status} from Google Books API.")
            raw_body = resp.read().decode('utf-8')
            return json.loads(raw_body)
    except urllib.error.HTTPError as e:
        error_body = ""
        try:
            error_body = e.read().decode('utf-8', errors='replace')
        except Exception:
            pass
        log.debug(f"HTTP error response body: {error_body}")
        raise RuntimeError(f"Google Books API HTTP {e.code} ({e.reason})") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Network error contacting Google Books API: {e.reason}") from e
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Failed to decode JSON response from Google Books API: {e}") from e


def format_volume_summary(item):
    """Formats a single Google Books volume item into a readable summary dict."""
    info = item.get('volumeInfo', {})
    identifiers = info.get('industryIdentifiers', [])
    isbns = [
        f"{ident.get('type')}:{ident.get('identifier')}"
        for ident in identifiers
        if ident.get('identifier')
    ]

    return {
        'id': item.get('id'),
        'title': info.get('title'),
        'subtitle': info.get('subtitle'),
        'authors': info.get('authors', []),
        'publisher': info.get('publisher'),
        'publishedDate': info.get('publishedDate'),
        'pageCount': info.get('pageCount'),
        'categories': info.get('categories', []),
        'identifiers': isbns,
        'infoLink': info.get('infoLink'),
    }


def print_human_readable(data):
    """Prints formatted volume search results to stdout."""
    total_items = data.get('totalItems', 0)
    items = data.get('items') or []

    log.info(f"Total matching volumes reported: {total_items} (showing {len(items)})")
    if not items:
        print("No matching books found.")
        return

    for idx, item in enumerate(items, start=1):
        summary = format_volume_summary(item)
        title = summary['title'] or '(Untitled)'
        if summary['subtitle']:
            title = f"{title}: {summary['subtitle']}"

        authors = ', '.join(summary['authors']) if summary['authors'] else 'Unknown Author'
        pub_parts = [p for p in (summary['publisher'], summary['publishedDate']) if p]
        pub_info = ' | '.join(pub_parts) if pub_parts else 'N/A'
        isbn_info = ', '.join(summary['identifiers']) if summary['identifiers'] else 'N/A'

        print(f"\n[{idx}] {title}")
        print(f"    Authors:     {authors}")
        print(f"    Published:   {pub_info}")
        if summary['pageCount']:
            print(f"    Pages:       {summary['pageCount']}")
        print(f"    Identifiers: {isbn_info}")
        if summary['infoLink']:
            print(f"    Link:        {summary['infoLink']}")


def main():
    prog_usage = f"""
Examples of use:
  {__scriptName__} "intitle:dune"
  {__scriptName__} -k YOUR_API_KEY "isbn:9780143127550"
  GOOGLE_BOOKS_API_KEY=... {__scriptName__} --max-results 5 "inauthor:frank herbert"
  {__scriptName__} --json "clean code"
  {__scriptName__} -L DEBUG "python automation"
  {__scriptName__} --version
"""

    parser = argparse.ArgumentParser(
        formatter_class=RawTextHelpFormatter,
        description="Google Books API Search Tool\nSearches books and metadata via the Google Books Volumes API.",
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
        "-k", "--api-key",
        default=None,
        help="Google Books API key (falls back to GOOGLE_BOOKS_API_KEY)",
    )
    parser.add_argument(
        "-n", "--max-results",
        type=int,
        default=10,
        help="Maximum number of results to return, 1-40 (default: 10)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output parsed volume summaries as JSON",
    )
    parser.add_argument(
        "--raw-json",
        action="store_true",
        help="Output the raw JSON response payload from Google Books API",
    )
    parser.add_argument(
        "--no-prompt",
        action="store_true",
        help="Do not prompt interactively if API key is missing",
    )
    parser.add_argument(
        'query',
        nargs='?',
        default=None,
        help="Search query string (supports Google Books prefixes like intitle:, inauthor:, isbn:)",
    )

    args = parser.parse_args()
    setup_logging(args.loglevel)

    log.debug("Started Google Books search run")

    if not 1 <= args.max_results <= 40:
        log.error("--max-results must be between 1 and 40.")
        sys.exit(1)

    query = args.query
    if not query:
        if args.no_prompt:
            log.error("Search query cannot be empty.")
            sys.exit(1)
        query = prompt_if_missing(None, "Enter search query: ", secret=False)
        if not query:
            log.error("Search query cannot be empty.")
            sys.exit(1)

    resolved_key = resolve_credential(
        args.api_key,
        ("GOOGLE_BOOKS_API_KEY", "BOOKS_API_KEY"),
    )
    if not resolved_key and not args.no_prompt:
        resolved_key = prompt_if_missing(None, "Enter Google Books API Key (or press Enter to skip): ", secret=True)

    if not resolved_key:
        log.warning("Running without an API key; requests may be rate-limited.")

    try:
        data = query_google_books(
            query=query,
            api_key=resolved_key or None,
            max_results=args.max_results,
        )
    except Exception as e:
        log.error(f"Google Books query failed: {e}")
        log.debug("Exception details:", exc_info=True)
        sys.exit(1)

    if args.raw_json:
        print(json.dumps(data, indent=2))
    elif args.json:
        summaries = [format_volume_summary(item) for item in (data.get('items') or [])]
        print(json.dumps(summaries, indent=2))
    else:
        print_human_readable(data)

    log.debug("Finished Google Books search run successfully")
    sys.exit(0)


if __name__ == '__main__':
    main()
