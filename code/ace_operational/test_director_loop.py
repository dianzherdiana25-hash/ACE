"""Phase 2 tests for the local Research Director loop.

The director is a local model whose output is never trusted: these
tests pin the fail-closed parsing, the category vocabulary, the
fact-citation requirement, harness-owned ranking, cross-cycle
deduplication and model-guess provenance in the cognitive memory.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from ace_operational.cognitive_memory import CognitiveMemory
from ace_operational.director_loop import (
    DirectorLoop,
    ProposalRejected,
    build_observation,
    parse_proposals,
    render_prompt,
)

OBS = build_observation(
    gates={"G0": "PASS_SESSION", "G1": "NOT_ASSESSED"},
    gaps=[{"id": "gap-sandbox", "what": "OMEGA-05 blocked: no bwrap"},
          {"id": "gap-shipping", "what": "shipping family weak in OMEGA-11"}],
    results=[{"id": "omega11-contrast", "summary": "grammar >= token-search"}])

GOOD = json.dumps({"proposals": [
    {"title": "Uji pilot A/B/C pada tugas tertahan", "category": "experiment",
     "rationale": "G1 masih NOT_ASSESSED dan belum ada pilot kustodi penuh",
     "value": 5, "effort": 4, "based_on": ["G1"]},
    {"title": "Selidiki kelemahan keluarga shipping", "category": "measurement",
     "rationale": "Hasil OMEGA-11 menunjukkan shipping jauh tertinggal",
     "value": 4, "effort": 2, "based_on": ["gap-shipping", "omega11-contrast"]},
]})


def loop_in(tmp: str) -> DirectorLoop:
    return DirectorLoop(Path(tmp) / "agenda.json")


class ParseTests(unittest.TestCase):
    def test_valid_reply_is_ranked_by_the_harness(self):
        proposals = parse_proposals(GOOD, OBS)
        self.assertEqual([p["rank"] for p in proposals], [1, 2])
        self.assertEqual(proposals[0]["value"], 5)
        self.assertAlmostEqual(proposals[1]["score"], 2.0)

    def test_garbage_is_rejected_fail_closed(self):
        with self.assertRaises(ProposalRejected):
            parse_proposals("Maaf, saya tidak bisa menjawab.", OBS)

    def test_unknown_category_is_rejected(self):
        bad = json.dumps({"proposals": [
            {"title": "X", "category": "marketing", "rationale": "r",
             "value": 3, "effort": 2, "based_on": ["G1"]}]})
        with self.assertRaises(ProposalRejected):
            parse_proposals(bad, OBS)

    def test_fabricated_fact_citation_is_rejected(self):
        bad = json.dumps({"proposals": [
            {"title": "X", "category": "experiment", "rationale": "r",
             "value": 3, "effort": 2, "based_on": ["nonexistent-gap"]}]})
        with self.assertRaises(ProposalRejected):
            parse_proposals(bad, OBS)

    def test_too_many_proposals_is_rejected(self):
        many = {"proposals": [
            {"title": f"T{i}", "category": "experiment", "rationale": "r",
             "value": 3, "effort": 2, "based_on": ["G1"]} for i in range(6)]}
        with self.assertRaises(ProposalRejected):
            parse_proposals(json.dumps(many), OBS)

    def test_fenced_json_is_accepted(self):
        proposals = parse_proposals(f"```json\n{GOOD}\n```", OBS)
        self.assertEqual(len(proposals), 2)


class CycleTests(unittest.TestCase):
    def test_cycle_records_agenda_and_model_guess_memory(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory = CognitiveMemory(Path(tmp) / "mem")
            loop = DirectorLoop(Path(tmp) / "agenda.json", memory=memory)
            record = loop.run_cycle(OBS, lambda prompt: GOOD)
            self.assertEqual(record["status"], "accepted")
            self.assertEqual(len(record["proposals"]), 2)
            self.assertEqual(len(loop.current_agenda()), 2)
            hits = memory.recall("director_proposal agenda prioritas")["results"]
            episodic = [h for h in hits if h["kind"] == "episodic"]
            self.assertTrue(episodic)
            self.assertTrue(all(
                h["source"]["kind"] == "model" and h["guess"] for h in episodic))

    def test_rejected_cycle_is_recorded_with_reason(self):
        with tempfile.TemporaryDirectory() as tmp:
            loop = loop_in(tmp)
            record = loop.run_cycle(OBS, lambda prompt: "bukan json")
            self.assertEqual(record["status"], "rejected")
            self.assertIn("reason", record)
            self.assertEqual(loop.current_agenda(), [])

    def test_duplicates_across_cycles_are_dropped(self):
        with tempfile.TemporaryDirectory() as tmp:
            loop = loop_in(tmp)
            loop.run_cycle(OBS, lambda prompt: GOOD)
            second = loop.run_cycle(OBS, lambda prompt: GOOD)
            self.assertEqual(second["status"], "accepted")
            self.assertEqual(second["proposals"], [])
            self.assertEqual(second["duplicates_dropped"], 2)

    def test_prompt_carries_the_observation(self):
        seen = {}

        def infer(prompt: str) -> str:
            seen["prompt"] = prompt
            return GOOD

        with tempfile.TemporaryDirectory() as tmp:
            loop_in(tmp).run_cycle(OBS, infer)
        self.assertIn("gap-shipping", seen["prompt"])
        self.assertIn("NOT_ASSESSED", seen["prompt"])
        self.assertEqual(render_prompt(OBS), seen["prompt"])


if __name__ == "__main__":
    unittest.main()
