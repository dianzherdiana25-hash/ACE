"""Verifier integrasi batch read-only dan bentuk laporan saat flag mati."""
from hashlib import sha256
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from ace_operational import leap_wiring
from ace_perception.test_batch_perception_runner import job, plan
from ace_perception.test_ocr_engine import canvas, raster


class WiringTests(unittest.TestCase):
    def setUp(self):
        self.workspace = Path(self.enterContext(TemporaryDirectory()))
        self.engine = SimpleNamespace(workspace=self.workspace, cycle_count=1)
        self.stage = self.workspace/"evo0053_perception"
        self.stage.mkdir()
        payload = raster(canvas(["H"]))
        (self.stage/"page.pgm").write_bytes(payload)
        self.image = {"path":"page.pgm","bytes":len(payload),"sha256":sha256(payload).hexdigest()}

    def configure(self, **options):
        limits = {"attempts": 8, **options}
        data = plan([job("observation", [self.image])], **limits)
        (self.stage/"batch.json").write_bytes(data)
        return {"ACE_EVO0053_PERCEPTION":"1","ACE_EVO0053_PLAN_SHA256":sha256(data).hexdigest()}

    def test_standalone_off_does_not_read_workspace(self):
        class Unreadable:
            @property
            def workspace(self):
                raise AssertionError("Gerbang mati tidak membaca workspace.")
        with patch.dict(os.environ,{},clear=True):
            self.assertEqual(leap_wiring.step_evo0053_perception(Unreadable()),{"status":"disabled"})

    def test_periodic_report_default_shape_and_flagged_batch_integration(self):
        expected = self.configure()
        fixture_report={"gates":[],"named_evidence_debt":[]}
        with patch("tools.periodic_self_report.build_periodic_self_report",return_value=fixture_report):
            with patch.dict(os.environ,{},clear=True):
                disabled=leap_wiring.step_periodic_self_report(self.engine)
            with patch.dict(os.environ,expected,clear=True):
                enabled=leap_wiring.step_periodic_self_report(self.engine)
        self.assertEqual(set(disabled),{"status","gates_count","debts_count","report_path"})
        result=enabled.pop("perception")
        self.assertEqual(enabled,disabled)
        self.assertEqual(result["status"],"reported")
        self.assertEqual(result["counts"],{"reported":1})
        self.assertEqual(result["plan_sha256"],expected["ACE_EVO0053_PLAN_SHA256"])
        self.assertEqual(sorted(item.name for item in self.stage.iterdir()),["batch.json","page.pgm"])

    def test_bad_anchor_and_batch_limit_fail_closed(self):
        large=self.configure(byte_budget=4_000_001)
        with patch.dict(os.environ,large,clear=True):
            self.assertEqual(leap_wiring.step_evo0053_perception(self.engine),
                             {"status":"hold","reason":"cycle_batch_limits"})
        with patch.dict(os.environ,{"ACE_EVO0053_PERCEPTION":"1"},clear=True):
            self.assertEqual(leap_wiring.step_evo0053_perception(self.engine)["reason"],"plan_anchor_missing_or_invalid")
        with patch.dict(os.environ,{**large,"ACE_EVO0053_PLAN_SHA256":"a"*64},clear=True):
            self.assertEqual(leap_wiring.step_evo0053_perception(self.engine)["reason"],"plan_unreadable_or_invalid")
