from hashlib import sha256
import os
from pathlib import Path
from shutil import copytree
from types import SimpleNamespace
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from ._contracts import GuardianError, decode, identity
from .closed_bench import measure, recheck
from ace_operational.leap_wiring import _guardian_fixture_evidence, step_custody_manifest_check

SOURCE = Path(__file__).parent / "fixtures" / "closed_guardian"


class GuardianBenchTests(unittest.TestCase):
    def test_end_to_end_rerun_and_recheck_pinned_report(self):
        plan = decode((SOURCE / "plan.json").read_bytes())
        report = decode((SOURCE / "run.json").read_bytes())
        snapshot = identity(plan)
        live = measure(plan, snapshot, SOURCE)
        for key in ("isolation", "receipt_coverage", "checked_actions", "correct_outcomes", "registered_classes_seen", "calibration"):
            self.assertEqual(live[key], report[key])
        checks = recheck(plan, snapshot, report, SOURCE)
        self.assertTrue(checks["isolation_checks_passed"])
        self.assertTrue(checks["recovery_under_limit"])
        self.assertEqual(checks["receipt_coverage"], "1")
        self.assertEqual(checks["registered_classes_seen"], 8)
        broken = {**report, "checked_actions": 9}
        with self.assertRaises(GuardianError):
            recheck(plan, snapshot, broken, SOURCE)

    def test_opt_in_is_read_only_and_held_on_byte_mismatch(self):
        with TemporaryDirectory() as tmp, patch.dict(os.environ, {}, clear=True):
            ws = Path(tmp)
            root = ws / "evo0060_guardian"
            copytree(SOURCE, root)
            engine = SimpleNamespace(workspace=ws, cycle_count=1)
            self.assertNotIn("guardian", step_custody_manifest_check(engine))
            self.assertEqual(_guardian_fixture_evidence(engine), {"status": "disabled"})
            os.environ["ACE_EVO0060_GUARDIAN"] = "1"
            self.assertEqual(step_custody_manifest_check(engine)["guardian"]["status"], "held")
            for flag, filename in (("PLAN", "plan.json"), ("RUN", "run.json")):
                os.environ[f"ACE_EVO0060_{flag}_SHA256"] = sha256((root / filename).read_bytes()).hexdigest()
            leaf = step_custody_manifest_check(engine)["guardian"]
            self.assertEqual(leaf["status"], "ok")
            self.assertEqual(leaf["checked_actions"], 11)
            self.assertFalse(any(path.name == "recovered" for path in ws.iterdir()))
            (root / "failed" / "heap.json").write_text("changed", encoding="utf-8")
            self.assertEqual(step_custody_manifest_check(engine)["guardian"]["status"], "held")
