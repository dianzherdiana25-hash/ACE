"""Gabungkan adaptor LoRA lintas tugas atas satu lapisan dan basis.

Faktor A disusun bertumpuk, dan setiap blok kolom B diskalakan menurut
bobot tugas serta alpha/rank asal. Delta hasil sama dengan jumlah
tertimbang delta masing-masing. Probe mencatat jarak dari adaptor
asal tugas supaya perubahan akibat campuran tetap dapat diperiksa.
"""
import argparse
from dataclasses import dataclass
from math import fsum
from pathlib import Path
import sys

from ._forge_io import InputError, canonical, decode, digest, entries, identity, integer, object_fields, read_bytes, string
from ._numeric import MAX_FEATURES, operation_budget, real, reference, stable, vector
from .dataset_forge import MAX_BYTES


MAX_RANK = 128
MAX_TASKS = 12


@dataclass(frozen=True, slots=True)
class Factor:
    base: str
    layer: str
    alpha: float
    rank: int
    features: int
    outputs: int
    a: list
    b: list

    @classmethod
    def read(cls, row):
        object_fields(row, ("schema", "base_sha256", "layer", "rank", "alpha", "a", "b"))
        if row["schema"] != "ace.lora-dense-adapter.v1":
            raise InputError("Masukan bukan adaptor LoRA dense.")
        rank = integer(row["rank"], 1, MAX_RANK)
        left = entries(row["a"], MAX_RANK)
        right = entries(row["b"], MAX_FEATURES)
        if len(left) != rank or not isinstance(left[0], list) or not 1 <= len(left[0]) <= MAX_FEATURES or not right:
            raise InputError("Bentuk faktor LoRA tidak sah.")
        width = len(left[0])
        return cls(digest(row["base_sha256"]), string(row["layer"], "lapisan"),
                   real(row["alpha"], 1e-8, MAX_RANK), rank, width, len(right),
                   [vector(value, width, "faktor A", limit=1e9) for value in left],
                   [vector(value, rank, "faktor B", limit=1e9) for value in right])

    def layout(self):
        return self.base, self.layer, self.features, self.outputs

    def delta(self, example):
        projection = [fsum(a * x for a, x in zip(row, example, strict=True)) for row in self.a]
        values = [self.alpha / self.rank * fsum(b * x for b, x in zip(row, projection, strict=True)) for row in self.b]
        stable(values)
        return values


def _input(raw, expected, snapshots):
    object_fields(raw, ("recipe_ref", "maximum_rank", "maximum_probe_delta", "contributors", "probes"))
    if identity(raw) != digest(expected):
        raise InputError("Resep merge lintas tugas berbeda dari anchor.")
    recipe = string(raw["recipe_ref"], "rujukan resep")
    refs, ids, used = {recipe}, set(), set()
    by_hash = {}
    for value in entries(snapshots, MAX_TASKS):
        checksum = identity(value)
        if checksum in by_hash:
            raise InputError("Snapshot adaptor ganda.")
        by_hash[checksum] = Factor.read(value)
    factors = {}
    for row in entries(raw["contributors"], MAX_TASKS):
        object_fields(row, ("task_kind", "adapter_sha256", "adapter_ref", "weight_bp"))
        task = reference(row["task_kind"], ids, "jenis tugas")
        pointer = reference(row["adapter_ref"], refs, "rujukan adaptor")
        checksum = digest(row["adapter_sha256"])
        if checksum in used or checksum not in by_hash:
            raise InputError("Checksum adaptor ganda atau hilang.")
        used.add(checksum)
        factors[task] = (by_hash[checksum], integer(row["weight_bp"], 1, 10_000), checksum, pointer)
    if len(factors) < 2 or sum(i[1] for i in factors.values()) != 10_000 or used != by_hash.keys():
        raise InputError("Campuran memerlukan dua tugas atau lebih dan bobot tepat 10.000 basis points.")
    return recipe, refs, dict(sorted(factors.items()))


def merge(raw, snapshots, expected):
    recipe, refs, factors = _input(raw, expected, snapshots)
    cap = integer(raw["maximum_rank"], 1, MAX_RANK)
    tolerance = real(raw["maximum_probe_delta"], 0, 10**12)
    base, layer, width, output = next(iter(factors.values()))[0].layout()
    if any(value[0].layout() != (base, layer, width, output) for value in factors.values()):
        raise InputError("Basis, lapisan, atau dimensi adaptor tidak cocok.")
    rank = sum(item[0].rank for item in factors.values())
    if rank > cap:
        raise InputError("Jumlah rank melampaui batas rencana.")
    a = []
    b = [[] for _ in range(output)]
    for value, weight, _, _ in factors.values():
        a.extend(value.a)
        scale = value.alpha / value.rank * weight / 10_000
        for left, right in zip(b, value.b, strict=True):
            left.extend(scalar * scale for scalar in right)
    merged = {"schema": "ace.lora-dense-adapter.v1", "base_sha256": base,
              "layer": layer, "rank": rank, "alpha": rank, "a": a, "b": b}
    actual = Factor.read(merged)
    probes, test_ids, coverage = [], set(), set()
    rows = entries(raw["probes"], 1000)
    operation_budget(len(rows) * rank * (width + output))
    for row in rows:
        object_fields(row, ("id", "task_kind", "input", "source_ref"))
        key = reference(row["id"], test_ids, "ID probe")
        task = string(row["task_kind"], "jenis tugas probe")
        if task not in factors:
            raise InputError("Probe menunjuk tugas di luar resep.")
        pointer = reference(row["source_ref"], refs, "rujukan probe")
        example = vector(row["input"], width, "input probe")
        local = factors[task][0].delta(example)
        combined = actual.delta(example)
        error = max(abs(x-y) for x, y in zip(local, combined, strict=True))
        probes.append({"id": key, "task_kind": task, "source_ref": pointer, "local_delta": local, "merged_delta": combined,
                       "max_absolute_delta": error, "within_probe_limit": error <= tolerance})
        coverage.add(task)
    untested = sorted(factors.keys() - coverage)
    failed = sorted(row["id"] for row in probes if not row["within_probe_limit"])
    return {
        "schema": "ace.forge-multitask-merge.v1", "recipe_ref": recipe, "recipe_sha256": expected,
        "adapter": merged, "adapter_sha256": identity(merged),
        "contributors": [{"task_kind": key, "source_sha256": value[2], "source_ref": value[3], "weight_bp": value[1]}
                         for key, value in factors.items()],
        "probes": sorted(probes, key=lambda row: row["id"]), "failed_probes": failed, "untested_tasks": untested,
        "status": "hold" if failed else "partially_probed" if untested else "numeric_probes_within_limits",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recipe", type=Path)
    parser.add_argument("adapters", type=Path)
    parser.add_argument("--expect-recipe-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        result = merge(decode(read_bytes(args.recipe, MAX_BYTES)), decode(read_bytes(args.adapters, MAX_BYTES)),
                       args.expect_recipe_sha256)
        sys.stdout.write(canonical(result).decode("utf-8") + "\n")
    except (OSError, ValueError, OverflowError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return int(result["status"] == "hold")


if __name__ == "__main__":
    raise SystemExit(main())
