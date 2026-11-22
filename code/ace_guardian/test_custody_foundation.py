from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._contracts import GuardianError, canonical, identity
from ._snapshots import build_manifest
from .action_gate import assess
from .custody_rules import policy_data, standing
from .fork_redactor import redact
from .gate_receipt_ledger import append, verify_ledger
from .incremental_fork import increment
from .promotion_dossier import dossier
from .resource_guardian import guard
from .rule_compiler import compile_rules
from .rule_dsl import parse
from .rule_simulator import simulate
from .test_twins import call, plan

AT = "2025-07-01T00:00:00Z"

def action(key, kind, **facts):
    return {"id": key, "kind": kind, "facts": facts}

def stash(root, path, raw):
    (root / path).write_bytes(raw)
    return sha256(raw).hexdigest()

class CustodyTests(unittest.TestCase):
    def test_11_incremental_uses_old_bytes_only_for_equal_hashes(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            old, changed = root / "old", root / "changed"
            old.mkdir()
            changed.mkdir()
            stash(old, "same", b"same")
            stash(old, "remove", b"gone")
            stash(changed, "new", b"new")
            recent = build_manifest(old, ["same", "remove"])
            next_only = build_manifest(changed, ["new"])
            new = {"schema": recent["schema"],
                   "files": next_only["files"] + [row for row in recent["files"] if row["path"] == "same"]}
            report = call(increment, plan("incremental", before=recent, after=new), old, changed, root / "destination")
            self.assertEqual((report["reused"], report["changed"], report["removed"]), (["same"], ["new"], ["remove"]))
            (root / "destination/same").write_bytes(b"fork only")
            self.assertEqual((old / "same").read_bytes(), b"same")

    def test_12_sweep_detects_shared_ram_overlap_but_no_false_boundary_overlap(self):
        probe = plan("resources", limits={"cpu_units": 4, "memory_mib": 10, "twins": 2}, intervals=[
            {"id": "first", "start": AT, "end": "2025-07-01T00:20:00Z", "cpu_units": 2, "memory_mib": 6},
            {"id": "second", "start": "2025-07-01T00:10:00Z", "end": "2025-07-01T00:30:00Z", "cpu_units": 2, "memory_mib": 6}])
        result = call(guard, probe)
        self.assertEqual(result["violations"][0]["excess"], {"memory_mib": 2})
        probe["intervals"][1]["start"] = probe["intervals"][0]["end"]
        self.assertTrue(call(guard, probe)["allowed"])

    def test_13_redaction_uses_explicit_pointer_for_unnamed_secret_and_standard_keys(self):
        sample = "fixture-value-only"
        probe = plan("fork-redaction", snapshot={"rows": [{"arbitrary": sample, "token": sample, "safe": 7}]},
                     fields=["/rows/0/arbitrary"])
        report = call(redact, probe)
        self.assertNotIn(sample.encode(), canonical(report))
        self.assertEqual(report["snapshot"]["rows"][0]["safe"], 7)
        self.assertEqual(report["counts"], {"explicit": 1, "sensitive_name": 1})
        probe["fields"].append("/absent")
        with self.assertRaises(GuardianError):
            call(redact, probe)

    def test_14_promotion_custody_verifies_files_and_requires_every_metric_ref(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            sources = [{"id": f"proof{index}", "path": f"p{index}",
                        "sha256": stash(root, f"p{index}", str(index).encode())} for index in range(3)]
            metric = {"id": "score", "baseline": 5, "candidate": 8, "baseline_ref": sources[0]["sha256"],
                      "candidate_ref": sources[1]["sha256"], "direction": "higher", "minimum_gain": 2}
            card = plan("promotion-plan", metrics=[metric],
                        validations=[{"id": "test", "passed": True, "source": sources[2]["sha256"]}])
            probe = plan("promotion-dossier", bundle="fixture", artifacts=sources, scorecard=card)
            self.assertEqual(call(dossier, probe, root)["recommendation"], "eligible")
            probe["artifacts"] = sources[:2]
            self.assertEqual(call(dossier, probe, root)["missing_evidence"], [sources[2]["sha256"]])
            (root / "p0").write_bytes(b"changed")
            with self.assertRaises(GuardianError):
                call(dossier, probe, root)

    def test_15_rule_dsl_has_typed_conditions_and_precise_error_line(self):
        result = call(parse, plan("rule-text", lines=["# fixture", "", "allow next mission if ready=true and tries=2"]))
        self.assertEqual(result["rules"][0]["conditions"], {"ready": True, "tries": 2})
        with self.assertRaisesRegex(GuardianError, "baris 2"):
            call(parse, plan("rule-text", lines=["allow first mission", "allow next mission if ready=true and ready=false"]))

    def test_16_rule_compile_checks_types_and_orders_deny_over_specific_allow(self):
        probe = plan("compile-rules", revision="sample", actions=[{"kind": "read", "fields": {"ok": "bool"}}],
                     lines=["allow typed read if ok=true", "deny all read"])
        result = call(compile_rules, probe)
        self.assertEqual([row["rule"] for row in result["by_kind"]["read"]], ["all", "typed"])
        probe["lines"][0] = "allow typed read if ok=1"
        with self.assertRaises(GuardianError):
            call(compile_rules, probe)

    def test_17_action_gate_receipts_cover_allow_deny_and_unknown(self):
        probe = plan("action-gate", policy=policy_data(), actions=[
            action("allow", "local_read", verified=True, sealed=False),
            action("deny", "local_read", verified=True, sealed=True),
            action("malformed", "local_read", verified=1, sealed=False),
            action("unknown", "outer")])
        self.assertEqual([(row["outcome"], row["reason"]) for row in call(assess, probe)["decisions"]],
                         [("allow", "matching_rule"), ("deny", "matching_rule"),
                          ("deny", "invalid_action_facts"), ("deny", "unregistered_action")])

    def test_18_policy_cannot_authorize_external_operations_in_fixture(self):
        policy = call(standing, plan("custody"))
        self.assertEqual(len(policy["catalog"]), 8)
        self.assertTrue(all(policy["by_kind"][key][0]["effect"] == "deny"
                            for key in ("external_send", "publication", "money", "main_merge", "locked_write", "memory_write")))

    def test_19_ledger_replays_exact_decision_and_rejects_tamper(self):
        result = call(assess, plan("action-gate", policy=policy_data(), actions=[
            action("allow", "local_read", verified=True, sealed=False)]))["decisions"][0]
        probe = plan("gate-receipt", prior=[], decision=result, at=AT)
        receipt = call(append, probe)
        probe["prior"].append(deepcopy(receipt["receipt"]))
        self.assertTrue(call(append, probe)["replay"])
        probe["prior"][0]["decision"]["outcome"] = "deny"
        with self.assertRaises(GuardianError):
            verify_ledger(probe["prior"])

    def test_20_rule_simulation_names_new_reviews_without_mutating_history(self):
        before = policy_data()
        after = deepcopy(before)
        after["revision"] = "new"
        after["lines"].append("review pause local_read if verified=true")
        actions = [action("read", "local_read", verified=True, sealed=False), action("wire", "memory_write", approval=True)]
        probe = plan("rule-simulation", previous=before, candidate=after, history=actions)
        original = identity(probe)
        result = call(simulate, probe)
        self.assertEqual(result["transition_counts"], {"allow->review": 1, "deny->deny": 1})
        self.assertEqual(result["changes"][0]["candidate"]["matched_rules"], ["pause", "read_verified"])
        self.assertEqual(identity(probe), original)
