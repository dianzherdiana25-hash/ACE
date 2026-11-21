"""Petakan ketidakpastian OCR ke wilayah gambar asli.

Skor memakai jarak terburuk dua penilai pada glyph yang disepakati.
Margin alternatif dicatat terpisah. Peta memotong boks ke tile dan
mempertahankan coverage kosong, glyph tidak sepakat, dan skor rendah.
Angka adalah proxy geometri dari OCR yang sama.
"""
import argparse
from hashlib import sha256
from pathlib import Path
import sys

from . import _raster, _vision, ocr_engine
from .audio_pipeline import _canonical, _integer


MAX_TILES = 16384


def _ratio(vote):
    return vote["distance"]*10_000//vote["maximum_distance"]


def _estimate(raw):
    votes = [raw["pixel_vote"], raw["projection_vote"]]
    margins = [vote["second_margin"]*10_000//vote["maximum_distance"] for vote in votes
               if vote["second_margin"] is not None]
    return {"box": raw["box"], "status": raw["status"], "nearest_distance_bp": max(map(_ratio, votes)),
            "minimum_alternative_margin_bp": min(margins) if margins else None,
            "geometry_score_bp": 10_000-max(map(_ratio, votes)) if raw["status"] == "agreed" else None}


def _tile_map(glyphs, width, height, edge, limit):
    columns, rows = (width+edge-1)//edge, (height+edge-1)//edge
    if columns*rows > MAX_TILES:
        raise ValueError("Peta confidence melebihi jumlah tile.")
    sums = [[0, 0, 0, 0] for _ in range(columns*rows)]
    for glyph in glyphs:
        x0, y0, x1, y1 = glyph["box"]
        confidence = glyph["geometry_score_bp"]
        for row in range(y0//edge, (y1-1)//edge+1):
            for col in range(x0//edge, (x1-1)//edge+1):
                pixels = (min(x1, (col+1)*edge)-max(x0, col*edge))*(min(y1, (row+1)*edge)-max(y0, row*edge))
                bucket = sums[row*columns+col]
                if confidence is None:
                    bucket[1] += pixels
                else:
                    bucket[0] += pixels
                    bucket[2] += pixels*confidence
                    if confidence < limit:
                        bucket[3] += pixels

    tiles = []
    for index, (scored, unresolved, weighted, weak) in enumerate(sums):
        row, col = divmod(index, columns)
        box = [col*edge, row*edge, min(width, (col+1)*edge), min(height, (row+1)*edge)]
        if unresolved:
            status = "unresolved"
        elif not scored:
            status = "empty"
        elif weak:
            status = "low_geometry_score"
        else:
            status = "scored"
        tiles.append({"row": row, "column": col, "box": box, "status": status,
                      "scored_box_pixels": scored, "unresolved_box_pixels": unresolved,
                      "weak_box_pixels": weak, "mean_geometry_score_bp": weighted//scored if scored else None})
    return columns, rows, tiles


def map_confidence(image_data, font_data, *, tile_px=32, low_score_bp=9000, light_ink=False, limit_bp=2000,
                   word_gap=3):
    edge = _integer(tile_px, 1, 1024, "Lebar tile")
    minimum = _integer(low_score_bp, 1, 10_000, "Ambang skor tile")
    source = ocr_engine.recognize(image_data, font_data, light_ink=light_ink, limit_bp=limit_bp, word_gap=word_gap)
    glyphs = [_estimate(item) for row in source["lines"] for item in row["glyphs"]]
    width, height = source["width"], source["height"]
    columns, rows, tiles = _tile_map(glyphs, width, height, edge, minimum)
    return {"schema": "ace.perception-ocr-confidence-map.v1", "image_sha256": source["image_sha256"],
            "font_sha256": source["font_sha256"], "size": [width, height], "ocr_status": source["status"],
            "tile_size": edge, "columns": columns, "rows": rows, "glyphs": glyphs, "tiles": tiles,
            "metric": "ocr_geometric_proximity", "low_score_bp": minimum}


def render_tile_raster(report):
    intensities = []
    for tile in report["tiles"]:
        score = tile["mean_geometry_score_bp"]
        if tile["status"] == "unresolved":
            intensities.append(0)
        elif score is None:
            intensities.append(255)
        else:
            intensities.append(32 + score*192//10_000)
    return _vision.encode(report["columns"], report["rows"], intensities)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("font", type=Path)
    parser.add_argument("--tile-px", type=int, default=32)
    parser.add_argument("--low-score-bp", type=int, default=9000)
    parser.add_argument("--light-ink", action="store_true")
    parser.add_argument("--limit-bp", type=int, default=2000)
    parser.add_argument("--word-gap", type=int, default=3)
    parser.add_argument("--preview", type=Path)
    args = parser.parse_args(argv)
    try:
        report = map_confidence(_raster.read(args.image), _raster.read(args.font, ocr_engine.MAX_FONT_BYTES),
                               tile_px=args.tile_px, low_score_bp=args.low_score_bp, light_ink=args.light_ink,
                               limit_bp=args.limit_bp, word_gap=args.word_gap)
        if args.preview is not None:
            artifact = render_tile_raster(report)
            with args.preview.open("xb") as stream:
                stream.write(artifact)
            report["preview_sha256"] = sha256(artifact).hexdigest()
        sys.stdout.buffer.write(_canonical(report) + b"\n")
    except (OSError, OverflowError, RecursionError, ValueError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
