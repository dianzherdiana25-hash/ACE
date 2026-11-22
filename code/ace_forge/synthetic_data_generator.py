"""Bangun contoh sintetis yang bisa dinilai ulang tanpa organ.

Setiap tugas menghasilkan input terstruktur dan jawaban kanonis.
Pemeriksa memakai perhitungan independen untuk tiga keluarga tugas,
dan generator tidak memasukkan calon yang gagal pemeriksaan atau
menduplikasi prompt. Laporan mutu sintetis berdiri terpisah dari
indeks verifikasi eksternal untuk dataset_forge.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

from ._forge_io import InputError, canonical, decode, entries, integer, object_fields, read_bytes, string
from .dataset_forge import MAX_BYTES, Source


PROMPTS = {
    "frequency": "Hitung banyaknya kemunculan bilangan yang ditanyakan. Jawab dengan satu integer JSON.",
    "prefix_sum": "Jumlahkan prefiks sepanjang n. Jawab dengan satu integer JSON.",
    "interval_coverage": "Hitung jumlah titik integer unik yang tercakup interval tertutup. Jawab dengan satu integer JSON.",
}
MAX_COUNT = 2_000


class Sampler:
    """Deret pseudoacak portabel dengan penghitung eksplisit."""

    def __init__(self, seed, kind, attempt):
        self.key = (seed, kind, attempt)
        self.cursor = 0

    def within(self, low, high):
        index = self.cursor
        self.cursor += 1
        payload = canonical([*self.key, index])
        number = int.from_bytes(hashlib.sha256(payload).digest(), "big")
        return low + number % (high - low + 1)


def _sample(kind, draws):
    if kind == "interval_coverage":
        pairs = [sorted((draws.within(-20, 20), draws.within(-20, 20))) for _ in range(draws.within(2, 7))]
        total = 0
        active = None
        for left, right in sorted(pairs):
            if active is None or left > active + 1:
                total += right - left + 1
                active = right
            elif right > active:
                total += right - active
                active = right
        return {"intervals": pairs}, total
    values = [draws.within(-12, 12) for _ in range(draws.within(4, 15))]
    if kind == "frequency":
        query = draws.within(-12, 12)
        return {"values": values, "query": query}, Counter(values)[query]
    length = draws.within(0, len(values))
    accumulator = 0
    for value in values[:length]:
        accumulator += value
    return {"values": values, "n": length}, accumulator


def _verify_answer(kind, payload):
    if kind == "interval_coverage":
        object_fields(payload, ("intervals",))
        pairs = entries(payload["intervals"], 7)
        if len(pairs) < 2:
            raise InputError("Tugas interval membutuhkan setidaknya dua interval.")
        points = set()
        for pair in pairs:
            if not isinstance(pair, list) or len(pair) != 2:
                raise InputError("Pasangan interval tidak sah.")
            left, right = (integer(item, -20, 20) for item in pair)
            if left > right:
                raise InputError("Interval terbalik.")
            points.update(range(left, right + 1))
        return len(points)
    key = "query" if kind == "frequency" else "n"
    object_fields(payload, ("values", key))
    values = [integer(item, -12, 12) for item in entries(payload["values"], 15)]
    if len(values) < 4:
        raise InputError("Vektor sintetis terlalu pendek.")
    if kind == "frequency":
        query = integer(payload["query"], -12, 12)
        return len([item for item in values if item == query])
    length = integer(payload["n"], 0, len(values))
    return sum(values[index] for index in range(length))


def check(raw):
    """Cocokkan tugas, format, partisi asal, dan jawaban mekanis."""
    example = Source.read(raw)
    kind = example.task_kind
    if kind not in PROMPTS:
        return {"valid": False, "reason": "unknown_task_kind"}
    lead = PROMPTS[kind] + "\n"
    if not example.prompt.startswith(lead) or example.language != "id" or example.family != f"synthetic/{kind}":
        return {"valid": False, "reason": "template_mismatch"}
    payload_bytes = example.prompt.removeprefix(lead).encode("utf-8")
    try:
        payload = decode(payload_bytes)
        expected = _verify_answer(kind, payload)
    except (ValueError, RecursionError):
        return {"valid": False, "reason": "invalid_payload"}
    if canonical(payload) != payload_bytes:
        return {"valid": False, "reason": "noncanonical_payload"}
    valid = example.target == str(expected)
    return {"valid": valid, "reason": "valid" if valid else "incorrect_or_noncanonical_answer"}


def generate(raw):
    object_fields(raw, ("seed", "per_task_kind", "held_out_basis_points", "license"))
    seed = integer(raw["seed"], 0, 2**64 - 1)
    coverage = raw["per_task_kind"]
    object_fields(coverage, PROMPTS)
    desired = {kind: integer(count, 0, MAX_COUNT) for kind, count in coverage.items()}
    basis_points = integer(raw["held_out_basis_points"], 0, 10_000)
    license_id = string(raw["license"], "lisensi yang dideklarasikan")
    result = []
    stats = {}
    for kind in sorted(desired):
        requested = desired[kind]
        counts = Counter()
        prompts = set()
        for attempt in range(8 * requested):
            if counts["written"] == requested:
                break
            payload, solution = _sample(kind, Sampler(seed, kind, attempt))
            prompt = PROMPTS[kind] + "\n" + canonical(payload).decode("utf-8")
            key = hashlib.sha256(canonical([seed, kind, attempt])).hexdigest()
            record = {"event_id": f"synthetic-{key}", "family_id": f"synthetic/{kind}",
                      "language": "id", "task_kind": kind, "target": str(solution), "prompt": prompt}
            if prompt in prompts:
                counts["duplicate_prompt"] += 1
                continue
            verdict = check(record)
            if not verdict["valid"]:
                counts["rejected_quality"] += 1
                continue
            prompts.add(prompt)
            counts["written"] += 1
            result.append(record)
        stats[kind] = {"requested": requested, "written": counts["written"],
                       "duplicate_prompt": counts["duplicate_prompt"], "rejected_quality": counts["rejected_quality"],
                       "shortfall": requested - counts["written"]}
    candidates = {"examples": result, "seed": seed, "allowed_licenses": [license_id],
                  "held_out_basis_points": basis_points}
    return candidates, {"schema": "ace.synthetic-quality.v1", "seed": seed, "families": stats,
                        "examples": len(result), "verification_index": None}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--report-only", action="store_true")
    args = parser.parse_args(argv)
    try:
        candidates, report = generate(decode(read_bytes(args.input, MAX_BYTES)))
        sys.stdout.write(json.dumps(report if args.report_only else candidates, ensure_ascii=False, sort_keys=True) + "\n")
    except (OSError, ValueError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
