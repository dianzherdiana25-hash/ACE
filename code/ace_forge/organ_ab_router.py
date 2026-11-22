"""Siapkan alokasi A/B deterministik atas roster tugas yang dibekukan.

Tugas yang memenuhi prasyarat masuk ke strata berdasarkan jenis dan
tingkat. Dalam tiap strata, hash seed dan ID menentukan urutan alokasi.
Tugas yang belum memenuhi prasyarat dicatat terpisah dari kelompok
analisis. Receipt alokasi membawa identitas artefak dan sumber tugas.
"""
import argparse
from collections import defaultdict
from pathlib import Path
import sys

from ._forge_io import InputError, canonical, decode, digest, entries, identity, integer, object_fields, read_bytes, string
from ._numeric import reference
from .dataset_forge import MAX_BYTES


MAX_TASKS = 25_000


def _arm(raw, refs):
    object_fields(raw, ("artifact_sha256", "artifact_ref"))
    return {"artifact_sha256": digest(raw["artifact_sha256"]),
            "artifact_ref": reference(raw["artifact_ref"], refs, "rujukan artefak")}


def assign(raw, expected_plan_sha256):
    object_fields(raw, ("plan_ref", "seed", "candidate_ratio_bp", "baseline", "candidate", "tasks"))
    if identity(raw) != digest(expected_plan_sha256):
        raise InputError("Roster atau kebijakan A/B berbeda dari anchor.")
    plan_ref = string(raw["plan_ref"], "rujukan rencana A/B")
    ratio = integer(raw["candidate_ratio_bp"], 0, 10_000)
    seed = integer(raw["seed"], 0, 2**64 - 1)
    refs, ids = {plan_ref}, set()
    arms = {name: _arm(raw[name], refs) for name in ("baseline", "candidate")}
    if arms["baseline"]["artifact_sha256"] == arms["candidate"]["artifact_sha256"]:
        raise InputError("Dua lengan A/B harus menunjuk artefak berbeda.")
    controls = defaultdict(list)
    items = entries(raw["tasks"], MAX_TASKS)
    out = []
    for item in items:
        object_fields(item, ("id", "task_ref", "task_kind", "difficulty", "eligible", "eligibility_ref"))
        key = reference(item["id"], ids, "ID tugas")
        task_ref = reference(item["task_ref"], refs, "rujukan tugas")
        eligibility = reference(item["eligibility_ref"], refs, "rujukan kelayakan")
        kind = string(item["task_kind"], "jenis tugas")
        difficulty = string(item["difficulty"], "tingkat tugas")
        if type(item["eligible"]) is not bool:
            raise InputError("Kelayakan tugas harus boolean eksplisit.")
        metadata = {"id": key, "task_ref": task_ref, "eligibility_ref": eligibility,
                    "task_kind": kind, "difficulty": difficulty, "in_comparison": item["eligible"]}
        if item["eligible"]:
            controls[(kind, difficulty)].append((identity([seed, kind, difficulty, key]), metadata))
        else:
            out.append({**metadata, "arm": "baseline", "allocation": "outside_comparison",
                        **arms["baseline"]})
    strata = []
    for (kind, level), group in sorted(controls.items()):
        group.sort(key=lambda pair: (pair[0], pair[1]["id"]))
        candidate = (len(group) * ratio + 5_000) // 10_000
        for index, (_, task) in enumerate(group):
            arm = "candidate" if index < candidate else "baseline"
            out.append({**task, "arm": arm, "allocation": "stratified", **arms[arm]})
        strata.append({"task_kind": kind, "difficulty": level, "candidate": candidate,
                       "baseline": len(group) - candidate, "both_arms": 0 < candidate < len(group)})
    route_rows = []
    for row in sorted(out, key=lambda item: item["id"]):
        record = {**row, "plan_sha256": expected_plan_sha256}
        route_rows.append({**record, "allocation_sha256": identity(record)})
    return {
        "schema": "ace.forge-organ-ab-plan.v1", "plan_ref": plan_ref, "plan_sha256": expected_plan_sha256,
        "seed": seed, "candidate_ratio_bp": ratio, "arms": arms, "strata": strata,
        "eligible": sum(row["in_comparison"] for row in out), "excluded": sum(not row["in_comparison"] for row in out),
        "allocations": route_rows,
    }


def audit(raw, candidate, expected_plan_sha256):
    """Lokalisasikan perubahan satu receipt atau jumlah record keseluruhan."""
    expected = assign(raw, expected_plan_sha256)
    if not isinstance(candidate, dict):
        raise InputError("Receipt alokasi harus objek.")
    given = candidate.get("allocations")
    desired = expected["allocations"]
    if not isinstance(given, list) or len(given) > MAX_TASKS:
        return {"valid": False, "changed": [], "reason": "allocation_list_missing_or_invalid"}
    header = {key: value for key, value in candidate.items() if key != "allocations"}
    check_header = {key: value for key, value in expected.items() if key != "allocations"}
    changes = [row["id"] for row, observed in zip(desired, given) if canonical(row) != canonical(observed)]
    if len(given) < len(desired):
        changes.extend(item["id"] for item in desired[len(given):])
    valid = canonical(candidate) == canonical(expected)
    reason = None if valid else "header_mismatch" if canonical(header) != canonical(check_header) else "allocation_mismatch"
    return {"valid": valid, "changed": changes, "expected_count": len(desired), "given_count": len(given), "reason": reason}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("--expect-plan-sha256", required=True)
    parser.add_argument("--verify", type=Path)
    args = parser.parse_args(argv)
    try:
        policy = decode(read_bytes(args.plan, MAX_BYTES))
        if args.verify:
            result = audit(policy, decode(read_bytes(args.verify, MAX_BYTES)), args.expect_plan_sha256)
            code = int(not result["valid"])
        else:
            result = assign(policy, args.expect_plan_sha256)
            code = 0
        sys.stdout.write(canonical(result).decode("utf-8") + "\n")
    except (OSError, ValueError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
