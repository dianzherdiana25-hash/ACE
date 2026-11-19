#!/usr/bin/env python3
"""Linter korpus generasi berikut: skema + kendala mekanis + duplikat lintas berkas (Garis B3).

Pemeriksaan dalam satu lintasan:
1. **Skema**: JSON objek valid tanpa kunci duplikat; field tepat
   `{id, kind, task_kind, instruction}` bertipe string tidak kosong;
   `kind == "episode"`, `task_kind in {"code", "language"}`; kode wajib
   memuat `"docstring Bahasa Indonesia"`.
2. **Kendala mekanis** (opsional lewat `--lang-specs`, `--lang-samples-dir`,
   dan `--code-specs`): memverifikasi konsistensi internal spesifikasi kendala
   (mis. frasa wajib tidak memuat akar kata terlarang, urutan fakta tidak
   kembar) + kecocokan teks instruksi + sampel bahasa terhadap
   `verify_layered_lang_spec` atau `verify_composite_code_spec`.
3. **Duplikat lintas berkas**: menolak ID ganda lintas berkas, duplikat
   instruksi ternormalisasi, benturan awalan 60-karakter lintas berkas maupun
   terhadap berkas `--frozen`, serta kemiripan dekat (Jaccard token >= ambang).

Exit code:
- 0: bersih (tidak ada pelanggaran)
- 1: ditemukan pelanggaran
- 2: argumen/berkas pendukung tidak dapat dibaca
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
from typing import Any

from tools.corpus_lint import FROZEN_PREFIX_LEN, REQUIRED_CODE_PHRASE, REQUIRED_FIELDS, ALLOWED_TASK_KINDS

LINT_V2_SCHEMA = "ace.corpus-lint-v2.v1"
_TOKEN_RE = re.compile(r"[0-9a-zA-ZÀ-ÖØ-öø-ÿ_]+")
_WORD_RE = re.compile(r"[0-9A-Za-zÀ-ÖØ-öø-ÿ]+(?:[-'][0-9A-Za-zÀ-ÖØ-öø-ÿ]+)*")
_SENTENCE_SPLIT_RE = re.compile(r"[.!?]+(?:\s+|$)")
_ID_PREFIXES = ("", "me", "mem", "men", "meng", "meny", "di", "ber", "be", "ter", "te", "pe", "pem", "pen", "peng", "peny", "per", "ke", "se")
_ID_SUFFIXES = ("", "kan", "an", "i", "nya", "lah", "kah")
_MULTI_INFLECTIONS = {
    "en": ("", "s", "es", "ed", "ing", "er", "ly"),
    "es": ("", "s", "es", "o", "a", "os", "as", "ado", "ada"),
    "de": ("", "e", "en", "er", "es", "te", "ten", "ung"),
    "fr": ("", "s", "e", "es", "er", "é", "ée", "ment"),
}


class CorpusLintV2Error(ValueError):
    """Kesalahan argumen CLI atau berkas masukan pendukung yang tidak dapat dibaca."""


def _expand_forbidden_forms(root: str, language: str) -> set[str]:
    clean = root.strip().lower()
    if not clean:
        return set()
    if language == "id":
        stems = {clean}
        if len(clean) > 2 and clean[0] in {"k", "p", "t", "s"}:
            stems.add(clean[1:])
        return {
            f"{p}{s}{u}"
            for p in _ID_PREFIXES
            for s in stems
            for u in _ID_SUFFIXES
            if s == clean or any(p.endswith(npf) for npf in ("me", "mem", "men", "meng", "meny", "pe", "pem", "pen", "peng", "peny"))
        }
    return {f"{clean}{s}" for s in _MULTI_INFLECTIONS.get(language, ("", "s"))}


_RECOGNIZED_LANG_SPEC_KEYS = frozenset(
    {
        "word_count",
        "sentence_count",
        "required_phrases",
        "forbidden_words",
        "forbidden_roots",
        "forbidden_affix_roots",
        "required_order",
        "surface_hygiene",
    }
)
_RECOGNIZED_LANG_LAYERS = frozenset(
    {
        "word_count",
        "sentence_count",
        "required_phrases",
        "forbidden_words",
        "required_order",
        "surface_hygiene",
    }
)


def _check_layered_lang_sample(text: str, spec: dict[str, Any]) -> list[str]:
    if not text.strip():
        return ["empty_sample"]
    if not isinstance(spec, dict) or not any(k in _RECOGNIZED_LANG_SPEC_KEYS for k in spec):
        return ["vacuous_spec:no_recognized_constraint_keys"]
    active = list(spec.get("active_layers") or ["word_count", "sentence_count", "required_phrases", "forbidden_words", "required_order"])
    if not (set(active) & _RECOGNIZED_LANG_LAYERS):
        return ["vacuous_spec:no_recognized_active_layers"]
    lang = str(spec.get("language", "id")).strip().lower() or "id"
    words = _WORD_RE.findall(text)
    sentences = [p.strip() for p in _SENTENCE_SPLIT_RE.split(text.strip()) if p.strip()]
    failed: list[str] = []

    if "word_count" in active:
        exp_wc = (spec.get("word_count") or {}).get("exact")
        if isinstance(exp_wc, int) and len(words) != exp_wc:
            failed.append("word_count")
    if "sentence_count" in active:
        exp_sc = (spec.get("sentence_count") or {}).get("exact")
        if isinstance(exp_sc, int) and len(sentences) != exp_sc:
            failed.append("sentence_count")
    if "required_phrases" in active:
        if any(p not in text for p in (spec.get("required_phrases") or [])):
            failed.append("required_phrases")
    if "forbidden_words" in active:
        roots = [str(r) for r in (spec.get("forbidden_roots") or spec.get("forbidden_affix_roots") or [])]
        expanded = {str(w).lower() for w in (spec.get("forbidden_words") or [])}
        for r in roots:
            expanded.update(_expand_forbidden_forms(r, lang))
        if any(w.lower() in expanded for w in words):
            failed.append("forbidden_words")
    if "required_order" in active:
        seq = list(spec.get("required_order") or [])
        last = -1
        for fact in seq:
            pos = text.find(str(fact))
            if pos < 0 or pos <= last:
                failed.append("required_order")
                break
            last = pos
    if "surface_hygiene" in active:
        hyg = spec.get("surface_hygiene") or {}
        if hyg.get("forbid_digits", True) and re.search(r"[0-9]", text):
            failed.append("surface_hygiene:digits")
        tok = str(hyg.get("closing_token", "")).strip()
        if tok and not text.rstrip().endswith(tok):
            failed.append("surface_hygiene:closing_token")
    return failed


def _check_composite_code_instruction(episode: dict[str, Any], spec: dict[str, Any]) -> bool:
    instr = str(episode.get("instruction", ""))
    req = [
        str(spec.get("algorithm", "")).strip(),
        str(spec.get("complexity_time", "")).strip(),
        str(spec.get("complexity_space", "")).strip(),
        str(spec.get("exact_signature", "")).strip(),
        str(spec.get("exact_return_format", "")).strip(),
    ]
    banned = [str(t).strip() for t in (spec.get("forbidden_tools") or []) if str(t).strip()]
    if any(not x for x in req) or not banned:
        return False
    return all(x in instr for x in req) and all(t in instr for t in banned) and REQUIRED_CODE_PHRASE in instr


def _normalize_text(text: str) -> str:
    return " ".join(text.casefold().split())


def _token_shingles(text: str) -> set[str]:
    tokens = _TOKEN_RE.findall(text.casefold())
    if len(tokens) < 3:
        return set(tokens)
    return {f"{tokens[i]} {tokens[i+1]} {tokens[i+2]}" for i in range(len(tokens) - 2)}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _unique_json_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in pairs:
        if k in out:
            raise ValueError(f"kunci JSON duplikat: {k}")
        out[k] = v
    return out


def _load_specs_map(path: Path | None) -> dict[str, dict[str, Any]]:
    if path is None:
        return {}
    if not path.is_file():
        raise CorpusLintV2Error(f"Berkas spesifikasi tidak ditemukan: {path}")
    specs: dict[str, dict[str, Any]] = {}
    for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw.strip():
            continue
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise CorpusLintV2Error(f"JSON spesifikasi tidak sah '{path}' baris {line_no}: {exc}") from exc
        if not isinstance(obj, dict) or not isinstance(obj.get("episode_id"), str) or not obj["episode_id"].strip():
            raise CorpusLintV2Error(f"Spesifikasi '{path}' baris {line_no} wajib memuat 'episode_id' string.")
        ep_id = obj["episode_id"].strip()
        if ep_id in specs:
            raise CorpusLintV2Error(f"Duplicate episode_id '{ep_id}' dalam '{path}'.")
        specs[ep_id] = obj
    return specs


def _load_frozen_entries(frozen_paths: list[Path]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for path in frozen_paths:
        if not path.is_file():
            raise CorpusLintV2Error(f"Berkas korpus beku tidak ditemukan: {path}")
        try:
            raw_text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise CorpusLintV2Error(f"Gagal membaca korpus beku '{path}': {exc}") from exc
        for line_no, raw in enumerate(raw_text.splitlines(), start=1):
            if not raw.strip():
                raise CorpusLintV2Error(f"Baris kosong pada korpus beku '{path}' baris {line_no}.")
            try:
                obj = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise CorpusLintV2Error(f"JSON korpus beku tidak sah '{path}' baris {line_no}: {exc}") from exc
            if not isinstance(obj, dict):
                raise CorpusLintV2Error(f"Baris '{path}' baris {line_no} wajib objek.")
            prompt_text = obj.get("instruction") if isinstance(obj.get("instruction"), str) else obj.get("prompt")
            if not isinstance(prompt_text, str) or not prompt_text.strip():
                raise CorpusLintV2Error(f"Baris korpus beku '{path}' baris {line_no} tanpa field 'instruction'/'prompt'.")
            norm = _normalize_text(prompt_text)
            entries.append(
                {
                    "file": str(path),
                    "line": line_no,
                    "id": str(obj.get("id", "")),
                    "prefix60": norm[:FROZEN_PREFIX_LEN],
                    "norm": norm,
                    "shingles": _token_shingles(norm),
                }
            )
    return entries


def lint_corpus_files_v2(
    corpus_paths: list[Path],
    *,
    lang_specs_path: Path | None = None,
    lang_samples_dir: Path | None = None,
    code_specs_path: Path | None = None,
    frozen_paths: list[Path] | None = None,
    near_dup_threshold: float = 0.85,
) -> dict[str, Any]:
    """Jalankan lint skema, kendala mekanis, dan duplikat lintas berkas."""
    if not corpus_paths:
        raise CorpusLintV2Error("Minimal satu berkas korpus harus diberikan.")
    if not (0.0 < near_dup_threshold <= 1.0):
        raise CorpusLintV2Error("--near-dup-threshold wajib berada pada (0.0, 1.0].")
    if lang_samples_dir is not None and not lang_samples_dir.is_dir():
        raise CorpusLintV2Error(f"Direktori sampel bahasa tidak ditemukan: {lang_samples_dir}")

    lang_specs = _load_specs_map(lang_specs_path)
    code_specs = _load_specs_map(code_specs_path)
    frozen_entries = _load_frozen_entries(frozen_paths or [])
    frozen_by_prefix = {e["prefix60"]: e for e in frozen_entries if e["prefix60"]}

    violations: list[dict[str, Any]] = []
    seen_ids: dict[str, tuple[str, int]] = {}
    seen_norms: dict[str, tuple[str, int, str]] = {}
    seen_prefixes: dict[str, tuple[str, int, str]] = {}
    corpus_records: list[dict[str, Any]] = []
    file_summaries: list[dict[str, Any]] = []

    def add_violation(file_name: str, line_no: int, code: str, message: str, item_id: str = "") -> None:
        violations.append(
            {
                "file": file_name,
                "line": line_no,
                "id": item_id,
                "code": code,
                "message": message,
            }
        )

    for cpath in corpus_paths:
        if not cpath.is_file():
            raise CorpusLintV2Error(f"Berkas korpus tidak ditemukan: {cpath}")
        raw_text = cpath.read_text(encoding="utf-8")
        raw_lines = raw_text.splitlines()
        if not raw_lines:
            add_violation(str(cpath), 0, "empty_corpus", "Berkas korpus kosong.")
            file_summaries.append({"file": str(cpath), "lines": 0})
            continue

        file_summaries.append({"file": str(cpath), "lines": len(raw_lines)})
        for line_no, raw_line in enumerate(raw_lines, start=1):
            if not raw_line.strip():
                add_violation(str(cpath), line_no, "empty_line", "Baris kosong tidak diizinkan.")
                continue
            try:
                obj = json.loads(raw_line, object_pairs_hook=_unique_json_pairs)
            except (json.JSONDecodeError, ValueError) as exc:
                add_violation(str(cpath), line_no, "invalid_json", f"JSON tidak sah: {exc}")
                continue
            if not isinstance(obj, dict):
                add_violation(str(cpath), line_no, "non_dict_row", "Baris harus berupa objek JSON.")
                continue

            raw_id = obj.get("id")
            item_id = raw_id.strip() if isinstance(raw_id, str) and raw_id.strip() else ""
            missing = sorted(REQUIRED_FIELDS - set(obj.keys()))
            extra = sorted(set(obj.keys()) - REQUIRED_FIELDS)
            if missing or extra:
                add_violation(
                    str(cpath),
                    line_no,
                    "schema_mismatch",
                    f"Field skema tidak cocok (missing={missing}, extra={extra}).",
                    item_id,
                )
                continue

            bad_types = [k for k in REQUIRED_FIELDS if not isinstance(obj[k], str) or not obj[k].strip()]
            if bad_types:
                add_violation(
                    str(cpath),
                    line_no,
                    "invalid_field_value",
                    f"Field wajib string non-kosong: {bad_types}.",
                    item_id,
                )
                continue

            if obj["kind"] != "episode":
                add_violation(str(cpath), line_no, "invalid_kind", f"kind wajib 'episode', dapat '{obj['kind']}'.", item_id)
            if obj["task_kind"] not in ALLOWED_TASK_KINDS:
                add_violation(str(cpath), line_no, "invalid_task_kind", f"task_kind tidak valid: '{obj['task_kind']}'.", item_id)

            instr = obj["instruction"]
            if obj["task_kind"] == "code" and REQUIRED_CODE_PHRASE not in instr:
                add_violation(
                    str(cpath),
                    line_no,
                    "missing_code_docstring_req",
                    f"Episode kode wajib memuat '{REQUIRED_CODE_PHRASE}'.",
                    item_id,
                )

            # Lintas berkas: ID duplikat, instruksi persis, awalan 60 karakter, korpus beku, dan kemiripan dekat.
            if item_id in seen_ids:
                prev_f, prev_l = seen_ids[item_id]
                add_violation(
                    str(cpath),
                    line_no,
                    "cross_file_duplicate_id" if prev_f != str(cpath) else "duplicate_id",
                    f"ID '{item_id}' ganda dengan {prev_f}:{prev_l}.",
                    item_id,
                )
            else:
                seen_ids[item_id] = (str(cpath), line_no)

            norm = _normalize_text(instr)
            prefix60 = norm[:FROZEN_PREFIX_LEN]
            if norm in seen_norms:
                pf, pl, pid = seen_norms[norm]
                add_violation(
                    str(cpath),
                    line_no,
                    "cross_file_duplicate_instruction" if pf != str(cpath) else "duplicate_instruction",
                    f"Instruksi persis duplikat dengan {pid} di {pf}:{pl}.",
                    item_id,
                )
            else:
                seen_norms[norm] = (str(cpath), line_no, item_id)

            if prefix60 in seen_prefixes:
                pf, pl, pid = seen_prefixes[prefix60]
                add_violation(
                    str(cpath),
                    line_no,
                    "cross_file_prefix60_collision" if pf != str(cpath) else "prefix60_collision",
                    f"Awalan 60 karakter berbenturan dengan {pid} di {pf}:{pl}.",
                    item_id,
                )
            else:
                seen_prefixes[prefix60] = (str(cpath), line_no, item_id)

            if prefix60 in frozen_by_prefix:
                finfo = frozen_by_prefix[prefix60]
                add_violation(
                    str(cpath),
                    line_no,
                    "frozen_corpus_collision",
                    f"Awalan 60 karakter tumpang tindih dengan korpus beku {finfo['file']}:{finfo['line']} ({finfo['id']}).",
                    item_id,
                )

            shingles = _token_shingles(norm)
            for prev in corpus_records:
                sim = _jaccard(shingles, prev["shingles"])
                if sim >= near_dup_threshold and norm != prev["norm"]:
                    add_violation(
                        str(cpath),
                        line_no,
                        "cross_file_near_duplicate" if prev["file"] != str(cpath) else "near_duplicate_instruction",
                        f"Kemiripan Jaccard={sim:.2f} >= {near_dup_threshold} dengan {prev['id']} ({prev['file']}:{prev['line']}).",
                        item_id,
                    )
            for froz in frozen_entries:
                sim = _jaccard(shingles, froz["shingles"])
                if sim >= near_dup_threshold:
                    add_violation(
                        str(cpath),
                        line_no,
                        "frozen_near_duplicate",
                        f"Kemiripan Jaccard={sim:.2f} dengan korpus beku {froz['id']} ({froz['file']}:{froz['line']}).",
                        item_id,
                    )

            corpus_records.append(
                {"file": str(cpath), "line": line_no, "id": item_id, "norm": norm, "shingles": shingles}
            )

            # Lapis 2: Kendala mekanis dari sidecar + sampel jika tersedia.
            if obj["task_kind"] == "language" and item_id in lang_specs:
                spec = lang_specs[item_id]
                req_phrases = [str(p) for p in (spec.get("required_phrases") or [])]
                roots = [str(r).lower() for r in (spec.get("forbidden_roots") or spec.get("forbidden_affix_roots") or [])]
                order = [str(f) for f in (spec.get("required_order") or [])]
                if len(order) >= 2 and len(set(order)) != len(order):
                    add_violation(str(cpath), line_no, "contradictory_order_constraint", "Fakta berurutan memuat entri identik.", item_id)
                for ph in req_phrases:
                    ph_tokens = set(_TOKEN_RE.findall(ph.lower()))
                    if ph_tokens & set(roots):
                        add_violation(
                            str(cpath),
                            line_no,
                            "contradictory_phrase_forbidden_root",
                            f"Frasa wajib '{ph}' mengandung akar kata terlarang.",
                            item_id,
                        )
                active_layers = spec.get("active_layers") or ["word_count", "sentence_count", "required_phrases", "forbidden_words", "required_order"]
                if "required_phrases" in active_layers:
                    for ph in req_phrases:
                        if ph not in instr:
                            add_violation(str(cpath), line_no, "instruction_missing_required_phrase", f"Instruksi tidak mencantumkan frasa wajib '{ph}'.", item_id)
                if lang_samples_dir is not None:
                    sample_file = lang_samples_dir / f"{item_id}.txt"
                    if not sample_file.is_file():
                        add_violation(str(cpath), line_no, "missing_lang_sample", f"Berkas sampel tidak ada: {sample_file}", item_id)
                    else:
                        sample_text = sample_file.read_text(encoding="utf-8").strip()
                        spec_eval = dict(spec)
                        if "active_layers" not in spec_eval:
                            spec_eval["active_layers"] = active_layers
                        if "forbidden_roots" not in spec_eval and "forbidden_affix_roots" in spec_eval:
                            spec_eval["forbidden_roots"] = spec_eval["forbidden_affix_roots"]
                        failed_checks = _check_layered_lang_sample(sample_text, spec_eval)
                        if failed_checks:
                            add_violation(str(cpath), line_no, "sample_constraint_failed", f"Sampel gagal cek mekanis: {sorted(failed_checks)}", item_id)

            elif obj["task_kind"] == "code" and item_id in code_specs:
                cspec = code_specs[item_id]
                if not _check_composite_code_instruction(obj, cspec):
                    add_violation(
                        str(cpath),
                        line_no,
                        "code_composite_constraint_mismatch",
                        "Instruksi kode tidak selaras dengan spec komposit.",
                        item_id,
                    )

    return {
        "schema": LINT_V2_SCHEMA,
        "valid": len(violations) == 0,
        "files": file_summaries,
        "episodes_checked": len(corpus_records),
        "violation_count": len(violations),
        "violations": violations,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Linter korpus generasi berikut (skema + mekanis + lintas berkas).")
    parser.add_argument("corpora", nargs="+", type=Path, help="Satu atau lebih berkas JSONL korpus.")
    parser.add_argument("--lang-specs", type=Path, help="Sidecar JSONL spesifikasi bahasa.")
    parser.add_argument("--lang-samples-dir", type=Path, help="Direktori berkas sampel jawaban bahasa (*.txt).")
    parser.add_argument("--code-specs", type=Path, help="Sidecar JSONL spesifikasi kode komposit.")
    parser.add_argument("--frozen", action="append", type=Path, default=[], help="Berkas korpus beku anti-duplikat.")
    parser.add_argument("--near-dup-threshold", type=float, default=0.85, help="Ambang Jaccard near-duplicate.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        report = lint_corpus_files_v2(
            args.corpora,
            lang_specs_path=args.lang_specs,
            lang_samples_dir=args.lang_samples_dir,
            code_specs_path=args.code_specs,
            frozen_paths=args.frozen or None,
            near_dup_threshold=args.near_dup_threshold,
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["valid"] else 1
    except CorpusLintV2Error as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
