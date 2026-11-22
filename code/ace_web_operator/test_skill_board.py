"""Verifier denominator roadmap, status fixture, atestasi dan retensi."""
from pathlib import Path
import unittest

from ace_web_operator import skill_board
from ace_web_operator._contracts import ContractError,decode,identity
from ace_web_operator.test_skill_composer import acquired


class BoardTests(unittest.TestCase):
    def setUp(self):
        self.registry={"schema":"ace.web.skill-registry.v1","revision":1,"source_ref":"fixture/registry",
                       "entries":[acquired("one"),acquired("two"),acquired("three",status="FIXTURE_VERIFIED")]}
        self.roadmap={"schema":"ace.web.skill-roadmap.v1","source_ref":"fixture/roadmap",
                      "clusters":[{"id":"k01","title":"Uji","domain":"software","source_ref":"fixture/cluster",
                                    "skills":[{"id":key,"title":key,"source_ref":"fixture/"+key}
                                              for key in ("one","two","three","four")]}]}
        self.staleness={"schema":"ace.web.skill-staleness-report.v1","plan_sha256":"c"*64,"source_ref":"fixture/check",
                        "registry_sha256":identity(self.registry),"versions_sha256":"c"*64,"as_of":"2026-01-05T00:00:00Z",
                        "unregistered_versions":[],"skills":[{"skill":"one","cluster":"k01","status":"STALE",
                            "reasons":["verification_expired"],"age_seconds":4*86400,"verification_sha256":"d"*64,
                            "registry_ref":"fixture/registry","version_ref":"fixture/version","age_rule_ref":"fixture/rule",
                            "retention":None}]}

    def board(self):
        plan={"schema":"ace.web.skill-board-plan.v1","source_ref":"fixture/count","roadmap_sha256":identity(self.roadmap),
              "registry_sha256":identity(self.registry),"staleness_sha256":identity(self.staleness)}
        return skill_board.build(plan,identity(plan),self.roadmap,self.registry,self.staleness)

    def test_learned_report_only_counts_acquired_with_valid_scope_and_no_stale_evidence(self):
        result=self.board()
        self.assertEqual(result["counts"],{"ACQUIRED":1,"FRAGILE":1,"MISSING":2})
        self.assertEqual(result["skills_requested"],4)
        self.assertEqual(result["clusters"][0]["skills"][2]["reason"],"FIXTURE_VERIFIED")
        self.assertIn("fixture/authority",skill_board.markdown(result))

    def test_refuses_staleness_for_other_revision(self):
        self.staleness["registry_sha256"]="a"*64
        with self.assertRaisesRegex(ContractError,"revisi"):
            self.board()

    def test_named_program_roadmap_has_forty_clusters_of_ten_candidates(self):
        roadmap=decode((Path(__file__).with_name("fixtures")/"evo0055_skill_roadmap.json").read_bytes())
        self.assertEqual(len(roadmap["clusters"]),40)
        self.assertTrue(all(len(cluster["skills"])==10 for cluster in roadmap["clusters"]))
        self.assertEqual(len({row["id"] for cluster in roadmap["clusters"] for row in cluster["skills"]}),400)
