"""Tes regresi fixture-only untuk tools.recall_precision_probe (AG43)."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from ace_operational.cognitive_memory import CognitiveMemory
from tools import recall_precision_probe


class RecallPrecisionProbeTest(unittest.TestCase):
    def test_hand_verifiable_precision_recall_fractions(self) -> None:
        # Hitungan tangan:
        # - q1: relevant={a,b,c} (3), retrieved=[a,b,x] (3) -> TP=2 -> P=2/3, R=2/3
        # - q2: relevant={d}     (1), retrieved=[d,y]   (2) -> TP=1 -> P=1/2, R=1.0
        # - q3: relevant={e}     (1), retrieved=[]      (0) -> TP=0 -> P=0.0, R=0.0
        # Aggregate:
        # - total TP=3, total retrieved=5, total relevant=5 -> micro P=0.6, micro R=0.6
        # - macro P = (2/3 + 0.5 + 0.0) / 3 = 7/18 ~= 0.388889
        # - macro R = (2/3 + 1.0 + 0.0) / 3 = 5/9  ~= 0.555556
        queries = [
            {"query_id": "q1", "query": "alpha", "relevant_ids": ["a", "b", "c"]},
            {"query_id": "q2", "query": "beta", "relevant_ids": ["d"]},
            {"query_id": "q3", "query": "gamma", "relevant_ids": ["e"]},
        ]
        canned = {
            "q1": ["a", "b", "x"],
            "q2": ["d", "y"],
            "q3": [],
        }

        report = recall_precision_probe.evaluate_recall_precision(
            queries,
            lambda q, _limit: canned[q["query_id"]],
        )
        self.assertEqual(report["schema"], recall_precision_probe.SCHEMA)
        by_id = {row["query_id"]: row for row in report["queries"]}

        self.assertAlmostEqual(by_id["q1"]["precision"], 2 / 3, places=5)
        self.assertAlmostEqual(by_id["q1"]["recall"], 2 / 3, places=5)
        self.assertEqual(by_id["q1"]["false_positives"], ["x"])
        self.assertEqual(by_id["q1"]["false_negatives"], ["c"])

        self.assertAlmostEqual(by_id["q2"]["precision"], 0.5, places=5)
        self.assertAlmostEqual(by_id["q2"]["recall"], 1.0, places=5)

        self.assertEqual(by_id["q3"]["precision"], 0.0)
        self.assertEqual(by_id["q3"]["recall"], 0.0)

        summary = report["summary"]
        self.assertEqual(summary["total_tp"], 3)
        self.assertEqual(summary["total_retrieved"], 5)
        self.assertEqual(summary["total_relevant"], 5)
        self.assertAlmostEqual(summary["micro_precision"], 0.6, places=5)
        self.assertAlmostEqual(summary["micro_recall"], 0.6, places=5)
        self.assertAlmostEqual(summary["macro_precision"], 7 / 18, places=5)
        self.assertAlmostEqual(summary["macro_recall"], 5 / 9, places=5)
        self.assertEqual(summary["zero_recall_queries"], ["q3"])

    def test_cli_probe_over_cognitive_memory_fixture_readonly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            mem_dir = root / "mem"
            mem = CognitiveMemory(mem_dir)
            d1 = mem.anchor_evidence(b"bridge-evidence")
            id_bridge = mem.remember(
                kind="semantic",
                content={"topic": "bridge relay backoff", "fact": "jeda eksponensial mencegah busy loop"},
                source_kind="evidence",
                source_ref=d1,
                confidence=0.9,
            )
            id_house = mem.remember(
                kind="procedural",
                content={"topic": "house check cli", "step": "validasi status stale dan pid"},
                source_kind="operator",
                source_ref="doc:house_check",
                confidence=0.85,
            )
            mem_jsonl = mem_dir / "memory.jsonl"
            before_bytes = mem_jsonl.read_bytes()

            queries_path = root / "queries.jsonl"
            queries_path.write_text(
                "\n".join(
                    [
                        json.dumps({"query_id": "q-relay", "query": "bridge relay backoff", "relevant_ids": [id_bridge]}),
                        json.dumps({"query_id": "q-house", "query": "house check stale", "relevant_ids": [id_house]}),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            out_path = root / "probe.json"

            rc = recall_precision_probe.main(
                ["--memory", str(mem_jsonl), "--queries", str(queries_path), "--out", str(out_path)]
            )
            self.assertEqual(rc, 0)
            # Pastikan file sumber memory.jsonl sama sekali tidak dimodifikasi.
            self.assertEqual(mem_jsonl.read_bytes(), before_bytes)

            rep = json.loads(out_path.read_text(encoding="utf-8"))

        self.assertEqual(rep["summary"]["query_count"], 2)
        self.assertGreater(rep["summary"]["micro_recall"], 0.5)
        by_id = {row["query_id"]: row for row in rep["queries"]}
        self.assertIn(id_bridge, by_id["q-relay"]["retrieved_ids"])
        self.assertIn(id_house, by_id["q-house"]["retrieved_ids"])


if __name__ == "__main__":
    unittest.main()
