"""Mapped E1.4r/s component-composition controls; not scientific scoring."""
import tempfile
import unittest
from pathlib import Path

from .e14_integrated_graph import DurableGraphBudget, execute_protocol, graph_oracle
from .e14_integrated_policy import mapped_only_policy
from .e14_shared_budget import BudgetContractError
from .e14r_worker import mappings

WORD = (1,2,1,1,2,2,1)
ARTIFACT = {"kind": "edge-relative-word-v1", "word": list(WORD),
            "source_sha256": "0"*64}

class MappedPolicyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.sqlite = Path(self.tmp.name) / "arms.sqlite"

    def run_case(self, truth, mode="active"):
        journal = DurableGraphBudget(self.sqlite, f"{truth}:{mode}")
        return execute_protocol(journal, mapped_only_policy(ARTIFACT, mode),
                                lambda graph:graph_oracle(graph,truth))

    def test_true_mapping_accepted_with_qualification(self):
        for truth in mappings(WORD):
            with self.subTest(truth=truth):
                outcome = self.run_case(truth)
                self.assertEqual(outcome["decision"], "accept")
                self.assertEqual(outcome["actions"][-1]["word"], list(truth))
                self.assertLessEqual(outcome["journal"]["purchased"], 3)
                self.assertEqual(outcome["journal"]["receipts"][0]["reused_in"],
                                 ["repair", "inheritance"])

    def test_shorter_alias_must_not_be_accepted(self):
        outcome = self.run_case(WORD[:-1])
        self.assertEqual(outcome["decision"], "abstain")
        self.assertEqual(outcome["journal"]["purchased"], 2)

    def test_unrecognized_target_abstains(self):
        outcome = self.run_case((1,)*10)
        self.assertEqual(outcome["decision"], "abstain")
        self.assertLessEqual(outcome["journal"]["purchased"], 3)

    def test_one_positive_receipt_control_is_not_robust(self):
        outcome = self.run_case(WORD[:-1], mode="receipt")
        self.assertEqual(outcome["decision"], "accept")
        self.assertNotEqual(outcome["actions"][-1]["word"], list(WORD[:-1]))
        # Deliberately demonstrates why standalone positive receipt is unsafe.

    def test_bad_artifact_and_mode_rejected(self):
        with self.assertRaises(BudgetContractError):
            mapped_only_policy(ARTIFACT, "untrusted")
        with self.assertRaises(ValueError):
            mapped_only_policy({**ARTIFACT,"source_sha256":"bad"})

    def test_equal_cap_for_active_and_receipt_baseline(self):
        active = self.run_case(WORD,mode="active")
        receipt = self.run_case(WORD,mode="receipt")
        self.assertLessEqual(active["journal"]["purchased"],4)
        self.assertLessEqual(receipt["journal"]["purchased"],4)
        self.assertEqual(active["journal"]["shared_cap"],receipt["journal"]["shared_cap"])

if __name__ == "__main__":
    unittest.main()
