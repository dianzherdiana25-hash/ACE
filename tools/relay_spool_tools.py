"""Perkakas mandiri validator dan pembersih spool relai brain bridge (D8).

Mengapa modul ini dibuat terpisah: relai store-and-forward (`brain_bridge_relay`
dan `brain_bridge_pump`) memakai pasangan berkas JSON `req/<id>.json` serta
`resp/<id>.json` dengan pembersihan sementara via `.tmp`. Ketika transpor gagal
atau terpotong di tengah jalan, operator butuh cara offline yang aman untuk:
1) memvalidasi skema & keutuhan berkas spool dengan alasan penolakan eksplisit,
2) mendata berkas yatim (tak berpasangan atau melewati batas umur) secara
   *dry-run* bawaan agar tidak menghapus antrean aktif secara tidak sengaja.

Modul ini sengaja berdiri sendiri dan TIDAK disambungkan ke engine maupun relai hidup.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys
import time
from typing import Any, Sequence


VALIDATOR_SCHEMA = "ace.relay-spool-validation.v1"
CLEANER_SCHEMA = "ace.relay-spool-clean.v1"

SUBDIRS = ("req", "resp")


class RelaySpoolError(ValueError):
    """Galat input atau konfigurasi untuk perkakas spool relai."""


def _reject_non_finite(token: str) -> Any:
    raise ValueError(f"konstanta JSON non-finit ditolak: {token}")


def _strict_loads(raw_text: str) -> Any:
    return json.loads(raw_text, parse_constant=_reject_non_finite)


def _infer_kind(path: Path, explicit_kind: str | None) -> str | None:
    if explicit_kind is not None:
        if explicit_kind in SUBDIRS:
            return explicit_kind
        return explicit_kind
    parent_name = path.parent.name
    if parent_name in SUBDIRS:
        return parent_name
    return None


def validate_spool_file(path: Path, *, kind: str | None = None) -> dict[str, Any]:
    """Validasi satu berkas spool relai (`req` atau `resp`) secara read-only."""
    target = Path(path)
    resolved_kind = _infer_kind(target, kind)
    reasons: list[str] = []

    if resolved_kind not in SUBDIRS:
        reasons.append(f"unknown_spool_kind:{resolved_kind}")

    if target.is_symlink():
        reasons.append("symlink_disallowed")
    elif not target.exists():
        reasons.append("file_not_found")
    elif not target.is_file():
        reasons.append("not_a_regular_file")

    if reasons and not target.is_file():
        return {
            "schema": VALIDATOR_SCHEMA,
            "path": str(target),
            "kind": resolved_kind,
            "valid": False,
            "reasons": reasons,
        }
    if target.is_symlink():
        return {
            "schema": VALIDATOR_SCHEMA,
            "path": str(target),
            "kind": resolved_kind,
            "valid": False,
            "reasons": reasons,
        }

    try:
        raw_bytes = target.read_bytes()
    except OSError as exc:
        reasons.append(f"read_error:{exc}")
        return {
            "schema": VALIDATOR_SCHEMA,
            "path": str(target),
            "kind": resolved_kind,
            "valid": False,
            "reasons": reasons,
        }

    if not raw_bytes or not raw_bytes.strip():
        reasons.append("empty_file")
        return {
            "schema": VALIDATOR_SCHEMA,
            "path": str(target),
            "kind": resolved_kind,
            "valid": False,
            "reasons": reasons,
        }

    try:
        text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        reasons.append(f"invalid_utf8:{exc.reason}")
        return {
            "schema": VALIDATOR_SCHEMA,
            "path": str(target),
            "kind": resolved_kind,
            "valid": False,
            "reasons": reasons,
        }

    try:
        doc = _strict_loads(text)
    except json.JSONDecodeError as exc:
        reasons.append(f"corrupt_or_truncated_json:{exc.msg}")
        return {
            "schema": VALIDATOR_SCHEMA,
            "path": str(target),
            "kind": resolved_kind,
            "valid": False,
            "reasons": reasons,
        }
    except ValueError as exc:
        reasons.append(f"non_finite_json_number:{exc}")
        return {
            "schema": VALIDATOR_SCHEMA,
            "path": str(target),
            "kind": resolved_kind,
            "valid": False,
            "reasons": reasons,
        }

    if not isinstance(doc, dict):
        reasons.append(f"non_object_root:{type(doc).__name__}")
        return {
            "schema": VALIDATOR_SCHEMA,
            "path": str(target),
            "kind": resolved_kind,
            "valid": False,
            "reasons": reasons,
        }

    if resolved_kind == "req":
        req_path = doc.get("path")
        if "path" not in doc:
            reasons.append("missing_field:path")
        elif not isinstance(req_path, str) or not req_path.startswith("/") or any(c.isspace() for c in req_path):
            reasons.append("invalid_field:path")

        if "request" not in doc:
            reasons.append("missing_field:request")
        elif not isinstance(doc.get("request"), dict):
            reasons.append("invalid_type:request")

        ts = doc.get("ts")
        if "ts" not in doc:
            reasons.append("missing_field:ts")
        elif isinstance(ts, bool) or not isinstance(ts, (int, float)) or not math.isfinite(ts) or ts < 0:
            reasons.append("invalid_field:ts")

    elif resolved_kind == "resp":
        status = doc.get("status")
        if "status" not in doc:
            reasons.append("missing_field:status")
        elif isinstance(status, bool) or not isinstance(status, int) or not (100 <= status <= 599):
            reasons.append("invalid_field:status")

        if "body" not in doc:
            reasons.append("missing_field:body")
        elif not isinstance(doc.get("body"), dict):
            reasons.append("invalid_type:body")

    return {
        "schema": VALIDATOR_SCHEMA,
        "path": str(target),
        "kind": resolved_kind,
        "valid": len(reasons) == 0,
        "reasons": reasons,
    }


def validate_spool_dir(spool_dir: Path) -> dict[str, Any]:
    """Validasi seluruh berkas dalam direktori spool (`req/` dan `resp/`)."""
    root = Path(spool_dir)
    if root.is_symlink() or not root.is_dir():
        raise RelaySpoolError(f"Direktori spool tidak ditemukan atau symlink: {spool_dir}")

    results: list[dict[str, Any]] = []
    warnings: list[str] = []
    for sub in SUBDIRS:
        sub_dir = root / sub
        if sub_dir.is_symlink():
            warnings.append(f"symlink_subdir_skipped:{sub}")
            continue
        if not sub_dir.exists():
            warnings.append(f"missing_subdir:{sub}")
            continue
        if not sub_dir.is_dir():
            warnings.append(f"non_dir_subdir:{sub}")
            continue
        for entry in sorted(sub_dir.iterdir(), key=lambda p: p.name):
            if entry.is_dir() and not entry.is_symlink():
                results.append(
                    {
                        "schema": VALIDATOR_SCHEMA,
                        "path": str(entry),
                        "kind": sub,
                        "valid": False,
                        "reasons": ["unexpected_subdirectory"],
                    }
                )
                continue
            if entry.name.endswith(".tmp") or entry.suffix != ".json":
                results.append(
                    {
                        "schema": VALIDATOR_SCHEMA,
                        "path": str(entry),
                        "kind": sub,
                        "valid": False,
                        "reasons": ["non_json_or_temp_artifact"],
                    }
                )
                continue
            results.append(validate_spool_file(entry, kind=sub))

    valid_count = sum(1 for r in results if r["valid"])
    invalid_count = len(results) - valid_count
    reason_counts: dict[str, int] = {}
    for item in results:
        for r in item["reasons"]:
            key = r.split(":", 1)[0]
            reason_counts[key] = reason_counts.get(key, 0) + 1

    return {
        "schema": VALIDATOR_SCHEMA,
        "spool_dir": str(root),
        "valid": invalid_count == 0 and len(warnings) == 0,
        "total_files": len(results),
        "valid_count": valid_count,
        "invalid_count": invalid_count,
        "warnings": warnings,
        "reason_counts": dict(sorted(reason_counts.items())),
        "files": results,
    }


def _validate_max_age(max_age_seconds: float) -> float:
    if (
        isinstance(max_age_seconds, bool)
        or not isinstance(max_age_seconds, (int, float))
        or not math.isfinite(max_age_seconds)
        or max_age_seconds < 0
    ):
        raise RelaySpoolError(f"max_age_seconds wajib angka non-negatif finit: {max_age_seconds!r}")
    return float(max_age_seconds)


def find_orphan_spool_files(
    spool_dir: Path,
    *,
    max_age_seconds: float = 3600.0,
    now: float | None = None,
) -> dict[str, Any]:
    """Temukan daftar berkas spool yatim (tak berpasangan atau melewati batas umur)."""
    root = Path(spool_dir)
    if root.is_symlink() or not root.is_dir():
        raise RelaySpoolError(f"Direktori spool tidak ditemukan atau symlink: {spool_dir}")
    max_age = _validate_max_age(max_age_seconds)
    now_ts = float(now) if now is not None else time.time()

    req_dir = root / "req"
    resp_dir = root / "resp"
    req_stems: set[str] = set()
    if req_dir.is_dir() and not req_dir.is_symlink():
        for entry in req_dir.iterdir():
            if not entry.is_symlink() and entry.is_file() and entry.suffix == ".json":
                req_stems.add(entry.stem)

    orphans: list[dict[str, Any]] = []
    skipped_symlinks: list[str] = []
    active_count = 0

    for sub in SUBDIRS:
        sub_dir = root / sub
        if sub_dir.is_symlink():
            skipped_symlinks.append(str(sub_dir))
            continue
        if not sub_dir.is_dir():
            continue
        for entry in sorted(sub_dir.iterdir(), key=lambda p: p.name):
            if entry.is_symlink():
                skipped_symlinks.append(str(entry))
                continue
            if not entry.is_file():
                continue
            st = entry.stat()
            age_seconds = max(0.0, now_ts - float(st.st_mtime))
            reasons: list[str] = []
            if entry.name.endswith(".tmp") or entry.suffix != ".json":
                reasons.append("temp_or_unexpected_artifact")
            if sub == "resp" and entry.suffix == ".json" and entry.stem not in req_stems:
                reasons.append("unreferenced_resp")
            if age_seconds > max_age:
                reasons.append("expired_age")

            if reasons:
                orphans.append(
                    {
                        "path": str(entry),
                        "rel_path": f"{sub}/{entry.name}",
                        "kind": sub,
                        "size_bytes": int(st.st_size),
                        "age_seconds": round(age_seconds, 3),
                        "reasons": reasons,
                    }
                )
            else:
                active_count += 1

    return {
        "schema": CLEANER_SCHEMA,
        "spool_dir": str(root),
        "max_age_seconds": max_age,
        "now": now_ts,
        "active_count": active_count,
        "orphan_count": len(orphans),
        "skipped_symlinks": sorted(skipped_symlinks),
        "orphans": orphans,
    }


def clean_orphan_spool(
    spool_dir: Path,
    *,
    max_age_seconds: float = 3600.0,
    execute: bool = False,
    now: float | None = None,
) -> dict[str, Any]:
    """Daftar atau hapus berkas spool yatim; mode bawaan adalah DRY-RUN (`execute=False`)."""
    scan = find_orphan_spool_files(spool_dir, max_age_seconds=max_age_seconds, now=now)
    deleted: list[str] = []
    errors: list[str] = []

    if execute:
        for item in scan["orphans"]:
            target = Path(item["path"])
            try:
                if target.is_symlink() or not target.is_file():
                    continue
                target.unlink()
                deleted.append(item["rel_path"])
            except OSError as exc:
                errors.append(f"{item['rel_path']}:{exc}")

    return {
        **scan,
        "dry_run": not execute,
        "would_delete": [item["rel_path"] for item in scan["orphans"]],
        "deleted": deleted,
        "deleted_count": len(deleted),
        "errors": errors,
    }


def render_clean_markdown(report: dict[str, Any]) -> str:
    mode_label = "DRY-RUN (tidak ada penghapusan)" if report["dry_run"] else "EXECUTE (hapus eksplisit)"
    lines = [
        "# Pembersihan Spool Relai ACE",
        "",
        f"- Direktori spool: `{report['spool_dir']}`",
        f"- Mode: **{mode_label}**",
        f"- Batas umur (detik): `{report['max_age_seconds']}`",
        f"- Berkas aktif aman: `{report['active_count']}`",
        f"- Berkas yatim terdeteksi: `{report['orphan_count']}`",
        f"- Berkas terhapus: `{report['deleted_count']}`",
        "",
    ]
    if report["orphans"]:
        lines.append("## Daftar Berkas Yatim")
        lines.append("")
        for item in report["orphans"]:
            reasons = ", ".join(item["reasons"])
            lines.append(
                f"- `{item['rel_path']}` ({item['size_bytes']} B, umur {item['age_seconds']}s) -> `{reasons}`"
            )
    else:
        lines.append("Tidak ada berkas yatim terdeteksi.")
    return "\n".join(lines) + "\n"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validator dan pembersih DRY-RUN spool relai brain bridge (mandiri)."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_val = sub.add_parser("validate", help="Validasi berkas atau direktori spool")
    p_val.add_argument("--spool-dir", type=Path, help="Direktori spool (berisi req/ dan resp/)")
    p_val.add_argument("--file", type=Path, help="Satu berkas spool JSON untuk divalidasi")
    p_val.add_argument("--kind", choices=SUBDIRS, default=None, help="Jenis berkas eksplisit saat memakai --file")

    p_clean = sub.add_parser("clean", help="Daftar/bersihkan berkas spool yatim (bawaan DRY-RUN)")
    p_clean.add_argument("--spool-dir", type=Path, required=True, help="Direktori spool (berisi req/ dan resp/)")
    p_clean.add_argument("--max-age-seconds", type=float, default=3600.0, help="Batas umur berkas (detik)")
    p_clean.add_argument(
        "--execute",
        action="store_true",
        help="Eksekusi penghapusan nyata; tanpa flag ini perintah hanya berjalan DRY-RUN",
    )
    p_clean.add_argument("--format", choices=("json", "md"), default="json", help="Format keluaran")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "validate":
            if bool(args.spool_dir) == bool(args.file):
                raise RelaySpoolError("Pilih tepat satu dari --spool-dir atau --file.")
            if args.file is not None:
                res = validate_spool_file(args.file, kind=args.kind)
                print(json.dumps(res, indent=2, ensure_ascii=False))
                return 0 if res["valid"] else 1
            res = validate_spool_dir(args.spool_dir)
            print(json.dumps(res, indent=2, ensure_ascii=False))
            return 0 if res["valid"] else 1

        report = clean_orphan_spool(
            args.spool_dir,
            max_age_seconds=args.max_age_seconds,
            execute=bool(args.execute),
        )
        if args.format == "md":
            print(render_clean_markdown(report), end="")
        else:
            print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0 if not report["errors"] else 1
    except RelaySpoolError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
