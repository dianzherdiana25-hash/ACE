"""Public development benchmark for ACE FR-01 retrieval, not a sealed holdout.

Fixtures are deliberately identical to registered regression tasks. Run without
external AI; this does not demonstrate scientific generalization.
"""
from __future__ import annotations

import json
import resource
import time

from ace_code_agent.repo_retrieval import BoundedRepositoryRetriever
from ace_code_agent.test_repo_retrieval import TestBoundedRepositoryRetriever


def run() -> dict:
    total_start = time.perf_counter()
    fixture = TestBoundedRepositoryRetriever("test_preregistered_three_cases_recall_at_one")
    fixture.setUp()
    try:
        index = fixture.build()
        cases = [
            ("release_lock", "src/lease.py"),
            ("validate_owner", "src/checks.py"),
            ("handle_request", "src/router.py"),
        ]
        conditions = {}
        for mode in ("lexical", "structural", "hybrid"):
            start = time.perf_counter()
            outcomes = []
            for query, expected in cases:
                ranked = BoundedRepositoryRetriever.search(index, query, mode=mode, limit=3)
                paths = [entry["path"] for entry in ranked]
                outcomes.append({
                    "query": query,
                    "expected": expected,
                    "rank": (paths.index(expected) + 1) if expected in paths else None,
                    "top1": paths[0] if paths else None,
                })
            conditions[mode] = {
                "top1_correct": sum(x["rank"] == 1 for x in outcomes),
                "recall_at_3": sum(x["rank"] is not None for x in outcomes),
                "queries": len(cases),
                "query_wall_ms": round((time.perf_counter() - start) * 1000, 3),
                "outcomes": outcomes,
            }
        return {
            "schema": "ace.fr01.public.benchmark.v1",
            "evaluation": "PUBLIC_DEVELOPMENT_ONLY",
            "source_head": index["head"],
            "fixture_tasks": len(cases),
            "files_indexed": index["file_count"],
            "symbols_indexed": index["symbol_count"],
            "index_wall_ms": index["elapsed_ms"],
            "total_wall_ms": round((time.perf_counter() - total_start) * 1000, 3),
            "max_rss_linux_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            "conditions": conditions,
            "external_ai_calls": 0,
            "candidate_source_executed": False,
            "scientific_status": "NOT_ASSESSED",
            "release_gate": "BLOCK_RELEASE",
        }
    finally:
        fixture.tearDown()


if __name__ == "__main__":
    print(json.dumps(run(), sort_keys=True))
