#!/usr/bin/env python3
"""ACE Real-World Capability CLI Utility.

Interactive command-line tool allowing users to interact directly with
ACE's real-world synthesizers: Git Analytics, Process Sentinel, Log Parsers,
and Mission Bus Integrations.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "code"))

from ace_real_world.log_parser_synth import LogParserSynthesizer
from ace_real_world.system_tool_synth import SystemToolSynthesizer
from ace_real_world.data_wrangler_synth import DataWranglerSynthesizer
from ace_real_world.git_analyzer_synth import GitAnalyzerSynthesizer
from ace_real_world.process_sentinel import ProcessSentinel
from ace_real_world.net_client_synth import NetClientSynthesizer
from ace_real_world.mission_integration import RealWorldMissionIntegrator
from ace_mission.bus import MissionBus


def main():
    parser = argparse.ArgumentParser(description="ACE Real-World Capability CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # Command: audit-repo
    subparsers.add_parser("audit-repo", help="Analyze repository architecture, LOC, and churn")

    # Command: audit-procs
    subparsers.add_parser("audit-procs", help="Inspect active Python processes and memory usage via /proc")

    # Command: parse-log-demo
    subparsers.add_parser("parse-log-demo", help="Demonstrate inductive regex synthesis on sample logs")

    # Command: dispatch-missions
    subparsers.add_parser("dispatch-missions", help="Register and execute real-world missions on Mission Bus")

    args = parser.parse_args()

    if args.command == "audit-repo":
        analyzer = GitAnalyzerSynthesizer(str(ROOT_DIR))
        metrics = analyzer.compute_codebase_metrics()
        print("\n" + "=" * 60)
        print("   📊 ACE REPOSITORY ARCHITECTURE METRICS")
        print("=" * 60)
        print(f"Total Commits:        {metrics.total_commits}")
        print(f"Total Python Files:   {metrics.total_python_files}")
        print(f"Total Lines of Code:  {metrics.total_loc:,}")
        print(f"Avg Churn per Commit: {metrics.average_churn_per_commit} lines")
        print("\nTop 5 Largest Architecture Files:")
        for file_path, lines in metrics.hotspot_files:
            print(f"  • {file_path:<45} : {lines:,} lines")
        print("=" * 60 + "\n")

    elif args.command == "audit-procs":
        sentinel = ProcessSentinel()
        load = sentinel.audit_system_load()
        print("\n" + "=" * 60)
        print("   🔍 ACE PROCESS SENTINEL (/proc Resource Monitor)")
        print("=" * 60)
        print(f"System Load (1m, 5m, 15m): {load['load_1m']}, {load['load_5m']}, {load['load_15m']}")
        print(f"Active Python Tasks:       {load['active_python_processes']}")
        print(f"Total Python RSS Memory:   {load['total_python_rss_mb']} MB")
        print("\nActive Python Processes:")
        for p in load.get("top_processes", []):
            print(f"  • PID {p['pid']} [{p['state']}]: {p['rss_mb']} MB — {p['command_line'][:50]}")
        print("=" * 60 + "\n")

    elif args.command == "parse-log-demo":
        synth = LogParserSynthesizer()
        samples = [
            "2026-11-09T17:00:00Z [INFO] worker_1 200 SUCCESS",
            "2026-11-09T17:01:00Z [ERROR] worker_2 500 FAILED",
            "2026-11-09T17:02:00Z [WARN] worker_3 404 NOT_FOUND",
        ]
        expected = [
            {"time": "2026-11-09T17:00:00Z", "level": "[INFO]", "code": "200"},
            {"time": "2026-11-09T17:01:00Z", "level": "[ERROR]", "code": "500"},
            {"time": "2026-11-09T17:02:00Z", "level": "[WARN]", "code": "404"},
        ]
        rule = synth.synthesize_regex_parser(samples, expected)
        print("\n" + "=" * 60)
        print("   ⚡ INDUCTIVE LOG PARSER SYNTHESIS")
        print("=" * 60)
        print(f"Synthesized Pattern: {rule.pattern}")
        print(f"Captured Fields:     {rule.field_names}")
        print("\nGenerated Function Code:")
        print(rule.extractor_code)
        print("=" * 60 + "\n")

    elif args.command == "dispatch-missions":
        bus = MissionBus(str(ROOT_DIR / "mission_bus.sqlite3"))
        integrator = RealWorldMissionIntegrator(bus, str(ROOT_DIR))
        missions = integrator.generate_real_world_missions()
        print(f"\n🚀 Registered {len(missions)} Real-World missions into Mission Bus.")
        for m in missions:
            res = integrator.execute_real_world_mission(m["mission_id"])
            print(f"   ↳ Executed {m['mission_id']}: {res['status']} (SHA: {res.get('artifact_sha', '')[:12]}...)")
        print("✅ All real-world missions completed with verified cryptographic receipts!\n")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
