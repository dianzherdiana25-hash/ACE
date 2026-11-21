"""Lacak retensi kasus terhadap satu baseline sepanjang checkpoint tempa.

Snapshot direncanakan berurutan dan memakai roster yang sama.
Kehilangan setelah observasi retained dicatat sebagai delayed, dan
pulih setelah regressed sebagai recovery. Interval tanpa bukti
memutus rentetan dan tetap terlihat di setiap domain.
"""
import argparse
from collections import defaultdict
from pathlib import Path
import sys

from . import forgetting_guard
from ._forge_io import InputError, canonical, decode, digest, entries, identity, object_fields, read_bytes, string, utc_stamp
from ._numeric import reference
from .dataset_forge import MAX_BYTES


MAX_SNAPSHOTS = 52
MAX_CELLS = 100_000


def _arm_rows(raw, cases, refs):
    observations = {}
    for row in entries(raw, forgetting_guard.MAX_CASES):
        object_fields(row, ("case_id", "assessment"))
        key = string(row["case_id"], "ID kasus")
        if key in observations or key not in cases:
            raise InputError("Observasi ganda atau kasus di luar protokol longitudinal.")
        observations[key] = forgetting_guard._arm(row["assessment"], refs)
    return observations


def _timeline(raw, artifacts, cases, refs):
    stored = {}
    for row in entries(raw, MAX_SNAPSHOTS):
        object_fields(row, ("checkpoint_sha256", "snapshot_ref", "assessments"))
        key = digest(row["checkpoint_sha256"])
        if key in stored or key not in artifacts:
            raise InputError("Snapshot ganda atau checkpoint di luar timeline.")
        stored[key] = (reference(row["snapshot_ref"], refs, "rujukan snapshot"),
                       _arm_rows(row["assessments"], cases, refs))
    return stored


def assess(raw, observed, expected):
    object_fields(raw, ("plan_ref", "protocol", "baseline_sha256", "checkpoints", "observations_sha256"))
    if identity(raw) != digest(expected):
        raise InputError("Timeline berbeda dari anchor.")
    if identity(observed) != digest(raw["observations_sha256"]):
        raise InputError("Receipt longitudinal berbeda dari komitmen observasi.")
    source = string(raw["plan_ref"], "rujukan timeline")
    proto, cases, refs = forgetting_guard._protocol(raw["protocol"])
    reference(source, refs, "rujukan rencana")
    baseline = digest(raw["baseline_sha256"])
    lineup = {}
    previous = None
    for row in entries(raw["checkpoints"], MAX_SNAPSHOTS):
        object_fields(row, ("checkpoint_sha256", "checkpoint_ref", "at"))
        key = digest(row["checkpoint_sha256"])
        at = utc_stamp(row["at"])
        if key == baseline or key in lineup or previous is not None and at <= previous:
            raise InputError("Checkpoint ganda atau jadwal longitudinal tidak meningkat.")
        lineup[key] = (reference(row["checkpoint_ref"], refs, "rujukan checkpoint"), at.isoformat())
        previous = at
    if not lineup or len(lineup) * len(cases) > MAX_CELLS:
        raise InputError("Timeline kosong atau matriks kasus terlalu besar.")
    object_fields(observed, ("receipt_ref", "baseline_sha256", "baseline", "snapshots"))
    if digest(observed["baseline_sha256"]) != baseline:
        raise InputError("Identitas baseline receipt berbeda dari timeline.")
    receipt = reference(observed["receipt_ref"], refs, "rujukan receipt")
    initial = _arm_rows(observed["baseline"], cases, refs)
    snapshots = _timeline(observed["snapshots"], lineup, cases, refs)
    histories = defaultdict(list)
    checkpoints = []
    grouped_cases = sorted(cases)
    for key, (pointer, at) in lineup.items():
        source_ref, result = snapshots.get(key, (None, {}))
        joined = [{"case_id": case, "baseline": initial.get(case), "candidate": result.get(case)} for case in grouped_cases]
        verdict = forgetting_guard.screen({"protocol": proto, "results": joined}, identity(proto))
        checkpoint = {"checkpoint_sha256": key, "checkpoint_ref": pointer, "at": at, "snapshot_ref": source_ref,
                      "status": verdict["status"], "domains": []}
        for domain in verdict["domains"]:
            checkpoint["domains"].append({key: value for key, value in domain.items() if key != "cases"})
            for row in domain["cases"]:
                histories[row["case_id"]].append({"checkpoint_sha256": key, "status": row["status"],
                                                 "assessment_ref": row["candidate"]["assessment_ref"] if row["candidate"] else None})
        checkpoints.append(checkpoint)

    transitions = []
    for key, values in sorted(histories.items()):
        start = initial.get(key)
        if not start or not start["passed"]:
            continue
        previous = None
        current_run = longest = 0
        delayed = []
        recoveries = []
        for row in values:
            state = row["status"]
            if state == "regressed":
                current_run += 1
                longest = max(longest, current_run)
                if previous == "retained":
                    delayed.append(row["checkpoint_sha256"])
            else:
                current_run = 0
                if state == "retained" and previous == "regressed":
                    recoveries.append(row["checkpoint_sha256"])
            previous = state
        transitions.append({**cases[key], "baseline_assessment_ref": start["assessment_ref"], "longest_regression": longest,
                            "delayed_regressions": delayed, "recoveries": recoveries, "timeline": values})
    return {"schema": "ace.forge-longitudinal-forgetting.v1", "plan_ref": source, "plan_sha256": expected,
            "protocol_ref": proto["protocol_ref"], "protocol_sha256": identity(proto),
            "baseline_sha256": baseline, "receipt_ref": receipt, "observations_sha256": raw["observations_sha256"],
            "checkpoints": checkpoints, "baseline_pass_cases": transitions}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("receipts", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        product = assess(decode(read_bytes(args.plan, MAX_BYTES)), decode(read_bytes(args.receipts, MAX_BYTES)),
                         args.expect_sha256)
        sys.stdout.write(canonical(product).decode("utf-8") + "\n")
    except (OSError, ValueError, OverflowError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return int(any(row["status"] == "hold" for row in product["checkpoints"]))


if __name__ == "__main__":
    raise SystemExit(main())
