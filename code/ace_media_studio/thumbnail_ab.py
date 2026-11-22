"""Buat dua thumbnail dengan satu faktor berbeda dan urutan tampilan tersamar yang seimbang."""
import argparse
from hashlib import sha256
from pathlib import Path
from random import Random
import sys

from ._contracts import (ContractError, canonical, checked, decode, entries,
                         identifier, identity, integer, read, schema)
from .cover_maker import make_cover


def draft_comparison(plan, expected):
    checked(plan, expected)
    schema(plan, "ace.media.thumbnail-ab.v1", ("base_cover", "factor", "levels", "subjects", "seed"))
    factor = plan["factor"]
    if factor not in ("accent", "background", "foreground"):
        raise ContractError("Faktor eksperimen terbatas pada satu warna.")
    seed = integer(plan["seed"], "Seed", 0, 2**63 - 1)
    cover = plan["base_cover"]
    if not isinstance(cover, dict):
        raise ContractError("Rencana sampul perlu objek.")
    levels = entries(plan["levels"], 2, 2)
    candidates = {}
    for label, value in zip(("A", "B"), levels, strict=True):
        item = cover | {factor: value}
        raw, report = make_cover(item, identity(item))
        if report["status"] != "pass":
            raise ContractError(f"Kontras thumbnail {label} tidak lulus batas.")
        candidates[label] = raw
    hashes = {key: sha256(value).hexdigest() for key, value in candidates.items()}
    if hashes["A"] == hashes["B"]:
        raise ContractError("Faktor tidak mengubah raster thumbnail.")
    subjects = [identifier(value, "ID unit fixture") for value in entries(plan["subjects"], 200, 2)]
    if len(set(subjects)) != len(subjects) or len(subjects) % 2:
        raise ContractError("Daftar unit harus unik dan genap untuk counterbalancing.")
    subjects.sort()
    Random(seed).shuffle(subjects)
    assignments = []
    for index, subject in enumerate(subjects):
        order = ["A", "B"] if index % 2 == 0 else ["B", "A"]
        assignments.append({"unit": subject, "display": [{"slot": i + 1, "sha256": hashes[key]} for i, key in enumerate(order)]})
    overview = {"schema": "ace.media.thumbnail-ab-plan-receipt.v1", "plan_sha256": expected, "factor": factor,
                "design": "counterbalanced_two_order", "image_sha256": hashes,
                "assignments": sorted(assignments, key=lambda row: row["unit"]), "result": None}
    return {f"thumbnail_{key}.png": raw for key, raw in candidates.items()}, overview


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        files, report = draft_comparison(decode(read(args.plan)), args.expect_sha256)
        args.output.mkdir()
        for name, content in files.items():
            (args.output / name).write_bytes(content)
        (args.output / "assignment.json").write_bytes(canonical(report) + b"\n")
        sys.stdout.buffer.write(canonical(report) + b"\n")
    except (OSError, ValueError, TypeError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
