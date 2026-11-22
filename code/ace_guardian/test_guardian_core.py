from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._contracts import GuardianError, canonical, identity
from ._snapshots import build_manifest
from .action_gate import assess
from .adversarial_rule_tests import probe
from .calibration_scorer import score
from .compliance_reporter import report
from .confidence_ledger import GENESIS as CONFIDENCE, ledger
from .coverage_checker import check
from .custody_rules import policy_data
from .exception_manager import exceptions
from .gate_receipt_ledger import append
from .house_supervisor import supervise
from .incident_journal import GENESIS as INCIDENT, index
from .recovery_playbooks import ACTIONS, execute
from .rule_change_protocol import review
from .rule_compiler import compile_rules
from .test_custody_foundation import AT, action, stash
from .test_twins import call, plan

LATER = "2025-07-01T00:10:00Z"
END = "2025-07-01T00:20:00Z"


def policy():
    return plan("compile-rules", revision="first",
                actions=[{"kind": "reading", "fields": {"verified": "bool", "sealed": "bool"}}],
                lines=["deny seal reading if sealed=true", "allow known reading if verified=true"])


def receipts(actions, selected=None):
    source = selected or policy_data()
    decisions = call(assess, plan("action-gate", policy=source, actions=actions))["decisions"]
    result = []
    for row in decisions:
        new = call(append, plan("gate-receipt", prior=result, decision=row, at=LATER))
        result.append(new["receipt"])
    return result


class GuardianCoreTests(unittest.TestCase):
    def test_21_rule_product_detects_missing_boundary_rule(self):
        before = policy()
        probe_plan = plan("policy-probe", policy=before, domains=[], case_limit=20, invariants=[
            {"id": "sealed", "kind": "reading", "when": {"sealed": True}, "must_not": "allow"}])
        good = call(probe, probe_plan)
        self.assertEqual((good["tested"], good["invariant_counts"]["sealed"], good["passed"]), (4, 2, True))
        before["lines"].pop(0)
        weakened = call(probe, probe_plan)
        self.assertEqual(weakened["violations"][0]["facts"], {"sealed": True, "verified": True})

    def test_22_exact_exception_can_unhold_review_but_never_override_deny(self):
        policy_def = policy_data()
        review_action = action("copy", "fixture_copy", verified=False, isolated=True)
        decision = call(assess, plan("action-gate", policy=policy_def, actions=[review_action]))["decisions"][0]
        grant = {"id": "operator", "kind": "fixture_copy", "request_sha256": decision["request_sha256"],
                 "policy_sha256": decision["policy_sha256"], "starts": AT, "expires": END,
                 "approval_ref": "a"*64, "reason": "explicit review fixture"}
        request = plan("exceptions", at=LATER, decision=decision, grants=[grant], approved=["a"*64])
        self.assertEqual(call(exceptions, request)["outcome"], "allow")
        request["at"] = END
        self.assertEqual(call(exceptions, request)["outcome"], "review")
        request.update(at=LATER, decision={**decision, "outcome": "deny"})
        self.assertEqual(call(exceptions, request)["outcome"], "deny")

    def test_23_rule_change_ensures_version_coverage_and_gold(self):
        before = policy()
        candidate = deepcopy(before)
        candidate["revision"] = "second"
        candidate["lines"].append("review review reading if verified=true")
        compiled = call(compile_rules, before)
        request = plan("rule-change", parent=compiled["compiled_sha256"], previous=before, candidate=candidate, cases=[
            {"action": action("first", "reading", verified=True, sealed=False), "baseline": "allow", "candidate": "review"}
        ])
        self.assertEqual(call(review, request)["disposition"], "ready_for_review")
        request["cases"][0]["candidate"] = "deny"
        self.assertEqual(call(review, request)["disposition"], "held")

    def test_24_compliance_records_missing_actions_and_counts_applied_rules(self):
        safe = action("safe", "local_read", verified=True, sealed=False)
        log = receipts([safe])
        request = plan("compliance-report", **{"from": AT, "until": END, "ledger": log, "actions": [
            {"id": safe["id"], "request_sha256": identity(safe), "at": AT},
            {"id": "absent", "request_sha256": "f"*64, "at": AT}
        ]})
        result = call(report, request)
        self.assertEqual(result["coverage"], "1/2")
        self.assertEqual(result["per_rule"], {"read_verified": {"allow": 1}})
        self.assertEqual(result["missing"], ["absent"])

    def test_25_coverage_distinguishes_unregistered_kind_missing_outcome(self):
        sample = action("safe", "local_read", verified=True, sealed=False)
        request = plan("policy-coverage", policy=policy_data(), ledger=receipts([sample]), classes=[
            {"kind": "local_read", "expected_outcomes": ["allow", "deny"]},
            {"kind": "unknown", "expected_outcomes": ["deny"]}])
        result = call(check, request)
        self.assertFalse(result["complete"])
        self.assertEqual(result["coverage"][0]["untested_outcomes"], ["deny"])
        self.assertEqual(result["coverage"][1]["classification"], "unregistered")

    def test_26_heartbeat_exact_age_and_first_dependency_affected(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            options = {key: {"path": key, "max_age": 600} for key in ("bridge", "engine", "pump")}
            base = plan("heartbeat", component="engine", at=AT, running=True, sequence=1)
            stash(root, "engine", canonical(base))
            stash(root, "bridge", canonical({**base, "component": "bridge", "running": False}))
            result = call(supervise, plan("heartbeats", at=LATER, components=options), root)
            self.assertEqual(result["first_unhealthy"], "bridge")
            self.assertEqual(result["states"]["engine"]["status"], "healthy")
            self.assertEqual(result["states"]["pump"]["status"], "missing")

    def test_27_playbook_runs_real_restore_onto_new_fixture_and_does_not_replace_sources(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            backup, failed, fresh = (root / key for key in ("backup", "failed", "fresh"))
            backup.mkdir()
            failed.mkdir()
            stash(backup, "index.json", b"valid fixture")
            stash(failed, "index.json", b"injected fault")
            checked = plan("rollback-plan", verified_snapshot=build_manifest(backup, ["index.json"]),
                           current_snapshot=build_manifest(failed, ["index.json"]))
            request = plan("recovery-playbook", fault="checkpoint_corrupt", steps=list(ACTIONS), rollback=checked)
            clock = iter([1, 1.125])
            result = execute(request, identity(request), backup, failed, fresh, clock=lambda: next(clock))
            self.assertEqual((result["status"], result["elapsed_milliseconds"]), ("fixture_recovered", 125))
            self.assertEqual((fresh / "index.json").read_bytes(), b"valid fixture")
            self.assertEqual((failed / "index.json").read_bytes(), b"injected fault")

    def test_28_incident_retains_original_failure_and_recovery_evidence(self):
        events = []
        prior = INCIDENT
        for phase, at in [("failed", AT), ("detected", AT), ("recovering", LATER), ("restored", END), ("closed", END)]:
            row = {"id": "fixture", "component": "pump", "phase": phase, "at": at, "source": f"s:{phase}", "prior": prior}
            prior = identity(row)
            events.append(row)
        result = call(index, plan("incident-index", events=events))["incidents"][0]
        self.assertEqual((result["state"], len(result["events"])), ("closed", 5))
        self.assertEqual(result["events"][0]["source"], "s:failed")
        events[2]["prior"] = "f"*64
        with self.assertRaises(GuardianError):
            call(index, plan("incident-index", events=events))

    def test_29_ledger_rejects_resolution_with_same_source_and_locks_prediction(self):
        forecast = {"id": "one", "kind": "forecast", "domain": "engine", "at": AT,
                    "value": 7000, "source": "a"*64, "previous": CONFIDENCE}
        resolved = {**forecast, "kind": "resolve", "at": LATER, "value": True, "source": "b"*64, "previous": identity(forecast)}
        data = plan("confidence-ledger", events=[forecast, resolved])
        self.assertEqual(call(ledger, data)["completed"][0]["confidence_bp"], 7000)
        resolved["source"] = forecast["source"]
        with self.assertRaises(GuardianError):
            call(ledger, data)

    def test_30_ece_and_brier_use_exact_weight_and_include_confidence_one(self):
        rows = [{"id": key, "domain": "engine", "confidence_bp": p, "observed": outcome,
                 "resolved_ref": sha*64} for key, p, outcome, sha in [
                     ("low", 2000, False, "a"), ("high", 8000, True, "b"), ("edge", 10000, True, "c")]]
        result = call(score, plan("calibration", rows=rows, bins=2, minimum=3))["domains"]["engine"]
        self.assertEqual((result["ece"], result["brier"]), ("2/15", "2/75"))
        self.assertEqual([row["count"] for row in result["bins"]], [1, 2])
