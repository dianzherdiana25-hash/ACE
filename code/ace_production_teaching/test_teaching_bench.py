from hashlib import sha256
from importlib.util import find_spec
from pathlib import Path
import unittest

from ._contracts import decode, identity
from .teaching_bench import run_bench


FIXTURES = Path(__file__).parent / "fixtures"
HAS_READERS = bool(find_spec("pptx") and find_spec("pypdf"))


@unittest.skipUnless(HAS_READERS, "Backend artefak dan verifier lokal diperlukan")
class TeachingBenchTests(unittest.TestCase):
    def test_real_artifacts_and_simulation_receipts_are_bound_to_fixture(self):
        plan = decode((FIXTURES / "teaching_plan.json").read_bytes())
        outputs, result = run_bench(plan, identity(plan), FIXTURES)
        self.assertEqual(result["status"], "fixture_pass")
        self.assertEqual(result["details"], {"artifact_count": 5, "artifact_passed": 5, "detected": 1,
                         "learner_items_per_arm": 4, "learner_post_passed": 4, "learner_pre_passed": 2, "misconceptions_in_key": 1})
        self.assertEqual(result["metrics"]["simulation_gain_bp"], 5000)
        archive = FIXTURES / "teaching_bench_evidence"
        archived = decode((archive / "run.json").read_bytes())
        self.assertEqual(archived["plan_sha256"], identity(plan))
        for name, ref in archived["artifacts"].items():
            self.assertEqual(sha256((archive / name).read_bytes()).hexdigest(), ref["sha256"])
            self.assertEqual(sha256(outputs[name]).hexdigest(), result["artifacts"][name]["sha256"])

    def test_unrelated_intervention_cannot_raise_fixture_scores(self):
        plan = decode((FIXTURES / "teaching_plan.json").read_bytes())
        plan["simulation"]["initial_knowledge"].append({"topic": "unrelated", "level": 1})
        plan["simulation"]["interventions"][0]["topic"] = "unrelated"
        _, result = run_bench(plan, identity(plan), FIXTURES)
        self.assertEqual(result["metrics"]["simulation_gain_bp"], 0)
        self.assertEqual(result["status"], "fixture_hold")
