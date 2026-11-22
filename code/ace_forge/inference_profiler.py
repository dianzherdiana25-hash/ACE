"""Profilkan skor dan waktu dari receipt inferensi yang sudah direkam.

Laporkan latensi dan throughput per pita panjang konteks. Warmup
dikeluarkan dari ringkasan dan hasil tanpa penilaian tetap terlihat
melalui coverage. Kuantil nearest-rank mengukur data fixture mentah
tanpa menggunakan jam sistem atau menghubungi organ.
"""
import argparse
from bisect import bisect_left
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
import sys

from ._forge_io import InputError, canonical, decode, digest, entries, identity, integer, object_fields, read_bytes, string
from ._numeric import reference
from .dataset_forge import MAX_BYTES
from .forgetting_guard import _fraction


MAX_RUNS = 20_000
MAX_AMOUNT = 10**12


@dataclass(frozen=True, slots=True)
class Observation:
    key: str
    source: str
    input_count: int
    output_count: int
    elapsed: int
    first: int | None
    memory: int
    quality: dict | None
    phase: str

    @classmethod
    def read(cls, row, artifact, ids, refs):
        object_fields(row, ("id", "source_ref", "artifact_sha256", "input_tokens", "output_tokens",
                            "elapsed_ns", "first_token_ns", "peak_bytes", "quality", "phase"))
        if digest(row["artifact_sha256"]) != artifact:
            raise InputError("Receipt inferensi memakai artefak berbeda.")
        kind = row["phase"]
        if kind not in ("warmup", "measured"):
            raise InputError("Fase inferensi tidak dikenal.")
        took = integer(row["elapsed_ns"], 1, MAX_AMOUNT)
        output = integer(row["output_tokens"], 0, MAX_AMOUNT)
        first = row["first_token_ns"]
        if first is not None:
            if output == 0:
                raise InputError("First token membutuhkan keluaran.")
            first = integer(first, 0, took)
        judged = row["quality"]
        if judged is not None:
            object_fields(judged, ("passed", "assessment_ref"))
            if type(judged["passed"]) is not bool:
                raise InputError("Penilaian perlakuan harus boolean eksplisit.")
            judged = {"assessment_ref": reference(judged["assessment_ref"], refs, "rujukan penilaian"),
                      "passed": judged["passed"]}
        return cls(reference(row["id"], ids, "ID receipt"), reference(row["source_ref"], refs, "rujukan inferensi"),
                   integer(row["input_tokens"], 1, MAX_AMOUNT), output, took, first,
                   integer(row["peak_bytes"], 0, MAX_AMOUNT), judged, kind)

    def export(self):
        return {"id": self.key, "source_ref": self.source, "input_tokens": self.input_count,
                "output_tokens": self.output_count, "elapsed_ns": self.elapsed, "first_token_ns": self.first,
                "peak_bytes": self.memory, "quality": self.quality, "phase": self.phase}


def _quantiles(values):
    data = sorted(values)
    if not data:
        return None
    return {f"p{percent}": data[(percent * len(data) + 99) // 100 - 1] for percent in (50, 95, 99)}


def _describe(rows, minimum):
    warmups = [item for item in rows if item.phase == "warmup"]
    samples = [item for item in rows if item.phase == "measured"]
    assessed = [item for item in samples if item.quality is not None]
    first = [item.first for item in samples if item.first is not None]
    clean = len(samples) >= minimum
    tokens = sum(item.output_count for item in samples)
    elapsed = sum(item.elapsed for item in samples)
    passed = sum(item.quality["passed"] for item in assessed)
    return {
        "status": "profiled" if clean else "insufficient_samples",
        "warmups": len(warmups), "measured": len(samples), "first_token_measured": len(first),
        "input_tokens": sum(item.input_count for item in samples), "output_tokens": tokens,
        "elapsed_ns": elapsed, "latency_ns": _quantiles(item.elapsed for item in samples) if clean else None,
        "first_token_ns": _quantiles(first) if len(first) >= minimum else None,
        "token_rate_per_second": _fraction(Fraction(tokens * 10**9, elapsed)) if clean else None,
        "peak_bytes": max((item.memory for item in samples), default=None),
        "quality": {"assessed": len(assessed), "passed": passed,
                    "coverage": _fraction(Fraction(len(assessed), len(samples))) if samples else None,
                    "pass_rate": _fraction(Fraction(passed, len(assessed))) if len(assessed) >= minimum else None},
    }


def profile(raw, expected_sha256):
    object_fields(raw, ("protocol_ref", "artifact_sha256", "minimum_samples", "context_boundaries", "receipts"))
    if identity(raw) != digest(expected_sha256):
        raise InputError("Snapshot profil berbeda dari anchor.")
    protocol = string(raw["protocol_ref"], "rujukan protokol inferensi")
    artifact = digest(raw["artifact_sha256"])
    minimum = integer(raw["minimum_samples"], 1, MAX_RUNS)
    boundaries = [integer(item, 1, MAX_AMOUNT) for item in entries(raw["context_boundaries"], 100)]
    if any(left >= right for left, right in zip(boundaries, boundaries[1:])):
        raise InputError("Batas konteks harus meningkat tanpa duplikasi.")
    ids, refs = set(), {protocol}
    observations = sorted((Observation.read(row, artifact, ids, refs) for row in entries(raw["receipts"], MAX_RUNS)),
                          key=lambda item: item.key)
    grouped = [[] for _ in range(len(boundaries) + 1)]
    for item in observations:
        grouped[bisect_left(boundaries, item.input_count)].append(item)
    results = []
    for index, items in enumerate(grouped):
        results.append({"context_min": boundaries[index - 1] + 1 if index else 1,
                        "context_max": boundaries[index] if index < len(boundaries) else None,
                        **_describe(items, minimum), "receipt_ids": [item.key for item in items]})
    return {"schema": "ace.forge-inference-profile.v1", "protocol_ref": protocol, "artifact_sha256": artifact,
            "snapshot_sha256": expected_sha256, "minimum_samples": minimum, "summary": _describe(observations, minimum),
            "context_profiles": results, "receipts": [item.export() for item in observations]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--expect-input-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        result = profile(decode(read_bytes(args.input, MAX_BYTES)), args.expect_input_sha256)
        sys.stdout.write(canonical(result).decode("utf-8") + "\n")
    except (OSError, ValueError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
