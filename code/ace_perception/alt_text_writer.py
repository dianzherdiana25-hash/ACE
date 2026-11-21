"""Tulis alt text dari bentuk dan letak yang dapat dibaca ulang.

Paket melaporkan wilayah yang dipilih, potongan yang tidak muat,
serta hash atas deskripsi geometri. Kosakata bergantung pada
layout dan polaritas yang teramati, tanpa menafsirkan identitas
atau tujuan objek dari bentuk saja.
"""
import argparse
from pathlib import Path
import sys

from . import _raster, scene_describer
from .audio_pipeline import _canonical, _integer, _sha


SHAPES = {"elongated_horizontal": "wilayah mendatar", "elongated_vertical": "wilayah tegak",
          "compact": "wilayah padat", "irregular": "wilayah tak beraturan"}


def _position(box, width, height):
    x = (box[0]+box[2])*3//(2*width)
    y = (box[1]+box[3])*3//(2*height)
    return ("kiri", "tengah", "kanan")[min(x, 2)], ("atas", "tengah", "bawah")[min(y, 2)]


def write(data, *, maximum_chars=160, maximum_regions=4, light_ink=False, threshold=None, minimum_pixels=3):
    budget = _integer(maximum_chars, 32, 1000, "Batas karakter")
    cap = _integer(maximum_regions, 1, 24, "Jumlah wilayah")
    scene = scene_describer.describe(data, light_ink=light_ink, threshold=threshold,
                                     minimum_pixels=minimum_pixels, maximum_regions=cap)
    width, height = scene["size"]
    base = f"Gambar {width} × {height} piksel."
    if not scene["regions"]:
        fallback = " Tidak ada wilayah terdeteksi."
        output = base+fallback if len(base+fallback) <= budget else base
        used = []
        visible = 0
    else:
        eligible = sorted(scene["regions"], key=lambda row: (-row["component_pixels"], row["id"]))
        tone = "terang" if light_ink else "gelap"
        used = []
        for row in eligible:
            horizontal, vertical = _position(row["box"], width, height)
            position = "tengah" if horizontal == vertical == "tengah" else f"{horizontal} {vertical}"
            phrase = f"{SHAPES[row['shape_hint']]} {tone} di {position}"
            proposed = base+" "+", ".join([*(item["phrase"] for item in used), phrase])+"."
            if len(proposed) <= budget:
                used.append({"id": row["id"], "box": row["box"], "phrase": phrase})
        visible = len(eligible)
        output = base if not used else base+" "+", ".join(item["phrase"] for item in used)+"."
    return {"schema": "ace.perception-alt-text.v1", "image_sha256": scene["image_sha256"],
            "scene_sha256": _sha(scene), "language": "id", "maximum_chars": budget, "characters": len(output),
            "alt_text": output, "regions": used, "regions_not_in_text": visible-len(used)+scene["omitted_limit"],
            "discarded_small": scene["omitted_small"]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("--maximum-chars", type=int, default=160)
    parser.add_argument("--maximum-regions", type=int, default=4)
    parser.add_argument("--light-ink", action="store_true")
    parser.add_argument("--threshold", type=int)
    args = parser.parse_args(argv)
    try:
        result = write(_raster.read(args.image), maximum_chars=args.maximum_chars, maximum_regions=args.maximum_regions,
                       light_ink=args.light_ink, threshold=args.threshold)
        sys.stdout.buffer.write(_canonical(result)+b"\n")
    except (OSError, OverflowError, ValueError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
