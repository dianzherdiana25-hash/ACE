"""Unit & Adversarial Tests for ACE Fase 9 Autonomous Research Operating Mode."""
from __future__ import annotations

from pathlib import Path
import sqlite3
import tempfile
import unittest

from ace_autonomy import IntegrityError, PolicyError

from .coordinator import run_autonomous_research_campaign, write_agenda_evidence_gz
from .models import ResearchArchive, ResearchCampaignBudget
from .verify import verify_agenda_artifact


class TestAutonomousResearchAgenda(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[2]

    def test_campaign_budget_bounds_enforced(self) -> None:
        ResearchCampaignBudget(max_cycles=5, max_total_steps=32, max_total_cpu_s=20.0).validate()
        for bad in (
            ResearchCampaignBudget(max_cycles=0),
            ResearchCampaignBudget(max_cycles=99),
            ResearchCampaignBudget(max_total_steps=500),
            ResearchCampaignBudget(max_total_cpu_s=-1.0),
        ):
            with self.assertRaises(PolicyError):
                bad.validate()

    def test_research_archive_detects_negative_result_deletion_or_tamper(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp) / "arch"
            with ResearchArchive(ws) as arch:
                arch.append_cycle({
                    "cycle_index": 1,
                    "hypothesis_id": "H_POS",
                    "gap_id": "G1",
                    "outcome_status": "SUPPORTED_BOUNDED",
                    "falsified": False,
                })
                arch.append_cycle({
                    "cycle_index": 2,
                    "hypothesis_id": "H_NEG",
                    "gap_id": "G2",
                    "outcome_status": "REFUTED_NEGATIVE_ARCHIVED",
                    "falsified": True,
                })
                self.assertEqual(len(arch.list_records()), 2)

            # Tamper with negative result row to hide falsification -> fail-closed IntegrityError!
            con = sqlite3.connect(ws / "research_archive.sqlite3")
            con.execute("UPDATE archived_cycles SET falsified=0 WHERE hypothesis_id='H_NEG'")
            con.commit()
            con.close()

            with self.assertRaises(IntegrityError):
                ResearchArchive(ws)

    def test_five_cycle_autonomous_campaign_and_post_refutation_adaptation(self) -> None:
        rep = run_autonomous_research_campaign(self.repo_root)
        self.assertEqual(rep["campaign_budget"]["cycles_executed"], 5)
        self.assertEqual(rep["campaign_budget"]["human_prompts_between_cycles"], 0)
        self.assertFalse(rep["oaie_established"])
        self.assertTrue(rep["evidence_flags"]["ACE_BASE_RUNTIME_EXECUTED"])
        self.assertTrue(rep["evidence_flags"]["NEW_CAPABILITY_INTEGRATED_AND_EXECUTED"])
        self.assertFalse(rep["evidence_flags"]["SCIENTIFIC_CAPABILITY_VALIDATED"])
        self.assertTrue(rep["agenda_loop_gates"]["all_passed"])

        arch = rep["archive_summary"]
        self.assertGreaterEqual(arch["supported_bounded"], 3)
        self.assertGreaterEqual(arch["refuted_negative_archived"], 1)
        self.assertGreaterEqual(arch["abstained_unidentifiable"], 1)
        self.assertTrue(arch["metacognitive_post_refutation_abstention_verified"])

        with tempfile.TemporaryDirectory() as tmp:
            gz = Path(tmp) / "agenda.json.gz"
            sha = write_agenda_evidence_gz(rep, gz)
            ver = verify_agenda_artifact(gz, self.repo_root, replay=True)
            self.assertTrue(ver["verified"])
            self.assertEqual(ver["uncompressed_sha256"], sha)


if __name__ == "__main__":
    unittest.main()
