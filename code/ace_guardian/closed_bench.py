"""Buktikan isolasi, receipt, pemulihan, dan ECE pada satu fixture dengan artefak yang stabil."""
import argparse
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

from ._contracts import GuardianError, anchor, canonical, decode, identity, integer, obj, read, schema
from ._snapshots import read_fixture, verify, validate_manifest
from .action_gate import assess
from .compliance_reporter import report as compliance_report
from .custody_rules import policy_data
from .ece_publisher import build_report
from .gate_receipt_ledger import append
from .recovery_drill import drill
from .state_forker import fork

SCOPE = "closed_local_fixture"

def section(name, **payload):
    return {"schema": f"ace.guardian.{name}.v1", **payload}

def computed(plan):
    actions = plan["actions"]
    gate = section("action-gate", policy=policy_data(), actions=actions)
    decisions = assess(gate, identity(gate))["decisions"]
    ledger = []
    for decision in decisions:
        step = section("gate-receipt", prior=ledger, decision=decision, at=plan["at"])
        ledger.append(append(step, identity(step))["receipt"])
    start, end = plan["window"]
    controls = [{"id": row["id"], "at": plan["at"], "request_sha256": identity(row)} for row in actions]
    check = section("compliance-report", **{"from": start, "until": end, "ledger": ledger, "actions": controls})
    receipt_coverage = compliance_report(check, identity(check))
    labels = plan["action_outcomes"]
    found = {row["action_id"]: row["outcome"] for row in decisions}
    if not isinstance(labels, dict) or labels.keys() != found.keys():
        raise GuardianError("Label action bench harus tepat satu per aksi.")
    classes = set(policy_data_entry["kind"] for policy_data_entry in policy_data()["actions"])
    return {"checked_actions": len(actions), "correct_outcomes": sum(found[key] == value for key, value in labels.items()),
            "registered_classes": len(classes), "registered_classes_seen": len(classes & {row["kind"] for row in decisions}),
            "receipt_coverage": receipt_coverage, "ledger": ledger,
            "calibration": build_report(plan["calibration"], identity(plan["calibration"]))}

def baselines(plan, root):
    rollback = plan["recovery"]["playbook"]["rollback"]
    source = root / "snapshot"
    failed = root / "failed"
    before = rollback["verified_snapshot"]
    after = rollback["current_snapshot"]
    first = verify(source, before, reject_extras=True)
    second = verify(failed, after, reject_extras=True)
    return source, failed, before, first, second

def measure(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.guardian.closed-bench.v1", (
        "at", "window", "actions", "action_outcomes", "recovery", "calibration"))
    source, failed, manifest, before, damaged = baselines(plan, root)
    with TemporaryDirectory(prefix="ace-guardian-bench-") as tmp:
        twin, recovered = (Path(tmp) / name for name in ("twin", "recovered"))
        stats = fork(source, twin, manifest, identity(manifest))
        selected = sorted(before)[0]
        same_inode = (source / selected).stat().st_ino == (twin / selected).stat().st_ino
        changed = b"guardian fixture mutation\n"
        (twin / selected).write_bytes(changed)
        origin_same = all(read_fixture(source, name) == raw for name, raw in before.items())
        changed_twin = read_fixture(twin, selected) == changed != before[selected]
        recovery = drill(plan["recovery"], identity(plan["recovery"]), source, failed, recovered)
        restored = verify(recovered, manifest, reject_extras=True) == before
        fault_same = all(read_fixture(failed, name) == raw for name, raw in damaged.items())
    return section("closed-guardian-result", plan_sha256=expected, scope=SCOPE,
                   isolation={"files": stats["files"], "distinct_inode": not same_inode,
                              "origin_intact_after_twin_mutation": origin_same, "mutated_twin": changed_twin},
                   recovered_bytes_match=restored, fault_source_intact=fault_same, recovery=recovery, **computed(plan))

def recheck(plan, plan_expected, report, root):
    anchor(plan, plan_expected)
    schema(plan, "ace.guardian.closed-bench.v1", (
        "at", "window", "actions", "action_outcomes", "recovery", "calibration"))
    _, _, manifest, approved_bytes, failed_bytes = baselines(plan, root)
    values = computed(plan)
    schema(report, "ace.guardian.closed-guardian-result.v1",
           ("plan_sha256", "scope", "isolation", "recovered_bytes_match", "fault_source_intact", "recovery", *values))
    if report["plan_sha256"] != plan_expected or report["scope"] != SCOPE or any(report[key] != value for key, value in values.items()):
        raise GuardianError("Hasil deterministik fixture tidak cocok dengan plan terjangkar.")
    isolation = obj(report["isolation"], ("files", "distinct_inode", "origin_intact_after_twin_mutation", "mutated_twin"))
    booleans = [isolation[key] for key in ("distinct_inode", "origin_intact_after_twin_mutation", "mutated_twin")] + [
        report["recovered_bytes_match"], report["fault_source_intact"]]
    if isolation["files"] != len(validate_manifest(manifest)) or any(type(value) is not bool for value in booleans):
        raise GuardianError("Bukti isolasi fixture tidak konsisten.")
    recovery = obj(report["recovery"], ("status", "process_exit", "elapsed_ms", "under_limit", "limit_ms", "playbook", "scope"))
    limit = plan["recovery"]["limit_ms"]
    elapsed = integer(recovery["elapsed_ms"], "Durasi subprocess", 0, 300_000_000)
    exit_code = integer(recovery["process_exit"], "Kode keluar proses", -255, 255)
    measured = exit_code < 0 and recovery["status"] == "fixture_recovered" and elapsed < limit
    if recovery["limit_ms"] != limit or recovery["under_limit"] is not measured or recovery["scope"] != "local_fixture_subprocess":
        raise GuardianError("Batas dan status waktu pemulihan tidak konsisten.")
    recipe = plan["recovery"]["playbook"]
    replay = obj(recovery["playbook"], ("status", "fault", "elapsed_milliseconds", "steps", "rollback_receipt", "playbook_sha256"))
    expected_rollback = {
        "status": "restored_isolated_fixture", "plan_sha256": identity(recipe["rollback"]),
        "sources_reverified": True, "files": len(approved_bytes),
        "added": sorted(approved_bytes.keys() - failed_bytes.keys()),
        "removed": sorted(failed_bytes.keys() - approved_bytes.keys()),
        "replaced": sorted(key for key in approved_bytes.keys() & failed_bytes.keys() if approved_bytes[key] != failed_bytes[key]),
    }
    fingerprint = identity(expected_rollback)
    expected_steps = [
        {"step": "verify_sources", "files": len(approved_bytes), "status": "ok"},
        {"step": "restore_to_fresh_path", "receipt": fingerprint, "status": "ok"},
        {"step": "verify_restored", "status": "ok"},
    ]
    if (replay["playbook_sha256"] != identity(recipe) or replay["fault"] != recipe["fault"]
            or replay["status"] != recovery["status"] or replay["steps"] != expected_steps
            or replay["rollback_receipt"] != {**expected_rollback, "receipt_sha256": fingerprint}
            or not 0 <= replay["elapsed_milliseconds"] <= elapsed):
        raise GuardianError("Receipt atau langkah playbook berbeda dari snapshot fixture.")
    return {"scope": SCOPE, "isolation_checks_passed": all(booleans),
            "receipt_coverage": values["receipt_coverage"]["coverage"], "checked_actions": values["checked_actions"],
            "registered_classes_seen": values["registered_classes_seen"], "recovery_elapsed_ms": elapsed,
            "recovery_under_limit": measured, "ece_by_domain": {
                row["domain"]: row["ece"] for row in values["calibration"]["domains"]}}

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("--expect-sha256", required=True, help="Hash atas JSON kanonis, tanpa newline.")
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--verify-report", type=Path)
    args = parser.parse_args(argv)
    try:
        plan = decode(read(args.plan))
        if args.verify_report:
            result = recheck(plan, args.expect_sha256, decode(read(args.verify_report)), args.root)
        else:
            result = measure(plan, args.expect_sha256, args.root)
    except (OSError, ValueError, KeyError, TypeError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    sys.stdout.buffer.write(canonical(result) + b"\n")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
