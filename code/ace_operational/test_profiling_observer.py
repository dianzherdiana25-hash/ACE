"""Tests for the observer-only profiling pilot (development band).

Pins: schema shape; ProfilingBudget == Budget scores (the observer
must not change what the solver decides); instrumented == plain
solve results; queue wait / cache explicitly N/A; self-time
accounting without double-counting; completeness reconciliation
(dropped=0 alone is not completeness); fail-open collection.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from ace_operational import pilot_abc
from ace_operational.curriculum_lab import generate_task
from ace_operational.profiling_observer import (
    PHASES,
    SCHEMA_VERSION,
    Collector,
    PhaseAggregator,
    ProfilingBudget,
    analyze_pilot,
    instrumented_solver,
    load_sidecar,
    run_dev_pilot,
    validate_sidecar,
)
from ace_operational.reasoning_lab import Budget


def _budget_pair(task, agg):
    shown = [tuple(c) for c in task["shown_cases"]]
    by_case = {tuple(c): e for c, e in zip(task["cases"], task["expected"])}
    kw = dict(entrypoint=task["entrypoint"], shown_cases=shown,
              shown_expected=[by_case[c] for c in shown])
    return (Budget(200, **kw),
            ProfilingBudget(200, aggregator=agg, **kw))


class BudgetEquivalenceTests(unittest.TestCase):
    def setUp(self):
        self.tasks = []
        for family in ("pricing", "shipping"):
            for seed in range(1, 7):
                try:
                    self.tasks.append(generate_task(family, 1, seed=seed))
                except Exception:
                    continue
        self.assertTrue(self.tasks)

    def test_profiling_budget_scores_identically(self):
        with tempfile.TemporaryDirectory() as td:
            collector = Collector(Path(td), "run-x")
            for task in self.tasks:
                agg = PhaseAggregator(collector, "job-x")
                plain, prof = _budget_pair(task, agg)
                codes = [task["buggy_code"], task["reference_code"],
                         "def broken(:\n", "x = 1\n"]
                groups = pilot_abc.variants_by_group(task["buggy_code"],
                                                     task["spec"])
                for group in groups.values():
                    codes.extend(group[:3])
                for code in codes:
                    self.assertEqual(plain.score(code), prof.score(code),
                                     "observer changed a score")
                self.assertEqual(plain.used, prof.used)

    def test_cache_compiles_budget_scores_identically(self):
        # Post-parse-once instrument mirror: memoised compile must
        # not change any score (mirrors pilot_abc.CachingBudget).
        with tempfile.TemporaryDirectory() as td:
            collector = Collector(Path(td), "run-x")
            for task in self.tasks[:3]:
                agg = PhaseAggregator(collector, "job-x")
                shown = [tuple(c) for c in task["shown_cases"]]
                by_case = {tuple(c): e for c, e in
                           zip(task["cases"], task["expected"])}
                kw = dict(entrypoint=task["entrypoint"],
                          shown_cases=shown,
                          shown_expected=[by_case[c] for c in shown])
                from ace_operational.reasoning_lab import Budget
                plain = Budget(200, **kw)
                prof = ProfilingBudget(200, aggregator=agg,
                                       cache_compiles=True, **kw)
                codes = [task["buggy_code"], task["reference_code"],
                         "def broken(:\n", task["buggy_code"],
                         task["reference_code"]]
                for code in codes:
                    self.assertEqual(plain.score(code), prof.score(code))
                self.assertEqual(plain.used, prof.used)
                self.assertEqual(len(prof._compiled), 2)

    def test_shadow_counter_is_not_a_cache(self):
        with tempfile.TemporaryDirectory() as td:
            collector = Collector(Path(td), "run-x")
            agg = PhaseAggregator(collector, "job-x")
            _, prof = _budget_pair(self.tasks[0], agg)
            code = self.tasks[0]["buggy_code"]
            first = prof.score(code)
            second = prof.score(code)  # genuinely recomputed
            self.assertEqual(first, second)
            self.assertEqual(prof.potential_hits, 1)
            self.assertEqual(prof.distinct_keys, 1)


class InstrumentedSolveTests(unittest.TestCase):
    def test_instrumented_solve_matches_plain_solve(self):
        tasks = []
        for seed in range(1, 7):
            try:
                tasks.append(generate_task("pricing", 2, seed=seed))
            except Exception:
                continue
        self.assertTrue(tasks)
        with tempfile.TemporaryDirectory() as td:
            collector = Collector(Path(td), "run-x")
            for task in tasks:
                public = pilot_abc._public(task)
                plain, _ = _budget_pair(task, PhaseAggregator(collector, "j"))
                expected = pilot_abc.solve_with_config(
                    public, plain, pilot_abc.BASE_CONFIG)
                agg = PhaseAggregator(collector, "job-y")
                _, prof = _budget_pair(task, agg)
                with instrumented_solver(agg):
                    got = pilot_abc.solve_with_config(
                        public, prof, pilot_abc.BASE_CONFIG)
                self.assertEqual(expected["code"], got["code"])
                self.assertEqual(expected["shown_score"],
                                 got["shown_score"])
                self.assertEqual(expected["evals"], got["evals"])
                # all solver phases were observed
                for phase in ("enumeration", "transform_serialize",
                              "parse", "compile", "exec_shown"):
                    self.assertIn(phase, agg.totals)
            # hooks fully removed after the context
            self.assertIs(pilot_abc.variants_by_group.__module__,
                          pilot_abc.__name__)


class CollectorTests(unittest.TestCase):
    def test_span_self_time_excludes_children(self):
        import time
        with tempfile.TemporaryDirectory() as td:
            collector = Collector(Path(td), "run-x")
            with collector.span("exec_shown", job_id="j") as parent:
                with collector.span("parse", job_id="j",
                                    parent_span_id=parent["span_id"]):
                    time.sleep(0.01)
                time.sleep(0.01)
            collector.footer(jobs_registered=0, jobs_completed=0,
                             completeness="complete")
            manifest = {"jobs_registered": 0,
                        "segments": collector.segments}
            (Path(td) / "profiling_manifest.json").write_text(
                json.dumps(manifest))
            _, events = load_sidecar(Path(td))
            spans = {e["phase"]: e for e in events
                     if e.get("type") == "phase_span"}
            parent_span = spans["exec_shown"]
            child = spans["parse"]
            self.assertAlmostEqual(
                parent_span["wall_self_s"] + child["wall_inclusive_s"],
                parent_span["wall_inclusive_s"], places=3)
            self.assertLess(parent_span["wall_self_s"],
                            parent_span["wall_inclusive_s"])

    def test_disabled_collector_is_a_noop(self):
        collector = Collector(Path("/nonexistent"), "run-x",
                              enabled=False)
        self.assertFalse(collector.emit({"type": "job_lifecycle"}))
        self.assertEqual(collector.dropped_events, 0)

    def test_validation_rejects_missing_footer(self):
        manifest = {"jobs_registered": 1, "segments": []}
        events = [{"seq": 1, "type": "job_summary",
                   "completeness": "complete"}]
        verdict = validate_sidecar(manifest, events)
        self.assertFalse(verdict["complete"])
        self.assertTrue(any("footer" in p for p in verdict["problems"]))

    def test_validation_rejects_dropped_events(self):
        manifest = {"jobs_registered": 0, "segments": []}
        events = [{"seq": 1, "type": "run_footer", "jobs_registered": 0,
                   "jobs_completed": 0, "dropped_events": 3,
                   "completeness": "complete"}]
        verdict = validate_sidecar(manifest, events)
        self.assertFalse(verdict["complete"])


class DevPilotTests(unittest.TestCase):
    def test_pilot_sidecar_schema_and_na_fields(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "run"
            run_dev_pilot(out_dir=out, levels=(1,), seeds=(1, 2),
                          reps=1)
            manifest, events = load_sidecar(out)
            self.assertEqual(manifest["schema_version"], SCHEMA_VERSION)
            for key in ("digests", "clock_domains", "job_process_model",
                        "timeout_policy", "retention_rotation",
                        "jobs_registered"):
                self.assertIn(key, manifest)
            verdict = validate_sidecar(manifest, events)
            self.assertTrue(verdict["complete"], verdict["problems"])
            summaries = [e for e in events
                         if e.get("type") == "job_summary"]
            self.assertTrue(summaries)
            for s in summaries:
                # queue wait explicitly N/A — no coordinator
                self.assertIsNone(s["queue_wait"]["value"])
                self.assertEqual(s["queue_wait"]["availability"],
                                 "unavailable")
                # cache hit/miss N/A; shadow counters under own name
                self.assertIsNone(s["cache"]["hit"])
                self.assertIsNone(s["cache"]["miss"])
                self.assertIn("potential_hits", s["cache"])
                # outcome split into three non-ambiguous fields
                self.assertIn("solved", s)
                self.assertIn("termination_reason", s)
                self.assertIn("infra_status", s)
                self.assertIn("logical_score_calls", s)
                self.assertIn("peak_rss", s)
                self.assertIn("io_bytes", s)
            phases_seen = {e["phase"] for e in events
                           if e.get("type") == "phase_span"}
            for phase in PHASES:
                self.assertIn(phase, phases_seen)
            analysis = analyze_pilot(out)
            self.assertEqual(analysis["scientific_field_mismatches"], [])
            self.assertTrue(analysis["completeness"]["complete"])
            self.assertEqual(
                len(analysis["phase_ranking_attributed"]), 8)


if __name__ == "__main__":
    unittest.main()
