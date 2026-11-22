"""Periksa keberadaan tinta tambahan pada kotak tanda tangan.

Raster formulir kosong menjadi rujukan bersumber. Perbandingan
terarah menghitung tinta baru, kehilangan tinta cetak, dan ukuran
komponen. Hasil menyatakan kehadiran tanda pada wilayah tertentu
dengan ambang eksplisit, tanpa menilai identitas atau keaslian.
"""
import argparse
from hashlib import sha256
from pathlib import Path
import sys

from . import _raster, _vision
from .audio_pipeline import _canonical, _integer
from .perceptual_memory import _digest
from .screen_understanding import _components


def inspect(marked, blank, layout):
    a, b = map(_raster.decode, (marked, blank))
    if (a.width, a.height) != (b.width, b.height):
        raise ValueError("Formulir terisi dan kosong harus berukuran sama.")
    names = ("blank_sha256", "box", "minimum_contrast", "minimum_new_pixels", "minimum_component",
             "maximum_missing_bp", "light_ink")
    settings = _vision.spec(layout, "ace.perception-signature-layout.v1", names)
    original = sha256(blank).hexdigest()
    if original != _digest(settings["blank_sha256"]):
        raise ValueError("Formulir kosong berbeda dari anchor.")
    box = _vision.bounded_box(settings["box"], a)
    span = (box[2]-box[0])*(box[3]-box[1])
    if span > 800_000:
        raise ValueError("Area tanda tangan terlalu besar.")
    t = _integer(settings["minimum_contrast"], 1, 255, "Kontras tinta baru")
    support = _integer(settings["minimum_new_pixels"], 1, span, "Piksel baru minimum")
    minimum_unit = _integer(settings["minimum_component"], 1, span, "Komponen minimum")
    allowed_loss = _integer(settings["maximum_missing_bp"], 0, 10000, "Tinta hilang maksimum")
    light = settings["light_ink"]
    if type(light) is not bool:
        raise ValueError("Polaritas tanda perlu boolean.")
    expected = [(v*255+b.maximum//2)//b.maximum for v in b.rectangle(box)]
    observed = [(v*255+a.maximum//2)//a.maximum for v in a.rectangle(box)]
    changes = [new-old if light else old-new for old, new in zip(expected, observed, strict=True)]
    ink = [value >= t for value in changes]
    lost = sum(value <= -t for value in changes)
    components = list(_components(ink, box[2]-box[0]))
    total = sum(ink)
    strongest = max((score for _, score in components), default=0)
    status = "present" if total >= support and strongest >= minimum_unit else "not_detected"
    if lost*10000 > allowed_loss*span:
        status = "registration_uncertain"
    qualifying = []
    for coords, size in components:
        if size >= minimum_unit and len(qualifying) < 128:
            x, y = box[:2]
            qualifying.append({"box": [coords[0]+x, coords[1]+y, coords[2]+x, coords[3]+y], "new_pixels": size})
    return {"schema": "ace.perception-signature-presence.v1", "image_sha256": sha256(marked).hexdigest(),
            "blank_sha256": original, "layout_sha256": sha256(layout).hexdigest(), "box": box, "status": status,
            "observed_new_pixels": total, "removed_pixels": lost, "largest_component": strongest,
            "components": qualifying, "component_total": len(components), "examined_pixels": span}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("marked", type=Path)
    parser.add_argument("blank", type=Path)
    parser.add_argument("layout", type=Path)
    args = parser.parse_args(argv)
    try:
        report = inspect(_raster.read(args.marked), _raster.read(args.blank), _raster.read(args.layout, _vision.MAX_SPEC_BYTES))
        sys.stdout.buffer.write(_canonical(report)+b"\n")
    except (OSError, OverflowError, ValueError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return int(report["status"] == "registration_uncertain")


if __name__ == "__main__":
    raise SystemExit(main())
