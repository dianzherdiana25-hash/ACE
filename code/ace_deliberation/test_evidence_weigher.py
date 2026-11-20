"""Uji bobot eksak, keluarga berkorelasi, dan asal klaim."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_deliberation import evidence_weigher as weigher


def source(identifier, family, credibility, verified=True):
    return {"id": identifier, "family": family, "source_ref": f"fixture/src/{identifier}",
            "credibility": credibility, "verified": verified}


def evidence(identifier, src, stance, strength, claim="main"):
    return {"id": identifier, "claim": claim, "source": src, "evidence_ref": f"fixture/raw/{identifier}",
            "stance": stance, "strength": strength}


def exact(numerator, denominator):
    return {"numerator": numerator, "denominator": denominator}


class WeigherTests(unittest.TestCase):
    def fixture(self):
        return {
            "claims": ["unexplored", "main"],
            "sources": [source("s1", "same", "0.8"), source("s2", "same", "0.7"),
                        source("s3", "other", 1), source("s4", "unverified", 1, False)],
            "evidence": [evidence("a", "s1", "support", "0.5"),
                         evidence("b", "s2", "support", "0.9"),
                         evidence("c", "s2", "oppose", "0.8"),
                         evidence("d", "s3", "support", "0.1"),
                         evidence("e", "s4", "support", 1)],
        }

    def test_uses_one_voice_per_family_per_side_and_preserves_conflict(self):
        result = weigher.weigh_evidence(self.fixture())
        main, unexplored = result["claims"]
        self.assertEqual((main["support"], main["oppose"], main["margin"]),
                         (exact(73, 100), exact(14, 25), exact(17, 100)))
        self.assertEqual(main["contradictory_families"], ["same"])
        trace = {row["evidence_id"]: row for row in main["evidence"]}
        self.assertEqual(trace["b"]["counted_weight"], exact(63, 100))
        self.assertEqual(trace["b"]["source_ref"], "fixture/src/s2")
        self.assertEqual(trace["a"]["state"], "same_family_stronger_or_earlier_id")
        self.assertEqual(trace["e"]["state"], "unverified_source")
        self.assertEqual(trace["e"]["counted_weight"], exact(0, 1))
        self.assertEqual((unexplored["support"], unexplored["evidence"]), (exact(0, 1), []))

    def test_tie_uses_id_and_result_is_independent_of_input_order(self):
        raw = {"claims": ["main"], "sources": [source("s", "x", 1)],
               "evidence": [evidence("later", "s", "support", 1), evidence("earlier", "s", "support", 1)]}
        expected = weigher.weigh_evidence(raw)
        self.assertEqual(expected["claims"][0]["evidence"][0]["evidence_id"], "earlier")
        self.assertEqual(expected["claims"][0]["evidence"][0]["state"], "counted")
        self.assertEqual(expected, weigher.weigh_evidence({**raw, "evidence": raw["evidence"][::-1]}))

    def test_rejects_unknown_source_duplicate_reference_and_invalid_weight(self):
        for changes in ({"source": "unknown"}, {"claim": "unknown"},
                        {"evidence_ref": "fixture/raw/b"}, {"strength": "1.5"}, {"strength": True}):
            with self.subTest(changes=changes), self.assertRaises(weigher.EvidenceError):
                raw = self.fixture()
                raw["evidence"][0].update(changes)
                weigher.weigh_evidence(raw)

    def test_independent_source_can_be_relevant_to_distinct_claims(self):
        raw = {"claims": ["main", "other"], "sources": [source("s", "a", 1)],
               "evidence": [evidence("e1", "s", "support", 1),
                            {**evidence("e2", "s", "oppose", 1, claim="other"),
                             "evidence_ref": "fixture/raw/e1"}]}
        main, other = weigher.weigh_evidence(raw)["claims"]
        self.assertEqual(main["margin"], exact(1, 1))
        self.assertEqual(other["margin"], exact(-1, 1))

    def test_verified_zero_weight_does_not_count_as_independent_support(self):
        raw = {"claims": ["main"], "sources": [source("s", "a", 0)],
               "evidence": [evidence("e1", "s", "support", 1)]}
        claim, = weigher.weigh_evidence(raw)["claims"]
        self.assertEqual(claim["counted_families"]["support"], [])
        self.assertEqual(claim["evidence"][0]["state"], "zero_weight")

    def test_cli_keeps_rejected_weight_trace(self):
        path = Path(self.enterContext(TemporaryDirectory())) / "evidence.json"
        path.write_text(json.dumps(self.fixture()), encoding="utf-8")
        with redirect_stdout(StringIO()) as output:
            self.assertEqual(weigher.main([str(path)]), 0)
        trace = json.loads(output.getvalue())["claims"][0]["evidence"]
        self.assertIn("unverified_source", [row["state"] for row in trace])

    def test_smallest_decimal_products_keep_exact_precision(self):
        raw = {"claims": ["main"], "sources": [source("s", "a", "0.000000000001")],
               "evidence": [evidence("e1", "s", "oppose", "0.000000000001")]}
        claim, = weigher.weigh_evidence(raw)["claims"]
        self.assertEqual(claim["oppose"], exact(1, 10**24))
        self.assertEqual(claim["margin"], exact(-1, 10**24))

    def test_source_ref_duplicates_cannot_create_two_families(self):
        raw = self.fixture()
        raw["sources"][1]["source_ref"] = raw["sources"][0]["source_ref"]
        raw["sources"][1]["family"] = "misleading"
        with self.assertRaisesRegex(weigher.EvidenceError, "Rujukan sumber ganda"):
            weigher.weigh_evidence(raw)

    def test_verified_flag_must_be_boolean_not_truthy(self):
        raw = self.fixture()
        raw["sources"][0]["verified"] = "verified"
        with self.assertRaisesRegex(weigher.EvidenceError, "boolean eksplisit"):
            weigher.weigh_evidence(raw)

    def test_report_is_independent_of_catalog_order(self):
        raw = self.fixture()
        reversed_raw = {key: values[::-1] for key, values in raw.items()}
        self.assertEqual(weigher.weigh_evidence(raw), weigher.weigh_evidence(reversed_raw))

    def test_verified_challenger_is_preserved_even_when_support_wins(self):
        raw = self.fixture()
        main = weigher.weigh_evidence(raw)["claims"][0]
        challenger, = [row for row in main["evidence"] if row["stance"] == "oppose"]
        self.assertEqual(challenger["evidence_ref"], "fixture/raw/c")
        self.assertEqual(challenger["counted_weight"], exact(14, 25))
