"""Tes jalur tempa perkakas terisolasi: spesifikasi sah lulus vs impor terlarang ditolak (AG81)."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from tools import tool_forge


class ToolForgeTest(unittest.TestCase):
    def test_valid_spec_forges_and_passes_while_forbidden_import_fails_static_audit(self) -> None:
        valid_spec = {
            "name": "normalize_key_toy",
            "origin_gap": "gap-dedup-case-01",
            "io_contract": {
                "inputs": [{"name": "payload", "type": "str | dict"}],
                "output": "normalized str | dict",
            },
            "test_cases": [
                {"input": "  Halo_ACE ", "expected": "halo_ace"},
                {"input": {"Key": "  NILAI "}, "expected": {"Key": "nilai"}},
            ],
        }
        forbidden_spec = {
            "name": "unsafe_shell_toy",
            "origin_gap": "gap-bad-import-02",
            "io_contract": {
                "inputs": [{"name": "payload", "type": "str"}],
                "output": "str",
            },
            "imports": ["subprocess", "autonomous_engine"],
            "test_cases": [{"input": "x", "expected": "x"}],
        }

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            valid_json = root / "valid_spec.json"
            bad_json = root / "bad_spec.json"
            valid_out = root / "valid_adoption.json"
            bad_out = root / "bad_adoption.json"
            forge_dir = root / "sandbox"

            valid_json.write_text(json.dumps(valid_spec), encoding="utf-8")
            bad_json.write_text(json.dumps(forbidden_spec), encoding="utf-8")

            self.assertEqual(
                tool_forge.main(
                    ["--spec", str(valid_json), "--forge-dir", str(forge_dir), "--out", str(valid_out)]
                ),
                0,
            )
            self.assertEqual(
                tool_forge.main(
                    ["--spec", str(bad_json), "--forge-dir", str(forge_dir), "--out", str(bad_out)]
                ),
                1,
            )

            rep_ok = json.loads(valid_out.read_text(encoding="utf-8"))
            rep_bad = json.loads(bad_out.read_text(encoding="utf-8"))

            self.assertTrue((forge_dir / "normalize_key_toy" / "normalize_key_toy.py").is_file())
            self.assertTrue((forge_dir / "normalize_key_toy" / "test_normalize_key_toy.py").is_file())

        self.assertEqual(rep_ok["schema"], tool_forge.SCHEMA)
        self.assertEqual(rep_ok["adoption_verdict"], "approved")
        self.assertTrue(rep_ok["static_audit"]["passed"])
        self.assertTrue(rep_ok["unit_tests"]["executed"])
        self.assertTrue(rep_ok["unit_tests"]["passed"])

        self.assertEqual(rep_bad["adoption_verdict"], "rejected")
        self.assertFalse(rep_bad["static_audit"]["passed"])
        # Karena gagal audit statis, modul berimpor terlarang tidak dieksekusi di tes.
        self.assertFalse(rep_bad["unit_tests"]["executed"])
        self.assertIn("forbidden_import:subprocess", rep_bad["static_audit"]["findings"])
        self.assertIn("forbidden_import:autonomous_engine", rep_bad["static_audit"]["findings"])


if __name__ == "__main__":
    unittest.main()
