"""ACE Real-World Capability Evolution Domain.

Brings autonomous program synthesis into practical production environments:
1. LogParserSynthesizer: High-throughput pure-Python structured log extractors.
2. SystemToolSynthesizer: POSIX-compliant, shell-injection-safe system automation utilities.
3. DataWranglerSynthesizer: Inductive input-output data transformers for JSON and CSV schemas.
"""
from __future__ import annotations

from .log_parser_synth import LogParserSynthesizer, LogRule
from .system_tool_synth import SystemToolSynthesizer, CommandRule
from .data_wrangler_synth import DataWranglerSynthesizer, TransformRule

__all__ = [
    "LogParserSynthesizer",
    "LogRule",
    "SystemToolSynthesizer",
    "CommandRule",
    "DataWranglerSynthesizer",
    "TransformRule",
]
