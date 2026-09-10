
# Testing Documentation

This repository employs a multi-layered testing strategy, ranging from static analysis (linting) to dynamic infrastructure testing via Molecule.

## Table of Contents

- [Running PyTest Tests](#running-pytest-tests)
- [Pre-commit hooks](#pre-commit-hooks)

---

## Running PyTest Tests

### Execution
Run unit tests directly from the repository root:

```bash
pytest tests/unit/
```

Or target a specific module:

```bash
pytest tests/unit/test_redact.py
```

#### Debugging & Logging using pytest
- Use `--tb=short` for concise errors.
- Enable logging: `pytest --log-cli-level=DEBUG -s ...`.

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
