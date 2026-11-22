"""Simpan aset media menurut isi dan catat atribusi setiap entri secara terpisah."""
import argparse
from hashlib import sha256
from pathlib import Path
import sys

from ._assets import asset
from ._audio import MAX_WAV, parse_wav
from ._contracts import (ContractError, canonical, checked, decode, digest, entries,
                         identifier, integer, obj, read, schema, text)
from ._raster import MAX_BYTES, raster


CAP = {"image": MAX_BYTES, "audio": MAX_WAV, "text": 1_000_000}


def _measure(data, kind):
    if kind == "image":
        return raster(data).receipt()
    if kind == "audio":
        return parse_wav(data).receipt()
    decoded = data.decode("utf-8")
    if not decoded.strip() or "\x00" in decoded:
        raise ContractError("Aset teks tidak valid atau kosong.")
    return {"lines": len(decoded.splitlines())}


def collect(plan, expected, source_root):
    checked(plan, expected)
    schema(plan, "ace.media.library-plan.v1", ("id", "items", "max_total_bytes"))
    title = identifier(plan["id"], "Pustaka")
    budget = integer(plan["max_total_bytes"], "Batas byte pustaka", 1, 60_000_000)
    used = {}
    objects = {}
    total = 0
    for row in entries(plan["items"], 120, 1):
        obj(row, ("id", "kind", "path", "sha256", "source_ref", "license_ref", "tags"))
        key = identifier(row["id"], "ID aset")
        anchor = digest(row["sha256"])
        kind = row["kind"]
        if kind not in CAP or key in used:
            raise ContractError("Jenis aset belum didukung atau ID ganda.")
        source = text(row["source_ref"], "Pointer sumber")
        license_ref = text(row["license_ref"], "Pointer lisensi")
        tags = sorted({identifier(tag, "Tag") for tag in entries(row["tags"], 20)})
        data = asset(source_root, row["path"], anchor, CAP[kind])
        if anchor not in objects:
            if total + len(data) > budget:
                raise ContractError("Pustaka melampaui anggaran byte unik.")
            objects[anchor] = data
            total += len(data)
        used[key] = {"id": key, "kind": kind, "sha256": anchor, "bytes": len(data), "source_ref": source,
                     "license_ref": license_ref, "tags": tags, "measurement": _measure(data, kind)}
    records = [used[key] for key in sorted(used)]
    index = {"schema": "ace.media.library.v1", "plan_sha256": expected, "id": title,
             "assets": records, "objects": len(objects), "unique_bytes": total}
    return index, objects


def verify_library(index, expected, store):
    checked(index, expected)
    schema(index, "ace.media.library.v1", ("plan_sha256", "id", "assets", "objects", "unique_bytes"))
    anchors = set()
    seen = set()
    total = 0
    problems = []
    for row in entries(index["assets"], 120, 1):
        obj(row, ("id", "kind", "sha256", "bytes", "source_ref", "license_ref", "tags", "measurement"))
        kind = row["kind"]
        anchor = digest(row["sha256"])
        key = identifier(row["id"], "ID aset")
        if kind not in CAP or key in seen:
            raise ContractError("Daftar pustaka tidak sah.")
        seen.add(key)
        try:
            data = asset(store, f"objects/{anchor}", anchor, CAP[kind])
            if len(data) != row["bytes"] or _measure(data, kind) != row["measurement"]:
                problems.append({"id": key, "reason": "measurement_mismatch"})
            if anchor not in anchors:
                total += len(data)
        except (OSError, ValueError):
            problems.append({"id": key, "reason": "absent_or_hash_mismatch"})
        anchors.add(anchor)
    if len(anchors) != index["objects"] or total != index["unique_bytes"]:
        problems.append({"id": None, "reason": "object_count_or_size"})
    return {"schema": "ace.media.library-verification.v1", "index_sha256": expected, "assets": len(seen),
            "findings": problems, "ok": not problems}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest="mode", required=True)
    create = modes.add_parser("build")
    create.add_argument("plan", type=Path)
    create.add_argument("source_root", type=Path)
    create.add_argument("output", type=Path)
    check = modes.add_parser("verify")
    check.add_argument("store", type=Path)
    for mode in (create, check):
        mode.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        if args.mode == "build":
            report, objects = collect(decode(read(args.plan)), args.expect_sha256, args.source_root)
            args.output.mkdir()
            (args.output / "objects").mkdir()
            for anchor, data in objects.items():
                (args.output / "objects" / anchor).write_bytes(data)
            (args.output / "index.json").write_bytes(canonical(report) + b"\n")
        else:
            report = verify_library(decode(read(args.store / "index.json")), args.expect_sha256, args.store)
        sys.stdout.buffer.write(canonical(report) + b"\n")
    except (OSError, ValueError, TypeError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return int(not report.get("ok", True))


if __name__ == "__main__":
    raise SystemExit(main())
