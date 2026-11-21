"""Gabungkan vote klasifikasi gambar dari receipt organ yang terdaftar.

Setiap gambar dan organ memiliki paling banyak satu receipt.
Konsensus memerlukan cakupan, dukungan dari bobot terdaftar, jumlah
organ, dan selisih cukup dari runner-up. Organ absen atau abstain
tetap terlihat. Fungsi ini memproses snapshot hasil yang sudah ada.
"""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import sys

from . import _raster
from .audio_pipeline import _canonical, _integer, _sha
from .document_extractor import _token
from .ocr_engine import _pairs
from .perceptual_memory import _digest


MAX_IMAGES = 10_000
MAX_ORGANS = 32
MAX_LABELS = 128
MAX_RECEIPTS = 50_000
MAX_INPUT_BYTES = 16_000_000


def _indexed(rows, cap, required, key, label):
    if not isinstance(rows, list) or not 1 <= len(rows) <= cap:
        raise ValueError(f"Jumlah {label} di luar batas.")
    lookup = {}
    for row in rows:
        if not isinstance(row, dict) or set(row) != required:
            raise ValueError(f"Bentuk {label} tidak sah.")
        identity = _token(row[key], label)
        if identity in lookup:
            raise ValueError(f"Identitas {label} ganda.")
        lookup[identity] = row
    return lookup


def _plan(raw, expected):
    required = {"plan_ref", "taxonomy_ref", "receipt_sha256", "labels", "organs", "images", "minimum_voters",
                "minimum_coverage_bp", "minimum_winner_bp", "minimum_margin_bp", "minimum_vote_confidence_bp"}
    if not isinstance(raw, dict) or set(raw) != required or _sha(raw) != _digest(expected):
        raise ValueError("Rencana klasifikasi tidak sah atau berbeda dari anchor.")
    labels = raw["labels"]
    if not isinstance(labels, list) or not 2 <= len(labels) <= MAX_LABELS:
        raise ValueError("Taksonomi perlu dua label atau lebih.")
    names = {_token(item, "Label") for item in labels}
    if len(names) != len(labels):
        raise ValueError("Label taksonomi ganda.")
    organs = _indexed(raw["organs"], MAX_ORGANS, {"id", "weight", "organ_ref"}, "id", "organ")
    images = _indexed(raw["images"], MAX_IMAGES, {"id", "image_sha256", "image_ref"}, "id", "gambar")
    refs = {_token(raw["plan_ref"], "Rujukan rencana")}
    hashes = set()
    pointers = [raw["taxonomy_ref"]]
    pointers.extend(row["organ_ref"] for row in organs.values())
    pointers.extend(row["image_ref"] for row in images.values())
    for item in pointers:
        ref = _token(item, "Rujukan rencana")
        if ref in refs:
            raise ValueError("Rujukan rencana ganda.")
        refs.add(ref)
    for row in images.values():
        key = _digest(row["image_sha256"])
        if key in hashes:
            raise ValueError("Roster mengulang hash gambar.")
        hashes.add(key)
    weights = {key: _integer(item["weight"], 1, 1000, "Bobot organ") for key, item in organs.items()}
    policy = {"minimum_voters": _integer(raw["minimum_voters"], 1, len(organs), "Kuorum")}
    for field in ("minimum_coverage_bp", "minimum_winner_bp", "minimum_margin_bp", "minimum_vote_confidence_bp"):
        policy[field] = _integer(raw[field], int(field != "minimum_vote_confidence_bp"), 10_000, field)
    return names, images, refs, weights, policy


def _votes(raw, names, images, refs, organ_weights, confidence):
    if not isinstance(raw, list) or len(raw) > MAX_RECEIPTS:
        raise ValueError("Jumlah vote melampaui batas.")
    index = defaultdict(dict)
    for row in raw:
        fields = {"image_id", "image_sha256", "organ_id", "label", "confidence_bp", "receipt_ref"}
        if not isinstance(row, dict) or set(row) != fields:
            raise ValueError("Vote tidak sesuai skema.")
        image, organ = _token(row["image_id"], "ID gambar"), _token(row["organ_id"], "ID organ")
        pointer = _token(row["receipt_ref"], "Rujukan vote")
        if (image not in images or organ not in organ_weights or organ in index[image]
                or pointer in refs or row["image_sha256"] != images[image]["image_sha256"]):
            raise ValueError("Vote ganda atau tidak terikat gambar dan organ.")
        refs.add(pointer)
        label = row["label"]
        certainty = row["confidence_bp"]
        if label is None and certainty is None:
            outcome = "abstained"
        else:
            if not isinstance(label, str) or label not in names:
                raise ValueError("Vote label di luar taksonomi.")
            score = _integer(certainty, 0, 10_000, "Confidence vote")
            outcome = "counted" if score >= confidence else "low_confidence"
        index[image][organ] = {"organ_id": organ, "receipt_ref": pointer, "label": label,
                               "confidence_bp": certainty, "status": outcome}
    return index


def _classify(image, votes, weights, policy):
    tallies = defaultdict(lambda: {"weight": 0, "organs": []})
    for key, row in sorted(votes.items()):
        if row["status"] != "counted":
            continue
        tab = tallies[row["label"]]
        tab["organs"].append(key)
        tab["weight"] += weights[key]
    ranking = sorted(({"label": key, **value} for key, value in tallies.items()), key=lambda row: (-row["weight"], row["label"]))
    maximum = sum(weights.values())
    active = sum(item["weight"] for item in ranking)
    winner = ranking[0] if ranking else None
    next_weight = ranking[1]["weight"] if len(ranking) > 1 else 0
    reasons = []
    if active*10_000 < policy["minimum_coverage_bp"]*maximum:
        reasons.append("coverage")
    if winner is None or len(winner["organs"]) < policy["minimum_voters"]:
        reasons.append("quorum")
    if winner is not None:
        if winner["weight"]*10_000 < policy["minimum_winner_bp"]*maximum:
            reasons.append("support")
        if (winner["weight"]-next_weight)*10_000 < policy["minimum_margin_bp"]*maximum:
            reasons.append("margin")
    return {**image, "status": "unresolved" if reasons else "classified", "label": None if reasons else winner["label"],
            "reasons": reasons, "eligible_weight": active, "registered_weight": maximum, "ranking": ranking,
            "observations": [votes.get(key, {"organ_id": key, "receipt_ref": None, "label": None,
                                             "confidence_bp": None, "status": "missing"}) for key in sorted(weights)]}


def classify(plan, votes, expected):
    labels, images, refs, weights, policy = _plan(plan, expected)
    if _sha(votes) != _digest(plan["receipt_sha256"]):
        raise ValueError("Snapshot vote berbeda dari komitmen.")
    calls = _votes(votes, labels, images, refs, weights, policy["minimum_vote_confidence_bp"])
    rows = [_classify(image, calls.get(key, {}), weights, policy) for key, image in sorted(images.items())]
    resolved = sum(row["status"] == "classified" for row in rows)
    return {"schema": "ace.perception-image-votes.v1", "plan_ref": plan["plan_ref"], "taxonomy_ref": plan["taxonomy_ref"],
            "plan_sha256": expected, "receipt_sha256": plan["receipt_sha256"], "classifications": rows,
            "resolved": resolved, "unresolved": len(rows)-resolved}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("votes", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        data = [json.loads(_raster.read(path, MAX_INPUT_BYTES).decode("utf-8"), object_pairs_hook=_pairs)
                for path in (args.plan, args.votes)]
        result = classify(*data, args.expect_sha256)
        sys.stdout.buffer.write(_canonical(result) + b"\n")
    except (OSError, ValueError, OverflowError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return int(bool(result["unresolved"]))


if __name__ == "__main__":
    raise SystemExit(main())
