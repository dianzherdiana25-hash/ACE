from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._contracts import identity
from .anomaly_questioner import questions
from .test_data_analyst import column, table


class QuestionsTests(unittest.TestCase):
    def test_question_retains_observed_line_and_opens_falsifier(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            src, spec = table(root, b"day,value\n1,1\n2,2\n3,3\n4,40\n",
                              [column("day", "integer"), column("value", "integer")])
            plan = {"schema": "ace.institute.anomaly-question-plan.v1", "source_ref": "fixture:input", "maximum": 5,
                    "units": "lux", "patterns": {"schema": "ace.institute.pattern-plan.v1", "data": src, "format": spec,
                    "value": "value", "order": "day", "group": None, "minimum_run": 3, "mad_multiplier": "4"}}
            report = questions(plan, identity(plan), root)
            item = report["items"][0]
            self.assertEqual(item["data"], src | {"line": 5})
            self.assertEqual(item["comparison"]["observed"], "40")
            self.assertTrue(item["question"].endswith("?"))
            self.assertIn("Pengukuran ulang", item["falsifier"])
