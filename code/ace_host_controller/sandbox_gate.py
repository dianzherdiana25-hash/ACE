"""Sandbox isolation and security gate for ACE Host Controller.

Enforces fail-closed BLOCKED_ENVIRONMENT if candidates attempt uncontained OS execution,
dangerous AST operations, network calls, filesystem mutations, or reflection escapes.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass, field
import os
from typing import Any, Optional


class SandboxSecurityError(PermissionError):
    """Raised when candidate code violates sandbox isolation or security policies."""


@dataclass(frozen=True)
class GateResult:
    """Result of sandbox audit."""

    allowed: bool
    reason: str
    violations: list[str] = field(default_factory=list)

    def enforce(self) -> None:
        """Raise SandboxSecurityError if audit failed."""
        if not self.allowed:
            raise SandboxSecurityError(
                f"{self.reason}: {', '.join(self.violations) if self.violations else 'disallowed'}"
            )


class HostSandboxGate:
    """Security gate auditing candidate code and execution environment."""

    FORBIDDEN_MODULES = frozenset({
        "os",
        "sys",
        "subprocess",
        "shutil",
        "socket",
        "urllib",
        "requests",
        "http",
        "ftplib",
        "ctypes",
        "pty",
        "multiprocessing",
        "threading",
        "asyncio",
        "posix",
        "nt",
        "winreg",
        "pickle",
        "shelve",
        "marshal",
        "gc",
        "inspect",
        "traceback",
        "linecache",
        "pdb",
        "importlib",
    })

    FORBIDDEN_CALLS = frozenset({
        "eval",
        "exec",
        "__import__",
        "open",
        "compile",
        "globals",
        "locals",
        "vars",
        "dir",
        "input",
        "breakpoint",
        "exit",
        "quit",
    })

    FORBIDDEN_ATTRS = frozenset({
        "__subclasses__",
        "__bases__",
        "__mro__",
        "__globals__",
        "__code__",
        "__builtins__",
        "__closure__",
    })

    def __init__(
        self,
        max_ast_nodes: int = 5000,
        enforce_os_containment: bool = True,
        strict_ast_only: bool = True,
    ):
        self.max_ast_nodes = max_ast_nodes
        self.enforce_os_containment = enforce_os_containment
        self.strict_ast_only = strict_ast_only

    def check_environment_containment(self) -> GateResult:
        """Verify whether the host environment provides certified OS-level isolation.
        
        If standard subprocess execution is unconfined (no container cgroup/seccomp/bwrap),
        this fails closed with BLOCKED_ENVIRONMENT.
        """
        if not self.enforce_os_containment:
            return GateResult(allowed=True, reason="CONTAINMENT_BYPASS_FOR_TESTING")

        # In standard unprivileged Linux process without bwrap/seccomp sandbox,
        # executing raw untrusted code is unconfined.
        has_bwrap = os.path.exists("/usr/bin/bwrap")
        has_docker = os.path.exists("/.dockerenv")
        has_bubblewrap = os.path.exists("/usr/bin/bubblewrap")
        
        # If in a non-containerized standard user environment running uncontained code:
        # We enforce AST-only safe execution or fail closed.
        if not (has_bwrap or has_docker or has_bubblewrap):
            return GateResult(
                allowed=False,
                reason="BLOCKED_ENVIRONMENT",
                violations=["No OS sandbox (bwrap/seccomp/container) found for untrusted raw process execution"],
            )
        return GateResult(allowed=True, reason="CONTAINMENT_VERIFIED")

    def audit_ast(self, code_str: str) -> GateResult:
        """Audit candidate Python code AST for unsafe imports, calls, or attribute traversals."""
        violations: list[str] = []

        try:
            tree = ast.parse(code_str)
        except SyntaxError as exc:
            return GateResult(
                allowed=False,
                reason="SYNTAX_ERROR",
                violations=[f"Parse failure: {exc}"],
            )

        node_count = sum(1 for _ in ast.walk(tree))
        if node_count > self.max_ast_nodes:
            violations.append(
                f"AST node count {node_count} exceeds maximum {self.max_ast_nodes}"
            )

        for node in ast.walk(tree):
            # Check imports
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root_mod = alias.name.split(".")[0]
                    if root_mod in self.FORBIDDEN_MODULES:
                        violations.append(f"Forbidden import '{alias.name}'")
            elif isinstance(node, ast.ImportFrom):
                mod = (node.module or "").split(".")[0]
                if mod in self.FORBIDDEN_MODULES:
                    violations.append(f"Forbidden import from '{node.module}'")

            # Check calls
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id in self.FORBIDDEN_CALLS:
                    violations.append(f"Forbidden function call '{node.func.id}()'")

            # Check attribute access
            elif isinstance(node, ast.Attribute):
                if node.attr in self.FORBIDDEN_ATTRS:
                    violations.append(f"Forbidden attribute access '{node.attr}'")

        if violations:
            return GateResult(
                allowed=False,
                reason="FORBIDDEN_AST_CONSTRUCTS",
                violations=violations,
            )
        return GateResult(allowed=True, reason="AST_AUDIT_PASSED")

    def audit_mechanism_spec(self, spec: dict[str, Any]) -> GateResult:
        """Audit declarative candidate mechanism specification dictionary."""
        violations: list[str] = []
        if not isinstance(spec, dict):
            return GateResult(
                allowed=False,
                reason="INVALID_SPEC_TYPE",
                violations=["Specification must be a dictionary"],
            )

        allowed_keys = {
            "schema",
            "candidate_id",
            "parent_id",
            "generation",
            "rules",
            "features",
            "weights",
            "hyperparameters",
            "source_code",
            "description",
        }
        unknown_keys = set(spec.keys()) - allowed_keys
        if unknown_keys:
            violations.append(f"Unknown specification keys: {sorted(unknown_keys)}")

        # If source_code is present, audit its AST
        if "source_code" in spec and isinstance(spec["source_code"], str):
            ast_res = self.audit_ast(spec["source_code"])
            if not ast_res.allowed:
                violations.extend(ast_res.violations)

        if violations:
            return GateResult(
                allowed=False,
                reason="SPEC_AUDIT_FAILED",
                violations=violations,
            )
        return GateResult(allowed=True, reason="SPEC_AUDIT_PASSED")
