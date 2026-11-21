"""Verifier independensi pemasok, salinan dan sumber yang membantah."""
import unittest

from ace_web_operator import fact_verifier_web
from ace_web_operator._contracts import identity


class FactTests(unittest.TestCase):
    def setUp(self):
        self.subject={"subject":"kelas-a","predicate":"peserta","value":12,"unit":"orang","scope":"fixture-rekap-01"}
        self.registry={"schema":"ace.web.publisher-registry.v1","source_ref":"fixture/publishers",
                       "publishers":[{"host":host+".invalid","owner_group":owner,"source_ref":"fixture/"+host}
                                     for host,owner in (("first","team_a"),("mirror","team_a"),("independent","team_b"))]}
        self.evidence={"schema":"ace.web.fact-observations.v1","observations":[]}
        self.add("first","a",12)
        self.add("mirror","b",12)

    def add(self,host,stamp,value):
        self.evidence["observations"].append({"id":host,"address":f"https://{host}.invalid/page","html_sha256":stamp*64,
                                             "artifact_ref":f"fixture/{host}.html","observation":{**self.subject,"value":value}})

    def decide(self):
        plan={"schema":"ace.web.fact-plan.v1","id":"class_count","source_ref":"fixture/claim","claim":self.subject,
              "registry_sha256":identity(self.registry),"evidence_sha256":identity(self.evidence)}
        return fact_verifier_web.verify(plan,identity(plan),self.registry,self.evidence)

    def test_two_brands_same_owner_and_identical_bytes_do_not_provide_two_votes(self):
        self.add("independent","a",12)
        self.assertEqual(self.decide()["status"],"insufficient_independent_sources")
        self.evidence["observations"][-1]["html_sha256"]="c"*64
        report=self.decide()
        self.assertEqual(report["support_groups"],["team_a","team_b"])
        self.assertEqual(report["status"],"verified_fixture_scopes")

    def test_incompatible_value_reported_as_dispute(self):
        self.add("independent","c",13)
        self.assertEqual(self.decide()["status"],"disputed")
