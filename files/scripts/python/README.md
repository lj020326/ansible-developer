# Python Utility Scripts (`files/scripts/python/`)

Collection of standalone Python (and companion shell/PowerShell) operational, validation, packaging, and static-analysis utilities used across this repository and external infrastructure repositories.

## Directory Overview

| Script / File | Category | Description |
| :--- | :--- | :--- |
| `fix_shellchecks.py` | Static Analysis / Linting | Extensible ShellCheck remediation engine with a rule-handler registry, dry-run previews, directory ranking, and safe `# shellcheck disable=` injection. |
| `package_dir.py` | Developer / AI Context | Packages directory trees into token-optimized YAML 1.2 context bundles, preserving symlinks as pointer stubs and summarizing oversized subdirectories. |
| `redact_key_values.py` | Security / Hygiene | Redacts sensitive values (`key`, `password`, `secret`, `token`, etc.) from `.env`, `.ini`, shell, and YAML files with optional `--peek` character preservation. |
| `rotate_ssh_key.py` | Security / Access | Automates SSH key generation (`ed25519`, `rsa`, `mlkem768x25519-sha256`), key backups, and deployment to GitHub, Bitbucket, Gitea, and Linux hosts. |
| `sync-records-bidirectional.py` | Backup / Sync | Hash-tracked bidirectional incremental sync utility with per-path remote-write protection and macOS/SMTP notifications. |
| `verify_htpasswd.py` | Auth / Validation | Verifies credentials against `.htpasswd` files using native `bcrypt` (supporting `$2y$` normalization and 72-byte truncation). |
| `verify_ssl_connection.py` | TLS / Diagnostics | Validates TLS/SSL endpoints via both `http.client` and `requests` with automatic OS CA bundle resolution. |
| `validate_cacerts.py` / `validate_cacerts_urllib.py` | TLS / Diagnostics | Validates HTTPS endpoints against OpenSSL or custom CA certificate bundles using `pycurl` or `urllib`. |
| `sync_python_certs_with_macOS_keychain.sh` / `validate_python_cacerts.sh` | TLS / macOS | Syncs `curl.se` root CAs with macOS `System.keychain` into Python/certifi CA bundles and validates them. |
| `convert_pdf_to_image_pdf.py` | Document Processing | Rasterizes text/vector PDFs into flattened image-based PDFs via `pdf2image` and Pillow. |
| `combine_apache_config.py` | Web Server | Recursively resolves Apache `Include` directives into a single consolidated configuration output. |
| `emailchecker.py` / `monitorconnection.py` / `urlfromsitemap.py` | Network / Web | Lightweight utilities for SMTP `VRFY` checks, internet speed logging, and `sitemap.xml` URL extraction. |
| `cloudstack_api_keys.py` / `cloudstack_helper.py` | CloudStack | Legacy CloudStack API key management and TCP/API health-check helpers. |
| `pyenv-install.sh` / `pyenv-install.ps1` | Environment Setup | Cross-platform bootstrap installers for `pyenv` / `pyenv-win` and Python runtimes. |
| `verify_user_passwd.py` / `sketchpaint.py` | Legacy / Misc | Local `/etc/shadow` password verification helper and legacy Tkinter drawing script. |
| `TESTING.md` & `tests/unit/` | Testing | Unit test documentation and `pytest` suites (`test_fix_shellchecks.py`, `test_redact.py`). |

---

## `fix_shellchecks.py`: Architecture & Iterative Remediation Workflow

`fix_shellchecks.py` parses ShellCheck TTY output (from a saved report such as `.shellcheck-issues.txt` or live `shellcheck -f tty` runs) into structured `ShellCheckFinding` objects and dispatches each finding to a `RuleHandlerRegistry` keyed by ShellCheck rule code (e.g., `SC2086`, `SC2155`, `SC2268`).

### Key Design Properties

- **Non-Destructive Defaults:** Runs in **dry-run mode** by default; files are only modified when `-w` / `--write` is explicitly supplied.
- **Offset-Safe Line Editing:** Handlers return `EditSpan(lineno, start, end, replacement, rule, expected_original)` objects. `apply_edits_to_content_detailed()` deduplicates identical spans, validates `expected_original` against the live line slice, and applies edits right-to-left (with span replacements applied before zero-width line insertions at column `0`) so multi-edit lines never corrupt column offsets.
- **Git-Aware Script Discovery:** Uses `git ls-files --cached --others --exclude-standard` inside Git worktrees (automatically respecting `.gitignore` entries like `save/` while keeping tracked `archive/` directories in scope), falling back to `os.walk` outside Git.
- **Actionable Triage Telemetry:** Regenerating a report (`-g`) prints a breakdown of all parsed findings by rule code and severity (marking which rules are `handled` vs. `unhandled`) alongside a ranked **Top N directories by handled issue type** table.
- **Controlled Directive Suppression:** `--disable-unhandled` (optionally scoped with `--suppress-rules SCxxxx`) inserts `# shellcheck disable=SCxxxx` above skipped/unhandled findings—or merges the code into an existing `# shellcheck disable=...` line immediately above the target statement.

### Currently Registered Rule Handlers

| Rule | Behavior | Automated Edits? |
| :--- | :--- | :--- |
| **`SC1091`** | Converts leading `. <target>` to `source <target>` (unless `--no-convert-dot-source`) and inserts `# shellcheck source=<target|/dev/null>` above the line (unless `--no-source-directive`). | Yes |
| **`SC2001`** | Rewrites simple `echo`/`printf ... \| sed 's/...'` literal substitutions into Bash parameter expansion (`${VAR/search/replace}` or `${VAR//search/replace}`); skips regex metacharacters or complex flags. | Yes (conservative) |
| **`SC2004`** | Strips redundant `${VAR}` braces to `VAR` inside `$((...))` arithmetic expansions. | Yes |
| **`SC2046`** | Wraps unquoted `$(...)` command substitutions in double quotes `"$(...)"` while ignoring arithmetic `$((...))` and already-quoted substitutions. | Yes |
| **`SC2061`** | Wraps unquoted `find` `-name` / `-iname` / `-path` glob arguments in double quotes. | Yes |
| **`SC2086`** | Double-quotes unquoted variable expansions (`$VAR`, `${VAR}`, `$1`), quoting all unquoted expansions on a flagged line by default (`--quote-all-on-line`) while skipping variables in `DEFAULT_SC2086_SKIP_VARS` (`COMMON_OPTS`, `EXCLUDES`, etc.) and tracking nested `$(...)` quote contexts. | Yes |
| **`SC2155`** | Splits single-variable `<decl> VAR=<rhs>` (`local`, `export`, `readonly`, `declare`) into a separate declaration line and assignment line; skips multi-assignment declarations. | Yes |
| **`SC2268`** | Rewrites legacy x-prefixed comparisons (`"x$var" != "x"`, `[ x$var = x ]`, etc.) into `"$var" != ""`. | Yes |
| **`SC2034`** | Logs and skips unused-variable warnings (safe for sourced files, indirect references, and side-effecting subshells); pair with `--disable-unhandled --suppress-rules SC2034` to suppress intentionally exported/shared variables. | No (skip + optional disable) |
| **`SC2181`** | Logs and skips indirect `$?` exit-code checks because the preceding command lives outside the flagged line. | No (skip + optional disable) |
| **`SC2317`** | Logs and skips unreachable-code warnings for manual review. | No (skip + optional disable) |
| **`SC2329`** | Logs and skips uninvoked-function warnings (traps, hooks, and dynamic dispatch). | No (skip + optional disable) |

---

## Case Study: Iterative Repository-Wide ShellCheck Remediation

When cleaning up a repository with hundreds or thousands of pre-existing ShellCheck findings across active and archived scripts, running every rule in one pass creates massive, hard-to-review diffs. The workflow below summarizes how `fix_shellchecks.py` is used iteratively—one rule class and directory slice at a time—to drive findings down safely:

### Phase 1: Baseline Discovery & Triage
1. **Generate the initial baseline report** (runs `shellcheck -f tty --norc` across all Git-tracked scripts and writes `.shellcheck-issues.txt`):
   ```bash
   python3 files/scripts/python/fix_shellchecks.py -g
   ```
2. **Review the triage summary** printed at the end of `-g`:
   - Identify high-volume **handled** rules (e.g., `SC2086`, `SC2155`, `SC1091`, `SC2061`, `SC2001`).
   - Identify **unhandled** high-volume rules (e.g., `SC2004`, `SC2046`, `SC2268`) that warrant implementing new handlers before bulk remediation.
   - Use the **Top 10 directories by handled issue type** ranking to pick isolated, low-risk directories first.

### Phase 2: High-Frequency Quoting & Declaration Rules (`SC2086`, `SC2155`, `SC1091`)
1. **Tackle `SC2086` directory-by-directory** (dry-run first, inspect `--log-level DEBUG` for skipped multi-flag variables like `COMMON_OPTS` or `OPTIONS`, adjust with `--skip-vars` / `--include-vars`, then write):
   ```bash
   # Dry-run on top-ranked directory
   python3 files/scripts/python/fix_shellchecks.py --rules SC2086 --dir files/scripts/docker --log-level DEBUG

   # Apply in-place once verified
   python3 files/scripts/python/fix_shellchecks.py --rules SC2086 --dir files/scripts/docker -w
   ```
2. **Split masked return values (`SC2155`) and normalize sourcing (`SC1091`)**:
   ```bash
   python3 files/scripts/python/fix_shellchecks.py --rules SC2155 -w
   python3 files/scripts/python/fix_shellchecks.py --rules SC1091 -w
   ```
3. **Regenerate the report** after each milestone so line numbers and remaining counts stay accurate:
   ```bash
   python3 files/scripts/python/fix_shellchecks.py -g
   ```

### Phase 3: Triage Intentionally Unmodified Rules (`SC2034`, `SC2181`, `SC2317`, `SC2329`)
1. For shared library files or legacy scripts where variables (`SC2034`) or functions (`SC2329`) are consumed externally, preview and inject targeted `# shellcheck disable=...` directives—excluding `archive/` if desired:
   ```bash
   # Preview suppressions on active scripts only
   python3 files/scripts/python/fix_shellchecks.py -g --exclude "*/archive/*" --disable-unhandled --suppress-rules SC2034

   # Apply directives in place (merges cleanly with existing disable directives)
   python3 files/scripts/python/fix_shellchecks.py -g --exclude "*/archive/*" --disable-unhandled --suppress-rules SC2034 -w
   ```

### Phase 4: Implement New Handlers for Remaining Rules (`SC2004`, `SC2046`, `SC2268`)
1. When the baseline summary reveals new high-count unhandled rules (`SC2004`, `SC2046`, `SC2268`), add `make_scXXXX_handler()` functions to `fix_shellchecks.py`, register them in `create_default_registry()`, and add unit tests in `tests/unit/test_fix_shellchecks.py`.
2. Verify unit tests pass (`pytest tests/unit/test_fix_shellchecks.py -v`), then run a scoped dry-run and write pass for only the newly added rules:
   ```bash
   python3 files/scripts/python/fix_shellchecks.py -g --rules SC2004 SC2046 SC2268 --log-level DEBUG
   python3 files/scripts/python/fix_shellchecks.py --rules SC2004 SC2046 SC2268 -w
   ```
3. Run a final `python3 files/scripts/python/fix_shellchecks.py -g` and `git diff` review to confirm all targeted issues are resolved without regressions.

---

## Applying `fix_shellchecks.py` to Another Repository

You can copy `fix_shellchecks.py` (and `tests/unit/test_fix_shellchecks.py`) into another repository or invoke it directly against another Git repository root.

### 1. Running Against Another Repository
Run the script from the target repository's root directory so relative paths in `.shellcheck-issues.txt` resolve accurately:

```bash
cd /path/to/target-repo

# Generate a fresh baseline log for the target repo
python3 /path/to/fix_shellchecks.py -g

# Or run live against a specific subdirectory without creating a log file
python3 /path/to/fix_shellchecks.py scripts/ --run-shellcheck --rules SC2086 SC2155
```

### 2. Customizing Repo-Specific Behavior via CLI Flags
- **Repo-specific multi-word variables (`SC2086`):** Pass `--skip-vars MY_FLAGS EXTRA_ARGS` (or update `DEFAULT_SC2086_SKIP_VARS`) for variables intentionally holding unquoted argument lists.
- **Custom `.shellcheckrc`:** Pass `--use-rc` if the target repo maintains a `.shellcheckrc` (by default, `--norc` is passed for deterministic scans).
- **Excluding vendor/archive paths:** Use `--exclude "vendor/*" --exclude "*/archive/*"` during log generation or live scans.

### 3. Adding a New Rule Handler or Enhancing an Existing One
To support additional ShellCheck rules discovered in a new repository:

1. **Inspect the exact ShellCheck TTY output** in `.shellcheck-issues.txt` (noting `src_line`, `caret_offset`, `caret_len`, and `message`).
2. **Implement a handler factory** `make_scXXXX_handler() -> RuleHandler` in `fix_shellchecks.py`:
   - Accept a `ShellCheckFinding` and return `List[EditSpan]`.
   - Always populate `expected_original` on each `EditSpan` so `apply_edits_to_content_detailed()` skips edits safely if a previous rule already modified the line.
   - Return `[]` and log via `logger.debug(...)` whenever an expression is ambiguous or unsafe to rewrite automatically.
3. **Register the handler** in `create_default_registry()` inside the `available` dictionary:
   ```python
   "SCXXXX": make_scXXXX_handler(),
   ```
4. **Add unit tests** in `tests/unit/test_fix_shellchecks.py` covering:
   - Standard positive rewrites (`apply_edits_to_content`),
   - Already-fixed / no-op lines (ensuring idempotency),
   - Edge cases / ambiguous syntax that must be skipped safely,
   - `TestRegistryAndParsing.test_default_registry_includes_all_registered_handlers`.
