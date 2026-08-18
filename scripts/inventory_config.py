#!/usr/bin/env python3
"""Parse and validate Inventory signed configuration documents.

Uses only the Python standard library. The JSON Schema file is the field
source of truth; this module implements the subset needed to enforce it
without third-party packages.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ANDROID_ID = re.compile(r"^[0-9A-F]{16}$")
RUNTIME_NAME = re.compile(r"^[0-9A-F]{16}\.yml$")
ISO_DATE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
SECRET_KEY = re.compile(
    r"^(token|secret|privatekey|password|authorizationcode|valid_hash)$",
    re.IGNORECASE,
)
FORBIDDEN_RUNTIME_NAMES = {
    "default.yml",
    "DEFAULT.yml",
    "any.yml",
    "all.yml",
    "wildcard.yml",
    "*.yml",
}

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schema" / "inventory-config.schema.json"


class ConfigError(ValueError):
    """A configuration document or repository layout error."""


def load_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def parse_yaml(text: str) -> Any:
    """Parse the constrained YAML subset used by Inventory device files."""
    if "\t" in text:
        raise ConfigError("Tabs are not allowed in configuration YAML.")
    lines = text.splitlines()
    root, index = _parse_mapping(lines, 0, 0, allow_empty=True)
    if index != len(lines):
        raise ConfigError(f"Unexpected content at line {index + 1}.")
    if not isinstance(root, dict):
        raise ConfigError("Document root must be a mapping.")
    return root


def _parse_mapping(
    lines: list[str], start: int, indent: int, *, allow_empty: bool
) -> tuple[dict[str, Any], int]:
    mapping: dict[str, Any] = {}
    index = start
    saw_entry = False
    while index < len(lines):
        raw = lines[index]
        stripped = raw.split("#", 1)[0].rstrip()
        if not stripped:
            index += 1
            continue
        current = len(raw) - len(raw.lstrip(" "))
        if current < indent:
            break
        if current > indent:
            raise ConfigError(f"Unexpected indent at line {index + 1}.")
        if stripped.startswith("- "):
            raise ConfigError(f"Sequences are not allowed at line {index + 1}.")
        if ":" not in stripped:
            raise ConfigError(f"Expected key: value at line {index + 1}.")
        key, _, remainder = stripped.partition(":")
        key = key.strip()
        if not key or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            raise ConfigError(f"Invalid key {key!r} at line {index + 1}.")
        if key in mapping:
            raise ConfigError(f"Duplicate key {key!r} at line {index + 1}.")
        remainder = remainder.strip()
        index += 1
        if remainder:
            mapping[key] = _parse_scalar(remainder, index)
        else:
            child_indent = _next_indent(lines, index)
            if child_indent is None or child_indent <= indent:
                raise ConfigError(f"Missing value for {key!r} at line {index}.")
            mapping[key], index = _parse_mapping(
                lines, index, child_indent, allow_empty=False
            )
        saw_entry = True
    if not saw_entry and not allow_empty:
        raise ConfigError("Expected a nested mapping.")
    return mapping, index


def _next_indent(lines: list[str], start: int) -> int | None:
    for raw in lines[start:]:
        stripped = raw.split("#", 1)[0].rstrip()
        if not stripped:
            continue
        return len(raw) - len(raw.lstrip(" "))
    return None


def _parse_scalar(text: str, line_no: int) -> Any:
    if text in {"&", "*"} or text.startswith("&") or text.startswith("*"):
        raise ConfigError(f"YAML anchors and aliases are not allowed at line {line_no}.")
    if text.startswith("!!"):
        raise ConfigError(f"YAML tags are not allowed at line {line_no}.")
    if text[0] in "{[":
        raise ConfigError(f"Flow collections are not allowed at line {line_no}.")
    if text[0] in "|>":
        raise ConfigError(f"Multiline scalars are not allowed at line {line_no}.")
    if text[0] in "\"'":
        return _parse_quoted(text, line_no)
    lowered = text.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered in {"null", "~"}:
        return None
    if re.fullmatch(r"-?0|[1-9][0-9]*", text):
        return int(text)
    if re.fullmatch(r"-?(?:0|[1-9][0-9]*)\.[0-9]+", text):
        raise ConfigError(f"Floating-point values are not allowed at line {line_no}.")
    if any(ch in text for ch in ":#{}[],&*!|>%@`"):
        raise ConfigError(
            f"Unquoted scalar {text!r} at line {line_no} contains reserved characters."
        )
    return text


def _parse_quoted(text: str, line_no: int) -> str:
    quote = text[0]
    if quote not in {"'", '"'} or len(text) < 2 or text[-1] != quote:
        raise ConfigError(f"Unterminated quoted string at line {line_no}.")
    inner = text[1:-1]
    if quote == "'":
        return inner.replace("''", "'")
    out: list[str] = []
    escaped = False
    for char in inner:
        if escaped:
            escapes = {"n": "\n", "t": "\t", '"': '"', "\\": "\\"}
            if char not in escapes:
                raise ConfigError(f"Unsupported escape at line {line_no}.")
            out.append(escapes[char])
            escaped = False
        elif char == "\\":
            escaped = True
        else:
            out.append(char)
    if escaped:
        raise ConfigError(f"Unterminated escape at line {line_no}.")
    return "".join(out)


def validate_schema(instance: Any, schema: dict[str, Any] | None = None) -> None:
    validate_against(instance, schema or load_schema(), "$")


def validate_against(instance: Any, schema: dict[str, Any], path: str) -> None:
    expected = schema.get("type")
    if expected is not None and not _type_matches(instance, expected):
        raise ConfigError(f"{path}: expected {expected}, got {_json_type(instance)}.")
    if "enum" in schema and instance not in schema["enum"]:
        raise ConfigError(f"{path}: {instance!r} is not one of {schema['enum']}.")
    if "const" in schema and instance != schema["const"]:
        raise ConfigError(f"{path}: expected {schema['const']!r}.")
    if isinstance(instance, str):
        if "minLength" in schema and len(instance) < schema["minLength"]:
            raise ConfigError(f"{path}: shorter than minLength {schema['minLength']}.")
        if "maxLength" in schema and len(instance) > schema["maxLength"]:
            raise ConfigError(f"{path}: longer than maxLength {schema['maxLength']}.")
        pattern = schema.get("pattern")
        if pattern and re.search(pattern, instance) is None:
            raise ConfigError(f"{path}: {instance!r} does not match {pattern}.")
    if isinstance(instance, int) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            raise ConfigError(f"{path}: {instance} is below minimum {schema['minimum']}.")
        if "exclusiveMinimum" in schema and instance <= schema["exclusiveMinimum"]:
            raise ConfigError(
                f"{path}: {instance} is not greater than {schema['exclusiveMinimum']}."
            )
    if isinstance(instance, dict):
        required = schema.get("required", [])
        for key in required:
            if key not in instance:
                raise ConfigError(f"{path}: missing required property {key!r}.")
        properties = schema.get("properties", {})
        additional = schema.get("additionalProperties", True)
        for key, value in instance.items():
            child = f"{path}.{key}" if path != "$" else key
            if key in properties:
                validate_against(value, properties[key], child)
            elif additional is False:
                raise ConfigError(f"{path}: additional property {key!r} is not allowed.")
            elif isinstance(additional, dict):
                validate_against(value, additional, child)


def _type_matches(instance: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(instance, dict)
    if expected == "string":
        return isinstance(instance, str)
    if expected == "integer":
        return isinstance(instance, int) and not isinstance(instance, bool)
    if expected == "boolean":
        return isinstance(instance, bool)
    if expected == "null":
        return instance is None
    raise ConfigError(f"Unsupported schema type {expected!r}.")


def _json_type(instance: Any) -> str:
    if instance is None:
        return "null"
    if isinstance(instance, bool):
        return "boolean"
    if isinstance(instance, int):
        return "integer"
    if isinstance(instance, str):
        return "string"
    if isinstance(instance, dict):
        return "object"
    return type(instance).__name__


def collect_keys(instance: Any) -> list[str]:
    keys: list[str] = []
    if isinstance(instance, dict):
        for key, value in instance.items():
            keys.append(key)
            keys.extend(collect_keys(value))
    return keys


def reject_secrets(instance: Any) -> None:
    for key in collect_keys(instance):
        if SECRET_KEY.fullmatch(key):
            raise ConfigError(f"Refusing configuration containing secret-like key {key!r}.")


def validate_document(document: dict[str, Any]) -> None:
    reject_secrets(document)
    validate_schema(document)
    expire = document.get("license", {}).get("expire")
    if isinstance(expire, str):
        _assert_real_date(expire)


def _assert_real_date(value: str) -> None:
    if not ISO_DATE.fullmatch(value):
        raise ConfigError(f"license.expire {value!r} is not YYYY-MM-DD.")
    year, month, day = (int(part) for part in value.split("-"))
    if month < 1 or month > 12 or day < 1 or day > 31:
        raise ConfigError(f"license.expire {value!r} is not a real calendar date.")
    lengths = [31, 29 if _is_leap(year) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    if day > lengths[month - 1]:
        raise ConfigError(f"license.expire {value!r} is not a real calendar date.")


def _is_leap(year: int) -> bool:
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def android_id_from_filename(path: Path) -> str:
    name = path.name
    if name in FORBIDDEN_RUNTIME_NAMES or name.lower() in {
        item.lower() for item in FORBIDDEN_RUNTIME_NAMES
    }:
        raise ConfigError(f"{name} is a wildcard/default name and is not allowed.")
    if not RUNTIME_NAME.fullmatch(name):
        raise ConfigError(
            f"{name} is not <ANDROID_ID>.yml with a 16-digit uppercase hex Android ID."
        )
    return path.stem


def validate_file(path: Path, *, require_filename_sn: bool = False) -> dict[str, Any]:
    if not path.is_file():
        raise ConfigError(f"{path} is not a file.")
    if path.suffix != ".yml":
        raise ConfigError(f"{path} is not a .yml file.")
    document = parse_yaml(path.read_text(encoding="utf-8"))
    validate_document(document)
    if require_filename_sn:
        android_id = android_id_from_filename(path)
        serial = document["license"]["sn"]
        if serial != android_id:
            raise ConfigError(
                f"license.sn {serial} does not match filename Android ID {android_id}."
            )
    return document


def bump_revision(path: Path) -> int:
    document = validate_file(path, require_filename_sn=True)
    current = document["revision"]
    nxt = current + 1
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    replaced = False
    updated: list[str] = []
    for line in lines:
        if not replaced and re.fullmatch(r"revision:\s*-?[0-9]+\s*(#.*)?\n?", line):
            suffix = ""
            if line.endswith("\n"):
                suffix = "\n"
                if line.endswith("\r\n"):
                    suffix = "\r\n"
            comment = ""
            if "#" in line:
                comment = " #" + line.split("#", 1)[1].rstrip("\r\n")
            updated.append(f"revision: {nxt}{comment}{suffix}")
            replaced = True
        else:
            updated.append(line)
    if not replaced:
        raise ConfigError("Could not find a top-level integer revision line to increment.")
    path.write_text("".join(updated), encoding="utf-8")
    return nxt


def iter_yaml_files(root: Path) -> list[Path]:
    roots = [root, root / "examples", root / "fixtures"]
    files: list[Path] = []
    for base in roots:
        if not base.exists():
            continue
        if base == root:
            files.extend(path for path in base.glob("*.yml") if path.is_file())
            continue
        files.extend(
            path
            for path in base.rglob("*.yml")
            if path.is_file() and ".git" not in path.parts
        )
    return sorted(set(files))


def check_repository(root: Path) -> list[Path]:
    validated: list[Path] = []
    for path in iter_yaml_files(root):
        relative = path.relative_to(root)
        if path.name in FORBIDDEN_RUNTIME_NAMES or path.stem.lower() in {
            "default",
            "any",
            "all",
            "wildcard",
        }:
            raise ConfigError(f"{relative} is a wildcard/default configuration and is forbidden.")
        if len(relative.parts) == 1:
            if not RUNTIME_NAME.fullmatch(path.name):
                raise ConfigError(
                    f"{relative} is at the repository root but is not a runtime <ANDROID_ID>.yml."
                )
            validate_file(path, require_filename_sn=True)
            signature = path.with_name(path.name + ".asc")
            if not signature.is_file():
                raise ConfigError(f"{relative} is missing detached signature {signature.name}.")
            validated.append(path)
            continue
        if relative.parts[0] not in {"examples", "fixtures"}:
            raise ConfigError(
                f"{relative} is not a runtime, example, or fixture configuration."
            )
        if relative.parts[:3] == ("fixtures", "schema", "invalid"):
            continue
        require_sn = relative.parts[0] == "examples"
        validate_file(path, require_filename_sn=require_sn)
        validated.append(path)
    return validated
