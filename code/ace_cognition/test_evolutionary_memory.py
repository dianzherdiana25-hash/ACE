"""Unit tests for Evolutionary Associative Memory."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ace_cognition.evolutionary_memory import EvolutionaryMemory


class TestEvolutionaryMemory(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.mem_file = Path(self.temp_dir.name) / "memory.json"
        self.memory = EvolutionaryMemory(storage_path=str(self.mem_file))

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_record_and_query_similarity(self):
        code_1 = (
            "def kernel_a(length: int, density: int, stride_val: int) -> int:\n"
            "    return 0 if (length % 2 == 0) else 1\n"
        )
        code_2 = (
            "def kernel_b(length: int, density: int, stride_val: int) -> int:\n"
            "    return 0 if (density % 3 == 0) else 1\n"
        )
        code_3 = (
            "def string_parser(w: str) -> bool:\n"
            "    return w.startswith('abc')\n"
        )

        self.memory.record_experience(
            cycle_id=1,
            task_id="task_parity",
            hypothesis_id="hyp_1",
            source_code=code_1,
            score=0.90,
            decision="ACCEPTED",
        )
        self.memory.record_experience(
            cycle_id=2,
            task_id="task_density",
            hypothesis_id="hyp_2",
            source_code=code_2,
            score=0.85,
            decision="ACCEPTED",
        )
        self.memory.record_experience(
            cycle_id=3,
            task_id="task_string",
            hypothesis_id="hyp_3",
            source_code=code_3,
            score=0.40,
            decision="REJECTED",
        )

        query = "def cand(length: int, density: int, stride_val: int) -> int:\n    return 0 if (length % 4 == 0) else 1\n"
        results = self.memory.query_similar(query, top_k=2)

        self.assertGreaterEqual(len(results), 1)
        best_entry, best_sim = results[0]
        self.assertEqual(best_entry.task_id, "task_parity")
        self.assertGreater(best_sim, 0.50)

    def test_persistence_reload(self):
        code = "def sample(): return 42\n"
        self.memory.record_experience(
            cycle_id=10,
            task_id="t10",
            hypothesis_id="h10",
            source_code=code,
            score=0.99,
            decision="ACCEPTED",
        )

        # Reload in a new instance
        reloaded = EvolutionaryMemory(storage_path=str(self.mem_file))
        self.assertEqual(len(reloaded.entries), 1)
        self.assertEqual(reloaded.entries[0].hypothesis_id, "h10")


if __name__ == "__main__":
    unittest.main()
