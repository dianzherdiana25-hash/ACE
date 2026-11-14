"""Weakness-targeting curriculum generator: targeting
follows the gap report's ranking (gaps first, partials
by headroom, saturated/covered never), every shipped
task passes the identifiability control (exposure,
plus rival discrimination when the source can name
rivals), shortfalls are counted rather than padded,
and malformed input is refused."""
from __future__ import annotations

import unittest

from ace_operational.curriculum_generator import (
    CurriculumGenError, generate_practice_set)


# ------------------------------------------------------------------
# synthetic gap report (catalog_gap output shape)
# ------------------------------------------------------------------

def _entry(status, headroom=None):
    return {"status": status, "headroom_tasks": headroom}


def _report():
    per_class = {
        "gap_measured": _entry("gap", headroom=6),
        "gap_unmeasured": _entry("unmeasured"),
        "partial_small": _entry("partial", headroom=3),
        "partial_big": _entry("partial", headroom=9),
        "sat_class": _entry("saturated", headroom=0),
        "cov_class": _entry("covered", headroom=0),
    }
    gaps = [
        {"class": "gap_measured", "kind": "no_admitted_operators",
         "severity": 6, "evidence_strength": 10,
         "reason": "measured but nothing admitted"},
        {"class": "gap_unmeasured", "kind": "unmeasured",
         "severity": 0, "evidence_strength": 0,
         "reason": "declared but never measured"},
    ]
    return {"per_class": per_class, "gaps": gaps,
            "saturated": [{"class": "sat_class"}], "blind_spots": []}


# ------------------------------------------------------------------
# fake task source: codes are labels, run() reads a
# behaviour table. The buggy program fails shown
# case 1 and passes shown case 2.
# ------------------------------------------------------------------

BEHAVIOURS = {
    "buggy": {1: "wrong", 2: "b"},
    "buggy_clean": {1: "a", 2: "b"},
    "rival_fail": {1: "also-wrong", 2: "b"},
    "rival_pass": {1: "a", 2: "b"},
}


class FakeSource:
    name = "fake_family"

    def __init__(self, rivals_mode="discriminating", buggy="buggy",
                 fail_first=False, constant_id=False):
        self.rivals_mode = rivals_mode
        self.buggy = buggy
        self.fail_first = fail_first
        self.constant_id = constant_id
        self.build_calls: list[tuple[str, int]] = []

    def build(self, class_name, seed):
        self.build_calls.append((class_name, seed))
        if self.fail_first and \
                sum(1 for cls, _ in self.build_calls
                    if cls == class_name) == 1:
            return None
        task_id = "fake-constant" if self.constant_id \
            else f"fake-{class_name}-{seed}"
        return {"task_id": task_id, "defects": [class_name],
                "buggy_code": self.buggy,
                "shown_cases": [1, 2], "shown_truth": ["a", "b"],
                "holdout_cases": [3], "holdout_truth": ["c"]}

    def run(self, code, case):
        return BEHAVIOURS[code][case]

    def rivals(self, task):
        if self.rivals_mode == "discriminating":
            return [("rival_fail", "rival_fail"),
                    ("rival_pass", "rival_pass")]
        if self.rivals_mode == "all_pass":
            return [("rival_pass", "rival_pass")]
        return None  # "none": no rivals constructible


def _one_gap_report():
    return {"per_class": {"only_gap": _entry("gap", headroom=4)},
            "gaps": [{"class": "only_gap",
                      "kind": "no_admitted_operators", "severity": 4,
                      "evidence_strength": 5, "reason": "r"}],
            "saturated": [], "blind_spots": []}


# ------------------------------------------------------------------
# targeting
# ------------------------------------------------------------------

class TargetingTests(unittest.TestCase):
    def test_gaps_first_then_partials_by_headroom(self):
        source = FakeSource()
        manifest = generate_practice_set(
            _report(), source, seed=7, tasks_per_gap=1,
            tasks_per_partial=1, max_attempts=2)
        order = [r["class"] for r in manifest["targeting"]]
        self.assertEqual(
            order, ["gap_measured", "gap_unmeasured",
                    "partial_big", "partial_small"])
        self.assertEqual(manifest["totals"]["built"], 4)
        self.assertEqual(manifest["totals"]["requested"], 4)

    def test_saturated_and_covered_never_built(self):
        source = FakeSource()
        manifest = generate_practice_set(
            _report(), source, seed=7, tasks_per_gap=1,
            tasks_per_partial=1, max_attempts=2)
        built_for = {cls for cls, _ in source.build_calls}
        self.assertNotIn("sat_class", built_for)
        self.assertNotIn("cov_class", built_for)
        excluded = {e["class"]: e for e in manifest["excluded"]}
        self.assertEqual(excluded["sat_class"]["status"], "saturated")
        self.assertIn("saturated", excluded["sat_class"]["reason"])
        self.assertEqual(excluded["cov_class"]["status"], "covered")

    def test_class_limit_defers_remaining_targets(self):
        source = FakeSource()
        manifest = generate_practice_set(
            _report(), source, seed=7, tasks_per_gap=1,
            tasks_per_partial=1, max_attempts=2, class_limit=2)
        self.assertEqual([r["class"] for r in manifest["targeting"]],
                         ["gap_measured", "gap_unmeasured"])
        deferred = {e["class"] for e in manifest["excluded"]}
        self.assertIn("partial_big", deferred)
        self.assertIn("partial_small", deferred)


# ------------------------------------------------------------------
# identifiability control
# ------------------------------------------------------------------

class IdentifiabilityTests(unittest.TestCase):
    def test_discriminating_annotation(self):
        manifest = generate_practice_set(
            _one_gap_report(), FakeSource(), seed=3, tasks_per_gap=1,
            tasks_per_partial=0, max_attempts=2)
        task = manifest["tasks"][0]
        ident = task["identifiability"]
        self.assertEqual(ident["level"], "discriminating")
        self.assertEqual(ident["shown_cases"], 2)
        self.assertEqual(ident["buggy_shown_failures"], 1)
        self.assertEqual(ident["rivals_checked"], 2)
        self.assertEqual(ident["rivals_failing_shown"], 1)
        self.assertEqual(ident["rivals_not_excluded"], ["rival_pass"])
        self.assertEqual(
            manifest["totals"]["by_identifiability"],
            {"discriminating": 1})

    def test_shown_only_when_no_rivals(self):
        manifest = generate_practice_set(
            _one_gap_report(), FakeSource(rivals_mode="none"), seed=3,
            tasks_per_gap=1, tasks_per_partial=0, max_attempts=2)
        ident = manifest["tasks"][0]["identifiability"]
        self.assertEqual(ident["level"], "shown_only")
        self.assertIsNone(ident["rivals_checked"])
        self.assertIsNone(ident["rivals_failing_shown"])

    def test_shown_only_for_dict_source_without_rivals(self):
        fake = FakeSource()
        source = {"build": fake.build, "run": fake.run,
                  "name": "dict_family"}
        manifest = generate_practice_set(
            _one_gap_report(), source, seed=3, tasks_per_gap=1,
            tasks_per_partial=0, max_attempts=2)
        self.assertEqual(manifest["source"], "dict_family")
        self.assertEqual(
            manifest["tasks"][0]["identifiability"]["level"],
            "shown_only")

    def test_unexposed_defect_is_rejected_not_shipped(self):
        source = FakeSource(buggy="buggy_clean")
        manifest = generate_practice_set(
            _one_gap_report(), source, seed=3, tasks_per_gap=1,
            tasks_per_partial=0, max_attempts=3)
        record = manifest["targeting"][0]
        self.assertEqual(record["built"], 0)
        self.assertEqual(record["shortfall"], 1)
        self.assertEqual(
            record["rejected"]["shown_does_not_expose_defect"], 3)
        self.assertEqual(manifest["tasks"], [])

    def test_all_rivals_passing_is_rejected(self):
        source = FakeSource(rivals_mode="all_pass")
        manifest = generate_practice_set(
            _one_gap_report(), source, seed=3, tasks_per_gap=1,
            tasks_per_partial=0, max_attempts=3)
        record = manifest["targeting"][0]
        self.assertEqual(record["built"], 0)
        self.assertEqual(
            record["rejected"]["shown_consistent_with_all_rivals"], 3)

    def test_generation_failure_is_retried(self):
        source = FakeSource(fail_first=True)
        manifest = generate_practice_set(
            _one_gap_report(), source, seed=3, tasks_per_gap=1,
            tasks_per_partial=0, max_attempts=3)
        record = manifest["targeting"][0]
        self.assertEqual(record["built"], 1)
        self.assertEqual(record["rejected"]["generation_failure"], 1)

    def test_duplicate_task_id_is_rejected(self):
        source = FakeSource(constant_id=True)
        manifest = generate_practice_set(
            _one_gap_report(), source, seed=3, tasks_per_gap=2,
            tasks_per_partial=0, max_attempts=2)
        record = manifest["targeting"][0]
        self.assertEqual(record["built"], 1)
        self.assertEqual(record["rejected"]["duplicate_task_id"], 2)
        self.assertEqual(record["shortfall"], 1)


# ------------------------------------------------------------------
# determinism + fail-closed validation
# ------------------------------------------------------------------

class DeterminismAndValidationTests(unittest.TestCase):
    def test_same_seed_same_manifest(self):
        first = generate_practice_set(
            _report(), FakeSource(), seed=11, tasks_per_gap=1,
            tasks_per_partial=1, max_attempts=2)
        second = generate_practice_set(
            _report(), FakeSource(), seed=11, tasks_per_gap=1,
            tasks_per_partial=1, max_attempts=2)
        self.assertEqual(first, second)

    def test_different_seed_changes_build_schedule(self):
        first = generate_practice_set(
            _one_gap_report(), FakeSource(), seed=1, tasks_per_gap=1,
            tasks_per_partial=0, max_attempts=2)
        second = generate_practice_set(
            _one_gap_report(), FakeSource(), seed=2, tasks_per_gap=1,
            tasks_per_partial=0, max_attempts=2)
        self.assertNotEqual(first["tasks"][0]["build_seed"],
                            second["tasks"][0]["build_seed"])

    def test_malformed_reports_raise(self):
        bad_reports = [
            "not a dict",
            {"gaps": []},  # no per_class
            {"per_class": {}, "gaps": "not a list"},
            {"per_class": {"x": {"status": "mystery",
                                 "headroom_tasks": 1}}, "gaps": []},
            {"per_class": {"x": _entry("partial")},  # headroom None
             "gaps": []},
            {"per_class": {}, "gaps": [{"class": "ghost",
                                        "kind": "unmeasured"}]},
        ]
        for report in bad_reports:
            with self.subTest(report=report):
                with self.assertRaises(CurriculumGenError):
                    generate_practice_set(
                        report, FakeSource(), tasks_per_gap=1,
                        tasks_per_partial=0)

    def test_bad_quotas_raise(self):
        for kwargs in ({"tasks_per_gap": 0, "tasks_per_partial": 0},
                       {"tasks_per_gap": -1},
                       {"tasks_per_gap": 1, "max_attempts": 0},
                       {"tasks_per_gap": 1, "class_limit": 0}):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(CurriculumGenError):
                    generate_practice_set(
                        _one_gap_report(), FakeSource(), **kwargs)

    def test_broken_source_raises(self):
        with self.assertRaises(CurriculumGenError):
            generate_practice_set(
                _one_gap_report(), {"build": None, "run": lambda c, k: 1},
                tasks_per_gap=1, tasks_per_partial=0)

    def test_task_for_the_wrong_class_raises(self):
        class WrongClassSource(FakeSource):
            def build(self, class_name, seed):
                task = super().build(class_name, seed)
                task["defects"] = ["some_other_class"]
                return task

        with self.assertRaises(CurriculumGenError):
            generate_practice_set(
                _one_gap_report(), WrongClassSource(), tasks_per_gap=1,
                tasks_per_partial=0, max_attempts=1)

    def test_task_without_shown_cases_raises(self):
        class EmptyShownSource(FakeSource):
            def build(self, class_name, seed):
                task = super().build(class_name, seed)
                task["shown_cases"] = []
                task["shown_truth"] = []
                return task

        with self.assertRaises(CurriculumGenError):
            generate_practice_set(
                _one_gap_report(), EmptyShownSource(), tasks_per_gap=1,
                tasks_per_partial=0, max_attempts=1)


if __name__ == "__main__":
    unittest.main()
