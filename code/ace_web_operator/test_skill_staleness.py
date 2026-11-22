"""Verifier kesegaran tanggal dan bukti perubahan versi tanpa klaim baru."""
import unittest

from ace_web_operator import skill_staleness
from ace_web_operator._contracts import identity
from ace_web_operator.test_skill_composer import acquired


class StaleTests(unittest.TestCase):
    def setUp(self):
        self.registry={"schema":"ace.web.skill-registry.v1","revision":1,"source_ref":"fixture/registry",
                       "entries":[acquired(),acquired("untested","a",status="FIXTURE_VERIFIED")]}
        self.versions={"schema":"ace.web.skill-version-snapshot.v1","source_ref":"fixture/version",
                       "entries":[{"id":"parse","current_version":1,"package_sha256":"b"*64,"source_ref":"fixture/parse",
                                   "retention":None}]}
        self.plan={"schema":"ace.web.skill-staleness-plan.v1","source_ref":"fixture/policy","registry_sha256":identity(self.registry),
                   "as_of":"2026-01-07T23:59:59Z","cluster_limits":[{"cluster":"k01","days":7,"source_ref":"fixture/age"}]}

    def scan(self):
        self.plan["versions_sha256"]=identity(self.versions)
        return skill_staleness.scan(self.plan,identity(self.plan),self.registry,self.versions)["skills"]

    def test_age_boundary_and_unverified_entry(self):
        rows=self.scan()
        self.assertEqual([row["status"] for row in rows],["CURRENT","UNVERIFIED"])
        self.plan["as_of"]="2026-01-08T00:00:00Z"
        self.assertEqual(self.scan()[0]["reasons"],["verification_expired"])

    def test_drift_and_missing_version_remain_distinct(self):
        self.versions["entries"][0]["current_version"]=2
        self.assertEqual(self.scan()[0]["reasons"],["version_drift"])
        self.versions["entries"]=[]
        self.assertEqual(self.scan()[0]["status"],"UNKNOWN")
