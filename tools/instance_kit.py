#!/usr/bin/env python3
"""Kit isolasi multi-instans ACE — skema + validator tumpang-tindih (WS-H #21).

Menyediakan fondasi statis (`foundation_only: true`,
`second_instance_active: false`, skema `ace.instance-isolation.v1`) untuk:
1. `--init`: menyusun konfigurasi JSON instans baru dengan direktori terpisah
   (`workspace_dir`, `store_dir`, `cache_dir`, `log_dir`), port khusus, dan
   `lock_namespace` terpisah — tanpa mengaktifkan instans kedua.
2. `--validate`: memeriksa satu atau banyak konfigurasi instans terhadap
   duplikasi `instance_id`, tabrakan/nesting direktori (`is_relative_to`),
   symlink direktori, tabrakan port, tabrakan `lock_namespace`, dan
   pelanggaran status `second_instance_active`.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple


SCHEMA_VERSION = "ace.instance-isolation.v1"
DIR_FIELDS = ("workspace_dir", "store_dir", "cache_dir", "log_dir")
_INSTANCE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{1,63}$")


class InstanceKitError(ValueError):
    """Error masukan parameter atau berkas konfigurasi instans."""


def normalize_instance_id(raw: str) -> str:
    if not isinstance(raw, str):
        raise InstanceKitError("instance_id harus berupa string.")
    cleaned = raw.strip()
    if not _INSTANCE_ID_RE.match(cleaned) or ".." in cleaned:
        raise InstanceKitError(
            f"instance_id tidak sah ({raw!r}); gunakan huruf/angka/'_'/'-'/'.' tanpa '..'."
        )
    return cleaned


def build_instance_config(
    *,
    instance_id: str,
    base_dir: Path,
    port_base: int = 8100,
    port_count: int = 2,
    lock_namespace: Optional[str] = None,
    allowed_root: Optional[Path] = None,
) -> Dict[str, Any]:
    """Bangun konfigurasi isolasi instans (non-aktif) tanpa membuat proses atau state live."""
    norm_id = normalize_instance_id(instance_id)
    if port_base < 1024 or port_base + max(port_count - 1, 0) > 65535 or port_count < 1:
        raise InstanceKitError(
            f"Rentang port tidak sah: port_base={port_base}, port_count={port_count}"
        )

    root = Path(base_dir).resolve()
    inst_root = root / norm_id
    ports = {
        "api": port_base,
        "bridge": port_base + 1,
    } if port_count == 2 else {
        f"svc_{i}": port_base + i for i in range(port_count)
    }

    cfg: Dict[str, Any] = {
        "schema": SCHEMA_VERSION,
        "foundation_only": True,
        "second_instance_active": False,
        "instance_id": norm_id,
        "allowed_root": str((allowed_root or inst_root).resolve()),
        "directories": {
            "workspace_dir": str(inst_root / "workspace"),
            "store_dir": str(inst_root / "store"),
            "cache_dir": str(inst_root / "cache"),
            "log_dir": str(inst_root / "logs"),
        },
        "ports": ports,
        "lock_namespace": lock_namespace or f"ace-lock-{norm_id}",
    }
    return cfg


def load_instance_config(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        raise InstanceKitError(f"Berkas konfigurasi tidak ditemukan: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InstanceKitError(f"Gagal membaca JSON '{path}': {exc}") from exc
    if not isinstance(data, dict):
        raise InstanceKitError(f"Konfigurasi '{path}' harus berupa JSON object.")
    return data


def _check_symlink_components(path_obj: Path) -> Optional[str]:
    """Deteksi apakah komponen path yang sudah ada di disk merupakan symlink."""
    cur = Path(path_obj.anchor) if path_obj.is_absolute() else Path(".")
    for part in path_obj.parts:
        if part in ("", path_obj.anchor):
            continue
        cur = cur / part
        if cur.exists() or cur.is_symlink():
            if cur.is_symlink():
                return str(cur)
    return None


def _paths_overlap(a: Path, b: Path) -> bool:
    return a == b or a.is_relative_to(b) or b.is_relative_to(a)


def validate_isolation(
    configs: Sequence[Dict[str, Any]],
    *,
    require_inactive_foundation: bool = True,
    check_symlinks: bool = True,
) -> Dict[str, Any]:
    """Validasi isolasi direktori, symlink/containment, port, lock, dan status aktif."""
    if not configs:
        raise InstanceKitError("Minimal satu konfigurasi instans diperlukan untuk validasi.")

    violations: List[Dict[str, Any]] = []
    seen_ids: Dict[str, int] = {}
    seen_locks: Dict[str, str] = {}
    seen_ports: Dict[int, Tuple[str, str]] = {}
    recorded_dirs: List[Tuple[str, str, Path]] = []

    for idx, cfg in enumerate(configs):
        if not isinstance(cfg, dict):
            violations.append(
                {
                    "kind": "invalid_config_type",
                    "instance": f"index:{idx}",
                    "detail": "Entri konfigurasi bukan dict.",
                }
            )
            continue

        raw_id = cfg.get("instance_id")
        try:
            inst_id = normalize_instance_id(str(raw_id))
        except InstanceKitError as exc:
            inst_id = f"index:{idx}"
            violations.append(
                {"kind": "invalid_instance_id", "instance": inst_id, "detail": str(exc)}
            )

        if inst_id in seen_ids:
            violations.append(
                {
                    "kind": "duplicate_instance_id",
                    "instance": inst_id,
                    "detail": f"instance_id duplikat pada indeks {seen_ids[inst_id]} dan {idx}",
                }
            )
        else:
            seen_ids[inst_id] = idx

        if cfg.get("schema") != SCHEMA_VERSION:
            violations.append(
                {
                    "kind": "schema_mismatch",
                    "instance": inst_id,
                    "detail": f"Skema wajib {SCHEMA_VERSION}, ditemukan {cfg.get('schema')!r}",
                }
            )

        if require_inactive_foundation and cfg.get("second_instance_active") is not False:
            violations.append(
                {
                    "kind": "active_flag_forbidden",
                    "instance": inst_id,
                    "detail": "Fondasi WS-H mewajibkan second_instance_active=false",
                }
            )

        # Cek direktori
        dirs = cfg.get("directories")
        if not isinstance(dirs, dict):
            violations.append(
                {
                    "kind": "missing_directories",
                    "instance": inst_id,
                    "detail": "Field 'directories' wajib berupa dict.",
                }
            )
            dirs = {}

        allowed_root_raw = cfg.get("allowed_root")
        allowed_root: Optional[Path] = None
        if isinstance(allowed_root_raw, str) and allowed_root_raw.strip():
            allowed_root = Path(os.path.abspath(allowed_root_raw)).resolve()
            if check_symlinks:
                sym = _check_symlink_components(Path(os.path.abspath(allowed_root_raw)))
                if sym:
                    violations.append(
                        {
                            "kind": "symlink_allowed_root",
                            "instance": inst_id,
                            "detail": f"allowed_root mengandung symlink: {sym}",
                        }
                    )

        for field in DIR_FIELDS:
            raw_val = dirs.get(field)
            if not isinstance(raw_val, str) or not raw_val.strip():
                violations.append(
                    {
                        "kind": "missing_directory_field",
                        "instance": inst_id,
                        "detail": f"Direktori wajib '{field}' hilang/kosong.",
                    }
                )
                continue
            abs_unres = Path(os.path.abspath(raw_val))
            if check_symlinks:
                sym = _check_symlink_components(abs_unres)
                if sym:
                    violations.append(
                        {
                            "kind": "symlink_in_directory_path",
                            "instance": inst_id,
                            "detail": f"{field} mengandung symlink: {sym}",
                        }
                    )
            resolved = abs_unres.resolve()
            if allowed_root is not None and not resolved.is_relative_to(allowed_root):
                violations.append(
                    {
                        "kind": "root_containment_escape",
                        "instance": inst_id,
                        "detail": f"{field} ({resolved}) keluar dari allowed_root ({allowed_root})",
                    }
                )
            recorded_dirs.append((inst_id, field, resolved))

        # Cek lock_namespace
        lock_ns = cfg.get("lock_namespace")
        if not isinstance(lock_ns, str) or not lock_ns.strip():
            violations.append(
                {
                    "kind": "missing_lock_namespace",
                    "instance": inst_id,
                    "detail": "Field 'lock_namespace' wajib berupa string tidak kosong.",
                }
            )
        else:
            if lock_ns in seen_locks:
                violations.append(
                    {
                        "kind": "lock_namespace_collision",
                        "instance": inst_id,
                        "detail": f"lock_namespace {lock_ns!r} bertabrakan dengan '{seen_locks[lock_ns]}'",
                    }
                )
            else:
                seen_locks[lock_ns] = inst_id

        # Cek ports
        ports = cfg.get("ports")
        if not isinstance(ports, dict) or not ports:
            violations.append(
                {
                    "kind": "invalid_ports",
                    "instance": inst_id,
                    "detail": "Field 'ports' wajib berupa dict tidak kosong.",
                }
            )
        else:
            for port_name, port_val in sorted(ports.items()):
                if isinstance(port_val, bool) or not isinstance(port_val, int) or not (1 <= port_val <= 65535):
                    violations.append(
                        {
                            "kind": "invalid_port_number",
                            "instance": inst_id,
                            "detail": f"Port '{port_name}' tidak sah: {port_val!r}",
                        }
                    )
                    continue
                if port_val in seen_ports:
                    other_inst, other_name = seen_ports[port_val]
                    violations.append(
                        {
                            "kind": "port_collision",
                            "instance": inst_id,
                            "detail": (
                                f"Port {port_val} ({port_name}) bertabrakan dengan "
                                f"{other_inst}:{other_name}"
                            ),
                        }
                    )
                else:
                    seen_ports[port_val] = (inst_id, str(port_name))

    # Cek tumpang-tindih / nesting direktori baik antar-instans maupun intra-instans
    for i in range(len(recorded_dirs)):
        inst_a, field_a, path_a = recorded_dirs[i]
        for j in range(i + 1, len(recorded_dirs)):
            inst_b, field_b, path_b = recorded_dirs[j]
            if _paths_overlap(path_a, path_b):
                scope = "intra_instance" if inst_a == inst_b else "cross_instance"
                violations.append(
                    {
                        "kind": f"directory_overlap_{scope}",
                        "instance": f"{inst_a} <-> {inst_b}",
                        "detail": (
                            f"Direktori tumpang-tindih/nesting: "
                            f"{inst_a}.{field_a}={path_a} vs {inst_b}.{field_b}={path_b}"
                        ),
                    }
                )

    return {
        "schema": SCHEMA_VERSION,
        "foundation_only": True,
        "second_instance_active": False,
        "isolated": len(violations) == 0,
        "instance_count": len(configs),
        "directory_count": len(recorded_dirs),
        "port_count": len(seen_ports),
        "violation_count": len(violations),
        "violations": violations,
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Kit isolasi multi-instans ACE (generator config + validator tumpang-tindih)."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--init", action="store_true", help="Bangun konfigurasi isolasi instans baru")
    mode.add_argument("--validate", nargs="+", help="Validasi isolasi terhadap satu atau lebih berkas JSON")

    parser.add_argument("--instance-id", default=None, help="ID instans untuk --init (mis. ace-inst-02)")
    parser.add_argument("--base-dir", default="/tmp/ace-instances", help="Direktori induk isolasi untuk --init")
    parser.add_argument("--port-base", type=int, default=8100, help="Port awal untuk --init (default: 8100)")
    parser.add_argument("--port-count", type=int, default=2, help="Jumlah port layanan untuk --init (default: 2)")
    parser.add_argument("--lock-namespace", default=None, help="Namespace lock opsional untuk --init")
    parser.add_argument("--out", default=None, help="Tulis JSON config hasil --init ke berkas ini")

    args = parser.parse_args(argv)
    try:
        if args.init:
            if not args.instance_id:
                raise InstanceKitError("--init wajib disertai --instance-id")
            cfg = build_instance_config(
                instance_id=args.instance_id,
                base_dir=Path(args.base_dir),
                port_base=args.port_base,
                port_count=args.port_count,
                lock_namespace=args.lock_namespace,
            )
            text = json.dumps(cfg, indent=2, ensure_ascii=False)
            if args.out:
                out_path = Path(args.out)
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_text(text + "\n", encoding="utf-8")
            print(text)
            return 0

        loaded = [load_instance_config(Path(p)) for p in args.validate]
        report = validate_isolation(loaded)
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0 if report["isolated"] else 1
    except InstanceKitError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
