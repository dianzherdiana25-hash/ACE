#!/usr/bin/env python3
"""Pipeline distilasi pola EVO 0007 ke store staging JSONL terpisah.

Membaca keluaran ter-ratifikasi beserta alasan judge dari berkas evidence
(JSONL/JSON/.json.gz) dan menghasilkan catatan `pattern_distilled`
(task_shape memakai kosakata tugas, approach dari output ter-ratifikasi,
pitfalls dari alasan judge, dan provenance lengkap) ke berkas staging JSONL
terpisah. Perkakas ini BUKAN penulis store engine.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from typing import Any

DISTILL_SCHEMA = "ace.pattern-distilled.v1"

_STOPWORDS = frozenset(
    {
        "yang", "dan", "atau", "untuk", "dengan", "pada", "dari", "ke", "di", "dalam",
        "sebagai", "adalah", "akan", "harus", "wajib", "buat", "tulis", "fungsi",
        "berupa", "satu", "dua", "tiga", "tanpa", "serta", "jika", "bila", "agar",
        "tidak", "bukan", "ini", "itu", "oleh", "saat", "tiap", "setiap", "the",
        "and", "for", "with", "that", "this", "from", "into", "your", "must",
        "only", "python", "sertakan", "memuat", "tepat", "kasus",
    }
)

_TOKEN_RE = re.compile(r"[a-zA-Z0-9_]{3,}", re.UNICODE)
_DEF_RE = re.compile(r"^\s*def\s+([a-zA-Z_][a-zA-Z0-9_]*\([^)]*\))", re.MULTILINE)


class PatternDistillError(ValueError):
    """Kesalahan masukan berkas evidence, format JSON, atau argumen CLI."""


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _atomic_write_text(target: Path, content: str) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(f".{target.name}.tmp.{os.getpid()}")
    try:
        tmp.write_text(content, encoding="utf-8")
        os.replace(tmp, target)
    except OSError as exc:
        if tmp.exists():
            tmp.unlink(missing_ok=True)
        raise PatternDistillError(f"Gagal menulis staging store '{target}': {exc}") from exc


def _read_evidence_records(path: Path) -> list[tuple[int, dict[str, Any]]]:
    if not path.is_file():
        raise PatternDistillError(f"Berkas evidence tidak ditemukan: {path}")
    try:
        if path.suffix == ".gz":
            raw_text = gzip.decompress(path.read_bytes()).decode("utf-8")
        else:
            raw_text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError, EOFError, zlib_error_fallback()) as exc:
        raise PatternDistillError(f"Gagal membaca '{path}': {exc}") from exc

    stripped = raw_text.strip()
    if not stripped:
        raise PatternDistillError(f"Berkas evidence kosong: {path}")

    # Cek JSON tunggal (list atau wrapper dict) vs JSONL per baris.
    is_jsonl_ext = path.name.endswith(".jsonl") or path.name.endswith(".jsonl.gz")
    if not is_jsonl_ext and (stripped.startswith("[") or stripped.startswith("{")):
        try:
            payload = json.loads(stripped)
        except (json.JSONDecodeError, ValueError):
            payload = None
        if isinstance(payload, list):
            records: list[tuple[int, dict[str, Any]]] = []
            for idx, item in enumerate(payload, start=1):
                if not isinstance(item, dict):
                    raise PatternDistillError(f"Entri #{idx} pada '{path}' wajib berupa objek JSON.")
                records.append((idx, item))
            return records
        if isinstance(payload, dict):
            for key in ("episodes", "records", "results", "items"):
                if key in payload and isinstance(payload[key], list):
                    records = []
                    for idx, item in enumerate(payload[key], start=1):
                        if not isinstance(item, dict):
                            raise PatternDistillError(
                                f"Entri {key}[{idx - 1}] pada '{path}' wajib berupa objek JSON."
                            )
                        records.append((idx, item))
                    return records
            if any(k in payload for k in ("id", "episode_id", "ratified", "status", "verdict")):
                return [(1, payload)]
            raise PatternDistillError(f"Objek JSON '{path}' tidak memiliki daftar episode yang dikenali.")

    records = []
    for line_no, raw_line in enumerate(raw_text.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except (json.JSONDecodeError, ValueError) as exc:
            raise PatternDistillError(f"JSONL tidak sah pada '{path}' baris {line_no}: {exc}") from exc
        if not isinstance(obj, dict):
            raise PatternDistillError(f"Baris {line_no} pada '{path}' wajib berupa objek JSON.")
        records.append((line_no, obj))
    if not records:
        raise PatternDistillError(f"Tidak ada rekaman JSON ditemukan pada '{path}'.")
    return records


def zlib_error_fallback() -> type[BaseException]:
    import zlib

    return zlib.error


def _is_ratified(rec: dict[str, Any]) -> bool:
    if isinstance(rec.get("ratified"), bool):
        return rec["ratified"]
    for key in ("status", "verdict", "decision"):
        val = rec.get(key)
        if isinstance(val, str) and val.strip().upper() in {"ACCEPTED", "RATIFIED", "PASS", "PASSED"}:
            return True
    return False


def _extract_task_shape(rec: dict[str, Any]) -> dict[str, Any]:
    task_kind = rec.get("task_kind")
    tk = task_kind.strip() if isinstance(task_kind, str) and task_kind.strip() else "unknown"
    text_parts = [
        rec.get(k)
        for k in ("instruction", "prompt", "problem", "title")
        if isinstance(rec.get(k), str) and rec.get(k).strip()
    ]
    combined = " ".join(text_parts)
    tokens: list[str] = []
    seen: set[str] = set()
    for m in _TOKEN_RE.findall(combined.lower()):
        if m in _STOPWORDS or m.isdigit() or m in seen:
            continue
        seen.add(m)
        tokens.append(m)
        if len(tokens) >= 12:
            break

    low = combined.lower()
    constraints: list[str] = []
    checks = (
        ("docstring_id", "docstring bahasa indonesia"),
        ("exact_word_count", "tepat "),
        ("forbidden_words", "dilarang"),
        ("verbatim_phrase", "frasa"),
        ("ordered_facts", "urutan"),
        ("edge_empty", "kosong"),
    )
    for tag, marker in checks:
        if marker in low:
            constraints.append(tag)

    sig_tokens = ",".join(tokens[:6]) if tokens else "generic"
    return {
        "task_kind": tk,
        "signature": f"{tk}:{sig_tokens}",
        "keywords": tokens,
        "constraints_detected": constraints,
    }


def _extract_approach(output_text: str, task_kind: str) -> list[str]:
    steps: list[str] = []
    seen: set[str] = set()

    def add_step(text: str) -> None:
        cleaned = " ".join(text.strip().split())
        if not cleaned or cleaned in seen:
            return
        seen.add(cleaned)
        steps.append(cleaned[:220])

    if task_kind == "code" or "def " in output_text:
        for sig in _DEF_RE.findall(output_text):
            add_step(f"Definisikan fungsi `{sig}` sesuai kontrak parameter.")
        if '"""' in output_text or "'''" in output_text:
            add_step("Sertakan docstring Bahasa Indonesia yang menjelaskan parameter, kembalian, dan kasus tepi.")
        if re.search(r"\bif\s+not\b|\b==\s*0\b|\blen\([^)]*\)\s*==\s*0", output_text):
            add_step("Tangani kasus tepi masukan kosong atau nol secara eksplisit di awal fungsi.")
        if "raise " in output_text:
            add_step("Validasi masukan tak sah dengan exception eksplisit yang konsisten.")

    for line in output_text.splitlines():
        s = line.strip()
        if not s or s.startswith(("def ", "```")):
            continue
        if re.match(r"^(?:[-*]|\d+[.)])\s+", s):
            add_step(re.sub(r"^(?:[-*]|\d+[.)])\s+", "", s))
        elif len(steps) < 5 and len(s) >= 20:
            add_step(s)
        if len(steps) >= 6:
            break

    if not steps:
        add_step("Penuhi seluruh spesifikasi keluaran secara langsung dan ringkas.")
    return steps[:6]


def _extract_pitfalls(reasons_raw: Any, score: float | None, margin: float | None) -> list[str]:
    pitfalls: list[str] = []
    seen: set[str] = set()

    items: list[str] = []
    if isinstance(reasons_raw, list):
        items = [str(r).strip() for r in reasons_raw if str(r).strip()]
    elif isinstance(reasons_raw, str) and reasons_raw.strip():
        items = [seg.strip() for seg in re.split(r"[;\n]+", reasons_raw) if seg.strip()]

    for item in items:
        norm = " ".join(item.split())[:220]
        if norm and norm not in seen:
            seen.add(norm)
            pitfalls.append(norm)
        if len(pitfalls) >= 6:
            break

    if margin is not None and margin <= 10.0:
        note = f"Margin penilaian tipis ({margin:.2f}); periksa ulang kendala tepi agar tidak gagal di judge."
        if note not in seen:
            pitfalls.append(note)
    elif score is not None and score < 80.0:
        note = f"Skor penerimaan pita menengah ({score:.2f}); verifikasi setiap kendala satu per satu."
        if note not in seen:
            pitfalls.append(note)

    if not pitfalls:
        pitfalls.append("Pastikan tidak ada pelanggaran format, tipe keluaran, atau kendala tersurat.")
    return pitfalls[:6]


def _as_optional_float(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        f = float(value)
    except OverflowError:
        return None
    return f if f == f and abs(f) != float("inf") else None


def distill_evidence(
    evidence_paths: list[Path],
    output_path: Path,
    *,
    append: bool = False,
    allow_empty: bool = False,
) -> dict[str, Any]:
    """Distilasi keluaran ter-ratifikasi dari `evidence_paths` ke `output_path` JSONL staging."""
    if not evidence_paths:
        raise PatternDistillError("Minimal satu berkas evidence harus diberikan.")

    existing_records: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, str]] = set()
    if append and output_path.is_file():
        for line_no, raw in enumerate(output_path.read_text(encoding="utf-8").splitlines(), start=1):
            if not raw.strip():
                continue
            try:
                old = json.loads(raw)
            except (json.JSONDecodeError, ValueError) as exc:
                raise PatternDistillError(
                    f"Staging store '{output_path}' baris {line_no} rusak: {exc}"
                ) from exc
            if not isinstance(old, dict):
                raise PatternDistillError(f"Staging store '{output_path}' baris {line_no} bukan objek.")
            existing_records.append(old)
            ep_id = str(old.get("source_episode", ""))
            prov_raw = old.get("provenance")
            prov = prov_raw if isinstance(prov_raw, dict) else {}
            sha = str(prov.get("output_sha256", ""))
            seen_keys.add((ep_id, sha))

    distilled: list[dict[str, Any]] = []
    skipped_unratified = 0
    skipped_incomplete = 0
    skipped_duplicate = 0
    total_records = 0

    for ev_path in evidence_paths:
        entries = _read_evidence_records(ev_path)
        for entry_idx, rec in entries:
            total_records += 1
            if not _is_ratified(rec):
                skipped_unratified += 1
                continue

            ep_id = rec.get("episode_id") or rec.get("id")
            if not isinstance(ep_id, str) or not ep_id.strip():
                skipped_incomplete += 1
                continue
            ep_id = ep_id.strip()

            output_val = None
            for k in ("output", "response", "answer", "candidate", "code"):
                v = rec.get(k)
                if isinstance(v, str) and v.strip():
                    output_val = v
                    break
            if output_val is None:
                skipped_incomplete += 1
                continue

            out_sha = _sha256_text(output_val)
            dedup_key = (ep_id, out_sha)
            if dedup_key in seen_keys:
                skipped_duplicate += 1
                continue
            seen_keys.add(dedup_key)

            shape = _extract_task_shape(rec)
            score = _as_optional_float(rec.get("score"))
            margin = _as_optional_float(rec.get("margin"))
            reasons = rec.get("reasons") or rec.get("judge_reasons") or rec.get("rationale")

            instr_text = next(
                (
                    rec.get(k)
                    for k in ("instruction", "prompt", "problem", "title")
                    if isinstance(rec.get(k), str)
                ),
                "",
            )

            pattern_rec = {
                "schema": DISTILL_SCHEMA,
                "event_class": "pattern_distilled",
                "kind": "semantic",
                "staging_only": True,
                "source_episode": ep_id,
                "task_shape": shape,
                "approach": _extract_approach(output_val, shape["task_kind"]),
                "pitfalls": _extract_pitfalls(reasons, score, margin),
                "provenance": {
                    "evidence_file": str(ev_path),
                    "entry_index": entry_idx,
                    "task_kind": shape["task_kind"],
                    "score": score,
                    "margin": margin,
                    "output_sha256": out_sha,
                    "instruction_sha256": _sha256_text(instr_text),
                },
            }
            distilled.append(pattern_rec)

    if not distilled and not (append and existing_records) and not allow_empty:
        raise PatternDistillError(
            "Tidak ada episode ter-ratifikasi lengkap yang dapat didistilasi menjadi pola."
        )

    all_records = [*existing_records, *distilled] if append else distilled
    serialized = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in all_records)
    _atomic_write_text(output_path, serialized)

    return {
        "schema": DISTILL_SCHEMA,
        "output_staging_store": str(output_path),
        "evidence_files": [str(p) for p in evidence_paths],
        "total_records_read": total_records,
        "distilled_count": len(distilled),
        "total_store_records": len(all_records),
        "skipped_unratified": skipped_unratified,
        "skipped_incomplete": skipped_incomplete,
        "skipped_duplicate": skipped_duplicate,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Pipeline distilasi pola EVO 0007 dari berkas evidence ke staging JSONL terpisah."
    )
    parser.add_argument("evidence", nargs="+", type=Path, help="Berkas evidence JSON/JSONL/.json.gz.")
    parser.add_argument("--output", type=Path, required=True, help="Path store staging JSONL keluaran.")
    parser.add_argument(
        "--append",
        action="store_true",
        help="Tambahkan ke store staging yang sudah ada dengan deduplikasi (source_episode, output_sha256).",
    )
    parser.add_argument(
        "--allow-empty",
        action="store_true",
        help="Izinkan keluar kode 0 walau 0 pola terdistilasi.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
        summary = distill_evidence(
            args.evidence,
            args.output,
            append=args.append,
            allow_empty=args.allow_empty,
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    except SystemExit as exc:
        return 0 if exc.code == 0 else 2
    except (OSError, PatternDistillError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
