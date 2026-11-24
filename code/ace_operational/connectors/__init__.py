"""Isolated credential & browser-session connectors for ACE v3.

Secrets live only in host-local storage (`<workspace>/vault/`).
They are NEVER exposed over MCP read tools, AI prompts, memory, or git commits.
"""
from __future__ import annotations

from .vault import SecretVault, contains_secret_pattern, redact_secrets

__all__ = [
    "SecretVault",
    "contains_secret_pattern",
    "redact_secrets",
]
