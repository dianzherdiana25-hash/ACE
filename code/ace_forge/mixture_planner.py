"""Rencanakan campuran data dari kapasitas dan prioritas per jenis tugas.

Minimum tiap jenis dialokasikan dulu. Sisa kursi dialokasikan dengan
metode highest averages pada bobot dan kuota tersisa, sehingga pilihan
dapat diulang. Jenis yang stoknya kurang dan contoh yang kurang mutu
muncul sebagai temuan yang dapat ditelusuri melalui rujukan file.
"""
import argparse
from collections import defaultdict
from dataclasses import dataclass
from fractions import Fraction
from heapq import heappop, heappush
from pathlib import Path
import sys

from ._forge_io import InputError, canonical, decode, digest, entries, identity, integer, object_fields, read_bytes, string
from ._numeric import reference
from .dataset_forge import MAX_BYTES
from .forgetting_guard import _fraction


MAX_CANDIDATES = 25_000


@dataclass(frozen=True, slots=True)
class Quota:
    kind: str
    minimum: int
    maximum: int
    weight: int

    @classmethod
    def read(cls, row, names):
        object_fields(row, ("task_kind", "minimum", "maximum", "weight"))
        minimum = integer(row["minimum"], 0, MAX_CANDIDATES)
        return cls(reference(row["task_kind"], names, "jenis tugas"), minimum,
                   integer(row["maximum"], minimum, MAX_CANDIDATES), integer(row["weight"], 1, 1000))


def _ranked(candidates, quotas, minimum, refs):
    accepted = defaultdict(list)
    excluded = []
    ids = set()
    for row in entries(candidates, MAX_CANDIDATES):
        object_fields(row, ("example_id", "task_kind", "split", "status", "score_bp", "evidence_ref"))
        example = reference(row["example_id"], ids, "ID contoh")
        kind = string(row["task_kind"], "jenis tugas")
        evidence = reference(row["evidence_ref"], refs, "rujukan bukti")
        if row["split"] not in ("train", "held_out"):
            raise InputError("Partisi contoh tidak dikenal.")
        status = row["status"]
        if status not in ("ready", "hold", "unscored"):
            raise InputError("Status mutu tidak dikenal.")
        score = row["score_bp"]
        if status == "unscored":
            if score is not None:
                raise InputError("Contoh unscored harus memiliki skor null.")
        else:
            score = integer(score, 0, 10_000)
        decision = {"example_id": example, "task_kind": kind, "evidence_ref": evidence, "score_bp": score}
        if row["split"] != "train":
            reason = "held_out"
        elif kind not in quotas:
            reason = "task_not_requested"
        elif status != "ready":
            reason = f"quality_{status}"
        elif score < minimum:
            reason = "below_mixture_floor"
        else:
            accepted[kind].append(decision)
            continue
        excluded.append({**decision, "reason": reason})
    for records in accepted.values():
        records.sort(key=lambda row: (-row["score_bp"], row["example_id"]))
    return accepted, sorted(excluded, key=lambda row: row["example_id"])


def _allocate(quotas, caps, target):
    draws = {key: quota.minimum for key, quota in quotas.items()}
    open_quotas = []
    for key, quota in quotas.items():
        if caps[key] > quota.minimum:
            heappush(open_quotas, (-quota.weight, key))
    for _ in range(target - sum(draws.values())):
        _, key = heappop(open_quotas)
        draws[key] += 1
        if draws[key] < caps[key]:
            quota = quotas[key]
            heappush(open_quotas, (-Fraction(quota.weight, draws[key] - quota.minimum + 1), key))
    return draws


def plan(raw, expected_sha256):
    object_fields(raw, ("policy_ref", "quality_report_ref", "target_examples", "minimum_score_bp", "quotas", "candidates"))
    observed = identity(raw)
    if digest(expected_sha256) != observed:
        raise InputError("Kebijakan atau stok kandidat berubah sejak anchor.")
    policy = string(raw["policy_ref"], "rujukan kebijakan")
    refs = {policy}
    inventory = reference(raw["quality_report_ref"], refs, "rujukan mutu")
    target = integer(raw["target_examples"], 1, MAX_CANDIDATES)
    minimum = integer(raw["minimum_score_bp"], 0, 10_000)
    keys = set()
    quotas = {row.kind: row for row in (Quota.read(item, keys) for item in entries(raw["quotas"], 100))}
    if not quotas:
        raise InputError("Campuran harus memiliki setidaknya satu kuota.")
    accepted, excluded = _ranked(raw["candidates"], quotas, minimum, refs)
    capacity = {key: min(quota.maximum, len(accepted[key])) for key, quota in quotas.items()}
    below = sorted(key for key, quota in quotas.items() if capacity[key] < quota.minimum)
    below_reports = [
        {"task_kind": key, "required": quotas[key].minimum, "available": capacity[key]} for key in below
    ]
    blockers = [reason for reason, failed in (
        ("unmet_minimum", bool(below)),
        ("sum_minimum_above_target", sum(row.minimum for row in quotas.values()) > target),
        ("insufficient_capacity", sum(capacity.values()) < target),
    ) if failed]
    draws = _allocate(quotas, capacity, target) if not blockers else None
    plan_by_kind = []
    for key, quota in sorted(quotas.items()):
        count = draws[key] if draws is not None else None
        plan_by_kind.append({"task_kind": key, "minimum": quota.minimum, "capacity": capacity[key],
                             "eligible": len(accepted[key]), "weight": quota.weight, "count": count,
                             "share": _fraction(Fraction(count, target)) if count is not None else None,
                             "examples": accepted[key][:count] if count is not None else []})
    return {"schema": "ace.forge-mixture-plan.v1", "input_sha256": observed, "policy_ref": policy,
            "quality_report_ref": inventory, "target_examples": target, "capacity": sum(capacity.values()),
            "status": "hold" if blockers else "ready", "blockers": blockers, "minimum_shortfalls": below_reports,
            "planned_examples": sum(draws.values()) if draws is not None else 0,
            "by_task": plan_by_kind, "excluded": excluded}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--expect-input-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        result = plan(decode(read_bytes(args.input, MAX_BYTES)), args.expect_input_sha256)
        sys.stdout.write(canonical(result).decode("utf-8") + "\n")
    except (OSError, ValueError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return int(result["status"] != "ready")


if __name__ == "__main__":
    raise SystemExit(main())
