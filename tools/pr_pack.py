#!/usr/bin/env python3
"""Pengemas deskripsi draft PR dry-run dari manifest rilis C5 + templat rumah ACE.

Kenapa modul ini ada:
Setiap draft PR di repo ACE wajib memuat empat bagian templat rumah (`Apa yang
dibangun`, `Kenapa`, `Cara menjalankan tes`, `Hasil tes terakhir`) beserta
daftar berkas berubah, hash SHA-256, klasifikasi jalur, dan peringatan allowlist
dari manifest rilis (C5). Modul ini merakit bundel Markdown lengkap secara
dry-run murni di disk lokal — tidak pernah memanggil jaringan, tidak pernah
menjalankan `git push`, dan tidak pernah membuat PR di GitHub.

Exit code:
- 0: bundel deskripsi draft PR berhasil dirakit (dan tanpa peringatan bila `--strict`)
- 1: `--strict` aktif dan manifest memuat peringatan allowlist/jalur
- 2: berkas manifest, metadata, atau argumen CLI tidak sah
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

PR_PACK_SCHEMA = "ace.pr-pack.v1"
REQUIRED_TEMPLATE_HEADINGS: tuple[str, ...] = (
    "## Apa yang dibangun",
    "## Kenapa",
    "## Cara menjalankan tes",
    "## Hasil tes terakhir",
    "## Manifest Berkas Berubah",
    "## Peringatan Allowlist & Wilayah",
)


class PrPackError(ValueError):
    """Kesalahan berkas manifest C5, bagian templat rumah, atau argumen CLI."""


def _as_lines(value: Any, field_name: str) -> list[str]:
    if isinstance(value, str):
        cleaned = [ln.rstrip() for ln in value.strip().splitlines() if ln.strip()]
        if not cleaned:
            raise PrPackError(f"Bagian templat '{field_name}' tidak boleh kosong.")
        return cleaned
    if isinstance(value, list):
        cleaned = [str(item).strip() for item in value if str(item).strip()]
        if not cleaned:
            raise PrPackError(f"Bagian templat '{field_name}' tidak boleh kosong.")
        return cleaned
    raise PrPackError(f"Bagian templat '{field_name}' wajib string atau list string tidak kosong.")


def validate_manifest(manifest: Any) -> dict[str, Any]:
    """Validasi struktur manifest rilis C5 sebelum dibundel ke deskripsi PR."""
    if not isinstance(manifest, dict):
        raise PrPackError("Manifest rilis wajib berupa objek JSON.")

    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        raise PrPackError("Manifest rilis wajib memuat daftar 'files' tidak kosong.")

    for idx, entry in enumerate(files):
        if not isinstance(entry, dict):
            raise PrPackError(f"Entri files[{idx}] wajib berupa objek JSON.")
        if not isinstance(entry.get("path"), str) or not entry["path"].strip():
            raise PrPackError(f"Entri files[{idx}] wajib memiliki 'path' string tidak kosong.")
        if "classification" not in entry or "size_bytes" not in entry:
            raise PrPackError(f"Entri files[{idx}] wajib memiliki 'classification' dan 'size_bytes'.")

    branch = str(manifest.get("branch") or manifest.get("head_ref") or "").strip()
    if not branch:
        raise PrPackError("Manifest rilis wajib memuat 'branch' atau 'head_ref'.")

    return manifest


def load_json_file(path: Path, label: str) -> dict[str, Any]:
    """Muat satu berkas JSON secara baca-saja."""
    if not path.is_file():
        raise PrPackError(f"Berkas {label} tidak ditemukan: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PrPackError(f"Gagal membaca JSON {label} '{path}': {exc}") from exc
    if not isinstance(data, dict):
        raise PrPackError(f"Berkas {label} '{path}' wajib berupa objek JSON.")
    return data


def _format_bullets(items: list[str]) -> list[str]:
    out: list[str] = []
    for item in items:
        s = item.strip()
        if s.startswith(("- ", "* ")):
            out.append(s)
        else:
            out.append(f"- {s}")
    return out


def pack_pr_description(
    manifest: dict[str, Any],
    *,
    title: str,
    what: str | list[str],
    why: str | list[str],
    test_commands: str | list[str],
    test_results: str | list[str],
    notes: str | list[str] | None = None,
) -> dict[str, Any]:
    """Rakit bundel deskripsi draft PR (Markdown + metadata amplop dry-run)."""
    validated = validate_manifest(manifest)
    clean_title = title.strip() if isinstance(title, str) else ""
    if not clean_title:
        raise PrPackError("Judul draft PR ('title') wajib string tidak kosong.")

    what_lines = _as_lines(what, "apa/what")
    why_lines = _as_lines(why, "kenapa/why")
    cmd_lines = _as_lines(test_commands, "tes/test_commands")
    res_lines = _as_lines(test_results, "hasil/test_results")
    note_lines = _as_lines(notes, "notes") if notes else []

    branch = str(validated.get("branch") or validated.get("head_ref") or "unknown").strip()
    base_ref = str(validated.get("base_ref") or validated.get("base_branch") or "main").strip()
    base_sha = str(validated.get("base_sha") or "-").strip()
    head_sha = str(validated.get("head_sha") or "-").strip()
    manifest_sha = str(validated.get("manifest_sha256") or "-").strip()
    files = validated["files"]
    warnings = list(validated.get("warnings") or [])
    summary = validated.get("summary") or {}

    md_lines: list[str] = [
        f"# {clean_title}",
        "",
        "> **Mode:** `DRY-RUN SAJA` (`dry_run: true`, `network_calls: 0`, `git_push: false`, `pr_created: false`).",
        f"> **Cabang:** `{branch}` → `{base_ref}` (`base_sha`: `{base_sha[:12]}`, `head_sha`: `{head_sha[:12]}`)",
        f"> **Manifest SHA-256:** `{manifest_sha}`",
        "",
        "## Apa yang dibangun",
        "",
        *_format_bullets(what_lines),
        "",
        "## Kenapa",
        "",
        *_format_bullets(why_lines),
        "",
    ]

    if note_lines:
        md_lines.extend(
            [
                "## Catatan interpretasi",
                "",
                *_format_bullets(note_lines),
                "",
            ]
        )

    md_lines.extend(
        [
            "## Cara menjalankan tes",
            "",
            "```bash",
            *cmd_lines,
            "```",
            "",
            "## Hasil tes terakhir",
            "",
            *_format_bullets(res_lines),
            "",
            "## Manifest Berkas Berubah",
            "",
            f"- **Total berkas berubah:** {len(files)}",
            f"- **Total ukuran:** {summary.get('total_size_bytes', sum(int(f.get('size_bytes', 0)) for f in files))} byte",
            "",
            "| Path | Status | Klasifikasi | Ukuran (Byte) | SHA-256 | Allowlist |",
            "| --- | :---: | --- | ---: | --- | :---: |",
        ]
    )

    for entry in files:
        sha_disp = str(entry.get("sha256") or "-")
        if len(sha_disp) > 16:
            sha_disp = sha_disp[:16] + "..."
        allow_disp = "YA" if entry.get("in_allowlist", True) else "PERINGATAN"
        md_lines.append(
            f"| `{entry['path']}` | `{entry.get('status', 'M')}` | `{entry['classification']}` "
            f"| {entry['size_bytes']} | `{sha_disp}` | {allow_disp} |"
        )

    md_lines.extend(
        [
            "",
            "## Peringatan Allowlist & Wilayah",
            "",
        ]
    )
    if warnings:
        for w in warnings:
            reasons = "; ".join(str(r) for r in (w.get("reasons") or []))
            md_lines.append(f"- `{w.get('path', '?')}`: {reasons or 'di luar kebijakan allowlist'}")
    else:
        md_lines.append("- Tidak ada peringatan jalur; seluruh berkas berada di dalam allowlist program.")

    md_lines.append("")
    markdown = "\n".join(md_lines)
    bundle_sha256 = hashlib.sha256(markdown.encode("utf-8")).hexdigest()

    return {
        "schema": PR_PACK_SCHEMA,
        "dry_run_only": True,
        "network_calls": 0,
        "git_push_executed": False,
        "pr_created": False,
        "title": clean_title,
        "branch": branch,
        "base_ref": base_ref,
        "manifest_sha256": manifest_sha,
        "bundle_sha256": bundle_sha256,
        "changed_file_count": len(files),
        "warning_count": len(warnings),
        "required_headings_present": all(h in markdown for h in REQUIRED_TEMPLATE_HEADINGS),
        "markdown": markdown,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Kemas deskripsi draft PR lengkap dari manifest C5 + templat rumah secara dry-run."
    )
    parser.add_argument("--manifest", required=True, type=Path, help="Path berkas JSON manifest rilis C5.")
    parser.add_argument(
        "--meta",
        type=Path,
        default=None,
        help="Path berkas JSON opsional berisi field templat (title, what/apa, why/kenapa, test_commands/tes, test_results/hasil).",
    )
    parser.add_argument("--title", default=None, help="Judul draft PR.")
    parser.add_argument("--what", action="append", default=None, help="Butir 'Apa yang dibangun' (dapat diulang).")
    parser.add_argument("--why", action="append", default=None, help="Butir 'Kenapa' (dapat diulang).")
    parser.add_argument("--test-cmd", action="append", default=None, help="Baris perintah tes (dapat diulang).")
    parser.add_argument("--test-result", action="append", default=None, help="Butir hasil tes terakhir (dapat diulang).")
    parser.add_argument("--note", action="append", default=None, help="Catatan interpretasi opsional (dapat diulang).")
    parser.add_argument("--out", type=Path, default=None, help="Tulis berkas Markdown bundel PR ke path ini.")
    parser.add_argument("--json-out", type=Path, default=None, help="Tulis amplop JSON dry-run ke path ini.")
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Keluar dengan kode 1 bila manifest memiliki peringatan allowlist.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        manifest = load_json_file(args.manifest, "manifest")
        meta = load_json_file(args.meta, "meta") if args.meta else {}

        title = args.title or meta.get("title") or f"[Draft] {manifest.get('branch', 'PR')}"
        what = args.what or meta.get("what") or meta.get("apa")
        why = args.why or meta.get("why") or meta.get("kenapa")
        test_cmds = args.test_cmd or meta.get("test_commands") or meta.get("tes")
        test_results = args.test_result or meta.get("test_results") or meta.get("hasil")
        notes = args.note or meta.get("notes") or meta.get("catatan")

        if not what or not why or not test_cmds or not test_results:
            raise PrPackError(
                "Seluruh empat bagian templat rumah wajib diisi (--what, --why, --test-cmd, --test-result atau via --meta)."
            )

        bundle = pack_pr_description(
            manifest,
            title=str(title),
            what=what,
            why=why,
            test_commands=test_cmds,
            test_results=test_results,
            notes=notes,
        )
    except PrPackError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(bundle["markdown"], encoding="utf-8")
    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(bundle, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if args.format == "json":
        sys.stdout.write(json.dumps(bundle, ensure_ascii=False, indent=2) + "\n")
    else:
        sys.stdout.write(bundle["markdown"])

    if args.strict and bundle["warning_count"] > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
