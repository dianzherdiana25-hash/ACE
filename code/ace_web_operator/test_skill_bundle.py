"""Perakit bundel: rantai hash per skill, agregat klaster, dan create-only."""
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_web_operator import skill_absorber,skill_bundle,skill_registry,skill_verifier
from ace_web_operator._contracts import ContractError,canonical,decode,identity
from ace_web_operator.test_skill_absorber import package_input
from ace_web_operator.test_skill_verifier import evidence


def _write(root,name,doc):
    payload=canonical(doc)+b"\n"
    target=root/name
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_bytes(payload)
    return {"path":name,"sha256":sha256(payload).hexdigest()}


class SkillBundleTests(unittest.TestCase):
    def setUp(self):
        self.base=Path(self.enterContext(TemporaryDirectory()))
        self.curriculum=self.base/"curriculum"
        self.curriculum.mkdir()
        self.inputs=self.base/"inputs"
        self.inputs.mkdir()
        self.package,self.suite,self.answers=evidence(self.curriculum)
        absorb_plan=package_input(self.curriculum,identity(self.suite))
        _package,absorb_receipt=skill_absorber.absorb(self.curriculum,absorb_plan,identity(absorb_plan))
        self.verification=skill_verifier.evaluate(self.package,identity(self.package),self.suite,
                                                   self.answers,identity(self.answers))
        lesson=(self.curriculum/"lesson.md").read_bytes()
        (self.inputs/"lesson.md").write_bytes(lesson)
        self.plan={"schema":"ace.web.skill-bundle-plan.v1","source_ref":"fixture/bundle",
                   "skill":"two_values","cluster":"k01",
                   "suite":_write(self.inputs,"suite.json",self.suite),
                   "plan":_write(self.inputs,"absorb_plan.json",absorb_plan),
                   "sources":[{"path":"lesson.md","sha256":sha256(lesson).hexdigest()}],
                   "package":_write(self.inputs,"package.json",self.package),
                   "absorb_receipt":_write(self.inputs,"absorb_receipt.json",absorb_receipt),
                   "answers":_write(self.inputs,"answers.json",self.answers),
                   "verification":_write(self.inputs,"verification.json",self.verification),
                   "attempts":[{"at":"2026-01-01T00:00:00Z","status":"fixture_passed",
                                "answers_sha256":identity(self.answers),
                                "verification_sha256":identity(self.verification),
                                "source_ref":"fixture/attempt-1"}]}

    def test_assemble_skill_manifest_matches_every_file(self):
        files,receipt=skill_bundle.assemble_skill(self.inputs,self.plan,identity(self.plan))
        self.assertEqual(receipt["status"],"assembled")
        for name in ("suite.json","plan.json","package.json","absorb_receipt.json","answers.json",
                     "verification.json","attempts.json","MANIFEST.json","sources/lesson.md"):
            self.assertIn(name,files)
        manifest=decode(files["MANIFEST.json"])
        self.assertEqual(manifest["verification_sha256"],identity(self.verification))
        self.assertEqual(manifest["package_sha256"],identity(self.package))
        for name,anchor in manifest["files"].items():
            self.assertEqual(sha256(files[name]).hexdigest(),anchor)
        self.assertEqual(receipt["manifest_sha256"],sha256(files["MANIFEST.json"]).hexdigest())

    def test_main_skill_bundle_is_create_only(self):
        plan_file=self.base/"bundle_plan.json"
        plan_file.write_bytes(canonical(self.plan)+b"\n")
        output=self.base/"bundle_out"
        argv=["skill",str(self.inputs),str(plan_file),str(output),"--expect-sha256",identity(self.plan)]
        self.assertEqual(skill_bundle.main(argv),0)
        self.assertTrue((output/"MANIFEST.json").exists())
        self.assertTrue((output/"sources"/"lesson.md").exists())
        with self.assertRaises(SystemExit) as caught:
            skill_bundle.main(argv)
        self.assertEqual(caught.exception.code,2)

    def test_tampered_artifact_bytes_rejected(self):
        target=self.inputs/"answers.json"
        target.write_bytes(target.read_bytes()+b" ")
        with self.assertRaisesRegex(ContractError,"SHA-256"):
            skill_bundle.assemble_skill(self.inputs,self.plan,identity(self.plan))

    def test_answers_chain_mismatch_rejected(self):
        broken=dict(self.answers)
        broken["suite_sha256"]="0"*64
        self.plan["answers"]=_write(self.inputs,"answers.json",broken)
        with self.assertRaisesRegex(ContractError,"tidak tertambat"):
            skill_bundle.assemble_skill(self.inputs,self.plan,identity(self.plan))

    def _cluster_plan(self):
        before={"schema":"ace.web.skill-registry.v1","revision":0,"source_ref":"fixture/empty","entries":[]}
        batch={"schema":"ace.web.skill-verification-batch.v1","entries":[
            {"source_ref":"fixture/batch","package":self.package,"package_sha256":identity(self.package),
             "suite":self.suite,"answers":self.answers,"answer_sha256":identity(self.answers)}]}
        policy={"schema":"ace.web.skill-registry-policy.v1","source_ref":"fixture/policy",
                "previous_sha256":identity(before),"batch_sha256":identity(batch),"attested_receipts":[]}
        after,revision=skill_registry.revise(before,policy,identity(policy),batch)
        campaign={"schema":"ace.web.skill-campaign-review.v1","source_ref":"fixture/campaign",
                  "registry_candidate":after,"acquired_before":0,"acquired_after":0}
        board={"schema":"ace.web.skill-board-report.v1","source_ref":"fixture/board",
               "registry_sha256":identity(after),"counts":{"ACQUIRED":0,"FRAGILE":0,"MISSING":1}}
        files,receipt=skill_bundle.assemble_skill(self.inputs,self.plan,identity(self.plan))
        manifest_ref=_write(self.inputs,"bundle_two_values/MANIFEST.json",decode(files["MANIFEST.json"]))
        return {"schema":"ace.web.skill-cluster-bundle-plan.v1","source_ref":"fixture/cluster","cluster":"k01",
                "registry_before":_write(self.inputs,"registry_before.json",before),
                "registry_after":_write(self.inputs,"registry_after.json",after),
                "policy":_write(self.inputs,"policy.json",policy),
                "batch":_write(self.inputs,"batch.json",batch),
                "revision_report":_write(self.inputs,"revision_report.json",revision),
                "campaign_review":_write(self.inputs,"campaign_review.json",campaign),
                "board_report":_write(self.inputs,"board_report.json",board),
                "skill_manifests":[{"skill":"two_values",**manifest_ref}]}

    def test_assemble_cluster_aggregate(self):
        plan=self._cluster_plan()
        files,receipt=skill_bundle.assemble_cluster(self.inputs,plan,identity(plan))
        self.assertEqual(receipt["status"],"assembled")
        manifest=decode(files["CLUSTER_MANIFEST.json"])
        after=decode((self.inputs/"registry_after.json").read_bytes())
        self.assertEqual(manifest["registry_after_sha256"],identity(after))
        self.assertEqual(manifest["registry_before_sha256"],
                         identity({"schema":"ace.web.skill-registry.v1","revision":0,
                                   "source_ref":"fixture/empty","entries":[]}))
        self.assertEqual(len(manifest["skill_manifests"]),1)
        self.assertEqual(manifest["skill_manifests"][0]["manifest_sha256"],
                         plan["skill_manifests"][0]["sha256"])
        for name,anchor in manifest["files"].items():
            self.assertEqual(sha256(files[name]).hexdigest(),anchor)
        self.assertEqual(receipt["cluster_manifest_sha256"],sha256(files["CLUSTER_MANIFEST.json"]).hexdigest())

    def test_cluster_policy_chain_mismatch_rejected(self):
        plan=self._cluster_plan()
        after=decode((self.inputs/"registry_after.json").read_bytes())
        policy=decode((self.inputs/"policy.json").read_bytes())
        policy["previous_sha256"]=identity(after)
        plan["policy"]=_write(self.inputs,"policy.json",policy)
        with self.assertRaisesRegex(ContractError,"tidak menambat"):
            skill_bundle.assemble_cluster(self.inputs,plan,identity(plan))


if __name__=="__main__":
    unittest.main()
