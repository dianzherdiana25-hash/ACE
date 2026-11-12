"""OMEGA-06 adversarial tests for the Experiment Protocol and Evidence Kernel.

The test list follows the OMEGA-06 line of the execution programme:
leakage canary, forged success flag, fixture mutation, changed
evaluator, candidate editing its own test, train/test contamination,
partial result replay — plus preregistration/custody discipline.
"""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from ace_operational.experiment_kernel import (
    ContaminationError,
    CustodyError,
    ExperimentKernel,
    ForgedVerdictError,
    KernelError,
    NotPreregisteredError,
)

CAND_KEY = b"candidate-custodian-test-key"
EVAL_KEY = b"evaluator-custodian-test-key"
BUDGET = {"evaluation_passes": 1}
PROTOCOL = {"name": "fixture-eval", "version": 1,
            "pass_rule": {"metric": "evaluator_pass", "gte": 6}}

EVALUATOR = b"held-out evaluator source v1"
FIXTURE = b"fixture with two genuine defects"
GOOD = b"candidate artifact: correct fix"
BAD = b"candidate artifact: partial fix"
BASELINE = b"candidate artifact: deterministic baseline"


def make_kernel(test: unittest.TestCase) -> ExperimentKernel:
    temp = tempfile.TemporaryDirectory(prefix="ace-kernel-")
    test.addCleanup(temp.cleanup)
    return ExperimentKernel(Path(temp.name) / "lab",
                            candidate_key=CAND_KEY, evaluator_key=EVAL_KEY)


class KernelFixture(unittest.TestCase):
    def setUp(self):
        self.kernel = make_kernel(self)
        self.kernel.custody_evaluator("ev-1", EVALUATOR, FIXTURE)
        for cid, artifact in (("cand-good", GOOD), ("cand-bad", BAD),
                              ("cand-base", BASELINE)):
            self.kernel.custody_candidate(cid, artifact)

    def prereg(self, **overrides):
        args = dict(experiment_id="exp-1", hypothesis="feedback patch beats one-shot",
                    protocol=PROTOCOL, evaluator_id="ev-1", budget=BUDGET,
                    candidate_ids=["cand-good", "cand-bad", "cand-base"],
                    baseline_candidate_id="cand-base",
                    negative_control_id="cand-bad", canary_tokens=["CANARY-7f3a"])
        args.update(overrides)
        return self.kernel.preregister(**args)


class PreregistrationTests(KernelFixture):
    def test_result_before_preregistration_is_rejected(self):
        with self.assertRaises(NotPreregisteredError):
            self.kernel.record_result(
                experiment_id="exp-1", candidate_id="cand-good",
                candidate_artifact=GOOD, metrics={"evaluator_pass": 6.0},
                claimed_verdict="pass", raw_telemetry={})

    def test_preregistration_is_immutable(self):
        self.prereg()
        with self.assertRaises(KernelError):
            self.prereg(hypothesis="a different story")

    def test_preregistration_needs_baseline_and_custody(self):
        with self.assertRaises(KernelError):
            self.prereg(candidate_ids=["cand-good"],
                        baseline_candidate_id="cand-base")
        fresh = make_kernel(self)
        with self.assertRaises(CustodyError):
            fresh.preregister(
                experiment_id="x", hypothesis="h", protocol=PROTOCOL,
                evaluator_id="ev-1", budget=BUDGET, candidate_ids=["cand-good"],
                baseline_candidate_id="cand-good")

    def test_unregistered_candidate_cannot_submit(self):
        self.prereg()
        self.kernel.custody_candidate("cand-late", b"late artifact")
        with self.assertRaises(KernelError):
            self.kernel.record_result(
                experiment_id="exp-1", candidate_id="cand-late",
                candidate_artifact=b"late artifact",
                metrics={"evaluator_pass": 6.0}, claimed_verdict="pass",
                raw_telemetry={})


class VerdictTests(KernelFixture):
    def setUp(self):
        super().setUp()
        self.prereg()

    def submit(self, cid="cand-good", artifact=GOOD, metrics=None,
               verdict="pass", telemetry=None, reason=None):
        return self.kernel.record_result(
            experiment_id="exp-1", candidate_id=cid, candidate_artifact=artifact,
            metrics=metrics if metrics is not None else {"evaluator_pass": 6.0},
            claimed_verdict=verdict, raw_telemetry=telemetry or {},
            abstain_reason=reason)

    def test_happy_path_pass_and_fail(self):
        self.submit()
        self.submit(cid="cand-bad", artifact=BAD,
                    metrics={"evaluator_pass": 4.0}, verdict="fail")
        audit = self.kernel.audit("exp-1")
        self.assertEqual(audit["status"], "CLEAN")
        self.assertEqual(audit["results_verified"], 2)

    def test_forged_success_flag_is_rejected(self):
        with self.assertRaises(ForgedVerdictError):
            self.submit(metrics={"evaluator_pass": 2.0}, verdict="pass")

    def test_forged_failure_flag_is_rejected(self):
        with self.assertRaises(ForgedVerdictError):
            self.submit(metrics={"evaluator_pass": 6.0}, verdict="fail")

    def test_abstain_needs_reason_when_metrics_are_decisive(self):
        with self.assertRaises(ForgedVerdictError):
            self.submit(verdict="abstain")
        entry = self.submit(verdict="abstain", reason="evaluator host lost power")
        self.assertEqual(entry["result"]["verdict"], "abstain")

    def test_missing_metric_derives_abstain(self):
        entry = self.submit(metrics={"other": 1.0}, verdict="abstain")
        self.assertEqual(entry["result"]["verdict"], "abstain")


class ContaminationTests(KernelFixture):
    def setUp(self):
        super().setUp()
        self.prereg()

    def test_leakage_canary_in_artifact(self):
        poisoned = GOOD + b"  # CANARY-7f3a"
        # custody would never match a poisoned artifact, so register the
        # poisoned bytes as their own candidate to isolate the canary path
        kernel = make_kernel(self)
        kernel.custody_evaluator("ev-1", EVALUATOR, FIXTURE)
        kernel.custody_candidate("cand-poison", poisoned)
        kernel.custody_candidate("cand-base", BASELINE)
        kernel.preregister(
            experiment_id="exp-c", hypothesis="h", protocol=PROTOCOL,
            evaluator_id="ev-1", budget=BUDGET,
            candidate_ids=["cand-poison", "cand-base"],
            baseline_candidate_id="cand-base", canary_tokens=["CANARY-7f3a"])
        with self.assertRaises(ContaminationError):
            kernel.record_result(
                experiment_id="exp-c", candidate_id="cand-poison",
                candidate_artifact=poisoned, metrics={"evaluator_pass": 6.0},
                claimed_verdict="pass", raw_telemetry={})

    def test_leakage_canary_in_telemetry(self):
        with self.assertRaises(ContaminationError):
            self.kernel.record_result(
                experiment_id="exp-1", candidate_id="cand-good",
                candidate_artifact=GOOD, metrics={"evaluator_pass": 6.0},
                claimed_verdict="pass",
                raw_telemetry={"note": "saw CANARY-7f3a in the held-out set"})

    def test_candidate_that_is_the_evaluator_is_rejected(self):
        kernel = make_kernel(self)
        kernel.custody_evaluator("ev-1", EVALUATOR, FIXTURE)
        kernel.custody_candidate("cand-cheat", EVALUATOR)  # artifact == evaluator
        kernel.custody_candidate("cand-base", BASELINE)
        kernel.preregister(
            experiment_id="exp-t", hypothesis="h", protocol=PROTOCOL,
            evaluator_id="ev-1", budget=BUDGET,
            candidate_ids=["cand-cheat", "cand-base"],
            baseline_candidate_id="cand-base")
        with self.assertRaises(ContaminationError):
            kernel.record_result(
                experiment_id="exp-t", candidate_id="cand-cheat",
                candidate_artifact=EVALUATOR, metrics={"evaluator_pass": 6.0},
                claimed_verdict="pass", raw_telemetry={})

    def test_candidate_that_is_the_fixture_is_contamination(self):
        kernel = make_kernel(self)
        kernel.custody_evaluator("ev-1", EVALUATOR, FIXTURE)
        kernel.custody_candidate("cand-copy", FIXTURE)  # artifact == fixture
        kernel.custody_candidate("cand-base", BASELINE)
        kernel.preregister(
            experiment_id="exp-f", hypothesis="h", protocol=PROTOCOL,
            evaluator_id="ev-1", budget=BUDGET,
            candidate_ids=["cand-copy", "cand-base"],
            baseline_candidate_id="cand-base")
        with self.assertRaises(ContaminationError):
            kernel.record_result(
                experiment_id="exp-f", candidate_id="cand-copy",
                candidate_artifact=FIXTURE, metrics={"evaluator_pass": 6.0},
                claimed_verdict="pass", raw_telemetry={})

    def test_artifact_swap_after_custody_is_rejected(self):
        with self.assertRaises(CustodyError):
            self.kernel.record_result(
                experiment_id="exp-1", candidate_id="cand-good",
                candidate_artifact=b"quietly improved artifact",
                metrics={"evaluator_pass": 6.0}, claimed_verdict="pass",
                raw_telemetry={})


class AuditTests(KernelFixture):
    def setUp(self):
        super().setUp()
        self.prereg()
        self.kernel.record_result(
            experiment_id="exp-1", candidate_id="cand-good",
            candidate_artifact=GOOD, metrics={"evaluator_pass": 6.0},
            claimed_verdict="pass", raw_telemetry={"seconds": 12.5})

    def test_changed_evaluator_is_detected_at_audit(self):
        self.kernel.custody_evaluator("ev-1", b"held-out evaluator source v2 CHANGED",
                                      FIXTURE)
        audit = self.kernel.audit("exp-1")
        self.assertEqual(audit["status"], "VIOLATIONS")
        self.assertTrue(any("evaluator changed" in p for p in audit["problems"]))

    def test_fixture_mutation_is_detected_at_audit(self):
        self.kernel.custody_evaluator("ev-1", EVALUATOR, b"fixture quietly fixed")
        audit = self.kernel.audit("exp-1")
        self.assertEqual(audit["status"], "VIOLATIONS")
        self.assertTrue(any("fixture mutated" in p for p in audit["problems"]))

    def test_wrong_custody_key_breaks_signatures(self):
        impostor = ExperimentKernel(self.kernel.root, candidate_key=b"wrong",
                                    evaluator_key=b"wrong")
        audit = impostor.audit("exp-1")
        self.assertEqual(audit["status"], "VIOLATIONS")
        self.assertTrue(any("signature invalid" in p for p in audit["problems"]))

    def test_partial_ledger_replay_is_incomplete_not_clean(self):
        self.kernel.record_result(
            experiment_id="exp-1", candidate_id="cand-base",
            candidate_artifact=BASELINE, metrics={"evaluator_pass": 6.0},
            claimed_verdict="pass", raw_telemetry={})
        lines = self.kernel.ledger_path.read_text(encoding="utf-8").splitlines()
        entry = json.loads(lines[1])
        entry["result"]["metrics"] = {"evaluator_pass": 0.0}  # tamper entry 2
        lines[1] = json.dumps(entry)
        self.kernel.ledger_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        audit = self.kernel.audit("exp-1")
        self.assertEqual(audit["status"], "INCOMPLETE")
        self.assertEqual(audit["chain_break_at"], 2)
        self.assertEqual(audit["ledger_entries_verified"], 1)

    def test_negative_control_passing_is_a_violation(self):
        self.kernel.record_result(
            experiment_id="exp-1", candidate_id="cand-bad",
            candidate_artifact=BAD, metrics={"evaluator_pass": 6.0},
            claimed_verdict="pass", raw_telemetry={})
        audit = self.kernel.audit("exp-1")
        self.assertEqual(audit["status"], "VIOLATIONS")
        self.assertTrue(any("negative control" in p for p in audit["problems"]))


if __name__ == "__main__":
    unittest.main()
