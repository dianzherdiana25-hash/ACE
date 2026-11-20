"""Tes unit untuk tools/curiosity_questions.py (AG96)."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from tools.curiosity_questions import SCHEMA, generate_curiosity_questions, main


class CuriosityQuestionsTests(unittest.TestCase):
    def test_overlapping_gaps_merge_and_asked_questions_excluded(self) -> None:
        # Bentuk AG76 ace.house-world-model.v1
        world_model = {
            "schema": "ace.house-world-model.v1",
            "house_state": "degraded",
            "stale_subsystems": ["recall_store", "archive_rotator"],
            "exhausted_roles": [],
            "world_gaps": [
                {
                    "gap_id": "gap-recall-1",
                    "subsystem": "recall_store",
                    "reason": "Tugas bertetangga mendapat 0-record recall",
                    "severity": 0.70,
                },
                {
                    "gap_id": "gap-archive-1",
                    "subsystem": "archive_rotator",
                    "reason": "Rotasi arsip melewati batas interval yang dijadwalkan",
                    "severity": 0.60,
                },
            ],
        }
        # Anomali dari HypothesisBook pada domain yang sama ('recall_store') + satu anomali baru ('bridge_relay')
        hypothesis_book = {
            "schema": "ace.hypothesis-book.v1",
            "hypotheses": [
                {
                    "hypothesis_id": "hyp-recall-ambang",
                    "domain": "recall_store",
                    "status": "belum_tentu",
                    "cause": "Ambang skor filter kandidat recall menolak tetangga dekat",
                },
                {
                    "hypothesis_id": "hyp-relay-jitter",
                    "domain": "bridge_relay",
                    "status": "gugur",
                    "cause": "Jeda awal 100ms tidak mengurangi kegagalan koneksi singkat",
                },
            ],
        }
        asked_questions = [
            {
                "topic_key": "archive_rotator",
                "question": "Apa akar penyebab rotasi arsip melewati batas interval?",
            }
        ]

        report = generate_curiosity_questions(
            world_model,
            hypothesis_book,
            asked_questions=asked_questions,
        )
        self.assertEqual(report["schema"], SCHEMA)
        # Input: 2 world_gaps (archive_rotator stale ter-dedup di _extract_world_signals), 2 hypothesis anomalies = 4 sinyal
        # Overlapping recall_store (world_gap + hypothesis anomaly) -> bergabung jadi 1 cluster.
        # archive_rotator tersaring karena sudah ada di asked_questions.
        # Tersisa tepat 2 pertanyaan unik: recall_store (gabungan 2 sinyal) dan bridge_relay (1 sinyal gugur).
        self.assertEqual(report["excluded_already_asked_count"], 1)
        self.assertEqual(report["question_count"], 2)

        by_topic = {q["topic_key"]: q for q in report["questions"]}
        self.assertNotIn("archive_rotator", by_topic)
        self.assertEqual(by_topic["recall_store"]["merged_signal_count"], 2)
        self.assertEqual(
            set(by_topic["recall_store"]["source_ids"]),
            {"gap-recall-1", "hyp-recall-ambang"},
        )
        self.assertEqual(report["questions"][0]["rank"], 1)

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            wm_path = tmp / "wm.json"
            hb_path = tmp / "hb.json"
            asked_path = tmp / "asked.json"
            wm_path.write_text(json.dumps(world_model), encoding="utf-8")
            hb_path.write_text(json.dumps(hypothesis_book), encoding="utf-8")
            asked_path.write_text(json.dumps(asked_questions), encoding="utf-8")
            self.assertEqual(
                main(
                    [
                        "--world-model",
                        str(wm_path),
                        "--hypotheses",
                        str(hb_path),
                        "--asked",
                        str(asked_path),
                    ]
                ),
                0,
            )


if __name__ == "__main__":
    unittest.main()
