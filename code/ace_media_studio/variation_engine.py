"""Jelajahi variasi terkendali dari satu brief dengan faktor, seed, dan hash hasil."""
import argparse
from hashlib import sha256
from itertools import product
from pathlib import Path
from random import Random
import sys

from ._contracts import (ContractError, canonical, checked, decode, entries,
                         identifier, identity, integer, read, schema, text)
from ._raster import color
from .image_generator import render


def _palette(raw):
    values = []
    for item in entries(raw, 8, 1):
        rgba = color(item)
        if rgba[3] != 255:
            raise ContractError("Palet varian perlu opaque.")
        values.append("#{:02x}{:02x}{:02x}".format(*rgba[:3]))
    if len(set(values)) != len(values):
        raise ContractError("Palet varian memiliki warna ganda.")
    return values


def _choice_grid(palettes, positions, motifs, seed):
    rng = Random(seed)
    grid = list(product(palettes, positions, motifs))
    rng.shuffle(grid)
    count_by_axis = [{value: 0 for value in set(axis)} for axis in (palettes, positions, motifs)]
    while grid:
        index = min(range(len(grid)), key=lambda pos: sum(count[value] for count, value in zip(count_by_axis, grid[pos], strict=True)))
        values = grid.pop(index)
        for item, count in zip(values, count_by_axis, strict=True):
            count[item] += 1
        yield values


def variants(plan, expected):
    checked(plan, expected)
    schema(plan, "ace.media.variation-plan.v1", ("id", "source_ref", "brief", "background",
                                                  "colors", "positions", "motifs", "count", "seed"))
    project = identifier(plan["id"], "ID proyek")
    source = text(plan["source_ref"], "Pointer brief")
    brief = text(plan["brief"], "Brief", 200)
    background = _palette([plan["background"]])[0]
    colors = _palette(plan["colors"])
    if background in colors:
        raise ContractError("Warna motif harus berbeda dari background.")
    positions = entries(plan["positions"], 3, 1)
    motifs = entries(plan["motifs"], 3, 1)
    if (any(item not in ("left", "center", "right") for item in positions) or len(set(positions)) != len(positions)
            or any(item not in ("disc", "diamond", "stripe") for item in motifs) or len(set(motifs)) != len(motifs)):
        raise ContractError("Posisi atau bentuk faktor tidak sah atau duplikat.")
    count = integer(plan["count"], "Jumlah varian", 1, min(24, len(colors) * len(positions) * len(motifs)))
    seed = integer(plan["seed"], "Seed", 0, 2**63 - 1)
    index = []
    binary = {}
    for offset, (swatch, position, motif) in enumerate(_choice_grid(colors, positions, motifs, seed), 1):
        x = {"left": 15, "center": 40, "right": 65}[position]
        if motif == "disc":
            shape = f"ELLIPSE {x - 8} 16 16 16 {swatch}"
        elif motif == "diamond":
            shape = f"POLYGON {swatch} {x},14 {x + 9},24 {x},34 {x - 9},24"
        else:
            shape = f"RECT {x - 3} 12 6 24 {swatch}"
        key = f"variant_{offset:02}"
        image = {"schema": "ace.media.image-plan.v1", "id": key, "source_ref": source,
                 "format": "png", "instructions": f"CANVAS 80 48 {background}\n{shape}"}
        data, report = render(image, identity(image))
        index.append({"id": key, "palette_color": swatch, "position": position, "motif": motif,
                      "image_sha256": report["image_sha256"]})
        binary[f"{key}.png"] = data
        if offset == count:
            break
    if len({item["image_sha256"] for item in index}) != count:
        raise ContractError("Render menghasilkan duplikasi byte antar varian.")
    return binary, {"schema": "ace.media.variation-receipt.v1", "plan_sha256": expected, "id": project,
                    "brief_sha256": sha256(brief.encode()).hexdigest(), "source_ref": source,
                    "method": "seeded_balanced_factor_grid", "variants": index}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        images, report = variants(decode(read(args.plan)), args.expect_sha256)
        args.output.mkdir()
        for path, data in images.items():
            (args.output / path).write_bytes(data)
        (args.output / "variants.json").write_bytes(canonical(report) + b"\n")
        sys.stdout.buffer.write(canonical(report) + b"\n")
    except (OSError, ValueError, TypeError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
