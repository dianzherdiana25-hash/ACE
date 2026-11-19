"""Unit & adversarial tests untuk tools/repo_status_dashboard_v3.py (G1)."""
from __future__ import annotations

import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from tools import repo_status_dashboard_v3 as v3

REPO_ROOT = Path(__file__).resolve().parents[1]


class TestRepoStatusDashboardV3(unittest.TestCase):
    def test_01_empty_repo_reports_source_not_present_honestly_with_zero_hardcoding(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "empty_repo"
            root.mkdir()
            state = v3.collect_v3_status(root)
            self.assertEqual(state["schema"], v3.DASHBOARD_V3_SCHEMA)
            self.assertEqual(state["summary"]["gate_count"], 0)
            self.assertEqual(state["summary"]["corpus_count"], 0)
            self.assertEqual(state["summary"]["organ_count"], 0)
            self.assertIsNone(state["summary"]["storage_debt_files"])
            self.assertEqual(state["sources_status"]["organ_slate"], v3.SOURCE_NOT_PRESENT)
            self.assertEqual(state["sources_status"]["stage"], v3.SOURCE_NOT_PRESENT)
            self.assertEqual(state["sources_status"]["daily_digest"], v3.SOURCE_NOT_PRESENT)

            html_text = v3.render_v3_html(state)
            self.assertIn(v3.SOURCE_NOT_PRESENT, html_text)
            self.assertIn('<div class="v" id="stat-gates">0</div>', html_text)
            self.assertIn('<div class="v" id="stat-storage-debt">SOURCE_NOT_PRESENT</div>', html_text)
            self.assertNotIn("https://", html_text)
            self.assertNotIn("http://", html_text)

    def test_02_rich_fixture_auto_storage_debt_organ_slate_and_xss_safety(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            repo = base / "repo"
            (repo / "docs").mkdir(parents=True)
            (repo / "handover").mkdir(parents=True)
            (repo / "tools").mkdir(parents=True)
            subprocess.run(["git", "-C", str(repo), "init", "-b", "main"], check=True, capture_output=True)
            subprocess.run(["git", "-C", str(repo), "config", "user.name", "U"], check=True, capture_output=True)
            subprocess.run(["git", "-C", str(repo), "config", "user.email", "u@e.com"], check=True, capture_output=True)

            (repo / "docs" / "EVO_0007_GATES.md").write_text("- G0: PASS\n- G3: MEASURED — SPECIALIZATION\n", encoding="utf-8")
            (repo / "handover" / "BRAIN_SLATE_V2_DEPLOYMENT_20261116.md").write_text(
                "| unit | organ | model | port |\n|---|---|---|---|\n| ace-front | front brain | Qwen3.5-4B | 8001 |\n| ace-coder | coder | qwen2.5-coder-7b | 8002 |\n",
                encoding="utf-8",
            )
            (repo / "handover" / "SAMPLE_CORPUS.jsonl").write_text('{"id":"1","task_kind":"code"}\n', encoding="utf-8")
            (repo / "tools" / "alpha.py").write_text('"""Alat uji."""\nX = 1\n', encoding="utf-8")
            subprocess.run(["git", "-C", str(repo), "add", "."], check=True, capture_output=True)
            subprocess.run(["git", "-C", str(repo), "commit", "-m", "init"], check=True, capture_output=True)
            # Tambahkan 2 berkas untracked -> storage debt dinamis = 2
            (repo / "pending1.txt").write_text("a", encoding="utf-8")
            (repo / "pending2.txt").write_text("b", encoding="utf-8")

            digest_f = base / "digest.json"
            digest_f.write_text(json.dumps({"schema": "ace.daily-digest.v1", "summary": {"commit_count": 1}}), encoding="utf-8")
            hb_f = base / "hb.json"
            hb_f.write_text(json.dumps({"note": "</script><script>alert(1)</script>"}), encoding="utf-8")

            out_html = base / "dash_v3.html"
            with mock.patch.object(socket, "create_connection", side_effect=AssertionError("offline")):
                rc = v3.main(
                    [
                        "--root",
                        str(repo),
                        "--auto-storage-debt",
                        "--digest-file",
                        str(digest_f),
                        "--heartbeat-file",
                        str(hb_f),
                        "--output",
                        str(out_html),
                    ]
                )
            self.assertEqual(rc, 0)
            html_text = out_html.read_text(encoding="utf-8")
            self.assertIn('<div class="v" id="stat-gates">2</div>', html_text)
            self.assertIn('<div class="v" id="stat-organs">2</div>', html_text)
            self.assertIn('<div class="v" id="stat-storage-debt">2</div>', html_text)
            self.assertIn("Qwen3.5-4B", html_text)
            self.assertIn("search-input", html_text)
            self.assertIn("tab-btn", html_text)
            self.assertNotIn("</script><script>alert(1)</script>", html_text)
            self.assertIn("&lt;/script&gt;&lt;script&gt;alert(1)&lt;/script&gt;", html_text)

    def test_03_live_repo_scan_and_error_handling_exit_2(self) -> None:
        state = v3.collect_v3_status(REPO_ROOT)
        self.assertGreater(state["summary"]["gate_count"], 0)
        self.assertGreater(state["summary"]["tool_count"], 0)
        self.assertEqual(state["sources_status"]["organ_slate"], "LOADED")
        self.assertGreaterEqual(state["summary"]["organ_count"], 3)

        rc_missing = v3.main(["--root", "/tmp/does_not_exist_ace_v3"])
        self.assertEqual(rc_missing, 2)

        with tempfile.TemporaryDirectory() as tmp:
            debt = Path(tmp) / "debt.json"
            debt.write_text("{}", encoding="utf-8")
            with self.assertRaises(ValueError):
                v3.collect_v3_status(REPO_ROOT, storage_debt_file=debt, auto_storage_debt=True)


if __name__ == "__main__":
    unittest.main()
