"""Regression tests for the bounded generic machines and isolated pilot."""

import json
from copy import deepcopy
import unittest
from unittest.mock import patch

from .blind import _machine
from .contract import ContractError, canonical_json
from .dsl import Fuel, FuelExhausted, compile_ast, predict
from .evaluator.bank import _chain, development_bank
from .evaluator.oracle import graph
from .evaluator.pilot import _record, summarize, verify_replay
from .isolation import WorkerError, fit_isolated


class MachineTests(unittest.TestCase):
    def test_typed_machines_reject_invalid_state_bit_shape_and_family(self):
        programs = (
            ("S", {"op": "symbol_machine", "table": [[[1, 0], [0, 1], [0, 0]]]}),
            ("S", {"op": "symbol_machine", "table": [[[0, 2], [0, 1], [0, 0]]]}),
            ("S", {"op": "graph_machine", "table": [[0, 0, 0]], "accept": [1]}),
            ("G", {"op": "graph_machine", "table": [[0, -2, 0]], "accept": [1]}),
            ("G", {"op": "graph_machine", "table": [[0, 0, 0]], "accept": [1, 0]}),
            ("G", {"op": "graph_machine", "table": [[0, 0]], "accept": [1]}),
        )
        for family, ast in programs:
            with self.subTest(ast=ast), self.assertRaises(ContractError):
                compile_ast(canonical_json({"family": family, "ast": ast}))

    def test_graph_machine_against_oracle_on_chains_and_zero_cost_cycle(self):
        machine = _machine("G", ((1, 1, 1), (0, 0, 0)), (1, 0))
        cases = [_chain([]), _chain([0]), _chain([0, 1]), _chain([0, 0, 1]),
                 {"nodes": 2, "start": 0, "goal": 1, "edges": [[0, 0, 1, 0], [0, 1, 0, 3]]}]
        for value in cases:
            with self.subTest(value=value):
                self.assertEqual(predict(machine.ast, canonical_json(value), Fuel(500)),
                                 graph("edge_even", value))
        with self.assertRaises(FuelExhausted):
            predict(machine.ast, canonical_json(cases[-1]), Fuel(1))

    def test_both_families_fit_in_isolation_without_source_or_metadata(self):
        episodes = development_bank()[0]
        for episode in (episodes[0], episodes[-1]):
            raw = json.loads(episode.fit_request)
            result = fit_isolated(episode.fit_request, policy="blind")
            raw["task_id"] = "ab" * 16
            raw["source"] = raw["target"]
            raw["seed"] = 0
            comparison = fit_isolated(canonical_json(raw), policy="blind")
            self.assertEqual(result.status, "fit")
            self.assertEqual(result.program.ast, comparison.program.ast)
            self.assertEqual(result.steps, comparison.steps)
            for demo in raw["target"]:
                prediction = predict(result.program.ast, canonical_json(demo["input"]), Fuel(30000))
                self.assertEqual(canonical_json(prediction), canonical_json(demo["output"]))
            raw["fuel"] = 1
            limited = fit_isolated(canonical_json(raw), policy="blind")
            self.assertEqual(limited.status, "fuel_exhausted")
            self.assertEqual(limited.steps, 1)

    def test_pilot_counts_worker_failures_in_both_denominators(self):
        episode = development_bank()[0][0]
        with patch("e13.evaluator.pilot.fit_isolated", side_effect=WorkerError("unavailable")):
            row = _record(episode, "blind")
        self.assertEqual(row["fit_status"], "worker_error")
        self.assertEqual([(s["correct"], s["total"], s["failures"]) for s in summarize([row])],
                         [(0, 6, 6), (0, 6, 6)])


    def test_beam_is_deterministic_and_keeps_a_bounded_ast_on_fuel_stop(self):
        episodes = development_bank()[0]
        for episode in (episodes[0], episodes[-1]):
            first = fit_isolated(episode.fit_request, policy="beam")
            second = fit_isolated(episode.fit_request, policy="beam")
            self.assertEqual((first.program.sha256, first.candidates, first.steps),
                             (second.program.sha256, second.candidates, second.steps))
            self.assertLessEqual(first.candidates, 160)
            request = json.loads(episode.fit_request)
            request["fuel"] = 1
            limited = fit_isolated(canonical_json(request), policy="beam")
            self.assertEqual(limited.status, "fuel_exhausted")
            self.assertEqual(limited.steps, 1)
            self.assertEqual(limited.program.family, episode.family)

    def test_replay_check_rejects_changed_result_and_accepts_timing_change(self):
        reference = {"mode": "development", "runs": [
            {"fit_steps": 21, "worker": {"cpu_us": 10}, "scoring_cpu_us": 4}
        ]}
        replay = deepcopy(reference)
        replay["runs"][0]["worker"]["cpu_us"] = 99
        verify_replay(reference, replay)
        replay["runs"][0]["fit_steps"] = 22
        with self.assertRaisesRegex(ValueError, "deterministic fields"):
            verify_replay(reference, replay)
