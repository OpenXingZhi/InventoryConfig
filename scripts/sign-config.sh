#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 || $# -gt 2 ]]; then
  echo "usage: $0 <ANDROID_ID>.yml [GPG_KEY_ID]" >&2
  exit 2
fi

file=$1
key=${2:-${INVENTORY_CONFIG_SIGNING_KEY:-}}
here=$(cd "$(dirname "$0")" && pwd)

if [[ -z "$key" ]]; then
  echo "provide GPG_KEY_ID or INVENTORY_CONFIG_SIGNING_KEY" >&2
  exit 2
fi

python3 "$here/validate-config.py" "$file" --bind-filename
gpg --batch --yes --local-user "$key" --armor --detach-sign \
  --output "$file.asc" "$file"
gpg --batch --verify "$file.asc" "$file"

echo "signed: $file"
