from hashlib import sha256
import os
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from ._contracts import decode, identity
from .closed_bench import assess
from ace_operational.leap_wiring import step_evo0059_presence, step_mobile_report

FIXTURES = Path(__file__).parent / "fixtures" / "closed_presence"


class PresenceBenchTests(unittest.TestCase):
    def test_canonical_fixture_report_is_recomputed(self):
        plan = decode((FIXTURES / "plan.json").read_bytes())
        report = assess(plan, identity(plan), FIXTURES)
        self.assertEqual(report, decode((FIXTURES / "run.json").read_bytes()))
        self.assertEqual((report["dialogue"]["correct"], report["dialogue"]["gold"]), (10, 10))
        self.assertEqual((report["dialogue"]["summary_checked"], report["dialogue"]["unsupported_summary"]), (9, []))
        self.assertEqual((report["time"]["correct"], report["time"]["evaluated"]), (16, 16))

    def test_mobile_report_gate_default_on_and_missing_anchor_are_explicit(self):
        with TemporaryDirectory() as tmp, patch.dict(os.environ, {}, clear=True):
            workspace = Path(tmp)
            engine = SimpleNamespace(workspace=workspace)
            off = step_mobile_report(engine)
            self.assertEqual(set(off), {"status", "report_bytes"})
            self.assertEqual(step_evo0059_presence(engine), {"status": "disabled"})
            shutil.copytree(FIXTURES, workspace / "evo0059_presence")
            os.environ["ACE_EVO0059_PRESENCE"] = "1"
            self.assertEqual(step_mobile_report(engine)["presence"]["status"], "held")
            os.environ["ACE_EVO0059_PLAN_SHA256"] = sha256((FIXTURES / "plan.json").read_bytes()).hexdigest()
            leaf = step_mobile_report(engine)["presence"]
            self.assertEqual((leaf["status"], leaf["temporal_count"]), ("ok", 16))
            (workspace / "evo0059_presence" / "time_labels.json").write_bytes(b"{}")
            self.assertEqual(step_mobile_report(engine)["presence"]["status"], "held")
