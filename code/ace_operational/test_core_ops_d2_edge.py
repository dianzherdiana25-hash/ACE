"""Tes edge-case dan adversarial Garis D2 untuk modul operasional inti non-verdict."""
from __future__ import annotations

from decimal import Decimal
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from ace_autonomy.budget import BudgetController, BudgetUsage
from ace_autonomy.errors import BudgetExhaustedError
from ace_autonomy.policy import BudgetCeiling
from ace_operational.admission_hygiene import (
    SCHEMA_MDL_COSTS,
    filter_parsimonious_keys,
    operator_mdl_cost,
)
from ace_operational.brain_registry import BrainRegistry
from ace_operational.catalog_artifact import (
    ARTIFACT_NAME,
    extract_classes,
    load_catalog,
    materialize,
    verify_catalog,
)
from ace_operational.catalog_gap import (
    STATUS_COVERED,
    STATUS_PARTIAL,
    STATUS_SATURATED,
    CatalogGapError,
    analyze_catalog_gaps,
)
from ace_operational import preaudit_validator as pv


def _gap_record(**overrides: object) -> dict:
    rec: dict = {
        "pool_tasks": 3,
        "candidate_operators": 4,
        "admitted_operators": ["('op_a', (1,), 0)"],
        "admitted_chains": [],
        "eval_tasks": 10,
        "eval_solved_baseline": 0,
        "eval_solved_extended": 5,
    }
    rec.update(overrides)
    return rec


class _DummyAdapter:
    def __init__(self, broken_on_key: str) -> None:
        self.broken_on_key = broken_on_key

    def passes(self, mutated_code: str, reference_cases: list[tuple], reference_truth: list) -> int:
        if self.broken_on_key in mutated_code:
            return max(0, len(reference_cases) - 1)
        return len(reference_cases)


class BrainRegistryEdgeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="d2-brains-")
        self.addCleanup(self.tmp.cleanup)
        self.reg_path = Path(self.tmp.name) / "brains.json"
        self.reg = BrainRegistry(self.reg_path)

    def test_01_rejects_unknown_status_without_writing_file(self) -> None:
        with self.assertRaises(ValueError):
            self.reg.register("b1", kind="local", descriptor="Qwen3", status="pending")
        self.assertFalse(self.reg_path.exists())

    def test_02_dismiss_and_reinstate_unknown_brain_raises_key_error(self) -> None:
        with self.assertRaises(KeyError):
            self.reg.dismiss("missing-brain", reason="test")
        with self.assertRaises(KeyError):
            self.reg.reinstate("missing-brain", reason="test")

    def test_03_match_bidirectional_substring_and_none_empty_hints(self) -> None:
        self.reg.register("qwen", kind="local-gguf", descriptor="Qwen3-8B-Q4_K_M.gguf")
        self.assertIsNone(self.reg.match(None))
        self.assertIsNone(self.reg.match(""))
        self.assertIsNotNone(self.reg.match("qwen3-8b"))
        self.assertIsNotNone(self.reg.match("/models/Qwen3-8B-Q4_K_M.gguf"))
        self.assertIsNone(self.reg.match("llama-70b"))

    def test_04_corrupt_registry_json_raises_decode_error(self) -> None:
        self.reg_path.write_text("{corrupt", encoding="utf-8")
        with self.assertRaises(json.JSONDecodeError):
            BrainRegistry(self.reg_path)

    def test_05_empty_descriptor_must_not_wildcard_match_unrelated_models(self) -> None:
        # Bug yang sudah diperbaiki (2026-11-20): match() kini melewati
        # descriptor kosong — "" in hint selalu True sehingga brain ber-
        # descriptor kosong dulu cocok dengan model apa pun.
        self.reg.register("blank", kind="local", descriptor="")
        self.assertIsNone(self.reg.match("llama-70b"))

    def test_06_dismiss_after_reinstate_updates_reason_and_appends_event(self) -> None:
        self.reg.register("qwen", kind="local", descriptor="Qwen3-8B")
        self.reg.dismiss("qwen", reason="drill-1")
        self.reg.reinstate("qwen", reason="passed")
        self.reg.dismiss("qwen", reason="drill-2")
        rec = self.reg.get("qwen")
        assert rec is not None
        self.assertEqual(rec["status"], "dismissed")
        self.assertEqual(rec["dismissal_reason"], "drill-2")
        self.assertEqual([e["kind"] for e in self.reg.events()], ["registered", "dismissed", "reinstated", "dismissed"])


class CatalogArtifactEdgeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="d2-cat-")
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def test_07_extract_classes_handles_missing_lists_and_none_record(self) -> None:
        classes = extract_classes({"by_class": {"empty_rec": None, "only_ops": {"admitted_operators": ["b", "a"]}}})
        self.assertEqual(classes["empty_rec"], {"operators": [], "chains": []})
        self.assertEqual(classes["only_ops"], {"operators": ["a", "b"], "chains": []})

    def test_08_verify_catalog_detects_non_dict_json_and_wrong_artifact_name(self) -> None:
        arr_path = self.dir / "arr.json"
        arr_path.write_text("[]", encoding="utf-8")
        rep_arr = verify_catalog(arr_path)
        self.assertFalse(rep_arr["valid"])
        self.assertIn("not a JSON object", rep_arr["problems"][0])

        bad_name = self.dir / "badname.json"
        bad_name.write_text(json.dumps({"artifact_name": "other", "classes": {}}), encoding="utf-8")
        rep_name = verify_catalog(bad_name)
        self.assertFalse(rep_name["valid"])
        self.assertTrue(any("artifact_name" in p for p in rep_name["problems"]))

    def test_09_verify_catalog_detects_unsorted_operators_and_unsorted_chains(self) -> None:
        ev = self.dir / "ev.json"
        ev.write_text(json.dumps({"by_class": {"c1": {"admitted_operators": ["z", "a"], "admitted_chains": ["c2", "c1"]}}}))
        out = self.dir / "cat.json"
        materialize(ev, out)
        art = json.loads(out.read_text(encoding="utf-8"))
        art["classes"]["c1"]["operators"] = ["z", "a"]
        out.write_text(json.dumps(art), encoding="utf-8")
        rep = verify_catalog(out)
        self.assertFalse(rep["valid"])
        self.assertTrue(any("canonical (sorted)" in p for p in rep["problems"]))

    def test_10_verify_catalog_detects_corrupt_class_record_types(self) -> None:
        bad = self.dir / "bad_cls.json"
        bad.write_text(
            json.dumps({"artifact_name": ARTIFACT_NAME, "classes": {"c1": {"operators": "not-a-list", "chains": []}}}),
            encoding="utf-8",
        )
        rep = verify_catalog(bad)
        self.assertFalse(rep["valid"])
        self.assertTrue(any("missing or not lists" in p for p in rep["problems"]))
        with self.assertRaises(ValueError):
            load_catalog(bad)

    def test_11_materialize_reproducible_regardless_of_input_order(self) -> None:
        ev1 = self.dir / "ev1.json"
        ev2 = self.dir / "ev2.json"
        ev1.write_text(json.dumps({"by_class": {"b": {"admitted_operators": ["2", "1"]}, "a": {"admitted_chains": ["x"]}}}))
        ev2.write_text(json.dumps({"by_class": {"a": {"admitted_chains": ["x"]}, "b": {"admitted_operators": ["1", "2"]}}}))
        o1, o2 = self.dir / "o1.json", self.dir / "o2.json"
        a1 = materialize(ev1, o1)
        a2 = materialize(ev2, o2)
        self.assertEqual(a1["artifact_digest"], a2["artifact_digest"])
        self.assertEqual(a1["classes"], a2["classes"])


class CatalogGapEdgeTests(unittest.TestCase):
    def test_12_saturation_exact_090_threshold_vs_0899_below(self) -> None:
        rep = {
            "by_class": {
                "at_threshold": _gap_record(eval_tasks=10, eval_solved_baseline=9, eval_solved_extended=9),
                "just_below": _gap_record(eval_tasks=100, eval_solved_baseline=89, eval_solved_extended=89),
            }
        }
        out = analyze_catalog_gaps(rep, {"classes": {}})
        self.assertEqual(out["per_class"]["at_threshold"]["status"], STATUS_SATURATED)
        self.assertEqual(out["per_class"]["just_below"]["status"], STATUS_PARTIAL)

    def test_13_eval_tasks_zero_yields_none_rates_and_not_saturated(self) -> None:
        rep = {
            "by_class": {
                "zero_eval": _gap_record(
                    eval_tasks=0,
                    eval_solved_baseline=0,
                    eval_solved_extended=0,
                    candidate_operators=0,
                )
            }
        }
        out = analyze_catalog_gaps(rep, {"classes": {}})
        entry = out["per_class"]["zero_eval"]
        self.assertEqual(entry["status"], STATUS_PARTIAL)
        self.assertIsNone(entry["baseline_rate"])
        self.assertIsNone(entry["extended_rate"])
        self.assertIsNone(entry["candidate_yield"])

    def test_14_full_solve_with_positive_lift_is_covered_even_above_090_baseline(self) -> None:
        rep = {"by_class": {"almost": _gap_record(eval_tasks=20, eval_solved_baseline=19, eval_solved_extended=20)}}
        out = analyze_catalog_gaps(rep, {"classes": {}})
        self.assertEqual(out["per_class"]["almost"]["status"], STATUS_COVERED)
        self.assertEqual(out["per_class"]["almost"]["lift_tasks"], 1)

    def test_15_universe_duplicates_and_empty_name_rejected(self) -> None:
        with self.assertRaises(CatalogGapError):
            analyze_catalog_gaps({"by_class": {}}, {"classes": {}}, universe_classes=["a", "a"])
        with self.assertRaises(CatalogGapError):
            analyze_catalog_gaps({"by_class": {}}, {"classes": {}}, universe_classes=[""])

    def test_16_blind_spot_validation_rejects_non_list_non_dict_and_empty_name(self) -> None:
        with self.assertRaises(CatalogGapError):
            analyze_catalog_gaps({"by_class": {}}, {"classes": {}}, blind_spots="bad")  # type: ignore[arg-type]
        with self.assertRaises(CatalogGapError):
            analyze_catalog_gaps({"by_class": {}}, {"classes": {}}, blind_spots=["bad"])  # type: ignore[list-item]
        with self.assertRaises(CatalogGapError):
            analyze_catalog_gaps({"by_class": {}}, {"classes": {}}, blind_spots=[{"name": "", "reason": "x"}])

    def test_17_catalog_inconsistency_detected_for_chains_and_missing_ops(self) -> None:
        rep = {"by_class": {"c": _gap_record(admitted_operators=["op1"], admitted_chains=["ch1"])}}
        cat = {"classes": {"c": {"operators": ["op1"], "chains": ["ch_other"]}}}
        out = analyze_catalog_gaps(rep, cat)
        self.assertTrue(out["per_class"]["c"]["in_catalog"])
        self.assertFalse(out["per_class"]["c"]["catalog_consistent"])


class AdmissionHygieneEdgeTests(unittest.TestCase):
    def test_18_operator_mdl_cost_known_unknown_and_chain_scaling(self) -> None:
        self.assertEqual(operator_mdl_cost(("int_delta", (1,), 1)), SCHEMA_MDL_COSTS["int_delta"])
        self.assertEqual(operator_mdl_cost(("brand_new_schema", (1,), 1)), 2.5)
        chain = (("int_delta", (1,), 1), ("string_literal", (2,), "x"))
        expected = SCHEMA_MDL_COSTS["int_delta"] + SCHEMA_MDL_COSTS["string_literal"] + 0.5 * 2
        self.assertAlmostEqual(operator_mdl_cost(chain), expected)
        self.assertEqual(operator_mdl_cost("not-a-tuple"), 3.0)

    def test_19_filter_parsimonious_empty_or_all_below_min_pool_fixes(self) -> None:
        k1 = ("int_delta", (1,), 1)
        selected, stats = filter_parsimonious_keys({k1: {"t1"}}, min_pool_fixes=2)
        self.assertEqual(selected, [])
        self.assertEqual(stats["eligible_before"], 0)
        self.assertEqual(stats["admitted_after"], 0)

    def test_20_filter_parsimonious_deterministic_tiebreak_by_repr(self) -> None:
        ka = ("int_delta", (1,), 1)
        kb = ("int_delta", (1,), 2)
        sel, stats = filter_parsimonious_keys({kb: {"t1", "t2"}, ka: {"t1", "t2"}}, min_pool_fixes=2)
        self.assertEqual(sel, [ka])
        self.assertEqual(stats["pruned_count"], 1)

    def test_21_filter_parsimonious_clean_breakage_prefers_nonbreaking_operator(self) -> None:
        # Even though k_cheap has lower MDL cost, it breaks a clean reference; k_clean must win.
        k_cheap = ("int_delta", (1,), 1)
        k_clean = ("binop_swap", (1,), "Sub")
        selected, stats = filter_parsimonious_keys(
            {k_cheap: {"t1", "t2"}, k_clean: {"t1", "t2"}},
            min_pool_fixes=2,
            reference_codes=["def f(x): return x"],
            apply_fn=lambda ref, k: "BROKEN" if k == k_cheap else "CLEAN",
            adapter=_DummyAdapter("BROKEN"),
            reference_cases=[(1,)],
            reference_truth=[1],
        )
        self.assertEqual(selected, [k_clean])
        self.assertEqual(stats["clean_breakages"][repr(k_cheap)], 1)
        self.assertEqual(stats["clean_breakages"][repr(k_clean)], 0)

    def test_22_filter_parsimonious_min_pool_fixes_one_multi_task_set_cover(self) -> None:
        # When MDL costs differ, greedy selects lower MDL cost first;
        # when MDL costs tie, greater uncovered-task gain wins.
        k1 = ("int_delta", (1,), 1)
        k2 = ("string_literal", (2,), "a")
        k_both_higher_mdl = ("binop_swap", (3,), "Add")
        sel_mdl, _ = filter_parsimonious_keys({k1: {"t1"}, k2: {"t2"}, k_both_higher_mdl: {"t1", "t2"}}, min_pool_fixes=1)
        self.assertEqual(sel_mdl, [k1, k2])

        t1 = ("binop_swap", (1,), "Sub")
        t2 = ("binop_swap", (2,), "Add")
        t_both = ("binop_swap", (3,), "Mult")
        sel_tie, _ = filter_parsimonious_keys({t1: {"t1"}, t2: {"t2"}, t_both: {"t1", "t2"}}, min_pool_fixes=1)
        self.assertEqual(sel_tie, [t_both])


class PreauditValidatorEdgeTests(unittest.TestCase):
    def test_23_parse_json_bytes_rejects_duplicate_keys_nan_infinity_and_bad_utf8(self) -> None:
        with self.assertRaises(pv.ParseError):
            pv.parse_json_bytes(b'{"a": 1, "a": 2}')
        with self.assertRaises(pv.ParseError):
            pv.parse_json_bytes(b'{"a": NaN}')
        with self.assertRaises(pv.ParseError):
            pv.parse_json_bytes(b'{"a": Infinity}')
        with self.assertRaises(pv.ParseError):
            pv.parse_json_bytes(b"\xff\xfe{}")

    def test_24_parse_jsonl_bytes_isolates_malformed_lines_and_skips_blanks(self) -> None:
        raw = b'\n  \n{"seq": 1}\n{bad_json}\n{"seq": 2, "seq": 3}\n{"seq": 4}\n'
        entries, errors = pv.parse_jsonl_bytes(raw)
        self.assertEqual(len(entries), 2)
        self.assertEqual([lineno for lineno, _ in errors], [4, 5])

    def test_25_resolve_pointer_handles_root_list_indices_entry_and_errors(self) -> None:
        doc = [{"seq": 10, "nested": {"arr": ["x", "y"]}}, {"seq": 10}]
        self.assertEqual(pv.resolve_pointer(doc, ""), doc)
        self.assertEqual(pv.resolve_pointer(doc, "/"), doc)
        self.assertEqual(pv.resolve_pointer(doc, "/entry:0/nested/arr/1"), "y")
        with self.assertRaises(pv.PointerError):
            pv.resolve_pointer(doc, "no_leading_slash")
        with self.assertRaises(pv.PointerError):
            pv.resolve_pointer(doc, "/entry:9")
        with self.assertRaises(pv.PointerError):
            pv.resolve_pointer(doc, "/entry_seq:10/nested")  # duplicate seq=10
        with self.assertRaises(pv.PointerError):
            pv.resolve_pointer({"a": 5}, "/a/b")  # scalar descent

    def test_26_values_equal_distinguishes_bool_from_int_and_normalizes_decimal(self) -> None:
        self.assertFalse(pv.values_equal(True, 1))
        self.assertFalse(pv.values_equal(False, 0))
        self.assertTrue(pv.values_equal(Decimal("1e2"), 100))
        self.assertTrue(pv.values_equal([0, {"v": Decimal("0.00")}], [Decimal("0"), {"v": 0}]))

    def test_27_main_rejects_overlapping_source_root_and_out_dir_without_writing(self) -> None:
        with tempfile.TemporaryDirectory(prefix="d2-pv-") as td:
            root = Path(td)
            src = root / "src"
            src.mkdir()
            nested_out = src / "out"
            manifest = root / "manifest.json"
            manifest.write_text("{}", encoding="utf-8")
            rc = pv.main(["--manifest", str(manifest), "--source-root", str(src), "--out-dir", str(nested_out)])
            self.assertEqual(rc, 1)
            self.assertFalse(nested_out.exists())


class AutonomyBudgetBoundaryTests(unittest.TestCase):
    def test_28_budget_usage_from_dict_empty_dict_and_partial_fields(self) -> None:
        empty = BudgetUsage.from_dict({})
        self.assertEqual(empty.steps_used, 0)
        self.assertEqual(empty.retries_by_step, {})
        partial = BudgetUsage.from_dict({"steps_used": 4})
        self.assertEqual(partial.steps_used, 4)
        self.assertEqual(partial.candidates_staged, 0)
        self.assertEqual(partial.wall_seconds_used, 0.0)

    def test_29_budget_usage_from_dict_rejects_non_dict_retries_with_contract_error(self) -> None:
        # Bug yang sudah diperbaiki (2026-11-20): BudgetUsage.from_dict kini
        # memvalidasi retries_by_step bertipe dict dan melempar ValueError,
        # bukan AttributeError mentah dari .items() pada list.
        with self.assertRaises((TypeError, ValueError)):
            BudgetUsage.from_dict({"retries_by_step": ["not-a-dict"]})

    def test_30_budget_controller_exact_ceiling_boundaries_and_finish_zero_delta(self) -> None:
        ctrl = BudgetController(BudgetCeiling(max_steps=1, max_candidates=1, wall_seconds=2.0, cpu_seconds=2.0))
        ctrl.check_pre_step(0, {"tool": "stage_candidate"})
        with patch("ace_autonomy.budget.time.monotonic", side_effect=[10.0, 12.0]), \
                patch("ace_autonomy.budget.total_process_cpu_seconds", side_effect=[1.0, 3.0]):
            tok = ctrl.begin_measurement()
            ctrl.finish_measurement(tok, step_completed=True, staged_candidate=True)
        with self.assertRaises(BudgetExhaustedError):
            ctrl.check_pre_step(1, {"tool": "inspect"})


if __name__ == "__main__":
    unittest.main()
