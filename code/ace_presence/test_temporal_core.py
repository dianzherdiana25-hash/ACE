from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._contracts import PresenceError, canonical, identity
from .calendar_engine import calendar
from .commitment_tracker import track
from .deadline_risk_forecaster import forecast
from .dialogue_eval import evaluate
from .dialogue_replay import replay
from .duration_estimator import estimate
from .fact_expiry_janitor import mark
from .horizon_planner import plan_horizon
from .moment_memory import recall
from .quota_calendar import quotas
from .rhythm_learner import learn
from .schedule_optimizer import optimize
from .temporal_store import timeline
from .test_rolling_summary import sample, save
from .time_bench import bench
from .workload_forecaster import project

def at(hhmm, date="2025-05-01"):
    return f"{date}T{hhmm}:00Z"

def fact_plan():
    return {"schema": "ace.presence.facts-plan.v1", "as_of": "2025-05-02", "events": [
        {"id": "first", "fact": "lab", "value": "A", "from": "2025-05-01", "until": None, "source": "r1", "supersedes": None},
        {"id": "second", "fact": "lab", "value": "B", "from": "2025-05-02", "until": "2025-05-03", "source": "r2", "supersedes": "first"},
    ]}

def quota_plan():
    return {"schema": "ace.presence.quota-plan.v1", "as_of": at("19:00"),
            "providers": [{"id": "vendor", "limit": 10, "zone": "Asia/Jakarta"}],
            "usage": [{"id": key, "provider": "vendor", "at": at(time), "units": units, "source": key}
                      for key, time, units in [("old", "16:59", 8), ("new", "17:00", 3)]]}

def call(operation, plan, *args):
    return operation(plan, identity(plan), *args)

class TimeCoreTests(unittest.TestCase):
    def test_16_validity_is_half_open_and_revision_remains_in_history(self):
        plan = fact_plan()
        report = call(timeline, plan)
        self.assertEqual(report["active"]["lab"]["value"], "B")
        self.assertEqual(report["history"]["lab"][0]["until"], "2025-05-02")
        self.assertIsNone(plan["events"][0]["until"])
        plan["as_of"] = "2025-05-03"
        self.assertEqual(call(timeline, plan)["active"], {})

    def test_17_local_day_covers_23_hours_on_dst_advance(self):
        plan = {"schema": "ace.presence.calendar-plan.v1", "day": "2025-03-09", "zone": "America/New_York",
                "events": [{"id": key, "start": at(start, "2025-03-09"), "end": at(end, "2025-03-09"),
                            "title": key, "source": "fixture"} for key, start, end in
                           [("before", "04:00", "05:00"), ("overlap", "04:30", "06:30")]]}
        report = call(calendar, plan)
        self.assertEqual(report["utc_window"], ["2025-03-09T05:00:00Z", "2025-03-10T04:00:00Z"])
        self.assertEqual([row["id"] for row in report["events"]], ["overlap"])

    def test_18_reverse_dag_deadlines_keep_critical_path_and_reject_cycles(self):
        plan = {"schema": "ace.presence.horizon-plan.v1", "start": at("09:00"), "deadline": at("10:00"),
                "milestones": [{"id": key, "minutes": duration, "requires": deps, "source": key} for key, duration, deps in
                               [("draft", 30, []), ("review", 20, ["draft"]), ("package", 10, ["draft"])]]}
        report = call(plan_horizon, plan)
        self.assertTrue(report["can_fit_parallel"])
        self.assertEqual(report["milestones"][0]["latest_start"], at("09:10"))
        plan["milestones"][0]["requires"] = ["review"]
        with self.assertRaises(PresenceError):
            call(plan_horizon, plan)

    def test_19_rhythm_accounts_exact_minutes_across_midnight(self):
        plan = {"schema": "ace.presence.rhythm-plan.v1",
                "records": [{"start": at("23:40"), "end": at("00:25", "2025-05-02"), "source": "shift"}]}
        self.assertEqual([(row["utc_hour"], row["minutes"]) for row in call(learn, plan)["buckets"]], [(23, 20), (0, 25)])

    def test_20_risk_shows_uncertainty_for_unknown_class(self):
        plan = {"schema": "ace.presence.deadline-risk.v1", "history": [
            {"kind": "report", "minutes": minutes} for minutes in (10, 15, 20, 50)], "minimum_sample": 3,
                "tasks": [{"id": "alpha", "kind": "report", "minutes_to_deadline": 15},
                          {"id": "beta", "kind": "code", "minutes_to_deadline": 30}]}
        rows = call(forecast, plan)["tasks"]
        self.assertEqual(rows[0]["past_misses"], 2)
        self.assertEqual(rows[0]["probability"], "1/2")
        self.assertIsNone(rows[1]["probability"])

    def test_21_commitment_uses_exact_warning_boundary_and_evidence(self):
        plan = {"schema": "ace.presence.commitments.v1", "as_of": "2025-05-03", "alert_days": 2,
                "promises": [{"id": key, "due_on": f"2025-05-0{day}", "action": key, "source": "journal"}
                             for key, day in [("late", 1), ("closed", 2), ("warn", 5), ("future", 6)]],
                "resolutions": [{"id": "closed", "at": "2025-05-03", "source": "receipt"}]}
        rows = call(track, plan)["commitments"]
        self.assertEqual([row["status"] for row in rows], ["overdue", "fulfilled", "due_soon", "open"])
        self.assertEqual(rows[1]["resolution_source"], "receipt")

    def test_22_expiry_keeps_holds_and_does_not_mutate_facts(self):
        plan = {"schema": "ace.presence.expiry-plan.v1", "as_of": "2025-05-03", "facts": [
            {"id": key, "until": "2025-05-03", "source": "sample.md", "hold": hold}
            for key, hold in [("retire", False), ("retain", True)]]}
        raw = canonical(plan)
        report = call(mark, plan)
        self.assertEqual(report["expire_candidates"][0]["id"], "retire")
        self.assertEqual(report["retained"], [{"id": "retain", "reason": "held"}])
        self.assertEqual(canonical(plan), raw)

    def test_23_schedule_optimization_minimizes_weighted_move(self):
        plan = {"schema": "ace.presence.optimize-plan.v1", "busy": [{"start": at("09:30"), "end": at("10:00")}],
                "missions": [{"id": key, "duration": 30, "preferred": at("09:00"),
                              "starts": [at("09:00"), at("09:30"), at("10:00")], "weight": cost}
                             for key, cost in [("urgent", 4), ("normal", 1)]]}
        report = call(optimize, plan)
        self.assertEqual(report, {"feasible": True, "cost": 60, "starts": {"normal": at("10:00"), "urgent": at("09:00")}})

    def test_24_anniversary_filters_topic_and_keeps_original_source(self):
        plan = {"schema": "ace.presence.moments-plan.v1", "as_of": "2025-01-01", "topic": "panel",
                "tolerance_days": 1, "events": [
                    {"id": key, "date": "2023-12-31", "recur_annually": True, "summary": topic, "source": key}
                    for key, topic in [("sensor", "panel upload"), ("other", "calibration")]]}
        result = call(recall, plan)["matches"]
        self.assertEqual([(row["id"], row["relevant_on"], row["source"]) for row in result],
                         [("sensor", "2024-12-31", "sensor")])

    def test_25_duration_uses_nearest_complexity_and_keeps_ties(self):
        plan = {"schema": "ace.presence.duration-plan.v1", "kind": "repair", "complexity": 5,
                "minimum_samples": 2, "history": [{"kind": "repair", "complexity": level,
                "minutes": length, "source": f"trace:{level}"} for level, length in [(1, 2), (4, 20), (5, 10), (6, 60)]]}
        report = call(estimate, plan)
        self.assertEqual((report["samples"], report["median_minutes"], report["p90_minutes"]), (3, 20, 60))

    def test_26_workload_splits_partial_spans_exactly(self):
        plan = {"schema": "ace.presence.workload.v1",
                "windows": [{"id": "am", "start": at("09:00"), "end": at("10:00"), "capacity_minutes": 20}],
                "jobs": [{"id": "load", "start": at("09:30"), "end": at("10:30"), "estimated_minutes": 45, "source": "e"}]}
        row = call(project, plan)["windows"][0]
        self.assertEqual(row["load_minutes"], "45/2")
        self.assertTrue(row["overbooked"])

    def test_27_provider_timezone_reset(self):
        row = call(quotas, quota_plan())["providers"]["vendor"]
        self.assertEqual((row["day"], row["used"], row["remaining"]), ("2025-05-02", 3, 7))

    def test_28_eval_detects_both_wrong_recall_and_fabricated_summary(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            ref, source = sample(root)
            plan = {"schema": "ace.presence.dialogue-eval.v1", "dialogue": ref,
                    "gold": [{"id": "opening", "kind": "fact"}, {"id": "next", "kind": "promise"}],
                    "recalled": [{"id": "opening", "kind": "fact", "turn_sha256": source["events"][0]["sha256"]},
                                 {"id": "next", "kind": "promise", "turn_sha256": source["events"][1]["sha256"]}],
                    "summary": [{"id": "opening", "message": "Data disappeared.",
                                 "turn_sha256": source["events"][0]["sha256"]}]}
            report = call(evaluate, plan, root)
            self.assertEqual(report["recall"], "1/2")
            self.assertEqual(report["invalid_recall"], ["next"])
            self.assertEqual(report["unsupported_summary"], ["opening"])

    def test_29_replay_range_keeps_link_back_to_prior_turn(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            ref, source = sample(root)
            plan = {"schema": "ace.presence.replay-plan.v1", "dialogue": ref, "start_seq": 2, "stop_seq": 3}
            report = call(replay, plan, root)
            self.assertEqual(report["events"], source["events"][1:3])
            self.assertEqual(report["prior_sha256"], source["events"][0]["sha256"])

    def test_30_bench_measures_partial_failure_positively_and_negatively(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            cases = [{"id": "active", "kind": "active_fact_ids", "input": fact_plan()},
                     {"id": "quota", "kind": "quota_remaining", "input": quota_plan()}]
            plan = {"schema": "ace.presence.time-bench.v1",
                    "cases": save(root, "cases.json", canonical(cases)),
                    "labels": save(root, "labels.json", canonical({"active": ["lab"], "quota": {"vendor": 6}}))}
            report = call(bench, plan, root)
            self.assertEqual((report["correct"], report["evaluated"], report["accuracy"]), (1, 2, "1/2"))
            self.assertEqual(report["results"][1]["observed"], {"vendor": 7})
