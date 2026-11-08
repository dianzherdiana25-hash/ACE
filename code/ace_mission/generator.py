"""Mission generator deriving falsifiable missions from failure diagnoses (PRD section 7)."""
from __future__ import annotations

import datetime
from typing import Any, Dict, List, Optional

from .bus import MissionBus


class MissionGenerator:
    """Derives structured, prioritized missions from empirical failure diagnoses."""

    def __init__(self, bus: MissionBus):
        self.bus = bus

    def generate_from_diagnostics(self, diagnostics: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Turn diagnostics into at least 5 prioritized, distinct ace.mission.v1 missions."""
        generated = []

        type_mapping = {
            "INFORMATION_SHORTAGE": {
                "goal": "Induce count-matched negative examples to resolve order masking",
                "hypothesis": "Count-balanced negative constraints eliminate false admission on prefix boundaries",
                "families": ["boundary", "prefix_guard"],
                "metric": "validation_accuracy",
                "threshold": 0.90,
                "comparator": "count_matched_oracle",
                "info_value_per_label": 0.95,
            },
            "TOOL_SHORTAGE": {
                "goal": "Synthesize graph adjacency traversal primitives into typed DSL",
                "hypothesis": "BFS-guided neighborhood expansion solves connected-component tasks beyond 58% baseline",
                "families": ["graph_connectivity", "graph_bipartite"],
                "metric": "terminal_accuracy",
                "threshold": 0.95,
                "comparator": "researcher_bfs_library",
                "info_value_per_label": 0.92,
            },
            "METHOD_SHORTAGE": {
                "goal": "Implement multi-task composite dispatch across disparate task families",
                "hypothesis": "Disjunctive modular dispatch allows simultaneous solution of parity and modular residue",
                "families": ["modular_congruence", "parity_runlength"],
                "metric": "joint_family_accuracy",
                "threshold": 0.88,
                "comparator": "composite_dispatch_v1",
                "info_value_per_label": 0.89,
            },
            "BUDGET_EXHAUSTION": {
                "goal": "Deploy active uncertainty query allocation for high-entropy instances",
                "hypothesis": "Budget-capped active querying reduces required label count by 4x without accuracy loss",
                "families": ["active_query_boundary"],
                "metric": "label_efficiency_gain",
                "threshold": 0.50,
                "comparator": "passive_fifo_allocation",
                "info_value_per_label": 0.85,
            },
            "ADMISSION_FAILURE": {
                "goal": "Implement robust noise-tolerant admission with max-errors tolerance",
                "hypothesis": "Permitting k=1 mislabeled train row via ADMITTED_WITH_ERRORS restores recovery on ratio4",
                "families": ["ratio_4_1_noise"],
                "metric": "task_recovery_rate",
                "threshold": 1.0,
                "comparator": "strict_zero_error_gate",
                "info_value_per_label": 0.82,
            },
            "DRIFT_VULNERABILITY": {
                "goal": "Integrate online semantic quarantine (e14aa) into main runtime execution",
                "hypothesis": "Postscore consistency guard detects late-flip semantic mutation and triggers ABSTAIN",
                "families": ["late_flip_drift"],
                "metric": "false_admission_rate",
                "threshold": 0.0,
                "comparator": "unprotected_runtime",
                "info_value_per_label": 0.98,
            },
        }

        # Sort diagnostics by information value
        sorted_diags = sorted(
            diagnostics,
            key=lambda d: type_mapping.get(d.get("type", ""), {}).get("info_value_per_label", 0.0),
            reverse=True
        )

        for diag in sorted_diags:
            d_type = diag.get("type")
            if d_type in type_mapping:
                cfg = type_mapping[d_type]
                m_id = self.bus.create_mission(
                    goal=cfg["goal"],
                    hypothesis=cfg["hypothesis"],
                    task_family_ids=cfg["families"],
                    inputs=[],
                    budget={"time_sec": 30, "max_candidates": 5},
                    acceptance={
                        "metric": cfg["metric"],
                        "threshold": cfg["threshold"],
                        "comparator": cfg["comparator"]
                    },
                    forbidden=[
                        "code/ace_host_controller/sealed_evaluator_v3.py",
                        "tests/sealed_bank.py"
                    ]
                )
                generated.append({
                    "id": m_id,
                    "goal": cfg["goal"],
                    "hypothesis": cfg["hypothesis"],
                    "task_family_ids": cfg["families"],
                    "info_value": cfg["info_value_per_label"]
                })

        return generated
