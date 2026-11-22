"""Buktikan kampanye multi-batch, batas roster, dan akuntansi tanpa menulis registry."""
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._contracts import ContractError, canonical, decode, identity
from .skill_campaign import campaign
from .skill_registry import revise
from .skill_verifier import evaluate
from .test_skill_verifier import evidence

FIXTURE = Path(__file__).parent / "fixtures" / "evo0055_skill_roadmap.json"

class CampaignTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(TemporaryDirectory()))
        self.registry = {"schema": "ace.web.skill-registry.v1", "revision": 0,
                         "source_ref": "fixture/genesis", "entries": []}
        self.roadmap = {"schema": "ace.web.skill-roadmap.v1", "source_ref": "fixture/roadmap",
                        "clusters": [{"id": "k01", "title": "Sample", "domain": "software",
                                      "source_ref": "fixture/k01", "skills": [
                                          {"id": "two_values", "title": "Add pairs", "source_ref": "fixture/example"}
                                      ]}]}
        self.plan = {"schema": "ace.web.skill-campaign-plan.v1", "source_ref": "fixture/review",
                     "roadmap": self.save("roadmap.json", self.roadmap),
                     "registry": self.save("registry.json", self.registry), "batches": [], "target": 1}

    def save(self, name, data):
        raw = canonical(data) + b"\n"
        (self.root / name).write_bytes(raw)
        return {"path": name, "sha256": sha256(raw).hexdigest()}

    def add_batch(self, key, state, scope, *, version=1, attest=False):
        package, testing, answers = evidence(self.root, scope)
        package["version"] = version
        answers["package_sha256"] = identity(package)
        answers["at"] = f"2026-01-0{version}T00:00:00Z"
        proof = evaluate(package, identity(package), testing, answers, identity(answers))
        batch = {"schema": "ace.web.skill-verification-batch.v1", "entries": [
            {"source_ref": f"fixture/{key}", "package": package, "package_sha256": identity(package),
             "suite": testing, "answers": answers, "answer_sha256": identity(answers)}
        ]}
        whitelist = [{"skill": "two_values", "verification_sha256": identity(proof),
                      "package_sha256": identity(package), "authority_ref": "fixture/emulated_attestor"}] if attest else []
        rule = {"schema": "ace.web.skill-registry-policy.v1", "source_ref": f"fixture/{key}_policy",
                "previous_sha256": identity(state), "batch_sha256": identity(batch), "attested_receipts": whitelist}
        self.plan["batches"].append({"id": key, "policy": self.save(f"{key}_policy.json", rule),
                                     "batch": self.save(f"{key}_batch.json", batch)})
        return revise(state, rule, identity(rule), batch)[0]

    def test_fixture_attestation_does_not_count_and_next_unattested_receipt_stays_open(self):
        stage = self.add_batch("rehearsal", self.registry, "fixture", attest=True)
        final = self.add_batch("ordered", stage, "controlled", version=2)
        before = {path.name: path.read_bytes() for path in self.root.iterdir()}
        report = campaign(self.plan, identity(self.plan), self.root)
        self.assertEqual([row["transitions"][0]["to"] for row in report["batches"]],
                         ["FIXTURE_VERIFIED", "AWAITING_ATTESTATION"])
        self.assertEqual(report["registry_candidate"], final)
        self.assertEqual((report["acquired_after"], report["remaining_to_target"]), (0, 1))
        self.assertEqual({path.name: path.read_bytes() for path in self.root.iterdir()}, before)

    def test_wrong_parent_rejects_whole_preview_and_genesis_remains_unchanged(self):
        self.add_batch("rehearsal", self.registry, "fixture")
        self.add_batch("stale", self.registry, "controlled", version=2)
        historical = (self.root / "registry.json").read_bytes()
        with self.assertRaisesRegex(ContractError, "berbeda"):
            campaign(self.plan, identity(self.plan), self.root)
        self.assertEqual((self.root / "registry.json").read_bytes(), historical)

    def test_empty_actual_roadmap_with_empty_fixture_registry_reports_all_candidates(self):
        road = decode(FIXTURE.read_bytes())
        self.plan["roadmap"] = self.save("roadmap.json", road)
        self.plan["target"] = 300
        report = campaign(self.plan, identity(self.plan), self.root)
        self.assertEqual(report["planned_skills"], 400)
        self.assertEqual(report["remaining_to_target"], 300)
        self.assertEqual(report["acquired_after"], 0)
