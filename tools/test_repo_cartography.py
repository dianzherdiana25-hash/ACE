"""Unit & adversarial tests untuk tools/repo_cartography.py (G3)."""
from __future__ import annotations

import json
from pathlib import Path
import socket
import tempfile
import unittest
from unittest import mock

from tools import repo_cartography as rc

REPO_ROOT = Path(__file__).resolve().parents[1]


class TestRepoCartography(unittest.TestCase):
    def test_01_detects_cross_subsystem_edges_cycle_and_protected_zone_without_import(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            (repo / "code" / "alpha").mkdir(parents=True)
            (repo / "code" / "beta").mkdir(parents=True)
            (repo / "code" / "ace_evaluator").mkdir(parents=True)
            (repo / "handover").mkdir(parents=True)
            (repo / "tools").mkdir(parents=True)

            # Sengaja tanam side-effect exception di tingkat modul agar terbukti tidak diimpor
            (repo / "code" / "alpha" / "mod_a.py").write_text(
                'import beta.mod_b\nraise RuntimeError("MUST NOT IMPORT")\n',
                encoding="utf-8",
            )
            (repo / "code" / "beta" / "mod_b.py").write_text(
                "from alpha import mod_a\nX = 1\n",
                encoding="utf-8",
            )
            (repo / "code" / "ace_evaluator" / "sealed.py").write_text(
                '"""Sealed."""\n',
                encoding="utf-8",
            )
            (repo / "tools" / "cli_a.py").write_text(
                "import alpha.mod_a\n",
                encoding="utf-8",
            )
            (repo / "handover" / "CORPUS.jsonl").write_text("{}\n", encoding="utf-8")

            with mock.patch.object(socket, "create_connection", side_effect=AssertionError("offline")):
                carto = rc.build_cartography(repo)

            self.assertEqual(carto["schema"], rc.CARTOGRAPHY_SCHEMA)
            zones = {s["subsystem"]: s["zone"] for s in carto["subsystems"]}
            self.assertEqual(zones["code/ace_evaluator"], "PROTECTED_INSTRUMENT")
            self.assertEqual(zones["handover"], "FROZEN_CORPUS_SPEC")
            self.assertEqual(zones["tools"], "SAFE_WORKSPACE")
            # Siklus alpha <-> beta harus terdeteksi
            self.assertIn(["code/alpha", "code/beta"], carto["cycles"])

            md = rc.render_markdown(carto)
            self.assertIn("```mermaid", md)
            self.assertIn("flowchart LR", md)
            self.assertIn("PROTECTED_INSTRUMENT", md)

    def test_02_check_fresh_stale_and_error_handling(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            (repo / "tools").mkdir(parents=True)
            (repo / "tools" / "one.py").write_text('"""Satu."""\n', encoding="utf-8")
            out_md = repo / "docs" / "REPO_CARTOGRAPHY.md"

            self.assertEqual(rc.main(["--root", str(repo), "--output", str(out_md)]), 0)
            self.assertEqual(rc.main(["--root", str(repo), "--check", str(out_md)]), 0)

            (repo / "tools" / "two.py").write_text('"""Dua."""\nimport one\n', encoding="utf-8")
            self.assertEqual(rc.main(["--root", str(repo), "--check", str(out_md)]), 1)
            self.assertEqual(rc.main(["--root", "/tmp/does_not_exist_ace_rc"]), 2)

    def test_03_live_repo_cartography_fresh_and_populated(self) -> None:
        target = REPO_ROOT / "docs" / "REPO_CARTOGRAPHY.md"
        self.assertTrue(target.is_file(), "docs/REPO_CARTOGRAPHY.md harus dibuat dan mutakhir")
        fresh, msg = rc.check_cartography(REPO_ROOT, target)
        self.assertTrue(fresh, msg)

        raw = json.dumps(rc.build_cartography(REPO_ROOT))
        data = json.loads(raw)
        self.assertGreaterEqual(data["summary"]["subsystem_count"], 20)
        self.assertGreater(data["summary"]["total_prod_modules"], 100)
        zones = {s["subsystem"]: s["zone"] for s in data["subsystems"]}
        self.assertEqual(zones["code/ace_evaluator"], "PROTECTED_INSTRUMENT")
        self.assertEqual(zones["code/ace_operational"], "MIXED_PROTECTED")


if __name__ == "__main__":
    unittest.main()
