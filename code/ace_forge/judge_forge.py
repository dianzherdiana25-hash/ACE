"""Tempa kalibrator judge monoton dari skor dan penilaian yang direkam.

Kalibrasi bekerja per domain dan rubrik. Pool-adjacent-violators
menggabungkan blok yang melanggar monotoni dengan bobot contoh eksak.
Interpolasi hanya berlaku di rentang skor train. Receipt membandingkan
error sebelum dan sesudah pada kasus held-out yang benar-benar tercakup.
"""
import argparse
from bisect import bisect_left
from collections import defaultdict
from fractions import Fraction
from pathlib import Path
import sys

from ._forge_io import InputError, canonical, decode, digest, entries, identity, integer, object_fields, read_bytes, string
from ._numeric import reference
from .dataset_forge import MAX_BYTES
from .forgetting_guard import _fraction


MAX_CASES = 5000


def _rows(raw, recipe):
    ids, refs, families = set(), {recipe}, {}
    grouped = defaultdict(list)
    for row in entries(raw, MAX_CASES):
        object_fields(row, ("id", "family_id", "split", "domain", "rubric_ref",
                            "score_bp", "assessor_bp", "evaluation_ref"))
        key = reference(row["id"], ids, "ID penilaian")
        family = string(row["family_id"], "keluarga")
        split = row["split"]
        if split not in ("train", "held_out") or families.setdefault(family, split) != split:
            raise InputError("Keluarga dipakai lintas partisi atau split salah.")
        group = string(row["domain"], "domain"), string(row["rubric_ref"], "rujukan rubrik")
        proof = reference(row["evaluation_ref"], refs, "rujukan penilaian")
        grouped[group].append({"id": key, "family_id": family, "split": split, "evaluation_ref": proof,
                               "score_bp": integer(row["score_bp"], 0, 10_000),
                               "assessor_bp": integer(row["assessor_bp"], 0, 10_000)})
    return grouped


def _curve(rows):
    pooled = defaultdict(list)
    for row in rows:
        pooled[row["score_bp"]].append(row["assessor_bp"])
    stack = []
    for score, values in sorted(pooled.items()):
        stack.append((score, score, sum(values), len(values)))
        while len(stack) > 1:
            low, _, total, count = stack[-2]
            _, high, nxt, samples = stack[-1]
            if total * samples <= nxt * count:
                break
            stack[-2:] = [(low, high, total + nxt, count + samples)]
    return [{"lo": low, "hi": high, "count": count, "value_bp": _fraction(Fraction(total, count))}
            for low, high, total, count in stack]


def _calibration(curve, raw_score):
    if not curve or not curve[0]["lo"] <= raw_score <= curve[-1]["hi"]:
        return None
    index = bisect_left(curve, raw_score, key=lambda block: block["hi"])
    next_ = curve[index]
    end = Fraction(**next_["value_bp"])
    if raw_score >= next_["lo"]:
        return end
    previous = curve[index - 1]
    begin = Fraction(**previous["value_bp"])
    position = Fraction(raw_score - previous["hi"], next_["lo"] - previous["hi"])
    return begin + position * (end - begin)


def _held_scores(rows, curve):
    measured, before, after = [], [], []
    for row in sorted(rows, key=lambda item: item["id"]):
        outcome = _calibration(curve, row["score_bp"])
        if outcome is not None:
            before.append(abs(row["score_bp"] - row["assessor_bp"]))
            after.append(abs(outcome - row["assessor_bp"]))
        measured.append({**row, "calibrated_bp": _fraction(outcome) if outcome is not None else None})
    size = len(before)
    return measured, {"covered": size, "held_out": len(rows),
                      "mae_before_bp": _fraction(Fraction(sum(before), size)) if size else None,
                      "mae_after_bp": _fraction(sum(after) / size) if size else None}


def forge(raw, expected):
    object_fields(raw, ("recipe_ref", "minimum_train", "records"))
    if identity(raw) != digest(expected):
        raise InputError("Data kalibrator berbeda dari anchor.")
    name = string(raw["recipe_ref"], "rujukan resep")
    minimum = integer(raw["minimum_train"], 1, MAX_CASES)
    groups = _rows(raw["records"], name)
    if not groups:
        raise InputError("Dataset judge kosong.")
    curves, diagnostics = [], []
    for (domain, rubric), rows in sorted(groups.items()):
        train = [row for row in rows if row["split"] == "train"]
        fitted = _curve(train) if len(train) >= minimum else []
        if fitted:
            curves.append({"domain": domain, "rubric_ref": rubric, "blocks": fitted})
        outcomes, stats = _held_scores([row for row in rows if row["split"] == "held_out"], fitted)
        diagnostics.append({"domain": domain, "rubric_ref": rubric, "train": len(train),
                            "status": "fit" if fitted else "insufficient_training", **stats, "cases": outcomes})
    adapter = {"schema": "ace.judge-isotonic-calibrator.v1", "curves": curves}
    return {"schema": "ace.forge-judge-receipt.v1", "recipe_ref": name, "input_sha256": expected,
            "adapter": adapter, "adapter_sha256": identity(adapter), "groups": diagnostics}


def calibrate(query, expected, adapter, expected_adapter):
    object_fields(query, ("domain", "rubric_ref", "score_bp"))
    object_fields(adapter, ("schema", "curves"))
    if identity(query) != digest(expected) or identity(adapter) != digest(expected_adapter):
        raise InputError("Masukan kalibrasi berbeda dari anchor.")
    if adapter["schema"] != "ace.judge-isotonic-calibrator.v1":
        raise InputError("Skema adaptor judge tidak dikenal.")
    score = integer(query["score_bp"], 0, 10_000)
    target = string(query["domain"], "domain"), string(query["rubric_ref"], "rujukan rubrik")
    matching = None
    known = set()
    for row in entries(adapter["curves"], MAX_CASES):
        object_fields(row, ("domain", "rubric_ref", "blocks"))
        key = string(row["domain"], "domain"), string(row["rubric_ref"], "rubrik")
        if key in known:
            raise InputError("Kurva judge ganda.")
        known.add(key)
        last, previous = -1, Fraction(0)
        for block in entries(row["blocks"], 10_001):
            object_fields(block, ("lo", "hi", "count", "value_bp"))
            low = integer(block["lo"], last + 1, 10_000)
            last = integer(block["hi"], low, 10_000)
            count = integer(block["count"], 1, MAX_CASES)
            rate = block["value_bp"]
            object_fields(rate, ("numerator", "denominator"))
            value = Fraction(integer(rate["numerator"], 0, count * 10_000), integer(rate["denominator"], 1, count))
            if not previous <= value <= 10_000:
                raise InputError("Kurva judge tidak monoton.")
            previous = value
        if key == target:
            matching = row["blocks"]
    value = _calibration(matching, score)
    return {"schema": "ace.judge-calibrated-score.v1", "query_sha256": expected, "adapter_sha256": expected_adapter,
            "source_score_bp": score, "calibrated_bp": _fraction(value) if value is not None else None,
            "status": "covered" if value is not None else "uncovered"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--expect-input-sha256", required=True)
    parser.add_argument("--adapter", type=Path)
    parser.add_argument("--expect-adapter-sha256")
    args = parser.parse_args(argv)
    if (args.adapter is None) != (args.expect_adapter_sha256 is None):
        parser.error("Adaptor dan anchor wajib dipasangkan.")
    try:
        raw = decode(read_bytes(args.input, MAX_BYTES))
        if args.adapter:
            result = calibrate(raw, args.expect_input_sha256, decode(read_bytes(args.adapter, MAX_BYTES)),
                               args.expect_adapter_sha256)
        else:
            result = forge(raw, args.expect_input_sha256)
        sys.stdout.write(canonical(result).decode("utf-8") + "\n")
    except (OSError, ValueError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
