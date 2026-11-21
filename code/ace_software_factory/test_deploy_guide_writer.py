"""Verifier topologi deploy, rollback terbalik, dan kewajiban verifikasi."""
import unittest

from ace_software_factory import deploy_guide_writer as guide
from ace_software_factory._contracts import ContractError, identity


def step(key, kind, requires=(), rollback=None):
    return {"id": key, "kind": kind, "requires": list(requires), "action": f"Jalankan {key}",
            "verify": f"Periksa {key}", "rollback": rollback, "source_ref": f"fixture/deploy/{key}"}


class Guides(unittest.TestCase):
    def setUp(self):
        self.release = {"schema": "ace.factory-release-verification.v1", "status": "verified",
                        "zip_sha256": "a" * 64, "manifest_sha256": "b" * 64, "verified_files": 2}
        self.plan = {"schema": "ace.factory-deploy-plan.v1", "release_sha256": identity(self.release),
                     "product_id": "sample", "target": "host uji", "source_ref": "fixture/cutover",
                     "steps": [step("smoke", "verify", ["start"]), step("prepare", "preflight"),
                               step("save", "backup", ["prepare"]),
                               step("copy", "install", ["save"], "Pulihkan folder"),
                               step("start", "activate", ["copy"], "Hentikan unit")]}

    def test_orders_steps_and_produces_rollback_for_verified_release(self):
        document, report = guide.build(self.plan, self.release, identity(self.plan))
        self.assertEqual([row["id"] for row in report["steps"]], ["prepare", "save", "copy", "start", "smoke"])
        self.assertEqual(report["rollback_order"], ["start", "copy"])
        self.assertLess(document.index("Hentikan unit"), document.index("Pulihkan folder"))
        self.assertIn("fixture/deploy/smoke", document)

    def test_rejects_cycle_and_missing_transitive_verification(self):
        self.plan["steps"][1]["requires"] = ["prepare_two"]
        self.plan["steps"].append(step("prepare_two", "preflight", ["prepare"]))
        with self.assertRaisesRegex(ContractError, "siklus"):
            guide.build(self.plan, self.release, identity(self.plan))
        self.plan["steps"].pop()
        self.plan["steps"][1]["requires"] = []
        self.plan["steps"][0]["requires"] = ["copy"]
        with self.assertRaisesRegex(ContractError, "Setiap perubahan"):
            guide.build(self.plan, self.release, identity(self.plan))

    def test_no_missing_rollback_or_unverified_artifact(self):
        self.plan["steps"][3]["rollback"] = None
        with self.assertRaisesRegex(ContractError, "Rollback"):
            guide.build(self.plan, self.release, identity(self.plan))
        self.release["status"] = "invalid"
        self.plan["release_sha256"] = identity(self.release)
        with self.assertRaisesRegex(ContractError, "terverifikasi"):
            guide.build(self.plan, self.release, identity(self.plan))
