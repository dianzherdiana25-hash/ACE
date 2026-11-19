#!/usr/bin/env python3
"""Pengemas pembekuan korpus (Garis B3).

Mengubah daftar kandidat terpilih yang lulus `tools.corpus_lint_v2` menjadi:
1. Berkas korpus beku JSONL di direktori pembekuan target (bukan menulis liar).
2. Entri registry JSON yang diperbarui secara atomik (`tools.frozen_corpus_registry`).
3. Catatan pembekuan Markdown (`freeze_note`) yang memuat SHA-256, jumlah baris,
   sebaran `task_kind`, asal usulan, dan daftar periksa pengesahan manusia.

Gagal tertutup: bila ada ID tidak ditemukan, ID duplikat, atau kandidat
gagal lint v2, tidak ada satu pun berkas keluaran yang ditulis.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any

from tools.corpus_lint_v2 import CorpusLintV2Error, lint_corpus_files_v2
from tools.frozen_corpus_registry import (
    FrozenRegistryError,
    atomic_write_text,
    inspect_frozen_corpus,
    upsert_registry_entry,
)

FREEZE_PACK_SCHEMA = "ace.corpus-freeze-pack.v1"
_FREEZE_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*\.jsonl$")


class FreezePackError(ValueError):
    """Kesalahan masukan atau pelanggaran validasi saat mengemas korpus beku."""


def _load_selected_ids(selected_ids: list[str] | None, select_file: Path | None) -> list[str] | None:
    if selected_ids is None and select_file is None:
        return None
    ordered: list[str] = []
    if selected_ids:
        for raw in selected_ids:
            for item in raw.split(","):
                clean = item.strip()
                if clean:
                    ordered.append(clean)
    if select_file is not None:
        if not select_file.is_file():
            raise FreezePackError(f"Berkas daftar ID terpilih tidak ditemukan: {select_file}")
        for line in select_file.read_text(encoding="utf-8").splitlines():
            clean = line.strip()
            if clean and not clean.startswith("#"):
                ordered.append(clean)
    if not ordered:
        raise FreezePackError("Daftar ID terpilih tidak boleh kosong.")
    if len(set(ordered)) != len(ordered):
        raise FreezePackError("Daftar ID terpilih mengandung duplikat.")
    return ordered


def freeze_candidates(
    candidates_path: Path,
    *,
    freeze_dir: Path,
    freeze_name: str,
    registry_path: Path,
    note_path: Path,
    selected_ids: list[str] | None = None,
    select_file: Path | None = None,
    lang_specs_path: Path | None = None,
    lang_samples_dir: Path | None = None,
    code_specs_path: Path | None = None,
    frozen_paths: list[Path] | None = None,
    rationale: str = "Kandidat terpilih lolos pemeriksaan lint v2 dan siap pembekuan.",
    source_ref: str = "",
) -> dict[str, Any]:
    """Validasi, kemas korpus beku, mutakhirkan registry, dan tulis catatan pembekuan."""
    if not candidates_path.is_file():
        raise FreezePackError(f"Berkas kandidat tidak ditemukan: {candidates_path}")
    if not _FREEZE_NAME_RE.match(freeze_name) or "corpus" not in freeze_name.lower():
        raise FreezePackError(
            "freeze_name wajib nama berkas bersih berakhiran .jsonl dan memuat kata 'corpus'."
        )

    target_corpus_path = freeze_dir / freeze_name
    if target_corpus_path.exists():
        raise FreezePackError(f"Berkas korpus beku sudah ada dan tidak boleh ditimpa: {target_corpus_path}")

    id_filter = _load_selected_ids(selected_ids, select_file)
    all_lines = [line for line in candidates_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not all_lines:
        raise FreezePackError(f"Berkas kandidat kosong: {candidates_path}")

    parsed_rows: list[tuple[str, str]] = []
    for line_no, raw in enumerate(all_lines, start=1):
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise FreezePackError(f"JSON kandidat tidak sah baris {line_no}: {exc}") from exc
        if not isinstance(obj, dict) or not isinstance(obj.get("id"), str):
            raise FreezePackError(f"Baris kandidat {line_no} wajib objek dengan field 'id' string.")
        parsed_rows.append((obj["id"].strip(), raw))

    if id_filter is not None:
        row_by_id = {ep_id: raw for ep_id, raw in parsed_rows}
        missing = [ep_id for ep_id in id_filter if ep_id not in row_by_id]
        if missing:
            raise FreezePackError(f"ID terpilih tidak ditemukan di '{candidates_path}': {', '.join(missing)}")
        selected_lines = [row_by_id[ep_id] for ep_id in id_filter]
    else:
        selected_lines = [raw for _, raw in parsed_rows]

    # Tulis kandidat terpilih ke berkas sementara untuk diverifikasi linter v2 sebelum memutakhirkan target.
    freeze_dir.mkdir(parents=True, exist_ok=True)
    staged_path = target_corpus_path.with_suffix(".jsonl.staging")
    payload_text = "\n".join(selected_lines) + "\n"
    staged_path.write_text(payload_text, encoding="utf-8")
    try:
        try:
            lint_res = lint_corpus_files_v2(
                [staged_path],
                lang_specs_path=lang_specs_path,
                lang_samples_dir=lang_samples_dir,
                code_specs_path=code_specs_path,
                frozen_paths=frozen_paths,
            )
        except CorpusLintV2Error as exc:
            raise FreezePackError(f"Pemeriksaan lint v2 gagal: {exc}") from exc

        if not lint_res["valid"]:
            codes = sorted({v["code"] for v in lint_res["violations"]})
            raise FreezePackError(f"Kandidat gagal linter v2 dan tidak dibekukan: {', '.join(codes)}")

        # Pindahkan atomik ke tujuan akhir setelah lulus lint v2.
        staged_path.replace(target_corpus_path)
    finally:
        if staged_path.exists():
            staged_path.unlink(missing_ok=True)

    entry = inspect_frozen_corpus(target_corpus_path, root_dir=freeze_dir)
    registry_state = upsert_registry_entry(registry_path, entry, root_dir=freeze_dir)

    dist = Counter(entry["task_kind_distribution"])
    dist_lines = "\n".join(f"- `{k}`: {v}" for k, v in sorted(dist.items()))
    note_lines = [
        f"# Catatan Pembekuan Korpus: `{freeze_name}`",
        "",
        f"- Berkas korpus beku: `{entry['name']}`",
        f"- Jumlah baris: **{entry['line_count']}**",
        f"- Ukuran (byte): **{entry['bytes']}**",
        f"- SHA-256: `{entry['sha256']}`",
        f"- Asal kandidat: `{candidates_path.name}`",
        f"- Rujukan eksternal/PR/commit: `{source_ref or 'tidak ditetapkan'}`",
        "",
        "## Sebaran `task_kind`",
        dist_lines,
        "",
        "## Alasan Pembekuan",
        rationale,
        "",
        "## Daftar Periksa Pengesahan",
        "- [x] Lolos skema + kendala mekanis + cek anti-duplikat `corpus_lint_v2`.",
        "- [x] Entri registri terpin dengan SHA-256 pada registry.",
        "- [ ] Tanda tangan pengesahan hub (ila) / engineer utama (Ian) sebelum dipakai preregistrasi.",
    ]
    atomic_write_text(note_path, "\n".join(note_lines) + "\n")

    return {
        "schema": FREEZE_PACK_SCHEMA,
        "frozen_file": str(target_corpus_path),
        "registry_path": str(registry_path),
        "note_path": str(note_path),
        "registry_entry": entry,
        "registry_corpus_count": registry_state["corpus_count"],
        "freeze_sha256": hashlib.sha256(payload_text.encode("utf-8")).hexdigest(),
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Pengemas pembekuan korpus kandidat terpilih (Garis B3).")
    parser.add_argument("--candidates", type=Path, required=True, help="Berkas JSONL kandidat sumber.")
    parser.add_argument("--freeze-dir", type=Path, required=True, help="Direktori tujuan berkas korpus beku.")
    parser.add_argument("--freeze-name", required=True, help="Nama berkas beku (wajib memuat 'corpus' & '.jsonl').")
    parser.add_argument("--registry", type=Path, required=True, help="Path indeks registry JSON.")
    parser.add_argument("--note", type=Path, required=True, help="Path catatan pembekuan Markdown keluaran.")
    parser.add_argument("--select-id", action="append", help="ID kandidat terpilih (bisa diulang atau dipisah koma).")
    parser.add_argument("--select-file", type=Path, help="Berkas teks berisi ID terpilih (satu per baris).")
    parser.add_argument("--lang-specs", type=Path, help="Sidecar JSONL spesifikasi bahasa.")
    parser.add_argument("--lang-samples-dir", type=Path, help="Direktori sampel bahasa (*.txt).")
    parser.add_argument("--code-specs", type=Path, help="Sidecar JSONL spesifikasi kode.")
    parser.add_argument("--frozen", action="append", type=Path, default=[], help="Korpus beku pembanding anti-duplikat.")
    parser.add_argument("--rationale", default="Kandidat terpilih lolos pemeriksaan lint v2 dan siap pembekuan.")
    parser.add_argument("--source-ref", default="", help="Pin commit/PR/gelombang asal kandidat.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        res = freeze_candidates(
            args.candidates,
            freeze_dir=args.freeze_dir,
            freeze_name=args.freeze_name,
            registry_path=args.registry,
            note_path=args.note,
            selected_ids=args.select_id,
            select_file=args.select_file,
            lang_specs_path=args.lang_specs,
            lang_samples_dir=args.lang_samples_dir,
            code_specs_path=args.code_specs,
            frozen_paths=args.frozen or None,
            rationale=args.rationale,
            source_ref=args.source_ref,
        )
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0
    except (FreezePackError, FrozenRegistryError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
