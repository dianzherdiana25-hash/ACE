#!/usr/bin/env python3
"""Bundel migrasi dua-arah dengan verifikasi SHA-256 (WS-H #20).

Menyediakan fondasi portabilitas (`foundation_only: true`, skema
`ace.portability-pack.v1`) untuk:
- `--pack`: membungkus berkas/direktori terpilih menjadi bundel migrasi
  (direktori `manifest.json` + `payload/` atau arsip `.tar.gz`) beserta
  ukuran byte dan SHA-256 tiap berkas.
- `--verify`: memverifikasi keamanan path (anti-traversal, anti-symlink)
  serta keutuhan byte-per-byte seluruh berkas terhadap manifest.
- `--unpack`: memverifikasi bundel terlebih dahulu (fail-closed) lalu
  mengekstrak ke direktori tujuan dan memverifikasi ulang SHA-256 hasil tulis.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import shutil
import sys
import tarfile
import zlib
from pathlib import Path, PurePosixPath
from typing import Any, Dict, List, Optional, Sequence, Tuple

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tools import instance_kit as _instance_kit


SCHEMA_VERSION = "ace.portability-pack.v1"
PAYLOAD_DIRNAME = "payload"
MANIFEST_FILENAME = "manifest.json"


class PortabilityPackError(ValueError):
    """Error masukan, keamanan path, atau integritas bundel portabilitas."""


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path, chunk_size: int = 65536) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fp:
        while True:
            chunk = fp.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def normalize_rel_path(raw: str) -> str:
    if not isinstance(raw, str) or not raw.strip() or "\x00" in raw:
        raise PortabilityPackError(f"Path relatif tidak sah: {raw!r}")
    cleaned = raw.replace("\\", "/").strip()
    if cleaned.startswith("/") or (len(cleaned) >= 2 and cleaned[1] == ":"):
        raise PortabilityPackError(f"Path absolut ditolak: {raw!r}")
    posix = PurePosixPath(cleaned)
    if not posix.parts or any(part in ("", ".", "..") for part in posix.parts):
        raise PortabilityPackError(f"Path traversal / segmen tidak sah ditolak: {raw!r}")
    return posix.as_posix()


def _ensure_no_symlink_in_hierarchy(root: Path, rel_posix: str) -> Path:
    root_resolved = root.resolve()
    cur = root
    for part in PurePosixPath(rel_posix).parts:
        cur = cur / part
        if cur.is_symlink():
            raise PortabilityPackError(f"Symlink ditolak pada komponen path: {cur}")
    target_resolved = cur.resolve()
    try:
        target_resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise PortabilityPackError(f"Path keluar dari direktori sumber/tujuan: {rel_posix!r}") from exc
    return cur


def _collect_source_files(source_dir: Path, include_paths: Sequence[str]) -> List[Tuple[str, Path]]:
    if not source_dir.is_dir():
        raise PortabilityPackError(f"Direktori sumber tidak ditemukan: {source_dir}")
    if source_dir.is_symlink():
        raise PortabilityPackError(f"Direktori sumber tidak boleh berupa symlink: {source_dir}")

    collected: Dict[str, Path] = {}
    for raw in include_paths:
        rel = normalize_rel_path(raw)
        target = _ensure_no_symlink_in_hierarchy(source_dir, rel)
        if not target.exists():
            raise PortabilityPackError(f"Path sumber tidak ditemukan: {rel}")
        if target.is_file():
            collected[rel] = target
        elif target.is_dir():
            for dirpath, dirnames, filenames in os.walk(target, followlinks=False):
                dp = Path(dirpath)
                for dname in list(dirnames):
                    sub_dir = dp / dname
                    if sub_dir.is_symlink():
                        raise PortabilityPackError(f"Symlink direktori ditolak: {sub_dir}")
                for fname in sorted(filenames):
                    fpath = dp / fname
                    if fpath.is_symlink():
                        raise PortabilityPackError(f"Symlink berkas ditolak: {fpath}")
                    sub_rel = fpath.relative_to(source_dir).as_posix()
                    collected[normalize_rel_path(sub_rel)] = fpath
        else:
            raise PortabilityPackError(f"Jenis berkas tidak didukung: {target}")

    if not collected:
        raise PortabilityPackError("Tidak ada berkas yang dipilih untuk dibundel.")
    return sorted(collected.items(), key=lambda kv: kv[0])


def _compute_manifest_digest(files_entries: Sequence[Dict[str, Any]]) -> str:
    canonical = json.dumps(list(files_entries), sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def validate_instance_isolation_paths(config_paths: Sequence[Path]) -> Dict[str, Any]:
    """Muat dan verifikasi isolasi multi-instans fail-closed lewat tools.instance_kit."""
    try:
        configs = [_instance_kit.load_instance_config(Path(p)) for p in config_paths]
        report = _instance_kit.validate_isolation(configs)
    except _instance_kit.InstanceKitError as exc:
        raise PortabilityPackError(f"Konfigurasi instans tidak sah: {exc}") from exc
    if not report.get("isolated"):
        raise PortabilityPackError(
            "Validasi isolasi instans gagal (dibatalkan fail-closed): "
            + json.dumps(report.get("violations", []), ensure_ascii=False)
        )
    return report


def pack_bundle(
    *,
    source_dir: Path,
    out_path: Path,
    include_paths: Sequence[str],
    label: str = "ace-migration",
    force: bool = False,
    instance_configs: Optional[Sequence[Path]] = None,
) -> Dict[str, Any]:
    """Kemaskan berkas sumber menjadi bundel direktori atau arsip .tar.gz."""
    if instance_configs:
        validate_instance_isolation_paths(instance_configs)
    src = Path(source_dir)
    dest = Path(out_path)
    items = _collect_source_files(src, include_paths)

    entries: List[Dict[str, Any]] = []
    total_bytes = 0
    for rel, fpath in items:
        size = fpath.stat().st_size
        digest = _sha256_file(fpath)
        total_bytes += size
        entries.append({"path": rel, "bytes": size, "sha256": digest})

    manifest: Dict[str, Any] = {
        "schema": SCHEMA_VERSION,
        "foundation_only": True,
        "label": label,
        "file_count": len(entries),
        "total_bytes": total_bytes,
        "manifest_sha256": _compute_manifest_digest(entries),
        "files": entries,
    }
    manifest_bytes = (json.dumps(manifest, indent=2, ensure_ascii=False) + "\n").encode("utf-8")

    is_tar = dest.name.endswith(".tar.gz") or dest.name.endswith(".tgz")
    if dest.exists():
        if not force:
            raise PortabilityPackError(f"Target bundel sudah ada (gunakan --force): {dest}")
        if dest.is_dir():
            shutil.rmtree(dest)
        else:
            dest.unlink()

    if is_tar:
        dest.parent.mkdir(parents=True, exist_ok=True)
        with tarfile.open(dest, "w:gz") as tf:
            m_info = tarfile.TarInfo(name=MANIFEST_FILENAME)
            m_info.size = len(manifest_bytes)
            m_info.mode = 0o644
            tf.addfile(m_info, io.BytesIO(manifest_bytes))
            for rel, fpath in items:
                data = fpath.read_bytes()
                f_info = tarfile.TarInfo(name=f"{PAYLOAD_DIRNAME}/{rel}")
                f_info.size = len(data)
                f_info.mode = 0o644
                tf.addfile(f_info, io.BytesIO(data))
    else:
        payload_root = dest / PAYLOAD_DIRNAME
        payload_root.mkdir(parents=True, exist_ok=True)
        (dest / MANIFEST_FILENAME).write_bytes(manifest_bytes)
        for rel, fpath in items:
            out_file = payload_root / rel
            out_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(fpath, out_file)

    return {
        "schema": SCHEMA_VERSION,
        "foundation_only": True,
        "action": "pack",
        "format": "tar.gz" if is_tar else "directory",
        "bundle_path": str(dest),
        "file_count": len(entries),
        "total_bytes": total_bytes,
        "manifest_sha256": manifest["manifest_sha256"],
    }


def _read_bundle_contents(bundle_path: Path) -> Tuple[Dict[str, Any], Dict[str, bytes], List[str]]:
    if not bundle_path.exists():
        raise PortabilityPackError(f"Bundel tidak ditemukan: {bundle_path}")

    errors: List[str] = []
    payload_bytes: Dict[str, bytes] = {}

    if bundle_path.is_dir():
        manifest_file = bundle_path / MANIFEST_FILENAME
        payload_root = bundle_path / PAYLOAD_DIRNAME
        if not manifest_file.is_file():
            raise PortabilityPackError(f"Manifest hilang di bundel direktori: {manifest_file}")
        if not payload_root.is_dir():
            raise PortabilityPackError(f"Direktori payload hilang: {payload_root}")
        try:
            manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise PortabilityPackError(f"Manifest JSON rusak: {exc}") from exc

        for dirpath, dirnames, filenames in os.walk(payload_root, followlinks=False):
            dp = Path(dirpath)
            for dname in dirnames:
                if (dp / dname).is_symlink():
                    errors.append(f"symlink_in_bundle:{(dp / dname).relative_to(payload_root).as_posix()}")
            for fname in sorted(filenames):
                fp = dp / fname
                rel_raw = fp.relative_to(payload_root).as_posix()
                if fp.is_symlink():
                    errors.append(f"symlink_in_bundle:{rel_raw}")
                    continue
                payload_bytes[rel_raw] = fp.read_bytes()
    else:
        try:
            with tarfile.open(bundle_path, "r:*") as tf:
                members = tf.getmembers()
                manifest_raw: Optional[bytes] = None
                for member in members:
                    norm_name = member.name.lstrip("./")
                    if member.issym() or member.islnk():
                        errors.append(f"symlink_in_archive:{member.name}")
                        continue
                    if ".." in PurePosixPath(norm_name).parts or member.name.startswith("/"):
                        errors.append(f"unsafe_archive_path:{member.name}")
                        continue
                    if member.isdir():
                        continue
                    if not member.isfile():
                        errors.append(f"unsupported_member_type:{member.name}")
                        continue
                    extracted = tf.extractfile(member)
                    data = extracted.read() if extracted is not None else b""
                    if norm_name == MANIFEST_FILENAME:
                        manifest_raw = data
                    elif norm_name.startswith(f"{PAYLOAD_DIRNAME}/"):
                        rel = norm_name[len(PAYLOAD_DIRNAME) + 1 :]
                        payload_bytes[rel] = data
                    else:
                        errors.append(f"unexpected_archive_member:{member.name}")
        except (tarfile.TarError, OSError, EOFError, zlib.error) as exc:
            raise PortabilityPackError(f"Gagal membaca arsip bundel '{bundle_path}': {exc}") from exc

        if manifest_raw is None:
            raise PortabilityPackError("Manifest hilang dari arsip bundel.")
        try:
            manifest = json.loads(manifest_raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise PortabilityPackError(f"Manifest JSON di arsip rusak: {exc}") from exc

    if not isinstance(manifest, dict):
        raise PortabilityPackError("Manifest harus berupa JSON object.")
    return manifest, payload_bytes, errors


def verify_bundle(bundle_path: Path) -> Tuple[Dict[str, Any], Dict[str, bytes]]:
    """Verifikasi keamanan path dan integritas SHA-256 seluruh berkas dalam bundel."""
    manifest, payload_bytes, errors = _read_bundle_contents(Path(bundle_path))

    if manifest.get("schema") != SCHEMA_VERSION:
        errors.append(f"schema_mismatch:{manifest.get('schema')}")

    raw_files = manifest.get("files")
    if not isinstance(raw_files, list):
        raise PortabilityPackError("Manifest tidak memiliki daftar 'files' yang sah.")

    normalized_entries: List[Dict[str, Any]] = []
    missing: List[str] = []
    corrupted: List[Dict[str, Any]] = []
    verified_files: List[str] = []
    seen_paths: set[str] = set()

    for idx, item in enumerate(raw_files):
        if not isinstance(item, dict):
            errors.append(f"invalid_manifest_entry:{idx}")
            continue
        raw_rel = item.get("path")
        if not isinstance(raw_rel, str):
            errors.append(f"unsafe_manifest_path:non_str:{idx}")
            continue
        try:
            rel = normalize_rel_path(raw_rel)
        except PortabilityPackError as exc:
            errors.append(f"unsafe_manifest_path:{exc}")
            continue

        if rel in seen_paths:
            errors.append(f"duplicate_manifest_path:{rel}")
            continue
        seen_paths.add(rel)

        expected_bytes = item.get("bytes")
        expected_sha = item.get("sha256")
        if (
            isinstance(expected_bytes, bool)
            or not isinstance(expected_bytes, int)
            or expected_bytes < 0
            or not isinstance(expected_sha, str)
        ):
            errors.append(f"invalid_entry_metadata:{rel}")
            continue

        normalized_entries.append({"path": rel, "bytes": expected_bytes, "sha256": expected_sha})

        if rel not in payload_bytes:
            missing.append(rel)
            continue
        actual = payload_bytes[rel]
        actual_sha = _sha256_bytes(actual)
        if len(actual) != expected_bytes or actual_sha != expected_sha:
            corrupted.append(
                {
                    "path": rel,
                    "expected_bytes": expected_bytes,
                    "actual_bytes": len(actual),
                    "expected_sha256": expected_sha,
                    "actual_sha256": actual_sha,
                }
            )
        else:
            verified_files.append(rel)

    if manifest.get("manifest_sha256") != _compute_manifest_digest(raw_files):
        errors.append("manifest_sha256_mismatch")

    extra = sorted(p for p in payload_bytes if p not in seen_paths)

    ok = not (errors or missing or corrupted or extra)
    report = {
        "schema": SCHEMA_VERSION,
        "foundation_only": True,
        "action": "verify",
        "bundle_path": str(bundle_path),
        "ok": ok,
        "verified_count": len(verified_files),
        "expected_count": len(raw_files),
        "missing": sorted(missing),
        "extra": extra,
        "corrupted": corrupted,
        "errors": errors,
    }
    return report, payload_bytes


def unpack_bundle(
    *,
    bundle_path: Path,
    dest_dir: Path,
    force: bool = False,
    instance_configs: Optional[Sequence[Path]] = None,
) -> Dict[str, Any]:
    """Verifikasi integritas bundel terlebih dahulu, lalu bongkar dan verifikasi ulang hasil tulis."""
    if instance_configs:
        validate_instance_isolation_paths(instance_configs)
    report, payload_bytes = verify_bundle(bundle_path)
    if not report["ok"]:
        raise PortabilityPackError(
            "Verifikasi bundel gagal (unpack dibatalkan fail-closed): "
            + json.dumps(
                {
                    "missing": report["missing"],
                    "extra": report["extra"],
                    "corrupted": report["corrupted"],
                    "errors": report["errors"],
                }
            )
        )

    dest = Path(dest_dir)
    if dest.exists() and dest.is_symlink():
        raise PortabilityPackError(f"Direktori tujuan tidak boleh symlink: {dest}")
    dest.mkdir(parents=True, exist_ok=True)

    planned: List[Tuple[str, Path, bytes]] = []
    for rel in sorted(payload_bytes.keys()):
        target = _ensure_no_symlink_in_hierarchy(dest, rel)
        if target.exists() and not force:
            raise PortabilityPackError(f"Berkas tujuan sudah ada (gunakan --force): {target}")
        planned.append((rel, target, payload_bytes[rel]))

    restored_bytes = 0
    for rel, target, data in planned:
        target.parent.mkdir(parents=True, exist_ok=True)
        _ensure_no_symlink_in_hierarchy(dest, rel)
        target.write_bytes(data)
        if _sha256_file(target) != _sha256_bytes(data):
            raise PortabilityPackError(f"Verifikasi pasca-tulis gagal untuk {target}")
        restored_bytes += len(data)

    return {
        "schema": SCHEMA_VERSION,
        "foundation_only": True,
        "action": "unpack",
        "bundle_path": str(bundle_path),
        "dest_dir": str(dest),
        "ok": True,
        "restored_count": len(planned),
        "restored_bytes": restored_bytes,
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Bundel migrasi dua-arah ACE (pack + verify + unpack ber-SHA256)."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--pack", action="store_true", help="Kemas berkas terpilih menjadi bundel migrasi")
    mode.add_argument("--verify", action="store_true", help="Verifikasi bundel tanpa mengekstrak")
    mode.add_argument("--unpack", action="store_true", help="Verifikasi lalu bongkar bundel ke --dest-dir")

    parser.add_argument("--bundle", required=True, help="Path bundel direktori atau arsip .tar.gz")
    parser.add_argument("--source-dir", default=".", help="Direktori asal untuk --pack")
    parser.add_argument("--paths", nargs="+", default=None, help="Daftar path relatif yang dikemas pada --pack")
    parser.add_argument("--label", default="ace-migration", help="Label bundel")
    parser.add_argument("--dest-dir", default=None, help="Direktori tujuan untuk --unpack")
    parser.add_argument("--instance-configs", nargs="+", default=None, help="Opsional config JSON instance_kit untuk verifikasi isolasi")
    parser.add_argument("--force", action="store_true", help="Izinkan menimpa bundel/berkas yang sudah ada")

    args = parser.parse_args(argv)
    inst_cfgs = [Path(p) for p in args.instance_configs] if args.instance_configs else None
    try:
        if args.pack:
            if not args.paths:
                raise PortabilityPackError("--pack wajib disertai --paths")
            res = pack_bundle(
                source_dir=Path(args.source_dir),
                out_path=Path(args.bundle),
                include_paths=args.paths,
                label=args.label,
                force=args.force,
                instance_configs=inst_cfgs,
            )
            print(json.dumps(res, indent=2, ensure_ascii=False))
            return 0
        if args.verify:
            report, _ = verify_bundle(Path(args.bundle))
            print(json.dumps(report, indent=2, ensure_ascii=False))
            return 0 if report["ok"] else 1
        if not args.dest_dir:
            raise PortabilityPackError("--unpack wajib disertai --dest-dir")
        res = unpack_bundle(
            bundle_path=Path(args.bundle),
            dest_dir=Path(args.dest_dir),
            force=args.force,
            instance_configs=inst_cfgs,
        )
        print(json.dumps(res, indent=2, ensure_ascii=False))
        return 0
    except PortabilityPackError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
