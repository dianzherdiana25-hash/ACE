"""Simpan resep dan artefak studio dalam arsip deterministik yang bisa diverifikasi."""
import argparse
from hashlib import sha256
from io import BytesIO
from pathlib import Path, PurePosixPath
import stat
import sys
import zipfile

from ._assets import asset
from ._contracts import (ContractError, canonical, checked, decode, digest, entries,
                         identifier, integer, obj, read, schema, text)


MAX_TOTAL = 60_000_000
MAX_MEMBER = 48_000_000
FIXED_STAMP = (1980, 1, 1, 0, 0, 0)
ROLES = ("recipe", "asset", "output", "evidence")


def _entry(path):
    if (not isinstance(path, str) or len(path) > 240 or not path.isprintable() or
            "\\" in path or ":" in path or any(part in ("", ".", "..") for part in path.split("/")) or
            PurePosixPath(path).is_absolute() or path.casefold() == "manifest.json"):
        raise ContractError("Path anggota arsip tidak sah.")
    return path


def _member(target, name, data):
    item = zipfile.ZipInfo(name, FIXED_STAMP)
    item.create_system = 3
    item.external_attr = (stat.S_IFREG | 0o644) << 16
    target.writestr(item, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=6)


def package(plan, expected, root):
    checked(plan, expected)
    schema(plan, "ace.media.archive-plan.v1", ("project", "members"))
    project = identifier(plan["project"], "Proyek")
    members = {}
    seen = set()
    total = 0
    for item in entries(plan["members"], 120, 1):
        obj(item, ("source_path", "archive_path", "sha256", "role", "source_ref"))
        key = _entry(item["archive_path"])
        role = item["role"]
        if key.casefold() in seen or role not in ROLES:
            raise ContractError("Duplikat path arsip atau peran anggota tak didukung.")
        seen.add(key.casefold())
        pointer = text(item["source_ref"], "Pointer anggota")
        data = asset(root, item["source_path"], item["sha256"], MAX_MEMBER)
        total += len(data)
        if total > MAX_TOTAL:
            raise ContractError("Anggaran isi arsip dilampaui.")
        members[key] = (data, {"path": key, "role": role, "source_ref": pointer,
                               "bytes": len(data), "sha256": item["sha256"]})
    if not any(row["role"] == "recipe" for _, row in members.values()):
        raise ContractError("Arsip memerlukan resep render yang bisa diperiksa.")
    manifest = {"schema": "ace.media.project-archive.v1", "project": project,
                "plan_sha256": expected, "members": [members[key][1] for key in sorted(members)]}
    stream = BytesIO()
    with zipfile.ZipFile(stream, "w", allowZip64=False) as target:
        _member(target, "manifest.json", canonical(manifest) + b"\n")
        for name in sorted(members):
            _member(target, name, members[name][0])
    data = stream.getvalue()
    return data, {"schema": "ace.media.archive-receipt.v1", "manifest": manifest,
                  "manifest_sha256": sha256(canonical(manifest)).hexdigest(),
                  "archive_sha256": sha256(data).hexdigest()}


def verify_archive(data, expected):
    if len(data) > MAX_TOTAL + 1_000_000 or sha256(data).hexdigest() != digest(expected):
        raise ContractError("Arsip berbeda dari anchor atau ukurannya di luar batas.")
    try:
        with zipfile.ZipFile(BytesIO(data)) as archive:
            members = archive.infolist()
            if not 2 <= len(members) <= 121 or sum(item.file_size for item in members) > MAX_TOTAL + 250_000:
                raise ContractError("Jumlah anggota atau ukuran arsip melewati batas.")
            names = {}
            folded = set()
            for item in members:
                name = item.filename
                if name != "manifest.json":
                    _entry(name)
                if (item.file_size > MAX_MEMBER or name.casefold() in folded
                        or not stat.S_ISREG(item.external_attr >> 16)
                        or item.flag_bits & 1 or item.compress_type not in (zipfile.ZIP_DEFLATED, zipfile.ZIP_STORED)):
                    raise ContractError("Bentuk berkas anggota arsip tidak sah.")
                folded.add(name.casefold())
                names[name] = item
            if "manifest.json" not in names or names["manifest.json"].file_size > 250_000:
                raise ContractError("Arsip tidak memiliki manifest yang valid.")
            original_manifest = archive.read("manifest.json")
            manifest = decode(original_manifest)
            schema(manifest, "ace.media.project-archive.v1", ("project", "plan_sha256", "members"))
            if original_manifest != canonical(manifest) + b"\n":
                raise ContractError("Manifest arsip harus memiliki bentuk kanonis.")
            identifier(manifest["project"], "Proyek")
            digest(manifest["plan_sha256"])
            mapped = set()
            has_recipe = False
            for row in entries(manifest["members"], 120, 1):
                obj(row, ("path", "role", "source_ref", "bytes", "sha256"))
                name = _entry(row["path"])
                if name in mapped or name not in names or row["role"] not in ROLES:
                    raise ContractError("Identitas anggota manifest tidak sesuai dengan arsip.")
                has_recipe |= row["role"] == "recipe"
                text(row["source_ref"], "Pointer anggota")
                info = names[name]
                if info.file_size != integer(row["bytes"], "Ukuran", 0, MAX_MEMBER):
                    raise ContractError(f"Ukuran berbeda untuk {name}.")
                if sha256(archive.read(info)).hexdigest() != digest(row["sha256"]):
                    raise ContractError(f"Hash berbeda untuk {name}.")
                mapped.add(name)
            if mapped | {"manifest.json"} != names.keys() or not has_recipe:
                raise ContractError("Arsip memiliki berkas tak tercatat atau resep tidak tersedia.")
    except (zipfile.BadZipFile, NotImplementedError, RuntimeError) as error:
        raise ContractError("ZIP rusak atau format kompresi tidak didukung.") from error
    return {"schema": "ace.media.archive-verification.v1", "archive_sha256": expected, "members": len(mapped),
            "project": manifest["project"], "ok": True}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest="mode", required=True)
    build = modes.add_parser("build")
    build.add_argument("plan", type=Path)
    build.add_argument("root", type=Path)
    build.add_argument("output", type=Path)
    check = modes.add_parser("verify")
    check.add_argument("archive", type=Path)
    for mode in (build, check):
        mode.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        if args.mode == "build":
            data, report = package(decode(read(args.plan)), args.expect_sha256, args.root)
            with args.output.open("xb") as stream:
                stream.write(data)
        else:
            report = verify_archive(read(args.archive, MAX_TOTAL + 1_000_000), args.expect_sha256)
        sys.stdout.buffer.write(canonical(report) + b"\n")
    except (OSError, ValueError, TypeError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
