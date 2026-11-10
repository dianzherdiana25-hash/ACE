"""E2E Test Suite: Repository Retrieval and Code Understanding (Requirement 3).

4-Tier Systematic Verification:
Tier 1: Feature Coverage (happy-path AST codebase parsing, class/function extraction)
Tier 2: Boundary & Corner Cases (unparseable syntax, empty directories, non-existent files)
Tier 3: Cross-Feature Interactions (reading persistent research failure catalog and stagnation markers)
Tier 4: Real-World Scenarios (retrieval indexing over multi-package source tree for problem selection)
"""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

# Ensure ACE/code is on sys.path
_CODE_DIR = Path(__file__).resolve().parent.parent.parent / "code"
if str(_CODE_DIR) not in sys.path:
    sys.path.insert(0, str(_CODE_DIR))

from ace_code_agent.codebase_reader import CodebaseReader


class TestRepoRetrievalE2E(unittest.TestCase):
    """End-to-end verification of AST repository retrieval and codebase understanding."""

    def setUp(self):
        self.temp_repo = Path(tempfile.mkdtemp(prefix="ace_e2e_retrieval_"))
        self.code_dir = self.temp_repo / "code" / "sample_pkg"
        self.code_dir.mkdir(parents=True, exist_ok=True)
        self.checkpoints_dir = self.temp_repo / "checkpoints" / "self_dev"
        self.checkpoints_dir.mkdir(parents=True, exist_ok=True)
        self.reader = CodebaseReader(repo_root=self.temp_repo)

    def tearDown(self):
        shutil.rmtree(self.temp_repo, ignore_errors=True)

    # -------------------------------------------------------------------------
    # Tier 1: Feature Coverage (Happy Path)
    # -------------------------------------------------------------------------

    def test_tier1_scan_python_modules_extracts_ast_symbols(self):
        """Verify scan_python_modules extracts classes, functions, and lines from valid Python files."""
        sample_code = (
            "class Optimizer:\n"
            "    def step(self):\n"
            "        pass\n"
            "\n"
            "def calculate_loss(y_true, y_pred):\n"
            "    return y_true - y_pred\n"
        )
        file_path = self.code_dir / "optimizer.py"
        file_path.write_text(sample_code, encoding="utf-8")

        results = self.reader.scan_python_modules(subpackage="code/sample_pkg")
        rel_key = "code/sample_pkg/optimizer.py"

        self.assertIn(rel_key, results)
        mod_info = results[rel_key]
        self.assertTrue(mod_info["ast_valid"])
        self.assertIn("Optimizer", mod_info["classes"])
        self.assertIn("step", mod_info["functions"])
        self.assertIn("calculate_loss", mod_info["functions"])
        self.assertEqual(mod_info["line_count"], 6)

    def test_tier1_read_failure_history_from_state(self):
        """Verify read_failure_history accurately parses persistent research state JSON."""
        state_data = {
            "cycle_count": 5,
            "active_generation_id": "G1_cand_05",
            "failure_catalog": {
                "task_k1": [
                    {"rejection_reason": "INSUFFICIENT_GAIN"},
                    {"rejection_reason": "REGRESSION_DETECTED"},
                ],
                "task_k2": [
                    {"rejection_reason": "INSUFFICIENT_GAIN"},
                ],
            },
            "completed_cycles": [
                {"cycle_id": 1, "decision": "REJECTED"},
                {"cycle_id": 2, "decision": "STAGNATED"},
            ],
        }
        state_file = self.checkpoints_dir / "research_state.json"
        state_file.write_text(json.dumps(state_data), encoding="utf-8")

        diagnostics = self.reader.read_failure_history()
        self.assertTrue(diagnostics["state_available"])
        self.assertEqual(diagnostics["cycle_count"], 5)
        self.assertEqual(diagnostics["active_generation_id"], "G1_cand_05")
        self.assertEqual(diagnostics["total_rejections"], 3)
        self.assertEqual(diagnostics["stagnation_events"], 1)
        self.assertEqual(diagnostics["common_rejection_reasons"].get("INSUFFICIENT_GAIN"), 2)
        self.assertEqual(diagnostics["common_rejection_reasons"].get("REGRESSION_DETECTED"), 1)

    # -------------------------------------------------------------------------
    # Tier 2: Boundary & Corner Cases
    # -------------------------------------------------------------------------

    def test_tier2_syntax_error_file_is_handled_gracefully(self):
        """Verify that files with unparseable Python syntax record ast_valid: False without crashing."""
        broken_code = "def syntax_broken_func(\n  return 1"
        broken_path = self.code_dir / "broken.py"
        broken_path.write_text(broken_code, encoding="utf-8")

        results = self.reader.scan_python_modules(subpackage="code/sample_pkg")
        rel_key = "code/sample_pkg/broken.py"

        self.assertIn(rel_key, results)
        self.assertFalse(results[rel_key]["ast_valid"])
        self.assertIn("parse_error", results[rel_key])
        self.assertEqual(results[rel_key]["classes"], [])
        self.assertEqual(results[rel_key]["functions"], [])

    def test_tier2_non_existent_and_empty_directory_returns_empty_dict(self):
        """Verify that scanning a non-existent or empty package directory returns an empty dictionary."""
        results_non_existent = self.reader.scan_python_modules(subpackage="code/does_not_exist")
        self.assertEqual(results_non_existent, {})

        empty_dir = self.temp_repo / "code" / "empty_pkg"
        empty_dir.mkdir(parents=True, exist_ok=True)
        results_empty = self.reader.scan_python_modules(subpackage="code/empty_pkg")
        self.assertEqual(results_empty, {})

    def test_tier2_missing_state_file_returns_unavailable_flag(self):
        """Verify that failure history query with missing state file returns state_available: False."""
        diagnostics = self.reader.read_failure_history(state_file="non_existent_state.json")
        self.assertFalse(diagnostics["state_available"])
        self.assertEqual(diagnostics["cycle_count"], 0)
        self.assertEqual(diagnostics["total_rejections"], 0)

    # -------------------------------------------------------------------------
    # Tier 3: Cross-Feature Interactions
    # -------------------------------------------------------------------------

    def test_tier3_scan_real_ace_code_package(self):
        """Verify CodebaseReader scans actual ACE production packages and extracts symbols."""
        real_reader = CodebaseReader()  # Points to real repo root
        results = real_reader.scan_python_modules(subpackage="code/ace_host_controller")
        self.assertTrue(len(results) > 0)

        # Confirm critical host controller modules are indexed
        gate_key = "code/ace_host_controller/sandbox_gate.py"
        self.assertIn(gate_key, results)
        self.assertTrue(results[gate_key]["ast_valid"])
        self.assertIn("HostSandboxGate", results[gate_key]["classes"])

    # -------------------------------------------------------------------------
    # Tier 4: Real-World Scenarios
    # -------------------------------------------------------------------------

    def test_tier4_end_to_end_repo_indexing_and_unaddressed_task_detection(self):
        """Simulate repo retrieval workflow identifying unaddressed tasks based on failure catalog."""
        # Create a state where task_k1 and task_k2 have > 10 rejections, leaving them unaddressed
        state_data = {
            "cycle_count": 25,
            "active_generation_id": "G2_cand_25",
            "failure_catalog": {
                "task_k1": [{"rejection_reason": "NO_GAIN"} for _ in range(12)],
                "task_k2": [{"rejection_reason": "REGRESSION"} for _ in range(15)],
            },
            "completed_cycles": [],
        }
        state_file = self.checkpoints_dir / "research_state.json"
        state_file.write_text(json.dumps(state_data), encoding="utf-8")

        diagnostics = self.reader.read_failure_history()
        self.assertTrue(diagnostics["state_available"])
        self.assertIn("task_k1", diagnostics["unaddressed_tasks"])
        self.assertIn("task_k2", diagnostics["unaddressed_tasks"])
        self.assertEqual(diagnostics["task_failure_counts"]["task_k1"], 12)
        self.assertEqual(diagnostics["task_failure_counts"]["task_k2"], 15)


if __name__ == "__main__":
    unittest.main()
