"""Ukur kalibrasi persepsi pada keluarga held-out terpisah dari fit.

Kalibrasi memakai frekuensi benar per pita confidence dengan prior
Beta eksplisit. Hanya pita yang mencapai minimum data latih yang
mengeluarkan estimasi. Brier dan ECE dibandingkan pada baris held-out
berpasangan. Cakupan dan pita di luar dukungan tetap terlihat.
"""
import argparse
from collections import defaultdict
from fractions import Fraction
import json
from pathlib import Path
import sys
import unicodedata

from . import _raster
from .audio_pipeline import _canonical, _integer, _sha
from .document_extractor import _token
from .ocr_engine import _pairs
from .perceptual_memory import _digest


MAX_CASES = 20_000
MAX_INPUT_BYTES = 16_000_000


def _edges(raw):
    if not isinstance(raw, list) or not 2 <= len(raw) <= 101 or any(type(value) is not int for value in raw):
        raise ValueError("Batas pita confidence perlu daftar integer.")
    if raw[0] != 0 or raw[-1] != 10_000 or any(a >= b for a, b in zip(raw, raw[1:])):
        raise ValueError("Pita harus naik dari 0 sampai 10000.")
    return raw


def _bin(score, edges):
    for index, end in enumerate(edges[1:]):
        if score < end:
            return index
    return len(edges)-2


def _grade_rows(raw, edges):
    if not isinstance(raw, list) or len(raw) > MAX_CASES:
        raise ValueError("Jumlah receipt kalibrasi melampaui batas.")
    index, refs = set(), set()
    families = {}
    rows = []
    for record in raw:
        needed = {"id", "family", "modality", "assessment_ref", "split", "confidence_bp", "correct"}
        if not isinstance(record, dict) or set(record) != needed:
            raise ValueError("Receipt kalibrasi tidak sesuai skema.")
        key = _token(record["id"], "ID penilaian")
        pointer = _token(record["assessment_ref"], "Rujukan penilaian")
        family = unicodedata.normalize("NFC", _token(record["family"], "Keluarga").strip())
        modality = _token(record["modality"], "Modalitas")
        split = record["split"]
        if key in index or pointer in refs or split not in ("train", "held_out") or type(record["correct"]) is not bool:
            raise ValueError("Receipt kalibrasi ganda atau kolom split/verdict tidak sah.")
        if family in families and families[family] != split:
            raise ValueError("Keluarga kalibrasi tumpang tindih antara train dan held-out.")
        families[family] = split
        index.add(key)
        refs.add(pointer)
        score = _integer(record["confidence_bp"], 0, 10000, "Confidence")
        rows.append({**record, "family": family, "modality": modality, "confidence_bp": score, "bin": _bin(score, edges)})
    return rows


def _ratio(number):
    return {"numerator": number.numerator, "denominator": number.denominator} if number is not None else None


def _metrics(rows, edges, key):
    if not rows:
        return {"brier": None, "ece": None, "bins": []}
    grouped = defaultdict(list)
    loss = Fraction(0)
    for row in rows:
        value = row[key]
        loss += (value - int(row["correct"]))**2
        grouped[_bin(value*10000, edges)].append(row)
    error = sum(abs(sum(item[key] for item in values) - sum(item["correct"] for item in values)) for values in grouped.values())
    evidence = [{"left_bp": edges[index], "right_bp": edges[index+1],
                 "cases": len(values), "correct": sum(row["correct"] for row in values),
                 "mean_probability": _ratio(sum(row[key] for row in values)/len(values))}
                for index, values in sorted(grouped.items())]
    return {"brier": _ratio(loss/len(rows)), "ece": _ratio(Fraction(error)/len(rows)), "bins": evidence}


def assess(raw, receipts, expected):
    needed = {"plan_ref", "receipt_snapshot_sha256", "edges_bp", "minimum_examples", "alpha", "beta"}
    if not isinstance(raw, dict) or set(raw) != needed or _sha(raw) != _digest(expected):
        raise ValueError("Protokol kalibrasi berbeda dari anchor atau skema.")
    if _sha(receipts) != _digest(raw["receipt_snapshot_sha256"]):
        raise ValueError("Receipt berbeda dari komitmen kalibrasi.")
    pointer = _token(raw["plan_ref"], "Rujukan protokol")
    edges = _edges(raw["edges_bp"])
    minimum = _integer(raw["minimum_examples"], 1, MAX_CASES, "Batas minimum")
    alpha = _integer(raw["alpha"], 1, 1000, "Prior alpha")
    beta = _integer(raw["beta"], 1, 1000, "Prior beta")
    observations = _grade_rows(receipts, edges)
    fit = defaultdict(list)
    held_out = defaultdict(list)
    for row in observations:
        if row["split"] == "train":
            fit[row["modality"], row["bin"]].append(row)
        else:
            held_out[row["modality"]].append(row)

    summaries = []
    for modality in sorted({row["modality"] for row in observations}):
        bins = {}
        fitted = []
        for index in range(len(edges)-1):
            subset = fit.get((modality, index), [])
            total = len(subset)
            correct = sum(row["correct"] for row in subset)
            value = Fraction(correct+alpha, total+alpha+beta) if total >= minimum else None
            bins[index] = value
            fitted.append({"left_bp": edges[index], "right_bp": edges[index+1], "cases": total, "correct": correct,
                           "confidence": _ratio(value), "fit_refs": sorted(row["assessment_ref"] for row in subset)})
        checks = []
        compared = []
        for row in sorted(held_out[modality], key=lambda item: item["id"]):
            value = bins[row["bin"]]
            if value is not None:
                compared.append({**row, "calibrated": value, "raw": Fraction(row["confidence_bp"], 10_000)})
            checks.append({"id": row["id"], "assessment_ref": row["assessment_ref"], "correct": row["correct"],
                           "confidence_bp": row["confidence_bp"], "calibrated": _ratio(value),
                           "status": "paired" if value is not None else "unsupported_bin"})
        summaries.append({"modality": modality, "fit": fitted, "held_out_cases": len(checks), "paired": len(compared),
                          "raw_metrics": _metrics(compared, edges, "raw"),
                          "calibrated_metrics": _metrics(compared, edges, "calibrated"), "held_out": checks})
    return {"schema": "ace.perception-calibration.v1", "plan_ref": pointer, "plan_sha256": expected,
            "receipts_sha256": raw["receipt_snapshot_sha256"], "modalities": summaries}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("receipts", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        plan, receipts = (json.loads(_raster.read(path, MAX_INPUT_BYTES).decode("utf-8"), object_pairs_hook=_pairs)
                          for path in (args.plan, args.receipts))
        result = assess(plan, receipts, args.expect_sha256)
        sys.stdout.buffer.write(_canonical(result) + b"\n")
    except (OSError, ValueError, OverflowError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
