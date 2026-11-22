"""Buktikan gerbang default mati dan hanya receipt ber-anchor yang dinilai."""
from hashlib import sha256
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from ace_operational import leap_wiring
from ace_software_factory import spec_writer
from ace_software_factory._contracts import canonical, identity
from ace_software_factory.test_spec_writer import brief


class FactoryWiringTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(TemporaryDirectory()))
        self.engine = SimpleNamespace(workspace=self.root, store=None)
        self.spec = spec_writer.write(brief())
        self.contract = {"schema": "ace.factory-acceptance-contract.v1", "spec_sha256": identity(self.spec),
                         "source_ref": "fixture/expectation",
                         "rules": [{"id": "count", "operator": "equals", "expected": 2,
                                    "criterion_ref": "fixture/brief/1", "source_ref": "fixture/expectation/1"}]}
        self.observed = {"schema": "ace.factory-observations.v1", "product_id": "fixture_catalog",
                         "artifact_sha256": "a" * 64, "contract_sha256": identity(self.contract),
                         "records": [{"id": "count", "value": 2, "source_ref": "fixture/output/1"}]}
        self.bundle = {"schema": "ace.factory-acceptance-bundle.v1", "spec": self.spec, "contract": self.contract,
                       "observations": self.observed, "artifact_sha256": "a" * 64}
        self.path = self.root / "evo0054_factory" / "acceptance.json"

    def test_disabled_uses_existing_software_factory_step_without_new_reads(self):
        with patch.dict(os.environ, {"ACE_EVO0054_FACTORY": "0"}), patch(
                "ace_software_factory._artifact_io.read_relative", side_effect=AssertionError("dilarang baca")):
            self.assertEqual(leap_wiring.step_software_factory(self.engine), {"status": "skipped", "reason": "no store"})
            self.assertEqual(leap_wiring.step_evo0054_factory(self.engine), {"status": "disabled"})
        self.assertEqual(list(self.root.iterdir()), [])

    def test_runtime_reaches_acceptance_judge_without_changing_workspace(self):
        payload = canonical(self.bundle)
        self.path.parent.mkdir()
        self.path.write_bytes(payload)
        checksum = sha256(payload).hexdigest()
        with patch.dict(os.environ, {"ACE_EVO0054_FACTORY": "1", "ACE_EVO0054_ACCEPTANCE_SHA256": checksum}):
            result = leap_wiring.step_software_factory(self.engine)
            self.assertEqual(result["status"], "passed")
            self.assertEqual(result["acceptance"]["counts"]["passed"], 1)
            self.assertEqual(result["evidence_sha256"], checksum)
            self.assertEqual(list(self.path.parent.iterdir()), [self.path])
            self.assertEqual(self.path.read_bytes(), payload)
            self.path.write_bytes(payload + b" ")
            self.assertEqual(leap_wiring.step_software_factory(self.engine)["reason"], "acceptance_evidence_unavailable")

    def test_no_anchor_or_indirected_receipt_holds(self):
        self.path.parent.mkdir()
        payload = canonical(self.bundle)
        link_target = self.root / "source.json"
        link_target.write_bytes(payload)
        self.path.symlink_to(link_target)
        with patch.dict(os.environ, {"ACE_EVO0054_FACTORY": "1", "ACE_EVO0054_ACCEPTANCE_SHA256": ""}):
            self.assertEqual(leap_wiring.step_software_factory(self.engine)["reason"], "workspace_or_anchor_missing")
        with patch.dict(os.environ, {"ACE_EVO0054_FACTORY": "1",
                                    "ACE_EVO0054_ACCEPTANCE_SHA256": sha256(payload).hexdigest()}):
            self.assertEqual(leap_wiring.step_software_factory(self.engine)["reason"], "acceptance_evidence_unavailable")
