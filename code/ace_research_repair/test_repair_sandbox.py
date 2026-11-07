"""Adversarial security and isolation tests for repair candidate execution sandbox."""
from __future__ import annotations

import unittest

from .corpus import DevTestCase
from .sandbox import (
    TrustBoundary,
    audit_candidate_ast,
    is_os_sandbox_available,
    run_dev_suite,
)


class SandboxSecurityTests(unittest.TestCase):
    def test_untrusted_candidate_blocked_without_os_sandbox(self) -> None:
        """Untrusted candidates must be fail-closed (BLOCKED_ENVIRONMENT) when real OS sandbox is absent."""
        source = "def solve(x):\n    return x + 1\n"
        cases = (DevTestCase("t1", "call", (1,), 2),)

        os_avail, _ = is_os_sandbox_available()
        res = run_dev_suite(
            source,
            "solve",
            cases,
            trust_level=TrustBoundary.UNTRUSTED_CANDIDATE,
        )

        if not os_avail:
            self.assertTrue(res.get("blocked_environment"))
            self.assertEqual(res.get("status"), "BLOCKED_ENVIRONMENT")
            self.assertEqual(res.get("compile_error"), "BLOCKED_ENVIRONMENT")
            self.assertFalse(res.get("all_passed"))
        else:
            self.assertTrue(res.get("all_passed"))

    def test_trusted_fixture_allowed_and_executed(self) -> None:
        """Trusted fixed-fixture diagnostics remain functional under strict subprocess containment."""
        source = "def solve(x):\n    return x * 2\n"
        cases = (DevTestCase("t1", "call", (3,), 6),)
        res = run_dev_suite(
            source,
            "solve",
            cases,
            trust_level=TrustBoundary.TRUSTED_FIXTURE,
        )
        self.assertTrue(res["all_passed"])
        self.assertFalse(res.get("blocked_environment", False))

    def test_closed_ast_mutation_allowed(self) -> None:
        """Closed AST candidate mutations from internal operators execute within subprocess sandbox."""
        source = "def solve(x):\n    return x - 1\n"
        cases = (DevTestCase("t1", "call", (5,), 4),)
        res = run_dev_suite(
            source,
            "solve",
            cases,
            trust_level=TrustBoundary.CLOSED_AST_MUTATION,
        )
        self.assertTrue(res["all_passed"])

    def test_ast_deny_by_default_blocks_socket_and_network(self) -> None:
        """Network imports (socket, urllib, requests) are blocked at AST level before subprocess execution."""
        payloads = [
            "import socket\ndef solve(x):\n    return x\n",
            "from socket import create_connection\ndef solve(x):\n    return x\n",
            "import urllib.request\ndef solve(x):\n    return x\n",
        ]
        for src in payloads:
            ast_ok, err = audit_candidate_ast(src)
            self.assertFalse(ast_ok)
            self.assertIn("Forbidden", str(err))

            res = run_dev_suite(src, "solve", (DevTestCase("t1", "call", (1,), 1),))
            self.assertFalse(res["all_passed"])
            self.assertIn("AST_SECURITY_VIOLATION", res.get("sandbox_error", ""))

    def test_ast_deny_by_default_blocks_subprocess_and_os(self) -> None:
        """Process execution / OS imports (os, subprocess, shutil, ctypes) are blocked at AST level."""
        payloads = [
            "import os\ndef solve(x):\n    return os.getpid()\n",
            "import subprocess\ndef solve(x):\n    return 0\n",
            "import ctypes\ndef solve(x):\n    return 0\n",
            "import shutil\ndef solve(x):\n    return 0\n",
        ]
        for src in payloads:
            ast_ok, err = audit_candidate_ast(src)
            self.assertFalse(ast_ok)
            self.assertIn("Forbidden", str(err))

            res = run_dev_suite(src, "solve", (DevTestCase("t1", "call", (1,), 1),))
            self.assertFalse(res["all_passed"])
            self.assertIn("AST_SECURITY_VIOLATION", res.get("sandbox_error", ""))

    def test_ast_deny_by_default_blocks_dynamic_execution_and_file_io(self) -> None:
        """Calls to eval, exec, compile, open, globals, locals are blocked at AST level."""
        payloads = [
            "def solve(x):\n    return eval('x + 1')\n",
            "def solve(x):\n    exec('x = 2')\n    return x\n",
            "def solve(x):\n    return open('/etc/passwd').read()\n",
            "def solve(x):\n    return globals()\n",
        ]
        for src in payloads:
            ast_ok, err = audit_candidate_ast(src)
            self.assertFalse(ast_ok)
            self.assertIn("Forbidden", str(err))

            res = run_dev_suite(src, "solve", (DevTestCase("t1", "call", (1,), 1),))
            self.assertFalse(res["all_passed"])
            self.assertIn("AST_SECURITY_VIOLATION", res.get("sandbox_error", ""))

    def test_ast_deny_by_default_blocks_dunder_introspection_escape(self) -> None:
        """Attempts to access __subclasses__, __globals__, or __builtins__ are blocked at AST level."""
        src = "def solve(x):\n    return ().__class__.__bases__[0].__subclasses__()\n"
        ast_ok, err = audit_candidate_ast(src)
        self.assertFalse(ast_ok)
        self.assertIn("ForbiddenAttribute", str(err))

        res = run_dev_suite(src, "solve", (DevTestCase("t1", "call", (1,), 1),))
        self.assertFalse(res["all_passed"])
        self.assertIn("AST_SECURITY_VIOLATION", res.get("sandbox_error", ""))

    def test_cpu_and_wall_timeout_terminates_infinite_loop(self) -> None:
        """Infinite loop candidate is terminated cleanly without parent process interruption."""
        hang_src = "def hang(x):\n    while True:\n        x = x + 1\n    return x\n"
        res = run_dev_suite(
            hang_src,
            "hang",
            (DevTestCase("t1", "call", (1,), 2),),
            timeout_sec=0.5,
            cpu_limit_sec=1,
            trust_level=TrustBoundary.TRUSTED_FIXTURE,
        )
        self.assertFalse(res["all_passed"])
        self.assertTrue(res["timed_out"] or res.get("sandbox_error") is not None)

    def test_child_crash_isolated(self) -> None:
        """Child hard crash (SystemExit) is isolated from parent test runner."""
        crash_src = "import sys\ndef boom(x):\n    sys.exit(42)\n"
        res = run_dev_suite(
            crash_src,
            "boom",
            (DevTestCase("t1", "call", (1,), 2),),
            timeout_sec=1.5,
            cpu_limit_sec=1,
            trust_level=TrustBoundary.TRUSTED_FIXTURE,
        )
        self.assertFalse(res["all_passed"])
        self.assertEqual(res["cases"][0]["exception_type"], "SystemExit")


if __name__ == "__main__":
    unittest.main()
