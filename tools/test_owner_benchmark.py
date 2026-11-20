"""Tes pelaksana tolok ukur pemilik: fixture 6 tugas lintas domain + skoring solver mainan (AG39)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from tools.owner_benchmark import SCHEMA, load_benchmark_pack, run_benchmark


SCRIPT = Path(__file__).with_name("owner_benchmark.py")


def _six_cross_domain_pack_lines() -> list[dict]:
    return [
        {"kind": "pack_meta", "pack_id": "owner-core-benchmark", "pack_version": "2026.11.20-v1"},
        {"id": "code-1", "domain": "code", "prompt": "Kembalikan nama struktur LIFO.", "evaluator": {"kind": "exact_match", "expected": "stack"}},
        {"id": "code-2", "domain": "code", "prompt": "Sebut algoritma graf BFS & antrean.", "evaluator": {"kind": "contains_all", "tokens": ["bfs", "deque"]}},
        {"id": "lang-1", "domain": "language", "prompt": "Bentuk konfiks pekerjaan.", "evaluator": {"kind": "exact_match", "expected": "pe-an"}},
        {"id": "lang-2", "domain": "language", "prompt": "Tulis tepat dua kata berhubung.", "evaluator": {"kind": "regex_fullmatch", "pattern": r"[a-z]+-[a-z]+"}},
        {"id": "ops-1", "domain": "ops", "prompt": "Ambang stale status engine (detik).", "evaluator": {"kind": "numeric_tolerance", "expected": 300, "tolerance": 0.0}},
        {"id": "ops-2", "domain": "ops", "prompt": "Batas cap eksekutor kelas A.", "evaluator": {"kind": "numeric_tolerance", "expected": 3, "tolerance": 0.0}},
    ]


class OwnerBenchmarkTests(unittest.TestCase):
    def test_six_cross_domain_tasks_with_toy_solvers_and_sealed_version(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            pack_path = root / "pack.jsonl"
            pack_bytes = ("".join(json.dumps(r) + "\n" for r in _six_cross_domain_pack_lines())).encode("utf-8")
            pack_path.write_bytes(pack_bytes)
            expected_sha = hashlib.sha256(pack_bytes).hexdigest()

            meta, tasks = load_benchmark_pack(pack_path)
            self.assertEqual(len(tasks), 6)

            perfect_map = {
                "code-1": "stack",
                "code-2": "pakai bfs dengan deque",
                "lang-1": "pe-an",
                "lang-2": "buku-buku",
                "ops-1": "300",
                "ops-2": "3",
            }
            partial_map = {
                "code-1": "stack",
                "code-2": "dfs saja",
                "lang-1": "pe-an",
                "lang-2": "TIDAK COCOK",
                "ops-1": "300",
                "ops-2": "99",
            }

            full_rep = run_benchmark(
                tasks,
                lambda t: perfect_map[t["id"]],
                pack_id=meta["pack_id"],
                pack_version=meta["pack_version"],
                pack_sha256=meta["pack_sha256"],
                seed=17,
                solver_id="toy-perfect",
            )
            self.assertEqual(full_rep["schema"], SCHEMA)
            self.assertEqual(full_rep["sealed_pack"], {
                "pack_id": "owner-core-benchmark",
                "pack_version": "2026.11.20-v1",
                "pack_sha256": expected_sha,
            })
            self.assertEqual(full_rep["seed"], 17)
            self.assertEqual(full_rep["summary"]["passed_tasks"], 6)
            self.assertEqual(full_rep["summary"]["pass_rate"], 1.0)
            self.assertEqual(full_rep["by_domain"]["code"]["pass_rate"], 1.0)
            self.assertEqual(full_rep["by_domain"]["language"]["pass_rate"], 1.0)
            self.assertEqual(full_rep["by_domain"]["ops"]["pass_rate"], 1.0)

            part_rep = run_benchmark(
                tasks,
                lambda t: partial_map[t["id"]],
                pack_id=meta["pack_id"],
                pack_version=meta["pack_version"],
                pack_sha256=meta["pack_sha256"],
                seed=17,
                solver_id="toy-partial",
            )
            self.assertEqual(part_rep["summary"]["passed_tasks"], 3)
            self.assertEqual(part_rep["summary"]["pass_rate"], 0.5)
            for domain in ("code", "language", "ops"):
                self.assertEqual(part_rep["by_domain"][domain]["passed"], 1)
                self.assertEqual(part_rep["by_domain"][domain]["pass_rate"], 0.5)

            answers_path = root / "answers.json"
            answers_path.write_text(json.dumps(partial_map), encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable, str(SCRIPT),
                    "--pack", str(pack_path),
                    "--answers", str(answers_path),
                    "--seed", "42",
                ],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            cli_rep = json.loads(proc.stdout)
            self.assertEqual(cli_rep["seed"], 42)
            self.assertEqual(cli_rep["sealed_pack"]["pack_sha256"], expected_sha)
            self.assertEqual(cli_rep["summary"]["passed_tasks"], 3)


if __name__ == "__main__":
    unittest.main()
