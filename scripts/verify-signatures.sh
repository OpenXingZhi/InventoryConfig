#!/usr/bin/env bash
set -euo pipefail

EXPECTED_FPR=09BB309D68C53764893A8942A9DC26A6A93007F1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
KEY_FILE=$ROOT/keys/${EXPECTED_FPR}.asc

usage() {
  echo "usage: $0 [--tamper-check] [<file.yml> ...]" >&2
  exit 2
}

tamper_check=0
files=()
for arg in "$@"; do
  case "$arg" in
    --tamper-check) tamper_check=1 ;;
    -h | --help) usage ;;
    -*) usage ;;
    *) files+=("$arg") ;;
  esac
done

[[ -f "$KEY_FILE" ]] || {
  echo "missing tracked public key: $KEY_FILE" >&2
  exit 2
}

cleanup() {
  if [[ -n "${GNUPGHOME:-}" && -d "$GNUPGHOME" ]]; then
    rm -rf "$GNUPGHOME"
  fi
}

GNUPGHOME=$(mktemp -d)
export GNUPGHOME
chmod 700 "$GNUPGHOME"
trap cleanup EXIT

gpg --batch --import "$KEY_FILE" >/dev/null 2>&1
imported=$(
  gpg --batch --with-colons --list-keys |
    awk -F: '$1 == "fpr" { print $10; exit }'
)
if [[ "$imported" != "$EXPECTED_FPR" ]]; then
  echo "imported primary fingerprint ${imported:-<none>} != $EXPECTED_FPR" >&2
  exit 1
fi

verify_one() {
  local file=$1
  local asc=${file}.asc
  [[ -f "$file" && "$file" == *.yml ]] || {
    echo "Expected an existing .yml file: $file" >&2
    return 1
  }
  [[ -f "$asc" ]] || {
    echo "missing signature: $asc" >&2
    return 1
  }
  local status primary
  if ! status=$(gpg --batch --status-fd 1 --verify "$asc" "$file" 2>/dev/null); then
    echo "bad or untrusted signature: $file" >&2
    return 1
  fi
  primary=$(
    printf '%s\n' "$status" |
      awk '/^\[GNUPG:\] VALIDSIG / { print $12; exit }'
  )
  if [[ "$primary" != "$EXPECTED_FPR" ]]; then
    echo "wrong signer primary ${primary:-<none>} for $file" >&2
    return 1
  fi
  printf 'ok: %s\n' "$file"
}

if ((tamper_check)); then
  source_file=${files[0]:-}
  if [[ -z "$source_file" ]]; then
    shopt -s nullglob
    root_files=("$ROOT"/*.yml)
    ((${#root_files[@]})) || {
      echo "no root .yml files for tamper check" >&2
      exit 2
    }
    source_file=${root_files[0]}
  fi
  [[ -f "$source_file" && -f "$source_file.asc" ]] || {
    echo "tamper check needs $source_file and $source_file.asc" >&2
    exit 2
  }
  work=$(mktemp -d)
  trap 'rm -rf "$work"; cleanup' EXIT
  base=$(basename "$source_file")
  cp "$source_file" "$work/$base"
  cp "$source_file.asc" "$work/$base.asc"
  printf '\n# tampered\n' >>"$work/$base"
  if verify_one "$work/$base"; then
    echo "tampered copy unexpectedly verified: $work/$base" >&2
    exit 1
  fi
  echo "ok: tampered copy rejected"
  exit 0
fi

if ((${#files[@]} == 0)); then
  shopt -s nullglob
  files=("$ROOT"/*.yml)
fi
((${#files[@]})) || {
  echo "no .yml files to verify" >&2
  exit 2
}

for file in "${files[@]}"; do
  verify_one "$file"
done
