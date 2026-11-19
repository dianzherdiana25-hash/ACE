#!/usr/bin/env python3
"""Generator kurikulum EVO 0007 (usulan berdasar celah margin vs pembanding tetap).

Membaca store staging pola terdistilasi (opsional) + sensus gelombang +
kumpulan kandidat episode, lalu menghasilkan dua berkas JSONL dengan format
corpus rumah (`{id, kind, task_kind, instruction}`):
1. Kurikulum usulan: diurutkan menurut celah margin terkecil (pita kritis).
2. Kurikulum tetap pembanding: urutan beku deterministik menurut ID episode.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
import math
import os
from pathlib import Path
import sys
from typing import Any

CURRICULUM_SCHEMA = "ace.curriculum-gen.v1"
DEFAULT_TARGET_SCORE = 60.0


class CurriculumGenError(ValueError):
    """Kesalahan berkas masukan, format JSONL, atau argumen CLI curriculum_gen."""


def _atomic_write_text(target: Path, text: str) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(f".{target.name}.tmp.{os.getpid()}")
    try:
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, target)
    except OSError as exc:
        if tmp.exists():
            tmp.unlink(missing_ok=True)
        raise CurriculumGenError(f"Gagal menulis '{target}': {exc}") from exc


def _read_jsonl_objects(path: Path, label: str) -> list[dict[str, Any]]:
    if not path.is_file():
        raise CurriculumGenError(f"Berkas {label} tidak ditemukan: {path}")
    try:
        raw_text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise CurriculumGenError(f"Gagal membaca {label} '{path}': {exc}") from exc

    rows: list[dict[str, Any]] = []
    for line_no, raw in enumerate(raw_text.splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except (json.JSONDecodeError, ValueError) as exc:
            raise CurriculumGenError(f"JSONL {label} rusak pada '{path}' baris {line_no}: {exc}") from exc
        if not isinstance(obj, dict):
            raise CurriculumGenError(f"Baris {line_no} {label} '{path}' wajib berupa objek JSON.")
        rows.append(obj)
    return rows


def _load_candidates(path: Path) -> list[dict[str, str]]:
    rows = _read_jsonl_objects(path, "kandidat")
    if not rows:
        raise CurriculumGenError(f"Berkas kandidat kosong: {path}")

    seen: set[str] = set()
    normalized: list[dict[str, str]] = []
    for idx, obj in enumerate(rows, start=1):
        ep_id = obj.get("id")
        kind = obj.get("kind")
        task_kind = obj.get("task_kind")
        instruction = obj.get("instruction")
        if (
            not isinstance(ep_id, str)
            or not ep_id.strip()
            or kind != "episode"
            or not isinstance(task_kind, str)
            or task_kind not in ("code", "language")
            or not isinstance(instruction, str)
            or not instruction.strip()
        ):
            raise CurriculumGenError(
                f"Kandidat #{idx} tidak memenuhi schema corpus rumah {{id, kind='episode', task_kind, instruction}}."
            )
        clean_id = ep_id.strip()
        if clean_id in seen:
            raise CurriculumGenError(f"ID kandidat duplikat: {clean_id}")
        seen.add(clean_id)
        normalized.append(
            {
                "id": clean_id,
                "kind": "episode",
                "task_kind": task_kind,
                "instruction": instruction,
            }
        )
    return normalized


def _load_staging_coverage(staging_path: Path | None) -> tuple[set[str], set[str]]:
    if staging_path is None:
        return set(), set()
    rows = _read_jsonl_objects(staging_path, "staging")
    covered_ids: set[str] = set()
    covered_keywords: set[str] = set()
    for obj in rows:
        src = obj.get("source_episode")
        if isinstance(src, str) and src.strip():
            covered_ids.add(src.strip())
        shape = obj.get("task_shape")
        if isinstance(shape, dict):
            raw_kws = shape.get("keywords")
            if isinstance(raw_kws, list):
                for kw in raw_kws:
                    if isinstance(kw, str) and kw.strip():
                        covered_keywords.add(kw.strip().lower())
    return covered_ids, covered_keywords


def _finite_float(val: Any) -> float | None:
    if isinstance(val, bool) or not isinstance(val, (int, float)):
        return None
    try:
        f = float(val)
    except OverflowError:
        return None
    return f if math.isfinite(f) else None


def _load_census_gaps(
    census_path: Path,
    *,
    target_margin: float = 0.0,
    target_score: float = DEFAULT_TARGET_SCORE,
) -> dict[str, float]:
    if not census_path.is_file():
        raise CurriculumGenError(f"Berkas sensus tidak ditemukan: {census_path}")
    try:
        raw_text = census_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise CurriculumGenError(f"Gagal membaca sensus '{census_path}': {exc}") from exc

    stripped = raw_text.strip()
    if not stripped:
        raise CurriculumGenError(f"Berkas sensus kosong: {census_path}")

    entries: list[dict[str, Any]] = []
    if stripped.startswith("{") and "\n" not in stripped.lstrip("{}")[:2]:
        try:
            single = json.loads(stripped)
        except (json.JSONDecodeError, ValueError):
            single = None
    else:
        try:
            single = json.loads(stripped)
        except (json.JSONDecodeError, ValueError):
            single = None

    if isinstance(single, dict):
        if isinstance(single.get("episodes"), list):
            entries = [e for e in single["episodes"] if isinstance(e, dict)]
        elif isinstance(single.get("records"), list):
            entries = [e for e in single["records"] if isinstance(e, dict)]
        elif "id" in single:
            entries = [single]
        else:
            raise CurriculumGenError("Objek JSON sensus wajib memuat 'episodes', 'records', atau 'id'.")
    elif isinstance(single, list):
        entries = [e for e in single if isinstance(e, dict)]
    else:
        entries = _read_jsonl_objects(census_path, "sensus")

    gaps_by_id: dict[str, list[float]] = defaultdict(list)
    for row in entries:
        ep_id = row.get("id") or row.get("episode_id")
        if not isinstance(ep_id, str) or not ep_id.strip():
            continue
        ep_key = ep_id.strip()
        margin = _finite_float(row.get("margin"))
        if margin is not None:
            gaps_by_id[ep_key].append(abs(margin - target_margin))
            continue
        score = _finite_float(row.get("score"))
        if score is not None:
            gaps_by_id[ep_key].append(abs(score - target_score))

    return {ep_id: min(vals) for ep_id, vals in gaps_by_id.items()}


def generate_curricula(
    *,
    candidates_path: Path,
    census_path: Path,
    proposed_out: Path,
    baseline_out: Path,
    staging_path: Path | None = None,
    target_margin: float = 0.0,
    target_score: float = DEFAULT_TARGET_SCORE,
    limit: int | None = None,
) -> dict[str, Any]:
    """Hasilkan dua berkas kurikulum JSONL (usulan celah margin + pembanding beku)."""
    if limit is not None and limit < 1:
        raise CurriculumGenError("Nilai --limit harus >= 1.")

    candidates = _load_candidates(candidates_path)
    covered_ids, _ = _load_staging_coverage(staging_path)
    gaps = _load_census_gaps(census_path, target_margin=target_margin, target_score=target_score)

    def proposed_key(item: dict[str, str]) -> tuple[int, float, int, str]:
        ep_id = item["id"]
        has_gap = 0 if ep_id in gaps else 1
        gap_val = gaps.get(ep_id, float("inf"))
        already_covered = 1 if ep_id in covered_ids else 0
        return (has_gap, gap_val, already_covered, ep_id)

    proposed_sorted = sorted(candidates, key=proposed_key)
    baseline_sorted = sorted(candidates, key=lambda item: item["id"])

    if limit is not None:
        proposed_sorted = proposed_sorted[:limit]
        baseline_sorted = baseline_sorted[:limit]

    _atomic_write_text(
        proposed_out,
        "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in proposed_sorted),
    )
    _atomic_write_text(
        baseline_out,
        "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in baseline_sorted),
    )

    proposed_ids = [item["id"] for item in proposed_sorted]
    baseline_ids = [item["id"] for item in baseline_sorted]

    return {
        "schema": CURRICULUM_SCHEMA,
        "candidate_count": len(candidates),
        "emitted_count": len(proposed_sorted),
        "census_matched_count": sum(1 for item in candidates if item["id"] in gaps),
        "staging_covered_count": sum(1 for item in candidates if item["id"] in covered_ids),
        "proposed_out": str(proposed_out),
        "baseline_out": str(baseline_out),
        "order_differs": proposed_ids != baseline_ids,
        "proposed_top_ids": proposed_ids[:5],
        "baseline_top_ids": baseline_ids[:5],
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generator kurikulum usulan (celah margin) vs kurikulum pembanding tetap (format corpus rumah)."
    )
    parser.add_argument("--candidates", type=Path, required=True, help="Berkas kandidat corpus JSONL.")
    parser.add_argument("--census", type=Path, required=True, help="Berkas hasil sensus/gelombang JSON atau JSONL.")
    parser.add_argument("--staging", type=Path, default=None, help="Opsional berkas staging pattern_distilled JSONL.")
    parser.add_argument("--proposed-out", type=Path, required=True, help="Path berkas JSONL kurikulum usulan.")
    parser.add_argument("--baseline-out", type=Path, required=True, help="Path berkas JSONL kurikulum pembanding tetap.")
    parser.add_argument("--target-margin", type=float, default=0.0, help="Target margin ideal untuk celah (default: 0.0).")
    parser.add_argument("--target-score", type=float, default=DEFAULT_TARGET_SCORE, help="Target skor pita tengah bila margin absen (default: 60.0).")
    parser.add_argument("--limit", type=int, default=None, help="Batasi jumlah episode pada masing-masing kurikulum.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
        summary = generate_curricula(
            candidates_path=args.candidates,
            census_path=args.census,
            proposed_out=args.proposed_out,
            baseline_out=args.baseline_out,
            staging_path=args.staging,
            target_margin=args.target_margin,
            target_score=args.target_score,
            limit=args.limit,
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    except SystemExit as exc:
        return 0 if exc.code == 0 else 2
    except (OSError, CurriculumGenError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
