from hashlib import sha256
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
import unittest

from ._contracts import canonical, decode, identity
from .institute_bench import run_bench


FIXTURES = Path(__file__).parent / "fixtures"


class InstituteBenchTests(unittest.TestCase):
    def test_fixture_provenance_on_generated_report_matches_archived_manifest(self):
        plan = decode((FIXTURES / "closed_research_plan.json").read_bytes())
        evidence, report = run_bench(plan, identity(plan), FIXTURES)
        self.assertEqual(report["status"], "fixture_pass")
        self.assertEqual((report["claims_matched"], report["claim_count"]), (6, 6))
        self.assertTrue(report["all_supported_numbers_rechecked"])
        self.assertTrue(report["all_reference_numbers_sourced"])
        self.assertTrue(all(case["rubric_bp"] == 10000 for case in report["cases"]))
        archived = FIXTURES / "closed_research_evidence"
        self.assertEqual(decode((archived / "run.json").read_bytes()), report)
        for name, payload in evidence.items():
            self.assertEqual((archived / name).read_bytes(), payload)
            self.assertEqual(report["artifacts"][name]["sha256"], sha256(payload).hexdigest())

    def test_gold_change_is_visible_as_failed_threshold_not_rounded_up(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary) / "copy"
            shutil.copytree(FIXTURES, root)
            plan = decode((root / "closed_research_plan.json").read_bytes())
            gold = root / plan["gold"]["path"]
            answers = decode(gold.read_bytes())
            answers["cases"][0]["claim_status"]["absent"] = "contradicted"
            raw = canonical(answers)
            gold.write_bytes(raw)
            plan["gold"]["sha256"] = sha256(raw).hexdigest()
            _, receipt = run_bench(plan, identity(plan), root)
            self.assertEqual(receipt["claim_match_bp"], 8333)
            self.assertEqual(receipt["status"], "fixture_hold")
