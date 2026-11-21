"""Segel jejak sumber dan artefak persepsi dari direktori lokal.

Semua entri berukuran terbatas dan berelasi melalui DAG provenance.
Artefak turunan memerlukan leluhur sumber. Verifikasi menggunakan
head yang dipegang terpisah, lalu cek byte tanpa mengubah direktori.
"""
import argparse
from hashlib import sha256
from pathlib import Path
import sys

from . import _perception_io, _raster, _vision
from .audio_pipeline import _canonical, _integer, _sha
from .document_extractor import _token
from .perceptual_memory import _digest


MAX_ENTRIES = 256
MAX_ARTIFACT = 32_000_000
MAX_TOTAL = 96_000_000
ROLES = {"source", "transform", "receipt", "report"}


def _plan(raw, complete):
    data, paths = {}, set()
    if not isinstance(raw, list) or not 1 <= len(raw) <= MAX_ENTRIES:
        raise ValueError("Jumlah artefak bukti di luar batas.")
    total = 0
    for row in raw:
        expected = {"id", "path", "role", "parents", "declared_bytes", "sha256"}
        if not isinstance(row, dict) or set(row) != expected:
            raise ValueError("Bentuk entri bukti tidak sah.")
        key, role = _token(row["id"], "ID bukti"), _token(row["role"], "Peran bukti")
        path = row["path"]
        _perception_io.relative_parts(path)
        if key in data or path in paths or role not in ROLES:
            raise ValueError("Entri, path ganda, atau peran tak dikenal.")
        paths.add(path)
        size = _integer(row["declared_bytes"], 1, MAX_ARTIFACT, "Ukuran bukti")
        total += size
        parents = row["parents"]
        if not isinstance(parents, list) or len(parents) > 16:
            raise ValueError("Jumlah parent bukti tidak sah.")
        edges = [_token(parent, "ID parent") for parent in parents]
        if len(set(edges)) != len(edges) or (role == "source") == bool(edges):
            raise ValueError("Setiap artefak turunan harus mempunyai parent dan sumber tidak.")
        digest = _digest(row["sha256"]) if complete or row["sha256"] is not None else None
        data[key] = {"id": key, "path": path, "role": role, "parents": sorted(edges),
                     "declared_bytes": size, "sha256": digest}
    if total > MAX_TOTAL or any(parent not in data for row in data.values() for parent in row["parents"]):
        raise ValueError("Bukti terlalu besar atau parent tak terdaftar.")
    complete_ids = set()
    pending = dict(data)
    order = []
    while pending:
        stage = sorted(key for key, row in pending.items() if set(row["parents"]) <= complete_ids)
        if not stage:
            raise ValueError("Siklus pada provenance bukti.")
        for key in stage:
            complete_ids.add(key)
            order.append(pending.pop(key))
    return order


def seal(root, request):
    raw = _vision.spec(request, "ace.perception-evidence-request.v1", ("bundle_ref", "entries"))
    source = _token(raw["bundle_ref"], "Rujukan bundel")
    entries = _plan(raw["entries"], False)
    for row in entries:
        data = _perception_io.read_relative(root, row["path"], row["declared_bytes"], row["sha256"])
        if len(data) != row["declared_bytes"]:
            raise ValueError("Ukuran artefak berbeda dari deklarasi.")
        row["sha256"] = sha256(data).hexdigest()
    core = {"schema": "ace.perception-evidence.v1", "bundle_ref": source, "entries": entries,
            "request_sha256": sha256(request).hexdigest()}
    return {**core, "head_sha256": _sha(core)}


def verify(root, manifest, expected):
    fields = ("bundle_ref", "entries", "request_sha256", "head_sha256")
    raw = _vision.spec(manifest, "ace.perception-evidence.v1", fields)
    observed = _sha({key: value for key,value in raw.items() if key != "head_sha256"})
    if observed != _digest(expected) or observed != _digest(raw["head_sha256"]):
        raise ValueError("Manifest bukti berbeda dari anchor.")
    _digest(raw["request_sha256"])
    entries = _plan(raw["entries"], True)
    results = []
    for row in entries:
        try:
            data = _perception_io.read_relative(root, row["path"], row["declared_bytes"], row["sha256"])
            status = "verified" if len(data) == row["declared_bytes"] else "mismatch"
        except FileNotFoundError:
            status = "missing"
        except (OSError, ValueError):
            status = "mismatch"
        results.append({"id": row["id"], "path": row["path"], "sha256": row["sha256"], "status": status})
    return {"schema": "ace.perception-evidence-verification.v1", "head_sha256": observed,
            "bundle_ref": _token(raw["bundle_ref"], "Rujukan bundel"),
            "verified": all(row["status"] == "verified" for row in results), "entries": results}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("spec", type=Path)
    parser.add_argument("--expect-head-sha256")
    args = parser.parse_args(argv)
    try:
        data = _raster.read(args.spec, _vision.MAX_SPEC_BYTES)
        result = verify(args.root, data, args.expect_head_sha256) if args.expect_head_sha256 else seal(args.root, data)
        sys.stdout.buffer.write(_canonical(result)+b"\n")
    except (OSError, OverflowError, RecursionError, ValueError) as error:
        parser.exit(2, f"Error: {error}\n")
    return int(result.get("verified") is False)


if __name__ == "__main__":
    raise SystemExit(main())
