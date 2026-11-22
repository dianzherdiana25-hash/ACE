"""Uji deteksi objek tercatat terhadap aturan tugas yang tertambat.

Roster boks mengikat sumber raster, label, dan confidence per
observasi. Aturan dapat menahan label tertentu hanya di wilayah
tugas yang dideklarasikan. Observasi kurang atau lemah dicatat
terpisah dari hit yang melampaui ambang.
"""
import argparse
from collections import defaultdict
from hashlib import sha256
from pathlib import Path
import sys

from . import _raster, _vision
from .audio_pipeline import _canonical, _integer, _sha
from .document_extractor import _token
from .perceptual_memory import _digest


MAX_RECORDS = 512


def _regions(raw, image):
    if not isinstance(raw, list) or not 1 <= len(raw) <= MAX_RECORDS:
        raise ValueError("Roster wilayah di luar batas.")
    registry = {}
    for row in raw:
        if not isinstance(row, dict) or set(row) != {"id", "box"}:
            raise ValueError("Bentuk wilayah objek tidak sah.")
        key = _token(row["id"], "ID wilayah")
        if key in registry:
            raise ValueError("Wilayah objek ganda.")
        registry[key] = _vision.bounded_box(row["box"], image)
    return registry


def _rules(raw, registered):
    if not isinstance(raw, list) or not 1 <= len(raw) <= MAX_RECORDS:
        raise ValueError("Jumlah aturan tugas di luar batas.")
    items = defaultdict(list)
    keys = set()
    for row in raw:
        if not isinstance(row, dict) or set(row) != {"id", "label", "regions", "confidence_min_bp", "source_ref"}:
            raise ValueError("Bentuk aturan objek tidak sah.")
        name, label, pointer = (_token(row[k], k) for k in ("id", "label", "source_ref"))
        zones = row["regions"]
        if not isinstance(zones, list) or not zones or len(zones) > len(registered) or name in keys:
            raise ValueError("Aturan ganda atau wilayah aturan kosong.")
        allowed = {_token(zone, "ID wilayah aturan") for zone in zones}
        if len(allowed) != len(zones) or allowed-registered.keys():
            raise ValueError("Wilayah aturan ganda atau belum terdaftar.")
        keys.add(name)
        bound = _integer(row["confidence_min_bp"], 1, 10_000, "Confidence minimum")
        items[label].append((name, pointer, bound, allowed))
    return items


def flag(data, plan, evidence, expected_policy):
    image = _raster.decode(data)
    checksum = sha256(data).hexdigest()
    settings = _vision.spec(plan, "ace.perception-object-policy.v1", ("image_sha256", "regions", "rules"))
    if _sha(settings) != _digest(expected_policy) or _digest(settings["image_sha256"]) != checksum:
        raise ValueError("Kebijakan objek atau raster berbeda dari anchor.")
    registered = _regions(settings["regions"], image)
    rules = _rules(settings["rules"], registered)
    envelope = _vision.spec(evidence, "ace.perception-object-observations.v1", ("image_sha256", "observations"))
    if _digest(envelope["image_sha256"]) != checksum:
        raise ValueError("Receipt objek menunjuk raster berbeda.")
    results = {}
    pointers = set()
    rows = envelope["observations"]
    if not isinstance(rows, list) or len(rows) > len(registered):
        raise ValueError("Jumlah receipt objek di luar roster.")
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"region", "receipt_ref", "label", "confidence_bp"}:
            raise ValueError("Bentuk receipt objek tidak sah.")
        key, source = (_token(row[k], k) for k in ("region", "receipt_ref"))
        if key not in registered or key in results or source in pointers:
            raise ValueError("Receipt objek ganda atau tak dikenal.")
        results[key] = (source, row["label"], row["confidence_bp"])
        pointers.add(source)
    flagged = []
    zones = []
    for key, bbox in sorted(registered.items()):
        source, label, confidence = results.get(key, (None, None, None))
        current = "missing" if source is None else "abstained"
        if label is None:
            if confidence is not None:
                raise ValueError("Abstain perlu confidence null.")
        else:
            name = _token(label, "Label objek")
            value = _integer(confidence, 0, 10000, "Confidence objek")
            matches = sorted((rule for rule in rules.get(name, []) if key in rule[3]), key=lambda item: item[0])
            hit = [row for row in matches if value >= row[2]]
            current = "flagged" if hit else "low_confidence" if matches else "no_rule_hit"
            flagged.extend({"region": key, "rule": rule, "rule_ref": ref, "receipt_ref": source}
                           for rule, ref, _, _ in hit)
        zones.append({"id": key, "box": bbox, "status": current, "receipt_ref": source})
    return {"schema": "ace.perception-object-flags.v1", "image_sha256": checksum, "policy_sha256": expected_policy,
            "receipts_sha256": sha256(evidence).hexdigest(), "flags": flagged, "regions": zones,
            "status": "flagged" if flagged else "incomplete" if any(
                row["status"] in {"missing", "abstained", "low_confidence"} for row in zones) else "no_rule_hit"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("policy", type=Path)
    parser.add_argument("observations", type=Path)
    parser.add_argument("--expect-policy-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        report = flag(_raster.read(args.image), _raster.read(args.policy, _vision.MAX_SPEC_BYTES),
                      _raster.read(args.observations, _vision.MAX_SPEC_BYTES), args.expect_policy_sha256)
        sys.stdout.buffer.write(_canonical(report)+b"\n")
    except (OSError, OverflowError, ValueError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return int(report["status"] != "no_rule_hit")


if __name__ == "__main__":
    raise SystemExit(main())
