"""Uji kasus tepi untuk modul non-verdict ace_research_repair (>=25 kasus):
corpus, operators, represent, dan memory.
"""
from __future__ import annotations

import ast
import sqlite3
import tempfile
import unittest
from pathlib import Path

from .corpus import (
    DevTestCase,
    PerturbationSpec,
    canonical_json,
    sha256_digest,
    source_units,
    target_units,
)
from .memory import MemoryIntegrityError, RepairMemory
from .operators import generate_candidates
from .represent import (
    _trace_predicate,
    diagnose_reproduction,
    extract_fault_representation,
    infer_trace_regime_and_motif,
    inspect_module_ast,
)


class CorpusModuleEdgeTests(unittest.TestCase):
    """Kasus tepi pada ace_research_repair.corpus."""

    def test_canonical_json_sorts_keys_and_rejects_nan_inf(self) -> None:
        self.assertEqual(canonical_json({"b": 2, "a": 1}), b'{"a":1,"b":2}')
        for bad in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                canonical_json({"x": bad})

    def test_sha256_digest_consistent_across_key_orders_and_types(self) -> None:
        d1 = sha256_digest({"k2": [1, 2], "k1": "v"})
        d2 = sha256_digest({"k1": "v", "k2": [1, 2]})
        self.assertEqual(d1, d2)
        self.assertEqual(sha256_digest(b"abc"), sha256_digest("abc"))

    def test_public_unit_view_strips_truth_fields(self) -> None:
        unit = source_units()[0]
        view = unit.public_view()
        self.assertEqual(view.unit_id, unit.unit_id)
        self.assertEqual(view.entrypoint, unit.entrypoint)
        self.assertEqual(view.source_sha256, sha256_digest(unit.buggy_source))
        self.assertFalse(hasattr(view, "family_truth"))
        self.assertFalse(hasattr(view, "category"))
        self.assertFalse(hasattr(view, "split"))

    def test_source_and_target_banks_unique_ids_and_parseable_sources(self) -> None:
        all_units = source_units() + target_units()
        ids = [u.unit_id for u in all_units]
        self.assertEqual(len(ids), len(set(ids)))
        for unit in all_units:
            self.assertTrue(unit.dev_tests)
            self.assertTrue(unit.perturbation_spec.diverse_inputs)
            ast.parse(unit.buggy_source)

    def test_dev_testcase_and_perturbation_spec_to_dict(self) -> None:
        tc = DevTestCase("t1", "call", ([1, 2],), 3)
        ps = PerturbationSpec((([1],),), ((([1],), ([1],)),))
        self.assertEqual(tc.to_dict()["args"], [[1, 2]])
        self.assertEqual(ps.to_dict()["diverse_inputs"], [[[1]]])
        self.assertTrue(ps.to_dict()["expect_variation"])


class OperatorsModuleEdgeTests(unittest.TestCase):
    """Kasus tepi pada generator operator AST ace_research_repair.operators."""

    def test_zero_arg_empty_function_produces_no_candidates(self) -> None:
        self.assertEqual(generate_candidates("def noop():\n    pass\n", "noop"), [])

    def test_empty_guard_skipped_when_already_present(self) -> None:
        src = "def f(xs):\n    if not xs:\n        return []\n    return xs\n"
        names = {p.operator_name for p in generate_candidates(src, "f")}
        self.assertNotIn("OP_EMPTY_GUARD_INSERT", names)

    def test_default_none_init_handles_list_dict_set_only(self) -> None:
        src = "def collect(a=[], b={}, c={1}, d=0):\n    return a\n"
        patches = [p for p in generate_candidates(src, "collect") if p.operator_name == "OP_DEFAULT_NONE_INIT"]
        self.assertEqual(len(patches), 3)
        for p in patches:
            self.assertIn("=None", p.patched_source)

    def test_range_stop_adjust_handles_sub_1_sub_2_and_two_arg_range(self) -> None:
        src = "def f(n):\n    for i in range(n - 1):\n        pass\n    for j in range(0, n - 2):\n        pass\n"
        patches = [p for p in generate_candidates(src, "f") if p.operator_name == "OP_RANGE_STOP_ADJUST"]
        rendered = "\n".join(p.patched_source for p in patches)
        self.assertIn("range(n)", rendered)
        self.assertIn("range(n - 2)", rendered)
        self.assertIn("range(0, n - 1)", rendered)
        self.assertIn("range(0, n - 3)", rendered)

    def test_cmp_boundary_flip_skips_eq_and_chained_compares(self) -> None:
        src = "def f(a, b, c):\n    if a == b:\n        return 1\n    if 0 < a < c:\n        return 2\n    if a <= b:\n        return 3\n    return 0\n"
        patches = [p for p in generate_candidates(src, "f") if p.operator_name == "OP_CMP_BOUNDARY_FLIP"]
        self.assertEqual(len(patches), 1)
        self.assertIn("if a < b:", patches[0].patched_source)

    def test_slice_bound_adjust_rewrites_lower_one_and_upper(self) -> None:
        src = "def f(xs, hi):\n    return xs[1:hi]\n"
        patches = [p for p in generate_candidates(src, "f") if p.operator_name == "OP_SLICE_BOUND_ADJUST"]
        rendered = "\n".join(p.patched_source for p in patches)
        self.assertIn("xs[0:hi]", rendered)
        self.assertIn("xs[1:hi + 1]", rendered)

    def test_split_strip_and_maxsplit_operators(self) -> None:
        src = 'def f(line):\n    return line.split(":")\n'
        by_name = {p.operator_name: p.patched_source for p in generate_candidates(src, "f")}
        self.assertIn("line.strip().split(':')", by_name.get("OP_STR_STRIP_NORMALIZE", ""))
        self.assertIn("line.split(':', 1)", by_name.get("OP_SPLIT_MAXSPLIT_ONE", ""))

    def test_sign_guard_expand_and_mutable_copy_wrap(self) -> None:
        src = "def f(tok, tpl, hist):\n    row = tpl\n    hist.append(row)\n    return tok.isdigit()\n"
        patches = generate_candidates(src, "f")
        by_name: dict[str, list[str]] = {}
        for p in patches:
            by_name.setdefault(p.operator_name, []).append(p.patched_source)
        self.assertTrue(any(".lstrip('+-').isdigit()" in s for s in by_name["OP_SIGN_GUARD_EXPAND"]))
        joined_copy = "\n".join(by_name["OP_MUTABLE_COPY_WRAP"])
        self.assertIn("row = tpl.copy()", joined_copy)
        self.assertIn("hist.append(row.copy())", joined_copy)

    def test_state_reset_and_loop_tail_flush_operators(self) -> None:
        src = (
            "def f(xs):\n"
            "    out = []\n"
            "    cnt = 0\n"
            "    for x in xs:\n"
            "        if x > 0:\n"
            "            out.append(cnt)\n"
            "        cnt += 1\n"
            "    return out\n"
        )
        names = {p.operator_name for p in generate_candidates(src, "f")}
        self.assertIn("OP_STATE_RESET_ON_FLUSH", names)
        self.assertIn("OP_LOOP_TAIL_FLUSH", names)

    def test_swap_adjacent_never_moves_return_or_break(self) -> None:
        src = "def f(xs):\n    a = 1\n    for x in xs:\n        b = 2\n        break\n    return a\n"
        swaps = [p for p in generate_candidates(src, "f") if p.operator_name == "OP_SWAP_ADJACENT_STATE_STMTS"]
        self.assertEqual(swaps, [])

    def test_overfit_probes_respect_failing_test_names_and_uniqueness(self) -> None:
        src = "def helper(x):\n    return x\n\ndef entry(x):\n    return x + 1\n"
        tcs = (
            DevTestCase("pass_case", "call", (1,), 2),
            DevTestCase("fail_case", "call", (5,), 99),
        )
        patches = generate_candidates(src, "entry", dev_tests=tcs, failing_test_names={"fail_case"})
        guards = [p for p in patches if p.operator_name == "OP_OVERFIT_DEV_INPUT_GUARD"]
        self.assertEqual(len(guards), 1)
        self.assertIn("if x == 5:", guards[0].patched_source)
        self.assertNotIn("if x == 1:", guards[0].patched_source)
        sources = [p.patched_source for p in patches]
        self.assertEqual(len(sources), len(set(sources)))


class RepresentModuleEdgeTests(unittest.TestCase):
    """Kasus tepi pada ace_research_repair.represent."""

    def test_inspect_module_ast_missing_entrypoint(self) -> None:
        meta = inspect_module_ast("def other(x):\n    return x\n", "missing")
        self.assertFalse(meta["entrypoint_found"])
        self.assertEqual(meta["function_names"], ["other"])
        self.assertFalse(meta["has_mutable_default"])

    def test_inspect_module_ast_detects_stale_dataflow_and_while_subscript(self) -> None:
        src = (
            "def f(arr, delta):\n"
            "    base = arr[0]\n"
            "    adj = helper(base)\n"
            "    out = compute(base, delta)\n"
            "    i = 0\n"
            "    while i < len(arr):\n"
            "        _ = arr[i]\n"
            "        i += 1\n"
            "    return out\n"
        )
        meta = inspect_module_ast(src, "f")
        self.assertTrue(meta["entrypoint_found"])
        self.assertTrue(meta["has_stale_dataflow_chain"])
        self.assertTrue(meta["has_index_bound_loop"])

    def test_diagnose_reproduction_zero_failures_and_exception_boost_capped(self) -> None:
        clean = diagnose_reproduction(
            {"cases": [{"name": "ok", "passed": True, "executed_lines": [2, 3]}]},
            {"entrypoint_lineno": 1},
        )
        self.assertEqual(clean["failing_count"], 0)
        self.assertEqual(clean["ochiai_by_line"], {"2": 0.0, "3": 0.0})
        self.assertEqual(
            diagnose_reproduction({"cases": []}, {"entrypoint_lineno": 1})["ochiai_by_line"],
            {},
        )

        crashed = diagnose_reproduction(
            {
                "cases": [
                    {
                        "name": "boom",
                        "passed": False,
                        "executed_lines": [5],
                        "exception_lineno": 5,
                        "exception_type": "IndexError",
                    }
                ]
            },
            {"entrypoint_lineno": 1},
        )
        self.assertEqual(crashed["primary_failure_mode"], "IndexError")
        self.assertEqual(crashed["ochiai_by_line"]["5"], 1.0)
        self.assertIn("1", crashed["ochiai_by_line"])

    def test_diagnose_failure_mode_precedence_chain(self) -> None:
        modes = [
            ({"exception_type": "ValueError"}, "ValueError"),
            ({"arg_mutated": True}, "CallerArgMutated"),
            ({"aliased_return": True}, "AliasedReturn"),
            ({"sequence_second_failed": True}, "CrossCallStateLeak"),
            ({}, "AssertionMismatch"),
        ]
        for extra, expected in modes:
            with self.subTest(expected=expected):
                case = {"name": "c", "passed": False, "executed_lines": [1], **extra}
                res = diagnose_reproduction({"cases": [case]}, {"entrypoint_lineno": 1})
                self.assertEqual(res["primary_failure_mode"], expected)

    def test_trace_predicate_regimes_and_unknown_error(self) -> None:
        self.assertTrue(_trace_predicate("R_INDEX_GUARD", "ab"))
        self.assertTrue(_trace_predicate("R_TOKEN_STREAM", "aab"))
        self.assertTrue(_trace_predicate("R_STATE_CYCLE", "ab"))
        self.assertFalse(_trace_predicate("R_STATE_CYCLE", "ba"))
        self.assertTrue(_trace_predicate("R_DEPENDENCY", "aaab"))
        with self.assertRaises(ValueError):
            _trace_predicate("R_UNKNOWN", "ab")

    def test_infer_trace_regime_and_extract_representation_disabled_bridge(self) -> None:
        ast_meta = {
            "has_mutable_default": False,
            "has_stale_dataflow_chain": True,
            "has_index_bound_loop": False,
            "has_element_state_loop": False,
            "has_string_tokenizer_ops": False,
        }
        diag = {"failing_count": 1, "primary_failure_mode": "AssertionMismatch", "top_suspicious_lines": [3]}
        self.assertEqual(infer_trace_regime_and_motif(ast_meta, diag), ("R_DEPENDENCY", "AssertionMismatch|StaleDataflow"))

        rep = extract_fault_representation(ast_meta, diag, "0" * 64, "unit_x", bridge=None)
        self.assertEqual(rep["runtime"]["runtime_phase"], "DISABLED")
        self.assertFalse(rep["runtime"]["runtime_staged"])


class RepairMemoryEdgeTests(unittest.TestCase):
    """Kasus tepi pada ace_research_repair.memory."""

    def test_remember_rejects_empty_runtime_model_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, RepairMemory(Path(tmp) / "mem.db") as mem:
            with self.assertRaises(ValueError):
                mem.remember_validated_repair(
                    unit_id="S01",
                    runtime_model_id="",
                    trace_regime="R_INDEX_GUARD",
                    fine_signature="sig",
                    ast_node_kind="Call:range",
                    operator_family="boundary_index",
                    operator_name="OP_RANGE_STOP_ADJUST",
                    patch_id="p1",
                )

    def test_remember_is_idempotent_and_query_priors_filters_by_model_and_signature(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "mem.db"
            with RepairMemory(db) as mem:
                r1 = mem.remember_validated_repair(
                    unit_id="S01",
                    runtime_model_id="m1",
                    trace_regime="R_INDEX_GUARD",
                    fine_signature="sig_a",
                    ast_node_kind="Call:range",
                    operator_family="boundary_index",
                    operator_name="OP_A",
                    patch_id="p1",
                )
                r2 = mem.remember_validated_repair(
                    unit_id="S01",
                    runtime_model_id="m1",
                    trace_regime="R_INDEX_GUARD",
                    fine_signature="sig_a",
                    ast_node_kind="Call:range",
                    operator_family="boundary_index",
                    operator_name="OP_A",
                    patch_id="p1",
                )
                mem.remember_validated_repair(
                    unit_id="S02",
                    runtime_model_id="m1",
                    trace_regime="R_TOKEN_STREAM",
                    fine_signature="sig_b",
                    ast_node_kind="Call:split",
                    operator_family="parsing",
                    operator_name="OP_B",
                    patch_id="p2",
                )
                self.assertTrue(r1["inserted"])
                self.assertFalse(r2["inserted"])
                self.assertEqual(r1["ordinal"], r2["ordinal"])
                self.assertEqual(mem.query_priors(None, "sig_a")["matched_capability_records"], 0)

                priors = mem.query_priors("m1", "sig_a")
                self.assertEqual(priors["matched_capability_records"], 2)
                self.assertEqual(priors["family_counts"], {"boundary_index": 1, "parsing": 1})
                self.assertEqual(priors["operator_counts"], {"OP_A": 1})

    def test_tampering_repair_column_raises_memory_integrity_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "mem.db"
            with RepairMemory(db) as mem:
                mem.remember_validated_repair(
                    unit_id="S01",
                    runtime_model_id="m1",
                    trace_regime="R_INDEX_GUARD",
                    fine_signature="sig_a",
                    ast_node_kind="Call:range",
                    operator_family="boundary_index",
                    operator_name="OP_A",
                    patch_id="p1",
                )
            conn = sqlite3.connect(db)
            conn.execute("UPDATE repairs SET unit_id = 'TAMPERED'")
            conn.commit()
            conn.close()
            with self.assertRaises(MemoryIntegrityError):
                RepairMemory(db)

    def test_tampering_metadata_schema_raises_memory_integrity_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "mem.db"
            with RepairMemory(db):
                pass
            conn = sqlite3.connect(db)
            conn.execute("UPDATE metadata SET value = 'tampered.v9' WHERE key = 'schema'")
            conn.commit()
            conn.close()
            with self.assertRaises(MemoryIntegrityError):
                RepairMemory(db)


if __name__ == "__main__":
    unittest.main()
