"""Tes unit untuk tools/story_consistency_gate.py (AG88)."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from tools.story_consistency_gate import SCHEMA, check_chapter_consistency, main


def _sample_story_state() -> dict:
    return {
        "schema": "ace.story-state.v1",
        "characters": {
            "arya": {
                "character_id": "arya",
                "name": "Arya",
                "status": "alive",
                "status_tick": 0,
                "location": "Pelabuhan",
            },
            "seno": {
                "character_id": "seno",
                "name": "Seno",
                "status": "dead",
                "status_tick": 4,
                "location": "Benteng",
            },
        },
        "timeline": [
            {"event_id": "ev-benteng-jatuh", "tick": 8, "summary": "Benteng Utara direbut", "participants": ["arya"]},
        ],
        "facts": [
            {
                "fact_id": "fact-jembatan",
                "subject": "jembatan_utara",
                "predicate": "kondisi",
                "value": "roboh",
                "valid_from_tick": 6,
                "valid_until_tick": None,
            }
        ],
        "promises": [
            {
                "promise_id": "prom-peta",
                "description": "Peta kuno diserahkan ke kapten",
                "introduced_tick": 5,
                "status": "open",
            }
        ],
    }


class StoryConsistencyGateTests(unittest.TestCase):
    def test_clean_chapter_passes_lolos(self) -> None:
        state = _sample_story_state()
        clean_draft = {
            "chapter_id": "bab-09",
            "tick": 9,
            "active_characters": ["arya"],
            "fact_claims": [
                {"subject": "jembatan_utara", "predicate": "kondisi", "value": "roboh", "tick": 9},
            ],
            "timeline_markers": [
                {"marker_id": "m-pasca-benteng", "tick": 9, "after_event_id": "ev-benteng-jatuh"},
            ],
            "promise_updates": [
                {"promise_id": "prom-peta", "status": "fulfilled", "resolved_tick": 9},
            ],
        }
        report = check_chapter_consistency(state, clean_draft)
        self.assertEqual(report["schema"], SCHEMA)
        self.assertEqual(report["verdict"], "lolos")
        self.assertTrue(report["passed"])
        self.assertEqual(report["contradictions"], [])

    def test_flags_two_distinct_contradiction_types_and_cli(self) -> None:
        state = _sample_story_state()
        broken_draft = {
            "chapter_id": "bab-cacat",
            "tick": 7,
            "active_characters": ["arya", "seno"],  # Kontradiksi 1: tokoh mati masih aktif.
            "fact_claims": [
                {"subject": "seno", "predicate": "location", "value": "Pasar", "tick": 7},
                {"subject": "jembatan_utara", "predicate": "kondisi", "value": "utuh", "tick": 7},
            ],
            "timeline_markers": [
                # Kontradiksi 2: anakronisme linimasa (mengklaim sesudah ev-benteng-jatuh tick 8 saat bab tick 7).
                {"marker_id": "m-anakronisme", "tick": 7, "after_event_id": "ev-benteng-jatuh"},
            ],
        }
        report = check_chapter_consistency(state, broken_draft)
        self.assertEqual(report["verdict"], "konflik")
        self.assertFalse(report["passed"])
        types = set(report["contradiction_types"])
        self.assertIn("dead_character_active", types)
        self.assertIn("timeline_anachronism", types)
        self.assertIn("dead_character_fact_conflict", types)
        self.assertIn("fact_contradiction", types)

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            state_path = tmp / "state.json"
            draft_path = tmp / "draft.json"
            clean_path = tmp / "clean.json"
            state_path.write_text(json.dumps(state), encoding="utf-8")
            draft_path.write_text(json.dumps(broken_draft), encoding="utf-8")
            clean_path.write_text(
                json.dumps({"chapter_id": "bab-ok", "tick": 9, "active_characters": ["arya"]}),
                encoding="utf-8",
            )
            self.assertEqual(main(["--state", str(state_path), "--draft", str(draft_path)]), 2)
            self.assertEqual(main(["--state", str(state_path), "--draft", str(clean_path)]), 0)


if __name__ == "__main__":
    unittest.main()
