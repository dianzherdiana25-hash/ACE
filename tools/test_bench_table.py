"""Uji unit untuk tabulator benchmark tools/bench_table.py."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.bench_table import BenchTableError, render_markdown_table, summarize_bench

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "tools" / "bench_table.py"


class BenchTableTests(unittest.TestCase):
    """Pengujian perhitungan mean ± stdev, penanganan n=1, dan kesalahan input."""

    def test_known_mean_and_stdev_markdown_output(self) -> None:
        # Label A: score [10, 20, 30] -> mean=20.00, sample stdev=10.00; latency [100, 100, 100] -> 100.00 ± 0.00
        # Label B: score [5, 7] -> mean=6.00, sample stdev=sqrt(2)=1.41
        # Label C (n=1): score [42], ok=True (boolean diabaikan) -> 42.00 ± 0.00, tanpa latency (-)
        rows = [
            {"label": "A", "score": 10, "latency_ms": 100, "note": "ok"},
            {"label": "A", "score": 20, "latency_ms": 100},
            {"label": "A", "score": 30, "latency_ms": 100},
            {"label": "B", "score": 5, "latency_ms": 50},
            {"label": "B", "score": 7, "latency_ms": 70},
            {"label": "C", "score": 42, "ok": True},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            jsonl_path = Path(tmp) / "bench.jsonl"
            jsonl_path.write_text(
                "\n".join(json.dumps(r) for r in rows) + "\n",
                encoding="utf-8",
            )
            summary = summarize_bench(jsonl_path)
            self.assertEqual(summary["metrics"], ["latency_ms", "score"])
            by_label = {r["label"]: r for r in summary["rows"]}
            self.assertAlmostEqual(by_label["A"]["metrics"]["score"]["mean"], 20.0)
            self.assertAlmostEqual(by_label["A"]["metrics"]["score"]["stdev"], 10.0)
            self.assertAlmostEqual(by_label["B"]["metrics"]["score"]["mean"], 6.0)
            self.assertAlmostEqual(by_label["B"]["metrics"]["score"]["stdev"], 2 ** 0.5)
            self.assertAlmostEqual(by_label["C"]["metrics"]["score"]["stdev"], 0.0)
            self.assertNotIn("ok", summary["metrics"])

            md = render_markdown_table(summary, precision=2)
            self.assertIn("| label | n | latency_ms | score |", md)
            self.assertIn("| A | 3 | 100.00 ± 0.00 | 20.00 ± 10.00 |", md)
            self.assertIn("| B | 2 | 60.00 ± 14.14 | 6.00 ± 1.41 |", md)
            self.assertIn("| C | 1 | - | 42.00 ± 0.00 |", md)

            proc = subprocess.run(
                [sys.executable, str(SCRIPT), str(jsonl_path), "--precision", "2"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(proc.stdout, md)

    def test_custom_label_key_and_json_format(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            jsonl_path = Path(tmp) / "bench.jsonl"
            out_path = Path(tmp) / "out.json"
            jsonl_path.write_text(
                '{"variant": "base", "pass_rate": 0.5}\n{"variant": "base", "pass_rate": 0.7}\n',
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    str(jsonl_path),
                    "--label-key",
                    "variant",
                    "--format",
                    "json",
                    "--output",
                    str(out_path),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            payload = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["rows"][0]["label"], "base")
            self.assertAlmostEqual(payload["rows"][0]["metrics"]["pass_rate"]["mean"], 0.6)

    def test_missing_label_or_empty_file_exits_2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bad_jsonl = Path(tmp) / "bad.jsonl"
            bad_jsonl.write_text('{"score": 12}\n', encoding="utf-8")
            with self.assertRaises(BenchTableError):
                summarize_bench(bad_jsonl)

            empty_jsonl = Path(tmp) / "empty.jsonl"
            empty_jsonl.write_text("\n\n", encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, str(SCRIPT), str(empty_jsonl)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 2)
            self.assertIn("Error:", proc.stderr)

    def test_fuzz_hardening_float_overflow_and_huge_int_raise_bench_table_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p1 = Path(tmp) / "fsum_overflow.jsonl"
            p1.write_text('{"label": "a", "m": 1e308}\n{"label": "a", "m": 1e308}\n', encoding="utf-8")
            with self.assertRaises(BenchTableError):
                summarize_bench(p1)

            p2 = Path(tmp) / "int_overflow.jsonl"
            p2.write_text(json.dumps({"label": "a", "m": 10**400}) + "\n", encoding="utf-8")
            with self.assertRaises(BenchTableError):
                summarize_bench(p2)

            p3 = Path(tmp) / "digit_limit.jsonl"
            p3.write_text('{"label": "a", "m": ' + ("9" * 5000) + "}\n", encoding="utf-8")
            with self.assertRaises(BenchTableError):
                summarize_bench(p3)


if __name__ == "__main__":
    unittest.main()
