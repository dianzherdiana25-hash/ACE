"""OMEGA-08 adversarial tests for the Population and Lineage Archive.

The test list follows the OMEGA-08 line of the execution programme:
duplicate candidate identity, lineage cycles, missing evidence,
mixed-evaluator collision, Pareto/tie handling, corrupted evidence,
replays — plus the archive's basic truthfulness guarantees.
"""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from ace_operational.population_archive import (
    CorruptRecordError,
    LineageCycleError,
    MissingCandidateError,
    MissingParentError,
    MixedEvaluatorError,
    PopulationArchive,
)

BUDGET = {"evaluation_passes": 1, "max_tokens": 512}


def make_archive(test: unittest.TestCase) -> PopulationArchive:
    temp = tempfile.TemporaryDirectory(prefix="ace-pop-")
    test.addCleanup(temp.cleanup)
    return PopulationArchive(Path(temp.name) / "archive")


class RegistrationTests(unittest.TestCase):
    def setUp(self):
        self.archive = make_archive(self)

    def test_duplicate_candidate_identity_is_idempotent(self):
        first = self.archive.register_candidate(
            kind="patch", descriptor="fix A", artifact_bytes=b"code-v1")
        second = self.archive.register_candidate(
            kind="patch", descriptor="fix A", artifact_bytes=b"code-v1")
        self.assertEqual(first, second)
        self.assertEqual(self.archive.candidate_ids(), [first])
        self.assertEqual(self.archive.verify()["candidates"], 1)

    def test_same_descriptor_different_artifact_is_a_different_candidate(self):
        a = self.archive.register_candidate(
            kind="patch", descriptor="fix A", artifact_bytes=b"code-v1")
        b = self.archive.register_candidate(
            kind="patch", descriptor="fix A", artifact_bytes=b"code-v2")
        self.assertNotEqual(a, b)

    def test_missing_parent_is_rejected(self):
        with self.assertRaises(MissingParentError):
            self.archive.register_candidate(
                kind="patch", descriptor="orphan", artifact_bytes=b"x",
                parents=["cand_doesnotexist00000"])

    def test_evaluation_of_unknown_candidate_is_rejected(self):
        with self.assertRaises(MissingCandidateError):
            self.archive.record_evaluation(
                candidate_id="cand_doesnotexist00000", evaluator_id="ev",
                protocol="p", budget=BUDGET, metrics={"score": 1.0},
                outcome="pass")

    def test_duplicate_evaluation_is_idempotent(self):
        cand = self.archive.register_candidate(
            kind="patch", descriptor="d", artifact_bytes=b"v1")
        one = self.archive.record_evaluation(
            candidate_id=cand, evaluator_id="ev", protocol="p", budget=BUDGET,
            metrics={"score": 3.0}, outcome="pass")
        two = self.archive.record_evaluation(
            candidate_id=cand, evaluator_id="ev", protocol="p", budget=BUDGET,
            metrics={"score": 3.0}, outcome="pass")
        self.assertEqual(one, two)
        self.assertEqual(len(self.archive.evaluation_ids()), 1)


class LineageTests(unittest.TestCase):
    def setUp(self):
        self.archive = make_archive(self)

    def test_lineage_walks_all_ancestors(self):
        root = self.archive.register_candidate(
            kind="patch", descriptor="root", artifact_bytes=b"r")
        mid = self.archive.register_candidate(
            kind="patch", descriptor="mid", artifact_bytes=b"m", parents=[root])
        leaf = self.archive.register_candidate(
            kind="patch", descriptor="leaf", artifact_bytes=b"l", parents=[mid])
        self.assertEqual(set(self.archive.lineage(leaf)), {root, mid})

    def test_cycle_detection_in_traversal(self):
        # A true on-disk cycle cannot satisfy content addressing (it would
        # need a SHA-256 fixed point), so the traversal guard is exercised
        # directly against a cyclic in-memory graph.
        graph = {
            "cand_a": {"id": "cand_a", "parents": ["cand_b"]},
            "cand_b": {"id": "cand_b", "parents": ["cand_a"]},
        }
        with patch.object(self.archive, "load_candidate",
                          side_effect=lambda cid: graph[cid]):
            with self.assertRaises(LineageCycleError):
                self.archive.lineage("cand_a")

    def test_forged_cycle_on_disk_is_flagged_corrupt(self):
        # Hand-forged files claiming a cycle cannot have content-derived
        # IDs, so the archive flags them corrupt instead of trusting them.
        for name, parent in (("cand_forged_a", "cand_forged_b"),
                             ("cand_forged_b", "cand_forged_a")):
            record = {"id": name, "kind": "patch", "descriptor": "forged",
                      "artifact_digest": "0" * 64, "artifact_size_bytes": 1,
                      "parents": [parent], "metadata": {}}
            (self.archive.candidates_dir / f"{name}.json").write_text(
                json.dumps(record), encoding="utf-8")
        report = self.archive.verify()
        self.assertIn("cand_forged_a", report["corrupt"])
        self.assertIn("cand_forged_b", report["corrupt"])


class SelectionTests(unittest.TestCase):
    def setUp(self):
        self.archive = make_archive(self)
        self.a = self.archive.register_candidate(
            kind="patch", descriptor="A", artifact_bytes=b"a")
        self.b = self.archive.register_candidate(
            kind="patch", descriptor="B", artifact_bytes=b"b")
        self.c = self.archive.register_candidate(
            kind="patch", descriptor="C", artifact_bytes=b"c")

    def evaluate(self, cand, metrics, outcome="pass", evaluator="ev-1",
                 budget=None):
        return self.archive.record_evaluation(
            candidate_id=cand, evaluator_id=evaluator, protocol="proto-v1",
            budget=budget or BUDGET, metrics=metrics, outcome=outcome)

    def test_pareto_front_and_ties(self):
        self.evaluate(self.a, {"score": 6.0, "cost": 10.0})
        self.evaluate(self.b, {"score": 6.0, "cost": 10.0})  # exact tie with A
        self.evaluate(self.c, {"score": 4.0, "cost": 10.0})   # dominated
        result = self.archive.select(
            evaluator_id="ev-1", protocol="proto-v1", budget=BUDGET,
            objectives=[("score", "max"), ("cost", "min")])
        self.assertEqual(result["front"], sorted([self.a, self.b]))
        self.assertEqual(result["dominated"], [self.c])
        self.assertEqual(result["excluded"], {})

    def test_mixed_evaluator_collision_is_an_error(self):
        one = self.evaluate(self.a, {"score": 1.0}, evaluator="ev-1")
        two = self.evaluate(self.a, {"score": 2.0}, evaluator="ev-2")
        with self.assertRaises(MixedEvaluatorError):
            self.archive.assert_comparable([one, two])

    def test_different_budget_is_a_different_group(self):
        self.evaluate(self.a, {"score": 5.0}, budget={"evaluation_passes": 1})
        result = self.archive.select(
            evaluator_id="ev-1", protocol="proto-v1",
            budget={"evaluation_passes": 2},
            objectives=[("score", "max")])
        self.assertEqual(result["front"], [])
        self.assertIn(self.a, result["excluded"])

    def test_missing_metric_excludes_with_reason(self):
        self.evaluate(self.a, {"score": 5.0})
        result = self.archive.select(
            evaluator_id="ev-1", protocol="proto-v1", budget=BUDGET,
            objectives=[("score", "max"), ("cost", "min")])
        self.assertIn("missing metrics: cost", result["excluded"][self.a])

    def test_negative_results_are_archived_and_listed(self):
        self.evaluate(self.c, {"score": 0.0}, outcome="fail")
        negatives = self.archive.negatives()
        self.assertEqual(len(negatives), 1)
        self.assertEqual(negatives[0]["candidate_id"], self.c)


class IntegrityTests(unittest.TestCase):
    def setUp(self):
        self.archive = make_archive(self)
        self.cand = self.archive.register_candidate(
            kind="patch", descriptor="victim", artifact_bytes=b"original")
        self.ev = self.archive.record_evaluation(
            candidate_id=self.cand, evaluator_id="ev-1", protocol="proto-v1",
            budget=BUDGET, metrics={"score": 1.0}, outcome="pass",
            evidence_bytes=b"raw evidence")

    def test_corrupted_evaluation_is_flagged_and_excluded(self):
        path = self.archive.evaluations_dir / f"{self.ev}.json"
        record = json.loads(path.read_text(encoding="utf-8"))
        record["metrics"] = {"score": 999.0}  # forge a better score
        path.write_text(json.dumps(record), encoding="utf-8")
        report = self.archive.verify()
        self.assertIn(self.ev, report["corrupt"])
        result = self.archive.select(
            evaluator_id="ev-1", protocol="proto-v1", budget=BUDGET,
            objectives=[("score", "max")])
        self.assertEqual(result["front"], [])
        self.assertIn(self.cand, result["excluded"])

    def test_corrupted_candidate_is_flagged(self):
        path = self.archive.candidates_dir / f"{self.cand}.json"
        record = json.loads(path.read_text(encoding="utf-8"))
        record["descriptor"] = "tampered"
        path.write_text(json.dumps(record), encoding="utf-8")
        self.assertIn(self.cand, self.archive.verify()["corrupt"])

    def test_broken_ledger_chain_is_detected(self):
        lines = self.archive.ledger_path.read_text(encoding="utf-8").splitlines()
        entry = json.loads(lines[0])
        entry["event"]["record"]["descriptor"] = "tampered"
        lines[0] = json.dumps(entry)
        self.archive.ledger_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        self.assertFalse(self.archive.verify()["ledger_chain_ok"])

    def test_replay_reproduces_state_hash(self):
        self.archive.register_candidate(
            kind="patch", descriptor="child", artifact_bytes=b"v2",
            parents=[self.cand])
        report = self.archive.verify()
        self.assertTrue(report["ledger_chain_ok"])
        self.assertTrue(report["replay_matches"])
        self.assertEqual(report["replay_hash"], report["state_hash"])


if __name__ == "__main__":
    unittest.main()
