"""Kemas rilis lokal reproducible dari byte yang telah disetujui.

Verifier membandingkan daftar nama, jenis, ukuran dan SHA-256 terhadap
manifest eksternal. ZIP tanpa kompresi memakai cap waktu yang tetap
supaya perbedaan tool kompresi tidak mengubah byte hasil.
"""
import argparse
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import re
import stat
import sys
from zipfile import BadZipFile, ZIP_STORED, ZipFile, ZipInfo

from ._artifact_io import read_relative
from ._contracts import ContractError, canonical, checked, decode, digest, entries, identifier, integer, obj, read, schema, text
from .repo_scaffolder import _relative


VERSION = re.compile(r"(?:0|[1-9][0-9]{0,8})\.(?:0|[1-9][0-9]{0,8})\.(?:0|[1-9][0-9]{0,8})")
STAMP = (1980, 1, 1, 0, 0, 0)
MANIFEST = "release_manifest.json"
FILE_MAX = 2_000_000
TOTAL_MAX = 10_000_000
ZIP_MAX = 12_000_000
FILE_MODE = stat.S_IFREG | 0o644


def _common(raw):
    product = identifier(raw["product_id"], "ID produk")
    version = raw["version"]
    if not isinstance(version, str) or not VERSION.fullmatch(version):
        raise ContractError("Versi perlu angka major.minor.patch kanonis.")
    return product, version, text(raw["source_ref"], "Rujukan rilis")


def _manifest_files(raw):
    total = 0
    seen = set()
    records = []
    for row in entries(raw, 200, minimum=1):
        obj(row, ("path", "sha256", "bytes"))
        name = text(row["path"], "Path kemasan", 500)
        parts = _relative(name)
        if any(part.startswith(".") or ":" in part for part in parts) or name == MANIFEST or name.casefold() in seen:
            raise ContractError("Path kemasan ganda, dicadangkan, atau tidak portabel.")
        seen.add(name.casefold())
        size = integer(row["bytes"], "Ukuran berkas", 0, FILE_MAX)
        total += size
        records.append({"path": name, "sha256": digest(row["sha256"]), "bytes": size})
    if total > TOTAL_MAX:
        raise ContractError("Isi kemasan melampaui anggaran.")
    names = {name for name in seen}
    if any("/".join(parts[:index]) in names for name in names
           for parts in [name.split("/")] for index in range(1, len(parts))):
        raise ContractError("Berkas dan direktori berbagi path.")
    return sorted(records, key=lambda item: item["path"])


def _zip_entry(name):
    info = ZipInfo(filename=name, date_time=STAMP)
    info.create_system = 3
    info.external_attr = FILE_MODE << 16
    info.compress_type = ZIP_STORED
    return info


def build(root, plan, expected):
    checked(plan, expected)
    schema(plan, "ace.factory-release-plan.v1", ("product_id", "version", "source_ref", "files"))
    product, version, ref = _common(plan)
    rows = _manifest_files(plan["files"])
    manifest = {"schema": "ace.factory-release-manifest.v1", "product_id": product, "version": version,
                "source_ref": ref, "plan_sha256": expected, "files": rows}
    payload = {MANIFEST: canonical(manifest) + b"\n"}
    for row in rows:
        data = read_relative(root, row["path"], row["bytes"], row["sha256"])
        if len(data) != row["bytes"]:
            raise ContractError("Ukuran sumber berbeda dari rencana.")
        payload[row["path"]] = data
    stream = BytesIO()
    with ZipFile(stream, "w", allowZip64=False) as archive:
        for name, data in sorted(payload.items()):
            archive.writestr(_zip_entry(name), data)
    blob = stream.getvalue()
    report = {"schema": "ace.factory-release-report.v1", "filename": f"{product}-{version}.zip",
              "zip_sha256": sha256(blob).hexdigest(), "zip_bytes": len(blob),
              "manifest_sha256": sha256(payload[MANIFEST]).hexdigest(), "files": len(rows)}
    return blob, report


def verify(blob, manifest_anchor):
    digest(manifest_anchor)
    if not isinstance(blob, bytes) or len(blob) > ZIP_MAX:
        raise ContractError("Kemasan melampaui batas ZIP.")
    try:
        with ZipFile(BytesIO(blob)) as archive:
            infos = archive.infolist()
            if not 2 <= len(infos) <= 201:
                raise ContractError("Jumlah anggota kemasan tidak sah.")
            names = [item.filename for item in infos]
            if names != sorted(set(names)) or MANIFEST not in names:
                raise ContractError("Daftar anggota kemasan tidak sah.")
            total = 0
            for item in infos:
                if (item.date_time != STAMP or item.create_system != 3 or item.external_attr >> 16 != FILE_MODE
                        or item.compress_type != ZIP_STORED or item.compress_size != item.file_size
                        or item.file_size > FILE_MAX or item.flag_bits & 1):
                    raise ContractError("Metadata anggota kemasan tidak kanonis.")
                total += item.file_size
            if total > TOTAL_MAX + 1_000_000:
                raise ContractError("Ukuran deklarasi anggota di luar batas.")
            manifest_bytes = archive.read(MANIFEST)
            if sha256(manifest_bytes).hexdigest() != manifest_anchor:
                raise ContractError("Manifest tidak cocok dengan SHA-256 eksternal.")
            manifest = decode(manifest_bytes)
            schema(manifest, "ace.factory-release-manifest.v1",
                   ("product_id", "version", "source_ref", "plan_sha256", "files"))
            _common(manifest)
            digest(manifest["plan_sha256"])
            rows = _manifest_files(manifest["files"])
            if names != sorted([MANIFEST, *(row["path"] for row in rows)]):
                raise ContractError("Isi kemasan berbeda dari manifest.")
            for row in rows:
                item = archive.getinfo(row["path"])
                if item.file_size != row["bytes"] or sha256(archive.read(item)).hexdigest() != row["sha256"]:
                    raise ContractError(f"Anggota berbeda dari manifest: {row['path']}.")
    except (BadZipFile, NotImplementedError, OverflowError) as error:
        raise ContractError("Struktur ZIP tidak sah.") from error
    return {"schema": "ace.factory-release-verification.v1", "status": "verified",
            "zip_sha256": sha256(blob).hexdigest(), "manifest_sha256": manifest_anchor, "verified_files": len(rows)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest="mode", required=True)
    make = modes.add_parser("build")
    for name in ("root", "plan", "output"):
        make.add_argument(name, type=Path)
    make.add_argument("--expect-sha256", required=True)
    check = modes.add_parser("verify")
    check.add_argument("archive", type=Path)
    check.add_argument("--manifest-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        if args.mode == "build":
            blob, report = build(args.root, decode(read(args.plan)), args.expect_sha256)
            with args.output.open("xb") as stream:
                stream.write(blob)
        else:
            report = verify(read(args.archive, ZIP_MAX), args.manifest_sha256)
        sys.stdout.buffer.write(canonical(report) + b"\n")
    except (OSError, ValueError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
