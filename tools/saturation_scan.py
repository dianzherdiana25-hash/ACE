#!/usr/bin/env python3
"""Analisis kejenuhan judge atas JSONL hasil saring/ukur ACE (Garis B2).

Membaca satu atau lebih berkas JSONL/JSON/.json.gz hasil saring atau ukur
untuk mendeteksi:
1. Pasangan tugas jenuh (`always_pass` / semua lolos dan `always_fail` /
   semua gagal pada pengamatan berulang).
2. Pita skor yang berhenti membedakan (konsentrasi tinggi dengan rasio
   pembeda/split sangat rendah, keseragaman putusan 0%/100%, atau rentang
   skor intra-pasangan hampir nol).
3. Rekomendasi pensiun / pengerasan / kalibrasi ulang per kelompok tugas.

Perkakas ini baca-saja dan BUKAN instrumen verdict/scorer.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import gzip
import json
import math
import os
from pathlib import Path
import re
import sys
import zlib
from typing import Any

SATURATION_SCHEMA = "ace.judge-saturation-scan.v1"

SCORE_BANDS: tuple[str, ...] = ("0-39", "40-44", "45-75", "76-100")
DECILE_BANDS: tuple[str, ...] = (
    "0-9", "10-19", "20-29", "30-39", "40-49",
    "50-59", "60-69", "70-79", "80-89", "90-100",
)

_ID_PREFIX_GROUP_RE = re.compile(r"^([a-zA-Z]+(?:[_-][a-zA-Z]+)*?)[_-]?\d+$")


class SaturationScanError(ValueError):
    """Kesalahan berkas masukan, format JSON, atau argumen CLI saturation_scan."""


def _is_valid_score(value: Any) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        numeric = float(value)
    except (OverflowError, TypeError, ValueError):
        return False
    return math.isfinite(numeric) and 0.0 <= numeric <= 100.0


def _score_band(score: float) -> str:
    if score < 40.0:
        return "0-39"
    if score < 45.0:
        return "40-44"
    if score <= 75.0:
        return "45-75"
    return "76-100"


def _decile_band(score: float) -> str:
    if score >= 90.0:
        return "90-100"
    idx = min(8, max(0, int(score // 10)))
    return DECILE_BANDS[idx]


def _extract_ratified(obj: dict[str, Any]) -> bool | None:
    if "ratified" in obj and obj["ratified"] is not None:
        if isinstance(obj["ratified"], bool):
            return obj["ratified"]
        return None
    validator = obj.get("validator")
    if isinstance(validator, dict):
        parsed = validator.get("parsed")
        if isinstance(parsed, dict) and isinstance(parsed.get("accept"), bool):
            return parsed["accept"]
    for key in ("passed", "accept"):
        if isinstance(obj.get(key), bool):
            return obj[key]
    for key in ("status", "verdict", "decision"):
        val = obj.get(key)
        if isinstance(val, str):
            upper = val.strip().upper()
            if upper in {"RATIFY", "RATIFIED", "PASS", "PASSED", "ACCEPT", "ACCEPTED"}:
                return True
            if upper in {"REJECT", "REJECTED", "FAIL", "FAILED"}:
                return False
    return None


def _extract_score(obj: dict[str, Any]) -> tuple[bool, float | None]:
    for key in ("score", "judge_score"):
        if key in obj and obj[key] is not None:
            raw = obj[key]
            if not _is_valid_score(raw):
                return False, None
            return True, float(raw)
    validator = obj.get("validator")
    if isinstance(validator, dict):
        parsed = validator.get("parsed")
        if isinstance(parsed, dict) and "score" in parsed and parsed["score"] is not None:
            raw = parsed["score"]
            if not _is_valid_score(raw):
                return False, None
            return True, float(raw)
    return True, None


def _resolve_group(obj: dict[str, Any], task_kind: str, item_id: str, group_by: str) -> str:
    if group_by == "task_kind":
        return task_kind
    if group_by in {"group", "family", "wave", "domain"}:
        val = obj.get(group_by)
        if isinstance(val, str) and val.strip():
            return val.strip()
        pair = obj.get("pair")
        if isinstance(pair, dict):
            pval = pair.get(group_by)
            if isinstance(pval, str) and pval.strip():
                return pval.strip()
        return task_kind
    # mode "auto": prioritaskan group/family/wave/domain bila eksplisit, selain itu task_kind
    for key in ("group", "family", "wave_id", "wave", "domain"):
        val = obj.get(key)
        if isinstance(val, str) and val.strip():
            return f"{task_kind}:{val.strip()}"
    match = _ID_PREFIX_GROUP_RE.match(item_id)
    if match:
        prefix = match.group(1).rstrip("_-")
        if prefix and prefix != task_kind:
            return f"{task_kind}:{prefix}"
    return task_kind


def _read_lines_or_json(path: Path) -> list[tuple[int, str]]:
    if not path.is_file():
        raise SaturationScanError(f"Berkas hasil ukur tidak ditemukan: {path}")
    try:
        if path.name.endswith(".gz"):
            with gzip.open(path, "rt", encoding="utf-8") as fp:
                raw_text = fp.read()
        else:
            raw_text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError, EOFError, zlib.error) as exc:
        raise SaturationScanError(f"Gagal membaca '{path}': {exc}") from exc

    stripped = raw_text.lstrip()
    if path.suffix.lower() == ".json" or stripped.startswith("["):
        try:
            data = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            raise SaturationScanError(f"JSON tidak sah pada '{path}': {exc}") from exc
        if isinstance(data, list):
            return [(idx, json.dumps(item, ensure_ascii=False)) for idx, item in enumerate(data, start=1)]
        if isinstance(data, dict):
            return [(1, json.dumps(data, ensure_ascii=False))]
        raise SaturationScanError(f"Berkas '{path}' wajib berisi array atau objek JSON.")
    return list(enumerate(raw_text.splitlines(), start=1))


def scan_saturation(
    paths: list[Path],
    *,
    min_observations: int = 2,
    pass_score_threshold: float = 70.0,
    group_by: str = "auto",
    band_share_threshold: float = 0.20,
    spread_epsilon: float = 5.0,
) -> dict[str, Any]:
    """Analisis kejenuhan pasangan tugas, pita skor, dan rekomendasi per kelompok."""
    if not paths:
        raise SaturationScanError("Minimal satu berkas JSONL hasil ukur harus diberikan.")
    if min_observations < 1:
        raise SaturationScanError("--min-observations minimal 1.")
    if group_by not in {"auto", "task_kind", "group", "family", "wave", "domain"}:
        raise SaturationScanError(f"Nilai --group-by tidak sah: {group_by}")

    invalid_details: list[dict[str, Any]] = []
    valid_records: list[dict[str, Any]] = []
    total_lines = 0

    for path in paths:
        for line_no, raw_line in _read_lines_or_json(path):
            total_lines += 1
            if not raw_line.strip():
                invalid_details.append({"file": str(path), "line": line_no, "reason": "baris_kosong"})
                continue
            try:
                obj = json.loads(raw_line)
            except (json.JSONDecodeError, ValueError) as exc:
                invalid_details.append({"file": str(path), "line": line_no, "reason": f"json_tidak_sah: {exc}"})
                continue
            if not isinstance(obj, dict):
                invalid_details.append({"file": str(path), "line": line_no, "reason": "bukan_objek_json"})
                continue

            err_val = obj.get("error")
            if err_val is not None and str(err_val).strip() != "":
                invalid_details.append({"file": str(path), "line": line_no, "reason": f"error_row:{err_val}"})
                continue

            raw_id = obj.get("id")
            item_id = raw_id.strip() if isinstance(raw_id, str) and raw_id.strip() else ""
            if not item_id:
                invalid_details.append({"file": str(path), "line": line_no, "reason": "id_kosong"})
                continue

            raw_tk = obj.get("task_kind")
            task_kind = raw_tk.strip() if isinstance(raw_tk, str) and raw_tk.strip() else "unknown"
            ratified = _extract_ratified(obj)
            score_ok, score_val = _extract_score(obj)
            if not score_ok:
                invalid_details.append({"file": str(path), "line": line_no, "id": item_id, "reason": "score_tidak_sah"})
                continue
            if ratified is None and score_val is None:
                invalid_details.append({"file": str(path), "line": line_no, "id": item_id, "reason": "tanpa_verdict_atau_score"})
                continue

            effective_pass = ratified if ratified is not None else (float(score_val) >= pass_score_threshold)
            group = _resolve_group(obj, task_kind, item_id, group_by)
            valid_records.append(
                {
                    "id": item_id,
                    "task_kind": task_kind,
                    "group": group,
                    "passed": bool(effective_pass),
                    "score": score_val,
                }
            )

    if not valid_records:
        raise SaturationScanError("Tidak ditemukan baris hasil ukur yang valid dalam masukan.")

    # Kelompokkan observasi per (group, id) untuk analisis pasangan jenuh.
    pair_obs: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for rec in valid_records:
        pair_obs[(rec["group"], rec["id"])].append(rec)

    group_pairs: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "total_valid_rows": 0,
            "scored_rows": 0,
            "total_tasks": 0,
            "paired_tasks": 0,
            "single_observation_tasks": 0,
            "always_pass_ids": [],
            "always_fail_ids": [],
            "split_ids": [],
            "score_bands": {b: 0 for b in SCORE_BANDS},
            "scores": [],
        }
    )

    all_always_pass: list[dict[str, Any]] = []
    all_always_fail: list[dict[str, Any]] = []
    all_split: list[dict[str, Any]] = []
    pair_spreads_by_band: dict[str, list[float]] = defaultdict(list)
    pair_pass_by_band: dict[str, list[bool]] = defaultdict(list)

    for (group, item_id) in sorted(pair_obs):
        obs = pair_obs[(group, item_id)]
        gp = group_pairs[group]
        gp["total_tasks"] += 1
        gp["total_valid_rows"] += len(obs)
        scores = [r["score"] for r in obs if r["score"] is not None]
        gp["scored_rows"] += len(scores)
        gp["scores"].extend(scores)
        for s in scores:
            band = _score_band(s)
            gp["score_bands"][band] += 1

        if scores and len(obs) >= min_observations:
            spread = max(scores) - min(scores)
            mean_band = _score_band(sum(scores) / len(scores))
            pair_spreads_by_band[mean_band].append(spread)

        for r in obs:
            if r["score"] is not None:
                pair_pass_by_band[_score_band(r["score"])].append(r["passed"])

        if len(obs) < min_observations:
            gp["single_observation_tasks"] += 1
            continue

        gp["paired_tasks"] += 1
        passes = [r["passed"] for r in obs]
        mean_score = round(sum(scores) / len(scores), 2) if scores else None
        entry = {
            "id": item_id,
            "group": group,
            "task_kind": obs[0]["task_kind"],
            "observations": len(obs),
            "pass_count": sum(1 for p in passes if p),
            "fail_count": sum(1 for p in passes if not p),
            "mean_score": mean_score,
        }
        if all(passes):
            gp["always_pass_ids"].append(item_id)
            all_always_pass.append(entry)
        elif not any(passes):
            gp["always_fail_ids"].append(item_id)
            all_always_fail.append(entry)
        else:
            gp["split_ids"].append(item_id)
            all_split.append(entry)

    # Identifikasi pita skor yang berhenti membedakan.
    total_scored = sum(1 for r in valid_records if r["score"] is not None)
    band_breakdown: dict[str, Any] = {}
    non_discriminating_bands: list[dict[str, Any]] = []
    decile_counts = {d: 0 for d in DECILE_BANDS}
    for r in valid_records:
        if r["score"] is not None:
            decile_counts[_decile_band(r["score"])] += 1

    for band in SCORE_BANDS:
        verdicts = pair_pass_by_band.get(band, [])
        count = len(verdicts)
        share = round(count / total_scored, 4) if total_scored else 0.0
        pass_rate = round(sum(1 for v in verdicts if v) / count, 4) if count else None
        spreads = pair_spreads_by_band.get(band, [])
        mean_spread = round(sum(spreads) / len(spreads), 4) if spreads else None

        reasons: list[str] = []
        if count >= 2 and share >= band_share_threshold:
            if pass_rate == 1.0:
                reasons.append("CEILING_SATURATED" if band == "76-100" else "UNIFORM_ALL_PASS")
            elif pass_rate == 0.0:
                reasons.append("FLOOR_SATURATED" if band == "0-39" else "UNIFORM_ALL_FAIL")
            if mean_spread is not None and mean_spread <= spread_epsilon:
                reasons.append("ZERO_SPREAD_PILEUP")
            elif pass_rate is not None and (pass_rate >= 0.90 or pass_rate <= 0.10):
                reasons.append("LOW_SEPARATION")

        row = {
            "band": band,
            "count": count,
            "share": share,
            "pass_rate": pass_rate,
            "mean_pair_spread": mean_spread,
            "stopped_discriminating": len(reasons) > 0,
            "reasons": reasons,
        }
        band_breakdown[band] = row
        if reasons:
            non_discriminating_bands.append(row)

    # Susun rekomendasi pensiun/pengerasan per kelompok.
    group_recommendations: dict[str, Any] = {}
    for group in sorted(group_pairs):
        gp = group_pairs[group]
        paired_n = gp["paired_tasks"]
        always_pass_n = len(gp["always_pass_ids"])
        always_fail_n = len(gp["always_fail_ids"])
        split_n = len(gp["split_ids"])

        pass_sat_rate = round(always_pass_n / paired_n, 4) if paired_n else 0.0
        fail_sat_rate = round(always_fail_n / paired_n, 4) if paired_n else 0.0
        split_rate = round(split_n / paired_n, 4) if paired_n else 0.0
        mid_share = round(gp["score_bands"]["45-75"] / gp["scored_rows"], 4) if gp["scored_rows"] else 0.0
        ceil_share = round(gp["score_bands"]["76-100"] / gp["scored_rows"], 4) if gp["scored_rows"] else 0.0
        floor_share = round(gp["score_bands"]["0-39"] / gp["scored_rows"], 4) if gp["scored_rows"] else 0.0

        # Aturan rekomendasi deterministik per kelompok:
        # 1. Data kurang (<1 pasangan berulang): kumpulkan pengamatan berulang
        # 2. Jenuh lolos tinggi atau langit-langit penuh -> RETIRE_OR_REPLACE / HARDEN
        # 3. Jenuh gagal tinggi atau lantai penuh -> RECALIBRATE_OR_RETIRE_HARD
        # 4. Sebaliknya -> KEEP_CALIBRATED
        if paired_n == 0:
            action = "COLLECT_PAIRED_RUNS"
            rationale = "Belum ada tugas dengan >= min_observations untuk memisahkan kejenuhan dari kebetulan."
        elif pass_sat_rate >= 0.70 or (ceil_share >= 0.70 and split_rate <= 0.15):
            action = "RETIRE_EASY"
            rationale = (
                f"Kelompok jenuh lolos: always_pass_rate={pass_sat_rate}, ceil_76_100_share={ceil_share}. "
                f"Pensiunkan tugas {len(gp['always_pass_ids'])} item jenuh atau gantikan dengan batch v2 berlapis."
            )
        elif fail_sat_rate >= 0.70 or (floor_share >= 0.70 and split_rate <= 0.15):
            action = "RECALIBRATE_OR_RETIRE_FAILING"
            rationale = (
                f"Kelompok jenuh gagal: always_fail_rate={fail_sat_rate}, floor_0_39_share={floor_share}. "
                "Audit ambiguitas rubrik atau turunkan satu lapis kendala sebelum dijalankan ulang."
            )
        elif pass_sat_rate >= 0.40 or (ceil_share >= 0.50 and mid_share < 0.25):
            action = "HARDEN"
            rationale = (
                f"Kejenuhan naik: always_pass_rate={pass_sat_rate}, mid_band_45_75_share={mid_share}. "
                "Naikkan jumlah kendala per episode / tambahkan larangan alat agar jatuh kembali ke pita 45-75."
            )
        else:
            action = "KEEP_CALIBRATED"
            rationale = (
                f"Kelompok masih membedakan (split_rate={split_rate}, mid_band_45_75_share={mid_share}); pertahankan tugas non-jenuh."
            )

        group_recommendations[group] = {
            "group": group,
            "valid_rows": gp["total_valid_rows"],
            "total_tasks": gp["total_tasks"],
            "paired_tasks": paired_n,
            "single_observation_tasks": gp["single_observation_tasks"],
            "always_pass_count": always_pass_n,
            "always_fail_count": always_fail_n,
            "split_count": split_n,
            "always_pass_rate": pass_sat_rate,
            "always_fail_rate": fail_sat_rate,
            "split_rate": split_rate,
            "always_pass_ids": gp["always_pass_ids"],
            "always_fail_ids": gp["always_fail_ids"],
            "score_bands": gp["score_bands"],
            "mid_band_45_75_share": mid_share,
            "ceiling_76_100_share": ceil_share,
            "floor_0_39_share": floor_share,
            "action": action,
            "rationale": rationale,
        }

    return {
        "schema": SATURATION_SCHEMA,
        "inputs": [str(p) for p in paths],
        "config": {
            "min_observations": min_observations,
            "pass_score_threshold": pass_score_threshold,
            "group_by": group_by,
            "band_share_threshold": band_share_threshold,
            "spread_epsilon": spread_epsilon,
        },
        "summary": {
            "total_lines": total_lines,
            "valid_rows": len(valid_records),
            "invalid_rows": len(invalid_details),
            "scored_rows": total_scored,
            "total_tasks": len(pair_obs),
            "always_pass_tasks": len(all_always_pass),
            "always_fail_tasks": len(all_always_fail),
            "split_tasks": len(all_split),
            "saturated_tasks_total": len(all_always_pass) + len(all_always_fail),
            "non_discriminating_band_count": len(non_discriminating_bands),
        },
        "saturated_pairs": {
            "always_pass": all_always_pass,
            "always_fail": all_always_fail,
            "split": all_split,
        },
        "score_bands": band_breakdown,
        "score_deciles": decile_counts,
        "non_discriminating_bands": non_discriminating_bands,
        "recommendations_by_group": group_recommendations,
        "invalid_details": invalid_details,
    }


def render_markdown_report(result: dict[str, Any]) -> str:
    """Format ringkasan Markdown dari hasil analisis kejenuhan judge."""
    s = result["summary"]
    lines = [
        "# Laporan Analisis Kejenuhan Judge",
        "",
        f"- Baris valid / tidak valid: **{s['valid_rows']}** / **{s['invalid_rows']}**",
        f"- Pasangan jenuh: **{s['always_pass_tasks']}** always_pass, **{s['always_fail_tasks']}** always_fail, **{s['split_tasks']}** split",
        f"- Pita skor berhenti membedakan: **{s['non_discriminating_band_count']}**",
        "",
        "## Pita skor",
        "",
        "| Pita | Jumlah | Porsi | Pass rate | Mean pair spread | Status |",
        "| --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for band in SCORE_BANDS:
        row = result["score_bands"][band]
        status = ", ".join(row["reasons"]) if row["stopped_discriminating"] else "ACTIVE"
        pr = "-" if row["pass_rate"] is None else f"{row['pass_rate']:.2%}"
        ms = "-" if row["mean_pair_spread"] is None else f"{row['mean_pair_spread']:.2f}"
        lines.append(f"| `{band}` | {row['count']} | {row['share']:.1%} | {pr} | {ms} | {status} |")

    lines.extend(["", "## Rekomendasi per kelompok", "", "| Kelompok | Paired | Always pass | Always fail | Split | Aksi |", "| --- | ---: | ---: | ---: | ---: | --- |"])
    for group, rec in result["recommendations_by_group"].items():
        lines.append(
            f"| `{group}` | {rec['paired_tasks']} | {rec['always_pass_count']} | {rec['always_fail_count']} | {rec['split_count']} | `{rec['action']}` |"
        )
    return "\n".join(lines) + "\n"


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp.{os.getpid()}")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Analisis kejenuhan judge dari JSONL hasil saring/ukur.")
    parser.add_argument("inputs", nargs="+", type=Path, help="Berkas JSONL/JSON/.json.gz hasil saring/ukur.")
    parser.add_argument("--min-observations", type=int, default=2, help="Minimal pengamatan per tugas untuk cek pasangan.")
    parser.add_argument("--pass-score-threshold", type=float, default=70.0, help="Ambang score bila boolean ratified tidak ada.")
    parser.add_argument("--group-by", default="auto", choices=("auto", "task_kind", "group", "family", "wave", "domain"))
    parser.add_argument("--format", default="json", choices=("json", "markdown"))
    parser.add_argument("--output", type=Path, help="Simpan keluaran secara atomik ke berkas target.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        report = scan_saturation(
            args.inputs,
            min_observations=args.min_observations,
            pass_score_threshold=args.pass_score_threshold,
            group_by=args.group_by,
        )
        rendered = render_markdown_report(report) if args.format == "markdown" else json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        if args.output is not None:
            _atomic_write(args.output, rendered)
        print(rendered, end="")
        return 0
    except SaturationScanError as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
