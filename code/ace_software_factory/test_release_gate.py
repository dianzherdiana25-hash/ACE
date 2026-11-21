"""Verifier gerbang rilis dengan coverage yang terukur dan hash ZIP."""
import unittest

from ace_software_factory import release_gate
from ace_software_factory._contracts import identity


class GateTests(unittest.TestCase):
    def setUp(self):
        digest="a"*64
        files=[{"path":"sample.py","sha256":digest,"bytes":12}]
        artifact=identity(files)
        self.evidence={"acceptance":{"schema":"ace.factory-acceptance-report.v1","status":"passed","artifact_sha256":artifact,
                                    "counts":{"passed":2,"failed":0,"missing_rule":0,"missing_observation":0}},
                       "coverage":{"schema":"ace.factory-coverage-report.v1","status":"measured","files":files,"skipped":0,
                                   "modules":[{"path":"sample.py","ratio_bp":7500,"sha256":digest}]},
                       "scan":{"schema":"ace.factory-sast-report.v1","status":"no_rule_matches","findings":[],"unscanned":[],
                               "sources":[{"path":"sample.py","sha256":digest,"parse_ok":True}]},
                       "archive":{"schema":"ace.factory-release-verification.v1","status":"verified",
                                  "zip_sha256":"b"*64,"manifest_sha256":"c"*64,"verified_files":1}}
        self.plan={"schema":"ace.factory-release-gate-policy.v1","artifact_sha256":artifact,"zip_sha256":"b"*64,
                   "zip_manifest_sha256":"c"*64,"source_ref":"fixture/release","expected_criteria":2,
                   "required_modules":[{"path":"sample.py","min_bp":7500,"source_ref":"fixture/coverage"}],
                   "evidence_sha256":{key:identity(row) for key,row in self.evidence.items()}}

    def decide(self):
        return release_gate.evaluate(self.plan,identity(self.plan),self.evidence)

    def test_boundary_coverage_and_all_anchor_checks_required(self):
        outcome=self.decide()
        self.assertEqual(outcome["status"],"ready_for_review")
        self.assertEqual(outcome["blockers"],[])
        self.plan["required_modules"][0]["min_bp"]=7501
        self.assertEqual(self.decide()["blockers"],[{
            "rule":"coverage_below_requirement","path":"sample.py","reference":"fixture/coverage",
            "minimum_bp":7501,"observed_bp":7500}])

    def test_missing_archive_and_stale_hash_receipt_fail_closed(self):
        self.evidence.pop("archive")
        self.evidence["acceptance"]["counts"]["passed"]=3
        result=self.decide()
        self.assertEqual(result["status"],"held")
        self.assertIn({"rule":"unverified","evidence":"acceptance"},result["blockers"])
        self.assertIn({"rule":"missing","evidence":"archive"},result["blockers"])

    def test_valid_hash_for_different_source_still_does_not_pass(self):
        self.evidence["scan"]["sources"][0]["sha256"]="f"*64
        self.plan["evidence_sha256"]["scan"]=identity(self.evidence["scan"])
        self.assertEqual(self.decide()["blockers"],[{"rule":"scan_different_or_missing_source","path":"sample.py"}])
