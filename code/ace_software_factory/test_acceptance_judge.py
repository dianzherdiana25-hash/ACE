"""Verifier keputusan per-kriteria, bukti absen, dan anchor artefak."""
import unittest

from ace_software_factory import acceptance_judge, spec_writer
from ace_software_factory._contracts import ContractError, identity
from ace_software_factory.test_spec_writer import brief, utterance


class JudgeTests(unittest.TestCase):
    def setUp(self):
        source = brief()
        source["utterances"].append(utterance(5, "uji show: Laporkan bentuk benar."))
        self.spec = spec_writer.write(source)
        self.contract = {"schema": "ace.factory-acceptance-contract.v1", "spec_sha256": identity(self.spec),
                         "source_ref": "fixture/test-plan",
                         "rules": [{"id": "count", "criterion_ref": "fixture/brief/1", "operator": "at_least",
                                    "expected": 2, "source_ref": "fixture/test-plan/1"},
                                   {"id": "shape", "criterion_ref": "fixture/brief/5", "operator": "equals",
                                    "expected": {"ready": True}, "source_ref": "fixture/test-plan/2"}]}
        self.observations = {"schema": "ace.factory-observations.v1", "product_id": self.spec["product_id"],
                             "artifact_sha256": "a" * 64, "records": [
                                 {"id": "count", "value": 3, "source_ref": "fixture/observed/1"},
                                 {"id": "shape", "value": {"ready": True}, "source_ref": "fixture/observed/2"}]}

    def run_judge(self, artifact="a" * 64):
        self.observations["contract_sha256"] = identity(self.contract)
        return acceptance_judge.evaluate(self.spec, self.contract, self.observations, identity(self.contract),
                                         identity(self.observations), artifact)

    def test_requirements_and_source_refs_visible_in_passing_report(self):
        report = self.run_judge()
        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["counts"]["passed"], 2)
        self.assertEqual(report["results"][0]["requirement"], "show")
        self.assertEqual(report["results"][1]["observed_ref"], "fixture/observed/2")

    def test_missing_observations_different_from_nonmatching_and_unknown(self):
        self.observations["records"].pop()
        self.observations["records"][0]["value"] = True
        report = self.run_judge()
        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["counts"]["failed"], 1)
        self.assertEqual(report["counts"]["missing_observation"], 1)
        self.observations["records"][0].update(value=2)
        self.assertEqual(self.run_judge()["status"], "incomplete")

    def test_refuses_observations_for_another_artifact(self):
        with self.assertRaisesRegex(ContractError, "artefak"):
            self.run_judge(artifact="b" * 64)
