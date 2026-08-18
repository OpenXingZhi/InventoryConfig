#!/usr/bin/env python3
"""Stdlib tests for the Inventory configuration parser and schema."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from inventory_config import (  # noqa: E402
    ConfigError,
    android_id_from_filename,
    check_repository,
    parse_yaml,
    validate_document,
    validate_file,
)


class ParseYamlTests(unittest.TestCase):
    def test_parses_nested_document(self) -> None:
        document = parse_yaml(
            "revision: 2\n"
            "license:\n"
            "  sn: \"0123456789ABCDEF\"\n"
            "  expire: \"2027-12-31\"\n"
        )
        self.assertEqual(document["revision"], 2)
        self.assertEqual(document["license"]["expire"], "2027-12-31")

    def test_keeps_iso_date_as_string(self) -> None:
        document = parse_yaml("expire: 2027-12-31\n")
        self.assertEqual(document["expire"], "2027-12-31")
        self.assertIsInstance(document["expire"], str)

    def test_rejects_tabs_and_anchors(self) -> None:
        with self.assertRaises(ConfigError):
            parse_yaml("revision:\t1\n")
        with self.assertRaises(ConfigError):
            parse_yaml("license: *reuse\n")


class SchemaTests(unittest.TestCase):
    def test_example_is_valid(self) -> None:
        path = ROOT / "examples" / "0123456789ABCDEF.yml"
        document = validate_file(path, require_filename_sn=True)
        self.assertEqual(document["license"]["sn"], "0123456789ABCDEF")
        self.assertGreaterEqual(document["revision"], 1)

    def test_permanent_license_omits_expire(self) -> None:
        document = validate_file(ROOT / "fixtures" / "schema" / "valid" / "permanent.yml")
        self.assertNotIn("expire", document["license"])

    def test_rejects_session_state(self) -> None:
        with self.assertRaises(ConfigError):
            validate_file(
                ROOT / "fixtures" / "schema" / "invalid" / "session-current-inv.yml"
            )

    def test_rejects_non_iso_expire(self) -> None:
        with self.assertRaises(ConfigError):
            validate_document(
                {
                    "revision": 1,
                    "license": {"sn": "0123456789ABCDEF", "expire": "31/12/2027"},
                    "server": {"url": "https://inventory.example.invalid/"},
                    "reader": {
                        "deviceType": "RPAN",
                        "commType": "Bluetooth",
                        "rfidType": "HF",
                        "dataFormat": "ISO",
                        "checkSecurity": False,
                        "securityType": "AFI_EAS",
                        "afiInLib": "07",
                        "afiOutLib": "C2",
                        "onlyReadBookUid": False,
                    },
                    "display": {"showShelfDescription": False, "sort": "SHELF_AND_CLC"},
                }
            )

    def test_rejects_impossible_date(self) -> None:
        with self.assertRaises(ConfigError):
            validate_document(
                {
                    "revision": 1,
                    "license": {"sn": "0123456789ABCDEF", "expire": "2027-02-30"},
                    "server": {"url": "https://inventory.example.invalid/"},
                    "reader": {
                        "deviceType": "RPAN",
                        "commType": "Bluetooth",
                        "rfidType": "HF",
                        "dataFormat": "ISO",
                        "checkSecurity": False,
                        "securityType": "AFI_EAS",
                        "afiInLib": "07",
                        "afiOutLib": "C2",
                        "onlyReadBookUid": False,
                    },
                    "display": {"showShelfDescription": False, "sort": "SHELF_AND_CLC"},
                }
            )

    def test_rejects_impossible_expire_fixture(self) -> None:
        with self.assertRaises(ConfigError):
            validate_file(
                ROOT / "fixtures" / "schema" / "invalid" / "impossible-expire.yml"
            )

    def test_rejects_missing_reader(self) -> None:
        with self.assertRaises(ConfigError):
            validate_file(ROOT / "fixtures" / "schema" / "invalid" / "missing-reader.yml")

    def test_rejects_missing_display(self) -> None:
        with self.assertRaises(ConfigError):
            validate_file(ROOT / "fixtures" / "schema" / "invalid" / "missing-display.yml")

    def test_rejects_missing_reader_field(self) -> None:
        with self.assertRaises(ConfigError):
            validate_file(
                ROOT / "fixtures" / "schema" / "invalid" / "missing-reader-rfid-type.yml"
            )

    def test_rejects_missing_display_field(self) -> None:
        with self.assertRaises(ConfigError):
            validate_file(
                ROOT / "fixtures" / "schema" / "invalid" / "missing-display-sort.yml"
            )

    def test_schema_fixture_counts(self) -> None:
        valid = sorted(p.name for p in (ROOT / "fixtures" / "schema" / "valid").glob("*.yml"))
        invalid = sorted(
            p.name for p in (ROOT / "fixtures" / "schema" / "invalid").glob("*.yml")
        )
        self.assertEqual(valid, ["permanent.yml", "temporary-full.yml"])
        self.assertEqual(len(invalid), 16)
        self.assertIn("bad-expire.yml", invalid)
        self.assertIn("impossible-expire.yml", invalid)
        self.assertIn("missing-reader.yml", invalid)
        self.assertIn("missing-display.yml", invalid)
        self.assertIn("missing-reader-rfid-type.yml", invalid)
        self.assertIn("missing-display-sort.yml", invalid)


class FilenameTests(unittest.TestCase):
    def test_accepts_uppercase_android_id(self) -> None:
        self.assertEqual(
            android_id_from_filename(Path("0123456789ABCDEF.yml")),
            "0123456789ABCDEF",
        )

    def test_rejects_default_and_lowercase(self) -> None:
        with self.assertRaises(ConfigError):
            android_id_from_filename(Path("default.yml"))
        with self.assertRaises(ConfigError):
            android_id_from_filename(Path("0123456789abcdef.yml"))

    def test_filename_must_match_sn(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "0123456789ABCDEF.yml"
            path.write_text(
                "revision: 1\n"
                "license:\n"
                "  sn: \"DEADBEEFDEADBEEF\"\n"
                "server:\n"
                "  url: \"https://inventory.example.invalid/\"\n"
                "reader:\n"
                "  deviceType: RPAN\n"
                "  commType: Bluetooth\n"
                "  rfidType: HF\n"
                "  dataFormat: ISO\n"
                "  checkSecurity: false\n"
                "  securityType: AFI_EAS\n"
                "  afiInLib: \"07\"\n"
                "  afiOutLib: \"C2\"\n"
                "  onlyReadBookUid: false\n"
                "display:\n"
                "  showShelfDescription: false\n"
                "  sort: SHELF_AND_CLC\n",
                encoding="utf-8",
            )
            with self.assertRaises(ConfigError):
                validate_file(path, require_filename_sn=True)


class RepositoryTests(unittest.TestCase):
    def test_current_repository_is_clean(self) -> None:
        validated = check_repository(ROOT)
        self.assertTrue(any(path.name == "0123456789ABCDEF.yml" for path in validated))
        self.assertFalse(any(len(path.relative_to(ROOT).parts) == 1 for path in validated))


if __name__ == "__main__":
    unittest.main()
