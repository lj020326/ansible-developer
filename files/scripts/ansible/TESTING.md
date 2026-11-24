# Testing Guide for `files/scripts/ansible/`

This guide covers running the existing `pytest` unit tests and validating the scripts in `files/scripts/ansible/`—including the newer utilities (`vault_organizer.py`, `vault_scrambler.py`, `update_fqmns.py`, and `kics-find-missing-excludes.sh`)—in isolated temporary directories so repository files are not modified unintentionally.

---

## 1. Run Existing Unit Tests

From the repository root, run `pytest` against `tests/unit/`:

```bash
pytest -v files/scripts/ansible/tests/unit/
```


Or run an individual test file:

```bash
pytest -v files/scripts/ansible/tests/unit/test_vault_scrambler.py
pytest -v files/scripts/ansible/tests/unit/test_vault_organizer.py
```


---

## 2. Test `vault_organizer.py`

Create a temporary workspace to test grouping, cross-group/intra-group dependency sorting, cycle handling, and CLI exit codes:

```bash
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

cat <<'EOF' > "$TMP_DIR/vault_plain.yml"
---
# Top header comment
vault__z_app_token: "z-token"
vault__authelia_oidc_secret: "{{ vault__oidc_base_secret }}"
vault__oidc_base_secret: "base-secret-123"
vault__ansible_ssh_pass: "ssh-pass-123"
EOF

python3 files/scripts/ansible/vault_organizer.py --plaintext "$TMP_DIR/vault_plain.yml" > "$TMP_DIR/sorted.yml"
cat "$TMP_DIR/sorted.yml"
```


**Verify**:
* `vault__ansible_ssh_pass` appears before `vault__oidc_base_secret`, which appears before `vault__authelia_oidc_secret`, with `vault__z_app_token` grouped under `z`.
* `# Top header comment` is preserved in the output.
* Missing file and empty YAML exit with status `1`:
  ```bash
  python3 files/scripts/ansible/vault_organizer.py "$TMP_DIR/missing.yml" ; echo "exit=$?"
  printf -- "---\n" > "$TMP_DIR/empty.yml"
  python3 files/scripts/ansible/vault_organizer.py --plaintext "$TMP_DIR/empty.yml" ; echo "exit=$?"
  ```


---

## 3. Test `vault_scrambler.py`

Test deterministic plaintext scrambling, domain/LDAP anonymization, exclusion filtering, `--no-exclude`, and `--scramble-vault` ciphertext mode:

```bash
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

cat <<'EOF' > "$TMP_DIR/sample_vault.yml"
---
# Endpoint on internal.dettonville.int
vault__custom_url: "[https://app.dettonville.int/api](https://app.dettonville.int/api)"
vault__custom_password: "PlainPasswordValue99"
vault__custom_jinja: "{{ vault__custom_url }}"

# --------------------
# openbao
# --------------------
vault__openbao_token: "s.secretTokenValue"

vault__ldap_domain_user_map:
  jdoe:
    cn: "Jane Doe"
    given_name: "Jane"
    sn: "Doe"
    display_name: "Jane Doe"
    initials: "JD"
    mail: "jdoe@dettonville.int"
    username: "jdoe"
  admin:
    cn: "Admin"
    username: "admin"
EOF

# 1. Default plaintext scramble (excludes openbao, strips orphaned header, anonymizes domains)
python3 files/scripts/ansible/vault_scrambler.py --seed 42 --plaintext "$TMP_DIR/sample_vault.yml" > "$TMP_DIR/scrambled.yml"
grep -E "dettonville|openbao|jdoe" "$TMP_DIR/scrambled.yml" ; echo "grep_exit=$?"
cat "$TMP_DIR/scrambled.yml"

# 2. Retain excluded keys with --no-exclude
python3 files/scripts/ansible/vault_scrambler.py --seed 42 --no-exclude --plaintext "$TMP_DIR/sample_vault.yml" | grep -c "vault__openbao_token"

# 3. Direct vault ciphertext scrambling (--scramble-vault)
cat <<'EOF' > "$TMP_DIR/vault_cipher.yml"
---
sample_secret: !vault |
  $ANSIBLE_VAULT;1.1;AES256
  3035396432313934373035336261323935393930393466303939373863623133
EOF

python3 files/scripts/ansible/vault_scrambler.py --seed 42 --scramble-vault "$TMP_DIR/vault_cipher.yml" > "$TMP_DIR/vault_cipher_out.yml"
grep -q '!vault |' "$TMP_DIR/vault_cipher_out.yml"
grep -q '\$ANSIBLE_VAULT;1.1;AES256' "$TMP_DIR/vault_cipher_out.yml"
! grep -q '3035396432313934373035336261323935393930393466303939373863623133' "$TMP_DIR/vault_cipher_out.yml"
```

---

## 4. Test `update_fqmns.py`

Test dry-run behavior first, then `--apply` with `--capitalize-names` and `--add-task-names` inside a temporary copy:

```bash
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

cat <<'EOF' > "$TMP_DIR/tasks.yml"
---
- name: "install packages"
  package:
    name: curl
    state: present

- include_tasks: common.yml

- debug:
    var: ansible_hostname

- set_fact:
    my_flag: true
EOF

# Dry run should not modify the file
python3 files/scripts/ansible/update_fqmns.py "$TMP_DIR/tasks.yml"
grep -q "  package:" "$TMP_DIR/tasks.yml"

# Apply FQCN + name transforms
python3 files/scripts/ansible/update_fqmns.py --apply --capitalize-names --add-task-names "$TMP_DIR/tasks.yml"
cat "$TMP_DIR/tasks.yml"
```


**Verify**:
* `"install packages"` becomes `"Install packages"` and `package:` becomes `ansible.builtin.package:`.
* Task names are generated for `include_tasks` (`Run common.yml`), `debug` (`Display ansible_hostname`), and `set_fact` (`Set my_flag`).

---

## 5. Test `kics-find-missing-excludes.sh` and Vault Password Helpers

Run `kics-find-missing-excludes.sh` in a temporary directory containing a sample `.kics-config.yml` and one existing vs. one missing file:

```bash
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

mkdir -p "$TMP_DIR/roles/demo/tasks"
touch "$TMP_DIR/roles/demo/tasks/existing.yml"

cat <<'EOF' > "$TMP_DIR/.kics-config.yml"
exclude-paths:
  - "roles/demo/tasks/existing.yml"
  - "roles/demo/tasks/deleted.yml"
  - "roles/**/glob_pattern.yml"
EOF

(
  cd "$TMP_DIR" || exit 1
  bash /Users/ljohnson/repos/ansible/ansible-developer/files/scripts/ansible/kics-find-missing-excludes.sh ".kics-config.yml" "roles"
)
```


**Verify**:
* Summary reports `Checked : 2` (glob entries are filtered out), `Still exist : 1`, and `Missing : 1`, listing `roles/demo/tasks/deleted.yml`.

To test `.vault_pass` lookup helpers in isolation with a temporary `HOME`:

```bash
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

mkdir -p "$TMP_DIR/proj/sub"
printf "temp-vault-secret\n" > "$TMP_DIR/proj/.vault_pass"

(
  cd "$TMP_DIR/proj/sub" || exit 1
  HOME="$TMP_DIR" bash /Users/ljohnson/repos/ansible/ansible-developer/files/scripts/ansible/get-vault-password.sh
)

(
  cd "$TMP_DIR/proj/sub" || exit 1
  HOME="$TMP_DIR" \
  IDEA_ANSIBLE_VAULT_CONTEXT_DIRECTORY="$TMP_DIR/proj/sub" \
  IDEA_ANSIBLE_VAULT_CONTEXT_FILE="$TMP_DIR/proj/sub/vars.yml" \
  bash /Users/ljohnson/repos/ansible/ansible-developer/files/scripts/ansible/idea-get-vault-password.sh
)
```

---

## 6. Static Linting (`shellcheck`, `ruff`, `mypy`)

```bash
shellcheck files/scripts/ansible/*.sh
ruff check files/scripts/ansible/
mypy files/scripts/ansible/
```
