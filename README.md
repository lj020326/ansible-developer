[![License](https://img.shields.io/badge/license-MIT-brightgreen.svg?style=flat)](LICENSE.md)

# ansible-developer

Developer environment bootstrap, shell customization, and Ansible/infrastructure automation utilities for standing up and maintaining local workstations (`macOS`, `Linux`, and `MSYS2`/`Cygwin`) and Ansible development workflows.

---

## Overview

`ansible-developer` provides scripts, shell environment configurations, editor/AI tooling configs, and Python/Bash utilities to standardize developer setups and streamline day-to-day Ansible and repository work:

* **Environment Bootstrapper**: Installs or updates the repository under `$HOME/repos/ansible/ansible-developer`, configures Python (`pyenv`) and required libraries (`ansible`, `certifi`, `bcrypt`, `passlib`, `requests`), installs CA certificates, and synchronizes user shell configs.
* **Bash Environment & Sync**: Manages `~/.bash_profile`, `~/.bashrc`, `~/.bash_env`, `~/.bash_prompt`, `~/.bash_aliases`, and `~/.bash_functions` from `files/scripts/bashenv/` via `sync-bashenv.sh` and the `syncbashenv` alias.
* **Ansible & Vault Tooling**: Utilities under `files/scripts/ansible/` for sorting/organizing vault variables (`vault_organizer.py`), sanitizing/scrambling vault files (`vault_scrambler.py`), converting short module names to FQCNs (`update_fqmns.py`), locating `.vault_pass` files, building/deploying collections (`deploy-ansible-collection.sh`), and auditing KICS exclude paths (`kics-find-missing-excludes.sh`).
* **Broader Script & Config Library**: Additional helper scripts and templates under `files/scripts/` (e.g., `certs/`, `docker/`, `git/`, `llm/`, `mac_os/`, `msys2/`, `openbao/`, `openldap/`, `pfsense/`, `python/`, `utils/`, `vmware/`, `windows/`) and editor/AI configurations under `files/env/dev/`.

---

## Repository Structure

```text
ansible-developer/
├── install-ansibledev.sh          # Cross-platform installer (macOS, Linux, MSYS2)
├── install-ansibledev-pvt.sh      # Internal/private remote installer wrapper
├── install-ansibledev-local.sh    # Symlink -> files/scripts/ansible/install-ansibledev-local.sh
├── sync-bashenv.sh                # Symlink -> files/scripts/sync-bashenv.sh
├── pytest.ini                     # Pytest configuration (pythonpath = files/scripts/python)
├── requirements.txt               # Python dependencies for development & testing
├── TESTING.md                     # Repository-level testing and pre-commit guide
├── TODO.md                        # Roadmap and reference notes
├── .pre-commit-config.yaml        # Pre-commit hooks (whitespace, EOF, JSON, private keys, shellcheck)
├── .editorconfig                  # Formatting rules across file types
├── .continue/rules/               # AI coding assistant rules for Bash, Python, and Markdown
├── docs/                          # Reference documentation and notes
└── files/
    ├── env/dev/                   # Editor & CLI configs (.continue, flyline, vscode, Windows Terminal)
    ├── git/                       # Git hooks and ignore templates
    ├── openldap/                  # OpenLDAP LDIF seed templates and RBAC notes
    └── scripts/
        ├── ansible/               # Core Ansible developer scripts, vault tools, and unit tests
        ├── bashenv/               # Bash dotfiles (.bash_aliases, .bash_functions, .bash_env, etc.)
        ├── certs/                 # Certificate inspection, CA import, and TLS validation scripts
        ├── docker/                # Docker registry, image, certificate, and systemd container scripts
        ├── git/                   # Git branch, history, hook, and repo sync helpers
        ├── llm/                   # Local LLM / Ollama utility scripts and configs
        ├── python/                # General Python utilities, pyenv installers, and unit tests
        └── ...                    # Additional domain scripts (backups, cyberark, openbao, pfsense, etc.)
```

---

## Initial Setup & Installation

### 1. Configure `~/.vault_pass`

Create a local `.vault_pass` file with restricted permissions (`600`) for Ansible Vault encryption/decryption workflows:

```bash
echo "vaultpasswordhere" > ~/.vault_pass
chmod 600 ~/.vault_pass
```

### 2. Run the Installer

Install from the public GitHub repository:

```bash
INSTALL_REMOTE_SCRIPT="https://raw.githubusercontent.com/lj020326/ansible-developer/main/install-ansibledev.sh"
bash -c "$(curl -fsSL "${INSTALL_REMOTE_SCRIPT}")"
```

Or install from the internal/private Git repository:

```bash
INSTALL_REMOTE_SCRIPT="https://raw.githubusercontent.com/lj020326/ansible-developer/main/install-ansibledev-pvt.sh"
bash -c "$(curl -fsSL "${INSTALL_REMOTE_SCRIPT}")"
```

If you already have a local copy or want to invoke the local script directly:

```bash
bash install-ansibledev-local.sh
```

`install-ansibledev.sh` supports options including `-L [ERROR|WARN|INFO|TRACE|DEBUG]`, `-r [GIT_REMOTE_URL]`, `-v`, and `-h`, and can run with `NONINTERACTIVE=1` or `CI=1`.

The installer shell script will:
1) create the local developer repo directory under $HOME/repos/ansible
2) clone the repo into the developer's local repo directory at $HOME/repos/ansible/ansible-developer
3) setup/synchronize the developer's bash environment with source bash files located in `files/scripts/bashenv`
4) source the bash env

### 3. Reload & Verify Your Shell Environment

Source `~/.bashrc` (or run `.bash` once aliases are loaded) and verify your Python and Ansible paths:

```bash
. ~/.bashrc
# or after initial load:
.bash

which python3
python3 -V
which ansible
ansible --version
```

### MSYS2 / Windows Home Directory Note

If you use MSYS2 and encounter SSH/Git authentication issues because `HOME` resolves to `/c/Users/<user>` while `nsswitch.conf` defaults to Cygwin home behavior, update `/etc/nsswitch.conf`:

```text
db_home: windows cygwin desc
```

See the [MSYS2 home directory guide](https://stackoverflow.com/questions/33942924/how-to-change-home-directory-and-start-directory-on-msys2) for details.

---

## Managing the Bash Environment

Source files for the shell environment live in `files/scripts/bashenv/`:

* `.bash_aliases` — Navigation (`cddev`, `cdansible`, `cdrepos`, `cdpyutils`, `cdk8s`, etc.), `ll`/`la`, Git helpers, SSH host aliases, `vaultencrypt`/`vaultdecrypt`, `venv`/`.venv`, and `syncbashenv`.
* `.bash_functions` — Shell functions including `blastit`, `cagetaccountpwd`, `certinfo`, `get-certs`, `getgitcomment`, `getgitrequestid`, `gitbranchdelete`, `gitcommitpush`, `gitmergebranch`, `gitpullrebase`, and `gitupdatesub`.
* `.bash_env`, `.bash_path`, `.bash_prompt`, `.bash_profile`, `.bashrc` — Environment variables, `PATH` setup, prompt formatting, and startup initialization.

To synchronize updates from the repository into `$HOME` and reload your shell:

```bash
syncbashenv
```

### `cagetpwd` function to get cyberark password using api

```shell
[ansible-developer](main)$ cagetpwd
CA_ACCOUNT_PWD=",sdkjfh;kewl4j<"
```

The alias/function definition above assumes/requires the developer to have configured the following env vars in the vaulted file at './files/private/vault/bashenv/.bash_secrets':
```shell
export CYBERARK_API_ENDPOINT="cyberarkpas.example.int"
export CYBERARK_API_BASE_URL="https://${CYBERARK_API_ENDPOINT}"
export CYBERARK_API_USERNAME="ca-user-account"
export CYBERARK_API_PASSWORD="ca-password"
## e.g., 'leej'
export CYBERARK_ACCOUNT_USERNAME="ca-user-safe-account-name"
```

---

---

## Key Ansible & Developer Utilities (`files/scripts/ansible/`)

For full details and usage examples, see [files/scripts/ansible/README.md](files/scripts/ansible/README.md) and [files/scripts/ansible/TESTING.md](files/scripts/ansible/TESTING.md).

| Utility | Type | Summary |
| :--- | :--- | :--- |
| `vault_organizer.py` | Python | Sorts `vault__` keys by logical prefix and topological dependency order (with cycle breaking) while preserving comments, quotes, and `!vault` blocks via `ruamel.yaml`. |
| `vault_scrambler.py` | Python | Sanitizes/scrambles plaintext vault/YAML files, anonymizes domains/comments/LDAP users, generates strong passwords, or scrambles `$ANSIBLE_VAULT` ciphertext blocks (`--scramble-vault`). |
| `update_fqmns.py` | Python | Converts short module names to FQCNs across `.yml`/`.yaml` files (dry-run by default; `--apply` to write), with optional `--capitalize-names` and `--add-task-names`. |
| `deploy-ansible-collection.sh` | Bash | Builds a collection tarball from `galaxy.yml` via `yq` and `ansible-galaxy`, with optional local install (`-l`, `-p`) and Galaxy publish/verify. |
| `get-vault-password.sh` / `idea-get-vault-password.sh` | Bash | Walks upward from `$PWD` (or `IDEA_ANSIBLE_VAULT_CONTEXT_FILE`) to locate `.vault_pass`, falling back to `$HOME/.vault_pass`. |
| `kics-find-missing-excludes.sh` | Bash | Compares non-glob `.["exclude-paths"][]` entries in `.kics-config.yml` against live `find` results to identify stale exclusions. |
| `ansible_facts_update.sh` / `ansible-env-setup.sh` | Bash | Migrates legacy `ansible_*` fact references to `ansible_facts[...]` or sets up `PYTHONPATH`, `PATH`, and `MANPATH` for an Ansible checkout. |

---

## Testing & Linting

See [TESTING.md](TESTING.md) and [files/scripts/ansible/TESTING.md](files/scripts/ansible/TESTING.md) for test workflows:

```bash
# Run unit tests
pytest -v files/scripts/ansible/tests/unit/
pytest files/scripts/python/tests/unit/

# Run pre-commit hooks across the repository
pre-commit install
pre-commit run --all-files
```

---

## Maintainer

* **Maintainer:** Lee Johnson
* **Contact:** <ljohnson@dettonville.org>
* **LinkedIn:** https://www.linkedin.com/in/leejjohnson/
* **Framework:** [Dettonville Cloud Infrastructure Services](https://dettonville.org)
