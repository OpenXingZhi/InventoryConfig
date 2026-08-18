#!/usr/bin/env bash
# Validate examples, fixtures, repository layout, and signer safety.
set -euo pipefail

here=$(cd "$(dirname -- "$0")" && pwd)
root=$(cd "$here/.." && pwd)
python3_bin=${PYTHON3:-python3}
export PYTHONPATH="$here${PYTHONPATH:+:$PYTHONPATH}"

pass=0
fail=0
assert_ok() {
  local name=$1
  shift
  if "$@"; then
    printf 'ok - %s\n' "$name"
    pass=$((pass + 1))
  else
    printf 'not ok - %s\n' "$name" >&2
    fail=$((fail + 1))
  fi
}

assert_fails() {
  local name=$1
  shift
  if "$@" >/dev/null 2>&1; then
    printf 'not ok - %s (expected failure)\n' "$name" >&2
    fail=$((fail + 1))
  else
    printf 'ok - %s\n' "$name"
    pass=$((pass + 1))
  fi
}

validate() {
  "$python3_bin" "$here/validate-config.py" "$@"
}

assert_ok "repository layout" validate --check-repo
assert_ok "example document" validate --require-filename-sn "$root/examples/0123456789ABCDEF.yml"
assert_ok "stdlib unit tests" "$python3_bin" "$root/tests/test_inventory_config.py"

for file in "$root/fixtures/schema/valid/"*.yml; do
  assert_ok "valid fixture $(basename -- "$file")" validate "$file"
done

for file in "$root/fixtures/schema/invalid/"*.yml; do
  assert_fails "invalid fixture $(basename -- "$file")" validate "$file"
done

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

# Signer rejects a default/wildcard name before consulting GPG.
cp "$root/examples/0123456789ABCDEF.yml" "$tmp/default.yml"
assert_fails "signer rejects default.yml" "$here/sign-config.sh" "$tmp/default.yml" "dummy-key"

cp "$root/examples/0123456789ABCDEF.yml" "$tmp/0123456789abcdef.yml"
assert_fails "signer rejects lowercase Android ID filename" \
  "$here/sign-config.sh" "$tmp/0123456789abcdef.yml" "dummy-key"

cp "$root/examples/0123456789ABCDEF.yml" "$tmp/0123456789ABCDEF.yml"
python3_bin="$python3_bin" "$python3_bin" - "$tmp/0123456789ABCDEF.yml" <<'PY'
from pathlib import Path
import sys
path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
path.write_text(text.replace("0123456789ABCDEF", "DEADBEEFDEADBEEF", 1), encoding="utf-8")
PY
assert_fails "signer rejects filename/SN mismatch" \
  "$here/sign-config.sh" "$tmp/0123456789ABCDEF.yml" "dummy-key"

cp "$root/fixtures/schema/invalid/revision-zero.yml" "$tmp/0123456789ABCDEF.yml"
assert_fails "signer rejects non-positive revision" \
  "$here/sign-config.sh" "$tmp/0123456789ABCDEF.yml" "dummy-key"

assert_fails "signer requires a key" "$here/sign-config.sh" "$root/examples/0123456789ABCDEF.yml"

if ! command -v gpg >/dev/null; then
  printf 'not ok - gpg is required for signer cryptographic tests\n' >&2
  fail=$((fail + 1))
else
  export GNUPGHOME="$tmp/gnupg"
  mkdir -m 700 "$GNUPGHOME"
  gpg --batch --pinentry-mode loopback --passphrase '' \
    --quick-generate-key "InventoryConfig CI <ci@invalid>" ed25519 sign never
  fingerprint=$(
    gpg --batch --list-secret-keys --with-colons |
      awk -F: '$1 == "fpr" { print $10; exit }'
  )
  work="$tmp/sign"
  mkdir "$work"
  cp "$root/examples/0123456789ABCDEF.yml" "$work/0123456789ABCDEF.yml"

  assert_ok "signer creates a detached armored signature" \
    "$here/sign-config.sh" "$work/0123456789ABCDEF.yml" "$fingerprint"
  assert_ok "signature file exists" test -f "$work/0123456789ABCDEF.yml.asc"
  assert_ok "signature verifies" \
    gpg --batch --verify "$work/0123456789ABCDEF.yml.asc" "$work/0123456789ABCDEF.yml"
  if grep -q "BEGIN PGP SIGNATURE" "$work/0123456789ABCDEF.yml.asc"; then
    printf 'ok - signature is armored\n'
    pass=$((pass + 1))
  else
    printf 'not ok - signature is armored\n' >&2
    fail=$((fail + 1))
  fi

  env_work="$tmp/env-sign"
  mkdir "$env_work"
  cp "$root/examples/0123456789ABCDEF.yml" "$env_work/0123456789ABCDEF.yml"
  assert_ok "signer accepts INVENTORY_CONFIG_SIGNING_KEY" \
    env INVENTORY_CONFIG_SIGNING_KEY="$fingerprint" \
    "$here/sign-config.sh" "$env_work/0123456789ABCDEF.yml"

  bump_work="$tmp/bump"
  mkdir "$bump_work"
  cp "$root/examples/0123456789ABCDEF.yml" "$bump_work/0123456789ABCDEF.yml"
  assert_ok "signer can bump revision before signing" \
    "$here/sign-config.sh" --bump-revision "$bump_work/0123456789ABCDEF.yml" "$fingerprint"
  if grep -q '^revision: 2$' "$bump_work/0123456789ABCDEF.yml"; then
    printf 'ok - bumped revision is 2\n'
    pass=$((pass + 1))
  else
    printf 'not ok - bumped revision is 2\n' >&2
    fail=$((fail + 1))
  fi
  assert_ok "bumped document still validates" \
    validate --require-filename-sn "$bump_work/0123456789ABCDEF.yml"

  # Ephemeral key material must stay in the temp directory.
  if find "$root" -path "$tmp" -prune -o \( -name '*.key' -o -name 'secring.*' \) -print | grep -q .; then
    printf 'not ok - no secret key files in the repository tree\n' >&2
    fail=$((fail + 1))
  else
    printf 'ok - no secret key files in the repository tree\n'
    pass=$((pass + 1))
  fi
fi

if command -v check-jsonschema >/dev/null; then
  assert_ok "check-jsonschema example" \
    check-jsonschema --schemafile "$root/schema/inventory-config.schema.json" \
    "$root/examples/0123456789ABCDEF.yml"
  for file in "$root/fixtures/schema/valid/"*.yml; do
    assert_ok "check-jsonschema $(basename -- "$file")" \
      check-jsonschema --schemafile "$root/schema/inventory-config.schema.json" "$file"
  done
  for file in "$root/fixtures/schema/invalid/"*.yml; do
    assert_fails "check-jsonschema rejects $(basename -- "$file")" \
      check-jsonschema --schemafile "$root/schema/inventory-config.schema.json" "$file"
  done
else
  printf 'ok - check-jsonschema not installed; stdlib validator covered schema checks\n'
  pass=$((pass + 1))
fi

printf '\n%d passed, %d failed\n' "$pass" "$fail"
if [[ "$fail" -ne 0 ]]; then
  exit 1
fi
