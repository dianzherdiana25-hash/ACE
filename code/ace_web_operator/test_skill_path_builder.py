"""Verifier topologi, tie-breaking, anggaran, dan premis yang hilang."""
import unittest

from ace_web_operator import skill_path_builder
from ace_web_operator._contracts import identity


def skill(key,refs,cost,rank):
    return {"id":key,"prerequisites":refs,"minutes":cost,"priority":rank,"source_ref":"fixture/"+key}


class PathTests(unittest.TestCase):
    def setUp(self):
        self.registry={"schema":"ace.web.skill-registry.v1","revision":0,"source_ref":"fixture/registry","entries":[]}
        self.plan={"schema":"ace.web.skill-path-plan.v1","source_ref":"fixture/path","registry_sha256":identity(self.registry),
                   "targets":["target","alt"],"minutes":6,"skills":[skill("target",["base"],2,60),
                       skill("base",[],2,90),skill("alt",[],2,90)]}

    def build(self):
        return skill_path_builder.build(self.plan,identity(self.plan),self.registry)

    def test_high_priority_ties_then_prerequisite_order_and_budget(self):
        report=self.build()
        self.assertEqual([row["skill"] for row in report["steps"]],["alt","base","target"])
        self.assertEqual(report["status"],"complete_path")
        self.plan["minutes"]=5
        result=self.build()
        self.assertEqual(result["budget_limited"],["target"])
        self.assertEqual(result["target_outstanding"],["target"])

    def test_missing_or_cyclic_dependency_remains_visible(self):
        self.plan["skills"][1]["prerequisites"]=["target","unlisted"]
        result=self.build()
        self.assertEqual(result["missing_skills"],["unlisted"])
        self.assertEqual([entry["skill"] for entry in result["blocked"]],["base","target"])
        self.assertEqual(result["target_outstanding"],["target"])
