"""Fixture per bentuk klaim prosa yang disetujui & audit dokumen historis (Garis A3 Tranche 2)."""
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from tools._director_sources import GitSnapshot
from tools.director_asset_check import verify_assets
from tools.director_prose_audit import (
    PROSE_AUDIT_SCHEMA,
    audit_historical_artifact,
    audit_historical_prose,
)


TOOLS = Path(__file__).resolve().parent
REPO_ROOT = TOOLS.parent


class DirectorHistoricalShapeFixturesTests(unittest.TestCase):
    def _git_fixture(self, files: dict[str, str]) -> GitSnapshot:
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        subprocess.check_output(["git", "-C", str(root), "init", "-q"], text=True)
        subprocess.check_output(["git", "-C", str(root), "config", "core.hooksPath", "/dev/null"], text=True)
        for rel, content in files.items():
            p = root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
        subprocess.check_output(["git", "-C", str(root), "add", "."], text=True)
        subprocess.check_output(
            [
                "git",
                "-C",
                str(root),
                "-c",
                "user.name=Fixture",
                "-c",
                "user.email=fixture@example.invalid",
                "-c",
                "commit.gpgsign=false",
                "commit",
                "-qm",
                "fixture",
            ],
            text=True,
        )
        return GitSnapshot(root)

    def test_fixture_shape_1_relative_markdown_links(self):
        repo = self._git_fixture({
            "code/ace_operational/store.py": "def load(): pass\n",
            "handover/VERDICT.md": (
                "Lihat [store module](../code/ace_operational/store.py#L1) "
                "dan [escaped link](../../outside.py).\n"
            ),
        })
        rows = verify_assets(repo, "handover/VERDICT.md")["assets"]
        files = {row["target"]: row["status"] for row in rows if row["kind"] == "file"}
        self.assertEqual(files.get("code/ace_operational/store.py"), "verified")
        # Escaping relative path must never silently pass as verified inside repo
        self.assertNotIn("outside.py", [r["target"] for r in rows if r["status"] == "verified"])

    def test_fixture_shape_2_status_constants_and_hex_shas_not_misclassified_as_modules(self):
        repo = self._git_fixture({
            "code/ace_autonomy/test_core.py": "def test_ok(): pass\n",
            "docs/validation/REV.md": (
                "Status: `VERIFIED_OFFLINE_CLOSED_LOOP` (`BLOCK_RELEASE`, commit `4b8226916dfa`).\n"
                "Modul uji nyata: `ace_autonomy.test_core`.\n"
            ),
        })
        assets = verify_assets(repo, "docs/validation/REV.md")["assets"]
        self.assertEqual(
            [(r["kind"], r["target"], r["status"]) for r in assets],
            [("module", "ace_autonomy.test_core", "verified")],
        )
        prose = audit_historical_prose(repo.read_text("docs/validation/REV.md"), product_path="docs/validation/REV.md")
        self.assertEqual(
            [(t["kind"], t["token"]) for t in prose["symbol_tokens"]],
            [
                ("status_constant", "VERIFIED_OFFLINE_CLOSED_LOOP"),
                ("status_constant", "BLOCK_RELEASE"),
                ("hex_digest", "4b8226916dfa"),
            ],
        )

    def test_fixture_shape_3_ratio_claims_with_decimal_or_percent(self):
        md = (
            "Progresi: `G0: 4/16 (25.0%)` -> `G3: 16/16 (100.0%)`.\n"
            "Replay 552/576 dan total 7/8 = 0.875.\n"
        )
        prose = audit_historical_prose(md)
        ratios = [c for c in prose["approved_claims"] if c["shape"] == "ratio_claim"]
        self.assertEqual([r["value"] for r in ratios], ["4/16", "16/16", "552/576", "7/8"])
        self.assertEqual(ratios[0].get("stated_percent"), "25.0")
        self.assertEqual(ratios[3].get("stated_decimal"), "0.875")

    def test_fixture_shape_4_kv_metric_assignments(self):
        md = "- Selesai dengan `forgetting_count = 0`, `preaudit_exit_code = 0`, N=8, macro_hits=2.\n"
        prose = audit_historical_prose(md)
        kvs = [c for c in prose["approved_claims"] if c["shape"] == "kv_metric_claim"]
        self.assertEqual(
            [(c["label"], c["value"]) for c in kvs],
            [("forgetting_count", "0"), ("preaudit_exit_code", "0"), ("N", "8"), ("macro_hits", "2")],
        )

    def test_fixture_shape_5_table_numeric_cells(self):
        md = (
            "| Subsystem | Modul | Jumlah Tes | Status | Durasi |\n"
            "|---|---|---|---|---|\n"
            "| BEFORE (terkoreksi) | 3/4 | 4/4 | 7/8 = 0.875 |\n"
            "| **TOTAL** | **18 Modules** | **179** | **ALL PASS** | **257.98s** |\n"
        )
        prose = audit_historical_prose(md)
        cells = [(c["shape"], c.get("label"), c["value"]) for c in prose["approved_claims"]]
        self.assertIn(("ratio_claim", "BEFORE (terkoreksi)", "3/4"), cells)
        self.assertIn(("ratio_claim", "BEFORE (terkoreksi)", "7/8"), cells)
        self.assertIn(("table_numeric_cell", "TOTAL", "18 Modules"), cells)
        self.assertIn(("table_numeric_cell", "TOTAL", "179"), cells)
        self.assertIn(("table_numeric_cell", "TOTAL", "257.98s"), cells)

    def test_fixture_shape_6_percentage_and_multiplier_claims(self):
        md = "Kompresi: `2.225x` MDL dan pengurangan pencarian `45.05%`.\n"
        prose = audit_historical_prose(md)
        pcts = [c for c in prose["approved_claims"] if c["shape"] == "percent_or_multiplier_claim"]
        self.assertEqual([(c["value"], c["unit"]) for c in pcts], [("2.225", "x"), ("45.05", "%")])

    def test_fixture_shape_7_free_prose_flagged_as_unrecognized_not_silently_dropped(self):
        md = (
            "```\n"
            "inside_fence = 99\n"
            "```\n"
            "Snapshot awal mencakup 89 ref branch dan 63 PR terbuka.\n"
        )
        prose = audit_historical_prose(md)
        self.assertEqual(prose["approved_claims"], [])
        self.assertEqual(len(prose["unrecognized_prose"]), 1)
        self.assertEqual(prose["unrecognized_prose"][0]["shape"], "unrecognized_prose")
        self.assertEqual(prose["unrecognized_prose"][0]["numbers"], ["89", "63"])

    def test_real_repo_historical_artifacts_map_claims_without_false_module_errors(self):
        repo = GitSnapshot(REPO_ROOT, "HEAD")
        closed_loop = "docs/validation/ACE_OAIE_CLOSED_LOOP_VERDICT_20261114.md"
        evo5 = "handover/EVO_0005_KONSOLIDASI_20261116.md"
        stage2 = "handover/PROPOSER_STAGE2_CONSTITUTION_VERDICT_20261114.md"

        res_closed = audit_historical_artifact(repo, closed_loop)
        self.assertEqual(res_closed["schema"], PROSE_AUDIT_SCHEMA)
        self.assertEqual(res_closed["asset_summary"]["counts_by_status"], {"verified": 15})
        self.assertGreaterEqual(res_closed["summary"]["counts_by_shape"]["ratio_claim"], 8)
        self.assertGreaterEqual(res_closed["summary"]["counts_by_shape"]["kv_metric_claim"], 5)

        res_evo5 = audit_historical_artifact(repo, evo5)
        self.assertEqual(res_evo5["asset_summary"]["counts_by_status"].get("not_found", 0), 0)
        self.assertGreaterEqual(res_evo5["summary"]["counts_by_shape"]["ratio_claim"], 9)

        res_stage2 = audit_historical_artifact(repo, stage2)
        self.assertEqual(res_stage2["asset_summary"]["counts_by_status"].get("not_found", 0), 0)

        cli = subprocess.run(
            [sys.executable, str(TOOLS / "director_prose_audit.py"), evo5, "--repo", str(REPO_ROOT)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(cli.returncode, 0, cli.stderr)
        payload = json.loads(cli.stdout)
        self.assertEqual(payload["product"], evo5)


if __name__ == "__main__":
    unittest.main()
