from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._contracts import PresenceError, canonical, identity
from ._journal import Journal
from .best_time_advisor import advise
from .daily_agenda import agenda
from .day_archiver import archive
from .deadline_collision import collide
from .dialogue_satisfaction import measure
from .estimate_calibrator import calibrate
from .greeting_keeper import greeting
from .owner_rhythm import rhythm
from .persona_continuity import audit
from .presence_quality import quality
from .presence_report import report
from .recurring_reminder import expand
from .register_switcher import render
from .reschedule_proposer import propose
from .shared_history_answerer import answer
from .smart_dnd import decide
from .test_dialogue_server import turn
from .test_rolling_summary import sample, save
from .test_temporal_core import at, call
from .topic_boundary_guard import check
from .topic_waitlist import queue
from .weekly_review import review
from .while_away_brief import brief

class AdvancedPresenceTests(unittest.TestCase):
    def test_41_history_requires_grant_and_actor_in_session(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            first, data = sample(root)
            second, _ = sample(root, "other")
            plan = {"schema": "ace.presence.shared-history.v1", "participant": "quoted", "query": "kalibrasi panel",
                    "after": "2025-05-01", "through": "2025-05-01", "max_quotes": 5, "sessions": [
                        {"ref": first, "shared_with": ["quoted"]}, {"ref": second, "shared_with": ["guest"]}]}
            rows = call(answer, plan, root)["quotes"]
            self.assertEqual(len(rows), 2)
            self.assertEqual({row["turn_sha256"] for row in rows}, {value["sha256"] for value in data["events"][:2]})
            plan["participant"] = "guest"
            self.assertEqual(call(answer, plan, root)["status"], "no_evidence")

    def test_42_topic_rules_apply_to_full_width_and_unknown_goes_to_review(self):
        plan = {"schema": "ace.presence.topic-boundary.v1", "channel": "help",
                "policies": [{"channel": "help", "topics": [{"id": "draft", "allow": False, "phrases": ["secret code"]}]}],
                "message": "Hidden ＳＥＣＲＥＴ CODE.", "tags": ["new_topic"]}
        self.assertEqual(call(check, plan), {"status": "blocked", "blocked": ["draft"], "unrecognized": ["new_topic"]})
        plan["message"] = "Something else."
        self.assertEqual(call(check, plan)["status"], "review")

    def test_43_formal_and_casual_keep_facts_and_reject_omission(self):
        plan = {"schema": "ace.presence.register-plan.v1", "channel": "app",
                "policy": [{"channel": "app", "mode": "formal", "allow_override": True}], "request": "casual",
                "facts": {"time": "09:00", "count": "14"},
                "templates": {"formal": "At {time} there are {count}.", "casual": "{count} ready at {time}."}}
        self.assertEqual(call(render, plan)["text"], "14 ready at 09:00.")
        plan["templates"]["formal"] = "At {time}."
        with self.assertRaises(PresenceError):
            call(render, plan)

    def test_44_feedback_does_not_treat_reply_without_signal_as_rating(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            journal = Journal(root / "survey.sqlite")
            journal.append(turn())
            journal.append(turn("respond", "assistant", "opening", "Observation."))
            journal.append(turn("rated", "user", "respond", "Feedback [helpful]: Yes."))
            ref = save(root, "survey.json", canonical(journal.export("fixture")))
            plan = {"schema": "ace.presence.satisfaction.v1", "dialogue": ref}
            result = call(measure, plan, root)
            self.assertEqual(result["helpful_fraction"], "1")
            self.assertEqual(result["replies_without_signal"], 1)
            self.assertEqual(result["feedback"][0]["reply_to"], "respond")

    def test_45_rhythm_includes_zero_days_and_only_allowed_calendar(self):
        plan = {"schema": "ace.presence.owner-rhythm.v1", "zone": "UTC", "first": "2025-05-01", "last": "2025-05-08",
                "calendar": [{"start": at("09:00"), "end": at("10:00"), "source": "included", "include": True},
                             {"start": at("11:00"), "end": at("12:00"), "source": "private", "include": False}]}
        thursday = call(rhythm, plan)["weekdays"][3]
        self.assertEqual(thursday, {"weekday": 3, "observed_dates": 2, "average_booked_minutes": "30", "sources": ["included"]})

    def test_46_advisor_drops_conflict_and_ranks_observed_before_unknown(self):
        plan = {"schema": "ace.presence.best-time.v1", "duration": 20, "busy": [{"start": at("08:00"), "end": at("08:30")}],
                "candidates": [{"id": key, "starts": at(when)} for key, when in
                               [("unknown", "09:00"), ("blocked", "08:05"), ("observed", "10:00")]],
                "focus_history": [{"weekday": 3, "hour": 10, "completed": 2, "tried": 3, "source": "s"}]}
        rows = call(advise, plan)["candidates"]
        self.assertEqual([(row["id"], row["focus_fraction"]) for row in rows], [("observed", "2/3"), ("unknown", None)])

    def test_47_waitlist_ages_and_retains_dangling_prerequisite(self):
        template = {"state": "queued", "added": "2025-04-01", "not_before": "2025-04-01", "priority": 3, "source": "t"}
        plan = {"schema": "ace.presence.topic-waitlist.v1", "as_of": "2025-05-01", "topics": [
            {**template, "id": "pending", "blocked_by": ["absent"]}, {**template, "id": "ready", "blocked_by": []}]}
        result = call(queue, plan)
        self.assertEqual(result["ready"][0]["score"], 7)
        self.assertEqual(result["waiting"][0]["blocked_by"], ["absent"])

    def test_48_recurring_reminder_skips_nonexistent_local_time(self):
        plan = {"schema": "ace.presence.recurring-plan.v1", "from": at("00:00", "2025-03-08"),
                "until": at("00:00", "2025-03-11"), "existing": [],
                "rules": [{"id": "daily", "first": "2025-03-08", "clock": "02:30", "zone": "America/New_York",
                           "every_days": 1, "source": "rule:1"}]}
        result = call(expand, plan)
        self.assertEqual([row["at"] for row in result["occurrences"]], [at("07:30", "2025-03-08"), at("06:30", "2025-03-10")])
        self.assertEqual(result["skipped"][0]["local_date"], "2025-03-09")
        plan["existing"] = [result["occurrences"][0]["sha256"]]
        self.assertEqual(len(call(expand, plan)["occurrences"]), 1)

    def test_49_agenda_orders_overdue_and_reports_truncation(self):
        plan = {"schema": "ace.presence.daily-agenda.v1",
                "calendar_plan": {"schema": "ace.presence.calendar-plan.v1", "day": "2025-05-02", "zone": "UTC", "events": []},
                "limit": 1, "commitments": [
                    {"id": key, "due_on": date, "title": key, "status": "open", "priority": priority, "source": key}
                    for key, date, priority in [("today", "2025-05-02", 100), ("old", "2025-05-01", 1)]]}
        result = call(agenda, plan)
        self.assertEqual(result["priority"][0]["id"], "old")
        self.assertTrue(result["priority"][0]["overdue"])
        self.assertEqual(result["omitted_commitments"], 1)

    def test_50_weekly_review_does_not_count_future_or_planned_as_recorded(self):
        plan = {"schema": "ace.presence.weekly-review.v1", "monday": "2025-04-28", "timeline": [
            {"id": key, "date": date, "status": tag, "title": key, "source": key}
            for key, date, tag in [("old", "2025-04-27", "recorded"), ("new", "2025-05-04", "recorded"),
                                   ("next", "2025-05-01", "planned")]]}
        result = call(review, plan)
        self.assertEqual(result["outside"], 1)
        self.assertEqual(result["totals"], {"recorded": 1, "planned": 1, "blocked": 0})

    def test_51_deadline_collision_checks_joint_demand(self):
        plan = {"schema": "ace.presence.deadline-collisions.v1",
                "working": [{"start": at("09:00"), "end": at("10:00")}], "tasks": [
                    {"id": key, "available_at": at("09:00"), "due_at": at("10:00"), "minutes": 40, "source": key}
                    for key in ("alpha", "beta")]}
        result = call(collide, plan)
        self.assertFalse(result["can_fit_preemptive"])
        self.assertEqual(result["collisions"][0]["deficit_minutes"], 20)
        self.assertEqual([row["id"] for row in result["collisions"][0]["tasks"]], ["alpha", "beta"])

    def test_52_reschedule_orders_feasible_candidates_by_displacement(self):
        plan = {"schema": "ace.presence.reschedule.v1", "appointment": {"start": at("09:30"), "end": at("09:45"), "source": "cal"},
                "work": [{"start": at("09:00"), "end": at("11:00")}],
                "busy": [{"start": at("09:30"), "end": at("09:40")}], "not_before": at("09:00"), "max_results": 2}
        rows = call(propose, plan)["proposals"]
        self.assertEqual([(row["start"], row["shift_seconds"]) for row in rows],
                         [(at("09:40"), 600), (at("09:15"), -900)])

    def test_53_estimate_bias_and_absolute_error_are_distinct(self):
        plan = {"schema": "ace.presence.estimate-calibration.v1", "minimum": 2, "pairs": [
            {"id": key, "kind": "lab", "forecast": 10, "actual": actual, "source": key}
            for key, actual in [("quick", 8), ("long", 16)]]}
        data = call(calibrate, plan)["groups"]["lab"]
        self.assertEqual((data["bias_minutes"], data["mae_minutes"], data["ratio_p90"]), ("2", "4", "8/5"))

    def test_54_day_archive_has_only_permitted_turn_metadata_and_provenance(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            ref, snapshot = sample(root)
            plan = {"schema": "ace.presence.day-archive-plan.v1", "date": "2025-05-01", "zone": "Asia/Jakarta",
                    "exports": [ref], "speakers": ["quoted"]}
            result = call(archive, plan, root)
            self.assertEqual([row["id"] for row in result["turns"]], ["opening", "next"])
            self.assertEqual(result["turns"][0]["turn_sha256"], snapshot["events"][0]["sha256"])
            digest = result.pop("sha256")
            self.assertEqual(digest, identity(result))
            self.assertNotIn(b"Kalibrasi panel", canonical(result))

    def test_55_while_away_uses_exact_bounds_priority_and_chronology(self):
        plan = {"schema": "ace.presence.while-away.v1", "after": at("09:00"), "through": at("11:00"), "limit": 2,
                "events": [{"id": key, "kind": "result", "at": at(when), "message": "Observation", "source": key,
                            "importance": rank} for key, when, rank in [
                                ("checkpoint", "09:00", 100), ("smaller", "09:10", 1),
                                ("first", "10:00", 5), ("last", "11:00", 8), ("future", "11:01", 100)]]}
        result = call(brief, plan)
        self.assertEqual([row["id"] for row in result["events"]], ["first", "last"])
        self.assertEqual(result["omitted"], 1)

    def test_56_persona_audit_reports_drift_and_missing_year(self):
        plan = {"schema": "ace.presence.continuity-plan.v1", "identity": "fixture", "years": [2024, 2025, 2026],
                "fixed_values": {"role": "helper"}, "versions": [
                    {"identity": "fixture", "date": "2024-01-01", "sha256": "a"*64, "previous": None,
                     "values": {"role": "helper"}, "source": "old"},
                    {"identity": "other", "date": "2025-01-01", "sha256": "b"*64, "previous": "a"*64,
                     "values": {"role": "helper"}, "source": "new"}]}
        result = call(audit, plan)
        self.assertFalse(result["continuous"])
        self.assertEqual(result["missing_years"], [2026])
        self.assertEqual(result["findings"][0]["reason"], "identity_changed")

    def test_57_greeting_honors_revocation_and_falls_back(self):
        row = {"receiver": "participant", "locale": "id", "opening": "Selamat datang kembali", "from": "2025-05-01",
               "until": "2025-06-01", "permission": True, "source": "consent"}
        plan = {"schema": "ace.presence.greeting.v1", "receiver": "participant", "as_of": "2025-05-02",
                "locale": "id", "choices": [row], "fallbacks": {"id": "Halo", "en": "Hello"}}
        self.assertEqual(call(greeting, plan)["source"], "consent")
        plan["choices"].append({**row, "from": "2025-05-02", "permission": False})
        self.assertEqual(call(greeting, plan)["opening"], "Halo")

    def test_58_presence_quality_abstains_for_sparse_ratings(self):
        plan = {"schema": "ace.presence.quality.v1", "from": "2025-05-01", "until": "2025-05-08", "minimum": 2,
                "observations": [
                    {"id": key, "channel": "mailbox", "date": "2025-05-01", "answered": answer,
                     "rated": rated, "helpful": helpful, "source": key}
                    for key, answer, rated, helpful in [("yes", True, True, True), ("no", False, False, False)]]}
        result = call(quality, plan)["channels"]["mailbox"]
        self.assertEqual(result["response_fraction"], "1/2")
        self.assertIsNone(result["helpful_fraction"])

    def test_59_dnd_requires_exact_grant_and_reports_deadline_conflict(self):
        allowed = {"id": "auth", "channel": "terminal", "urgency": "critical", "deadline": at("10:30")}
        plan = {"schema": "ace.presence.dnd-plan.v1", "now": at("09:20"),
                "quiet": [{"start": at("09:00"), "end": at("10:00")}],
                "interrupt_grants": [identity(allowed)], "requests": [
                    allowed, {**allowed, "id": "next"}, {**allowed, "id": "close", "deadline": at("09:40")}]}
        self.assertEqual([row["decision"] for row in call(decide, plan)["requests"]],
                         ["allow_verified_interrupt", "defer", "operator_review"])

    def test_60_period_report_uses_as_of_when_receipt_arrives_later(self):
        plan = {"schema": "ace.presence.period-report.v1", "start": "2025-05-01", "as_of": "2025-05-07",
                "promises": [{"id": key, "date": "2025-05-01", "due_on": date, "source": key}
                             for key, date in [("ontime", "2025-05-03"), ("late", "2025-05-04"),
                                                ("future_receipt", "2025-05-05"), ("today", "2025-05-07")]],
                "receipts": [{"promise": key, "date": date, "source": key, "kind": "fulfilled"}
                             for key, date in [("ontime", "2025-05-03"), ("late", "2025-05-05"),
                                                ("future_receipt", "2025-05-08")]]}
        result = call(report, plan)
        self.assertEqual(result["counts"], {"on_time": 1, "late": 1, "missed": 1, "due_today": 1, "cancelled": 0})
        self.assertIsNone(result["entries"][2]["resolution_source"])
