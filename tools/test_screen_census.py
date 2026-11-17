"""Uji unit untuk perkakas sensus hasil layar/ukur tools/screen_census.py."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.screen_census import CensusInputError, compute_census, format_text_table

REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_jsonl(path: Path, rows: list[str | dict]) -> None:
    lines = [r if isinstance(r, str) else json.dumps(r, ensure_ascii=False) for r in rows]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


class ScreenCensusTests(unittest.TestCase):
    """Verifikasi hitungan sensus pasangan A/B, pita skor, dan isolasi baris invalid."""

    def test_paired_ab_with_invalid_error_and_malformed_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "screen_ab.jsonl"
            _write_jsonl(
                p,
                [
                    # cd-code-001: A=True, B=True -> always_pass
                    {"id": "cd-code-001", "task_kind": "code", "run": "A", "ratified": True},
                    {"id": "cd-code-001", "task_kind": "code", "run": "B", "ratified": True},
                    # cd-code-002: A=False, B=False -> always_fail
                    {"id": "cd-code-002", "task_kind": "code", "run": "A", "ratified": False},
                    {"id": "cd-code-002", "task_kind": "code", "run": "B", "ratified": False},
                    # cd-code-003: A=True, B=False -> split
                    {"id": "cd-code-003", "task_kind": "code", "run": "A", "ratified": True},
                    {"id": "cd-code-003", "task_kind": "code", "run": "B", "ratified": False},
                    # cd-code-004: A=error (invalid!), B=True -> single_observation (bukan always_pass!)
                    {
                        "id": "cd-code-004",
                        "task_kind": "code",
                        "run": "A",
                        "ratified": False,
                        "error": "BrainUnavailable: timeout",
                    },
                    {"id": "cd-code-004", "task_kind": "code", "run": "B", "ratified": True},
                    # cd-lang-001: A=True, B=True -> always_pass
                    {"id": "cd-lang-001", "task_kind": "language", "run": "A", "ratified": True},
                    {"id": "cd-lang-001", "task_kind": "language", "run": "B", "ratified": True},
                    # Baris invalid: JSON rusak + tanpa id
                    "{broken json",
                    {"task_kind": "language", "ratified": True},
                ],
            )
            census = compute_census([p])
            self.assertEqual(census["total_lines"], 12)
            self.assertEqual(census["overall"]["valid_rows"], 9)
            self.assertEqual(census["overall"]["invalid_rows"], 3)

            code_paired = census["by_task_kind"]["code"]["paired"]
            self.assertEqual(code_paired["always_pass"], 1)
            self.assertEqual(code_paired["always_fail"], 1)
            self.assertEqual(code_paired["split"], 1)
            self.assertEqual(code_paired["single_observation"], 1)
            self.assertEqual(census["by_task_kind"]["code"]["invalid_rows"], 1)

            lang_paired = census["by_task_kind"]["language"]["paired"]
            self.assertEqual(lang_paired["always_pass"], 1)
            self.assertEqual(census["by_task_kind"]["language"]["invalid_rows"], 1)

            self.assertEqual(len(census["split_episodes"]), 1)
            self.assertEqual(census["split_episodes"][0]["id"], "cd-code-003")

    def test_score_bands_and_out_of_range_invalid_isolation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "scored.jsonl"
            _write_jsonl(
                p,
                [
                    {"id": "s-001", "task_kind": "code", "score": 0},
                    {"id": "s-002", "task_kind": "code", "score": 39.5},
                    {"id": "s-003", "task_kind": "code", "score": 40},
                    {"id": "s-004", "task_kind": "code", "score": 44},
                    {"id": "s-005", "task_kind": "language", "score": 45},
                    {"id": "s-006", "task_kind": "language", "score": 75},
                    {"id": "s-007", "task_kind": "language", "score": 76},
                    {"id": "s-008", "task_kind": "language", "score": 100},
                    # Baris invalid: error aktif, skor > 100, skor boolean, tanpa nilai
                    {"id": "s-009", "task_kind": "code", "score": 60, "error": "timeout"},
                    {"id": "s-010", "task_kind": "code", "score": 105},
                    {"id": "s-011", "task_kind": "language", "score": True},
                    {"id": "s-012", "task_kind": "language"},
                ],
            )
            census = compute_census([p])
            self.assertEqual(census["overall"]["valid_rows"], 8)
            self.assertEqual(census["overall"]["invalid_rows"], 4)
            self.assertEqual(census["overall"]["scored_rows"], 8)
            self.assertEqual(
                census["overall"]["score_bands"],
                {"0-39": 2, "40-44": 2, "45-75": 2, "76-100": 2},
            )
            self.assertEqual(
                census["by_task_kind"]["code"]["score_bands"],
                {"0-39": 2, "40-44": 2, "45-75": 0, "76-100": 0},
            )
            self.assertEqual(
                census["by_task_kind"]["language"]["score_bands"],
                {"0-39": 0, "40-44": 0, "45-75": 2, "76-100": 2},
            )

    def test_text_table_and_cli_outputs_both_table_and_json(self) -> None:
        script = REPO_ROOT / "tools" / "screen_census.py"
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "mix.jsonl"
            _write_jsonl(
                p,
                [
                    {"id": "m-001", "task_kind": "code", "score": 55},
                    {"id": "m-002", "task_kind": "code", "score": 82, "error": "judge_err"},
                ],
            )
            proc = subprocess.run(
                [sys.executable, str(script), str(p)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 0)
            self.assertIn("SENSUS HASIL LAYAR/UKUR ACE", proc.stdout)
            self.assertIn("--- JSON ---", proc.stdout)
            json_part = proc.stdout.split("--- JSON ---", 1)[1]
            parsed = json.loads(json_part)
            self.assertEqual(parsed["overall"]["valid_rows"], 1)
            self.assertEqual(parsed["overall"]["invalid_rows"], 1)
            self.assertIn("TOTAL", format_text_table(parsed))

    def test_missing_file_raises_and_cli_exits_2(self) -> None:
        script = REPO_ROOT / "tools" / "screen_census.py"
        with self.assertRaises(CensusInputError):
            compute_census([Path("/tmp/tidak_pernah_ada_census.jsonl")])
        proc = subprocess.run(
            [sys.executable, str(script), "/tmp/tidak_pernah_ada_census.jsonl"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 2)
        self.assertIn("Error:", proc.stderr)

    def test_fuzz_hardening_huge_integer_score_and_digit_limit_rejected_safely(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "huge.jsonl"
            p.write_text(
                "\n".join(
                    [
                        json.dumps({"id": "h-001", "task_kind": "code", "score": 10**400}),
                        '{"id": "h-002", "score": ' + ("9" * 5000) + "}",
                        json.dumps({"id": "h-003", "task_kind": "code", "score": 60}),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            census = compute_census([p])
            self.assertEqual(census["overall"]["valid_rows"], 1)
            self.assertEqual(census["overall"]["invalid_rows"], 2)

    def test_judge_score_alias_supported_and_validated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "judge_alias.jsonl"
            _write_jsonl(
                p,
                [
                    {"id": "j-001", "task_kind": "code", "judge_score": 55},
                    {"id": "j-002", "task_kind": "language", "judge_score": 82, "ratified": True},
                    {"id": "j-003", "task_kind": "code", "judge_score": 150},
                ],
            )
            census = compute_census([p])
            self.assertEqual(census["overall"]["valid_rows"], 2)
            self.assertEqual(census["overall"]["invalid_rows"], 1)
            self.assertEqual(census["overall"]["scored_rows"], 2)
            self.assertEqual(census["overall"]["score_bands"]["45-75"], 1)
            self.assertEqual(census["overall"]["score_bands"]["76-100"], 1)


if __name__ == "__main__":
    unittest.main()
