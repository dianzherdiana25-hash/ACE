import json
import random
import unittest
from dataclasses import replace

from .baseline import fit
from .contract import ContractError, canonical_json, parse_fit_request
from .development import run_fixture
from .public_bank import _graph_reference, public_fixtures
from .dsl import Fuel, FuelExhausted, compile_ast, predict


def ast(family, root, rule):
    return canonical_json({"family": family, "ast": {"op": root, "rule": {"op": rule}}})


class DevelopmentTests(unittest.TestCase):
    def test_public_fixtures(self):
        symbols, graph = public_fixtures()
        for fixture, family in ((symbols, "S"), (graph, "G")):
            with self.subTest(family=family):
                result = run_fixture(fixture, fit)
                self.assertEqual(result["family"], family)
                self.assertEqual((result["correct"], result["total"]), (3, 3))
                self.assertEqual(result["candidates"], 3)

    def test_fit_payload_excludes_probes_and_labels(self):
        fixture = public_fixtures()[1]
        canary = replace(fixture.probes[0], expected=73)
        observed = []

        def solver(raw):
            observed.append(raw)
            return fit(raw)

        original = run_fixture(fixture, solver)
        changed = run_fixture(replace(fixture, probes=(canary, *fixture.probes[1:])), solver)
        self.assertEqual(observed, [fixture.fit_request, fixture.fit_request])
        self.assertNotIn(canary.input, observed[0])
        self.assertEqual(original["program_sha256"], changed["program_sha256"])
        self.assertEqual(changed["correct"], 2)

    def test_fit_rejects_extra_fields_including_labels(self):
        raw = public_fixtures()[0].fit_request
        for field in ("labels", "grammar", "probes", "metadata", "split", "path"):
            request = json.loads(raw)
            request[field] = "canary"
            with self.subTest(field=field), self.assertRaises(ContractError):
                parse_fit_request(canonical_json(request))
        request = json.loads(raw)
        request["target"][0]["probe_label"] = 123
        with self.assertRaises(ContractError):
            parse_fit_request(canonical_json(request))

    def test_fit_rejects_non_opaque_id_and_duplicate_keys(self):
        raw = public_fixtures()[0].fit_request
        request = json.loads(raw)
        request["task_id"] = "graph-target-rule"
        with self.assertRaises(ContractError):
            parse_fit_request(canonical_json(request))
        duplicate = raw.replace(b'"version":1', b'"version":1,"version":1')
        self.assertNotEqual(duplicate, raw)
        with self.assertRaises(ContractError):
            parse_fit_request(duplicate)

    def test_probes_cannot_mutate_frozen_ast(self):
        candidate = fit(public_fixtures()[0].fit_request).program
        before = candidate.ast, candidate.sha256
        self.assertEqual(predict(candidate.ast, b"[1,3,2]", Fuel(20)), (1, 0))
        self.assertEqual(predict(candidate.ast, b"[9,9,2]", Fuel(20)), (0, 0))
        self.assertEqual((candidate.ast, candidate.sha256), before)

    def test_ast_rejects_unknown_and_wrongly_typed_nodes(self):
        cases = [
            ast("S", "exec", "lt"), ast("G", "path_cost", "network"),
            ast("G", "pair_flags", "lt"), ast("S", "pair_flags", []),
            b'{"family":"S","ast":{"op":"pair_flags","rule":{"op":"lt","file":"/tmp"}}}',
            b'{"family":"S","ast":{"op":"pair_flags","rule":{"op":"lt","op":"gt"}}}',
            b"[" * 1025,
        ]
        for case in cases:
            with self.subTest(case=case[:80]), self.assertRaises(ContractError):
                compile_ast(case)

    def test_symbol_fuel_stops_at_limit(self):
        program = ast("S", "pair_flags", "lt")
        limited = Fuel(2)
        with self.assertRaises(FuelExhausted):
            predict(program, b"[1,2,3]", limited)
        self.assertEqual(limited.used, 2)
        exact = Fuel(3)
        self.assertEqual(predict(program, b"[1,2,3]", exact), (1, 1))
        self.assertEqual(exact.used, 3)

    def test_graph_and_fit_enforce_fuel(self):
        fixture = public_fixtures()[1]
        program = ast("G", "path_cost", "different")
        limited = Fuel(1)
        with self.assertRaises(FuelExhausted):
            predict(program, fixture.probes[0].input, limited)
        self.assertEqual(limited.used, 1)
        request = json.loads(fixture.fit_request)
        request["fuel"] = 1
        with self.assertRaises(FuelExhausted):
            fit(canonical_json(request))

    def test_predict_rejects_invalid_probe_inputs(self):
        cases = [
            (ast("S", "pair_flags", "eq"), b"[true,2]"),
            (ast("S", "pair_flags", "eq"), b'{"input":[1,2],"output":[0]}'),
            (ast("G", "path_cost", "any"), b'{"nodes":2,"start":0,"goal":1,"edges":[[0,1,0,-1]]}'),
            (ast("G", "path_cost", "any"), b'{"nodes":2,"start":0,"goal":1,"edges":[[0,2,0,1]]}'),
        ]
        for program, raw in cases:
            with self.subTest(raw=raw), self.assertRaises(ContractError):
                predict(program, raw, Fuel(20))

    def test_graph_matches_reference_on_varied_small_graphs(self):
        generator = random.Random(13)
        for _ in range(40):
            nodes = generator.randint(1, 6)
            graph = {"nodes": nodes, "start": 0, "goal": nodes - 1, "edges": [
                [generator.randrange(nodes), generator.randrange(nodes),
                 generator.randrange(4), generator.randrange(5)]
                for _ in range(generator.randrange(24))
            ]}
            for rule in ("any", "different"):
                with self.subTest(rule=rule, graph=graph):
                    self.assertEqual(
                        predict(ast("G", "path_cost", rule), canonical_json(graph), Fuel(2_000)),
                        _graph_reference(graph, rule),
                    )
