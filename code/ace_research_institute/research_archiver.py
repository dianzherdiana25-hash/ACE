"""Bekukan sumber, resep, dan laporan riset dalam paket yang dapat diperiksa ulang."""
import argparse
from hashlib import sha256
from io import BytesIO
from pathlib import Path, PurePosixPath
import stat
import sys
import zipfile

from ._contracts import (ResearchError, anchor, canonical, decode, digest, identifier,
                         integer, items, obj, read, schema, source_bytes, text)


CAP = 12_000_000
MEMBER_CAP = 2_000_000
ROLES = {"protocol", "source", "report", "data", "analysis", "license"}


def _name(raw):
    value = text(raw, "Path arsip", 280)
    path = PurePosixPath(value)
    if (path.is_absolute() or value.casefold() == "manifest.json" or ":" in value or "\\" in value
            or any(item in ("", ".", "..") for item in value.split("/"))):
        raise ResearchError("Path arsip perlu relatif, bebas lompatan dan jelas.")
    return value


def _add(bundle, name, payload):
    member = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
    member.create_system = 3
    member.external_attr = (stat.S_IFREG | 0o644) << 16
    bundle.writestr(member, payload, compress_type=zipfile.ZIP_DEFLATED, compresslevel=6)


def archive(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.institute.archive-plan.v1", ("study", "members"))
    study = identifier(plan["study"], "Studi")
    payloads = {}
    seen = set()
    total = 0
    for row in items(plan["members"], 200, 2):
        obj(row, ("path", "sha256", "target", "role", "source_ref"))
        path = _name(row["target"])
        if path.casefold() in seen or row["role"] not in ROLES:
            raise ResearchError("Nama anggota ganda atau peran arsip tak terdaftar.")
        seen.add(path.casefold())
        data = source_bytes(root, row["path"], row["sha256"], MEMBER_CAP)
        total += len(data)
        if total > CAP:
            raise ResearchError("Ukuran isi arsip melewati batas.")
        payloads[path] = (data, {"path": path, "role": row["role"], "bytes": len(data), "sha256": row["sha256"],
                                 "source_ref": text(row["source_ref"], "Pointer anggota")})
    if not {"report", "source"} <= {row["role"] for _, row in payloads.values()}:
        raise ResearchError("Arsip riset perlu laporan dan sumber.")
    manifest = {"schema": "ace.institute.archive-manifest.v1", "plan_sha256": expected, "study": study,
                "members": [payloads[name][1] for name in sorted(payloads)], "uncompressed_data_bytes": total}
    memory = BytesIO()
    with zipfile.ZipFile(memory, "w", allowZip64=False) as bundle:
        _add(bundle, "manifest.json", canonical(manifest) + b"\n")
        for name in sorted(payloads):
            _add(bundle, name, payloads[name][0])
    raw = memory.getvalue()
    return raw, {"schema": "ace.institute.archive-receipt.v1", "archive_sha256": sha256(raw).hexdigest(), "manifest": manifest}


def verify(raw, expected):
    if len(raw) > CAP + 750000 or sha256(raw).hexdigest() != digest(expected):
        raise ResearchError("Hash arsip berbeda atau ukuran kompresi melewati batas.")
    try:
        with zipfile.ZipFile(BytesIO(raw), "r") as package:
            file_info = package.infolist()
            if not 3 <= len(file_info) <= 201 or sum(entry.file_size for entry in file_info) > CAP + 250000:
                raise ResearchError("Jumlah anggota atau ukuran hasil ekstrak melewati batas.")
            manifest_name = "manifest.json"
            names = {}
            folded = set()
            for item in file_info:
                filename = item.filename
                if filename != manifest_name:
                    _name(filename)
                if (filename.casefold() in folded or item.file_size > MEMBER_CAP or item.flag_bits & 1
                        or not stat.S_ISREG(item.external_attr >> 16)
                        or item.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)):
                    raise ResearchError("Nama ganda, kriptografi, kompresi atau tipe anggota tidak diizinkan.")
                folded.add(filename.casefold())
                names[filename] = item
            if manifest_name not in names or names[manifest_name].file_size > 250000:
                raise ResearchError("Arsip membutuhkan manifest kecil.")
            original = package.read(manifest_name)
            manifest = decode(original)
            schema(manifest, "ace.institute.archive-manifest.v1", ("plan_sha256", "study", "members", "uncompressed_data_bytes"))
            if original != canonical(manifest) + b"\n":
                raise ResearchError("Manifest perlu bentuk kanonis.")
            digest(manifest["plan_sha256"])
            identifier(manifest["study"], "Studi")
            seen = {manifest_name}
            roles = set()
            size = 0
            for row in items(manifest["members"], 200, 2):
                obj(row, ("path", "role", "bytes", "sha256", "source_ref"))
                filename = _name(row["path"])
                if filename in seen or filename not in names or row["role"] not in ROLES:
                    raise ResearchError("Peta manifest ganda, tidak lengkap, atau peran tidak dikenal.")
                text(row["source_ref"], "Pointer anggota")
                count = integer(row["bytes"], "Ukuran anggota", 0, MEMBER_CAP)
                if count != names[filename].file_size:
                    raise ResearchError(f"Ukuran anggota {filename} berbeda.")
                if sha256(package.read(filename)).hexdigest() != digest(row["sha256"]):
                    raise ResearchError(f"Hash anggota {filename} berbeda.")
                seen.add(filename)
                roles.add(row["role"])
                size += count
            if seen != names.keys() or not {"report", "source"} <= roles or size != manifest["uncompressed_data_bytes"]:
                raise ResearchError("Manifest tidak mencakup seluruh arsip.")
    except (zipfile.BadZipFile, RuntimeError, NotImplementedError) as error:
        raise ResearchError("Arsip ZIP rusak atau tidak didukung.") from error
    return {"schema": "ace.institute.archive-verifier.v1", "archive_sha256": expected, "study": manifest["study"],
            "members": len(seen) - 1, "verified_bytes": size, "ok": True}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest="mode", required=True)
    create = modes.add_parser("create")
    create.add_argument("root", type=Path)
    create.add_argument("output", type=Path)
    confirm = modes.add_parser("verify")
    for mode in (create, confirm):
        mode.add_argument("source", type=Path)
        mode.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        if args.mode == "create":
            data, report = archive(decode(read(args.source)), args.expect_sha256, args.root)
            with args.output.open("xb") as stream:
                stream.write(data)
        else:
            report = verify(read(args.source, CAP + 750000), args.expect_sha256)
        sys.stdout.buffer.write(canonical(report) + b"\n")
    except (OSError, ValueError, KeyError, TypeError, ArithmeticError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
