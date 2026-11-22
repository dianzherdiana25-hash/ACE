from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._contracts import identity
from .number_provenance import scan_prose, verify_numbers
from .test_comparison_analyst import save
from .test_deep_report_writer import report_plan
from .test_literature_reviewer import DIMS


class ProvenanceTests(unittest.TestCase):
    def test_numeric_tokens_link_to_exact_position_source_value_and_context(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            raw = b"`figure_13` Cahaya 31% dan 10 poin.\nTidak dihitung `n=20`.\n"
            offsets = dict(scan_prose(raw.decode()))
            self.assertEqual([row[0] for row in offsets.values()], ["31%", "10"])
            (line, column), *_ = offsets
            plan = {"schema": "ace.institute.number-proof-plan.v1", "draft": save(root, "report.md", raw),
                    "source_plan": report_plan(root)["checks"]["source_plan"],
                    "citations": [{"line": line, "column": column, "source_id": "paper", "measurement_id": "value",
                                   "dimensions": DIMS, "document_unit": "pct", "tolerance": "0"}]}
            result = verify_numbers(plan, identity(plan), root)
            self.assertEqual(result["coverage_bp"], 5000)
            self.assertEqual(result["numeric_tokens"][0]["source"]["line"], 6)
            self.assertEqual(result["numeric_tokens"][1]["status"], "missing_citation")
            plan["citations"][0]["document_unit"] = "ratio"
            result = verify_numbers(plan, identity(plan), root)
            self.assertEqual(result["numeric_tokens"][0]["status"], "document_unit_conflict")
