"""Tes reranker berjangkar peta bukti frontier + confidence (AG59)."""

from __future__ import annotations

import ast
from pathlib import Path
import unittest

from ace_operational.recall_reranker import TESTED_STATUS, rerank_candidates


class RecallRerankerTests(unittest.TestCase):
    def test_untested_or_unanchored_demoted_below_tested_at_equal_similarity(self) -> None:
        frontier_map = {
            "cand-tested": {
                "status": TESTED_STATUS,
                "evidence_ref": "evidence/tested_01.json",
            },
            "cand-untested": {
                "status": "KNOWN_UNTESTED",
                "evidence_ref": "evidence/untested_01.json",
            },
            "cand-no-evidence": {
                "status": TESTED_STATUS,
                "evidence_ref": "",  # KNOWN_AND_TESTED tanpa evidence_ref tidak sah dihitung teruji
            },
        }
        candidates = [
            {
                "id": "cand-untested",
                "score": 0.80,
                "record": {"id": "cand-untested", "confidence": 0.95, "evidence_refs": ["evidence/untested_01.json"]},
            },
            {
                "id": "cand-no-evidence",
                "score": 0.80,
                "record": {"id": "cand-no-evidence", "confidence": 0.90},
            },
            {
                "id": "cand-tested",
                "score": 0.80,
                "record": {"id": "cand-tested", "confidence": 0.70, "evidence_refs": ["evidence/tested_01.json"]},
            },
            {
                "id": "cand-missing-frontier",
                "score": 0.85,  # kemiripan sedikit lebih tinggi tetapi sama sekali tak berjangkar frontier
                "record": {"id": "cand-missing-frontier", "confidence": 0.99},
            },
        ]

        ranked = rerank_candidates(candidates, frontier_map)
        self.assertEqual(ranked[0]["id"], "cand-tested")
        self.assertTrue(ranked[0]["frontier_verified"])
        for row in ranked[1:]:
            self.assertFalse(row["frontier_verified"])
            self.assertLess(row["rerank_score"], ranked[0]["rerank_score"])

    def test_confidence_breaks_ties_within_same_verification_tier(self) -> None:
        frontier = {
            "a": {"status": TESTED_STATUS, "evidence_ref": "ev-a"},
            "b": {"status": TESTED_STATUS, "evidence_ref": "ev-b"},
        }
        ranked = rerank_candidates(
            [
                {"id": "a", "score": 0.75, "confidence": 0.4},
                {"id": "b", "score": 0.75, "confidence": 0.9},
            ],
            frontier,
        )
        self.assertEqual([r["id"] for r in ranked], ["b", "a"])

    def test_no_engine_imports(self) -> None:
        src = (Path(__file__).resolve().parent / "recall_reranker.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                self.assertNotIn("autonomous_engine", node.module)


if __name__ == "__main__":
    unittest.main()
