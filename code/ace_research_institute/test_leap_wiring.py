from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from ace_operational import leap_wiring

from ._contracts import canonical, identity
from .deep_report_writer import make_report
from .test_comparison_analyst import save
from .test_deep_report_writer import report_plan


class InstituteWiringTests(unittest.TestCase):
    def test_glossary_default_and_opt_in_missing_anchor_keep_existing_result(self):
        with TemporaryDirectory() as temporary:
            engine = SimpleNamespace(workspace=Path(temporary))
            gloss = {"schema": "fixture", "terms": ["one"], "summary": {"kind_counts": {"topic": 1}}}
            with patch.dict("os.environ", {}, clear=True), patch("tools.program_glossary.build_glossary", return_value=gloss):
                regular = leap_wiring.step_program_glossary(engine)
                self.assertEqual(regular, {"status": "ok", "groups": 1, "terms": 1, "schema": "fixture"})
            with patch.dict("os.environ", {"ACE_EVO0057_RESEARCH_INSTITUTE": "1"}, clear=True), patch(
                    "tools.program_glossary.build_glossary", return_value=gloss):
                gated = leap_wiring.step_program_glossary(engine)
                self.assertEqual(gated.pop("research_institute"), {"status": "held", "reason": "workspace_or_anchor_missing"})
                self.assertEqual(regular, gated)

    def test_read_only_quarter_recomputes_audit_and_holds_bad_bytes(self):
        with TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            root = workspace / "evo0057_research"
            root.mkdir()
            data = report_plan(root)
            result = make_report(data, identity(data), root)
            bundle = {"schema": "ace.institute.quarter-plan.v1", "quarter": "2025-Q1", "minimum_score_bp": 8500,
                      "sources": [{"id": "fixture", "completed_date": "2025-03-30", "source_ref": "fixture:quarter",
                                   "report": save(root, "report.json", canonical(result))}]}
            quarter = save(root, "quarter.json", canonical(bundle))
            environment = {"ACE_EVO0057_RESEARCH_INSTITUTE": "1", "ACE_EVO0057_QUARTER_SHA256": quarter["sha256"]}
            engine = SimpleNamespace(workspace=workspace)
            files = {path.name: path.read_bytes() for path in root.iterdir()}
            with patch.dict("os.environ", environment, clear=True):
                measured = leap_wiring.step_evo0057_institute_report(engine)
                self.assertEqual((measured["reviewed_count"], measured["rubric_passes"], measured["verified_numeric_total"]), (1, 1, 1))
                self.assertEqual({path.name: path.read_bytes() for path in root.iterdir()}, files)
                (root / "quarter.json").write_bytes(b"{}")
                self.assertEqual(leap_wiring.step_evo0057_institute_report(engine)["status"], "held")
