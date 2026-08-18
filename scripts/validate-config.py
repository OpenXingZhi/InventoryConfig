#!/usr/bin/env python3
"""Validate Inventory configuration YAML with the repository JSON Schema."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from inventory_config import ConfigError, check_repository, validate_file

ROOT = Path(__file__).resolve().parent.parent


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "files",
        nargs="*",
        type=Path,
        help="YAML files to validate",
    )
    parser.add_argument(
        "--require-filename-sn",
        action="store_true",
        help="Require <ANDROID_ID>.yml to match license.sn",
    )
    parser.add_argument(
        "--check-repo",
        action="store_true",
        help="Validate repository layout plus every YAML file",
    )
    args = parser.parse_args(argv)

    try:
        if args.check_repo:
            validated = check_repository(ROOT)
            print(f"ok: repository layout and {len(validated)} YAML file(s)")
        if not args.files and not args.check_repo:
            parser.error("provide files or --check-repo")
        for path in args.files:
            validate_file(path, require_filename_sn=args.require_filename_sn)
            print(f"ok: {path}")
    except ConfigError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
