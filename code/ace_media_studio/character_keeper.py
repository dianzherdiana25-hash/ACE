"""Jaga identitas visual karikatur orisinal lewat landmark dan palet yang terukur."""
import argparse
from hashlib import sha256
from pathlib import Path
import sys

from ._assets import asset
from ._contracts import (ContractError, canonical, checked, decode, entries, identifier,
                         identity, integer, obj, read, schema, text)
from ._raster import MAX_BYTES, color, raster
from .image_generator import render


FEATURES = ("body", "hair", "eyes", "mark", "shirt")
POSES = {"front": (0, 0), "lean_left": (-3, -1), "lean_right": (3, -1), "smile": (0, -1)}


def _rgb(palette, label):
    rgba = color(palette[label])
    if rgba[3] != 255:
        raise ContractError("Palet karakter harus opaque.")
    return "#{:02x}{:02x}{:02x}".format(*rgba[:3])


def _design(plan):
    schema(plan, "ace.media.character-bible.v1", ("id", "source_ref", "palette", "mark_side", "face_width", "hair_height"))
    actor = identifier(plan["id"], "ID karakter")
    source = text(plan["source_ref"], "Rujukan desain orisinal")
    palette = obj(plan["palette"], (*FEATURES, "background"))
    colors = {label: _rgb(palette, label) for label in palette}
    if len(set(colors.values())) != len(colors):
        raise ContractError("Warna landmark harus memiliki identitas unik.")
    if plan["mark_side"] not in ("left", "right"):
        raise ContractError("Tanda pipi perlu sisi kiri atau kanan.")
    width = integer(plan["face_width"], "Lebar wajah", 18, 26)
    height = integer(plan["hair_height"], "Tinggi rambut", 6, 13)
    return actor, source, colors, plan["mark_side"], width, height


def _pose(plan, name):
    actor, source, colors, mark, width, height = _design(plan)
    if name not in POSES:
        raise ContractError("Pose tidak terdaftar.")
    dx, dy = POSES[name]
    x, y = 24 + dx, 24 + dy
    hair_top = y - 14
    mark_x = x + (7 if mark == "right" else -7)
    mouth_y = y + (7 if name == "smile" else 8)
    lines = [f"CANVAS 48 48 {colors['background']}",
             f"RECT {x-12} 35 24 12 {colors['shirt']}",
             f"ELLIPSE {x-width//2} {y-12} {width} 24 {colors['body']}",
             f"RECT {x-7} {hair_top} 14 {height} {colors['hair']}",
             f"RECT {x-5} {y-1} 2 3 {colors['eyes']}",
             f"RECT {x+4} {y-1} 2 3 {colors['eyes']}",
             f"RECT {mark_x-1} {y+3} 3 2 {colors['mark']}",
             f"RECT {x-2} {mouth_y} 5 1 {colors['eyes']}"]
    points = {"body": (x, y + 1), "hair": (x, hair_top + 2), "eyes": (x - 4, y),
              "mark": (mark_x, y + 3), "shirt": (x, 43)}
    image = {"schema": "ace.media.image-plan.v1", "id": actor, "source_ref": source,
             "instructions": "\n".join(lines), "format": "png"}
    return image, points, colors


def portrait(plan, expected, pose):
    checked(plan, expected)
    image, points, colors = _pose(plan, pose)
    payload, report = render(image, identity(image))
    return payload, {"schema": "ace.media.character-portrait.v1", "bible_sha256": expected,
                     "source_ref": image["source_ref"], "actor": image["id"], "pose": pose,
                     "image_sha256": report["image_sha256"], "landmarks": {
                         key: {"point": list(points[key]), "color": colors[key]} for key in FEATURES}}


def verify(plan, expected, variants):
    checked(plan, expected)
    measurements = []
    used = set()
    for pose, payload in variants:
        if pose in used:
            raise ContractError("Pose yang diperiksa ganda.")
        used.add(pose)
        _, points, colors = _pose(plan, pose)
        candidate = raster(payload)
        if (candidate.width, candidate.height) != (48, 48):
            raise ContractError("Ukuran kandidat di luar format kartu karakter.")
        tests = [{"feature": feature, "point": list(points[feature]),
                  "pass": candidate.at(*points[feature]) == color(colors[feature])[:3]}
                 for feature in FEATURES]
        measurements.append({"pose": pose, "image_sha256": sha256(payload).hexdigest(), "checks": tests})
    if not measurements:
        raise ContractError("Tidak ada varian untuk diverifikasi.")
    successes = sum(test["pass"] for item in measurements for test in item["checks"])
    total = len(measurements) * len(FEATURES)
    return {"schema": "ace.media.character-audit.v1", "bible_sha256": expected,
            "score_bp": successes * 10000 // total, "passed_landmarks": successes,
            "landmarks": total, "variants": measurements}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bible", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    actions = parser.add_subparsers(dest="action", required=True)
    make = actions.add_parser("render")
    make.add_argument("pose", choices=tuple(POSES))
    make.add_argument("output", type=Path)
    inspect = actions.add_parser("verify")
    inspect.add_argument("root", type=Path)
    inspect.add_argument("variants", type=Path)
    args = parser.parse_args(argv)
    try:
        plan = decode(read(args.bible))
        if args.action == "render":
            raw, report = portrait(plan, args.expect_sha256, args.pose)
            with args.output.open("xb") as stream:
                stream.write(raw)
        else:
            paths = entries(decode(read(args.variants)), len(POSES), 1)
            variants = []
            for item in paths:
                obj(item, ("pose", "path", "sha256"))
                variants.append((item["pose"], asset(args.root, item["path"], item["sha256"], MAX_BYTES)))
            report = verify(plan, args.expect_sha256, variants)
        sys.stdout.buffer.write(canonical(report) + b"\n")
    except (OSError, ValueError, TypeError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return int(report.get("score_bp", 10000) < 9000)


if __name__ == "__main__":
    raise SystemExit(main())
