"""Uji unit untuk tools/pattern_distill.py (WS-A #1)."""
from __future__ import annotations

import gzip
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.pattern_distill import DISTILL_SCHEMA, PatternDistillError, distill_evidence

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "tools" / "pattern_distill.py"


class PatternDistillTests(unittest.TestCase):
    """Menguji jalur sukses dan jalur gagal pipeline distilasi pola staging EVO 0007."""

    def test_distill_ratified_jsonl_extracts_shape_approach_pitfalls_and_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp)
            ev = t / "ev.jsonl"
            out = t / "staging" / "patterns.jsonl"
            rows = [
                {
                    "id": "w2-code-001",
                    "task_kind": "code",
                    "instruction": "Buat fungsi Python gabung_interval(intervals) untuk daftar kosong dan tumpang tindih. Sertakan docstring Bahasa Indonesia.",
                    "ratified": True,
                    "score": 68.0,
                    "margin": 4.5,
                    "output": (
                        "def gabung_interval(intervals: list[tuple[int, int]]) -> list[tuple[int, int]]:\n"
                        '    """Menggabungkan interval bertumpukan termasuk daftar kosong."""\n'
                        "    if not intervals:\n"
                        "        return []\n"
                        "    return sorted(intervals)\n"
                    ),
                    "reasons": [
                        "Menangani daftar kosong dengan benar",
                        "Hampir gagal jika interval berdekatan ujungnya tidak disortir dulu",
                    ],
                },
                {
                    "id": "w2-code-002",
                    "task_kind": "code",
                    "instruction": "Buat fungsi gagal.",
                    "ratified": False,
                    "score": 25.0,
                    "output": "def x(): pass",
                    "reasons": ["Gagal total"],
                },
                {
                    "id": "w2-lang-001",
                    "task_kind": "language",
                    "instruction": "Tulis tepat 40 kata pengumuman resmi dilarang memakai kata mohon.",
                    "status": "ACCEPTED",
                    "score": 74.0,
                    "output": "1. Pastikan jumlah kata tepat.\n2. Periksa frasa wajib verbatim.",
                    "reasons": "Lolos jumlah kata; Hindari sinonim kata terlarang",
                },
            ]
            ev.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")

            summary = distill_evidence([ev], out)
            self.assertEqual(summary["schema"], DISTILL_SCHEMA)
            self.assertEqual(summary["total_records_read"], 3)
            self.assertEqual(summary["distilled_count"], 2)
            self.assertEqual(summary["skipped_unratified"], 1)

            lines = [json.loads(l) for l in out.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(len(lines), 2)
            rec0 = lines[0]
            self.assertEqual(rec0["event_class"], "pattern_distilled")
            self.assertEqual(rec0["kind"], "semantic")
            self.assertTrue(rec0["staging_only"])
            self.assertEqual(rec0["source_episode"], "w2-code-001")
            self.assertIn("gabung_interval", " ".join(rec0["task_shape"]["keywords"]))
            self.assertTrue(any("gabung_interval" in s for s in rec0["approach"]))
            self.assertTrue(any("Margin penilaian tipis" in p for p in rec0["pitfalls"]))
            self.assertEqual(rec0["provenance"]["score"], 68.0)
            self.assertEqual(len(rec0["provenance"]["output_sha256"]), 64)

    def test_distill_supports_json_gz_wrapper_and_append_dedup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp)
            gz = t / "ev.json.gz"
            out = t / "patterns.jsonl"
            payload = {
                "episodes": [
                    {
                        "episode_id": "ep-10",
                        "task_kind": "language",
                        "prompt": "Tulis ringkasan tepat 3 kalimat tanpa kata ganti.",
                        "verdict": "RATIFIED",
                        "output": "Kalimat satu lengkap. Kalimat dua jelas. Kalimat tiga ringkas.",
                        "reasons": ["Sesuai 3 kalimat"],
                    }
                ]
            }
            gz.write_bytes(gzip.compress(json.dumps(payload).encode("utf-8")))

            s1 = distill_evidence([gz], out)
            self.assertEqual(s1["distilled_count"], 1)
            s2 = distill_evidence([gz], out, append=True)
            self.assertEqual(s2["distilled_count"], 0)
            self.assertEqual(s2["skipped_duplicate"], 1)
            self.assertEqual(s2["total_store_records"], 1)

    def test_incomplete_ratified_records_skipped_and_zero_distilled_fails_unless_allow_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp)
            ev = t / "incomplete.jsonl"
            out = t / "patterns.jsonl"
            ev.write_text(
                "\n".join(
                    [
                        json.dumps({"id": "ep-1", "ratified": True, "output": ""}),
                        json.dumps({"ratified": True, "output": "ok"}),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            with self.assertRaises(PatternDistillError):
                distill_evidence([ev], out, allow_empty=False)

            summary = distill_evidence([ev], out, allow_empty=True)
            self.assertEqual(summary["distilled_count"], 0)
            self.assertEqual(summary["skipped_incomplete"], 2)

    def test_failure_paths_missing_or_corrupt_evidence_and_cli_exit_2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp)
            bad = t / "bad.jsonl"
            bad.write_text("{broken json\n", encoding="utf-8")
            with self.assertRaises(PatternDistillError):
                distill_evidence([bad], t / "out.jsonl")

            proc = subprocess.run(
                [sys.executable, str(SCRIPT), str(t / "missing.jsonl"), "--output", str(t / "out.jsonl")],
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 2)
            self.assertIn("Error:", proc.stderr)


class BoundedPatternTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / "episodes.jsonl"
        self.output = self.root / "patterns.jsonl"
        self.episode = {
            "id": "synthetic-01", "ratified": True, "task_kind": "code",
            "instruction": "Buat fungsi gabung_interval untuk interval kosong.",
            "output": "def gabung_interval(intervals):\n    if not intervals:\n        return []\n",
            "validator": {"parsed": {"reasons": ["Periksa interval kosong."]},
                          "raw": "RAW_VALIDATOR_TRANSCRIPT_ONLY"},
            "receipt": {"raw": "RAW_RECEIPT_ONLY"},
        }

    def write_episodes(self, rows):
        self.source.write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")

    def test_ratified_pattern_uses_task_output_and_judge_without_raw_receipts(self):
        self.write_episodes([self.episode])
        summary = distill_evidence([self.source], self.output)
        serialized = self.output.read_text(encoding="utf-8")
        pattern = json.loads(serialized)
        self.assertEqual(summary["distilled_count"], 1)
        self.assertEqual(pattern["event_class"], "pattern_distilled")
        self.assertEqual(pattern["source_episode"], "synthetic-01")
        self.assertIn("gabung_interval", pattern["task_shape"]["keywords"])
        self.assertTrue(any("gabung_interval" in step for step in pattern["approach"]))
        self.assertEqual(pattern["pitfalls"], ["Periksa interval kosong."])
        self.assertNotIn("RAW_RECEIPT_ONLY", serialized)
        self.assertNotIn("RAW_VALIDATOR_TRANSCRIPT_ONLY", serialized)
        self.assertNotIn("output", pattern)
        self.assertNotIn("receipt", pattern)
        self.assertNotIn("validator", pattern)

    def test_explicit_unratified_and_invalid_flags_cannot_be_overridden_by_status(self):
        rows = [dict(self.episode, id=f"skip-{i}", ratified=value, status="ACCEPTED")
                for i, value in enumerate((False, "true", 1, None))]
        self.write_episodes(rows)
        summary = distill_evidence([self.source], self.output, allow_empty=True)
        self.assertEqual(summary["skipped_unratified"], 4)
        self.assertEqual(summary["distilled_count"], 0)
        self.assertEqual(self.output.read_bytes(), b"")

    def test_cli_enforces_serialized_length_and_preserves_source_provenance(self):
        row = dict(self.episode, output="- " + 'karakter\\\"é\t' * 100,
                   reasons=["Periksa batas panjang " * 40])
        self.write_episodes([row])
        original = self.source.read_bytes()
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), str(self.source), "--output", str(self.output),
             "--max-chars", "1200"], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        lines = self.output.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 1)
        self.assertLessEqual(len(lines[0]), 1200)
        pattern = json.loads(lines[0])
        self.assertTrue(pattern["approach"][0])
        self.assertTrue(pattern["pitfalls"][0])
        self.assertEqual(pattern["source_episode"], row["id"])
        import hashlib
        self.assertEqual(pattern["provenance"]["output_sha256"],
                         hashlib.sha256(row["output"].encode()).hexdigest())
        self.assertEqual(self.source.read_bytes(), original)

    def test_impossible_or_invalid_budget_preserves_existing_output(self):
        self.write_episodes([self.episode])
        self.output.write_text("prior output\n", encoding="utf-8")
        for limit in (0, -1, True, 1.5, 10):
            with self.subTest(limit=limit), self.assertRaises(PatternDistillError):
                distill_evidence([self.source], self.output, max_chars=limit)
            self.assertEqual(self.output.read_text(), "prior output\n")

    def test_append_rejects_existing_record_over_budget(self):
        self.write_episodes([dict(self.episode, output="- " + "long summary " * 80)])
        distill_evidence([self.source], self.output, max_chars=4096)
        previous = self.output.read_bytes()
        self.assertGreater(len(previous.decode().rstrip("\n")), 700)
        with self.assertRaises(PatternDistillError):
            distill_evidence([self.source], self.output, append=True, max_chars=700)
        self.assertEqual(self.output.read_bytes(), previous)

    def test_output_must_not_replace_input(self):
        self.write_episodes([self.episode])
        original = self.source.read_bytes()
        with self.assertRaises(PatternDistillError):
            distill_evidence([self.source], self.source)
        self.assertEqual(self.source.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
