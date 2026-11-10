"""E2E Test Suite: Sandbox AST Security Gate and Containment (Requirement 2).

4-Tier Systematic Verification:
Tier 1: Feature Coverage (happy-path pure mathematical AST validation)
Tier 2: Boundary & Corner Cases (reflection escapes, forbidden calls/modules, max node limits, syntax errors)
Tier 3: Cross-Feature Interactions (mechanism spec audit with embedded code, fail-closed enforcement)
Tier 4: Real-World Scenarios (containment check failing closed with BLOCKED_ENVIRONMENT in unconfined OS)
"""
from __future__ import annotations

from pathlib import Path
import sys
import unittest

# Ensure ACE/code is on sys.path
_CODE_DIR = Path(__file__).resolve().parent.parent.parent / "code"
if str(_CODE_DIR) not in sys.path:
    sys.path.insert(0, str(_CODE_DIR))

from ace_host_controller.sandbox_gate import (
    GateResult,
    HostSandboxGate,
    SandboxSecurityError,
)


class TestSandboxASTGateE2E(unittest.TestCase):
    """End-to-end verification of static AST auditing and environment containment."""

    def setUp(self):
        self.gate = HostSandboxGate(
            max_ast_nodes=100,
            enforce_os_containment=True,
            strict_ast_only=True,
        )

    # -------------------------------------------------------------------------
    # Tier 1: Feature Coverage (Happy Path)
    # -------------------------------------------------------------------------

    def test_tier1_pure_mathematical_function_passes_audit(self):
        """Verify that pure mathematical and arithmetic candidate AST passes security audit."""
        clean_code = (
            "def candidate_predicate(length: int, density: int, stride_val: int) -> int:\n"
            "    val = (length * 3 + density) % 7\n"
            "    if val > stride_val:\n"
            "        return 1\n"
            "    return 0\n"
        )
        res = self.gate.audit_ast(clean_code)
        self.assertTrue(res.allowed)
        self.assertEqual(res.reason, "AST_AUDIT_PASSED")
        self.assertEqual(len(res.violations), 0)
        # Verify enforce() succeeds without raising exception
        res.enforce()

    def test_tier1_valid_mechanism_spec_passes_audit(self):
        """Verify declarative mechanism specification dictionary passes audit."""
        spec = {
            "schema": "ace.mechanism.v1",
            "candidate_id": "cand_pure_arithmetic_01",
            "parent_id": "G0_root",
            "generation": 1,
            "rules": ["length % 2 == 0", "density > 10"],
            "features": ["length", "density"],
            "source_code": "def evaluate(l: int) -> int:\n    return l * 2\n",
            "description": "Pure arithmetic doubling rule",
        }
        res = self.gate.audit_mechanism_spec(spec)
        self.assertTrue(res.allowed)
        self.assertEqual(res.reason, "SPEC_AUDIT_PASSED")
        res.enforce()

    # -------------------------------------------------------------------------
    # Tier 2: Boundary & Corner Cases (Attack Vectors & Malicious AST)
    # -------------------------------------------------------------------------

    def test_tier2_rejects_forbidden_module_imports(self):
        """Verify that importing forbidden OS, network, or introspection modules is blocked."""
        malicious_snippets = [
            "import os\nos.system('echo pwned')",
            "import sys\nsys.exit(0)",
            "import subprocess\nsubprocess.run(['ls'])",
            "import socket\ns = socket.socket()",
            "import importlib\nmod = importlib.import_module('os')",
            "from ctypes import c_int",
            "from posix import abort",
            "import gc\ngc.get_objects()",
            "import inspect\ninspect.stack()",
            "import shutil\nshutil.rmtree('/')",
        ]
        for snippet in malicious_snippets:
            with self.subTest(snippet=snippet):
                res = self.gate.audit_ast(snippet)
                self.assertFalse(res.allowed)
                self.assertEqual(res.reason, "FORBIDDEN_AST_CONSTRUCTS")
                self.assertTrue(any("Forbidden import" in v for v in res.violations))
                with self.assertRaises(SandboxSecurityError):
                    res.enforce()

    def test_tier2_rejects_forbidden_builtin_calls(self):
        """Verify that invoking dangerous builtins like eval, exec, open is strictly blocked."""
        dangerous_calls = [
            "x = eval('2 + 2')",
            "exec('a = 1')",
            "f = open('/data/data/com.termux/files/home/test.txt', 'w')",
            "c = compile('print(1)', '<string>', 'exec')",
            "g = globals()",
            "l = locals()",
            "imp = __import__('os')",
            "exit(1)",
            "quit()",
        ]
        for snippet in dangerous_calls:
            with self.subTest(snippet=snippet):
                res = self.gate.audit_ast(snippet)
                self.assertFalse(res.allowed)
                self.assertEqual(res.reason, "FORBIDDEN_AST_CONSTRUCTS")
                self.assertTrue(any("Forbidden function call" in v for v in res.violations))
                with self.assertRaises(SandboxSecurityError):
                    res.enforce()

    def test_tier2_rejects_reflection_and_dunder_attribute_traversals(self):
        """Verify that reflection escapes like __subclasses__, __globals__, __code__ are blocked."""
        reflection_attacks = [
            "classes = ().__class__.__subclasses__()",
            "bases = int.__class__.__bases__",
            "mro = object.__mro__",
            "g = (lambda: None).__globals__",
            "c = (lambda: None).__code__",
            "b = (lambda: None).__builtins__",
            "cl = (lambda: None).__closure__",
        ]
        for snippet in reflection_attacks:
            with self.subTest(snippet=snippet):
                res = self.gate.audit_ast(snippet)
                self.assertFalse(res.allowed)
                self.assertEqual(res.reason, "FORBIDDEN_AST_CONSTRUCTS")
                self.assertTrue(any("Forbidden attribute access" in v for v in res.violations))
                with self.assertRaises(SandboxSecurityError):
                    res.enforce()

    def test_tier2_rejects_ast_node_budget_exhaustion(self):
        """Verify that deeply nested or bloated AST trees exceeding node budget are blocked."""
        gate_strict = HostSandboxGate(max_ast_nodes=15)
        bloated_code = "a = 1 + 2 + 3 + 4 + 5 + 6 + 7 + 8 + 9 + 10 + 11 + 12 + 13 + 14 + 15"
        res = gate_strict.audit_ast(bloated_code)
        self.assertFalse(res.allowed)
        self.assertTrue(any("exceeds maximum" in v for v in res.violations))

    def test_tier2_syntax_error_fails_safely_without_crash(self):
        """Verify that invalid Python syntax fails gracefully with SYNTAX_ERROR."""
        invalid_code = "def incomplete_func(:"
        res = self.gate.audit_ast(invalid_code)
        self.assertFalse(res.allowed)
        self.assertEqual(res.reason, "SYNTAX_ERROR")
        self.assertTrue(any("Parse failure" in v for v in res.violations))

    # -------------------------------------------------------------------------
    # Tier 3: Cross-Feature Interactions
    # -------------------------------------------------------------------------

    def test_tier3_spec_with_embedded_malicious_source_is_blocked(self):
        """Verify mechanism spec embedding hidden malicious code in source_code is rejected."""
        trojan_spec = {
            "schema": "ace.mechanism.v1",
            "candidate_id": "trojan_cand_01",
            "parent_id": "G0_root",
            "rules": ["x > 0"],
            "source_code": "import subprocess\nsubprocess.call(['rm', '-rf', '/'])",
        }
        res = self.gate.audit_mechanism_spec(trojan_spec)
        self.assertFalse(res.allowed)
        self.assertEqual(res.reason, "SPEC_AUDIT_FAILED")
        self.assertTrue(any("Forbidden import 'subprocess'" in v for v in res.violations))
        with self.assertRaises(SandboxSecurityError):
            res.enforce()

    def test_tier3_spec_with_unauthorized_keys_is_rejected(self):
        """Verify mechanism spec with unknown or injection keys is rejected."""
        injection_spec = {
            "schema": "ace.mechanism.v1",
            "candidate_id": "cand_01",
            "parent_id": "G0_root",
            "unauthorized_privileged_override": True,
            "shell_payload": "echo hacked",
        }
        res = self.gate.audit_mechanism_spec(injection_spec)
        self.assertFalse(res.allowed)
        self.assertEqual(res.reason, "SPEC_AUDIT_FAILED")
        self.assertTrue(any("Unknown specification keys" in v for v in res.violations))

    # -------------------------------------------------------------------------
    # Tier 4: Real-World Scenarios
    # -------------------------------------------------------------------------

    def test_tier4_host_environment_containment_fails_closed(self):
        """Verify that in unconfined environments lacking genuine OS containers, check returns BLOCKED_ENVIRONMENT."""
        containment_res = self.gate.check_environment_containment()
        # In standard Termux Linux without bwrap/namespaces, this must fail closed
        if not containment_res.allowed:
            self.assertEqual(containment_res.reason, "BLOCKED_ENVIRONMENT")
            self.assertTrue(any("untrusted candidate execution blocked" in v for v in containment_res.violations))
            with self.assertRaises(SandboxSecurityError):
                containment_res.enforce()
        else:
            # If running in a certified sealed container, reason must reflect verified sealing
            self.assertTrue("CONTAINMENT_VERIFIED" in containment_res.reason)


if __name__ == "__main__":
    unittest.main()
