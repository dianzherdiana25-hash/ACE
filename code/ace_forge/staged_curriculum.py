"""Susun bahan tempa bertahap di atas dataset berkustodi.

Kesulitan diberikan lewat bukti luar. Tahap mengambil contoh baru dari
pita yang tidak tumpang tindih dan tepat di bawah batasnya. Replay
memakai contoh terpilih dari tahap lampau. Held-out dan contoh tanpa
anotasi tercatat sebagai pengecualian. Ekspor menunggu semua kuota.
"""
import argparse
from collections import Counter
from pathlib import Path
import sys

from ._forge_io import InputError, canonical, decode, digest, entries, identity, integer, object_fields, read_bytes, string
from ._numeric import reference
from .dataset_custody import MAX_MANIFEST_BYTES, verify
from .dataset_forge import MAX_BYTES, MAX_ROWS


MAX_STAGES = 100


def _plan(raw, expected):
    object_fields(raw, ("plan_ref", "seed", "stages", "annotations"))
    if identity(raw) != digest(expected):
        raise InputError("Rencana bertahap berbeda dari anchor.")
    ref = string(raw["plan_ref"], "rujukan kurikulum")
    seed = integer(raw["seed"], 0, 2**64 - 1)
    ids, pointers = set(), {ref}
    stages = []
    low = 0
    for row in entries(raw["stages"], MAX_STAGES):
        object_fields(row, ("id", "max_difficulty_bp", "new_examples", "replay_limit"))
        key = reference(row["id"], ids, "ID tahap")
        high = integer(row["max_difficulty_bp"], low, 10_000)
        count = integer(row["new_examples"], 1, MAX_ROWS)
        replay = integer(row["replay_limit"], 0, MAX_ROWS)
        stages.append((key, low, high, count, replay))
        low = high + 1
    if not stages or sum(row[-2] for row in stages) > MAX_ROWS:
        raise InputError("Jumlah tahap atau total kuota tidak sah.")
    annotations = {}
    for row in entries(raw["annotations"], MAX_ROWS):
        object_fields(row, ("example_id", "difficulty_bp", "evidence_ref"))
        key = string(row["example_id"], "ID contoh anotasi")
        if key in annotations:
            raise InputError("Anotasi sulit ganda.")
        annotations[key] = (integer(row["difficulty_bp"], 0, 10_000),
                            reference(row["evidence_ref"], pointers, "rujukan anotasi"))
    return ref, seed, stages, annotations


def _order(seed, stage, phase, row):
    identifier = row["example_id"]
    return identity([seed, stage, phase, identifier]), identifier


def _pointers(examples):
    return [{key: value for key, value in row.items() if key != "record"} for row in examples]


def prepare(data, manifest, expected_head, raw, expected):
    ref, seed, stages, annotations = _plan(raw, expected)
    if not verify(data, manifest, expected_head)["valid"]:
        raise InputError("Dataset tidak lolos verifikasi kustodi.")
    candidates = []
    excluded = Counter()
    seen = set()
    for line in data.splitlines():
        row = decode(line)
        key = row["example_id"]
        seen.add(key)
        if row["split"] == "held_out":
            excluded["held_out"] += 1
        elif key not in annotations:
            excluded["unannotated"] += 1
        elif annotations[key][0] > stages[-1][2]:
            excluded["above_final_stage"] += 1
        else:
            difficulty, proof = annotations[key]
            candidates.append({"example_id": key, "difficulty_bp": difficulty, "difficulty_ref": proof,
                               "dataset_evidence_ref": row["provenance"]["evidence_ref"], "record": row})
    if annotations.keys() - seen:
        raise InputError("Anotasi menunjuk contoh di luar dataset.")
    history = []
    outputs, audits = {}, []
    for key, low, high, quota, limit in stages:
        ordered = sorted((item for item in candidates if low <= item["difficulty_bp"] <= high),
                         key=lambda row: _order(seed, key, "new", row))
        chosen = ordered[:quota]
        replay = sorted(history, key=lambda row: _order(seed, key, "replay", row))[:limit]
        audits.append({"id": key, "difficulty_range_bp": [low, high], "available": len(ordered), "requested": quota,
                       "shortfall": max(0, quota - len(ordered)), "new": _pointers(chosen), "replay": _pointers(replay)})
        outputs[key] = [row["record"] for row in replay + chosen]
        history.extend(chosen)
    held = any(row["shortfall"] for row in audits)
    return ({} if held else outputs), {
        "schema": "ace.forge-staged-curriculum.v1", "plan_ref": ref, "plan_sha256": expected,
        "dataset_head_sha256": expected_head, "status": "hold" if held else "ready",
        "excluded": dict(sorted(excluded.items())), "stages": audits,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("plan", type=Path)
    parser.add_argument("--expect-head", required=True)
    parser.add_argument("--expect-plan-sha256", required=True)
    parser.add_argument("--export-stage")
    args = parser.parse_args(argv)
    try:
        outputs, report = prepare(read_bytes(args.dataset, MAX_BYTES), decode(read_bytes(args.manifest, MAX_MANIFEST_BYTES)),
                                  args.expect_head, decode(read_bytes(args.plan, MAX_BYTES)), args.expect_plan_sha256)
        if args.export_stage:
            if args.export_stage not in {item["id"] for item in report["stages"]}:
                raise InputError("ID tahap ekspor tidak dikenal.")
            for row in outputs.get(args.export_stage, []):
                sys.stdout.write(canonical(row).decode("utf-8") + "\n")
        else:
            sys.stdout.write(canonical(report).decode("utf-8") + "\n")
    except (OSError, ValueError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return int(report["status"] == "hold")


if __name__ == "__main__":
    raise SystemExit(main())
