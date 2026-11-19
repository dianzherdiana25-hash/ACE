"""Tes fixture untuk tools/director_screen.py (E2 — saringan direktur terpadu)."""
from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest

from tools._director_sources import GitSnapshot
from tools import director_screen as ds
from tools import wiring_audit


class DirectorScreenTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        subprocess.check_output(["git", "-C", str(self.root), "init", "-q"], text=True)
        subprocess.check_output(["git", "-C", str(self.root), "config", "core.hooksPath", "/dev/null"], text=True)

    def _snapshot(self, files: dict[str, object]) -> GitSnapshot:
        for rel, content in files.items():
            p = self.root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(
                content if isinstance(content, str) else json.dumps(content, indent=2),
                encoding="utf-8",
            )
        subprocess.check_output(["git", "-C", str(self.root), "add", "."], text=True)
        subprocess.check_output(
            [
                "git", "-C", str(self.root),
                "-c", "user.name=Fixture",
                "-c", "user.email=fixture@example.invalid",
                "-c", "commit.gpgsign=false",
                "commit", "-qm", "fixture commit",
            ],
            text=True,
        )
        return GitSnapshot(self.root)

    def test_01_clean_product_passes_with_lolos(self) -> None:
        snap = self._snapshot({
            "README.md": "# Produk Uji\n",
            "code/ace_demo/worker.py": "def run_step():\n    return 1\n",
            "metrics.json": {"total": 42},
            "prs.json": {"repository": "demo/ace", "pull_requests": [12]},
            "cycle_01.json": {
                "cycle": 1,
                "status": "accepted",
                "origin": "engine_run",
                "decisions": [{"id": "t-1", "decision": "accepted"}],
            },
            "product.json": {
                "assets": [
                    {"kind": "file", "target": "README.md"},
                    {"kind": "module", "target": "ace_demo.worker"},
                    {"kind": "function", "target": "ace_demo.worker::run_step"},
                    {"kind": "pr", "target": "https://github.com/demo/ace/pull/12"},
                ],
                "numeric_claims": [
                    {"label": "total_metric", "source": "metrics.json", "pointer": "/total", "value": 42},
                ],
            },
        })
        rep = ds.screen_product(snap, "product.json", pr_snapshot_path="prs.json", cycle_paths=["cycle_01.json"])
        self.assertEqual(rep["verdict"], ds.VERDICT_PASS)
        self.assertEqual(rep["summary"]["assets_verified"], 4)
        self.assertEqual(rep["summary"]["claims_verified"], 1)
        self.assertEqual(rep["summary"]["cycles_clean"], 1)
        self.assertEqual(rep["findings"], [])

        out_buf = io.StringIO()
        with contextlib.redirect_stdout(out_buf):
            rc = ds.main([
                "product.json",
                "--repo", str(self.root),
                "--pr-snapshot", "prs.json",
                "--cycle", "cycle_01.json",
                "--format", "markdown",
            ])
        self.assertEqual(rc, 0)
        self.assertIn("LOLOS", out_buf.getvalue())

    def test_02_missing_asset_rejected_with_tolak_and_actionable_finding(self) -> None:
        snap = self._snapshot({
            "code/ace_demo/real_mod.py": "def exist():\n    return True\n",
            "product.json": {
                "assets": [
                    {"kind": "file", "target": "tidak_ada_di_repo.py"},
                    {"kind": "function", "target": "ace_demo.real_mod::khayalan"},
                ],
            },
        })
        rep = ds.screen_product(snap, "product.json")
        self.assertEqual(rep["verdict"], ds.VERDICT_REJECT)
        self.assertEqual(rep["summary"]["blocker_count"], 2)
        targets = {f["target"] for f in rep["findings"]}
        self.assertIn("file:tidak_ada_di_repo.py", targets)
        self.assertIn("function:ace_demo.real_mod::khayalan", targets)
        self.assertTrue(all(f["remediation"] for f in rep["findings"]))

        out_buf = io.StringIO()
        with contextlib.redirect_stdout(out_buf):
            rc = ds.main(["product.json", "--repo", str(self.root)])
        self.assertEqual(rc, 1)

    def test_03_ungrounded_numeric_claim_rejected_with_tolak(self) -> None:
        snap = self._snapshot({
            "README.md": "# Ada\n",
            "metrics.json": {"passed": 10},
            "product.json": {
                "assets": [{"kind": "file", "target": "README.md"}],
                "numeric_claims": [
                    {"label": "inflated_pass", "source": "metrics.json", "pointer": "/passed", "value": 999},
                    {"label": "ghost_pointer", "source": "metrics.json", "pointer": "/not_here", "value": 1},
                ],
            },
        })
        rep = ds.screen_product(snap, "product.json")
        self.assertEqual(rep["verdict"], ds.VERDICT_REJECT)
        self.assertEqual(rep["summary"]["blocker_count"], 2)
        by_target = {f["target"]: f for f in rep["findings"]}
        self.assertEqual(by_target["inflated_pass"]["status"], "mismatch")
        self.assertEqual(by_target["ghost_pointer"]["status"], "not_found")
        self.assertIn("10", by_target["inflated_pass"]["remediation"])

    def test_04_repairable_ambiguity_returns_lolos_dengan_perbaikan_and_strict_fails(self) -> None:
        snap = self._snapshot({
            "README.md": "# Produk\n",
            "cycle_old.json": {"cycle": 1, "status": "accepted"},
            "product.md": "# Klaim\n- rujuk README.md dan #15\n",
        })
        rep = ds.screen_product(snap, "product.md", cycle_paths=["cycle_old.json"])
        self.assertEqual(rep["verdict"], ds.VERDICT_PASS_WITH_FIXES)
        self.assertEqual(rep["summary"]["blocker_count"], 0)
        self.assertGreaterEqual(rep["summary"]["improvement_count"], 2)

        with contextlib.redirect_stdout(io.StringIO()):
            rc_default = ds.main(["product.md", "--repo", str(self.root), "--cycle", "cycle_old.json"])
            rc_strict = ds.main(["product.md", "--repo", str(self.root), "--cycle", "cycle_old.json", "--strict"])
        self.assertEqual(rc_default, 0)
        self.assertEqual(rc_strict, 1)

    def test_05_empty_product_blocked_anti_vacuous_and_all_director_tools_wired(self) -> None:
        snap = self._snapshot({"empty.json": {}})
        rep = ds.screen_product(snap, "empty.json")
        self.assertEqual(rep["verdict"], ds.VERDICT_REJECT)
        self.assertEqual(rep["findings"][0]["status"], "empty_screen_no_verifiable_items")

        with contextlib.redirect_stderr(io.StringIO()):
            rc_bad = ds.main(["missing.json", "--repo", str(self.root)])
        self.assertEqual(rc_bad, 2)

        audit = wiring_audit.audit_wiring(Path(__file__).resolve().parents[1])
        by_path = {m["path"]: m for m in audit["modules"]}
        for path in (
            "tools/director_asset_check.py",
            "tools/director_value_check.py",
            "tools/director_cycle_record.py",
        ):
            self.assertEqual(by_path[path]["status"], "WIRED")
            self.assertIn("tools/director_screen.py", by_path[path]["non_test_callers"])


if __name__ == "__main__":
    unittest.main()
