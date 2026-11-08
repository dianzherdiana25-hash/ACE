"""Codebase Reader & Failure History Analyzer.

Enables ACE to inspect its own source code, parse AST structures,
and analyze empirical failure logs without human prompting.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


class CodebaseReader:
    """Reads repository source code and analyzes persistent failure histories."""

    def __init__(self, repo_root: Optional[Path] = None):
        if repo_root is None:
            self.repo_root = Path(__file__).resolve().parent.parent.parent
        else:
            self.repo_root = Path(repo_root)

    def scan_python_modules(self, subpackage: str = "code/ace_self_dev") -> Dict[str, Dict[str, Any]]:
        """Parse Python files in a target directory and extract AST metadata."""
        target_dir = self.repo_root / subpackage
        results: Dict[str, Dict[str, Any]] = {}

        if not target_dir.exists():
            return results

        for py_path in sorted(target_dir.rglob("*.py")):
            rel_path = str(py_path.relative_to(self.repo_root))
            try:
                content = py_path.read_text(encoding="utf-8")
                tree = ast.parse(content)
                classes = [n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
                functions = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
                results[rel_path] = {
                    "classes": classes,
                    "functions": functions,
                    "line_count": len(content.splitlines()),
                    "ast_valid": True,
                }
            except Exception as e:
                results[rel_path] = {
                    "classes": [],
                    "functions": [],
                    "line_count": 0,
                    "ast_valid": False,
                    "parse_error": str(e),
                }

        return results

    def read_failure_history(self, state_file: str = "checkpoints/self_dev/research_state.json") -> Dict[str, Any]:
        """Read and aggregate historical failure data from persistent research state."""
        full_path = self.repo_root / state_file
        diagnostics = {
            "cycle_count": 0,
            "total_rejections": 0,
            "stagnation_events": 0,
            "task_failure_counts": {},
            "common_rejection_reasons": {},
            "active_generation_id": "",
            "unaddressed_tasks": [],
            "state_available": False,
        }

        if not full_path.exists():
            return diagnostics

        try:
            with open(full_path, "r", encoding="utf-8") as f:
                state_data = json.load(f)

            diagnostics["state_available"] = True
            diagnostics["cycle_count"] = state_data.get("cycle_count", 0)
            diagnostics["active_generation_id"] = state_data.get("active_generation_id", "")

            # Count failures across tasks
            failure_cat = state_data.get("failure_catalog", {})
            for task_id, fails in failure_cat.items():
                diagnostics["task_failure_counts"][task_id] = len(fails)
                diagnostics["total_rejections"] += len(fails)
                for f_item in fails:
                    reason = f_item.get("rejection_reason", "UNKNOWN")
                    diagnostics["common_rejection_reasons"][reason] = (
                        diagnostics["common_rejection_reasons"].get(reason, 0) + 1
                    )

            # Check completed cycles for stagnation markers
            for c in state_data.get("completed_cycles", []):
                if c.get("decision") == "STAGNATED":
                    diagnostics["stagnation_events"] += 1

            # Determine tasks that remain unpromoted or below 0.60
            known_tasks = {"task_k1", "task_k2", "task_j1", "task_j2"}
            for t in known_tasks:
                if t not in failure_cat or diagnostics["task_failure_counts"].get(t, 0) > 10:
                    diagnostics["unaddressed_tasks"].append(t)

        except Exception as e:
            diagnostics["error"] = str(e)

        return diagnostics
