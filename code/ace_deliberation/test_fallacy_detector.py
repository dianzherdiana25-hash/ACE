"""Uji countermodel serta pembedaan struktur cacat dan premis kontradiktif."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_deliberation import fallacy_detector as detector


def atom(name):
    return {"atom": name}


def op(name, *args):
    return {"op": name, "args": list(args)}


def argument(premises, conclusion):
    return {"premises": [{"formula": formula, "source_ref": f"fixture/p{i}"}
                        for i, formula in enumerate(premises)],
            "conclusion": {"formula": conclusion, "source_ref": "fixture/conclusion"}}


class FallacyTests(unittest.TestCase):
    def test_affirming_consequent_includes_concrete_countermodel(self):
        p, q = atom("p"), atom("q")
        result = detector.inspect_argument(argument([op("implies", p, q), q], p))
        self.assertEqual(result["status"], "counterexample")
        self.assertEqual(result["first_counterexample"], {"p": False, "q": True})
        self.assertEqual(result["premise_satisfying_count"], 2)
        self.assertEqual(result["counterexample_count"], 1)
        self.assertEqual(result["findings"], [
            {"code": "affirming_consequent", "premise_refs": ["fixture/p0", "fixture/p1"]},
        ])

    def test_denying_antecedent_and_inclusive_or_have_distinct_witnesses(self):
        p, q = atom("p"), atom("q")
        deny = detector.inspect_argument(argument([op("implies", p, q), op("not", p)], op("not", q)))
        self.assertEqual(deny["findings"][0]["code"], "denying_antecedent")
        self.assertEqual(deny["first_counterexample"], {"p": False, "q": True})
        disjunct = detector.inspect_argument(argument([op("or", p, q), p], op("not", q)))
        self.assertEqual(disjunct["findings"][0]["code"], "affirming_inclusive_disjunct")
        self.assertEqual(disjunct["first_counterexample"], {"p": True, "q": True})

    def test_valid_modus_ponens_and_modus_tollens_do_not_raise_findings(self):
        p, q = atom("p"), atom("q")
        for raw in (argument([op("implies", p, q), p], q),
                    argument([op("implies", p, q), op("not", q)], op("not", p))):
            with self.subTest(raw=raw):
                result = detector.inspect_argument(raw)
                self.assertEqual(result["status"], "entailed")
                self.assertEqual(result["findings"], [])
                self.assertIsNone(result["first_counterexample"])

    def test_inconsistent_premises_are_reported_instead_of_vacuous_success(self):
        p = atom("p")
        result = detector.inspect_argument(argument([p, op("not", p)], atom("unrelated")))
        self.assertEqual(result["status"], "inconsistent_premises")
        self.assertEqual(result["premise_satisfying_count"], 0)
        self.assertEqual(result["counterexample_count"], 0)

    def test_repeated_conclusion_is_reported_even_for_entailment(self):
        p = atom("p")
        result = detector.inspect_argument(argument([p], p))
        self.assertEqual(result["status"], "entailed")
        self.assertEqual(result["findings"],
                         [{"code": "conclusion_restated_as_premise", "premise_refs": ["fixture/p0"]}])

    def test_previously_invalid_pattern_with_independent_valid_proof_is_not_flagged(self):
        q, r, p = atom("q"), atom("r"), atom("p")
        result = detector.inspect_argument(argument([op("implies", p, q), q, op("implies", r, p), r], p))
        self.assertEqual(result["status"], "entailed")
        self.assertEqual(result["findings"], [])

    def test_bounds_reject_atom_overflow_depth_overflow_unknown_operator_and_untrusted_names(self):
        deeply_nested = atom("p")
        for _ in range(16):
            deeply_nested = op("not", deeply_nested)
        for raw in (argument([atom(f"a{i}") for i in range(11)], atom("a0")),
                    argument([deeply_nested], atom("p")), argument([op("nor", atom("p"))], atom("q")),
                    argument([atom("bad name")], atom("q"))):
            with self.subTest(raw=raw), self.assertRaises(detector.FormulaError):
                detector.inspect_argument(raw)

    def test_cli_reproduces_unclassified_invalid_inference(self):
        raw = argument([atom("a")], atom("b"))
        path = Path(self.enterContext(TemporaryDirectory())) / "argument.json"
        path.write_text(json.dumps(raw), encoding="utf-8")
        with redirect_stdout(StringIO()) as output:
            self.assertEqual(detector.main([str(path)]), 1)
        result = json.loads(output.getvalue())
        self.assertEqual(result["first_counterexample"], {"a": True, "b": False})
        self.assertEqual(result["findings"], [])

    def test_proof_reports_countermodel_when_individual_premise_removed(self):
        p, q, r = atom("p"), atom("q"), atom("r")
        raw = argument([op("implies", p, q), p, op("or", r, op("not", r))], q)
        report = detector.inspect_argument(raw)
        self.assertEqual(report["status"], "entailed")
        self.assertEqual(report["premise_necessity_witnesses"], [
            {"omitted_ref": "fixture/p0", "counterexample": {"p": True, "q": False, "r": False}},
            {"omitted_ref": "fixture/p1", "counterexample": {"p": False, "q": False, "r": False}},
        ])

    def test_renumbering_premise_order_preserves_report_when_source_refs_stay(self):
        p, q = atom("p"), atom("q")
        raw = argument([op("implies", p, q), q], p)
        result = detector.inspect_argument(raw)
        raw["premises"].reverse()
        self.assertEqual(detector.inspect_argument(raw), result)

    def test_conclusion_and_premise_cannot_share_one_unqualified_source_ref(self):
        raw = argument([atom("p")], atom("q"))
        raw["conclusion"]["source_ref"] = raw["premises"][0]["source_ref"]
        with self.assertRaisesRegex(detector.FormulaError, "rujukan formula harus terpisah".capitalize()):
            detector.inspect_argument(raw)
