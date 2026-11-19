"""Fixture ujung-ke-ujung lab kurikulum historis."""
import hashlib
from html import unescape
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tools.curriculum_lab import run_lab
from tools.pattern_distill import PatternDistillError


class CurriculumLabTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.history = self.root / "history.jsonl"
        self.corpus = self.root / "corpus.jsonl"
        self.rows = [
            {"id": "accepted", "task_kind": "code", "ratified": True,
             "output": "def interval(xs): pass", "reasons": ["Periksa masukan kosong."]},
            {"id": "near", "task_kind": "code", "ratified": False, "output": "[]"},
            {"id": "near", "task_kind": "code", "ratified": False, "output": "None"},
            {"id": "open", "task_kind": "code", "ratified": False, "output": "[]"},
            {"id": "error", "task_kind": "code", "ratified": False, "error": "timeout"},
        ]
        self.write_jsonl(self.history, self.rows)
        self.write_jsonl(self.corpus, [
            {"id": "accepted", "task_kind": "code", "instruction": "interval kosong"},
            {"id": "near", "task_kind": "code", "instruction": "interval kosong"},
            {"id": "open", "task_kind": "code", "instruction": "matriks"},
        ])

    @staticmethod
    def write_jsonl(path, rows):
        path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")

    def test_cli_reports_supported_and_open_gaps_with_source_evidence(self):
        originals = {path: path.read_bytes() for path in (self.history, self.corpus)}
        script = Path(__file__).with_name("curriculum_lab.py")
        result = subprocess.run(
            [sys.executable, str(script), "--episodes", str(self.history),
             "--corpus", str(self.corpus), "--max-chars", "1200"],
            check=True, capture_output=True, text=True, cwd=self.root,
            env={**os.environ, "TMPDIR": str(self.root)},
        )
        proposed, open_gaps = unescape(result.stdout).split("## Celah terbuka")
        for line in ("Pola terdistilasi — 1", "Usulan — 1", "Celah terbuka — 1",
                     "Episode dikecualikan — 1", "Batas karakter per pola — 1200"):
            self.assertIn(line, proposed)
        self.assertIn("prioritas 2", proposed)
        self.assertIn(f"Bukti celah — {self.history}, entri 2 (near)", proposed)
        self.assertIn(f"Bukti celah — {self.history}, entri 3 (near)", proposed)
        self.assertIn(f"instruksi {self.corpus}, entri 2", proposed)
        digest = hashlib.sha256(self.rows[0]["output"].encode()).hexdigest()
        self.assertIn(f"Pola pendukung — `{digest}` · {self.history}, entri 1 (accepted)", proposed)
        self.assertIn("Pitfall — Periksa masukan kosong.", proposed)
        self.assertIn(f"Bukti celah — {self.history}, entri 4 (open)", open_gaps)
        self.assertNotIn("Pola pendukung", open_gaps)
        self.assertEqual({path: path.read_bytes() for path in self.root.iterdir()}, originals)

    def test_history_without_ratified_output_leaves_gap_open(self):
        self.write_jsonl(self.history, [{**self.rows[1], "instruction": "interval kosong"}])
        report = run_lab(self.history)
        self.assertIn("Pola terdistilasi — 0", report)
        self.assertIn("Usulan — 0", report)
        self.assertIn("Celah terbuka — 1", report)

    def test_missing_history_join_is_an_error(self):
        with self.assertRaisesRegex(ValueError, r"entri 1 \(accepted\)"):
            run_lab(self.history)

    def test_max_chars_reaches_the_distiller(self):
        with self.assertRaisesRegex(PatternDistillError, "--max-chars terlalu kecil"):
            run_lab(self.history, corpus=self.corpus, max_chars=64)


if __name__ == "__main__":
    unittest.main()
