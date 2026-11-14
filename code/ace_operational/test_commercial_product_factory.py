"""Tests for EPOCH F — Commercial Product Factory & Trustless B2A Verification Economy."""
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from ace_operational.commercial_product_factory import (
    AntiSlopKnowledgePublisher,
    CommercialProductFactory,
    TreasuryIsolationError,
    TrustlessB2AVerificationProtocol,
    UngroundedClaimError,
    run_commercial_factory_cycle,
)


class CommercialProductFactoryTests(unittest.TestCase):
    def test_commercial_cli_products_anti_slop_and_b2a_receipts(self) -> None:
        with tempfile.TemporaryDirectory() as d1:
            report = run_commercial_factory_cycle(d1)
            self.assertEqual(len(report["products"]), 2)
            self.assertTrue(all(p["tests_passed"] for p in report["products"]))
            self.assertEqual(report["receipts_verified_o1"], [True, True])
            self.assertEqual(report["opportunity_entries"], 1)
            self.assertTrue((Path(d1) / "products" / "ace_invoice_sla_auditor" / "pyproject.toml").exists())
            self.assertTrue((Path(d1) / "products" / "ace_b2a_citation_guard" / "pyproject.toml").exists())
            self.assertTrue((Path(d1) / "knowledge_pack" / "knowledge_bundle.json").exists())

    def test_fail_closed_ungrounded_claim_and_treasury_isolation(self) -> None:
        with tempfile.TemporaryDirectory() as d1:
            pub = AntiSlopKnowledgePublisher()
            with self.assertRaises(UngroundedClaimError):
                pub.publish_bundle(
                    out_dir=Path(d1) / "bad_bundle",
                    title="Slop",
                    claims=[{"text": "Fabricated stat 99%", "source_id": "non_existent"}],
                    verified_sources={"real_src": "abc"},
                )

            factory = CommercialProductFactory(Path(d1) / "products")
            with self.assertRaises(TreasuryIsolationError):
                factory._verify_treasury_isolation({"leak.py": "SECRET='sk_live_123456'"})

            p1 = factory.build_invoice_sla_auditor()
            with self.assertRaises(TreasuryIsolationError):
                TrustlessB2AVerificationProtocol.issue_receipt(
                    product=p1,
                    ledger_entry_sha256="a" * 64,
                    treasury_owner_custody_isolated=False,
                )


if __name__ == "__main__":
    unittest.main()
