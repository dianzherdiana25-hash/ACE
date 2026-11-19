#!/usr/bin/env python3
"""Sensus kandidat corpus JSONL untuk menilai kesiapan pembekuan secara objektif.

Kenapa modul ini ada:
Sebelum berkas kandidat diajukan menjadi corpus beku untuk evaluasi ACE,
engineer perlu mengetahui profil kepadatannya secara deterministik — komposisi
`task_kind`, sebaran jumlah kendala per soal, ada tidaknya duplikat `id` atau
duplikat instruksi, serta alasan konkret apakah berkas tersebut sudah layak
atau belum layak dibekukan. Pemeriksaan bersifat baca-saja agar tidak pernah
mengubah berkas corpus sumber maupun corpus beku.

Exit code:
- 0: semua berkas yang disensus berstatus LAYAK (atau mode `--no-fail-on-not-ready`)
- 1: minimal satu berkas berstatus BELUM_LAYAK
- 2: argumen CLI atau berkas masukan tidak dapat dibaca
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re
import statistics
import sys
from typing import Any

from tools.corpus_lint import ALLOWED_TASK_KINDS, FROZEN_PREFIX_LEN, load_frozen_prefixes

CENSUS_SCHEMA = "ace.candidate-census.v1"

_RECOGNIZED_SPEC_KEYS = frozenset(
    {
        "word_count",
        "sentence_count",
        "paragraph_count",
        "required_phrases",
        "forbidden_words",
        "forbidden_roots",
        "forbidden_affix_roots",
        "required_order",
        "surface_hygiene",
        "complexity_time",
        "complexity_space",
        "forbidden_imports",
        "forbidden_constructs",
        "edge_cases",
        "algorithm",
    }
)

# Pola deteksi klausul kendala yang sering dipakai pada corpus bahasa & kode ACE
# (Bahasa Indonesia maupun Bahasa Inggris).
_CONSTRAINT_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "word_count",
        re.compile(
            r"\b(?:tepat|persis|maksimal|minimal|setidaknya|paling\s+banyak|under|at\s+most|at\s+least|exactly)\s+\d+\s*(?:kata|words?)\b"
            r"|\b\d+\s*[-–]\s*\d+\s*(?:kata|words?)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "sentence_or_paragraph_count",
        re.compile(
            r"\b(?:tepat|persis|maksimal|minimal|dua|tiga|empat|lima|satu|\d+)\s+(?:sampai\s+\w+\s+)?(?:kalimat|paragraf|sentences?|paragraphs?)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "required_phrase_or_term",
        re.compile(
            r"\b(?:wajib\s+memuat|harus\s+memuat|memuat\s+frasa|sertakan\s+(?:frasa|istilah|contoh)|locks?\s+\w+\s+terms?|preserve\s+every)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "required_docstring_or_format",
        re.compile(
            r"\b(?:docstring\s+bahasa\s+indonesia|tanpa\s+daftar\s+poin|dalam\s+bentuk\s+tabel|table\s+of\s+the|formal\s+business\s+letter|json\s+object)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "forbidden_lexical_or_construct",
        re.compile(
            r"\b(?:dilarang|tidak\s+boleh|tanpa\s+(?:menggunakan\s+)?(?:loop|rekursi|impor|import|sorted|sort|kata|angka|daftar)|remove\s+all\s+blame|must\s+not\s+change|without\s+using)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "ordering_constraint",
        re.compile(
            r"\b(?:sebelum|sesudah|urutan\s+(?:menaik|menurun|fakta|terurut)|terurut\s+berdasarkan|claim\s+first|evidence\s+before|in\s+order\s+of)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "complexity_bound",
        re.compile(r"\bO\s*\([^)]+\)|\bsingle-pass\b|\bkompleksitas\s+(?:waktu|ruang)\b", re.IGNORECASE),
    ),
    (
        "numeric_or_modulo_bound",
        re.compile(
            r"\bmodulo\s*[\d\s_.,]+|\brentang\b|\b1\.\.3999\b|\bYYYY-MM-DD\b|\bdi\s+luar\s+rentang\b",
            re.IGNORECASE,
        ),
    ),
    (
        "edge_case_handling",
        re.compile(
            r"\b(?:kosong|negatif|seri|tie\s+rule|tumpang\s+tindih|bersentuhan|empty\s+input|single\s+interval|unsorted|boundary\s+tests?|degrade\s+gracefully|after\s+the|menangani\s+nilai)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "register_or_language_rule",
        re.compile(
            r"\b(?:bahasa\s+indonesia|indonesian\s+to\s+english|kontradiksi|contradiction|ambiguous|ambigu|disambiguate|attribution|attribute\s+each)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "explicit_constraint_list",
        re.compile(r"\b(?:kendala|constraints?|syarat)\s*:", re.IGNORECASE),
    ),
)

_WHITESPACE_RE = re.compile(r"\s+")


class CandidateCensusError(ValueError):
    """Kesalahan pembacaan berkas masukan atau argumen CLI sensus kandidat."""


def normalize_instruction(text: str) -> str:
    """Normalisasi teks instruksi untuk mendeteksi duplikat identik lintas spasi/huruf."""
    return _WHITESPACE_RE.sub(" ", text.strip()).lower()


def extract_constraints(record: dict[str, Any], instruction: str) -> tuple[int, list[str]]:
    """Hitung jumlah kendala terdeteksi pada satu baris kandidat secara deterministik.

    Jika baris menyertakan struktur kendala eksplisit (`constraints` atau `spec`),
    hitungan mengikuti kunci resmi atau elemen daftar tersebut; bila tidak, pola
    klausul kendala pada teks instruksi dihitung per kategori unik.
    """
    explicit_constraints = record.get("constraints")
    if isinstance(explicit_constraints, list):
        valid = [str(c).strip() for c in explicit_constraints if str(c).strip()]
        return len(valid), [f"explicit:{i}" for i in range(1, len(valid) + 1)]
    if isinstance(explicit_constraints, dict):
        keys = sorted(str(k) for k, v in explicit_constraints.items() if v not in (None, "", [], {}))
        return len(keys), [f"explicit:{k}" for k in keys]

    spec = record.get("spec")
    if isinstance(spec, dict):
        matched_keys = sorted(
            str(k)
            for k, v in spec.items()
            if k in _RECOGNIZED_SPEC_KEYS and v not in (None, "", [], {})
        )
        if matched_keys:
            return len(matched_keys), [f"spec:{k}" for k in matched_keys]

    matched_tags: list[str] = []
    for tag, pattern in _CONSTRAINT_PATTERNS:
        if pattern.search(instruction):
            matched_tags.append(tag)
    return len(matched_tags), matched_tags


def census_lines(
    lines: list[str],
    *,
    source_name: str = "<memory>",
    frozen_prefixes: dict[str, dict[str, Any]] | None = None,
    min_items: int = 1,
    require_episode_schema: bool = True,
) -> dict[str, Any]:
    """Lakukan sensus penuh atas daftar baris JSONL kandidat corpus."""
    active_frozen = frozen_prefixes or {}

    total_lines = len(lines)
    valid_records = 0
    invalid_lines: list[dict[str, Any]] = []
    schema_warnings: list[dict[str, Any]] = []

    task_kind_counts: Counter[str] = Counter()
    kind_counts: Counter[str] = Counter()
    instruction_field_counts: Counter[str] = Counter()

    seen_ids: dict[str, list[int]] = {}
    seen_instructions: dict[str, list[dict[str, Any]]] = {}
    seen_prefix60: dict[str, list[dict[str, Any]]] = {}
    frozen_overlaps: list[dict[str, Any]] = []

    constraint_counts_all: list[int] = []
    constraint_dist_all: Counter[int] = Counter()
    constraint_dist_by_kind: dict[str, Counter[int]] = {}
    zero_constraint_ids: list[str] = []

    for line_no, raw_line in enumerate(lines, start=1):
        stripped = raw_line.strip()
        if not stripped:
            invalid_lines.append({"line": line_no, "reason": "baris kosong"})
            continue

        try:
            obj = json.loads(stripped)
        except json.JSONDecodeError as exc:
            invalid_lines.append({"line": line_no, "reason": f"JSON tidak sah: {exc.msg}"})
            continue

        if not isinstance(obj, dict):
            invalid_lines.append({"line": line_no, "reason": "baris bukan objek JSON"})
            continue

        valid_records += 1

        raw_id = obj.get("id")
        if isinstance(raw_id, str) and raw_id.strip():
            item_id = raw_id.strip()
            seen_ids.setdefault(item_id, []).append(line_no)
        else:
            item_id = f"<line:{line_no}>"
            schema_warnings.append(
                {"line": line_no, "id": item_id, "code": "missing_or_invalid_id", "message": "Field 'id' kosong atau bukan string."}
            )

        raw_kind = obj.get("kind")
        if isinstance(raw_kind, str) and raw_kind.strip():
            kind_counts[raw_kind.strip()] += 1
            if require_episode_schema and raw_kind.strip() != "episode":
                schema_warnings.append(
                    {
                        "line": line_no,
                        "id": item_id,
                        "code": "unexpected_kind",
                        "message": f"Field 'kind' bernilai '{raw_kind.strip()}', bukan 'episode'.",
                    }
                )
        else:
            kind_counts["(missing)"] += 1
            if require_episode_schema:
                schema_warnings.append(
                    {"line": line_no, "id": item_id, "code": "missing_kind", "message": "Field 'kind' tidak ada atau bukan string."}
                )

        raw_tk = obj.get("task_kind")
        if isinstance(raw_tk, str) and raw_tk.strip():
            task_kind = raw_tk.strip()
            task_kind_counts[task_kind] += 1
            if task_kind not in ALLOWED_TASK_KINDS:
                schema_warnings.append(
                    {
                        "line": line_no,
                        "id": item_id,
                        "code": "unexpected_task_kind",
                        "message": f"task_kind '{task_kind}' di luar himpunan baku {sorted(ALLOWED_TASK_KINDS)}.",
                    }
                )
        else:
            task_kind = "(missing)"
            task_kind_counts[task_kind] += 1
            schema_warnings.append(
                {"line": line_no, "id": item_id, "code": "missing_task_kind", "message": "Field 'task_kind' kosong atau bukan string."}
            )

        instruction = ""
        if isinstance(obj.get("instruction"), str) and obj["instruction"].strip():
            instruction = obj["instruction"]
            instruction_field_counts["instruction"] += 1
        elif isinstance(obj.get("prompt"), str) and obj["prompt"].strip():
            instruction = obj["prompt"]
            instruction_field_counts["prompt"] += 1
            if require_episode_schema:
                schema_warnings.append(
                    {
                        "line": line_no,
                        "id": item_id,
                        "code": "nonstandard_instruction_field",
                        "message": "Memakai field 'prompt' alih-alih 'instruction' baku skema corpus episode.",
                    }
                )
        else:
            instruction_field_counts["(missing)"] += 1
            schema_warnings.append(
                {
                    "line": line_no,
                    "id": item_id,
                    "code": "missing_instruction",
                    "message": "Field 'instruction' (dan fallback 'prompt') kosong atau bukan string.",
                }
            )

        if instruction:
            norm_instr = normalize_instruction(instruction)
            seen_instructions.setdefault(norm_instr, []).append({"line": line_no, "id": item_id})
            p60 = instruction[:FROZEN_PREFIX_LEN]
            seen_prefix60.setdefault(p60, []).append({"line": line_no, "id": item_id})
            if p60 in active_frozen:
                frozen_overlaps.append(
                    {
                        "line": line_no,
                        "id": item_id,
                        "frozen_file": active_frozen[p60]["frozen_file"],
                        "frozen_id": active_frozen[p60]["frozen_id"],
                        "frozen_line": active_frozen[p60]["frozen_line"],
                    }
                )

        c_count, _tags = extract_constraints(obj, instruction)
        constraint_counts_all.append(c_count)
        constraint_dist_all[c_count] += 1
        constraint_dist_by_kind.setdefault(task_kind, Counter())[c_count] += 1
        if c_count == 0:
            zero_constraint_ids.append(item_id)

    duplicate_ids = [
        {"id": item_id, "lines": line_list, "count": len(line_list)}
        for item_id, line_list in sorted(seen_ids.items())
        if len(line_list) > 1
    ]
    duplicate_instructions = [
        {
            "preview": norm_text[:100],
            "count": len(entries),
            "occurrences": entries,
        }
        for norm_text, entries in sorted(seen_instructions.items(), key=lambda kv: kv[1][0]["line"])
        if len(entries) > 1
    ]
    prefix60_collisions = [
        {
            "prefix": p60,
            "count": len(entries),
            "occurrences": entries,
        }
        for p60, entries in sorted(seen_prefix60.items(), key=lambda kv: kv[1][0]["line"])
        if len(entries) > 1
    ]

    if constraint_counts_all:
        c_stats = {
            "min": min(constraint_counts_all),
            "max": max(constraint_counts_all),
            "mean": round(statistics.fmean(constraint_counts_all), 3),
            "median": round(float(statistics.median(constraint_counts_all)), 3),
            "zero_constraint_count": len(zero_constraint_ids),
            "zero_constraint_ids": zero_constraint_ids[:20],
        }
    else:
        c_stats = {
            "min": 0,
            "max": 0,
            "mean": 0.0,
            "median": 0.0,
            "zero_constraint_count": 0,
            "zero_constraint_ids": [],
        }

    # Evaluasi kesiapan pembekuan dengan alasan eksplisit.
    blocking_reasons: list[str] = []
    advisory_notes: list[str] = []

    if valid_records == 0:
        blocking_reasons.append("Berkas kosong atau tidak memuat satu pun baris JSON objek yang sah.")
    elif valid_records < min_items:
        blocking_reasons.append(f"Jumlah kandidat valid ({valid_records}) kurang dari batas minimum ({min_items}).")

    if invalid_lines:
        blocking_reasons.append(
            f"Terdapat {len(invalid_lines)} baris tidak sah/kosong (baris pertama bermasalah: {invalid_lines[0]['line']})."
        )

    if duplicate_ids:
        sample_ids = ", ".join(d["id"] for d in duplicate_ids[:5])
        blocking_reasons.append(f"Ditemukan {len(duplicate_ids)} duplikat id ({sample_ids}).")

    if duplicate_instructions:
        sample_lines = ", ".join(
            f"baris {'/'.join(str(o['line']) for o in d['occurrences'])}" for d in duplicate_instructions[:5]
        )
        blocking_reasons.append(
            f"Ditemukan {len(duplicate_instructions)} duplikat instruksi ternormalisasi ({sample_lines})."
        )

    if frozen_overlaps:
        sample_ov = ", ".join(f"{o['id']}->{o['frozen_id']}" for o in frozen_overlaps[:5])
        blocking_reasons.append(
            f"Ditemukan {len(frozen_overlaps)} tumpang tindih awalan 60 karakter dengan corpus beku ({sample_ov})."
        )

    severe_schema_codes = {"missing_or_invalid_id", "missing_instruction", "missing_task_kind", "unexpected_task_kind"}
    severe_schema = [w for w in schema_warnings if w["code"] in severe_schema_codes]
    if severe_schema:
        blocking_reasons.append(
            f"Terdapat {len(severe_schema)} pelanggaran skema wajib (contoh: baris {severe_schema[0]['line']} {severe_schema[0]['code']})."
        )

    compat_schema = [w for w in schema_warnings if w["code"] not in severe_schema_codes]
    if compat_schema:
        blocking_reasons.append(
            f"Terdapat {len(compat_schema)} ketidaksesuaian skema corpus episode baku (contoh: {compat_schema[0]['code']})."
        )

    if zero_constraint_ids:
        blocking_reasons.append(
            f"Terdapat {len(zero_constraint_ids)} kandidat tanpa kendala terdeteksi (risiko soal hampa/tidak diskriminatif)."
        )

    if prefix60_collisions and not duplicate_instructions:
        advisory_notes.append(
            f"Terdapat {len(prefix60_collisions)} benturan awalan 60 karakter antar kandidat meski instruksi lengkap berbeda."
        )

    if len([k for k in task_kind_counts if k in ALLOWED_TASK_KINDS]) == 1 and valid_records > 0:
        only_kind = next(k for k in task_kind_counts if k in ALLOWED_TASK_KINDS)
        advisory_notes.append(
            f"Corpus hanya memuat satu task_kind ('{only_kind}'); pertimbangkan penyeimbangan code/language bila dipakai evaluasi lintas domain."
        )

    ready = len(blocking_reasons) == 0
    verdict = "LAYAK" if ready else "BELUM_LAYAK"
    reasons = (
        ["Seluruh pemeriksaan skema, keunikan id/instruksi, dan keberadaan kendala terpenuhi."]
        if ready
        else blocking_reasons
    )

    return {
        "schema": CENSUS_SCHEMA,
        "source": source_name,
        "total_lines": total_lines,
        "valid_records": valid_records,
        "invalid_line_count": len(invalid_lines),
        "invalid_lines": invalid_lines,
        "task_kind_counts": dict(sorted(task_kind_counts.items())),
        "kind_counts": dict(sorted(kind_counts.items())),
        "instruction_field_counts": dict(sorted(instruction_field_counts.items())),
        "constraint_distribution": {str(k): constraint_dist_all[k] for k in sorted(constraint_dist_all)},
        "constraint_distribution_by_task_kind": {
            tk: {str(k): cnt[k] for k in sorted(cnt)}
            for tk, cnt in sorted(constraint_dist_by_kind.items())
        },
        "constraint_stats": c_stats,
        "duplicates": {
            "duplicate_id_count": len(duplicate_ids),
            "duplicate_ids": duplicate_ids,
            "duplicate_instruction_count": len(duplicate_instructions),
            "duplicate_instructions": duplicate_instructions,
            "prefix60_collision_count": len(prefix60_collisions),
            "prefix60_collisions": prefix60_collisions,
        },
        "frozen_overlap_count": len(frozen_overlaps),
        "frozen_overlaps": frozen_overlaps,
        "schema_warning_count": len(schema_warnings),
        "schema_warnings": schema_warnings[:50],
        "readiness": {
            "ready": ready,
            "verdict": verdict,
            "reasons": reasons,
            "advisory_notes": advisory_notes,
        },
    }


def census_file(
    path: Path,
    *,
    frozen_prefixes: dict[str, dict[str, Any]] | None = None,
    min_items: int = 1,
    require_episode_schema: bool = True,
) -> dict[str, Any]:
    """Baca satu berkas JSONL kandidat dari disk secara baca-saja dan jalankan sensus."""
    if not path.is_file():
        raise CandidateCensusError(f"Berkas kandidat tidak ditemukan: {path}")
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise CandidateCensusError(f"Gagal membaca berkas '{path}': {exc}") from exc
    return census_lines(
        text.splitlines(),
        source_name=str(path),
        frozen_prefixes=frozen_prefixes,
        min_items=min_items,
        require_episode_schema=require_episode_schema,
    )


def render_markdown(reports: list[dict[str, Any]]) -> str:
    """Susun ringkasan sensus dalam format Markdown deterministik."""
    lines = [
        "# Sensus Kandidat Corpus ACE",
        "",
        f"> Dihasilkan secara baca-saja oleh `tools/candidate_census.py` (`{CENSUS_SCHEMA}`).",
        "",
        "| Berkas | Baris Valid | `task_kind` | Sebaran Kendala | Duplikat ID | Duplikat Instruksi | Verdict Kesiapan |",
        "| --- | ---: | --- | --- | ---: | ---: | --- |",
    ]
    for r in reports:
        tk_str = ", ".join(f"{k}:{v}" for k, v in r["task_kind_counts"].items()) or "-"
        cd_str = ", ".join(f"{k}:{v}" for k, v in r["constraint_distribution"].items()) or "-"
        dup = r["duplicates"]
        lines.append(
            f"| `{r['source']}` | {r['valid_records']}/{r['total_lines']} | {tk_str} | {cd_str} "
            f"| {dup['duplicate_id_count']} | {dup['duplicate_instruction_count']} | **{r['readiness']['verdict']}** |"
        )
    lines.append("")
    for r in reports:
        lines.append(f"## `{r['source']}`")
        lines.append("")
        lines.append(f"- **Verdict Kesiapan:** `{r['readiness']['verdict']}`")
        lines.append(
            f"- **Statistik Kendala:** min={r['constraint_stats']['min']}, "
            f"median={r['constraint_stats']['median']}, mean={r['constraint_stats']['mean']}, "
            f"max={r['constraint_stats']['max']}, nol-kendala={r['constraint_stats']['zero_constraint_count']}"
        )
        lines.append("- **Alasan Verdict:**")
        for reason in r["readiness"]["reasons"]:
            lines.append(f"  - {reason}")
        if r["readiness"]["advisory_notes"]:
            lines.append("- **Catatan Tambahan:**")
            for note in r["readiness"]["advisory_notes"]:
                lines.append(f"  - {note}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Sensus berkas kandidat corpus JSONL (task_kind, kendala, duplikat, verdict kesiapan)."
    )
    parser.add_argument("files", nargs="+", help="Satu atau lebih path berkas JSONL kandidat/corpus.")
    parser.add_argument(
        "--frozen",
        action="append",
        default=[],
        help="Path berkas corpus beku pembanding untuk deteksi tumpang tindih awalan 60 karakter (dapat diulang).",
    )
    parser.add_argument("--min-items", type=int, default=1, help="Jumlah kandidat valid minimum agar LAYAK (default: 1).")
    parser.add_argument(
        "--allow-legacy-schema",
        action="store_true",
        help="Terima skema lama (`prompt`/non-episode) tanpa menjadikannya penghambat kesiapan.",
    )
    parser.add_argument(
        "--format",
        choices=("json", "markdown"),
        default="json",
        help="Format keluaran ke stdout (default: json).",
    )
    parser.add_argument("--json-out", help="Tulis laporan JSON lengkap ke path ini.")
    parser.add_argument("--markdown-out", help="Tulis laporan Markdown ke path ini.")
    parser.add_argument(
        "--no-fail-on-not-ready",
        action="store_true",
        help="Tetap keluar dengan exit code 0 meskipun ada berkas berstatus BELUM_LAYAK.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        if args.min_items < 1:
            raise CandidateCensusError("--min-items wajib >= 1.")
        frozen_paths = [Path(p) for p in args.frozen]
        frozen_prefixes = load_frozen_prefixes(frozen_paths) if frozen_paths else {}
        reports = [
            census_file(
                Path(f),
                frozen_prefixes=frozen_prefixes,
                min_items=args.min_items,
                require_episode_schema=not args.allow_legacy_schema,
            )
            for f in args.files
        ]
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    payload: dict[str, Any] = {
        "schema": CENSUS_SCHEMA,
        "file_count": len(reports),
        "ready_count": sum(1 for r in reports if r["readiness"]["ready"]),
        "not_ready_count": sum(1 for r in reports if not r["readiness"]["ready"]),
        "files": reports,
    }
    output_obj: Any = reports[0] if len(reports) == 1 else payload
    md_text = render_markdown(reports)

    if args.json_out:
        out_p = Path(args.json_out)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(json.dumps(output_obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.markdown_out:
        md_p = Path(args.markdown_out)
        md_p.parent.mkdir(parents=True, exist_ok=True)
        md_p.write_text(md_text, encoding="utf-8")

    if args.format == "markdown":
        sys.stdout.write(md_text)
    else:
        sys.stdout.write(json.dumps(output_obj, ensure_ascii=False, indent=2) + "\n")

    if not args.no_fail_on_not_ready and any(not r["readiness"]["ready"] for r in reports):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
