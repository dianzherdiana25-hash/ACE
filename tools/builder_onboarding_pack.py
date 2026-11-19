#!/usr/bin/env python3
"""Perakit paket onboarding kontributor ACE berbasis berkas kontrak aktual (`ace.builder-onboarding-pack.v1`).

Mengumpulkan status aktual berkas kontrak tata kelola, standar fuzz, verifikasi blob sumber,
daftar batas wilayah terlarang yang terdeteksi di disk, dan resep uji worktree overlay —
mendukung format JSON/Markdown serta pemeriksa kesegaran `--check`.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
ONBOARDING_SCHEMA = "ace.builder-onboarding-pack.v1"
DEFAULT_OUTPUT_REL = "docs/BUILDER_ONBOARDING_PACK.md"

CONTRACT_REFERENCES: tuple[tuple[str, str], ...] = (
    ("handover/GOVERNANCE_RULES_20261115.md", "Dua aturan tetap: hidup+tes hijau, & ratifikasi independen"),
    ("tools/FUZZ_STANDARD.md", "Standar matriks fuzz 3 seed x 300 iterasi (0 crash tak tertangani)"),
    ("tools/verify_sources.py", "Verifikator luring SHA-1 blob berkas impor hulu"),
    ("docs/UPSTREAM_SOURCES.json", "Manifes 25 berkas impor terpin blob Git"),
    ("STATUS.md", "Papan status & aturan konsolidasi"),
    ("PROJECT.md", "Ringkasan arsitektur & cakupan repositori ACE"),
)

PROTECTED_EXACT_PATHS: tuple[str, ...] = (
    "code/ace_operational/evo0007_run.py",
    "code/ace_operational/abc_v3_scorer.py",
    "code/ace_operational/g1_instrument.py",
    "code/ace_operational/g3_instrument.py",
    "code/ace_operational/g4_instrument.py",
    "code/ace_operational/g5_instrument.py",
    "code/ace_operational/round2_instrument.py",
    "code/ace_operational/memory_writeback.py",
    "code/ace_operational/cognitive_memory.py",
    "code/ace_operational/memory_bridge.py",
    "tools/memory_writeback.py",
    "tools/round2_gate_run.py",
    "tools/abc_v3_run.py",
)

_HEADING_RE = re.compile(r"^\s{0,3}#\s+(?P<title>.+?)\s*$")


def _extract_heading_and_stats(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    sha12 = hashlib.sha256(raw).hexdigest()[:12]
    try:
        text = raw.decode("utf-8")
        lines = text.splitlines()
        line_count = len(lines)
        title = "-"
        for ln in lines[:20]:
            m = _HEADING_RE.match(ln)
            if m:
                title = re.sub(r"\s+", " ", m.group("title")).strip()
                break
    except UnicodeDecodeError:
        line_count = 0
        title = "(binary)"
    return {
        "size_bytes": len(raw),
        "line_count": line_count,
        "sha256_prefix": sha12,
        "title": title,
    }


def _check_upstream_manifest_ro(root: Path) -> dict[str, Any]:
    manifest_path = root / "docs" / "UPSTREAM_SOURCES.json"
    if manifest_path.is_symlink() or not manifest_path.is_file():
        return {"status": "NOT_PRESENT", "recorded_count": 0, "matched_count": 0}
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        files = data.get("files") if isinstance(data, dict) else None
        if not isinstance(files, dict):
            return {"status": "INVALID", "recorded_count": 0, "matched_count": 0}
        matched = 0
        for rel in sorted(files):
            meta = files[rel]
            exp = meta.get("git_blob") if isinstance(meta, dict) else None
            target = (root / rel)
            if not target.is_file() or target.is_symlink() or not target.resolve().is_relative_to(root):
                continue
            raw = target.read_bytes()
            actual = hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()
            if actual == exp:
                matched += 1
        status = "PASS" if matched == len(files) and len(files) > 0 else "MISMATCH"
        return {"status": status, "recorded_count": len(files), "matched_count": matched}
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {"status": "INVALID", "recorded_count": 0, "matched_count": 0}


def build_onboarding_pack(repo_root: Path) -> dict[str, Any]:
    """Bangun data paket onboarding kontributor ACE langsung dari berkas disk."""
    root = repo_root.resolve()
    if not root.is_dir():
        raise ValueError(f"Direktori repositori tidak ditemukan: {repo_root}")

    contracts: list[dict[str, Any]] = []
    present_contracts = 0
    for rel, purpose in CONTRACT_REFERENCES:
        fpath = root / rel
        if fpath.is_symlink() or not fpath.is_file():
            contracts.append(
                {
                    "path": rel,
                    "purpose": purpose,
                    "status": "NOT_PRESENT",
                    "line_count": 0,
                    "sha256_prefix": "-",
                    "title": "-",
                }
            )
            continue
        present_contracts += 1
        meta = _extract_heading_and_stats(fpath)
        contracts.append(
            {
                "path": rel,
                "purpose": purpose,
                "status": "PRESENT",
                **meta,
            }
        )

    protected_observed: list[dict[str, str]] = []
    for rel in sorted(PROTECTED_EXACT_PATHS):
        p = root / rel
        state = "PRESENT_ON_DISK" if (p.is_file() and not p.is_symlink()) else "NOT_ON_MAIN_PROTECTED_RESERVED"
        protected_observed.append({"path": rel, "disk_state": state})

    eval_dir = root / "code" / "ace_evaluator"
    evaluator_files = (
        sorted(
            p.relative_to(root).as_posix()
            for p in eval_dir.rglob("*.py")
            if p.is_file() and not p.is_symlink() and not p.name.startswith("test_")
        )
        if eval_dir.is_dir() and not eval_dir.is_symlink()
        else []
    )

    handover_dir = root / "handover"
    frozen_jsonl = (
        sorted(
            p.relative_to(root).as_posix()
            for p in handover_dir.glob("*.jsonl")
            if p.is_file() and not p.is_symlink()
        )
        if handover_dir.is_dir() and not handover_dir.is_symlink()
        else []
    )

    fuzz_seeds = ["20261117", "20261118", "20261119"]
    fuzz_iterations = 300
    fuzz_doc = root / "tools" / "FUZZ_STANDARD.md"
    if fuzz_doc.is_file() and not fuzz_doc.is_symlink():
        txt = fuzz_doc.read_text(encoding="utf-8", errors="ignore")
        seeds_found = re.findall(r"\b20261\d{3}\b", txt)
        if seeds_found:
            fuzz_seeds = sorted(set(seeds_found))

    upstream = _check_upstream_manifest_ro(root)
    return {
        "schema": ONBOARDING_SCHEMA,
        "repo_name": root.name,
        "summary": {
            "contracts_present": present_contracts,
            "contracts_total": len(contracts),
            "upstream_status": upstream["status"],
            "upstream_matched": upstream["matched_count"],
            "upstream_recorded": upstream["recorded_count"],
            "protected_exact_count": len(protected_observed),
            "evaluator_prod_files_count": len(evaluator_files),
            "frozen_jsonl_count": len(frozen_jsonl),
        },
        "workflow_contract": {
            "branch_prefix": "gravity/<slug>",
            "base_branch": "origin/main",
            "pr_mode": "draft_only_never_merge",
            "overlay_testing": "git worktree add --detach /tmp/<combo> origin/main (Cwd=/tmp/<combo>, segera hapus sesudah uji)",
            "bytecode_flag": "PYTHONDONTWRITEBYTECODE=1",
            "network_policy": "zero_live_http_in_tools_and_tests",
            "fuzz_seeds": fuzz_seeds,
            "fuzz_iterations_per_seed": fuzz_iterations,
        },
        "contracts": contracts,
        "upstream_sources": upstream,
        "protected_zones": {
            "exact_paths": protected_observed,
            "evaluator_modules": evaluator_files,
            "frozen_corpora": frozen_jsonl,
        },
    }


def render_markdown(pack: dict[str, Any]) -> str:
    s = pack["summary"]
    wf = pack["workflow_contract"]
    lines = [
        f"# Paket Onboarding Kontributor Builder ACE — {pack['repo_name']}",
        "",
        f"> Dibangun deterministik oleh `tools/builder_onboarding_pack.py` (`{pack['schema']}`). Seluruh status berkas, checksum, dan batas wilayah terlarang dipindai langsung dari disk.",
        "",
        "## 1. Aturan Jalur & Kontrak Kerja (Tidak Dapat Ditawar)",
        "",
        f"- **Namespace Branch:** wajib `{wf['branch_prefix']}`, bercabang bersih dari `{wf['base_branch']}`.",
        "- **Kebijakan PR:** `1 PR = 1 serahan + unit tes`, selalu dibuka sebagai **Draft PR** ke `main`, tidak pernah merge.",
        f"- **Jaringan & Bytecode:** selalu ekspor `{wf['bytecode_flag']}`, `0` panggilan HTTP live di perkakas/tes.",
        f"- **Verifikasi Overlay Gabungan:** gunakan worktree terpisah `{wf['overlay_testing']}` agar `PYTHONPATH` terisolasi dari working directory utama.",
        f"- **Standar Fuzz Parser:** `python3 tools/fuzz_parsers.py --seeds {','.join(wf['fuzz_seeds'])} --iterations {wf['fuzz_iterations_per_seed']}` (`0` crash tak tertangani).",
        f"- **Verifikasi Sumber Impor:** `python3 tools/verify_sources.py` — status saat ini **{s['upstream_status']}** ({s['upstream_matched']}/{s['upstream_recorded']} blob cocok).",
        "",
        "## 2. Daftar Dokumen Kontrak Inti",
        "",
        "| Berkas | Status | Baris | SHA-256 | Peran |",
        "| --- | --- | ---: | --- | --- |",
    ]
    for c in pack["contracts"]:
        lines.append(
            f"| `{c['path']}` | `{c['status']}` | {c['line_count']} | `{c['sha256_prefix']}` | {c['purpose']} |"
        )

    lines.extend(
        [
            "",
            "## 3. Wilayah Terlarang (Hanya Engineer Utama — Jangan Disentuh)",
            "",
            f"- Jalur eksak dipantau (`{s['protected_exact_count']}` berkas) + `{s['evaluator_prod_files_count']}` modul produksi `code/ace_evaluator/` + `{s['frozen_jsonl_count']}` corpus beku `handover/*.jsonl` + jalur direktori staging aktif EVO 0007.",
            "",
            "| Berkas / Wilayah | Keadaan di Disk Saat Ini |",
            "| --- | --- |",
        ]
    )
    for pz in pack["protected_zones"]["exact_paths"]:
        lines.append(f"| `{pz['path']}` | `{pz['disk_state']}` |")

    if pack["protected_zones"]["evaluator_modules"]:
        lines.extend(["", "### Modul `code/ace_evaluator/` Terlindung", ""])
        for mod in pack["protected_zones"]["evaluator_modules"]:
            lines.append(f"- `{mod}`")

    if pack["protected_zones"]["frozen_corpora"]:
        lines.extend(["", "### Corpus Beku `handover/*.jsonl` (Read-Only)", ""])
        for cpath in pack["protected_zones"]["frozen_corpora"]:
            lines.append(f"- `{cpath}`")

    lines.extend(
        [
            "",
            "## 4. Resep Verifikasi Sebelum Buka Draft PR",
            "",
            "```bash",
            "PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=code:. python3 -m unittest <modul_uji_terkait> -v",
            "PYTHONDONTWRITEBYTECODE=1 python3 tools/verify_sources.py",
            "git status --short  # pastikan tidak ada perubahan di wilayah terlarang / sisa tmp",
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def check_onboarding_doc(repo_root: Path, target_file: Path) -> tuple[bool, str]:
    root = repo_root.resolve()
    target = target_file if target_file.is_absolute() else (root / target_file)
    expected = render_markdown(build_onboarding_pack(root))
    if not target.is_file():
        return False, f"STALE: berkas onboarding tidak ditemukan: {target}"
    actual = target.read_text(encoding="utf-8")
    if actual != expected:
        return False, f"STALE: {target} berbeda dari keadaan kontrak repositori saat ini."
    return True, f"FRESH: {target} mutakhir dan cocok persis ({len(expected)} karakter)."


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Perakit paket onboarding kontributor ACE + pemeriksa --check."
    )
    parser.add_argument("--root", type=Path, default=REPO_ROOT, help="Direktori akar repo target.")
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--check", type=Path, default=None, help="Verifikasi kesegaran dokumen onboarding (0/1).")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
        if args.check is not None:
            fresh, msg = check_onboarding_doc(args.root, args.check)
            print(msg, file=sys.stdout if fresh else sys.stderr)
            return 0 if fresh else 1

        pack = build_onboarding_pack(args.root)
        rendered = json.dumps(pack, ensure_ascii=False, indent=2) + "\n" if args.format == "json" else render_markdown(pack)
        if args.output is not None:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(rendered, encoding="utf-8")
        else:
            sys.stdout.write(rendered)
        return 0
    except SystemExit as exc:
        return 0 if exc.code == 0 else 2
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
