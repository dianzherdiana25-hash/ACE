"""Uji pelabelan grounded dan rekomendasi yang ditambatkan pada bukti."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_deliberation import synthesis_engine as engine
from ace_deliberation.test_argument_graph import edge, node


def fixture():
    return {
        "graph": {"nodes": [node(name) for name in ("one", "two", "critic", "defender", "support")]
                  + [node("e1", "evidence"), node("e2", "evidence")],
                  "edges": [
                      edge("critic", "one", "attacks"), edge("defender", "critic", "attacks"),
                      edge("e1", "support"), edge("support", "one"), edge("e2", "two"),
                  ]},
        "choices": ["two", "one"], "recognized_evidence_refs": ["fixture/e1"], "min_support_refs": 1,
    }


class SynthesisTests(unittest.TestCase):
    def test_grounded_acceptance_propagates_through_defeated_attacker(self):
        result = engine.synthesize(fixture())
        self.assertEqual(result["recommended_choice"], "one")
        self.assertEqual(result["grounded_status"]["critic"], "rejected")
        self.assertEqual(result["grounded_layers"][-1], {"accepted": ["one"], "rejected": []})
        winner, loser = result["positions"]
        self.assertEqual(winner["attackers"], [{"id": "critic", "status": "rejected"}])
        self.assertEqual(winner["accepted_support"], [
            {"evidence_id": "e1", "source_ref": "fixture/e1",
             "support_path": [edge("e1", "support"), edge("support", "one")]},
        ])
        self.assertFalse(loser["meets_support_threshold"])
        self.assertEqual(result["unrecognized_evidence_refs"], ["fixture/e2"])

    def test_mutual_attack_leaves_supported_options_undecided(self):
        raw = fixture()
        raw["graph"]["edges"] = [edge("one", "two", "attacks"), edge("two", "one", "attacks"),
                                 edge("e1", "one"), edge("e2", "two")]
        result = engine.synthesize(raw)
        self.assertEqual(result["reason"], "insufficient_accepted_support")
        self.assertEqual(result["grounded_status"]["one"], "undecided")
        self.assertEqual(result["grounded_status"]["two"], "undecided")
        self.assertEqual([row["accepted_support"] for row in result["positions"]], [[], []])

    def test_unrecognized_evidence_cannot_veto_an_option(self):
        raw = fixture()
        raw["graph"]["edges"].append(edge("e2", "one", "attacks"))
        self.assertEqual(engine.synthesize(raw)["recommended_choice"], "one")
        raw["recognized_evidence_refs"].append("fixture/e2")
        report = engine.synthesize(raw)
        self.assertEqual(report["recommended_choice"], "two")
        self.assertEqual(report["grounded_status"]["one"], "rejected")

    def test_equal_independent_support_is_deferred(self):
        raw = fixture()
        raw["recognized_evidence_refs"].append("fixture/e2")
        report = engine.synthesize(raw)
        self.assertEqual(report["status"], "defer")
        self.assertEqual(report["reason"], "tie")
        self.assertIsNone(report["recommended_choice"])

    def test_rejected_intermediate_claim_cannot_carry_support(self):
        raw = fixture()
        raw["graph"]["edges"].append(edge("defender", "support", "attacks"))
        report = engine.synthesize(raw)
        self.assertEqual(report["grounded_status"]["support"], "rejected")
        self.assertEqual(report["grounded_status"]["one"], "accepted")
        self.assertIsNone(report["recommended_choice"])

    def test_reordering_preserves_output_and_cli_accepts_only_declared_refs(self):
        raw = fixture()
        first = engine.synthesize(raw)
        raw["graph"]["nodes"].reverse()
        raw["graph"]["edges"].reverse()
        raw["choices"].reverse()
        self.assertEqual(engine.synthesize(raw), first)
        path = Path(self.enterContext(TemporaryDirectory())) / "arguments.json"
        path.write_text(json.dumps(raw), encoding="utf-8")
        with redirect_stdout(StringIO()) as output:
            self.assertEqual(engine.main([str(path)]), 0)
        self.assertEqual(json.loads(output.getvalue()), first)
        with self.assertRaisesRegex(engine.SynthesisError, "tidak ada"):
            engine.synthesize({**raw, "recognized_evidence_refs": ["fixture/unknown"]})

    def test_all_attack_graphs_on_three_claims_match_grounded_characteristic_function(self):
        from itertools import product

        keys = {"a", "b", "c"}
        arcs = [(source, target) for source in sorted(keys) for target in sorted(keys) if source != target]
        for flags in product((False, True), repeat=len(arcs)):
            active_arcs = {arc for arc, live in zip(arcs, flags) if live}
            accepted = set()
            while True:
                attacked = {target for source, target in active_arcs if source in accepted}
                next_accepted = {node_id for node_id in keys
                                 if all(source in attacked for source, target in active_arcs if target == node_id)}
                if next_accepted == accepted:
                    break
                accepted = next_accepted
            expected = {key: ("accepted" if key in accepted else "rejected" if key in attacked else "undecided")
                        for key in keys}
            actual, _, _ = engine._grounded(keys, [edge(*arc, "attacks") for arc in active_arcs])
            self.assertEqual(actual, expected)

    def test_aliases_of_one_evidence_ref_cannot_meet_two_source_rule(self):
        raw = fixture()
        raw["graph"]["nodes"].append({**node("alias", "evidence"), "source_ref": "fixture/e1"})
        raw["graph"]["edges"].append(edge("alias", "one"))
        raw["min_support_refs"] = 2
        report = engine.synthesize(raw)
        winner = report["positions"][0]
        self.assertFalse(winner["meets_support_threshold"])
        self.assertEqual(len(winner["accepted_support"]), 1)
        self.assertEqual(report["status"], "defer")

    def test_support_cycle_does_not_destroy_accepted_evidence_path(self):
        raw = fixture()
        raw["graph"]["edges"].append(edge("one", "support"))
        report = engine.synthesize(raw)
        path = report["positions"][0]["accepted_support"][0]["support_path"]
        self.assertEqual(len(path), 2)
        self.assertEqual(path[-1]["target"], "one")

    def test_zero_support_threshold_is_not_a_way_to_choose_unsupported_claims(self):
        with self.assertRaisesRegex(engine.SynthesisError, "min_support_refs"):
            engine.synthesize({**fixture(), "min_support_refs": 0})
