# Python Utility Scripts (`files/scripts/python/`)

Collection of standalone Python (and companion shell/PowerShell) operational, validation, packaging, and static-analysis utilities used across this repository and external infrastructure repositories.

## Directory Overview

| Script / File                                                             | Category                  | Description                                                                                                                                                     |
|:--------------------------------------------------------------------------|:--------------------------|:----------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `fix_shellchecks.py`                                                      | Static Analysis / Linting | Extensible ShellCheck remediation engine with a rule-handler registry, dry-run previews, directory ranking, and safe `# shellcheck disable=` injection.         |
| `package_dir.py`                                                          | Developer / AI Context    | Packages directory trees into token-optimized YAML 1.2 context bundles, preserving symlinks as pointer stubs and summarizing oversized subdirectories.          |
| `redact_key_values.py`                                                    | Security / Hygiene        | Redacts sensitive values (`key`, `password`, `secret`, `token`, etc.) from `.env`, `.ini`, shell, and YAML files with optional `--peek` character preservation. |
| `rotate_ssh_key.py`                                                       | Security / Access         | Automates SSH key generation (`ed25519`, `rsa`, `mlkem768x25519-sha256`), key backups, and deployment to GitHub, Bitbucket, Gitea, and Linux hosts.             |
| `sync-records-bidirectional.py`                                           | Backup / Sync             | Hash-tracked bidirectional incremental sync utility with per-path remote-write protection and macOS/SMTP notifications.                                         |
| `verify_htpasswd.py`                                                      | Auth / Validation         | Verifies credentials against `.htpasswd` files using native `bcrypt` (supporting `$2y$` normalization and 72-byte truncation).                                  |
| `verify_ssl_connection.py`                                                | TLS / Diagnostics         | Validates TLS/SSL endpoints via both `http.client` and `requests` with automatic OS CA bundle resolution.                                                       |
| `validate_cacerts.py` / `validate_cacerts_urllib.py`                      | TLS / Diagnostics         | Validates HTTPS endpoints against OpenSSL or custom CA certificate bundles using `pycurl` or `urllib`.                                                          |
| `sync_python_certs_with_macOS_keychain.sh` / `validate_python_cacerts.sh` | TLS / macOS               | Syncs `curl.se` root CAs with macOS `System.keychain` into Python/certifi CA bundles and validates them.                                                        |
| `convert_pdf_to_image_pdf.py`                                             | Document Processing       | Rasterizes text/vector PDFs into flattened image-based PDFs via `pdf2image` and Pillow.                                                                         |
| `combine_apache_config.py`                                                | Web Server                | Recursively resolves Apache `Include` directives into a single consolidated configuration output.                                                               |
| `emailchecker.py` / `monitorconnection.py` / `urlfromsitemap.py`          | Network / Web             | Lightweight utilities for SMTP `VRFY` checks, internet speed logging, and `sitemap.xml` URL extraction.                                                         |
| `cloudstack_api_keys.py` / `cloudstack_helper.py`                         | CloudStack                | Legacy CloudStack API key management and TCP/API health-check helpers.                                                                                          |
| `pyenv-install.sh` / `pyenv-install.ps1`                                  | Environment Setup         | Cross-platform bootstrap installers for `pyenv` / `pyenv-win` and Python runtimes.                                                                              |
| `verify_user_passwd.py` / `sketchpaint.py`                                | Legacy / Misc             | Local `/etc/shadow` password verification helper and legacy Tkinter drawing script.                                                                             |
| `TESTING.md` & `tests/unit/`                                              | Testing                   | Unit test documentation and `pytest` suites (`test_fix_shellchecks.py`, `test_redact.py`).                                                                      |

---

## `fix_shellchecks.py`: Architecture & Iterative Remediation Workflow

`fix_shellchecks.py` parses ShellCheck TTY output (from a saved report such as `.shellcheck-issues.txt` or live `shellcheck -f tty` runs) into structured `ShellCheckFinding` objects and dispatches each finding to a `RuleHandlerRegistry` keyed by ShellCheck rule code.

### Key Design Properties

- **Non-Destructive Defaults:** Runs in **dry-run mode** by default; files are only modified when `-w` / `--write` or `-a` / `--apply` is explicitly supplied.
- **Apply & Automatic Log Refresh (`-a` / `--apply`):** When combined with `-g` / `--regenerate`, `-a` applies fixes in place and automatically re-scans/refreshes the generated log afterward so line numbers and remaining finding counts stay synchronized with modified scripts.
- **Offset-Safe Line Editing:** Handlers return `EditSpan(lineno, start, end, replacement, rule, expected_original)` objects.
- **Normalized Relative Directory Keys:** `_directory_path_key()` and `_normalize_rel_path_str()` strip full workspace prefixes and leading `./` segments so directory reports remain concise and repo-relative.
- **Git-Aware Script Discovery:** Uses `git ls-files --cached --others --exclude-standard` inside Git worktrees (automatically respecting `.gitignore` entries like `save/` while keeping tracked `archive/` directories in scope), falling back to `os.walk` outside Git.
- **Actionable Triage Telemetry:** Regenerating a report (`-g`) prints a breakdown of all parsed findings by rule code and severity (marking which rules are `handled` vs. `unhandled`) alongside a ranked **Top N directories by handled issue type** table.
- **Controlled Directive Suppression:** `--disable-unhandled` (optionally scoped with `--suppress-rules SCxxxx`) inserts `# shellcheck disable=SCxxxx` above skipped/unhandled findings—or merges the code into an existing `# shellcheck disable=...` line immediately above the target statement (stepping past an adjacent `# shellcheck source=...` directive when present).

### Currently Registered Rule Handlers

| Rule | Behavior | Automated Edits? |
| :--- | :--- | :--- |
| **`SC1090`** | Inserts `# shellcheck source=/dev/null` above non-constant `source` lines (unless `--no-source-directive`). | Yes |
| **`SC1091`** | Converts leading `. <target>` to `source <target>` (unless `--no-convert-dot-source`) and inserts `# shellcheck source=<target|/dev/null>` above the line (unless `--no-source-directive`). | Yes |
| **`SC2001`** | Rewrites simple `echo`/`printf ... \| sed 's/...'` literal substitutions into Bash parameter expansion (`${VAR/search/replace}` or `${VAR//search/replace}`); skips regex metacharacters or complex flags. | Yes (conservative) |
| **`SC2004`** | Strips redundant `${VAR}` braces to `VAR` inside `$((...))` arithmetic expansions. | Yes |
| **`SC2006`** | Rewrites backtick command substitutions (`` `...` ``) to `$(...)`, selecting the substitution nearest the caret when multiple exist and skipping nested or backslash-escaped backticks. | Yes |
| **`SC2007`** | Rewrites deprecated `$[...]` arithmetic expressions outside single quotes to `$((...))` and simplifies leading `$var` tokens inside them. | Yes |
| **`SC2046`** | Wraps unquoted `$(...)` command substitutions in double quotes `"$(...)"` while ignoring arithmetic `$((...))` and already-quoted substitutions. | Yes |
| **`SC2061`** | Wraps unquoted `find` `-name` / `-iname` / `-path` (and `-ipath`/`-wholename`/`-iwholename`) glob arguments in double quotes. | Yes |
| **`SC2068`** | Quotes unquoted `$@` / `${@}` expansions outside single and double quotes as `"$@"`. | Yes |
| **`SC2086`** | Double-quotes unquoted variable expansions (`$VAR`, `${VAR}`, `$1`), quoting all unquoted expansions on a flagged line by default (`--quote-all-on-line`) while skipping variables in `DEFAULT_SC2086_SKIP_VARS` (`COMMON_OPTS`, `EXCLUDES`, `DOCKER_HTTP_CURL_HEADERS`, `SYSTEMD_CHECK_CMD`, `OPTIONS`) and tracking nested `$(...)` quote contexts. | Yes |
| **`SC2088`** | Rewrites `"~/path"` to `"$HOME/path"` and unquoted `~/path` to `$HOME/path` outside quotes. | Yes |
| **`SC2145`** | Rewrites `${ARR[@]}` inside double quotes to `${ARR[*]}`. | Yes |
| **`SC2155`** | Splits single-variable `<decl> VAR=<rhs>` (`local`, `export`, `readonly`, `declare`) into a separate declaration line and assignment line; skips multi-assignment declarations. | Yes |
| **`SC2162`** | Inserts `-r` right after unquoted `read` commands when `-r` is not already present. | Yes |
| **`SC2164`** | Appends ` \|\| exit` to unguarded `cd` commands outside quotes that are not already chained with `\|\|` or `&&`. | Yes |
| **`SC2166`** | Splits `-o` into `] \|\| [` and `-a` into `] && [` inside `[ ... ]` test brackets outside quotes. | Yes |
| **`SC2226`** | Appends ` .` to `ln` invocations lacking an explicit destination. | Yes |
| **`SC2231`** | Quotes unquoted variable expansions inside `for ... in ...` glob lists outside quotes. | Yes |
| **`SC2235`** | Rewrites `(...)` groups outside quotes into `{ ...; }`. | Yes |
| **`SC2268`** | Rewrites legacy x-prefixed comparisons (`"x$var" != "x"`, `[ x$var = x ]`, etc.) into `"$var" != ""`. | Yes |
| **`SC2269`** | Removes standalone self-assignment lines (`VAR="$VAR"`, `local VAR=$VAR`, etc.). | Yes |
| **`SC2010`, `SC2012`, `SC2015`, `SC2028`, `SC2059`, `SC2064`, `SC2104`, `SC2115`, `SC2124`, `SC2128`, `SC2148`, `SC2153`, `SC2154`, `SC2193`, `SC2199`, `SC2206`, `SC2207`, `SC2220`, `SC2259`, `SC2260`, `SC2294`, `SC2319`** | Registered conservative skip handlers that log a diagnostic at `DEBUG` level and leave lines untouched for manual review or `--disable-unhandled` suppression. | No (skip + optional disable) |
| **`SC2034`** | Logs and skips unused-variable warnings (safe for sourced files, indirect references, and side-effecting subshells); pair with `--disable-unhandled --suppress-rules SC2034` to suppress intentionally exported/shared variables. | No (skip + optional disable) |
| **`SC2181`** | Logs and skips indirect `$?` exit-code checks because the preceding command lives outside the flagged line. | No (skip + optional disable) |
| **`SC2317`** | Logs and skips unreachable-code warnings for manual review. | No (skip + optional disable) |
| **`SC2329`** | Logs and skips uninvoked-function warnings (traps, hooks, and dynamic dispatch). | No (skip + optional disable) |

---

## Applying, Reviewing (`git diff`), and Pushing ShellCheck Updates

When cleaning up a repository with hundreds or thousands of pre-existing ShellCheck findings across active and archived scripts, running every rule in one pass creates massive, hard-to-review diffs:

### Step 1: Generate Baseline Report & Triage
1. **Generate the initial baseline report** (runs `shellcheck -f tty --norc` across discovered scripts and writes `.shellcheck-issues.txt`):
   ```bash
   python3 files/scripts/python/fix_shellchecks.py -g
   ```
2. **Review the triage summary** printed at the end of `-g`:
   - Check rule counts and severities (`error`, `warning`, `info`, `style`) and whether rules are `handled` or `unhandled`.
   - Inspect the **Top N directories by handled issue type** ranking (`--top-dirs N`) to pick isolated, low-risk directories first.

### Step 2: Dry-Run, Apply (`-w` or `-g -a`), and Refresh Report
1. **Preview candidate changes first** (default dry-run mode writes nothing to disk); use `--log-level DEBUG` to inspect skipped variables or ambiguous lines:
   ```bash
   python3 files/scripts/python/fix_shellchecks.py --rules SC2086 --dir files/scripts/docker --log-level DEBUG
   ```
2. **Apply edits in place** using `-w` (or use `-g -a` when regenerating `.shellcheck-issues.txt` so the report is automatically re-scanned and refreshed after writing):
   ```bash
   # Apply scoped edits in place
   python3 files/scripts/python/fix_shellchecks.py --rules SC2086 --dir files/scripts/docker -w

   # Or apply and refresh the generated log in one command
   python3 files/scripts/python/fix_shellchecks.py -g -a --rules SC2155
   ```
3. **Suppress intentionally skipped rules when appropriate** (for example, `SC2034` on shared/exported variables, optionally excluding `*/archive/*`):
   ```bash
   # Preview suppressions
   python3 files/scripts/python/fix_shellchecks.py -g --exclude "*/archive/*" --disable-unhandled --suppress-rules SC2034

   # Apply and refresh log
   python3 files/scripts/python/fix_shellchecks.py -g -a --exclude "*/archive/*" --disable-unhandled --suppress-rules SC2034
   ```

### Step 3: Review with `git diff`, Run Tests, and Push
1. **Inspect `git status` and `git diff`** to verify every edit—especially quoting, `cd ... || exit` guards (`SC2164`), subshell/brace rewrites (`SC2235`), and `# shellcheck disable=` directives—before staging:
   ```bash
   git status
   git diff --stat
   git diff files/scripts/
   ```
   *(If `.shellcheck-issues.txt` is untracked or gitignored, confirm it is not accidentally committed.)*
2. **Run the unit test suite** (and `pre-commit` / `shellcheck` checks if configured):
   ```bash
   pytest -v files/scripts/python/tests/unit/test_fix_shellchecks.py
   ```
3. **Stage, commit, and push** each logical batch of fixes:
   ```bash
   git add -p
   git commit -m "fix(scripts): remediate SC2086 and SC2155 ShellCheck findings"
   git push
   ```

### Step 4: Extending Handlers for Newly Discovered Rules
1. When a scan surfaces new high-count unhandled rules, implement `make_scXXXX_handler() -> RuleHandler` in `fix_shellchecks.py`, register it in `create_default_registry()`, and add unit tests in `tests/unit/test_fix_shellchecks.py` (updating `test_default_registry_includes_all_registered_handlers` as well).
2. Run `pytest` and a scoped dry-run/apply pass on the new rule(s) before committing.

---

## Using `vault_scrambler.py` and `vault_organizer.py`

[`vault_scrambler.py`](../ansible/vault_scrambler.py) and [`vault_organizer.py`](../ansible/vault_organizer.py) (located under `files/scripts/ansible/`, and optionally exposed on `PATH` via aliases as `vaultscramble` and `vaultorganize`) help prepare sanitized example/template vault files and normalize vault key ordering from Ansible Vault or plain YAML files.

### Typical Workflows

1. **Scramble an Ansible Vault file into sanitized example files** (auto-detects vault encryption/decryption and writes to `save/`):
   ```bash
   # Using the script path directly
   ~/repos/ansible/ansible-developer/files/scripts/ansible/vault_scrambler.py vars/vault.yml > save/vault.example.yml

   # Include excluded/filtered entries with --no-exclude for a full example dump
   ~/repos/ansible/ansible-developer/files/scripts/ansible/vault_scrambler.py --no-exclude vars/vault.yml > save/vault.example-full.yml

   # Or via the CLI shims (`vaultscramble` / `vaultorganize`)
   vaultscramble vars/vault.yml > save/vault.example.yml
   vaultscramble --no-exclude vars/vault.yml > save/vault.example-full.yml
   ```
2. **Scramble a plain-text YAML file with `--plaintext`**:
   ```bash
   ~/repos/ansible/ansible-developer/files/scripts/ansible/vault_scrambler.py --plaintext save/vault.example-full.yml > save/vault.example.v4.yml
   ```
3. **Organize and sort vault keys into logical/dependency-ordered groups**:
   ```bash
   # Organize a plain-text example file
   ~/repos/ansible/ansible-developer/files/scripts/ansible/vault_organizer.py --plaintext save/vault.example.yml > save/vault_sorted.v2.example.yml
   vaultorganize --plaintext save/vault.example-full.yml > save/vault_sorted.example.yml

   # Organize a vault file directly
   vaultorganize vars/vault.yml > save/secrets/vault_sorted.yml
   ```

### Operational Notes & Warnings

- **Auto-Detection vs. `--plaintext`:** Both tools auto-detect Ansible Vault encryption when given an encrypted vault file (such as `vars/vault.yml`), whereas `--plaintext` forces plain YAML mode when operating on unencrypted example files.
- **Dependency Cycle Warnings:** `vault_organizer.py` / `vaultorganize` sorts keys into logical groups using dependency ordering and may emit `WARNING` messages when circular or unresolved group dependencies are encountered (for example, breaking cycles at groups such as `['docker', 'http']` or `['basic']`, or falling back to alphanumeric ordering for unresolved groups). Review the generated output and `git diff` to verify group ordering meets your playbook/role expectations.
- **Output Redirection & Ignored `save/` Paths:** Both commands write transformed YAML to `stdout`, so redirect (`>`) to your target path. In this repository, `save/` is gitignored and excluded from `package_dir.py` and `fix_shellchecks.py` discovery by default.

---

## Applying `fix_shellchecks.py` to Another Repository

You can invoke `fix_shellchecks.py` directly against another Git repository root or copy `fix_shellchecks.py` and `tests/unit/test_fix_shellchecks.py` into the target repository.

### 1. Running Against Another Repository
Run from the target repository's root directory so relative paths in `.shellcheck-issues.txt` resolve cleanly:

```bash
cd /path/to/target-repo

# Generate a fresh baseline log for the target repo
python3 /path/to/fix_shellchecks.py -g

# Or run live against a specific subdirectory without creating a log file
python3 /path/to/fix_shellchecks.py scripts/ --run-shellcheck --rules SC2086 SC2155
```

### 2. Customizing Repo-Specific Behavior via CLI Flags
- **Repo-specific multi-word variables (`SC2086`):** Pass `--skip-vars MY_FLAGS EXTRA_ARGS` (or `--include-vars` / `--no-default-skip`) for variables intentionally holding unquoted argument lists.
- **Custom `.shellcheckrc`:** Pass `--use-rc` if the target repo maintains a `.shellcheckrc` (by default, `--norc` is passed for deterministic scans).
- **Excluding vendor/archive paths:** Use `--exclude "vendor/*" --exclude "*/archive/*"` during log generation or live scans.
