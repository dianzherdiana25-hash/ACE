import unittest

from ._contracts import ProductionError, identity
from .hint_engine import next_hint


class HintsTests(unittest.TestCase):
    def test_unsafe_middle_hint_skips_without_showing_answer(self):
        plan = {"schema": "ace.teaching.hint-plan.v1", "exercise": "sum", "provided_ids": ["first"],
                "answer_forms": ["12"], "chain": [
                    {"id": "first", "level": 1, "prompt": "Periksa kedua angka.", "source_ref": "fixture:first"},
                    {"id": "unsafe", "level": 2, "prompt": "Nilainya 12.", "source_ref": "fixture:unsafe"},
                    {"id": "third", "level": 3, "prompt": "Kelompokkan menjadi puluhan.", "source_ref": "fixture:third"}]}
        proof = next_hint(plan, identity(plan))
        self.assertEqual(proof["hint"]["id"], "third")
        self.assertEqual(proof["held"], [{"id": "unsafe", "reason": "reserved_answer_overlap"}])
        self.assertNotIn("Nilainya 12", str(proof))
        plan["provided_ids"] = ["unsafe"]
        with self.assertRaisesRegex(ProductionError, "rantai aman"):
            next_hint(plan, identity(plan))
