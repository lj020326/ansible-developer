# Testing Documentation

This repository employs a multi-layered testing strategy, ranging from static analysis (linting) to dynamic infrastructure testing via Molecule.

## Table of Contents

- [Running PyTest Tests](#running-pytest-tests)
- [Testing `fix_shellchecks.py`](#testing-fix_shellcheckspy)
- [Pre-commit hooks](#pre-commit-hooks)

---

## Running PyTest Tests

### Execution
Run unit tests directly from the repository root (or `files/scripts/python/`):

```bash
pytest tests/unit/
```

Or target a specific module:

```bash
pytest tests/unit/
pytest tests/unit/test_redact.py
pytest tests/unit/test_fix_shellchecks.py
pytest tests/unit/test_fix_shellchecks.py::TestApplyEdits::test_apply_multiple_edits_on_same_line_preserves_offsets -v
pytest tests/unit/ 2>&1 | tee pytest-unit.log
```

#### Debugging & Logging using pytest

- Use `--tb=short` for concise errors.
- Enable logging: `pytest --log-cli-level=DEBUG -s ...`.

To view live debug output in pytest, pass the `-s` flag (disable stdout capturing) and `--log-cli-level=DEBUG`:

```shell
pytest -s --log-cli-level=DEBUG -v tests/unit/ 2>&1 | tee pytest-unit.log
```

---

## Testing `fix_shellchecks.py`

The unit test suite in `tests/unit/test_fix_shellchecks.py` validates parsing, handler dispatch, safe skip behavior, offset-preserving line edits, CLI log generation, and `# shellcheck disable=` directive merging.

### Test Suite Organization

| Test Class | Coverage |
| :--- | :--- |
| `TestRegistryAndParsing` | ANSI stripping, multi-rule TTY output parsing, default `RuleHandlerRegistry` contents, custom rule registration, and parsed-findings summary formatting. |
| `TestSc2004Sc2268AndSc2046Handlers` | Arithmetic `${VAR}` stripping (`SC2004`), x-prefix comparison rewrites (`SC2268`), and unquoted `$(...)` command substitution quoting (`SC2046`). |
| `TestSc2061Handler` | Quoting unquoted `find` `-name` glob patterns with and without nested variable quotes. |
| `TestSc2086Handler` | Quote-all-on-line vs. `--no-quote-all-on-line` caret fallback, `--skip-vars` filtering, already-quoted token detection, and mixed-rule log filtering. |
| `TestSc2155Handler` | Splitting single-variable `local`/`readonly` declarations while safely skipping multi-assignment lines. |
| `TestSc2181AndSc1091Handlers` | Safe no-op logging for `$?` checks (`SC2181`), `.` to `source` conversion, and `# shellcheck source=...` insertion for static and dynamic paths (`SC1091`). |
| `TestApplyEdits` | Right-to-left multi-edit offset preservation, duplicate `EditSpan` deduplication, out-of-range/mismatched token guards, and dry-run vs. `--write` file updates. |
| `TestCliAndSkipConfiguration` | `build_effective_skip_vars()`, interactive/non-interactive log generation prompts, `--enable-rule`/`--use-rc` CLI flags, and `--run-shellcheck` execution. |
| `TestDotSourceAndDisableDirectives` | End-to-end `SC1091` file updates and inserting/merging `# shellcheck disable=...` directives via `--disable-unhandled`. |
| `TestUsageAndReachabilityHandlers` | Safe skip behavior for `SC2034`, `SC2317`, and `SC2329`, plus `--suppress-rules` filtering. |

### Running Targeted `fix_shellchecks.py` Tests

```bash
# Run all fix_shellchecks unit tests with verbose output
pytest -v tests/unit/test_fix_shellchecks.py

# Run tests for specific rule handlers (e.g., SC2004, SC2046, SC2268)
pytest -v -k "TestSc2004Sc2268AndSc2046Handlers" tests/unit/test_fix_shellchecks.py

# Inspect debug logs emitted when handlers skip ambiguous lines
pytest -s --log-cli-level=DEBUG -v -k "skip" tests/unit/test_fix_shellchecks.py
```

### Adding Tests for New or Enhanced Rule Handlers

Whenever a new `SCxxxx` handler is registered in `create_default_registry()` or an existing handler is updated:

1. Update `TestRegistryAndParsing.test_default_registry_includes_all_registered_handlers` so the expected `registry.supported_rules()` list matches all registered rules.
2. Add unit tests verifying:
   - **Positive transformation:** `apply_edits_to_content(line, handler(finding))` produces the expected shell syntax and edit count.
   - **Idempotency:** Passing an already-compliant line returns `[]` so repeated runs produce zero duplicate edits.
   - **Safe skipping:** Ambiguous or unsupported constructs return `[]` without corrupting source lines.

---

## Pre-commit hooks

Git requires the hook scripts to be explicitly written into the repository's `.git/hooks/` directory.

### How to Set Up

1. **Navigate to the repository root**:
```bash
cd path/to/ansible-developer
```

2. **Install the git hook scripts**:
Run the following command to register pre-commit into your local `.git/hooks/` directory:
```bash
pre-commit install
## or specify hook types
pre-commit install --hook-type pre-commit
pre-commit install --hook-type pre-push
```

3. **Verify it works**:
You can manually test that the hooks fire across all files without needing to make a commit:
```bash
pre-commit run --all-files
```

### Additional Things to Check If It Fails:

* **Global hooks path:** If you use a custom global hooks template path via `git config --global core.hooksPath`, ensure it isn't intercepting or overriding local repository hooks.
* **Commit flags:** Ensure you aren't accidentally passing `--no-verify` (or `-n`), which explicitly tells git to skip the pre-commit hook execution.

Run the following commands to clear the cache and verify the environment:
```shell
pre-commit clean
pre-commit run --all-files
## or just a specified test
pre-commit run detect-private-key --all-files
```
