"""Unit tests for SubstrateGuardian somatic self-preservation."""
import unittest
from pathlib import Path
import tempfile
import sys

from ace_cognition.substrate_guardian import SubstrateGuardian, SubstrateTelemetry


class TestSubstrateGuardian(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp_dir.name)
        self.guardian = SubstrateGuardian(self.workspace)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_sense_returns_valid_telemetry(self):
        t = self.guardian.sense()
        self.assertIsInstance(t, SubstrateTelemetry)
        self.assertGreaterEqual(t.rss_mb, 0.0)
        self.assertGreater(t.disk_free_gb, 0.0)
        self.assertIn(t.status_level, {"OPTIMAL", "CAUTION", "THROTTLED", "CRITICAL"})
        self.assertIsInstance(t.to_dict(), dict)

    def test_emergency_freeze_creates_capsule(self):
        self.guardian.sense()
        out_dir = self.workspace / "freeze_target"
        res = self.guardian.execute_emergency_freeze(out_dir)
        self.assertEqual(res["status"], "FROZEN_SECURE")
        capsule = Path(res["capsule_path"])
        self.assertTrue(capsule.exists())
        self.assertIn("emergency_dna_capsule.json", capsule.name)


if __name__ == "__main__":
    unittest.main()
