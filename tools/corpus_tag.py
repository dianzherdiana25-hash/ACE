#!/usr/bin/env python3
"""Penandaan metadata prediksi pita kesulitan kandidat corpus ACE (WS-B #6).

Membaca berkas kandidat corpus JSONL (`{id, kind, task_kind, instruction}`) dan
satu atau lebih berkas riwayat sensus/screening (JSONL baris hasil ukur atau JSON
sensus teragregasi), lalu menulis berkas metadata terpisah (`ace.corpus-tags.v1`)
berisi prediksi pita kesulitan (`0-39`, `40-44`, `45-75`, `76-100`, atau `unknown`),
estimasi skor rata-rata, tingkat keyakinan, dan jejak fitur pencocokan.

Perkakas ini BERSIFAT READ-ONLY terhadap berkas kandidat corpus: isi berkas
kandidat tidak pernah dimodifikasi.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
from typing import Any

TAG_SCHEMA = "ace.corpus-tags.v1"
SCORE_BANDS = ("0-39", "40-44", "45-75", "76-100")
BAND_LABELS = {
    "0-39": "too_hard",
    "40-44": "borderline_low",
    "45-75": "mid_band_target",
    "76-100": "too_easy",
    "unknown": "insufficient_history",
}

_STOPWORDS = frozenset(
    {
        "yang", "dan", "atau", "untuk", "dengan", "pada", "dari", "ke", "di", "dalam",
        "sebagai", "adalah", "akan", "harus", "wajib", "buat", "tulis", "fungsi",
        "berupa", "satu", "dua", "tiga", "tanpa", "serta", "jika", "bila", "agar",
        "tidak", "bukan", "ini", "itu", "oleh", "saat", "tiap", "setiap", "the",
        "and", "for", "with", "that", "this", "from", "into", "your", "must",
        "only", "python", "sertakan", "docstring", "bahasa", "indonesia", "tepat",
        "kata", "kalimat", "memuat", "dilarang",
    }
)
_WORD_RE = re.compile(r"[a-zA-Z0-9_]{3,}")
_ID_PREFIX_RE = re.compile(r"^([a-zA-Z0-9_-]+?)[0-9]+$")


class CorpusTagError(ValueError):
    """Kesalahan masukan berkas corpus, riwayat sensus, atau parameter CLI."""


def _score_band(score: float) -> str:
    if score < 40.0:
        return "0-39"
    if score < 45.0:
        return "40-44"
    if score <= 75.0:
        return "45-75"
    return "76-100"


def _extract_id_prefix(item_id: str) -> str:
    match = _ID_PREFIX_RE.match(item_id.strip())
    if match:
        return match.group(1)
    return item_id.strip()


def _extract_keywords(text: str) -> set[str]:
    tokens = {tok.lower() for tok in _WORD_RE.findall(text)}
    return {tok for tok in tokens if tok not in _STOPWORDS and not tok.isdigit()}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    if inter == 0:
        return 0.0
    return inter / len(a | b)


def _valid_score(val: Any) -> float | None:
    if isinstance(val, bool) or not isinstance(val, (int, float)):
        return None
    fval = float(val)
    if not math.isfinite(fval) or not (0.0 <= fval <= 100.0):
        return None
    return fval


def _load_candidates(corpus_path: Path) -> tuple[list[dict[str, Any]], str]:
    if not corpus_path.is_file():
        raise CorpusTagError(f"Berkas kandidat corpus tidak ditemukan: {corpus_path}")
    try:
        raw_bytes = corpus_path.read_bytes()
        text = raw_bytes.decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise CorpusTagError(f"Gagal membaca corpus '{corpus_path}': {exc}") from exc

    sha256 = hashlib.sha256(raw_bytes).hexdigest()
    rows: list[dict[str, Any]] = []
    for line_no, raw_line in enumerate(text.splitlines(), start=1):
        if not raw_line.strip():
            continue
        try:
            obj = json.loads(raw_line)
        except json.JSONDecodeError as exc:
            raise CorpusTagError(f"JSON tidak sah di '{corpus_path}' baris {line_no}: {exc.msg}") from exc
        if not isinstance(obj, dict):
            raise CorpusTagError(f"Baris {line_no} pada '{corpus_path}' wajib objek JSON.")
        ep_id = obj.get("id")
        instr = obj.get("instruction")
        if not isinstance(ep_id, str) or not ep_id.strip():
            raise CorpusTagError(f"Baris {line_no} kekurangan string 'id' tidak kosong.")
        if not isinstance(instr, str) or not instr.strip():
            raise CorpusTagError(f"Baris {line_no} kekurangan string 'instruction' tidak kosong.")
        rows.append(
            {
                "id": ep_id,
                "kind": obj.get("kind", "episode"),
                "task_kind": str(obj.get("task_kind", "unknown") or "unknown"),
                "instruction": instr,
            }
        )
    if not rows:
        raise CorpusTagError(f"Berkas corpus '{corpus_path}' kosong.")
    return rows, sha256


def _load_history(history_paths: list[Path]) -> dict[str, Any]:
    if not history_paths:
        raise CorpusTagError("Minimal satu berkas riwayat sensus (`--history`) harus diberikan.")

    by_prefix: dict[str, list[float]] = defaultdict(list)
    by_task_kind: dict[str, list[float]] = defaultdict(list)
    historical_items: list[dict[str, Any]] = []
    # Dukungan band agregat apabila berkas berupa ringkasan sensus `screen_census`.
    aggregate_task_bands: dict[str, Counter[str]] = defaultdict(Counter)

    for path in history_paths:
        if not path.is_file():
            raise CorpusTagError(f"Berkas riwayat tidak ditemukan: {path}")
        try:
            raw_text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise CorpusTagError(f"Gagal membaca riwayat '{path}': {exc}") from exc

        stripped = raw_text.strip()
        if not stripped:
            continue

        # Coba parse sebagai JSON tunggal terlebih dahulu bila dimulai dengan '{' atau '['.
        parsed_rows: list[dict[str, Any]] = []
        if stripped.startswith("{") or stripped.startswith("["):
            try:
                doc = json.loads(stripped)
            except json.JSONDecodeError:
                doc = None
            if isinstance(doc, dict):
                # Cek apakah ini format ringkasan sensus (`by_task_kind` / `prefix_stats` / `episodes`).
                if isinstance(doc.get("by_task_kind"), dict):
                    for kind_name, bucket in doc["by_task_kind"].items():
                        if isinstance(bucket, dict) and isinstance(bucket.get("score_bands"), dict):
                            for b_name, b_cnt in bucket["score_bands"].items():
                                if b_name in SCORE_BANDS and isinstance(b_cnt, int) and not isinstance(b_cnt, bool) and b_cnt > 0:
                                    aggregate_task_bands[str(kind_name)][b_name] += b_cnt
                if isinstance(doc.get("prefix_stats"), dict):
                    for pref, stats in doc["prefix_stats"].items():
                        if isinstance(stats, dict):
                            scores = stats.get("scores")
                            if isinstance(scores, list):
                                for sc in scores:
                                    s_val = _valid_score(sc)
                                    if s_val is not None:
                                        by_prefix[str(pref)].append(s_val)
                            elif _valid_score(stats.get("mean_score")) is not None:
                                s_val = float(stats["mean_score"])
                                count = max(1, int(stats.get("count", 1))) if isinstance(stats.get("count", 1), int) else 1
                                by_prefix[str(pref)].extend([s_val] * min(count, 20))
                if isinstance(doc.get("episodes"), list):
                    parsed_rows.extend([r for r in doc["episodes"] if isinstance(r, dict)])
                elif "id" in doc and ("score" in doc or "ratified" in doc):
                    parsed_rows.append(doc)
            elif isinstance(doc, list):
                parsed_rows.extend([r for r in doc if isinstance(r, dict)])
        if not parsed_rows and not (stripped.startswith("{") and not "\n" in stripped):
            for line_no, raw_line in enumerate(raw_text.splitlines(), start=1):
                if not raw_line.strip():
                    continue
                try:
                    obj = json.loads(raw_line)
                except json.JSONDecodeError:
                    continue
                if isinstance(obj, dict):
                    parsed_rows.append(obj)

        for row in parsed_rows:
            if row.get("error"):
                continue
            score = _valid_score(row.get("score"))
            if score is None:
                ratified = row.get("ratified")
                if isinstance(ratified, bool):
                    score = 85.0 if ratified else 25.0
                else:
                    continue
            ep_id = row.get("id")
            ep_id_str = ep_id.strip() if isinstance(ep_id, str) else ""
            task_kind = str(row.get("task_kind", "unknown") or "unknown")
            by_task_kind[task_kind].append(score)
            if ep_id_str:
                by_prefix[_extract_id_prefix(ep_id_str)].append(score)
            template_name = row.get("template") or row.get("family") or ""
            if isinstance(template_name, str) and template_name.strip():
                by_prefix[template_name.strip()].append(score)
            instr = row.get("instruction")
            if isinstance(instr, str) and instr.strip():
                historical_items.append(
                    {
                        "id": ep_id_str,
                        "task_kind": task_kind,
                        "score": score,
                        "keywords": _extract_keywords(instr),
                    }
                )

    return {
        "by_prefix": by_prefix,
        "by_task_kind": by_task_kind,
        "historical_items": historical_items,
        "aggregate_task_bands": aggregate_task_bands,
    }


def _summarize_scores(scores: list[float]) -> tuple[str, float, dict[str, int]]:
    mean_score = sum(scores) / len(scores)
    band_counts = {b: 0 for b in SCORE_BANDS}
    for s in scores:
        band_counts[_score_band(s)] += 1
    # Pita prediksi ditentukan dari rata-rata historis (sesuai definisi target pita 45-75).
    return _score_band(mean_score), round(mean_score, 2), band_counts


def tag_corpus(
    *,
    corpus_path: Path,
    history_paths: list[Path],
    min_keyword_jaccard: float = 0.2,
) -> dict[str, Any]:
    """Petakan setiap kandidat corpus ke prediksi pita kesulitan historis."""
    if not (0.0 < min_keyword_jaccard <= 1.0):
        raise CorpusTagError("`--min-jaccard` harus berada pada rentang (0, 1].")

    candidates, corpus_sha256 = _load_candidates(corpus_path)
    history = _load_history(history_paths)

    tagged_rows: list[dict[str, Any]] = []
    band_summary: Counter[str] = Counter()
    source_summary: Counter[str] = Counter()

    for cand in candidates:
        ep_id = cand["id"]
        task_kind = cand["task_kind"]
        id_prefix = _extract_id_prefix(ep_id)
        keywords = _extract_keywords(cand["instruction"])

        matched_scores: list[float] = []
        match_source = "none"
        confidence = "none"
        band_counts = {b: 0 for b in SCORE_BANDS}
        predicted_band = "unknown"
        mean_score: float | None = None

        # Tier 1: kecocokan prefix ID / template historis.
        prefix_scores = history["by_prefix"].get(id_prefix)
        if prefix_scores:
            matched_scores = list(prefix_scores)
            predicted_band, mean_score, band_counts = _summarize_scores(matched_scores)
            match_source = "prefix_family"
            confidence = "high" if len(matched_scores) >= 3 else "medium"
        else:
            # Tier 2: kemiripan kata kunci instruksi pada task_kind yang sama.
            similar_scores: list[float] = []
            for hist in history["historical_items"]:
                if hist["task_kind"] != task_kind and hist["task_kind"] != "unknown":
                    continue
                if _jaccard(keywords, hist["keywords"]) >= min_keyword_jaccard:
                    similar_scores.append(hist["score"])

            if similar_scores:
                matched_scores = similar_scores
                predicted_band, mean_score, band_counts = _summarize_scores(matched_scores)
                match_source = "keyword_overlap"
                confidence = "medium" if len(matched_scores) >= 3 else "low"
            else:
                # Tier 3: fallback rata-rata task_kind historis atau ringkasan sensus.
                tk_scores = history["by_task_kind"].get(task_kind)
                if tk_scores:
                    matched_scores = list(tk_scores)
                    predicted_band, mean_score, band_counts = _summarize_scores(matched_scores)
                    match_source = "task_kind_fallback"
                    confidence = "low"
                elif history["aggregate_task_bands"].get(task_kind):
                    agg = history["aggregate_task_bands"][task_kind]
                    band_counts = {b: agg.get(b, 0) for b in SCORE_BANDS}
                    total_agg = sum(band_counts.values())
                    if total_agg > 0:
                        # Pilih pita terbanyak secara deterministik (prioritaskan pita tengah jika seri).
                        predicted_band = max(
                            SCORE_BANDS,
                            key=lambda b: (band_counts[b], b == "45-75"),
                        )
                        match_source = "census_aggregate_fallback"
                        confidence = "low"

        band_summary[predicted_band] += 1
        source_summary[match_source] += 1
        tagged_rows.append(
            {
                "episode_id": ep_id,
                "task_kind": task_kind,
                "predicted_band": predicted_band,
                "band_label": BAND_LABELS[predicted_band],
                "predicted_mean_score": mean_score,
                "confidence": confidence,
                "match_source": match_source,
                "matched_samples": len(matched_scores) if matched_scores else sum(band_counts.values()),
                "historical_band_counts": band_counts,
                "features": {
                    "id_prefix": id_prefix,
                    "top_keywords": sorted(keywords)[:8],
                },
            }
        )

    return {
        "schema": TAG_SCHEMA,
        "corpus": str(corpus_path),
        "corpus_sha256": corpus_sha256,
        "history_files": [str(p) for p in history_paths],
        "total_candidates": len(candidates),
        "summary": {
            "by_predicted_band": {b: band_summary.get(b, 0) for b in (*SCORE_BANDS, "unknown")},
            "by_match_source": dict(sorted(source_summary.items())),
        },
        "tags": tagged_rows,
    }


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    tmp_path.write_text(text, encoding="utf-8")
    os.replace(tmp_path, path)


def _parse_history_args(values: list[str] | None) -> list[Path]:
    if not values:
        return []
    paths: list[Path] = []
    for raw in values:
        for item in raw.split(","):
            cleaned = item.strip()
            if not cleaned:
                raise CorpusTagError("Nilai argumen `--history` tidak boleh kosong.")
            paths.append(Path(cleaned))
    return paths


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Penandaan metadata prediksi pita kesulitan kandidat corpus tanpa mengubah berkas kandidat."
    )
    parser.add_argument("--corpus", required=True, type=Path, help="Path berkas kandidat corpus JSONL (read-only).")
    parser.add_argument(
        "--history",
        action="append",
        required=True,
        help="Path berkas riwayat sensus/screening JSONL atau JSON (bisa diulang/dipisah koma).",
    )
    parser.add_argument("--out", required=True, type=Path, help="Path keluaran metadata terpisah (.json atau .jsonl).")
    parser.add_argument("--format", choices=("json", "jsonl"), default="json", help="Format berkas keluaran metadata.")
    parser.add_argument(
        "--min-jaccard",
        type=float,
        default=0.2,
        help="Ambang minimal Jaccard kata kunci untuk pencocokan teks historis (default: 0.2).",
    )
    args = parser.parse_args(argv)

    try:
        if args.corpus.resolve() == args.out.resolve():
            raise CorpusTagError("Path `--out` tidak boleh sama dengan `--corpus`; metadata wajib terpisah.")
        history_paths = _parse_history_args(args.history)
        report = tag_corpus(
            corpus_path=args.corpus,
            history_paths=history_paths,
            min_keyword_jaccard=args.min_jaccard,
        )
    except CorpusTagError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if args.format == "jsonl":
        content = "\n".join(json.dumps(item, ensure_ascii=False) for item in report["tags"]) + "\n"
    else:
        content = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    _atomic_write_text(args.out, content)

    brief = {
        "schema": report["schema"],
        "total_candidates": report["total_candidates"],
        "summary": report["summary"],
        "out": str(args.out),
    }
    print(json.dumps(brief, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
