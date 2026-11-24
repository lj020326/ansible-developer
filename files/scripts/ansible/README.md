# Ansible Developer Utility Scripts (`files/scripts/ansible/`)

This directory contains shell and Python automation utilities for Ansible development, vault management, fact migration, FQCN modernization, KICS security configuration hygiene, and unit testing.

## Directory Layout

```text
files/scripts/ansible/
├── ansible-env-setup.sh
├── ansible_facts_update.sh
├── deploy-ansible-collection.sh
├── get-vault-password.sh
├── idea-get-vault-password.sh
├── install-ansibledev-local.sh
├── kics-find-missing-excludes.sh
├── test-parent-dir-walk.sh
├── tests/
│   └── unit/
│       ├── test_vault_organizer.py
│       └── test_vault_scrambler.py
├── update_fqmns.py
├── vault_organizer.py
└── vault_scrambler.py
```


---

## Python Utilities

### `vault_organizer.py`
Sorts and groups `vault__` keys alpha-numerically by logical prefix (e.g., `vault__ansible_*` → `ansible`, `vault__gitea__*` → `gitea`) while ordering dependent variables and groups after their prerequisites based on Jinja/text references.

* **Cycle handling**: Uses topological sorting with alpha-numeric tie-breaking and deterministic cycle breaking so cyclic references log a warning without stalling independent or downstream keys.
* **Vault & YAML support**: Supports `--plaintext`, `--vault`, and auto-detection of `$ANSIBLE_VAULT` files (via `ansible.parsing.vault.VaultLib` when available or `ansible-vault view` fallback), preserving comments, quotes, and `!vault` scalars via `ruamel.yaml`.
* **Examples**:
  ```bash
  ./vault_organizer.py --plaintext vault.example.yml > sorted_vault.yml
  ./vault_organizer.py --vault --vault-password-file ~/.vault_pass inventory/group_vars/all/vault.yml > sorted_vault.yml
  ```


### `vault_scrambler.py`
Replaces sensitive values in YAML or Ansible Vault files with same-length or category-preserving randomized strings so sanitized structures can be shared or split safely.

* **Scrambling & anonymization**: Preserves structural characters, known tokens (`PRESERVE_TOKENS`), prefixes (`ssh-ed25519 `, `https://`, `github_pat_`, `{SSHA}`, `hf_`, `tk_`, etc.), PEM/OpenVPN/INI headers, and Jinja2 expressions (`{{ ... }}`, `{% ... %}`), while anonymizing sensitive domains (`DOMAIN_MAP`) in values, keys, and YAML comments.
* **LDAP & password handling**: Consistently maps usernames from `vault__ldap_domain_user_map` and `TRANSLATE_USERNAME_LIST` using `LDAP_USER_INFO_POOL` (while keeping `PRESERVED_LDAP_USERNAMES` intact) and generates 22–32 character strong passwords for credential-like keys unless structured/templated.
* **Exclusions & cleanup**: Drops keys matching `EXCLUDED_KEY_PATTERNS` unless `--no-exclude` is passed, and strips orphaned section headers via `_strip_orphaned_section_headers`.
* **Direct ciphertext scrambling**: Supports `--scramble-vault` to scramble `$ANSIBLE_VAULT` bodies character-by-character without decrypting while preserving vault headers and `!vault` block formatting.
* **Examples**:
  ```bash
  ./vault_scrambler.py --seed 42 --plaintext vault.example.yml > scrambled.yml
  ./vault_scrambler.py --seed 42 --scramble-vault vars/vault.yml > scrambled_vault.yml
  ./vault_scrambler.py --no-exclude --plaintext vault.example.yml > all_scrambled.yml
  ```


### `update_fqmns.py`
Converts short Ansible module names to Fully Qualified Collection Names (FQCNs) across `.yml` and `.yaml` files for `ansible.builtin`, `ansible.posix`, `ansible.windows`, `community.general`, `community.windows`, `community.docker`, and `openstack.cloud`.

* **Safe dry-run default**: Previews changes unless `--apply` is specified.
* **Optional task normalization**: Supports `--capitalize-names` for quoted task `- name:` entries and `--add-task-names` for `include_tasks`, `import_tasks`, `debug` (`var:` / `msg:`), and single-key `set_fact` tasks.
* **Examples**:
  ```bash
  ./update_fqmns.py playbooks/ roles/
  ./update_fqmns.py tasks/*.yml --apply --capitalize-names --add-task-names
  ```


---

## Shell Scripts

| Script | Purpose & Usage |
| :--- | :--- |
| `ansible-env-setup.sh` | Meant to be `source`d (`source ansible-env-setup.sh [-q]`) to prepend `lib`, `test/lib`, `bin`, and `docs/man` paths from a checkout onto `PYTHONPATH`, `PATH`, and `MANPATH`. |
| `ansible_facts_update.sh` | Runs in-place `sed -i -E` passes over `./**/*` to migrate legacy `ansible_*`, `hostvars[...]['ansible_*']`, `ansible_date_time.*`, and hardware fact references to `ansible_facts[...]`. |
| `deploy-ansible-collection.sh` | Reads `namespace`, `name`, and `version` from `galaxy.yml` using `yq`, builds the collection tarball with `ansible-galaxy collection build`, optionally installs locally (`-l`, `-p`), publishes to Galaxy (`-g` or `ANSIBLE_GALAXY_TOKEN`, skip with `-s`), and runs verification. |
| `get-vault-password.sh` | Walks up parent directories from `$PWD` and falls back to `$HOME/.vault_pass` to print the contents of `.vault_pass` for Ansible Vault password-script integration. |
| `idea-get-vault-password.sh` | JetBrains/IntelliJ Ansible Vault script helper that verifies `IDEA_ANSIBLE_VAULT_CONTEXT_DIRECTORY`, starts from `dirname "$IDEA_ANSIBLE_VAULT_CONTEXT_FILE"`, walks upward for `.vault_pass`, and falls back to `$HOME/.vault_pass`. |
| `install-ansibledev-local.sh` | Fetches and executes `https://raw.githubusercontent.com/lj020326/ansible-developer/main/install-ansibledev.sh` via `curl` and `bash`. |
| `kics-find-missing-excludes.sh` | Uses `yq` to read non-glob entries under `.["exclude-paths"][]` in a KICS config file (default `.kics-config.yml`) and compares them against a live `find` across target directories (default `inventory,playbooks,roles,molecule,tests,vars`) to report stale entries. |
| `test-parent-dir-walk.sh` | Diagnostic/test variant of the `.vault_pass` parent-directory walk starting from `dirname "${PWD}"` and printing step-by-step lookup progress. |

---

## Unit Tests

Unit tests live under `tests/unit/` and use `pytest` and `ruamel.yaml`:

* `tests/unit/test_vault_organizer.py` — Tests group extraction, text extraction, alphanumeric and dependency ordering, cycle breaking, comment/quote/`!vault` preservation, password loading/CLI decryption, and CLI error/success paths.
* `tests/unit/test_vault_scrambler.py` — Tests character/string scrambling, token/prefix/Jinja/PEM/INI preservation, domain and comment anonymization, LDAP user mapping and strong password generation, exclusions/header stripping, `--scramble-vault` mode, password loading/CLI decryption, and CLI paths.

Run the unit test suite from the repository root:

### Running Unit Tests

```bash
pytest -v files/scripts/ansible/tests/unit/
```

See [TESTING.md](./TESTING.md) for detailed test execution steps and verification procedures for the scripts in this directory.
