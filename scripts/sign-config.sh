#!/usr/bin/env bash
# Create a detached armored signature for one Inventory device configuration.
# The script never embeds a key, passphrase, or other secret.
set -euo pipefail

usage() {
  echo "usage: sign-config.sh [--bump-revision] <ANDROID_ID>.yml [signing-key-id]" >&2
  echo "signing-key-id may also be supplied as INVENTORY_CONFIG_SIGNING_KEY" >&2
}

bump_revision=0
positional=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --bump-revision)
      bump_revision=1
      shift
      ;;
    -h | --help)
      usage
      exit 0
      ;;
    --)
      shift
      positional+=("$@")
      break
      ;;
    -*)
      echo "Unknown option: $1" >&2
      usage
      exit 2
      ;;
    *)
      positional+=("$1")
      shift
      ;;
  esac
done

if [[ ${#positional[@]} -lt 1 || ${#positional[@]} -gt 2 ]]; then
  usage
  exit 2
fi

file=${positional[0]}
key=${positional[1]:-${INVENTORY_CONFIG_SIGNING_KEY:-}}

if [[ ! -f "$file" || "$file" != *.yml ]]; then
  echo "Expected an existing .yml file" >&2
  exit 2
fi

base=$(basename -- "$file")
if [[ "$base" == "default.yml" || "$base" == "any.yml" || "$base" == "all.yml" || "$base" == "wildcard.yml" || "$base" == "*.yml" ]]; then
  echo "Refusing to sign a wildcard/default configuration" >&2
  exit 2
fi
if [[ ! "$base" =~ ^[0-9A-F]{16}\.yml$ ]]; then
  echo "Filename must be <ANDROID_ID>.yml with a 16-digit uppercase hex Android ID" >&2
  exit 2
fi

if [[ -z "$key" ]]; then
  echo "Provide a signing key ID as the second argument or INVENTORY_CONFIG_SIGNING_KEY" >&2
  exit 2
fi

if [[ "$key" == *" "* || "$key" == *$'\n'* ]]; then
  echo "Signing key ID must be a single token" >&2
  exit 2
fi

for command in gpg python3; do
  if ! command -v "$command" >/dev/null; then
    echo "$command is required" >&2
    exit 2
  fi
done

here=$(cd "$(dirname -- "$0")" && pwd)
export PYTHONPATH="$here${PYTHONPATH:+:$PYTHONPATH}"
python3 "$here/validate-config.py" --require-filename-sn "$file"

if [[ "$bump_revision" -eq 1 ]]; then
  next_revision=$(python3 - "$file" <<'PY'
import sys
from pathlib import Path

from inventory_config import bump_revision

print(bump_revision(Path(sys.argv[1])))
PY
  )
  printf '%s: revision %s\n' "$file" "$next_revision"
  python3 "$here/validate-config.py" --require-filename-sn "$file"
fi

gpg --batch --yes --local-user "$key" --armor --detach-sign \
  --output "$file.asc" "$file"
gpg --batch --verify "$file.asc" "$file"
printf '%s: signed\n' "$file"
