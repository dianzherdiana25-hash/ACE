"""Catalog gap analysis: the tool classifies measured
classes (gap / saturated / covered / partial), surfaces
unmeasured universe classes, copies declared blind
spots verbatim, and refuses malformed records."""
from __future__ import annotations

import copy
import unittest

from ace_operational.catalog_gap import (
    CatalogGapError, analyze_catalog_gaps)


def _class_record(**overrides):
    record = {"pool_tasks": 3, "candidate_operators": 4,
              "admitted_operators": ["('int_constant', (1,), 0)"],
              "admitted_chains": [],
              "eval_tasks": 10, "eval_solved_baseline": 0,
              "eval_solved_extended": 5}
    record.update(overrides)
    return record


def _report(by_class):
    return {"by_class": by_class}


def _catalog(classes):
    return {"artifact_name": "operator_catalog_test",
            "classes": classes}


EMPTY_CATALOG = _catalog({})


class ClassificationTests(unittest.TestCase):
    def test_zero_admitted_is_a_gap(self):
        report = _report({"hopeless": _class_record(
            candidate_operators=7, admitted_operators=[],
            eval_tasks=6, eval_solved_extended=0)})
        out = analyze_catalog_gaps(report, EMPTY_CATALOG)
        entry = out["per_class"]["hopeless"]
        self.assertEqual(entry["status"], "gap")
        self.assertEqual(entry["admitted_operators"], 0)
        self.assertEqual(len(out["gaps"]), 1)
        gap = out["gaps"][0]
        self.assertEqual(gap["class"], "hopeless")
        self.assertEqual(gap["kind"], "no_admitted_operators")
        # severity = eval tasks the baseline leaves unsolved
        self.assertEqual(gap["severity"], 6)
        self.assertEqual(gap["evidence_strength"], 3 + 6 + 7)

    def test_zero_admitted_with_a_chain_is_not_a_gap(self):
        report = _report({"chainonly": _class_record(
            admitted_operators=[], admitted_chains=["(('a',), ('b',))"],
            eval_solved_extended=2)})
        out = analyze_catalog_gaps(report, EMPTY_CATALOG)
        self.assertEqual(out["per_class"]["chainonly"]["status"],
                         "partial")
        self.assertEqual(out["gaps"], [])

    def test_ceiling_with_zero_lift_is_saturated(self):
        report = _report({"ceiling": _class_record(
            eval_tasks=20, eval_solved_baseline=19,
            eval_solved_extended=19)})
        out = analyze_catalog_gaps(report, EMPTY_CATALOG)
        entry = out["per_class"]["ceiling"]
        self.assertEqual(entry["status"], "saturated")
        self.assertEqual(entry["lift_tasks"], 0)
        self.assertEqual(entry["baseline_rate"], 0.95)
        self.assertEqual(len(out["saturated"]), 1)
        self.assertEqual(out["saturated"][0]["class"], "ceiling")
        self.assertEqual(out["gaps"], [])

    def test_zero_lift_with_low_baseline_is_not_saturated(self):
        report = _report({"stuck": _class_record(
            eval_tasks=10, eval_solved_baseline=2,
            eval_solved_extended=2)})
        out = analyze_catalog_gaps(report, EMPTY_CATALOG)
        self.assertEqual(out["per_class"]["stuck"]["status"], "partial")
        self.assertEqual(out["saturated"], [])

    def test_full_extended_solve_is_covered(self):
        report = _report({"done": _class_record(
            eval_tasks=8, eval_solved_extended=8)})
        out = analyze_catalog_gaps(report, EMPTY_CATALOG)
        entry = out["per_class"]["done"]
        self.assertEqual(entry["status"], "covered")
        self.assertEqual(entry["headroom_tasks"], 0)
        self.assertEqual(entry["extended_rate"], 1.0)

    def test_partial_metrics(self):
        report = _report({"mid": _class_record()})
        out = analyze_catalog_gaps(report, EMPTY_CATALOG)
        entry = out["per_class"]["mid"]
        self.assertEqual(entry["status"], "partial")
        self.assertEqual(entry["lift_tasks"], 5)
        self.assertEqual(entry["lift_rate"], 0.5)
        self.assertEqual(entry["headroom_tasks"], 5)
        self.assertEqual(entry["candidate_yield"], 0.25)
        # the v4 shape carries no pool-fixed count: None, never guessed
        self.assertIsNone(entry["pool_tasks_fixed"])

    def test_pool_tasks_fixed_read_when_present(self):
        report = _report({"v5": _class_record(pool_tasks_fixed=2)})
        out = analyze_catalog_gaps(report, EMPTY_CATALOG)
        self.assertEqual(out["per_class"]["v5"]["pool_tasks_fixed"], 2)


class InventoryTests(unittest.TestCase):
    def test_unmeasured_universe_class_is_a_gap(self):
        report = _report({"seen": _class_record()})
        out = analyze_catalog_gaps(
            report, EMPTY_CATALOG,
            universe_classes=["seen", "never_measured"])
        entry = out["per_class"]["never_measured"]
        self.assertEqual(entry["status"], "unmeasured")
        self.assertEqual(entry["evidence_strength"], 0)
        self.assertEqual([g["class"] for g in out["gaps"]],
                         ["never_measured"])
        self.assertEqual(out["gaps"][0]["kind"], "unmeasured")

    def test_measured_gap_outranks_unmeasured(self):
        report = _report({"hopeless": _class_record(
            admitted_operators=[], eval_solved_extended=0)})
        out = analyze_catalog_gaps(
            report, EMPTY_CATALOG,
            universe_classes=["hopeless", "never_measured"])
        self.assertEqual([g["class"] for g in out["gaps"]],
                         ["hopeless", "never_measured"])

    def test_gap_ranking_by_severity_then_evidence(self):
        report = _report({
            "small": _class_record(
                admitted_operators=[], eval_tasks=4,
                eval_solved_extended=0),
            "big": _class_record(
                admitted_operators=[], eval_tasks=12,
                eval_solved_extended=0),
            "big_weak": _class_record(
                admitted_operators=[], pool_tasks=1,
                candidate_operators=1, eval_tasks=12,
                eval_solved_extended=0),
        })
        out = analyze_catalog_gaps(report, EMPTY_CATALOG)
        self.assertEqual([g["class"] for g in out["gaps"]],
                         ["big", "big_weak", "small"])

    def test_catalog_only_class(self):
        catalog = _catalog({"archived": {
            "operators": ["('binop_swap', (1,), 'Mult')"],
            "chains": []}})
        out = analyze_catalog_gaps(_report({}), catalog)
        entry = out["per_class"]["archived"]
        self.assertEqual(entry["status"], "catalog_only")
        self.assertEqual(entry["admitted_operators"], 1)
        self.assertIsNone(entry["eval_tasks"])
        self.assertEqual(out["gaps"], [])

    def test_catalog_consistency_cross_check(self):
        report = _report({"mid": _class_record()})
        matching = _catalog({"mid": {
            "operators": ["('int_constant', (1,), 0)"], "chains": []}})
        out = analyze_catalog_gaps(report, matching)
        self.assertTrue(out["per_class"]["mid"]["catalog_consistent"])
        different = _catalog({"mid": {
            "operators": ["('binop_swap', (1,), 'Mult')"], "chains": []}})
        out = analyze_catalog_gaps(report, different)
        self.assertFalse(out["per_class"]["mid"]["catalog_consistent"])
        out = analyze_catalog_gaps(report, EMPTY_CATALOG)
        self.assertIsNone(out["per_class"]["mid"]["catalog_consistent"])
        self.assertFalse(out["per_class"]["mid"]["in_catalog"])


class BlindSpotTests(unittest.TestCase):
    def test_blind_spots_copied_verbatim(self):
        declared = [{"name": "statement_order",
                     "reason": "schema enumerates expression edits only",
                     "source": "Addendum 49"}]
        out = analyze_catalog_gaps(_report({}), EMPTY_CATALOG,
                                   blind_spots=declared)
        self.assertEqual(out["blind_spots"], declared)
        # a copy, not an alias: mutating the input changes nothing
        declared[0]["reason"] = "tampered"
        self.assertEqual(out["blind_spots"][0]["reason"],
                         "schema enumerates expression edits only")

    def test_no_blind_spots_declared_means_empty_list(self):
        out = analyze_catalog_gaps(_report({}), EMPTY_CATALOG)
        self.assertEqual(out["blind_spots"], [])

    def test_blind_spot_without_reason_is_rejected(self):
        with self.assertRaises(CatalogGapError):
            analyze_catalog_gaps(_report({}), EMPTY_CATALOG,
                                 blind_spots=[{"name": "x"}])


class DeterminismTests(unittest.TestCase):
    def test_identical_inputs_identical_output(self):
        report = _report({
            "b_class": _class_record(admitted_operators=[],
                                     eval_solved_extended=0),
            "a_class": _class_record(),
        })
        first = analyze_catalog_gaps(
            copy.deepcopy(report), EMPTY_CATALOG,
            universe_classes=["a_class", "b_class", "c_class"])
        second = analyze_catalog_gaps(
            copy.deepcopy(report), EMPTY_CATALOG,
            universe_classes=["c_class", "b_class", "a_class"])
        self.assertEqual(first, second)
        self.assertEqual(list(first["per_class"]),
                         ["a_class", "b_class", "c_class"])


class MalformedInputTests(unittest.TestCase):
    def test_report_must_be_a_dict(self):
        with self.assertRaises(CatalogGapError):
            analyze_catalog_gaps(["not", "a", "dict"], EMPTY_CATALOG)

    def test_missing_by_class(self):
        with self.assertRaises(CatalogGapError):
            analyze_catalog_gaps({"control": {}}, EMPTY_CATALOG)

    def test_missing_count_field(self):
        record = _class_record()
        del record["eval_tasks"]
        with self.assertRaises(CatalogGapError):
            analyze_catalog_gaps(_report({"x": record}), EMPTY_CATALOG)

    def test_negative_count(self):
        with self.assertRaises(CatalogGapError):
            analyze_catalog_gaps(
                _report({"x": _class_record(pool_tasks=-1)}),
                EMPTY_CATALOG)

    def test_bool_is_not_a_count(self):
        with self.assertRaises(CatalogGapError):
            analyze_catalog_gaps(
                _report({"x": _class_record(eval_tasks=True)}),
                EMPTY_CATALOG)

    def test_solved_exceeds_eval_tasks(self):
        with self.assertRaises(CatalogGapError):
            analyze_catalog_gaps(
                _report({"x": _class_record(eval_tasks=4,
                                            eval_solved_extended=5)}),
                EMPTY_CATALOG)

    def test_admitted_must_be_string_list(self):
        with self.assertRaises(CatalogGapError):
            analyze_catalog_gaps(
                _report({"x": _class_record(admitted_operators=[42])}),
                EMPTY_CATALOG)

    def test_duplicate_admitted_keys_rejected(self):
        with self.assertRaises(CatalogGapError):
            analyze_catalog_gaps(
                _report({"x": _class_record(admitted_operators=[
                    "('int_constant', (1,), 0)",
                    "('int_constant', (1,), 0)"])}),
                EMPTY_CATALOG)

    def test_catalog_must_have_classes(self):
        with self.assertRaises(CatalogGapError):
            analyze_catalog_gaps(_report({}), {"artifact_name": "x"})

    def test_catalog_record_must_be_a_dict(self):
        with self.assertRaises(CatalogGapError):
            analyze_catalog_gaps(_report({}), _catalog({"x": ["ops"]}))

    def test_pool_fixed_exceeding_pool_rejected(self):
        with self.assertRaises(CatalogGapError):
            analyze_catalog_gaps(
                _report({"x": _class_record(pool_tasks=2,
                                            pool_tasks_fixed=3)}),
                EMPTY_CATALOG)


if __name__ == "__main__":
    unittest.main()
