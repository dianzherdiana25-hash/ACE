"""Verify paired controls, trace validation, and replay across isolated workers."""

import json
import unittest
from unittest.mock import patch

from .contract import ContractError, canonical_json
from .dsl import compile_ast
from .evaluator.bank import development_bank
from .extension import Candidate, Definition, _source_selection, parse_definition
from .isolation import WorkerError, fit_isolated, replay_isolated


class ExtensionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        episodes = development_bank()[0]
        cls.samples = (episodes[0].fit_request, episodes[-1].fit_request)

    def test_controls_match_source_effort_and_replay_in_fresh_process(self):
        for raw in self.samples:
            extension = fit_isolated(raw, policy="c_extend")
            reset = fit_isolated(raw, policy="c_no_transfer")
            sham = fit_isolated(raw, policy="c_sham")
            closed = fit_isolated(raw, policy="c_no_extend")
            self.assertEqual(extension.trace["source"], reset.trace["source"])
            self.assertEqual(extension.trace["source"], sham.trace["source"])
            self.assertEqual(extension.trace["source_steps"], reset.trace["source_steps"])
            self.assertEqual(extension.trace["source_steps"], sham.trace["source_steps"])
            self.assertEqual(extension.trace["source_selected"], extension.trace["parent"])
            self.assertIsNone(reset.trace["parent"])
            self.assertGreater(sham.trace["sham_shift"], 0)
            self.assertLessEqual(len(closed.program.table), 4)

            for result, parent in ((extension, extension.trace["source_definition"]), (reset, None)):
                replay = replay_isolated(raw, parent)
                self.assertEqual(replay.trace["source"], [])
                self.assertEqual(replay.program.sha256, result.program.sha256)
                self.assertEqual(replay.trace["target"], result.trace["target"])
                self.assertEqual(replay.trace["target_steps"], result.trace["target_steps"])

    def test_sham_derangement_retains_equal_scores_as_uninformative(self):
        candidates = [Candidate(Definition("S", ((0, 0, 0),)), (), 1),
                      Candidate(Definition("S", ((0, 1, 0), (0, 1, 0))), (), 1)]
        selected, shift, unchanged = _source_selection(candidates, 4, True)
        self.assertEqual(shift, 1)
        self.assertTrue(unchanged)
        self.assertEqual(selected, candidates[0].definition)

    def test_replay_withholds_original_source_and_rejects_invalid_parent(self):
        raw = self.samples[0]
        result = fit_isolated(raw, policy="c_extend")
        original = json.loads(raw)
        original["source"] = [{"input": [0, 1], "output": [15]}]
        definition = result.trace["source_definition"]
        replay = replay_isolated(canonical_json(original), definition)
        self.assertEqual(replay.program.sha256, result.program.sha256)

        with self.assertRaises(ContractError):
            replay_isolated(raw, {"version": 1, "family": "G", "transitions": [[0, 0, 0]]})
        with self.assertRaises(ContractError):
            parse_definition({"version": 1, "family": "S", "transitions": [[-1, 0, 0]]})

    def test_small_budget_fails_without_returning_an_unchecked_definition(self):
        request = json.loads(self.samples[0])
        request["fuel"] = 1
        result = fit_isolated(canonical_json(request), policy="c_extend")
        self.assertEqual(result.status, "fuel_exhausted")
        self.assertEqual(result.steps, 1)
        self.assertEqual(result.trace["source"], [])
        self.assertEqual(result.trace["target"], [])
        self.assertEqual(compile_ast(result.program.ast), result.program)

    def test_worker_trace_with_forged_parent_fails_closed(self):
        raw = self.samples[0]
        good = fit_isolated(raw, policy="c_extend")
        reply = {
            "program": json.loads(good.program.ast), "candidates": good.candidates,
            "steps": good.steps, "status": good.status, "cpu_us": 10, "rss_kib": 1024,
            "trace": {**good.trace, "parent": "0" * 64},
        }
        with patch("e13.isolation._sandbox_python", return_value=(canonical_json(reply), 100)):
            with self.assertRaisesRegex(WorkerError, "invalid isolated fit result"):
                fit_isolated(raw, policy="c_extend")
