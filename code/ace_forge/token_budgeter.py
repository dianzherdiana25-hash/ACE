"""Hitung anggaran token tempa dari ukuran contoh dan resep batch.

Perkiraan membedakan token nyata dari padding, pengulangan, dan
cadangan. Tarif diambil dari kebijakan yang ditambatkan dan dihitung
dengan pecahan eksak dalam unit internal. Laporan bisa menahan rencana
yang melebihi batas tanpa memulai proses tempa atau transaksi.
"""
import argparse
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
import sys

from ._forge_io import InputError, canonical, decode, digest, entries, identity, integer, object_fields, read_bytes, string
from ._numeric import reference
from .dataset_forge import MAX_BYTES
from .forgetting_guard import _fraction


MAX_JOBS = 200
MAX_BATCHES = 1000
MAX_EXAMPLES = 100_000
MAX_TOKENS = 10**12


@dataclass(frozen=True, slots=True)
class Batch:
    key: str
    ref: str
    real: int
    processed: int
    examples: int

    @classmethod
    def read(cls, row, policy, seen, refs):
        object_fields(row, ("id", "source_ref", "padding", "lengths"))
        key = reference(row["id"], seen, "ID batch")
        source = reference(row["source_ref"], refs, "rujukan batch")
        mode = row["padding"]
        if mode not in ("packed", "longest"):
            raise InputError("Mode padding tidak dikenal.")
        lengths = []
        for item in entries(row["lengths"], MAX_EXAMPLES):
            object_fields(item, ("input_tokens", "target_tokens"))
            prefix = integer(item["input_tokens"], 0, policy)
            response = integer(item["target_tokens"], 0, policy)
            lengths.append(integer(prefix + response, 1, policy))
        if not lengths:
            raise InputError("Batch kosong tidak memiliki perkiraan token.")
        real = sum(lengths)
        capacity = max(lengths) * len(lengths) if mode == "longest" else real
        return cls(key, source, real, capacity, len(lengths))

    def export(self, rounds):
        return {"id": self.key, "source_ref": self.ref, "examples": self.examples, "real_tokens": self.real * rounds,
                "processed_tokens": self.processed * rounds,
                "padding_tokens": (self.processed - self.real) * rounds, "passes": rounds}


def ceil_div(numerator, denominator):
    return (numerator + denominator - 1) // denominator


def estimate(raw, expected):
    object_fields(raw, ("policy_ref", "unit", "maximum_tokens", "maximum_cost_units", "reserve_bp",
                        "context_limit_tokens", "stages"))
    if identity(raw) != digest(expected):
        raise InputError("Kebijakan atau hitungan token berbeda dari anchor.")
    source = string(raw["policy_ref"], "rujukan kebijakan")
    unit = string(raw["unit"], "satuan tarif")
    ceiling = integer(raw["maximum_tokens"], 0, MAX_TOKENS)
    cost_cap = integer(raw["maximum_cost_units"], 0, MAX_TOKENS)
    reserve = integer(raw["reserve_bp"], 0, 10_000)
    context = integer(raw["context_limit_tokens"], 1, 1_000_000)
    refs, keys = {source}, set()
    stages = []
    real, processed, reserved = 0, 0, 0
    subtotal, reserved_total = Fraction(), Fraction()
    batches_seen = examples_seen = 0
    for row in entries(raw["stages"], MAX_JOBS):
        object_fields(row, ("id", "stage_ref", "passes", "rate_units_per_million", "batches"))
        key = reference(row["id"], keys, "ID tahap")
        pointer = reference(row["stage_ref"], refs, "rujukan tahap")
        passes = integer(row["passes"], 1, 10_000)
        rate = integer(row["rate_units_per_million"], 0, MAX_TOKENS)
        batch_ids = set()
        batch_list = entries(row["batches"], MAX_BATCHES)
        batches_seen += len(batch_list)
        if not batch_list or batches_seen > MAX_BATCHES:
            raise InputError("Tahap membutuhkan batch dan jumlah batch total harus dalam batas.")
        batches = []
        for item in batch_list:
            batch = Batch.read(item, context, batch_ids, refs)
            examples_seen += batch.examples
            if examples_seen > MAX_EXAMPLES:
                raise InputError("Total contoh melampaui batas.")
            batches.append(batch.export(passes))
        batches.sort(key=lambda item: item["id"])
        useful = sum(row["real_tokens"] for row in batches)
        estimated = sum(row["processed_tokens"] for row in batches)
        with_reserve = ceil_div(estimated * (10_000 + reserve), 10_000)
        cost = Fraction(estimated * rate, 1_000_000)
        safe_cost = Fraction(with_reserve * rate, 1_000_000)
        stages.append({"id": key, "stage_ref": pointer, "passes": passes, "rate_units_per_million": rate,
                       "real_tokens": useful, "processed_tokens": estimated, "reserved_tokens_total": with_reserve,
                       "cost_units": _fraction(cost), "reserved_cost_units": _fraction(safe_cost), "batches": batches})
        real += useful
        processed += estimated
        reserved += with_reserve
        subtotal += cost
        reserved_total += safe_cost
    if not stages:
        raise InputError("Resep anggaran memerlukan tahap.")
    blockers = [key for key, exceeded in (("token_cap", reserved > ceiling), ("cost_cap", reserved_total > cost_cap))
                if exceeded]
    return {"schema": "ace.forge-token-budget.v1", "policy_ref": source, "input_sha256": expected, "unit": unit,
            "status": "hold" if blockers else "within_budget", "blockers": blockers,
            "real_tokens": real, "processed_tokens": processed, "padding_tokens": processed - real,
            "reserved_tokens_total": reserved, "token_margin": ceiling - reserved,
            "cost_units": _fraction(subtotal), "reserved_cost_units": _fraction(reserved_total),
            "cost_margin_units": _fraction(cost_cap - reserved_total), "stages": sorted(stages, key=lambda item: item["id"])}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--expect-input-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        result = estimate(decode(read_bytes(args.input, MAX_BYTES)), args.expect_input_sha256)
        sys.stdout.write(canonical(result).decode("utf-8") + "\n")
    except (OSError, ValueError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return int(result["status"] == "hold")


if __name__ == "__main__":
    raise SystemExit(main())
