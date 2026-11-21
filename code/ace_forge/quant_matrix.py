"""Bandingkan varian kuantisasi pada roster tugas dan baseline bersama.

Matriks menahan agregat ketika pasangan tidak lengkap. Batas loss mutu
berlaku pada setiap tugas. Frontier diambil dari varian yang memenuhi
semua tugas, memakai loss maksimum, ukuran bobot, dan delta waktu.
"""
import argparse
from collections import defaultdict
from fractions import Fraction
from pathlib import Path
import sys

from ._forge_io import InputError, canonical, decode, digest, entries, identity, integer, object_fields, read_bytes, string
from ._numeric import reference
from .dataset_forge import MAX_BYTES
from .forgetting_guard import _fraction


MAX_VARIANTS = 64
MAX_CASES = 3000


def _plan(raw, expected):
    object_fields(raw, ("protocol_ref", "baseline", "variants", "cases", "maximum_loss_bp", "minimum_per_task"))
    if identity(raw) != digest(expected):
        raise InputError("Rencana matriks kuantisasi berbeda dari anchor.")
    pointer = string(raw["protocol_ref"], "rujukan protokol")
    refs = {pointer}
    object_fields(raw["baseline"], ("artifact_sha256", "bytes", "source_ref"))
    base = {"artifact_sha256": digest(raw["baseline"]["artifact_sha256"]),
            "bytes": integer(raw["baseline"]["bytes"], 1, 10**12),
            "source_ref": reference(raw["baseline"]["source_ref"], refs, "rujukan baseline")}
    variants, names, shas = {}, set(), {base["artifact_sha256"]}
    for row in entries(raw["variants"], MAX_VARIANTS):
        object_fields(row, ("id", "artifact_sha256", "bits", "strategy", "bytes", "source_ref"))
        key = reference(row["id"], names, "ID varian")
        checksum = digest(row["artifact_sha256"])
        if checksum in shas:
            raise InputError("Artefak varian ganda.")
        shas.add(checksum)
        variants[key] = {"id": key, "artifact_sha256": checksum, "bits": integer(row["bits"], 2, 16),
                         "strategy": string(row["strategy"], "strategi"), "bytes": integer(row["bytes"], 1, 10**12),
                         "source_ref": reference(row["source_ref"], refs, "rujukan varian")}
    cases, ids = {}, set()
    for row in entries(raw["cases"], MAX_CASES):
        object_fields(row, ("id", "task_kind", "source_ref"))
        key = reference(row["id"], ids, "ID kasus")
        cases[key] = {"case_id": key, "task_kind": string(row["task_kind"], "jenis tugas"),
                      "case_ref": reference(row["source_ref"], refs, "rujukan kasus")}
    if not variants or not cases:
        raise InputError("Matriks memerlukan varian dan kasus.")
    return (pointer, base, variants, cases, refs, integer(raw["maximum_loss_bp"], 0, 10_000),
            integer(raw["minimum_per_task"], 1, MAX_CASES))


def _metric(raw, artifact, refs):
    if raw is None:
        return None
    object_fields(raw, ("artifact_sha256", "quality_bp", "elapsed_us", "observation_ref"))
    if digest(raw["artifact_sha256"]) != artifact:
        raise InputError("Receipt tidak cocok dengan hash artefak.")
    return {"quality_bp": integer(raw["quality_bp"], 0, 10_000), "elapsed_us": integer(raw["elapsed_us"], 0, 10**12),
            "observation_ref": reference(raw["observation_ref"], refs, "rujukan ukur")}


def _observations(raw, base, variants, cases, refs):
    object_fields(raw, ("baseline", "variants"))
    result = {}
    for field, maximum in (("baseline", MAX_CASES), ("variants", MAX_VARIANTS * MAX_CASES)):
        for row in entries(raw[field], maximum):
            object_fields(row, ("case_id", "metric") if field == "baseline" else ("case_id", "variant_id", "metric"))
            key = string(row["case_id"], "ID kasus")
            variant = None if field == "baseline" else string(row["variant_id"], "ID varian")
            artifact = base if field == "baseline" else variants.get(variant)
            if key not in cases or artifact is None or (variant, key) in result:
                raise InputError("Receipt ganda atau di luar roster.")
            result[variant, key] = _metric(row["metric"], artifact["artifact_sha256"], refs)
    return result


def _summarize(rows, floor, loss_limit):
    paired = [row for row in rows if row["delta_quality_bp"] is not None]
    usable = len(rows) == len(paired) and len(paired) >= floor
    delta = Fraction(sum(item["delta_quality_bp"] for item in paired), len(paired)) if usable else None
    elapsed = Fraction(sum(item["delta_elapsed_us"] for item in paired), len(paired)) if usable else None
    return {"expected": len(rows), "paired": len(paired),
            "mean_quality_delta_bp": _fraction(delta) if usable else None,
            "mean_elapsed_delta_us": _fraction(elapsed) if usable else None,
            "status": "insufficient_evidence" if not usable else "quality_below_floor" if delta < -loss_limit else "within_floor"}


def _frontier(points):
    return sorted(key for key, value in points.items()
                  if not any(other != value and all(a <= b for a, b in zip(other, value, strict=True))
                             for other in points.values()))


def compare(raw, observations, expected):
    protocol, base, variants, cases, refs, policy, floor = _plan(raw, expected)
    measured = _observations(observations, base, variants, cases, refs)
    results, points = [], {}
    for key, variant in sorted(variants.items()):
        grouped = defaultdict(list)
        cards = []
        for card, case in sorted(cases.items()):
            a, b = measured.get((None, card)), measured.get((key, card))
            deltas = [b[name] - a[name] for name in ("quality_bp", "elapsed_us")] if a is not None and b is not None else (None, None)
            item = {**case, "baseline": a, "variant": b, "delta_quality_bp": deltas[0], "delta_elapsed_us": deltas[1]}
            grouped[case["task_kind"]].append(item)
            cards.append(item)
        tasks = [{"task_kind": name, **_summarize(items, floor, policy)} for name, items in sorted(grouped.items())]
        eligible = all(row["status"] == "within_floor" for row in tasks)
        if eligible:
            loss = max(-Fraction(**row["mean_quality_delta_bp"]) for row in tasks)
            wall = Fraction(sum(row["delta_elapsed_us"] for row in cards), len(cards))
            points[key] = (loss, variant["bytes"], wall)
        results.append({**variant, "bytes_ratio": _fraction(Fraction(variant["bytes"], base["bytes"])),
                        "eligible": eligible, "tasks": tasks, "cases": cards})
    return {"schema": "ace.forge-quantization-matrix.v1", "protocol_ref": protocol, "protocol_sha256": expected,
            "observations_sha256": identity(observations), "baseline": base, "maximum_loss_bp": policy, "variants": results,
            "evaluation_frontier": _frontier(points)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("protocol", type=Path)
    parser.add_argument("observations", type=Path)
    parser.add_argument("--expect-protocol-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        product = compare(decode(read_bytes(args.protocol, MAX_BYTES)), decode(read_bytes(args.observations, MAX_BYTES)),
                          args.expect_protocol_sha256)
        sys.stdout.write(canonical(product).decode("utf-8") + "\n")
    except (OSError, ValueError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
