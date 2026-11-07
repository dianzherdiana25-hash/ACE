"""Unit tests for ACE Repository Auditor commercial prototype."""
from __future__ import annotations

from pathlib import Path
import unittest

from ace_commercial.repo_auditor import ASTSecurityScanner, RepositoryAuditor
from ace_commercial import MARGINAL_COST_USD, SCHEMA, VERSION


class RepositoryAuditorTests(unittest.TestCase):

    def setUp(self):
        self.repo_root = Path(__file__).resolve().parents[2]
        self.auditor = RepositoryAuditor(self.repo_root)

    def test_ast_scanner_flags_eval_and_exec(self):
        import ast
        scanner = ASTSecurityScanner("unsafe_sample.py")
        code = "def foo():\n    eval('2+2')\n    exec('import os')\n"
        scanner.visit(ast.parse(code))
        self.assertEqual(len(scanner.findings), 2)
        self.assertTrue(all(f["severity"] == "CRITICAL" for f in scanner.findings))

    def test_ast_scanner_flags_dunder_introspection(self):
        import ast
        scanner = ASTSecurityScanner("introspection_sample.py")
        code = "def bar(obj):\n    return obj.__class__.__mro__\n"
        scanner.visit(ast.parse(code))
        self.assertTrue(len(scanner.findings) >= 2)
        targets = [f["target"] for f in scanner.findings]
        self.assertIn("__class__", targets)
        self.assertIn("__mro__", targets)

    def test_verify_cryptographic_evidence(self):
        res = self.auditor.verify_cryptographic_evidence()
        self.assertTrue(res["evidence_present"])
        self.assertTrue(res["total_artifacts"] > 0)
        self.assertTrue(res["all_valid"])

    def test_verify_upstream_pins(self):
        res = self.auditor.verify_upstream_pins()
        self.assertTrue(res["pinned_sources"])
        self.assertEqual(res["status"], "PASS")

    def test_full_audit_execution(self):
        audit = self.auditor.run_full_audit()
        self.assertEqual(audit["schema"], SCHEMA)
        self.assertEqual(audit["version"], VERSION)
        self.assertEqual(audit["marginal_cost_usd"], 0.00)
        self.assertGreaterEqual(audit["score"], 80)
        self.assertIn("A", audit["rating"])

    def test_generate_markdown_report(self):
        audit = self.auditor.run_full_audit()
        report = self.auditor.generate_markdown_report(audit)
        self.assertIn("ACE Repository Health & Cryptographic Evidence Audit Report", report)
        self.assertIn("Division of Responsibilities:", report)
        self.assertIn("ACE Autonomous Runtime (Deterministic Engine)", report)
        self.assertIn("Gemini Argon (External AI Assistant)", report)
        self.assertIn("Cryptographic Evidence Artifacts & State Verification", report)


if __name__ == "__main__":
    unittest.main()
