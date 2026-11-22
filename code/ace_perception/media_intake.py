"""Terima media lokal dengan izin eksplisit, identitas sumber, dan hash.

Permintaan yang belum memiliki izin untuk tujuan dan waktu terkait
ditahan sebelum byte media dibuka. Penerimaan menyimpan informasi
pemeriksaan format serta rujukan izin saja. Arsip opsional memakai
nama berdasarkan isi dan direktori ekspor baru.
"""
import argparse
from hashlib import sha256
from pathlib import Path
import re
import sys

from . import _audio, _perception_io, _raster, _vision
from .audio_pipeline import _canonical, _integer
from .document_extractor import _token
from .perceptual_memory import _digest, _utc


KINDS = {"pgm": _raster.MAX_BYTES, "wav": _audio.MAX_BYTES, "pdf": 12_000_000, "mp4": 32_000_000, "mkv": 32_000_000}
EXPORT_NAME = re.compile(r"[0-9a-f]{64}\.(?:pgm|wav|pdf|mp4|mkv)")


def _permission(raw, purpose, now):
    if raw is None:
        return None, "permission_missing"
    if not isinstance(raw, dict) or set(raw) != {"ref", "purposes", "start", "expires"}:
        raise ValueError("Bentuk izin media tidak sah.")
    source = _token(raw["ref"], "Rujukan izin")
    purposes = raw["purposes"]
    if not isinstance(purposes, list) or not 1 <= len(purposes) <= 20:
        raise ValueError("Izin perlu daftar tujuan.")
    allowed = {_token(value, "Tujuan izin") for value in purposes}
    if len(allowed) != len(purposes):
        raise ValueError("Tujuan izin ganda.")
    start, end = _utc(raw["start"]), _utc(raw["expires"])
    if end <= start:
        raise ValueError("Jendela izin terbalik atau kosong.")
    if purpose not in allowed:
        return source, "purpose_not_allowed"
    if now < start or now >= end:
        return source, "outside_permission_window"
    return source, None


def _verify_format(kind, data):
    if kind == "pgm":
        asset = _raster.decode(data)
        return {"check": "decoded", "width": asset.width, "height": asset.height, "gray_max": asset.maximum}
    if kind == "wav":
        asset = _audio.decode(data)
        return {"check": "decoded", "sample_rate": asset.sample_rate, "sample_count": asset.sample_count, "channels": asset.channels}
    if kind == "pdf":
        matches = data.startswith(b"%PDF-") and data[-1024:].rstrip().endswith(b"%%EOF")
    elif kind == "mp4":
        matches = len(data) >= 16 and data[4:8] == b"ftyp" and 16 <= int.from_bytes(data[:4], "big") <= len(data)
    else:
        matches = data.startswith(bytes.fromhex("1a45dfa3")) and len(data) >= 8
    if not matches:
        raise ValueError("Penanda format media tidak sesuai deklarasi.")
    return {"check": "header_only"}


def inspect(root, request):
    raw = _vision.spec(request, "ace.perception-intake-request.v1",
                       ("source_path", "source_ref", "source_sha256", "bytes", "kind", "purpose", "as_of", "permission"))
    path = raw["source_path"]
    _perception_io.relative_parts(path)
    kind = _token(raw["kind"], "Jenis media")
    if kind not in KINDS:
        raise ValueError("Jenis media belum didukung.")
    pointer = _token(raw["source_ref"], "Rujukan sumber")
    key = _digest(raw["source_sha256"])
    expected_size = _integer(raw["bytes"], 1, KINDS[kind], "Ukuran sumber")
    purpose = _token(raw["purpose"], "Tujuan media")
    now = _utc(raw["as_of"])
    permission, reason = _permission(raw["permission"], purpose, now)
    report = {"schema": "ace.perception-intake-receipt.v1", "request_sha256": sha256(request).hexdigest(),
              "source_ref": pointer, "permission_ref": permission, "purpose": purpose, "at": now.isoformat(),
              "declared_sha256": key, "observed_sha256": None, "bytes": None, "kind": kind,
              "status": "held", "reason": reason, "artifact": None, "format": None}
    if reason:
        return None, report
    data = _perception_io.read_relative(root, path, expected_size, key)
    if len(data) != expected_size:
        raise ValueError("Ukuran media berbeda dari deklarasi.")
    observed = _verify_format(kind, data)
    report.update(observed_sha256=key, bytes=len(data), status="accepted", artifact=f"{key}.{kind}", format=observed)
    return data, report


def _archive(directory, data, receipt):
    name = receipt["artifact"]
    if receipt["status"] != "accepted" or not EXPORT_NAME.fullmatch(name) or sha256(data).hexdigest() != receipt["observed_sha256"]:
        raise ValueError("Artefak penerimaan tidak cocok dengan receipt.")
    directory.mkdir(mode=0o700)
    with (directory/name).open("xb") as artifact:
        artifact.write(data)
    with (directory/"receipt.json").open("xb") as sidecar:
        sidecar.write(_canonical(receipt)+b"\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("request", type=Path)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args(argv)
    try:
        payload, receipt = inspect(args.root, _raster.read(args.request, _vision.MAX_SPEC_BYTES))
        if payload is not None and args.output_dir is not None:
            _archive(args.output_dir, payload, receipt)
        sys.stdout.buffer.write(_canonical(receipt)+b"\n")
    except (OSError, OverflowError, RecursionError, ValueError) as error:
        parser.exit(2, f"Error: {error}\n")
    return int(payload is None)


if __name__ == "__main__":
    raise SystemExit(main())
