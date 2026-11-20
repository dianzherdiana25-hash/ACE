"""Susun pencarian hiperparameter successive halving berbatas kredit.

Setiap rung memesan porsi yang sama per konfigurasi yang masih aktif.
Hasil harus menunjuk resep, rung, dan metrik yang terdaftar. Rung
parsial tidak menghasilkan eliminasi. Anggaran yang habis dilaporkan
sebagai penghentian pencarian dan receipt per rung tetap terlacak.
"""
import argparse
from dataclasses import dataclass
from pathlib import Path
import sys

from ._forge_io import InputError, canonical, decode, digest, entries, identity, integer, object_fields, read_bytes, string
from ._numeric import reference
from .dataset_forge import MAX_BYTES


MAX_CONFIGS = 128
MAX_RUNGS = 8
MAX_BUDGET = 10**9


@dataclass(frozen=True, slots=True)
class Configuration:
    key: str
    sha: str
    ref: str

    @classmethod
    def read(cls, raw, keys, shas, refs):
        object_fields(raw, ("id", "recipe_sha256", "recipe_ref"))
        checksum = digest(raw["recipe_sha256"])
        if checksum in shas:
            raise InputError("Resep konfigurasi ganda.")
        shas.add(checksum)
        return cls(reference(raw["id"], keys, "ID konfigurasi"), checksum,
                   reference(raw["recipe_ref"], refs, "rujukan resep"))


def _policy(raw):
    object_fields(raw, ("policy_ref", "direction", "metric", "limit_units", "reduction", "rung_units", "configurations"))
    ref = string(raw["policy_ref"], "rujukan kebijakan")
    direction = raw["direction"]
    if direction not in ("maximize", "minimize"):
        raise InputError("Arah optimasi tidak dikenal.")
    metric = string(raw["metric"], "nama metrik")
    budget = integer(raw["limit_units"], 1, MAX_BUDGET)
    reduction = integer(raw["reduction"], 2, MAX_CONFIGS)
    rungs = [integer(cost, 1, MAX_BUDGET) for cost in entries(raw["rung_units"], MAX_RUNGS)]
    if not rungs or any(base >= next_cost for base, next_cost in zip(rungs, rungs[1:])):
        raise InputError("Anggaran per rung harus naik secara ketat.")
    keys, shas, refs = set(), set(), {ref}
    configs = sorted((Configuration.read(row, keys, shas, refs) for row in entries(raw["configurations"], MAX_CONFIGS)),
                     key=lambda row: row.key)
    if len(configs) < 2:
        raise InputError("Pencarian membutuhkan dua konfigurasi berbeda.")
    return ref, direction, metric, budget, reduction, rungs, configs, refs


def _result_rows(raw, configs, rungs, metric, policy_hash, refs):
    known = {config.key: config for config in configs}
    by_slot = {}
    for row in entries(raw, MAX_CONFIGS * MAX_RUNGS):
        object_fields(row, ("id", "rung", "recipe_sha256", "policy_sha256", "trial_ref", "metric", "score", "units"))
        key = string(row["id"], "ID konfigurasi")
        rung = integer(row["rung"], 0, len(rungs) - 1)
        if key not in known or (rung, key) in by_slot:
            raise InputError("Konfigurasi trial tidak dikenal atau ganda per rung.")
        config = known[key]
        if (digest(row["recipe_sha256"]) != config.sha or digest(row["policy_sha256"]) != policy_hash
                or row["metric"] != metric or integer(row["units"], 1, MAX_BUDGET) != rungs[rung]):
            raise InputError("Trial tidak cocok dengan resep, kebijakan, metrik, atau anggaran rung.")
        by_slot[rung, key] = {
            "id": key, "score": integer(row["score"], -MAX_BUDGET, MAX_BUDGET),
            "trial_ref": reference(row["trial_ref"], refs, "rujukan trial"), "recipe_sha256": config.sha,
        }
    return by_slot


def _trial(config, number, units, metric, policy_hash):
    return {"id": config.key, "rung": number, "units": units, "metric": metric,
            "recipe_sha256": config.sha, "recipe_ref": config.ref, "policy_sha256": policy_hash}


def plan(policy, observations, expected_policy_sha256):
    if identity(policy) != digest(expected_policy_sha256):
        raise InputError("Kebijakan pencarian berbeda dari anchor.")
    policy_ref, direction, metric, budget, reduction, rungs, active, refs = _policy(policy)
    observations_by_slot = _result_rows(observations, active, rungs, metric, expected_policy_sha256, refs)
    used, history, pending = 0, [], []
    status, winner = "complete", None
    for number, units in enumerate(rungs):
        need = len(active) * units
        if need + used > budget:
            status = "budget_exhausted"
            break
        actual = []
        for config in active:
            observed = observations_by_slot.pop((number, config.key), None)
            if observed is None:
                pending.append(_trial(config, number, units, metric, expected_policy_sha256))
            else:
                actual.append(observed)
                used += units
        if pending:
            history.append({"rung": number, "units_per_trial": units, "completed": sorted(actual, key=lambda row: row["id"]),
                            "ranking": None, "advanced": None})
            status = "awaiting_trials"
            break
        order = sorted(actual, key=lambda row: ((-1 if direction == "maximize" else 1) * row["score"], row["id"]))
        retired = number == len(rungs) - 1
        keep = 1 if retired else (len(active) + reduction - 1) // reduction
        chosen = [row["id"] for row in order[:keep]]
        history.append({"rung": number, "units_per_trial": units, "completed": order,
                        "ranking": [row["id"] for row in order], "advanced": chosen})
        survivors = set(chosen)
        active = [config for config in active if config.key in survivors]
        if retired:
            winner = order[0]
    if observations_by_slot:
        raise InputError("Laporan memuat trial sebelum instruksi atau setelah eliminasi.")
    reserved = sum(row["units"] for row in pending)
    return {
        "schema": "ace.forge-hyperparam-search.v1", "policy_ref": policy_ref, "policy_sha256": expected_policy_sha256,
        "metric": metric, "direction": direction, "status": status, "winner": winner, "rungs": history,
        "pending": pending, "budget": {"limit_units": budget, "used_units": used, "reserved_units": reserved,
                                       "unassigned_units": budget - used - reserved},
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("policy", type=Path)
    parser.add_argument("observations", type=Path)
    parser.add_argument("--expect-policy-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        value = plan(decode(read_bytes(args.policy, MAX_BYTES)), decode(read_bytes(args.observations, MAX_BYTES)),
                     args.expect_policy_sha256)
        sys.stdout.write(canonical(value).decode("utf-8") + "\n")
    except (OSError, ValueError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
