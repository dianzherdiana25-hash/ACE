"""Uji unit untuk generator dashboard status repo tools/repo_status_dashboard.py."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.repo_status_dashboard import collect_repo_status, render_dashboard_html

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "tools" / "repo_status_dashboard.py"


class RepoStatusDashboardTests(unittest.TestCase):
    """Memastikan seluruh angka dan label pada HTML dibaca dinamis dari fixture."""

    def test_fixture_numbers_and_sections_reflected_in_single_file_html(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "fake_repo"
            (root / "docs" / "research").mkdir(parents=True)
            (root / "handover").mkdir(parents=True)

            # 1) Gate board markdown fixture
            (root / "docs" / "research" / "ACE_OMEGA_CHECKPOINT_ADDENDUM99.md").write_text(
                "# Checkpoint Uji Addendum 99\n"
                "- **G0: PASS.** Dasar.\n"
                "- **G3: MEASURED — SPECIALIZATION.** Terukur.\n"
                "- **G5: NOT_ASSESSED.** Belum.\n",
                encoding="utf-8",
            )
            # 2) Evo handover doc fixture
            (root / "handover" / "EVO_0007_VERDICT_UJI.md").write_text(
                "# Ringkasan Uji Evo 0007\nDetail baris dua.\n",
                encoding="utf-8",
            )
            # 3) Frozen corpus fixture (7 baris unik: 4 code, 3 language)
            corpus_rows = [
                {"id": f"c-{i}", "kind": "episode", "task_kind": "code", "instruction": "X"}
                for i in range(4)
            ] + [
                {"id": f"l-{i}", "kind": "episode", "task_kind": "language", "instruction": "Y"}
                for i in range(3)
            ]
            (root / "handover" / "TEST_CORPUS_FROZEN.jsonl").write_text(
                "\n".join(json.dumps(r) for r in corpus_rows) + "\n",
                encoding="utf-8",
            )

            out_html = Path(tmp) / "out" / "status.html"
            proc = subprocess.run(
                [sys.executable, str(SCRIPT), "--root", str(root), "--output", str(out_html)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            html_text = out_html.read_text(encoding="utf-8")

            # Verifikasi angka dinamis dari fixture tampil di HTML
            self.assertIn('<div class="v" id="stat-gates">3</div>', html_text)
            self.assertIn('<div class="v" id="stat-corpora">1</div>', html_text)
            self.assertIn('<div class="v" id="stat-corpus-lines">7</div>', html_text)
            self.assertIn('<div class="v" id="stat-timeline">2</div>', html_text)

            # Verifikasi entri gate, corpus, dan linimasa evo tampil serta bebas dependensi eksternal
            self.assertIn("MEASURED — SPECIALIZATION", html_text)
            self.assertIn("TEST_CORPUS_FROZEN.jsonl", html_text)
            self.assertIn("Ringkasan Uji Evo 0007", html_text)
            self.assertIn("Checkpoint Uji Addendum 99", html_text)
            self.assertNotIn("https://", html_text)
            self.assertNotIn("http://", html_text)

    def test_empty_repo_renders_without_hardcoded_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "empty_repo"
            root.mkdir()
            status = collect_repo_status(root)
            html_text = render_dashboard_html(status)
            self.assertEqual(status["gate_count"], 0)
            self.assertEqual(status["frozen_corpora"]["corpus_count"], 0)
            self.assertEqual(status["timeline_count"], 0)
            self.assertIn('<div class="v" id="stat-gates">0</div>', html_text)
            self.assertIn('<div class="v" id="stat-corpora">0</div>', html_text)

    def test_invalid_root_exits_2(self) -> None:
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "--root", "/tmp/tidak_ada_repo_status"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 2)
        self.assertIn("Error:", proc.stderr)


if __name__ == "__main__":
    unittest.main()
