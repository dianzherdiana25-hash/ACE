from hashlib import sha256
import gzip
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._contracts import canonical, identity
from ._snapshots import build_manifest
from .action_anomaly import detect as anomalies
from .custody_rules import policy_data
from .cycle_budget_guard import plan_budget
from .gate_regression_runner import regress
from .leak_detector import detect
from .log_rotator import manifest, split
from .organ_health_report import health
from .orphan_sweeper import sweep
from .recovery_drill import drill
from .recovery_playbooks import ACTIONS
from .safe_mode import transition
from .self_compliance_score import score
from .slow_step_trend import trend
from .state_of_ace import one_page
from .step_quarantine import suggest
from .store_verifier import inspect
from .test_custody_foundation import AT, action, stash
from .test_guardian_core import END, LATER, receipts
from .test_twins import call, plan
from .trusted_actor_admin import registry

class GuardianOperationsTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)

    def test_31_real_child_termination_followed_by_fixture_recovery(self):
        source, failed, target = (self.root / path for path in ("source", "failed", "recovered"))
        source.mkdir()
        failed.mkdir()
        stash(source, "s", b"healthy")
        stash(failed, "s", b"faulted")
        rollback = plan("rollback-plan", verified_snapshot=build_manifest(source, ["s"]),
                        current_snapshot=build_manifest(failed, ["s"]))
        recipe = plan("recovery-playbook", fault="process_stopped", steps=list(ACTIONS), rollback=rollback)
        result = call(drill, plan("recovery-drill", playbook=recipe, limit_ms=300_000), source, failed, target)
        self.assertTrue(result["under_limit"])
        self.assertLess(result["process_exit"], 0)
        self.assertEqual((target / "s").read_bytes(), b"healthy")
        self.assertEqual((failed / "s").read_bytes(), b"faulted")

    def test_32_leak_slope_uses_process_instances_and_robust_pairs(self):
        plan_data = plan("rss-leak", samples=[
            {"instance": key, "at": f"2025-07-01T0{hour}:00:00Z", "rss_mib": rss, "source": f"{key}:{hour}"}
            for key, hour, rss in [("active", 0, 10), ("active", 1, 15), ("active", 2, 20),
                                   ("active", 3, 150), ("active", 4, 30), ("new", 4, 13)]
        ], minimum=3, growth_mib_per_hour=5, min_total_mib=10)
        rows = call(detect, plan_data)["instances"]
        self.assertEqual((rows[0]["status"], rows[0]["slope"]), ("suspected_leak", "5"))
        self.assertEqual(rows[1]["status"], "insufficient")

    def test_33_old_unreferenced_files_are_candidates_only(self):
        for name in ("orphan", "retained"):
            stash(self.root, name, b"x")
        request = plan("orphans", now=END, age_seconds=1200, candidates=[
            {"path": key, "created": AT, "hold": False} for key in ("orphan", "retained", "missing")],
            references=["retained"])
        result = call(sweep, request, self.root)
        self.assertEqual([row["path"] for row in result["orphaned"]], ["orphan"])
        self.assertEqual(result["retained"], [{"path": "missing", "reason": "missing"},
                                              {"path": "retained", "reason": "referenced"}])
        self.assertTrue((self.root / "orphan").is_file())

    def test_34_verification_reports_each_tampered_removed_and_extra_file(self):
        for name in ("changed", "gone"):
            stash(self.root, name, b"source")
        known = build_manifest(self.root, ["gone", "changed"])
        stash(self.root, "changed", b"not the source")
        stash(self.root, "extra", b"extra")
        (self.root / "gone").unlink()
        result = call(inspect, plan("store-verification", manifest=known, reject_extras=True), self.root)
        self.assertEqual([row["status"] for row in result["files"]], ["different", "missing"])
        self.assertEqual(result["extra_paths"], ["extra"])
        self.assertFalse(result["ok"])

    def test_35_archived_log_decompresses_to_exact_lines_and_is_stable(self):
        first, second = [canonical({"at": when, "kind": "fixture", "message": "log row"}) + b"\n"
                         for when in (AT, "2025-07-02T00:01:00Z")]
        sha = stash(self.root, "daily.jsonl", first + second)
        request = plan("rotate-log", source={"path": "daily.jsonl", "sha256": sha}, as_of="2025-07-02", active_days=1)
        data = call(split, request, self.root)
        self.assertEqual(gzip.decompress(data["2025-07-01"]), first)
        self.assertEqual(data["active"], second)
        metadata = call(manifest, request, self.root)["partitions"]
        self.assertEqual(metadata[0]["sha256"], sha256(data["2025-07-01"]).hexdigest())
        self.assertEqual(call(split, request, self.root), data)

    def test_36_organ_health_preserves_streak_and_distinguishes_no_observation(self):
        request = plan("organ-health", as_of=END, max_age_seconds=600, organs=["edge", "empty"], observations=[
            {"organ": "edge", "at": when, "ok": ok, "source": when, "latency_ms": 10}
            for when, ok in [(AT, True), (LATER, False), (END, False)]])
        organs = call(health, request)["organs"]
        self.assertEqual((organs["edge"]["status"], organs["edge"]["failure_streak"]), ("degraded", 2))
        self.assertEqual(organs["empty"]["status"], "unobserved")

    def test_37_slowdown_obeys_split_and_preserves_exact_fraction(self):
        request = plan("slow-trend", **{"from": AT, "split": LATER, "until": END,
            "minimum": 2, "slowdown_bp": 1000, "rows": [
                {"step": "step", "at": f"2025-07-01T00:{minute:02d}:00Z", "ms": ms, "source": str(minute)}
                for minute, ms in [(0, 5), (3, 15), (10, 13), (19, 14), (20, 900)]]})
        data = call(trend, request)["steps"]["step"]
        self.assertEqual((data["baseline_ms"], data["recent_ms"], data["relative"]), ("10", "27/2", "7/20"))
        self.assertTrue(data["slower"])

    def test_38_quarantine_only_latest_streak_and_protects_required_action(self):
        request = plan("step-quarantine", outcomes=[
            {"step": key, "at": at, "ok": ok, "source": key + at} for key, at, ok in [
                ("guard", AT, False), ("guard", LATER, False), ("optional", AT, False),
                ("optional", LATER, True), ("optional", END, False)]], threshold=2, protected=["guard"])
        result = call(suggest, request)
        self.assertEqual(len(result["findings"]), 1)
        self.assertEqual(result["findings"][0]["suggestion"], "operator_review_protected")

    def test_39_budget_reserves_required_steps_and_defer_does_not_consume_time(self):
        request = plan("cycle-budget", total_ms=100, spent_ms=20, remaining_steps=[
            {"id": key, "estimated_ms": ms, "maximum_ms": 60, "required": needed}
            for key, ms, needed in [("large", 50, False), ("small", 10, False), ("required", 50, True)]])
        result = call(plan_budget, request)
        self.assertEqual([row["decision"] for row in result["steps"]], ["defer", "run_fixture", "run_fixture"])
        self.assertEqual(result["remaining_ms"], 20)

    def test_40_status_page_reads_only_hash_matched_panels_before_as_of(self):
        first = stash(self.root, "ready", canonical(plan("panel", as_at=AT, status="known", summary="Ready.")))
        future = stash(self.root, "future", canonical(plan("panel", as_at=END, status="known", summary="Future.")))
        request = plan("one-page", as_of=LATER, panels=[
            {"id": key, "path": key, "title": key, "sha256": sha} for key, sha in [("ready", first), ("future", future)]])
        panels = call(one_page, request, self.root)["panels"]
        self.assertEqual([row["status"] for row in panels], ["known", "unavailable"])
        self.assertEqual(panels[0]["source"]["sha256"], first)

    def test_41_safe_mode_latches_and_requires_current_clean_and_approval(self):
        probe = plan("safe-mode", previous={"mode": "normal", "at": AT},
                     samples=[{"at": LATER, "status": "critical", "source": "a"*64}],
                     minimum_clean=1, approval="b"*64, allowed_approvals=["b"*64])
        self.assertEqual(call(transition, probe)["mode"], "safe")
        probe["previous"]["mode"] = "safe"
        self.assertEqual(call(transition, probe)["reason"], "latched")
        probe["samples"][0]["status"] = "healthy"
        self.assertEqual(call(transition, probe)["reason"], "clean_and_approved")
        probe["allowed_approvals"] = []
        self.assertEqual(call(transition, probe)["mode"], "safe")

    def test_42_regression_fails_on_missing_class_or_rule_mismatch(self):
        data = plan("gate-regression", policy=policy_data(), required_kinds=["money", "local_read"], cases=[
            {"id": "read", "action": action("read", "local_read", verified=True, sealed=False),
             "expect": "allow", "first_rule": "default"}])
        result = call(regress, data)
        self.assertEqual(result["missing_kinds"], ["money"])
        self.assertEqual(result["verified"], 0)
        data["cases"][0]["first_rule"] = "read_verified"
        data["required_kinds"].pop(0)
        self.assertTrue(call(regress, data)["passed"])

    def test_43_trusted_actor_grant_expires_and_revocation_is_narrow(self):
        row = {"id": "grant", "actor": "agent", "scope": "read", "effect": "grant", "at": AT,
               "expires": END, "ref": "c"*64}
        request = plan("trusted-actors", at=LATER, scopes=["read", "review"], authority_refs=["c"*64], events=[
            row, {**row, "id": "grant2", "scope": "review"},
            {**row, "id": "revoke", "effect": "revoke", "at": LATER, "expires": None}])
        self.assertEqual([row["scope"] for row in call(registry, request)["active"]], ["review"])
        request["at"] = END
        self.assertEqual(call(registry, request)["active"], [])

    def test_44_anomaly_detects_outlier_and_unseen_actor_with_same_evidence(self):
        request = plan("action-anomalies", minimum_count=3, mad_multiplier=3, baseline=[
            {"id": f"item{n}", "kind": "read", "actor": "known", "units": value, "source": "c"*64}
            for n, value in enumerate([2, 3, 4])], observed=[
            {"id": "observation", "kind": "read", "actor": "other", "units": 12, "source": "a"*64}])
        result = call(anomalies, request)["findings"][0]
        self.assertEqual(result["flags"], ["unseen_actor_for_kind", "unit_outlier"])
        self.assertEqual(result["source"], "a"*64)

    def test_45_weekly_score_counts_deny_execution_as_bypass_and_keeps_missing(self):
        actions = [action("read", "local_read", verified=True, sealed=False),
                   action("forbidden", "money", approval=True)]
        rows = [{"id": row["id"], "at": END, "executed": True, "request_sha256": identity(row), "source": "a"*64}
                for row in actions]
        rows.append({**rows[0], "id": "missing"})
        data = plan("self-compliance", week_start="2025-06-30T00:00:00Z",
                    observed=rows, receipts=receipts(actions))
        result = call(score, data)
        self.assertEqual(result["score"], "1/3")
        self.assertEqual((result["counts"]["bypassed"], result["counts"]["no_receipt"]), (1, 1))
