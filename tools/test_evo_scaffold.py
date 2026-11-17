#!/usr/bin/env python3
"""Unit tests untuk tools/evo_scaffold.py (WS-F #16)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools import evo_scaffold


class TestEvoScaffold(unittest.TestCase):
    def test_creates_three_scaffold_artifacts_and_prevents_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "evo_0008"
            report = evo_scaffold.scaffold_evo(
                evo_id="EVO_0008",
                out_dir=out_dir,
                title="Uji distilasi pola multi-lengan",
                author="Ian",
                date_str="2026-11-17",
                claim="Lengan ter-distilasi mengungguli baseline pada korpus probe.",
            )

            self.assertEqual(report["schema"], "ace.evo-scaffold.v1")
            prereg = Path(report["files"]["preregistration_md"])
            manifest = Path(report["files"]["stage_manifest_json"])
            hook = Path(report["files"]["census_hook_json"])

            self.assertTrue(prereg.is_file())
            self.assertTrue(manifest.is_file())
            self.assertTrue(hook.is_file())

            md_text = prereg.read_text(encoding="utf-8")
            self.assertIn("# PREREGISTRASI EVO_0008 — DRAF", md_text)
            self.assertIn("## §1 Klaim yang diuji", md_text)
            self.assertIn("## §5 Ikatan tetap", md_text)

            manifest_data = json.loads(manifest.read_text(encoding="utf-8"))
            self.assertEqual(manifest_data["schema"], "ace.stage-verify.v1")
            self.assertEqual(manifest_data["files"], [])

            hook_data = json.loads(hook.read_text(encoding="utf-8"))
            self.assertEqual(hook_data["schema"], "ace.evo-census-hook.v1")
            self.assertIs(hook_data["enabled"], False)
            self.assertIs(hook_data["fail_closed"], True)
            self.assertIs(hook_data["writeback_during_probe"], False)

            with self.assertRaises(evo_scaffold.EvoScaffoldError):
                evo_scaffold.scaffold_evo(evo_id="EVO_0008", out_dir=out_dir)

            report_forced = evo_scaffold.scaffold_evo(
                evo_id="EVO_0008",
                out_dir=out_dir,
                date_str="2026-11-18",
                force=True,
            )
            self.assertEqual(report_forced["created_date"], "2026-11-18")

    def test_cli_validation_and_bad_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "evo_0009"
            rc = evo_scaffold.main(
                [
                    "--evo-id",
                    "EVO_0009",
                    "--out-dir",
                    str(out_dir),
                    "--date",
                    "2026-11-17",
                    "--arms",
                    "SEEDED",
                    "KOSONG",
                    "RANDOM",
                ]
            )
            self.assertEqual(rc, 0)
            hook = json.loads((out_dir / "census_hook.json").read_text(encoding="utf-8"))
            self.assertEqual(hook["arms"], ["SEEDED", "KOSONG", "RANDOM"])

            rc_bad_id = evo_scaffold.main(["--evo-id", "../bad", "--out-dir", tmp])
            self.assertEqual(rc_bad_id, 2)

            rc_bad_band = evo_scaffold.main(
                ["--evo-id", "EVO_0010", "--out-dir", tmp, "--min-score", "80", "--max-score", "40"]
            )
            self.assertEqual(rc_bad_band, 2)


if __name__ == "__main__":
    unittest.main()
