"""Tutup wilayah sensitif raster dengan nilai opak yang dapat diverifikasi.

Boks wajah, plat, dan teks berasal dari anotasi yang disegel ke
byte raster. Tidak adanya anotasi wajib menahan seluruh ekspor.
Laporan menyebut cakupan piksel dan sumber wilayah tanpa menyalin
isi yang ditutup atau menerbitkan artefak masukan.
"""
import argparse
from hashlib import sha256
from pathlib import Path
import sys

from . import _raster, _vision
from .audio_pipeline import _canonical, _integer
from .document_extractor import _token
from .perceptual_memory import _digest


MAX_AREAS = 256
CLASSES = {"face", "plate", "text"}


def _policy(plan, data, image):
    raw = _vision.spec(plan, "ace.perception-redactions.v1",
                       ("source_sha256", "mask_level", "padding_px", "required_ids", "annotations"))
    checksum = sha256(data).hexdigest()
    if _digest(raw["source_sha256"]) != checksum:
        raise ValueError("Anotasi menunjuk byte media berbeda.")
    replacement = _integer(raw["mask_level"], 0, image.maximum, "Nilai masker")
    padding = _integer(raw["padding_px"], 0, 256, "Padding")
    annotations = raw["annotations"]
    needed = raw["required_ids"]
    if not isinstance(annotations, list) or len(annotations) > MAX_AREAS or not isinstance(needed, list) or len(needed) > MAX_AREAS:
        raise ValueError("Jumlah area redaksi melampaui batas.")
    required = [_token(item, "ID wajib") for item in needed]
    if len(set(required)) != len(required):
        raise ValueError("ID wajib ganda.")
    seen = set()
    fixed = []
    for entry in annotations:
        if not isinstance(entry, dict) or set(entry) != {"id", "class", "source_ref", "box"}:
            raise ValueError("Bentuk anotasi tidak sah.")
        key = _token(entry["id"], "ID redaksi")
        label = _token(entry["class"], "Jenis redaksi")
        pointer = _token(entry["source_ref"], "Rujukan anotasi")
        if key in seen or label not in CLASSES:
            raise ValueError("Jenis atau identitas anotasi tidak sah.")
        x0, y0, x1, y1 = _vision.bounded_box(entry["box"], image)
        position = [max(0, x0-padding), max(0, y0-padding),
                    min(image.width, x1+padding), min(image.height, y1+padding)]
        fixed.append({"id": key, "class": label, "source_ref": pointer, "requested_box": entry["box"], "box": position})
        seen.add(key)
    return checksum, replacement, padding, sorted(set(required)-seen), fixed


def _union(areas, width, height):
    mask = bytearray(width*height)
    for row in areas:
        x0, y0, x1, y1 = row["box"]
        span = b"\x01"*(x1-x0)
        for y in range(y0, y1):
            mask[y*width+x0:y*width+x1] = span
    return mask


def redact(data, plan):
    image = _raster.decode(data)
    image_sha, replacement, padding, missing, areas = _policy(plan, data, image)
    summary = {"schema": "ace.perception-media-redaction.v1", "source_sha256": image_sha,
               "plan_sha256": sha256(plan).hexdigest(), "size": [image.width, image.height],
               "status": "held", "missing_ids": missing, "areas": sorted(areas, key=lambda item: item["id"]),
               "mask_level": replacement, "padding_px": padding, "covered_pixels": None, "output_sha256": None}
    if missing or not areas:
        summary["reason"] = "required_annotations_missing" if missing else "no_annotations"
        return None, summary
    mask = _union(areas, image.width, image.height)
    pixels = bytes(replacement if should_hide else value for should_hide, value in zip(mask, image.pixels, strict=True))
    payload = _vision.encode(image.width, image.height, pixels, image.maximum)
    summary.update(status="redacted", reason=None, covered_pixels=sum(mask), output_sha256=sha256(payload).hexdigest())
    return payload, summary


def verify(data, plan, output):
    expected, _ = redact(data, plan)
    if expected is None:
        raise ValueError("Tidak ada keluaran redaksi sah untuk diverifikasi.")
    return {"schema": "ace.perception-redaction-verification.v1", "source_sha256": sha256(data).hexdigest(),
            "actual_sha256": sha256(output).hexdigest(), "expected_sha256": sha256(expected).hexdigest(),
            "verified": output == expected}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("plan", type=Path)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--output", type=Path)
    mode.add_argument("--verify", type=Path)
    args = parser.parse_args(argv)
    try:
        source, plan = _raster.read(args.image), _raster.read(args.plan, _vision.MAX_SPEC_BYTES)
        if args.verify is not None:
            report = verify(source, plan, _raster.read(args.verify))
            code = int(not report["verified"])
        else:
            payload, report = redact(source, plan)
            if payload is not None:
                with args.output.open("xb") as stream:
                    stream.write(payload)
            code = int(payload is None)
        sys.stdout.buffer.write(_canonical(report) + b"\n")
    except (OSError, OverflowError, RecursionError, ValueError) as error:
        parser.exit(2, f"Error: {error}\n")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
