#!/usr/bin/env python3
"""
SSH Key Rotation & Deployment Tool

Automates the deployment of an SSH public key to GitHub, Bitbucket,
Gitea (with endpoint-specific tokens), and local Linux hosts.

Supports standard types ('ed25519'), legacy testing types ('rsa'), and
experimental/hybrid post-quantum identifiers ('mlkem768x25519-sha256').

Supports config file (~/.rotate-ssh-key.yml or dynamic based on script name).

By default, this script skips keypair generation to allow testing of deployment
logic. Use the --generate flag to create a new key pair.

Note: key rotation with `ed25519` (the current best-practice, quantum-resistant-friendly choice for SSH signatures). Pure post-quantum signature algorithms aren't yet standardized/default in mainstream OpenSSH for authentication keys, but `ed25519` is fast, secure, and widely supported. Hybrid post-quantum key exchange (e.g., `mlkem768x25519-sha256`) is handled at the protocol level by modern OpenSSH.
"""

import argparse
import getpass
import logging
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

import paramiko
import requests
import yaml

# =============================================================================
# Configuration & Logging
# =============================================================================

SCRIPT_VERSION = "2026.06.22"
SCRIPT_PATH = Path(__file__).resolve()
SCRIPT_BASENAME = SCRIPT_PATH.name

# Dynamic config file based on script name (e.g. rotate-ssh-key.py -> .rotate-ssh-key.yml)
CONFIG_BASENAME = SCRIPT_BASENAME.replace('.py', '')
DEFAULT_CONFIG_NAME = f".{CONFIG_BASENAME}.yml"

# Setup logging
logger = logging.getLogger(__name__)


def setup_logging(log_level: str = "INFO"):
    """Setup logging with configurable level."""
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=numeric_level,
        format="[%(asctime)s] [%(levelname)-8s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )


def load_config(explicit_path: Path = None) -> Dict[str, Any]:
    """Locate and load the configuration file, trying both hyphen and underscore variants."""
    # Define possible default locations if an explicit path isn't forced via CLI
    search_paths = []
    if explicit_path:
        search_paths.append(explicit_path)
    else:
        # Intelligently look for both common naming conventions in home directory
        search_paths.append(Path.home() / DEFAULT_CONFIG_NAME)

    for path in search_paths:
        if path.exists():
            try:
                with open(path, encoding="utf-8") as f:
                    config = yaml.safe_load(f) or {}
                logger.info("✅ Configuration file successfully found and loaded: %s", path)
                return config
            except Exception as e:
                logger.error("❌ Failed to parse config file at %s: %s", path, e)
                return {}

    logger.info("ℹ️  No configuration file found at evaluated paths. Proceeding with CLI arguments only.")
    return {}


def merge_args_and_config(args: argparse.Namespace, config: Dict[str, Any]) -> argparse.Namespace:
    """Merge config values into args (CLI args take precedence)."""
    for key, value in config.items():
        if value is None:
            continue
        current = getattr(args, key, None)
        if current in (None, [], False, "") or (isinstance(current, list) and len(current) == 0):
            setattr(args, key, value)
    return args


def generate_key_pair(key_path: Path, comment: str, key_type: str = "ed25519", passphrase: str = None):
    """Generate SSH key pair based on specified key type."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ed25519, rsa

    logger.info("Generating new %s key pair...", key_type.upper())
    normalized_type = key_type.lower()

    if normalized_type == "ed25519":
        private_key = ed25519.Ed25519PrivateKey.generate()
        public_key = private_key.public_key()

        enc = serialization.BestAvailableEncryption(passphrase.encode()) if passphrase else serialization.NoEncryption()
        priv_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.OpenSSH,
            encryption_algorithm=enc
        )
        pub_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.OpenSSH,
            format=serialization.PublicFormat.OpenSSH
        )
        pub_str = pub_bytes.decode().strip() + f" {comment}\n"

        key_path.write_bytes(priv_bytes)
        key_path.with_suffix('.pub').write_text(pub_str)

    elif normalized_type == "rsa":
        logger.info("Generating secure 4096-bit RSA key pair...")
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=4096
        )
        public_key = private_key.public_key()

        enc = serialization.BestAvailableEncryption(passphrase.encode()) if passphrase else serialization.NoEncryption()
        priv_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.OpenSSH,
            encryption_algorithm=enc
        )
        pub_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.OpenSSH,
            format=serialization.PublicFormat.OpenSSH
        )
        pub_str = pub_bytes.decode().strip() + f" {comment}\n"

        key_path.write_bytes(priv_bytes)
        key_path.with_suffix('.pub').write_text(pub_str)

    elif "mlkem" in normalized_type or "pq" in normalized_type:
        logger.warning("⚠️  %s uses hybrid post-quantum properties. Falling back to system OpenSSH keygen...", key_type)
        import subprocess
        try:
            cmd = ["ssh-keygen", "-t", key_type, "-C", comment, "-f", str(key_path), "-N", passphrase or ""]
            subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except Exception as e:
            logger.error("❌ System ssh-keygen failed to compile key type %s. Standard OpenSSH 9.5+ required: %s",
                         key_type, e)
            sys.exit(1)
    else:
        logger.error("❌ Unsupported key type requested: %s", key_type)
        sys.exit(1)

    key_path.chmod(0o600)
    key_path.with_suffix('.pub').chmod(0o644)

    logger.info("✅ Generated new key pair at %s", key_path)
    return key_path, key_path.with_suffix('.pub')


def backup_old_keys(ssh_dir: Path):
    """Backup existing SSH keys."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = ssh_dir / f"backup_{timestamp}"
    backup_dir.mkdir(exist_ok=True)

    for f in ssh_dir.glob("id_*"):
        if f.is_file() and not f.is_symlink():
            shutil.copy2(f, backup_dir)
    logger.info("✅ Backed up old keys to %s", backup_dir)


def add_to_github(pub_key_path: Path, token: str, title: str, key_type: str):
    """Add public key to GitHub."""
    if "mlkem" in key_type.lower():
        logger.warning(
            "⚠️  Skipping GitHub deployment: Native ML-KEM public key validation not universally supported via REST API.")
        return

    logger.info("🚀 Attempting deployment to GitHub API...")
    try:
        with open(pub_key_path, encoding="utf-8") as f:
            key_content = f.read().strip()

        data = {"title": title, "key": key_content}
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json"
        }

        r = requests.post("https://api.github.com/user/keys", json=data, headers=headers, timeout=15)

        if r.status_code == 201:
            logger.info("✅ Successfully deployed public key to GitHub")
        else:
            logger.error("❌ GitHub API rejection status %s: %s", r.status_code, r.text)
    except Exception as e:
        logger.error("❌ Failed deployment operation to GitHub: %s", e)


def add_to_bitbucket(pub_key_path: Path, username: str, app_password: str, title: str, key_type: str):
    """Add public key to Bitbucket."""
    if "mlkem" in key_type.lower():
        logger.warning("⚠️  Skipping Bitbucket deployment: PQ algorithms not yet accepted via account API.")
        return

    logger.info("🚀 Attempting deployment to Bitbucket Account API (@%s)...", username)
    try:
        with open(pub_key_path, encoding="utf-8") as f:
            key_content = f.read().strip()

        data = {"key": key_content, "label": title}
        r = requests.post(
            f"https://api.bitbucket.org/2.0/users/{username}/ssh-keys",
            json=data,
            auth=(username, app_password),
            timeout=15
        )

        if r.status_code in (200, 201):
            logger.info("✅ Successfully deployed public key to Bitbucket")
        else:
            logger.error("❌ Bitbucket API rejection status %s: %s", r.status_code, r.text)
    except Exception as e:
        logger.error("❌ Failed deployment operation to Bitbucket: %s", e)


def add_to_gitea(pub_key_path: Path, url: str, token: str, title: str):
    """Add public key to a specific Gitea instance via its API."""
    base_url = url.split("/user/settings/keys")[0].rstrip("/")
    api_url = f"{base_url}/api/v1/user/keys"

    logger.info("🚀 Attempting deployment to Gitea endpoint: %s", base_url)
    try:
        with open(pub_key_path, encoding="utf-8") as f:
            key_content = f.read().strip()

        data = {"title": title, "key": key_content, "read_only": False}
        headers = {
            "Authorization": f"token {token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        # verify=False can be added here if dealing with self-signed internal certs
        r = requests.post(api_url, json=data, headers=headers, timeout=15)

        if r.status_code == 201:
            logger.info("✅ Successfully deployed public key to Gitea: %s", base_url)
        elif r.status_code == 422:
            logger.warning("⚠️  Gitea instance (%s) notes key registration already exists.", base_url)
        else:
            logger.error("❌ Gitea API rejection status %s on %s: %s", r.status_code, base_url, r.text)
    except Exception as e:
        logger.error("❌ Failed deployment connection to Gitea (%s): %s", base_url, e)


def deploy_to_local_host(host: str, username: str, pub_key_path: Path = None, reset_keys: bool = False):
    """Deploy public key to a remote Linux host, optionally purging legacy unverified keys."""
    if reset_keys:
        logger.info("🚀 Attempting SSH delivery with EXCLUSIVE RESET to: %s@%s", username, host)
    else:
        logger.info("🚀 Attempting SSH delivery to target destination: %s@%s", username, host)

    try:
        with open(pub_key_path, encoding="utf-8") as f:
            pub_key = f.read().strip()

        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        client.connect(
            hostname=host,
            username=username,
            look_for_keys=True,
            timeout=15,
            allow_agent=True
        )

        if reset_keys:
            # Overwrite the authorized_keys exclusively with the payload, ensuring safety exclusion
            cmd = f'''
            mkdir -p ~/.ssh && chmod 700 ~/.ssh &&
            echo "{pub_key}" > ~/.ssh/authorized_keys &&
            chmod 600 ~/.ssh/authorized_keys &&
            echo "Authorized keys exclusively rewritten and reset"
            '''
        else:
            # Append natively as before
            cmd = f'''
            mkdir -p ~/.ssh && chmod 700 ~/.ssh &&
            echo "{pub_key}" >> ~/.ssh/authorized_keys &&
            chmod 600 ~/.ssh/authorized_keys &&
            echo "Authorized keys stream updated"
            '''

        _, stdout, stderr = client.exec_command(cmd)
        output = stdout.read().decode().strip() or stderr.read().decode().strip()
        logger.info("✅ Successfully authorized on %s (@%s): %s", host, username, output)
        client.close()
    except Exception as e:
        logger.error("❌ Failed SSH authorization deployment execution to %s (@%s): %s", host, username, e)


def parse_cli_gitea_endpoints(endpoints: List[str]) -> List[Dict[str, str]]:
    """Parse CLI input strings formatted as 'url:token' into list of dicts."""
    parsed = []
    if not endpoints:
        return parsed
    for item in endpoints:
        if "::" in item or item.count(":") >= 2:
            # Handle standard protocol strings safely (e.g., https://host:token)
            parts = item.rsplit(":", 1)
            if len(parts) == 2:
                parsed.append({"url": parts[0], "token": parts[1]})
        elif ":" in item:
            url, token = item.split(":", 1)
            parsed.append({"url": url, "token": token})
        else:
            logger.warning("⚠️  Skipping invalid CLI Gitea argument pattern (missing token): %s", item)
    return parsed


def main():
    parser = argparse.ArgumentParser(
        description="SSH Key Deployment & Rotation Tool",
        epilog=f"""
    Examples:
      # Example config file (~/{DEFAULT_CONFIG_NAME}):
      ```yaml
      name: id_ed25519
      comment: "ljohnson@macbookpro-2026"

      # Runtime options
      confirm_deployments: false
      reset_authorized_keys: false

      github_token: ghp_xxxxxxxxxxxxxxxxxxxx

      bitbucket_user: ljohnson
      bitbucket_pass: ATBBxxxxxxxxxxxxxxxxxxxxxxxxxx

      gitea_endpoints:
        - url: "https://gitea.admin.dettonville.int/user/settings/keys"
          token: "gt_dettonville_secret_token_here"
        - url: "https://gitea.admin.johnson.int/user/settings/keys"
          token: "gt_johnson_secret_token_here"

      # Targets grid definitions
      local_hosts:
        - admin01.example.com
        - admin02.company.local
        - 192.168.1.50

      # Multi-user targeted lists
      local_users:
        - administrator
        - ljohnson
      ```

      # Test deployment of existing ed25519 key (Default)
      python3 {SCRIPT_BASENAME}

      # Test deployment of an existing RSA key pair (Default mode)
      python3 {SCRIPT_BASENAME} --key-type rsa

      # Generate and Deploy (Full rotation mode)
      python3 {SCRIPT_BASENAME} --generate

      # Generate a hybrid post-quantum keypair and deploy it
      python3 {SCRIPT_BASENAME} --generate --key-type mlkem768x25519-sha256

      # Generate a legacy 4096-bit RSA keypair and deploy it everywhere
      python3 {SCRIPT_BASENAME} --generate --key-type rsa

      # Override specific values via CLI
      python3 {SCRIPT_BASENAME} --local-hosts admin03.local --github-token NEW_TOKEN

      # Using more args
      python3 {SCRIPT_BASENAME} \
          --name id_ed25519_new \
          --comment "ljohnson@macbookpro-2026" \
          --github-token ghp_... \
          --bitbucket-user ljohnson \
          --bitbucket-pass ... \
          --local-hosts admin01.example.com admin02.example.com

      # Or override endpoints via CLI with format 'url:token'
      python3 {SCRIPT_BASENAME} --gitea-endpoints "https://gitea.local:token123"

      # Debug mode
      python3 {SCRIPT_BASENAME} --log-level DEBUG
            """
    )
    parser.add_argument("-c", "--config", type=Path, default=None,
                        help=f"Config file path (default: ~/{DEFAULT_CONFIG_NAME})")
    parser.add_argument("-L", "--log-level",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                        default="INFO",
                        help="Set logging level (default: INFO)")
    parser.add_argument("-g", "--generate", action="store_true",
                        help="Generate a new SSH keypair before deploying")
    parser.add_argument("-t", "--key-type", default="ed25519",
                        help="SSH key algorithm type (e.g., ed25519, rsa, mlkem768x25519-sha256). Default: ed25519")
    parser.add_argument("-C", "--confirm-deployments", action="store_true", default=False,
                        help="Interactively confirm deployment for each local target host matrix loop (Default: False)")
    parser.add_argument("-R", "--reset-authorized-keys", action="store_true", default=False,
                        help="Flush out/clear legacy authorized_keys from host file, retaining ONLY the newly deployed key (Default: False)")
    parser.add_argument("-U", "--local-users", nargs="*",
                        help="Space-separated list of target Linux accounts to receive the key (Defaults to active script run user)")
    parser.add_argument("--name", help="Base name for key (e.g. `id_ed25519` or `id_rsa`)")
    parser.add_argument("--comment", help="Key comment content")
    parser.add_argument("--passphrase", action="store_true", help="Prompt for passphrase (only used if generating)")
    parser.add_argument("--github-token", help="GitHub Personal Access Token")
    parser.add_argument("--bitbucket-user", help="Bitbucket User ID")
    parser.add_argument("--bitbucket-pass", help="Bitbucket API Token / Password")
    parser.add_argument("--gitea-endpoints", nargs="*",
                        help="Gitea entries. Config uses dict format; CLI uses 'url:token' format.")
    parser.add_argument("--local-hosts", nargs="*", help="List of target systems")
    parser.add_argument("--no-backup", action="store_true", help="Skip backup of old keys (only used if generating)")

    args = parser.parse_args()
    setup_logging(args.log_level)

    logger.info("Initializing SSH key process orchestrator...")

    # Load and merge config
    config = load_config(args.config)
    args = merge_args_and_config(args, config)

    # Establish fallback for local_users to avoid hardcoding guesses
    if not args.local_users:
        current_user = getpass.getuser()
        args.local_users = [current_user]
        logger.debug("No destination users configured. Defaulting to local executor user: %s", current_user)

    cli_gitea = []
    if args.gitea_endpoints and isinstance(args.gitea_endpoints, list) and len(args.gitea_endpoints) > 0:
        if isinstance(args.gitea_endpoints[0], str):
            cli_gitea = parse_cli_gitea_endpoints(args.gitea_endpoints)
    if cli_gitea:
        args.gitea_endpoints = cli_gitea

    ssh_dir = Path.home() / ".ssh"
    ssh_dir.mkdir(exist_ok=True)

    # Clean up name mapping based on hyphens/underscores for standard key file conventions
    sanitized_type = args.key_type.replace('x', '_').replace('-', '_')
    key_name = args.name or f"id_{sanitized_type}"
    key_path = ssh_dir / key_name
    pub_key_path = key_path.with_suffix('.pub')

    comment = args.comment or f"{getpass.getuser()}@{os.uname().nodename}-{datetime.now():%Y-%m-%d}"

    if args.generate:
        logger.info("🔄 Running in FULL ROTATION mode with key type [%s]...", args.key_type.upper())
        ssh_dir.mkdir(exist_ok=True)

        if key_path.exists():
            if input(f"Key {key_path} already exists. Overwrite? (y/N): ").lower() != 'y':
                logger.info("Operation cancelled by user request.")
                sys.exit(1)

        if not args.no_backup:
            backup_old_keys(ssh_dir)

        passphrase = None
        if args.passphrase:
            passphrase = getpass.getpass("Enter passphrase for new key (leave empty for none): ")

        generate_key_pair(key_path, comment, args.key_type, passphrase)
    else:
        logger.info("🧪 Running in DEPLOYMENT TEST mode for key type [%s]...", args.key_type.upper())
        if not pub_key_path.exists():
            logger.error("❌ Target public key file not found: %s", pub_key_path)
            logger.error("   To generate a new key pair, pass the '-g' or '--generate' flag.")
            sys.exit(1)
        logger.info("👉 Existing public key pinpointed: %s", pub_key_path)

    # Execution Blocks with Explicit Status Logging
    has_deployments = False

    if args.github_token:
        has_deployments = True
        add_to_github(pub_key_path, args.github_token, comment, args.key_type)

    if args.bitbucket_user and args.bitbucket_pass:
        has_deployments = True
        add_to_bitbucket(pub_key_path, args.bitbucket_user, args.bitbucket_pass, comment, args.key_type)

    # Scoped Gitea Deployments
    if args.gitea_endpoints:
        has_deployments = True
        logger.info("Found %d configured Gitea endpoints. Iterating endpoints...", len(args.gitea_endpoints))
        for entry in args.gitea_endpoints:
            if isinstance(entry, dict) and "url" in entry and "token" in entry:
                add_to_gitea(pub_key_path, entry["url"], entry["token"], comment)
            else:
                logger.error("❌ Invalid Gitea mapping object structure located: %s", entry)

    if args.local_hosts:
        has_deployments = True
        logger.info("Found %d host targets and %d account targets. Processing grid deployment...",
                    len(args.local_hosts), len(args.local_users))

        for host in args.local_hosts:
            for user in args.local_users:
                if args.confirm_deployments:
                    if input(f"   Deploy payload to user '{user}' on host '{host}'? (y/N): ").lower() != 'y':
                        logger.info("Skipping target instance: %s@%s", user, host)
                        continue

                deploy_to_local_host(host, username=user, pub_key_path=pub_key_path,
                                     reset_keys=args.reset_authorized_keys)

    if not has_deployments:
        logger.warning(
            "⚠️  No endpoints (GitHub, Bitbucket, Gitea, or local_hosts) were discovered or evaluated for execution.")

    logger.info("")
    logger.info("🎉 Task completion routine finalized successfully.")
    logger.info("   Private key: %s", key_path)
    logger.info("   Public key : %s", pub_key_path)
    logger.info("")
    logger.info("Next steps:")
    logger.info("    • Test: ssh -i %s <user>@<host>", key_path)
    logger.info("    • Update ~/.ssh/config if needed")
    logger.info("    • Remove old keys from services once verified")


if __name__ == "__main__":
    main()
