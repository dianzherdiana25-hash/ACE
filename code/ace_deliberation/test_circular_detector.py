"""Uji fondasi yang memutus siklus, prasyarat AND, dan saksi sumber."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_deliberation import circular_detector as circular


def rule(identifier, conclusion, *premises):
    return {"id": identifier, "conclusion": conclusion, "premises": list(premises),
            "source_ref": f"fixture/rule/{identifier}"}


def fixture():
    return {"claims": [{"id": key, "source_ref": f"fixture/claim/{key}"} for key in ("a", "b", "c", "d")],
            "foundations": [{"id": "c", "source_ref": "fixture/axiom/c"}],
            "rules": [rule("ab", "a", "b"), rule("ba", "b", "a", "d"), rule("depend", "d", "b")]}


class CircularTests(unittest.TestCase):
    def test_three_node_cycle_has_reproducible_witness_and_source_refs(self):
        report = circular.detect(fixture())
        cycle, = report["cycles"]
        self.assertEqual(cycle["claims"], ["a", "b", "d"])
        self.assertEqual(cycle["witness"], [
            {"source": "a", "target": "b", "rule": "ab", "source_ref": "fixture/rule/ab"},
            {"source": "b", "target": "a", "rule": "ba", "source_ref": "fixture/rule/ba"},
        ])
        self.assertEqual(report["ungrounded_non_cyclic"], [])
        self.assertEqual(report["grounded"][0]["claim"], "c")

    def test_local_outside_grounding_breaks_cycle_through_alternative_rule(self):
        raw = fixture()
        raw["rules"].append(rule("independent", "b", "c"))
        report = circular.detect(raw)
        self.assertEqual(report["cycles"], [])
        self.assertEqual([row["claim"] for row in report["grounded"]], ["a", "b", "c", "d"])
        proof = report["grounded"][1]
        self.assertEqual(proof["rule"], "independent")
        self.assertEqual(proof["premises"], ["c"])

    def test_multi_premise_rule_does_not_ground_from_one_known_parent(self):
        raw = fixture()
        raw["rules"][-1] = rule("isolated", "d", "a", "c")
        raw["rules"].append(rule("partial", "a", "c", "d"))
        report = circular.detect(raw)
        self.assertEqual([row["claim"] for row in report["grounded"]], ["c"])
        self.assertTrue(report["cycles"])

    def test_unresolved_premise_outside_cycle_is_separate_witness_data(self):
        raw = fixture()
        raw["rules"].pop()
        cycle, = circular.detect(raw)["cycles"]
        self.assertEqual(cycle["claims"], ["a", "b"])
        self.assertEqual(cycle["external_unresolved_premises"], ["d"])

    def test_self_reference_reported_without_forcing_it_into_other_cycle(self):
        raw = fixture()
        raw["rules"] = [rule("self", "a", "a"), rule("lateral", "b", "a")]
        report = circular.detect(raw)
        self.assertEqual(report["cycles"][0]["claims"], ["a"])
        self.assertEqual(report["ungrounded_non_cyclic"], ["b", "d"])

    def test_invalid_foundation_and_duplicate_reference_are_refused(self):
        raw = fixture()
        for updates in ({"foundations": [{"id": "missing", "source_ref": "fixture/bad"}]},
                        {"rules": [*raw["rules"], raw["rules"][0]]},
                        {"rules": [rule("dup", "a", "b", "b")]}):
            with self.subTest(updates=updates), self.assertRaises(circular.CircularError):
                circular.detect({**raw, **updates})

    def test_cli_is_stable_across_catalog_shuffle_and_reports_cycle(self):
        raw = fixture()
        expected = circular.detect(raw)
        for values in raw.values():
            values.reverse()
        path = Path(self.enterContext(TemporaryDirectory())) / "circular.json"
        path.write_text(json.dumps(raw), encoding="utf-8")
        with redirect_stdout(StringIO()) as output:
            self.assertEqual(circular.main([str(path)]), 1)
        self.assertEqual(json.loads(output.getvalue()), expected)

    def test_closure_matches_naive_fixpoint_for_every_subset_of_rules(self):
        from itertools import combinations

        raw = fixture()
        rules = [*raw["rules"], rule("root", "a", "c"), rule("other", "d", "a", "c")]
        for size in range(len(rules) + 1):
            for subset in combinations(rules, size):
                closure = {"c"}
                while True:
                    added = {row["conclusion"] for row in subset if set(row["premises"]) <= closure}
                    if added <= closure:
                        break
                    closure |= added
                report = circular.detect({**raw, "rules": list(subset)})
                with self.subTest(rules=[rule["id"] for rule in subset]):
                    self.assertEqual({item["claim"] for item in report["grounded"]}, closure)
                    self.assertFalse(closure & {member for cycle in report["cycles"] for member in cycle["claims"]})

    def test_founded_self_reference_is_not_reported_as_unsupported_cycle(self):
        raw = fixture()
        raw["rules"] = [rule("self-founded", "c", "c"), rule("self-open", "a", "a")]
        report = circular.detect(raw)
        self.assertEqual([cycle["claims"] for cycle in report["cycles"]], [["a"]])
        self.assertEqual(report["grounded"], [
            {"claim": "c", "kind": "foundation", "claim_ref": "fixture/claim/c", "source_ref": "fixture/axiom/c"},
        ])

    def test_orphan_claim_without_rules_is_visible_and_never_used_as_foundation(self):
        raw = {**fixture(), "rules": [], "foundations": []}
        report = circular.detect(raw)
        self.assertEqual(report["ungrounded_non_cyclic"], ["a", "b", "c", "d"])
        self.assertEqual(report["cycles"], [])
        self.assertEqual(report["grounded"], [])
