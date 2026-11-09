"""ACE Real-World Capability Evolution Domain.

Brings autonomous program synthesis into practical production environments:
1. LogParserSynthesizer: High-throughput pure-Python structured log extractors.
2. SystemToolSynthesizer: POSIX-compliant, shell-injection-safe system automation utilities.
3. DataWranglerSynthesizer: Inductive input-output data transformers for JSON and CSV schemas.
4. GitAnalyzerSynthesizer: Repository churn, commit velocity, and hotspot analyzer.
5. ProcessSentinel: Linux /proc inspector auditing resource usage and zombie tasks on Termux.
6. NetClientSynthesizer: Resilient pure-Python HTTP client pipeline with exponential backoff.
7. RealWorldMissionIntegrator: Bridges real-world synthesis directly into ACE Mission Bus.
"""
from __future__ import annotations

from .log_parser_synth import LogParserSynthesizer, LogRule
from .system_tool_synth import SystemToolSynthesizer, CommandRule
from .data_wrangler_synth import DataWranglerSynthesizer, TransformRule
from .git_analyzer_synth import GitAnalyzerSynthesizer, ChurnRecord, CodebaseMetrics
from .process_sentinel import ProcessSentinel, ProcessReport
from .net_client_synth import NetClientSynthesizer, ClientRule
from .mission_integration import RealWorldMissionIntegrator

__all__ = [
    "LogParserSynthesizer",
    "LogRule",
    "SystemToolSynthesizer",
    "CommandRule",
    "DataWranglerSynthesizer",
    "TransformRule",
    "GitAnalyzerSynthesizer",
    "ChurnRecord",
    "CodebaseMetrics",
    "ProcessSentinel",
    "ProcessReport",
    "NetClientSynthesizer",
    "ClientRule",
    "RealWorldMissionIntegrator",
]
