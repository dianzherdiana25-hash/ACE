from hashlib import sha256
from io import BytesIO
from pathlib import Path
import tarfile
from tempfile import TemporaryDirectory
import unittest

from ._contracts import GuardianError, canonical, identity
from ._snapshots import build_manifest
from .abstention_calibrator import calibrate
from .calibration_to_director import advise
from .confidence_ledger import GENESIS as CONFIDENCE
from .decade_baseline_archiver import archive, report as archive_report
from .decade_closing_report import report as closing
from .decade_verdict_board import board
from .ece_publisher import build_report
from .flag_transition_manager import transition
from .incident_journal import GENESIS as INCIDENT
from .low_confidence_registry import registry
from .next_decade_opener import propose
from .postmortem_writer import postmortem
from .recovery_time_tracker import summarize
from .report_truth_checker import check
from .rollback_drill import drill
from .snapshot_retention import retain
from .standby_mirror import mirror
from .test_custody_foundation import AT, stash
from .test_guardian_core import END, LATER
from .test_twins import call, plan

def incident():
    timeline, prior = [], INCIDENT
    for phase, when, key in [("failed", AT, "done"), ("detected", LATER, "done"),
                             ("failed", LATER, "waiting"), ("recovering", LATER, "done"), ("restored", END, "done")]:
        row = {"phase": phase, "at": when, "id": key, "component": "engine", "source": f"log:{phase}", "prior": prior}
        timeline.append(row)
        prior = identity(row)
    return plan("incident-index", events=timeline)

class GuardianClosingTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)

    def test_46_snapshot_hold_and_minimum_win_when_budget_cannot_fit(self):
        request = plan("snapshot-retention", as_of=END, keep_count=1, max_age_days=10, max_bytes=15, snapshots=[
            {"id": key, "at": when, "bytes": 10, "manifest": f"{n}"*64, "hold": hold} for n, key, when, hold in
            [(1, "old", AT, True), (2, "mid", LATER, False), (3, "new", END, False)]])
        result = call(retain, request)
        self.assertEqual([row["id"] for row in result["retained"]], ["new", "old"])
        self.assertEqual(result["retire_candidates"][0]["reason"], "budget")
        self.assertEqual(result["over_budget_protected"], 5)

    def test_47_rollback_drill_compares_expected_diff_to_measured_bytes(self):
        for directory in ("backup", "damaged"):
            (self.root / directory).mkdir()
            stash(self.root / directory, "v", directory.encode())
        rollback = plan("rollback-plan", verified_snapshot=build_manifest(self.root / "backup", ["v"]),
                        current_snapshot=build_manifest(self.root / "damaged", ["v"]))
        request = plan("rollback-drill", cases=[{"id": "byte_changed", "snapshot": "backup", "current": "damaged",
                                               "rollback": rollback, "expected_changes": {"added": [], "removed": [], "replaced": ["v"]}}])
        self.assertEqual(call(drill, request, self.root)["passed"], 1)
        request["cases"][0]["expected_changes"]["replaced"] = []
        self.assertEqual(call(drill, request, self.root)["passed"], 0)

    def test_48_standby_uses_exact_manifest_generation_and_anchored_parent(self):
        stash(self.root, "f", b"fixture")
        manifest = build_manifest(self.root, ["f"])
        code = identity(manifest)
        active = {"sequence": 4, "at": AT, "manifest": manifest, "recorded_sha256": code, "follows": None}
        standby = {**active, "at": LATER, "follows": code}
        request = plan("standby-mirror", active=active, standby=standby, maximum_lag=1)
        self.assertTrue(call(mirror, request)["review_failover"])
        standby["follows"] = "a"*64
        self.assertEqual(call(mirror, request)["status"], "parent_unverified")

    def test_49_median_restore_with_open_incident_retained(self):
        result = call(summarize, plan("recovery-times", journal=incident(), required=["engine", "pump"]))
        self.assertEqual(result["components"]["engine"]["median_restore_seconds"], "1200")
        self.assertIsNone(result["components"]["pump"]["median_restore_seconds"])
        self.assertEqual(result["unresolved"][0]["id"], "waiting")

    def test_50_postmortem_keeps_unreviewed_root_cause_and_requires_valid_event(self):
        record = incident()
        source = identity(record["events"][0])
        request = plan("postmortem", journal=record, incident="done",
                       findings=[{"statement": "Failure observed.", "status": "observed", "source": source}],
                       followups=[{"id": "check", "proposal": "Replay.", "source": source}])
        outcome = call(postmortem, request)
        self.assertEqual(outcome["root_cause"], "operator_review_pending")
        self.assertEqual(outcome["timeline"][0]["phase"], "failed")
        request["findings"][0]["source"] = "a"*64
        with self.assertRaises(GuardianError):
            call(postmortem, request)

    def test_51_abstention_threshold_is_lowest_qualified_and_respects_sample_floor(self):
        request = plan("abstention-calibration", max_error_bp=0, minimum_accepted=2,
                       thresholds=[0, 5000, 8000, 10000], samples=[
                           {"id": key, "confidence_bp": confidence, "correct": correct}
                           for key, confidence, correct in [("bad", 4000, False), ("some", 7000, True), ("sure", 10000, True)]])
        result = call(calibrate, request)
        self.assertEqual(result["chosen_threshold_bp"], 5000)
        self.assertEqual(result["curve"][1]["coverage"], "2/3")
        request["minimum_accepted"] = 3
        self.assertIsNone(call(calibrate, request)["chosen_threshold_bp"])

    def test_52_unverified_expired_and_low_threshold_advise_abstention(self):
        row = {"domain": "code", "threshold_bp": 7500, "from": AT, "until": END, "source": "b"*64}
        probe = plan("director-calibration", now=LATER, request={
            "id": "candidate", "domain": "code", "confidence_bp": 7500, "request_ref": "a"*64},
            thresholds=[row], approved_refs=["b"*64])
        self.assertEqual(call(advise, probe)["advice"], "eligible_for_review")
        probe["request"]["confidence_bp"] -= 1
        self.assertEqual(call(advise, probe)["reason"], "below_threshold")
        probe["now"] = END
        self.assertEqual(call(advise, probe)["reason"], "no_current_evidence")

    def test_53_ece_report_keeps_unknown_domains_unmeasured(self):
        forecast = {"id": "x", "kind": "forecast", "domain": "snapshots", "at": AT, "value": 8000,
                    "source": "a"*64, "previous": CONFIDENCE}
        observed = {**forecast, "kind": "resolve", "at": LATER, "value": True,
                    "source": "b"*64, "previous": identity(forecast)}
        request = plan("ece-report", calibration_ledger=plan("confidence-ledger", events=[forecast, observed]),
                       bins=5, minimum=1, domains=["empty", "snapshots"])
        result = call(build_report, request)
        self.assertEqual([row["ece"] for row in result["domains"]], [None, "1/5"])
        self.assertIn("| empty | 0 | belum terukur |", result["markdown"])

    def test_54_low_confidence_needs_fresh_metric_and_samples(self):
        request = plan("low-confidence", now=LATER, domains=[
            {"domain": "vision", "max_ece_bp": 400, "minimum_samples": 10, "reason": "data sparse", "from": AT}],
            measurements=[{"domain": "vision", "ece_bp": 300, "samples": 9, "at": AT, "expires": END, "source": "a"*64}])
        self.assertEqual(call(registry, request)["domains"][0]["status"], "limited_measurement")
        request["measurements"][0]["samples"] = 10
        self.assertEqual(call(registry, request)["domains"][0]["status"], "eligible_for_confidence_review")
        request["now"] = END
        self.assertEqual(call(registry, request)["domains"][0]["status"], "limited_no_current_evidence")

    def test_55_truth_checker_distinguishes_wrong_type_pointer_and_digest(self):
        sha = stash(self.root, "log.json", canonical({"a/b": [10]}))
        row = {"id": "correct", "path": "log.json", "sha256": sha, "pointer": "/a~1b/0", "claims": 10}
        checks = call(check, plan("report-truth", claims=[
            row, {**row, "id": "wrong_type", "claims": "10"},
            {**row, "id": "missing", "pointer": "/a~1b/1"}, {**row, "id": "changed", "sha256": "e"*64}]), self.root)
        self.assertEqual([row["status"] for row in checks["claims"]],
                         ["supported", "contradicted", "pointer_missing", "unsupported"])

    def test_56_board_distinguishes_fixture_unverified_and_absent(self):
        raw = canonical(plan("verdict", evo="0051", scope="fixture", state="passed"))
        sha = stash(self.root, "one.json", raw)
        request = plan("decade-board", expect=["0051", "0052", "0053"], records=[
            {"evo": number, "path": "one.json", "sha256": sha} for number in ("0051", "0052")])
        result = call(board, request, self.root)["program"]
        self.assertEqual([(row["state"], row["reason"]) for row in result],
                         [("passed", "recorded"), ("not_assessed", "unverified_source"), ("not_assessed", "missing_source")])

    def test_57_flag_sequence_has_rollback_and_cannot_skip_review_phases(self):
        request = plan("flag-transition", at=LATER,
                       flags=[{"name": "ACE_FIXTURE", "phase": "off", "revision": "a"*64}],
                       change={"name": "ACE_FIXTURE", "from": "off", "to": "fixture", "parent": "a"*64},
                       readiness={"to": "fixture", "passed": True, "source": "b"*64, "at": AT, "expires": END})
        self.assertEqual(call(transition, request)["rollback"]["phase"], "off")
        request["change"]["to"] = "review"
        self.assertEqual(call(transition, request)["reason"], "invalid_or_stale_transition")

    def test_58_archive_is_reproducible_and_has_unmodified_payloads(self):
        stash(self.root, "two", b"two")
        stash(self.root, "one", b"one")
        request = plan("archive-baseline", manifest=build_manifest(self.root, ["two", "one"]))
        data = call(archive, request, self.root)
        self.assertEqual(data, call(archive, request, self.root))
        with tarfile.open(fileobj=BytesIO(data)) as unpacked:
            self.assertEqual(unpacked.getnames(), ["fixture/one", "fixture/two"])
            self.assertEqual(unpacked.extractfile("fixture/two").read(), b"two")
        self.assertEqual(call(archive_report, request, self.root)["sha256"], sha256(data).hexdigest())

    def test_59_fixture_positive_does_not_close_registered_target(self):
        row = {"evo": "0051", "state": "passed", "scope": "fixture", "reason": "recorded",
               "source": {"evo": "0051", "path": "sample", "sha256": "a"*64}}
        request = plan("decade-summary", program=[row], goal=1, outstanding=["heldout"])
        result = call(closing, request)
        self.assertEqual(result["fixture"], {"passed": 1})
        self.assertFalse(result["verified_goal_reached"])
        self.assertEqual(result["evo_without_registered_pass"], ["0051"])

    def test_60_future_tranche_ranks_blockers_and_lists_unanchored_separately(self):
        prototype = {"evo": "0060", "claim": "An issue.", "effort": 5, "verify": "Replay logged result."}
        request = plan("next-decade", limit=2, approved_sources=["a"*64], audit=[
            {**prototype, "id": key, "state": state, "source": ref*64} for key, state, ref in [
                ("unknown", "not_assessed", "a"), ("held", "blocked", "a"), ("unsupported", "blocked", "b")]])
        result = call(propose, request)
        self.assertEqual([row["audit_id"] for row in result["drafts"]], ["held", "unknown"])
        self.assertEqual(result["unanchored"], ["unsupported"])
        self.assertEqual(result["scope"], "human_review_only")
