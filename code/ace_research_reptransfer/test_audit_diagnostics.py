"""Unit tests for the independent post-score R9 audit diagnostics."""
from __future__ import annotations

import unittest

from .audit_diagnostics import (
    check_ast_import_isolation,
    run_full_audit,
)


class TestR9AuditDiagnostics(unittest.TestCase):
    def test_ast_import_isolation(self):
        res = check_ast_import_isolation()
        self.assertTrue(res["isolated"], msg=f"Violations: {res['violations']}")
        self.assertEqual(res["violations"], [])

    def test_full_audit_reproducibility_and_h6_unidentifiability(self):
        audit = run_full_audit()
        self.assertEqual(
            audit["committed_report_uncompressed_sha256"],
            "1f8f5836b79a811c6413879823ca6f21f6def998b4944d72f46f6bd697412d91",
        )
        # Regret vs blind controls (B, C) on U at B=32 must be strongly negative (A beats B & C).
        u_b32_regret = audit["transfer_regret"]["U_b32"]
        self.assertLess(u_b32_regret["mean_regret_vs_blind_BC"], -0.80)
        # Agreement gate suppresses low-budget spurious N admissions on C_g/C2_g at B=16,
        # yet CANNOT detect identical-observation H6 terminal complementation once a unique
        # hypothesis survives (at B=64 A_g still has false accepts > 0).
        ag = audit["agreement_gate"]
        self.assertEqual(ag["N_false_admissions_by_budget"]["32"]["A_g"], 0)
        self.assertGreater(ag["drift_false_accepts_by_budget"]["64"]["A_g"], 0)


if __name__ == "__main__":
    unittest.main()
