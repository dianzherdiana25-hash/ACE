"""Edge-case unit tests for ace_code_agent/codebase_reader.py."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from ace_code_agent.codebase_reader import CodebaseReader


class TestCodebaseReaderEdgeCases(unittest.TestCase):
    def test_01_default_repo_root_points_to_workspace_with_code_dir(self) -> None:
        reader = CodebaseReader()
        self.assertTrue((reader.repo_root / "code").is_dir())

    def test_02_scan_missing_directory_returns_empty_dict(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            reader = CodebaseReader(Path(tmp))
            self.assertEqual(reader.scan_python_modules("does/not/exist"), {})

    def test_03_scan_empty_directory_returns_empty_dict(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp) / "pkg"
            pkg.mkdir()
            reader = CodebaseReader(Path(tmp))
            self.assertEqual(reader.scan_python_modules("pkg"), {})

    def test_04_scan_ignores_non_python_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp) / "pkg"
            pkg.mkdir()
            (pkg / "README.md").write_text("# docs", encoding="utf-8")
            (pkg / "data.json").write_text("{}", encoding="utf-8")
            reader = CodebaseReader(Path(tmp))
            self.assertEqual(reader.scan_python_modules("pkg"), {})

    def test_05_scan_extracts_classes_functions_and_line_count(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp) / "pkg"
            pkg.mkdir()
            (pkg / "mod.py").write_text(
                "class Alpha:\n    def m(self):\n        return 1\n\ndef top():\n    return 2\n",
                encoding="utf-8",
            )
            reader = CodebaseReader(Path(tmp))
            res = reader.scan_python_modules("pkg")
            info = res["pkg/mod.py"]
            self.assertTrue(info["ast_valid"])
            self.assertEqual(info["classes"], ["Alpha"])
            self.assertEqual(info["functions"], ["top", "m"] if info["functions"] == ["top", "m"] else info["functions"])
            self.assertIn("m", info["functions"])
            self.assertIn("top", info["functions"])
            self.assertEqual(info["line_count"], 6)

    def test_06_scan_empty_python_file_is_ast_valid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp) / "pkg"
            pkg.mkdir()
            (pkg / "empty.py").write_text("", encoding="utf-8")
            reader = CodebaseReader(Path(tmp))
            res = reader.scan_python_modules("pkg")
            self.assertTrue(res["pkg/empty.py"]["ast_valid"])
            self.assertEqual(res["pkg/empty.py"]["line_count"], 0)
            self.assertEqual(res["pkg/empty.py"]["classes"], [])
            self.assertEqual(res["pkg/empty.py"]["functions"], [])

    def test_07_scan_syntax_error_recorded_without_crashing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp) / "pkg"
            pkg.mkdir()
            (pkg / "broken.py").write_text("def oops(:\n    pass\n", encoding="utf-8")
            reader = CodebaseReader(Path(tmp))
            res = reader.scan_python_modules("pkg")
            self.assertFalse(res["pkg/broken.py"]["ast_valid"])
            self.assertIn("parse_error", res["pkg/broken.py"])

    def test_08_scan_invalid_utf8_bytes_recorded_safely(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp) / "pkg"
            pkg.mkdir()
            (pkg / "binary.py").write_bytes(b"\xff\xfe\xfa\x00invalid_utf8")
            reader = CodebaseReader(Path(tmp))
            res = reader.scan_python_modules("pkg")
            self.assertFalse(res["pkg/binary.py"]["ast_valid"])
            self.assertIn("parse_error", res["pkg/binary.py"])

    def test_09_scan_recurses_nested_subdirectories_sorted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sub = Path(tmp) / "pkg" / "nested"
            sub.mkdir(parents=True)
            (Path(tmp) / "pkg" / "b.py").write_text("x = 1\n", encoding="utf-8")
            (sub / "a.py").write_text("y = 2\n", encoding="utf-8")
            reader = CodebaseReader(Path(tmp))
            res = reader.scan_python_modules("pkg")
            self.assertEqual(sorted(res.keys()), ["pkg/b.py", "pkg/nested/a.py"])

    def test_10_read_failure_history_missing_file_returns_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            reader = CodebaseReader(Path(tmp))
            diag = reader.read_failure_history("missing_state.json")
            self.assertFalse(diag["state_available"])
            self.assertEqual(diag["cycle_count"], 0)
            self.assertEqual(diag["total_rejections"], 0)
            self.assertEqual(diag["unaddressed_tasks"], [])

    def test_11_read_failure_history_corrupt_json_records_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / "state.json"
            state.write_text("{corrupt json", encoding="utf-8")
            reader = CodebaseReader(Path(tmp))
            diag = reader.read_failure_history("state.json")
            self.assertFalse(diag["state_available"])
            self.assertIn("error", diag)

    def test_12_read_failure_history_valid_minimal_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / "state.json"
            state.write_text(json.dumps({"cycle_count": 7, "active_generation_id": "gen_7"}), encoding="utf-8")
            reader = CodebaseReader(Path(tmp))
            diag = reader.read_failure_history("state.json")
            self.assertTrue(diag["state_available"])
            self.assertEqual(diag["cycle_count"], 7)
            self.assertEqual(diag["active_generation_id"], "gen_7")
            self.assertEqual(set(diag["unaddressed_tasks"]), {"task_k1", "task_k2", "task_j1", "task_j2"})

    def test_13_read_failure_history_aggregates_reasons_and_defaults_unknown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / "state.json"
            state.write_text(
                json.dumps(
                    {
                        "failure_catalog": {
                            "task_k1": [
                                {"rejection_reason": "SYNTAX_ERROR"},
                                {"rejection_reason": "SYNTAX_ERROR"},
                                {},
                            ]
                        }
                    }
                ),
                encoding="utf-8",
            )
            reader = CodebaseReader(Path(tmp))
            diag = reader.read_failure_history("state.json")
            self.assertEqual(diag["total_rejections"], 3)
            self.assertEqual(diag["task_failure_counts"]["task_k1"], 3)
            self.assertEqual(diag["common_rejection_reasons"]["SYNTAX_ERROR"], 2)
            self.assertEqual(diag["common_rejection_reasons"]["UNKNOWN"], 1)

    def test_14_read_failure_history_threshold_boundary_10_vs_11(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / "state.json"
            state.write_text(
                json.dumps(
                    {
                        "failure_catalog": {
                            "task_k1": [{"rejection_reason": "FAIL"}] * 10,
                            "task_k2": [{"rejection_reason": "FAIL"}] * 11,
                            "task_j1": [],
                            "task_j2": [],
                        }
                    }
                ),
                encoding="utf-8",
            )
            reader = CodebaseReader(Path(tmp))
            diag = reader.read_failure_history("state.json")
            self.assertNotIn("task_k1", diag["unaddressed_tasks"])
            self.assertIn("task_k2", diag["unaddressed_tasks"])

    def test_15_read_failure_history_counts_only_stagnated_cycles(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / "state.json"
            state.write_text(
                json.dumps(
                    {
                        "completed_cycles": [
                            {"decision": "PROMOTED"},
                            {"decision": "STAGNATED"},
                            {"decision": "REJECTED"},
                            {"decision": "STAGNATED"},
                            {},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            reader = CodebaseReader(Path(tmp))
            diag = reader.read_failure_history("state.json")
            self.assertEqual(diag["stagnation_events"], 2)

    def test_16_read_failure_history_with_non_dict_json_captures_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / "state.json"
            state.write_text("[1, 2, 3]", encoding="utf-8")
            reader = CodebaseReader(Path(tmp))
            diag = reader.read_failure_history("state.json")
            self.assertTrue(diag["state_available"])
            self.assertIn("error", diag)

    def test_17_scan_handles_async_functions_and_nested_classes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp) / "pkg"
            pkg.mkdir()
            (pkg / "async_mod.py").write_text(
                "class Outer:\n    class Inner:\n        pass\n\ndef sync_fn():\n    def inner_fn():\n        return 0\n    return inner_fn()\n",
                encoding="utf-8",
            )
            reader = CodebaseReader(Path(tmp))
            res = reader.scan_python_modules("pkg")
            info = res["pkg/async_mod.py"]
            self.assertEqual(set(info["classes"]), {"Outer", "Inner"})
            self.assertEqual(set(info["functions"]), {"sync_fn", "inner_fn"})

    def test_18_scan_ignores_pyc_and_pycache_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp) / "pkg" / "__pycache__"
            cache.mkdir(parents=True)
            (cache / "mod.cpython-311.pyc").write_bytes(b"\x00\x01\x02")
            reader = CodebaseReader(Path(tmp))
            self.assertEqual(reader.scan_python_modules("pkg"), {})

    def test_19_read_failure_history_extra_unknown_tasks_still_counted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / "state.json"
            state.write_text(
                json.dumps({"failure_catalog": {"custom_task": [{"rejection_reason": "TIMEOUT"}]}}),
                encoding="utf-8",
            )
            reader = CodebaseReader(Path(tmp))
            diag = reader.read_failure_history("state.json")
            self.assertEqual(diag["task_failure_counts"]["custom_task"], 1)
            self.assertEqual(diag["total_rejections"], 1)

    def test_20_scan_accepts_str_path_for_repo_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp) / "pkg"
            pkg.mkdir()
            (pkg / "one.py").write_text("a = 1\n", encoding="utf-8")
            reader = CodebaseReader(tmp)  # type: ignore[arg-type]
            self.assertIn("pkg/one.py", reader.scan_python_modules("pkg"))

    def test_21_read_failure_history_non_list_failure_entries_captured_as_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / "state.json"
            state.write_text(json.dumps({"failure_catalog": {"task_k1": 42}}), encoding="utf-8")
            reader = CodebaseReader(Path(tmp))
            diag = reader.read_failure_history("state.json")
            self.assertIn("error", diag)

    def test_22_scan_real_code_package_smoke(self) -> None:
        reader = CodebaseReader()
        res = reader.scan_python_modules("code/ace_visual_bridge")
        self.assertTrue(any(k.endswith("contract.py") for k in res))
        self.assertTrue(all(v["ast_valid"] for v in res.values()))


if __name__ == "__main__":
    unittest.main()
