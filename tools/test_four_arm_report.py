"""Uji unit untuk tools/four_arm_report.py (WS-A #3)."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.four_arm_report import FOUR_ARM_SCHEMA, FourArmReportError, analyze_four_arms, render_markdown_report

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "tools" / "four_arm_report.py"


def _make_rows(arm: str, *, total: int = 8, accepted: int = 4, delivered: int = 8, score: float = 65.0) -> list[dict]:
    out = []
    for i in range(total):
        out.append(
            {
                "id": f"ep-{i+1}",
                "arm": arm,
                "ratified": i < accepted,
                "context_delivered": i < delivered,
                "score": score,
            }
        )
    return out


class FourArmReportTests(unittest.TestCase):
    """Menguji laporan perbandingan empat-lengan serta gerbang delivery TIDAK_TERANTAR."""

    def test_all_arms_passing_delivery_gate_computes_clean_comparison(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "combined.jsonl"
            rows = (
                _make_rows("pattern", total=8, accepted=6, delivered=7, score=72.0)
                + _make_rows("receipt", total=8, accepted=4, delivered=6, score=60.0)
                + _make_rows("sham", total=8, accepted=3, delivered=7, score=58.0)
                + _make_rows("no_context", total=8, accepted=3, delivered=0, score=57.0)
            )
            p.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")

            report = analyze_four_arms([p])
            self.assertEqual(report["schema"], FOUR_ARM_SCHEMA)
            self.assertTrue(report["all_context_arms_delivered"])
            self.assertEqual(report["arms"]["pattern"]["delivery_gate_status"], "TERANTAR")
            self.assertEqual(report["arms"]["no_context"]["delivery_gate_status"], "TANPA_KONTEKS")
            self.assertAlmostEqual(report["comparisons"]["pattern_vs_sham"]["accept_rate_delta"], 0.375)
            self.assertTrue(report["comparisons"]["pattern_vs_sham"]["comparable"])
            self.assertEqual(report["scientific_verdict"], "NOT_ASSESSED")
            md = render_markdown_report(report)
            self.assertIn("TERANTAR", md)

    def test_delivery_below_75_percent_marked_tidak_terantar_not_nol_and_strict_exits_1(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp)
            files = {}
            specs = {
                "pattern": dict(total=8, accepted=5, delivered=7),   # 87.5% -> TERANTAR
                "receipt": dict(total=8, accepted=1, delivered=2),   # 25.0% -> TIDAK_TERANTAR
                "sham": dict(total=8, accepted=3, delivered=6),      # 75.0% -> TERANTAR
                "no_context": dict(total=8, accepted=3, delivered=0),
            }
            for arm, cfg in specs.items():
                fp = t / f"{arm}.jsonl"
                fp.write_text("\n".join(json.dumps(r) for r in _make_rows(arm, **cfg)) + "\n", encoding="utf-8")
                files[arm] = fp

            proc = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--pattern", str(files["pattern"]),
                    "--receipt", str(files["receipt"]),
                    "--sham", str(files["sham"]),
                    "--no-context", str(files["no_context"]),
                    "--format", "json",
                    "--strict-delivery",
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 1)
            report = json.loads(proc.stdout)
            self.assertFalse(report["all_context_arms_delivered"])
            self.assertEqual(report["undelivered_arms"], ["receipt"])
            self.assertEqual(report["arms"]["receipt"]["delivery_gate_status"], "TIDAK_TERANTAR")
            self.assertFalse(report["comparisons"]["pattern_vs_receipt"]["comparable"])
            self.assertIn("TIDAK_TERANTAR_BUKAN_NOL", report["comparisons"]["pattern_vs_receipt"]["blocked_reason"])

    def test_failure_paths_missing_arm_unknown_arm_or_bad_file_exit_2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp)
            partial = t / "partial.jsonl"
            partial.write_text("\n".join(json.dumps(r) for r in _make_rows("pattern")) + "\n", encoding="utf-8")
            with self.assertRaises(FourArmReportError):
                analyze_four_arms([partial])

            bad_arm = t / "bad_arm.jsonl"
            bad_arm.write_text('{"id":"1","arm":"imaginary","ratified":true}\n', encoding="utf-8")
            with self.assertRaises(FourArmReportError):
                analyze_four_arms([bad_arm])

            proc = subprocess.run(
                [sys.executable, str(SCRIPT), str(t / "missing.jsonl")],
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 2)
            self.assertIn("Error:", proc.stderr)


if __name__ == "__main__":
    unittest.main()
