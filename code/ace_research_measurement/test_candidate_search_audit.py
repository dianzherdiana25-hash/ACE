"""ACE R8 candidate-search task audit: deterministic and falsification tests."""
from copy import deepcopy
import json
from pathlib import Path
import unittest
from .candidate_search_audit import audit, from_full_source, git_blob, MODES, BUDGETS, TASKS

class AuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot=json.loads(Path(__file__).with_name("candidate_search_snapshot.json").read_text())

    def test_standard_totals(self):
        x=audit(self.snapshot)["by_budget"]["standard"]
        self.assertEqual([x[m]["solved"] for m in MODES],[0,1,5,6])
        self.assertEqual([x[m]["total_work"] for m in MODES],[240,1632,440866,286707])

    def test_tight_budget_reversal(self):
        x=audit(self.snapshot)["by_budget"]["tight"]
        self.assertEqual([x[m]["solved"] for m in MODES],[0,1,0,0])

    def test_beam_enumerate_sign_is_not_significant(self):
        x=audit(self.snapshot)["pairwise"]["standard:beam_vs_enumerate"]
        self.assertEqual((x["wins"],x["losses"],x["ties"]),(1,0,7))
        self.assertEqual(x["one_sided_unadjusted_sign_p"],0.5)

    def test_actual_work_far_from_equal(self):
        x=audit(self.snapshot)["pairwise"]["standard:beam_vs_fixed-list"]
        self.assertGreater(x["actual_work_ratio"],100)

    def test_no_general_intelligence_claim(self):
        x=audit(self.snapshot)
        self.assertEqual(x["science_gate"],"NOT_CONFIRMED")
        self.assertFalse(x["independent_mechanism_lineage_verified"])

    def test_missing_mode_rejected(self):
        x=deepcopy(self.snapshot)
        del x["arms"]["standard"]["beam"]
        with self.assertRaisesRegex(ValueError,"missing or extra"):
            audit(x)

    def test_over_budget_rejected(self):
        x=deepcopy(self.snapshot)
        x["arms"]["tight"]["beam"]["total_work"][0]=301
        with self.assertRaisesRegex(ValueError,"bound violation"):
            audit(x)

    def test_invalid_correctness_rejected(self):
        x=deepcopy(self.snapshot)
        x["arms"]["standard"]["beam"]["correct"][0]=4
        with self.assertRaisesRegex(ValueError,"contradictory"):
            audit(x)

    def test_zero_error_mismatch_rejected(self):
        x=deepcopy(self.snapshot)
        x["arms"]["standard"]["beam"]["absolute_error"][-1]=0
        with self.assertRaisesRegex(ValueError,"contradictory"):
            audit(x)

    def test_provenance_mutation_rejected(self):
        x=deepcopy(self.snapshot)
        x["source"]["git_blob_sha1"]="0"*40
        with self.assertRaisesRegex(ValueError,"provenance"):
            audit(x)

    def test_boolean_work_rejected(self):
        x=deepcopy(self.snapshot)
        x["arms"]["standard"]["beam"]["total_work"][0]=True
        with self.assertRaisesRegex(ValueError,"noninteger"):
            audit(x)

    def test_full_source_mutation_rejected(self):
        with self.assertRaisesRegex(ValueError,"pinned source"):
            from_full_source(b"{}")

    def test_extract_fixture(self):
        # A synthetic imitation of the 64-run format; NOT source confirmation.
        d={"schema":1,"status":"PUBLIC_SYNTHETIC_DEVELOPMENT_ONLY",
           "scientific_decision":"NOT_ASSESSED","budgets":self.snapshot["budgets"],"results":[]}
        for budget in BUDGETS:
            for mode in MODES:
                x=self.snapshot["arms"][budget][mode]
                for i,task in enumerate(TASKS):
                    d["results"].append({"budget":budget,"mode":mode,"task":task,
                        "result":{"holdout":{"correct":x["correct"][i],"absolute_error":x["absolute_error"][i]},
                                  "total_work":x["total_work"][i]},
                        "search":{"candidates":x["candidates"][i]},
                        "timing":{"cpu_seconds":x["cpu_seconds_total"]/8}})
        raw=json.dumps(d).encode()
        extracted=from_full_source(raw,expected=git_blob(raw))
        self.assertEqual(extracted["arms"]["standard"]["beam"]["correct"],
                         self.snapshot["arms"]["standard"]["beam"]["correct"])

if __name__ == "__main__": unittest.main()
