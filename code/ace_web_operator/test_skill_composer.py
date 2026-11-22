"""Verifier chaining port, prasyarat acquired, dan suite independen."""
import unittest

from ace_web_operator import skill_composer
from ace_web_operator._contracts import ContractError,identity


def acquired(key="parse",anchor="b",status="ACQUIRED"):
    return {"skill":key,"cluster":"k01","version":1,"status":status,"package_sha256":anchor*64,"suite_sha256":"c"*64,
            "verification_sha256":"d"*64,"score_bp":9500,"at":"2026-01-01T00:00:00Z","source_ref":"fixture/skill",
            "attestation_ref":"fixture/authority" if status=="ACQUIRED" else None}


class ComposeTests(unittest.TestCase):
    def setUp(self):
        self.registry={"schema":"ace.web.skill-registry.v1","revision":1,"source_ref":"fixture/registry",
                       "entries":[acquired(),acquired("total","a")]}
        self.plan={"schema":"ace.web.skill-composition-plan.v1","id":"summarize_pipe","source_ref":"fixture/recipe",
                   "heldout_sha256":"f"*64,"inputs":{"value":"text"},"outputs":{"sum":"last.result"},
                   "steps":[{"id":"last","skill":"total","package_sha256":"a"*64,"takes":{"input":"list"},
                             "produces":{"result":"integer"},"bindings":{"input":"first.result"},"source_ref":"fixture/total"},
                            {"id":"first","skill":"parse","package_sha256":"b"*64,"takes":{"input":"text"},
                             "produces":{"result":"list"},"bindings":{"input":"input.value"},"source_ref":"fixture/parse"}]}

    def run_fixture(self):
        self.plan["registry_sha256"]=identity(self.registry)
        return skill_composer.build(self.plan,identity(self.plan),self.registry)

    def test_composition_waits_for_its_own_suite_and_known_prerequisites(self):
        report=self.run_fixture()
        self.assertEqual([row["id"] for row in report["steps"]],["first","last"])
        self.assertEqual(report["status"],"ready_for_heldout")
        self.registry["entries"][0]=acquired(status="FIXTURE_VERIFIED")
        self.assertEqual(self.run_fixture()["gaps"][0]["reason"],"component_not_acquired")

    def test_type_mismatch_and_suite_reuse_are_rejected(self):
        self.plan["heldout_sha256"]="c"*64
        self.assertTrue(all(row["reason"]=="suite_not_independent" for row in self.run_fixture()["gaps"]))
        self.plan["steps"][0]["takes"]["input"]="text"
        with self.assertRaisesRegex(ContractError,"kompatibel"):
            self.run_fixture()
