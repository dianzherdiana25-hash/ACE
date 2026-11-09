"""System tool and shell command synthesizer with strict security validation.

Generates hardened, POSIX-compliant execution helpers and sanitizers
that prevent shell injection and path traversal vulnerabilities.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
import shlex
from typing import Any, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class CommandRule:
    rule_id: str
    command_template: str
    allowed_args: Tuple[str, ...]
    sanitizer_code: str


class SystemToolSynthesizer:
    """Synthesizes secure shell pipeline wrappers and environment monitors."""

    def __init__(self):
        self.rules: Dict[str, CommandRule] = {}

    def synthesize_safe_executor(
        self,
        base_command: str,
        expected_arg_types: Dict[str, str],
        func_name: str = "safe_execute_command",
    ) -> CommandRule:
        """Synthesize a hardened subprocess wrapper that disallows shell metacharacters."""
        # Clean base command
        safe_base = shlex.split(base_command)
        if not safe_base:
            raise ValueError("Base command cannot be empty")

        code = (
            f"import shlex\n"
            f"import subprocess\n"
            f"from typing import List, Dict, Any, Optional\n\n"
            f"FORBIDDEN_METACHARS = set(';|&><$`\\n\\r')\n\n"
            f"def {func_name}(args: Dict[str, str], timeout_seconds: float = 10.0) -> subprocess.CompletedProcess:\n"
            f"    # 1. Validate against shell metacharacters\n"
            f"    cmd_parts = {repr(safe_base)}.copy()\n"
            f"    for k, v in args.items():\n"
            f"        if any(c in v for c in FORBIDDEN_METACHARS):\n"
            f"            raise ValueError(f'Security alert: parameter {{k}} contains forbidden characters: {{v!r}}')\n"
            f"        cmd_parts.extend(['--' + k, v] if len(k) > 1 else ['-' + k, v])\n"
            f"    # 2. Execute directly via execve without shell=True\n"
            f"    return subprocess.run(cmd_parts, capture_output=True, text=True, timeout=timeout_seconds, check=False)\n"
        )

        rule = CommandRule(
            rule_id=f"rule_cmd_{len(self.rules) + 1}",
            command_template=" ".join(safe_base),
            allowed_args=tuple(expected_arg_types.keys()),
            sanitizer_code=code,
        )
        self.rules[rule.rule_id] = rule
        return rule

    def synthesize_path_sanitizer(
        self,
        allowed_root: str,
        func_name: str = "sanitize_workspace_path",
    ) -> str:
        """Synthesize an absolute path traversal guard ensuring paths stay within allowed root."""
        return (
            f"from pathlib import Path\n\n"
            f"def {func_name}(user_path: str) -> Path:\n"
            f"    root = Path({repr(allowed_root)}).resolve()\n"
            f"    target = (root / user_path).resolve()\n"
            f"    if root not in target.parents and target != root:\n"
            f"        raise PermissionError(f'Path traversal blocked: {{target}} is outside {{root}}')\n"
            f"    return target\n"
        )
