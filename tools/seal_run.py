#!/usr/bin/env python3
"""Salin run offline ke bundel baru, atau periksa integritas bundel SHA-256."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat

if __package__:
    from .pack_evidence import BUNDLE_SCHEMA, DEFAULT_MANIFEST_NAME, pack_evidence, verify_evidence
else:
    from pack_evidence import BUNDLE_SCHEMA, DEFAULT_MANIFEST_NAME, pack_evidence, verify_evidence


SHA256 = re.compile(r"[0-9a-f]{64}")


def _raise_walk_error(error: OSError) -> None:
    raise error


def _regular_files(root: Path) -> list[Path]:
    if root.is_symlink() or not root.is_dir():
        raise ValueError("Bundel atau sumber wajib berupa direktori biasa.")
    paths = []
    for parent, directories, files in os.walk(root, followlinks=False, onerror=_raise_walk_error):
        base = Path(parent)
        for name in directories:
            if (base / name).is_symlink():
                raise ValueError("Symlink direktori tidak didukung.")
        for name in files:
            path = base / name
            if not stat.S_ISREG(path.lstat().st_mode):
                raise ValueError("Bundel hanya menerima berkas reguler.")
            if "\\" in path.relative_to(root).as_posix():
                raise ValueError("Nama berkas bundel tidak boleh mengandung garis miring terbalik.")
            paths.append(path)
    return sorted(paths)


def _manifest_bytes(bundle: Path) -> bytes:
    manifest = bundle / DEFAULT_MANIFEST_NAME
    if not manifest.exists() or not stat.S_ISREG(manifest.lstat().st_mode):
        raise ValueError("Manifest bundel wajib berupa berkas reguler.")
    return manifest.read_bytes()


def _unique_fields(pairs):
    data = dict(pairs)
    if len(data) != len(pairs):
        raise ValueError("Field JSON manifest ganda.")
    return data


def _validate_manifest(raw: bytes) -> None:
    manifest = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_fields)
    if not isinstance(manifest, dict) or manifest.get("schema") != BUNDLE_SCHEMA:
        raise ValueError("Skema manifest bundel tidak dikenal.")
    entries = manifest.get("files")
    if not isinstance(entries, list) or not entries:
        raise ValueError("Manifest wajib memuat entri berkas.")
    if type(manifest.get("file_count")) is not int or manifest["file_count"] != len(entries):
        raise ValueError("file_count tidak cocok dengan daftar berkas.")
    seen = set()
    total = 0
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("Entri manifest wajib berupa objek.")
        path = entry.get("path")
        size = entry.get("size_bytes")
        digest = entry.get("sha256")
        if not isinstance(path, str) or "\x00" in path or "\\" in path:
            raise ValueError("Path manifest tidak sah.")
        canonical = PurePosixPath(path)
        if (not canonical.parts or canonical.is_absolute() or ".." in canonical.parts
                or path != canonical.as_posix() or path == DEFAULT_MANIFEST_NAME or path in seen):
            raise ValueError("Path manifest tidak kanonik, terlarang, atau ganda.")
        if type(size) is not int or size < 0 or not isinstance(digest, str) or not SHA256.fullmatch(digest):
            raise ValueError("Ukuran atau SHA-256 entri manifest tidak sah.")
        seen.add(path)
        total += size
    if type(manifest.get("total_bytes")) is not int or manifest["total_bytes"] != total:
        raise ValueError("total_bytes tidak cocok dengan ukuran entri manifest.")


def seal_run(source: Path, bundle: Path) -> dict:
    """Salin berkas reguler yang stabil ke direktori baru dan buat manifest."""
    if source.is_symlink():
        raise ValueError("Sumber tidak boleh symlink.")
    source = source.resolve()
    destination = bundle.resolve()
    if destination.is_relative_to(source) or source.is_relative_to(destination):
        raise ValueError("Sumber dan tujuan harus berupa pohon direktori terpisah.")
    files = _regular_files(source)
    if not files or source / DEFAULT_MANIFEST_NAME in files:
        raise ValueError("Sumber harus berisi berkas dan bebas manifest.json pada akar.")

    # Eksklusif. Kegagalan hanya membersihkan direktori yang dibuat di sini.
    bundle.mkdir(mode=0o700)
    try:
        for path in files:
            target = bundle / path.relative_to(source)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
        packed = pack_evidence(bundle)
        return {**packed, "manifest_sha256": hashlib.sha256(_manifest_bytes(bundle)).hexdigest()}
    except BaseException:
        shutil.rmtree(bundle)
        raise


def verify_run(bundle: Path, *, manifest_sha256: str | None = None) -> dict:
    """Verifikasi daftar isi dan, jika diberikan, hash manifest dari penyimpan independen."""
    if manifest_sha256 is not None and not SHA256.fullmatch(manifest_sha256):
        raise ValueError("Hash manifest wajib berupa SHA-256 heksadesimal huruf kecil.")
    _regular_files(bundle)
    raw = _manifest_bytes(bundle)
    actual = hashlib.sha256(raw).hexdigest()
    if manifest_sha256 is not None and actual != manifest_sha256:
        return {"action": "verify", "valid": False, "manifest_sha256": actual,
                "manifest_pinned": False, "reason": "manifest_sha256_mismatch"}
    _validate_manifest(raw)
    return {**verify_evidence(bundle), "manifest_sha256": actual,
            "manifest_pinned": manifest_sha256 is not None}


BUNDLE_MATRIX_SCHEMA = "ace.bundle-matrix-audit.v1"


def audit_bundle_matrix(entries: list[dict], *, base_dir: Path | None = None) -> dict:
    """Audit sekumpulan bundel lintas paket terhadap manifest_sha256 yang dipin."""
    if not isinstance(entries, list) or not entries:
        raise ValueError("Daftar bundel matriks wajib tidak kosong.")
    results = []
    seen_packages = set()
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise ValueError(f"Entri matriks #{index} wajib objek JSON.")
        package = entry.get("package")
        raw_bundle = entry.get("bundle")
        pinned_sha = entry.get("manifest_sha256")
        if not isinstance(package, str) or not package.strip():
            raise ValueError(f"Entri matriks #{index} wajib memiliki nama package.")
        if package in seen_packages:
            raise ValueError(f"Nama package ganda pada matriks: {package}.")
        seen_packages.add(package)
        if not isinstance(raw_bundle, str) or not raw_bundle.strip():
            raise ValueError(f"Entri matriks '{package}' wajib memiliki path bundle.")
        if not isinstance(pinned_sha, str) or not SHA256.fullmatch(pinned_sha):
            raise ValueError(f"Entri matriks '{package}' wajib mencantumkan manifest_sha256 64-hex.")
        bundle_path = Path(raw_bundle)
        if not bundle_path.is_absolute() and base_dir is not None:
            bundle_path = base_dir / bundle_path
        try:
            ver = verify_run(bundle_path, manifest_sha256=pinned_sha)
        except (OSError, ValueError) as exc:
            ver = {
                "action": "verify",
                "valid": False,
                "manifest_pinned": False,
                "reason": "corrupt_or_unreadable_bundle",
                "error": str(exc),
            }
        results.append({
            "package": package,
            "bundle": str(raw_bundle),
            "expected_manifest_sha256": pinned_sha,
            **ver,
        })
    results.sort(key=lambda row: row["package"])
    valid_count = sum(1 for row in results if row.get("valid") is True)
    return {
        "schema": BUNDLE_MATRIX_SCHEMA,
        "all_valid": valid_count == len(results),
        "summary": {
            "total_bundles": len(results),
            "valid_count": valid_count,
            "failed_count": len(results) - valid_count,
        },
        "bundles": results,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest="mode", required=True)
    pack = modes.add_parser("pack", help="Salin sumber ke bundel baru tanpa menimpa.")
    pack.add_argument("source", type=Path)
    pack.add_argument("bundle", type=Path)
    verify = modes.add_parser("verify", help="Cek bundel dan opsional pin SHA-256 manifest.")
    verify.add_argument("bundle", type=Path)
    verify.add_argument("--manifest-sha256")
    matrix = modes.add_parser("audit-matrix", help="Audit matriks bundel lintas paket dari spesifikasi JSON.")
    matrix.add_argument("spec", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.mode == "pack":
            result = seal_run(args.source, args.bundle)
        elif args.mode == "verify":
            result = verify_run(args.bundle, manifest_sha256=args.manifest_sha256)
        else:
            raw_spec = json.loads(args.spec.read_text(encoding="utf-8"), object_pairs_hook=_unique_fields)
            result = audit_bundle_matrix(raw_spec, base_dir=args.spec.parent)
            print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
            return 0 if result["all_valid"] else 2
    except (OSError, ValueError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if result.get("valid", True) else 2


if __name__ == "__main__":
    raise SystemExit(main())
