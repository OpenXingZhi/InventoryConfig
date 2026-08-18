#!/usr/bin/env python3
"""Validate one InventoryConfig YAML file."""

import argparse
import json
import re
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
from ruamel.yaml import YAML

ROOT = Path(__file__).resolve().parent.parent
ANDROID_ID = re.compile(r"^[0-9A-F]{16}$")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("file", type=Path)
    parser.add_argument(
        "--bind-filename",
        action="store_true",
        help="require filename stem to equal license.sn",
    )
    args = parser.parse_args()

    yaml = YAML(typ="safe")
    yaml.allow_duplicate_keys = False
    document = yaml.load(args.file)
    schema = json.loads(
        (ROOT / "schema" / "inventory-config.schema.json").read_text(encoding="utf-8")
    )
    Draft202012Validator.check_schema(schema)

    errors = sorted(
        Draft202012Validator(
            schema,
            format_checker=FormatChecker(),
        ).iter_errors(document),
        key=lambda error: list(error.path),
    )
    if errors:
        raise SystemExit("\n".join(error.message for error in errors))

    if args.bind_filename:
        stem = args.file.stem
        if not ANDROID_ID.fullmatch(stem):
            raise SystemExit("filename must be <16-digit uppercase ANDROID_ID>.yml")
        if document["license"]["sn"] != stem:
            raise SystemExit("filename Android ID must equal license.sn")

    print(f"ok: {args.file}")


if __name__ == "__main__":
    main()
