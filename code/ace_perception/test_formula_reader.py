"""Verifier tata bahasa, lokasi galat, dan pembacaan formula raster."""
import unittest

from ace_perception import _raster, formula_reader as model
from ace_perception.test_document_extractor import FULL, image
from ace_perception.test_ocr_engine import font


class FormulaTests(unittest.TestCase):
    def test_right_associative_powers_and_unary_precedence(self):
        report = model.parse_formula("−2^3^4 + B × 5.20")
        self.assertEqual(report["operator"], "+")
        left = report["left"]
        self.assertEqual(left["operator"], "-")
        self.assertEqual(left["argument"]["operator"], "^")
        self.assertEqual(left["argument"]["right"]["operator"], "^")
        self.assertEqual(left["range"], [0, 6])
        self.assertEqual(report["right"]["operator"], "*")
        self.assertEqual(report["right"]["right"]["literal"], "5.20")

    def test_group_operator_and_single_equation_instead_of_evaluation(self):
        modelled = model.parse_formula("(A+1)=A÷0")
        self.assertEqual(modelled["type"], "equation")
        self.assertEqual(modelled["left"]["type"], "group")
        self.assertEqual(modelled["right"]["operator"], "/")
        self.assertEqual(modelled["right"]["right"]["literal"], "0")

    def test_bad_inputs_are_located_and_never_partially_accepted(self):
        for formula, offset in (("1+2?", 3), ("A=B=C", 3), ("2 1", 2), ("(x+1", 4), ("2 +", 3), ("", 0)):
            with self.subTest(formula=formula):
                with self.assertRaises(model.FormulaError) as case:
                    model.parse_formula(formula)
                self.assertEqual(case.exception.position, offset)
        with self.assertRaisesRegex(model.FormulaError, "bersarang"):
            model.parse_formula("("*50+"1"+")"*50)

    def test_standalone_raster_formula_and_newline_hold(self):
        for lines, expected in ((["2-1"], "read"), (["2-1", "2-1"], "unsupported_formula")):
            scan = image(*lines)
            raster = _raster.decode(scan)
            layout = model._canonical({"schema": "ace.perception-formula-layout.v1", "word_gap": 4, "light_ink": False,
                                       "zones": [{"id": "a", "box": [0, 0, raster.width, raster.height]}]})
            report = model.read_formulas(scan, font(FULL), layout)
            row, = report["zones"]
            self.assertEqual(row["status"], expected)
            if expected == "read":
                self.assertEqual(row["ast"]["operator"], "-")
                self.assertEqual([glyph["character"] for glyph in row["ocr"]["glyphs"]], ["2", "-", "1"])
            else:
                self.assertIsNone(row["ast"])
                self.assertEqual(row["issue"]["character_offset"], 3)
