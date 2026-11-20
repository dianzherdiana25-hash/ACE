"""Verifier dekomposisi, saksi logis, dan asumsi peluang."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_deliberation import question_decomposer as model


def q(numerator, denominator=1):
    return {"numerator": numerator, "denominator": denominator}


def atom(name, estimate=None):
    return {"id": name, "question": f"Apakah {name} terjadi?", "source_ref": f"q/{name}",
            "probability": estimate, "forecast_ref": f"p/{name}" if estimate is not None else None}


def ref(name):
    return {"atom": name}


def expr(op, *children):
    return {"op": op, "children": list(children)}


def fixture():
    return {
        "question_id": "group", "question_ref": "q/group", "independence_ref": "q/independence",
        "expression": expr("all", ref("a"), expr("any", ref("b"), ref("c"))),
        "atoms": [atom("a", q(1, 2)), atom("b", q(1, 3)), atom("c", q(1, 4))],
    }


class DecompositionTests(unittest.TestCase):
    def test_independent_nested_probability_matches_manual_arithmetic(self):
        result = model.decompose(fixture())
        # P(B or C) = 1/3 + 1/4 - 1/12, lalu P(A) dikalikan sekali.
        self.assertEqual(result["probability"], q(1, 4))
        self.assertEqual(result["probability_status"], "conditional_on_independence")
        self.assertEqual(result["independence_ref"], "q/independence")
        self.assertEqual(result["assignments"], 8)
        self.assertEqual(result["satisfying"], 3)
        self.assertEqual(result["first_true_witness"], {"a": True, "b": False, "c": True})
        self.assertEqual(result["first_false_witness"], {"a": False, "b": False, "c": False})

    def test_questions_are_ranked_by_pivotal_assignment_then_identifier(self):
        report = model.decompose(fixture())
        self.assertEqual([(item["id"], item["pivotal_assignments"]) for item in report["subquestions"]],
                         [("a", 3), ("b", 1), ("c", 1)])
        self.assertEqual(report["subquestions"][0]["source_ref"], "q/a")
        self.assertEqual(report["subquestions"][0]["forecast_ref"], "p/a")

    def test_repeated_atom_is_the_same_random_variable(self):
        raw = {**fixture(), "expression": expr("all", ref("a"), ref("a")), "atoms": [atom("a", q(1, 2))]}
        result = model.decompose(raw)
        self.assertEqual(result["probability"], q(1, 2))
        self.assertEqual(result["subquestions"][0]["occurrences"], 2)
        self.assertEqual(result["assignments"], 2)

    def test_tautology_and_contradiction_need_neither_forecast_nor_model(self):
        raw = {**fixture(), "independence_ref": None, "atoms": [atom("a")]}
        for operator, expected in (("any", 1), ("all", 0)):
            with self.subTest(operator=operator):
                report = model.decompose({**raw, "expression": expr(operator, ref("a"), expr("not", ref("a")))})
                self.assertEqual(report["probability"], q(expected))
                self.assertEqual(report["probability_status"], "logical_constant")
                self.assertIsNone(report["first_true_witness" if not expected else "first_false_witness"])
                self.assertEqual(report["subquestions"][0]["pivotal_assignments"], 0)

    def test_unknown_dependence_withholds_probability_only(self):
        complete = model.decompose(fixture())
        report = model.decompose({**fixture(), "independence_ref": None})
        self.assertIsNone(report["probability"])
        self.assertEqual(report["satisfying"], complete["satisfying"])
        self.assertEqual(report["subquestions"], complete["subquestions"])
        self.assertEqual(report["missing_forecasts"], [])

    def test_missing_forecast_still_lists_which_question_lacks_input(self):
        raw = fixture()
        raw["atoms"][1] = atom("b")
        report = model.decompose(raw)
        self.assertIsNone(report["probability"])
        self.assertEqual(report["missing_forecasts"], ["b"])

    def test_unknown_and_unused_questions_are_both_reported(self):
        raw = fixture()
        raw["atoms"][1] = atom("unused", q(1, 3))
        with self.assertRaisesRegex(model.InputError, r"\['b'\].*\['unused'\]"):
            model.decompose(raw)

    def test_invalid_operator_and_unary_arity_are_rejected(self):
        for expression in (expr("xor", ref("a"), ref("b")), expr("not", ref("a"), ref("b")), expr("all")):
            with self.subTest(expression=expression), self.assertRaises(model.InputError):
                model.decompose({**fixture(), "expression": expression})

    def test_depth_limit_includes_leaf_and_bounds_recursive_evaluation(self):
        expression = ref("a")
        for _ in range(model.MAX_DEPTH):
            expression = expr("not", expression)
        with self.assertRaisesRegex(model.InputError, "terlalu besar"):
            model.decompose({**fixture(), "atoms": [atom("a")], "expression": expression})

    def test_absent_provenance_duplicate_refs_and_boolean_probability_fail(self):
        for change in (
            {"forecast_ref": None},
            {"forecast_ref": "p/b"},
            {"probability": q(True)},
            {"probability": q(1, 0)},
            {"id": "group"},
        ):
            raw = fixture()
            raw["atoms"][0].update(change)
            with self.subTest(change=change), self.assertRaises(model.InputError):
                model.decompose(raw)

    def test_cli_is_independent_of_atom_declaration_order(self):
        raw = fixture()
        path = Path(self.enterContext(TemporaryDirectory())) / "question.json"
        payloads = []
        for _ in range(2):
            path.write_text(json.dumps(raw), encoding="utf-8")
            with redirect_stdout(StringIO()) as output:
                self.assertEqual(model.main([str(path)]), 0)
            payloads.append(output.getvalue())
            raw["atoms"].reverse()
        self.assertEqual(payloads[0], payloads[1])

    def test_boundary_forecasts_can_zero_out_a_logically_possible_event(self):
        raw = fixture()
        raw["atoms"][0]["probability"] = q(0)
        report = model.decompose(raw)
        self.assertEqual(report["probability"], q(0))
        self.assertEqual(report["probability_status"], "conditional_on_independence")
        self.assertEqual(report["satisfying"], 3)
