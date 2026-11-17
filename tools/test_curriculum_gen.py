"""Uji unit untuk tools/curriculum_gen.py (WS-A #2)."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.curriculum_gen import CURRICULUM_SCHEMA, CurriculumGenError, generate_curricula

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "tools" / "curriculum_gen.py"


def _cand(ep_id: str, task_kind: str = "code") -> dict[str, str]:
    return {
        "id": ep_id,
        "kind": "episode",
        "task_kind": task_kind,
        "instruction": f"Instruksi untuk {ep_id}. Sertakan docstring Bahasa Indonesia.",
    }


class CurriculumGenTests(unittest.TestCase):
    """Menguji pembuatan dua kurikulum JSONL (usulan celah margin vs beku deterministik) & jalur gagal."""

    def test_proposed_orders_by_smallest_margin_gap_and_baseline_is_fixed_id_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp)
            cands = t / "candidates.jsonl"
            census = t / "wave_census.jsonl"
            staging = t / "patterns.jsonl"
            prop_out = t / "proposed.jsonl"
            base_out = t / "baseline.jsonl"

            rows = [_cand("ep-001"), _cand("ep-002"), _cand("ep-003", "language"), _cand("ep-004")]
            cands.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")

            # ep-003 paling dekat ke margin 0 (0.5), ep-002 berikutnya (3.0), ep-001 jauh (25.0), ep-004 belum disensus.
            census_rows = [
                {"id": "ep-001", "margin": 25.0},
                {"id": "ep-002", "margin": -3.0},
                {"id": "ep-003", "margin": 0.5},
            ]
            census.write_text("\n".join(json.dumps(r) for r in census_rows) + "\n", encoding="utf-8")
            staging.write_text(json.dumps({"source_episode": "ep-001", "task_shape": {"keywords": ["x"]}}) + "\n", encoding="utf-8")

            summary = generate_curricula(
                candidates_path=cands,
                census_path=census,
                staging_path=staging,
                proposed_out=prop_out,
                baseline_out=base_out,
            )
            self.assertEqual(summary["schema"], CURRICULUM_SCHEMA)
            self.assertTrue(summary["order_differs"])
            self.assertEqual(summary["census_matched_count"], 3)
            self.assertEqual(summary["staging_covered_count"], 1)

            prop_ids = [json.loads(l)["id"] for l in prop_out.read_text(encoding="utf-8").splitlines()]
            base_ids = [json.loads(l)["id"] for l in base_out.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(prop_ids, ["ep-003", "ep-002", "ep-001", "ep-004"])
            self.assertEqual(base_ids, ["ep-001", "ep-002", "ep-003", "ep-004"])

            for raw in prop_out.read_text(encoding="utf-8").splitlines():
                obj = json.loads(raw)
                self.assertEqual(set(obj.keys()), {"id", "kind", "task_kind", "instruction"})
                self.assertEqual(obj["kind"], "episode")

    def test_score_gap_fallback_and_limit_cli(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp)
            cands = t / "candidates.jsonl"
            census = t / "census.json"
            prop_out = t / "prop.jsonl"
            base_out = t / "base.jsonl"

            cands.write_text(
                "\n".join(json.dumps(_cand(eid)) for eid in ("ep-a", "ep-b", "ep-c")) + "\n",
                encoding="utf-8",
            )
            # target score default = 60.0 => ep-c gap 2, ep-a gap 35, ep-b gap 10
            census.write_text(
                json.dumps(
                    {
                        "episodes": [
                            {"id": "ep-a", "score": 95.0},
                            {"id": "ep-b", "score": 50.0},
                            {"id": "ep-c", "score": 62.0},
                        ]
                    }
                ),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--candidates",
                    str(cands),
                    "--census",
                    str(census),
                    "--proposed-out",
                    str(prop_out),
                    "--baseline-out",
                    str(base_out),
                    "--limit",
                    "2",
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            res = json.loads(proc.stdout)
            self.assertEqual(res["emitted_count"], 2)
            self.assertEqual(res["proposed_top_ids"], ["ep-c", "ep-b"])
            self.assertEqual(res["baseline_top_ids"], ["ep-a", "ep-b"])

    def test_failure_paths_invalid_candidate_schema_missing_files_exit_2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp)
            bad_cands = t / "bad.jsonl"
            census = t / "c.jsonl"
            census.write_text('{"id": "x", "margin": 1}\n', encoding="utf-8")

            bad_cands.write_text('{"id": "x", "kind": "bad", "task_kind": "code", "instruction": "a"}\n', encoding="utf-8")
            with self.assertRaises(CurriculumGenError):
                generate_curricula(
                    candidates_path=bad_cands,
                    census_path=census,
                    proposed_out=t / "p.jsonl",
                    baseline_out=t / "b.jsonl",
                )

            proc = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--candidates",
                    str(t / "missing.jsonl"),
                    "--census",
                    str(census),
                    "--proposed-out",
                    str(t / "p.jsonl"),
                    "--baseline-out",
                    str(t / "b.jsonl"),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 2)
            self.assertIn("Error:", proc.stderr)


if __name__ == "__main__":
    unittest.main()
