"""E2E Test Suite: Zero-Cost Governance and AI Provider Integration (Requirement 6).

4-Tier Systematic Verification:
Tier 1: Feature Coverage (execution budget accounting, query metering, capability permits)
Tier 2: Boundary & Corner Cases (budget exhaustion, unauthorized operation denial, invalid inputs)
Tier 3: Cross-Feature Interactions (advisor AST validation rejecting dangerous external code, zero-cost invariant)
Tier 4: Real-World Scenarios (graceful offline fallback to internal synthesis when AI provider is unavailable)
"""
from __future__ import annotations

from pathlib import Path
import sys
import unittest

# Ensure ACE/code is on sys.path
_CODE_DIR = Path(__file__).resolve().parent.parent.parent / "code"
if str(_CODE_DIR) not in sys.path:
    sys.path.insert(0, str(_CODE_DIR))

from ace_host_controller.budget_permits import (
    BudgetExceededError,
    CapabilityPermit,
    ExecutionBudget,
    PermitDeniedError,
)
from ace_code_agent.ai_advisor import MultiAIFleetAdvisor


class TestZeroCostGovernanceE2E(unittest.TestCase):
    """End-to-end verification of compute budget governance and zero-marginal-cost invariants."""

    # -------------------------------------------------------------------------
    # Tier 1: Feature Coverage (Happy Path)
    # -------------------------------------------------------------------------

    def test_tier1_execution_budget_tracks_time_and_queries(self):
        """Verify ExecutionBudget accurately meters consumed seconds and epistemic queries."""
        budget = ExecutionBudget(max_execution_seconds=60.0, max_queries=100, max_candidates=10)
        self.assertEqual(budget.remaining_seconds, 60.0)
        self.assertEqual(budget.remaining_queries, 100)

        budget.consume_time(12.5)
        budget.consume_queries(30)
        budget.record_candidate_eval()

        self.assertAlmostEqual(budget.used_seconds, 12.5, places=2)
        self.assertEqual(budget.used_queries, 30)
        self.assertEqual(budget.candidates_evaluated, 1)
        self.assertAlmostEqual(budget.remaining_seconds, 47.5, places=2)
        self.assertEqual(budget.remaining_queries, 70)

    def test_tier1_capability_permit_authorizes_granted_capabilities(self):
        """Verify CapabilityPermit authorizes explicitly listed operations without error."""
        permit = CapabilityPermit(allowed_capabilities=frozenset({"hypothesis_eval", "ast_inspect"}))
        permit.verify_capability("hypothesis_eval")
        permit.verify_capability("ast_inspect")

        permit_dict = permit.to_dict()
        self.assertIn("hypothesis_eval", permit_dict["allowed_capabilities"])
        self.assertFalse(permit_dict["allow_network"])
        self.assertFalse(permit_dict["allow_filesystem_write"])
        self.assertFalse(permit_dict["allow_shell_exec"])

    # -------------------------------------------------------------------------
    # Tier 2: Boundary & Corner Cases
    # -------------------------------------------------------------------------

    def test_tier2_budget_exhaustion_raises_budget_exceeded_error(self):
        """Verify exceeding query or candidate budget strictly raises BudgetExceededError."""
        budget = ExecutionBudget(max_execution_seconds=10.0, max_queries=5, max_candidates=2)
        budget.consume_queries(5)

        with self.assertRaises(BudgetExceededError) as ctx:
            budget.consume_queries(1)
        self.assertIn("Query budget exceeded", str(ctx.exception))

        budget.record_candidate_eval()
        budget.record_candidate_eval()
        with self.assertRaises(BudgetExceededError) as ctx:
            budget.record_candidate_eval()
        self.assertIn("Candidate evaluation limit exceeded", str(ctx.exception))

        with self.assertRaises(ValueError):
            budget.consume_time(-5.0)

        with self.assertRaises(ValueError):
            budget.consume_queries(-1)

    def test_tier2_unauthorized_operations_denied_by_default(self):
        """Verify CapabilityPermit strictly denies network, shell execution, and filesystem mutations."""
        permit = CapabilityPermit()  # Default: network=False, fs_write=False, shell_exec=False

        with self.assertRaises(PermitDeniedError) as ctx:
            permit.verify_operation("network")
        self.assertIn("Network access strictly denied", str(ctx.exception))

        with self.assertRaises(PermitDeniedError) as ctx:
            permit.verify_operation("fs_write")
        self.assertIn("Direct filesystem mutation strictly denied", str(ctx.exception))

        with self.assertRaises(PermitDeniedError) as ctx:
            permit.verify_operation("shell_exec")
        self.assertIn("Direct shell/subprocess execution strictly denied", str(ctx.exception))

        with self.assertRaises(PermitDeniedError) as ctx:
            permit.verify_capability("unauthorized_privilege")
        self.assertIn("not granted by permit", str(ctx.exception))

    # -------------------------------------------------------------------------
    # Tier 3: Cross-Feature Interactions
    # -------------------------------------------------------------------------

    def test_tier3_advisor_ast_validation_rejects_external_injection(self):
        """Verify MultiAIFleetAdvisor pure AST validator screens external AI snippets for dangerous constructs."""
        advisor = MultiAIFleetAdvisor()

        # 1. Clean mathematical code passes
        clean_code = "def custom_add(a: int, b: int) -> int:\n    return a + b\n"
        self.assertTrue(advisor.validate_pure_ast(clean_code))

        # 2. Injected imports or system calls fail
        unsafe_snippets = [
            "import os\ndef pwn(): pass",
            "from subprocess import run\ndef pwn(): pass",
            "def pwn():\n    return eval('1 + 1')",
            "def pwn():\n    return open('/etc/passwd').read()",
            "async def async_leak(): pass",
        ]
        for snippet in unsafe_snippets:
            with self.subTest(snippet=snippet):
                self.assertFalse(advisor.validate_pure_ast(snippet))

    def test_tier3_advisor_code_extraction(self):
        """Verify extraction of python code from markdown code fences or raw function definitions."""
        advisor = MultiAIFleetAdvisor()
        markdown_text = (
            "Here is the synthesized candidate:\n"
            "```python\n"
            "def candidate_rule(x: int) -> int:\n"
            "    return x % 3\n"
            "```\n"
            "Hope this works!"
        )
        extracted = advisor._extract_code(markdown_text)
        self.assertIsNotNone(extracted)
        self.assertIn("def candidate_rule", extracted)
        self.assertTrue(advisor.validate_pure_ast(extracted))

    # -------------------------------------------------------------------------
    # Tier 4: Real-World Scenarios
    # -------------------------------------------------------------------------

    def test_tier4_graceful_offline_fallback_preserves_zero_cost(self):
        """Verify MultiAIFleetAdvisor falls back gracefully to internal synthesis when ask-ai binary is absent."""
        fake_advisor = MultiAIFleetAdvisor(ask_ai_bin="/tmp/non_existent_ask_ai_binary")
        self.assertFalse(fake_advisor.is_available())

        # Consultation returns None safely without raising an unhandled exception or leaking cost
        res = fake_advisor.consult_code_patch(
            hypothesis_id="hyp_offline_01",
            hypothesis_statement="Test offline fallback.",
            strategy="COMPOSITE_DISPATCH",
            target_file="test.py",
            safe_id="hyp_offline_01",
            seed_val=42,
        )
        self.assertIsNone(res, "When external AI is unavailable, advisor must return None for internal fallback.")


if __name__ == "__main__":
    unittest.main()
