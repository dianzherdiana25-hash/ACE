"""Tests for opportunity_register (Addendum 38 §2)."""

import tempfile
import unittest
from pathlib import Path

from ace_operational.opportunity_register import (ASSETS,
                                                  OpportunityRegister,
                                                  build_scan_packet,
                                                  origin_share,
                                                  scan_opportunities,
                                                  seed_founder_flywheel)


class RegisterTests(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.reg = OpportunityRegister(Path(self.tmp.name) / "reg.jsonl")

    def tearDown(self):
        self.tmp.cleanup()

    def test_founder_flywheel_seeded_once_with_fences(self):
        entry = seed_founder_flywheel(self.reg)
        self.assertEqual(entry["origin"], "FOUNDER")
        self.assertEqual(entry["combination"],
                         ["venue_kbm", "venue_threads"])
        self.assertEqual(entry["status"], "design")
        self.assertTrue(any("privacy" in f for f in entry["fences"]))
        self.assertIsNone(seed_founder_flywheel(self.reg))
        self.assertEqual(len(self.reg.entries()), 1)

    def test_chain_verifies_and_detects_tamper(self):
        seed_founder_flywheel(self.reg)
        self.reg.append(title="x", combination=["venue_kbm", "venue_lynk_id"],
                        rationale="r", origin="brain_local_qwen3_8b",
                        status="proposed")
        entries = self.reg.entries()
        self.assertTrue(self.reg.verify_chain(entries))
        entries[0]["title"] = "tampered"
        self.assertFalse(self.reg.verify_chain(entries))

    def test_append_rejects_unknown_asset_and_single_asset(self):
        with self.assertRaises(ValueError):
            self.reg.append(title="x", combination=["venue_kbm", "nope"],
                            rationale="r", origin="FOUNDER",
                            status="proposed")
        with self.assertRaises(ValueError):
            self.reg.append(title="x", combination=["venue_kbm"],
                            rationale="r", origin="FOUNDER",
                            status="proposed")

    def test_append_rejects_non_brain_origin(self):
        with self.assertRaises(ValueError):
            self.reg.append(title="x",
                            combination=["venue_kbm", "venue_threads"],
                            rationale="r", origin="venue_kbm",
                            status="proposed")

    def test_origin_share_math(self):
        seed_founder_flywheel(self.reg)
        self.reg.append(title="x", combination=["venue_kbm", "venue_lynk_id"],
                        rationale="r", origin="brain_claude_ian_ila",
                        status="proposed")
        share = origin_share(self.reg.entries())
        self.assertEqual(share["total"], 2)
        self.assertEqual(share["ace_side_share"], 0.5)
        self.assertEqual(share["by_origin"]["FOUNDER"], 1)


class ScanTests(unittest.TestCase):

    def test_scan_excludes_registered_and_includes_unexploited(self):
        with tempfile.TemporaryDirectory() as tmp:
            reg = OpportunityRegister(Path(tmp) / "reg.jsonl")
            seed_founder_flywheel(reg)
            candidates = scan_opportunities(entries=reg.entries())
        combos = [tuple(c["combination"]) for c in candidates]
        self.assertNotIn(("venue_kbm", "venue_threads"), combos)
        self.assertIn(("cap_serial_fiction", "venue_lynk_id"), combos)
        # Every candidate involves at least one venue and is a pair.
        for combo in combos:
            self.assertEqual(len(combo), 2)
            self.assertTrue(any(a.startswith("venue_") for a in combo))

    def test_scan_is_deterministic(self):
        self.assertEqual(scan_opportunities(), scan_opportunities())

    def test_packet_shape(self):
        packet = build_scan_packet(scan_opportunities())
        self.assertEqual(packet["candidate_count"],
                         len(packet["facts"]))
        self.assertTrue(all(f["id"].startswith("candidate-")
                            for f in packet["facts"]))

    def test_registry_assets_have_evidence(self):
        for asset_id, asset in ASSETS.items():
            self.assertIn(asset["kind"], ("venue", "brain", "capability"),
                          asset_id)
            self.assertTrue(asset["evidence"], asset_id)
            self.assertTrue(asset["status"], asset_id)


if __name__ == "__main__":
    unittest.main()
