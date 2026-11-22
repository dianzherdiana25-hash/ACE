"""Verifier registry membedakan fixture, atestasi absen, dan bukti sah."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_web_operator import skill_registry,skill_verifier
from ace_web_operator._contracts import ContractError,identity
from ace_web_operator.test_skill_verifier import evidence


class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.root=Path(self.enterContext(TemporaryDirectory()))
        self.state={"schema":"ace.web.skill-registry.v1","revision":0,"source_ref":"fixture/empty","entries":[]}

    def run_fixture(self,scope,attest=False):
        package,suite,answers=evidence(self.root,scope=scope)
        proof=skill_verifier.evaluate(package,identity(package),suite,answers,identity(answers))
        batch={"schema":"ace.web.skill-verification-batch.v1","entries":[
            {"source_ref":"fixture/batch","package":package,"package_sha256":identity(package),
             "suite":suite,"answers":answers,"answer_sha256":identity(answers)}]}
        policy={"schema":"ace.web.skill-registry-policy.v1","source_ref":"fixture/authorized-registry",
                "previous_sha256":identity(self.state),"batch_sha256":identity(batch),
                "attested_receipts":[{"skill":"two_values","verification_sha256":identity(proof),
                                      "package_sha256":identity(package),"authority_ref":"fixture/attestor"}] if attest else []}
        return skill_registry.revise(self.state,policy,identity(policy),batch)

    def test_fixture_cannot_enter_acquired_even_if_policy_mentions_it(self):
        created,receipt=self.run_fixture("fixture",True)
        self.assertEqual(created["entries"][0]["status"],"FIXTURE_VERIFIED")
        self.assertEqual(receipt["registry_sha256"],identity(created))

    def test_controlled_receipt_requires_separate_hash_attestation(self):
        held,_=self.run_fixture("controlled",False)
        self.assertEqual(held["entries"][0]["status"],"AWAITING_ATTESTATION")
        valid,proof=self.run_fixture("controlled",True)
        self.assertEqual(valid["entries"][0]["status"],"ACQUIRED")
        self.assertEqual(proof["transitions"][0]["attestation_ref"],"fixture/attestor")
        self.state=valid
        with self.assertRaisesRegex(ContractError,"urutan"):
            self.run_fixture("controlled",True)
