"""Hitung delta spesialisasi per domain dan stabilitas lintas-seed antar laporan benchmark.

Dirancang untuk membandingkan laporan JSON keluaran ``tools/owner_benchmark.py``
(skema ``ace.owner-benchmark.v1``), baik sepasang laporan tunggal maupun
kumpulan laporan multi-seed, guna memverifikasi apakah perbaikan skor di satu
domain bersifat konsisten di seluruh seed atau hanya kebetulan fluktuasi seed.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence


SCHEMA = "ace.specialization-delta.v1"
DEFAULT_STABILITY_TOLERANCE = 0.05


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values)


def _pstdev(values: Sequence[float]) -> float:
    if len(values) <= 1:
        return 0.0
    mu = _mean(values)
    var = sum((v - mu) ** 2 for v in values) / len(values)
    return math.sqrt(var)


def _normalize_collection(raw: Any, label: str) -> list[dict[str, Any]]:
    if isinstance(raw, list):
        items = raw
    elif isinstance(raw, dict):
        if isinstance(raw.get("reports"), list):
            items = raw["reports"]
        else:
            items = [raw]
    else:
        raise ValueError(f"{label} harus berupa objek JSON atau daftar laporan")

    out: list[dict[str, Any]] = []
    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValueError(f"{label}[{idx}] bukan objek JSON")
        if "by_domain" not in item and "tasks" not in item:
            raise ValueError(f"{label}[{idx}] tidak memiliki 'by_domain' ataupun 'tasks'")
        out.append(item)
    if not out:
        raise ValueError(f"{label} kosong")
    return out


def _domain_metrics_from_report(report: Mapping[str, Any]) -> dict[str, dict[str, float]]:
    by_domain = report.get("by_domain")
    if isinstance(by_domain, Mapping) and by_domain:
        parsed: dict[str, dict[str, float]] = {}
        for domain, stats in by_domain.items():
            if not isinstance(stats, Mapping):
                continue
            total = float(stats.get("total", 0))
            passed = float(stats.get("passed", 0))
            pass_rate = stats.get("pass_rate")
            if pass_rate is None:
                pass_rate = (passed / total) if total > 0 else 0.0
            avg_score = stats.get("avg_score", pass_rate)
            parsed[str(domain)] = {
                "total": total,
                "passed": passed,
                "pass_rate": float(pass_rate),
                "avg_score": float(avg_score),
            }
        return parsed

    grouped: dict[str, list[tuple[bool, float]]] = {}
    for task in report.get("tasks", []):
        if not isinstance(task, Mapping):
            continue
        domain = str(task.get("domain", "unknown"))
        passed = bool(task.get("passed", False))
        score = float(task.get("score", 1.0 if passed else 0.0))
        grouped.setdefault(domain, []).append((passed, score))

    parsed = {}
    for domain, rows in grouped.items():
        total = float(len(rows))
        passed_count = float(sum(1 for ok, _ in rows if ok))
        avg_score = sum(score for _, score in rows) / total
        parsed[domain] = {
            "total": total,
            "passed": passed_count,
            "pass_rate": passed_count / total,
            "avg_score": avg_score,
        }
    return parsed


def _summary_metrics(report: Mapping[str, Any], dom_map: Mapping[str, Mapping[str, float]]) -> tuple[float, float]:
    summary = report.get("summary")
    if isinstance(summary, Mapping) and "pass_rate" in summary and "avg_score" in summary:
        return float(summary["pass_rate"]), float(summary["avg_score"])
    total = sum(v["total"] for v in dom_map.values())
    passed = sum(v["passed"] for v in dom_map.values())
    if total <= 0:
        return 0.0, 0.0
    weighted_score = sum(v["avg_score"] * v["total"] for v in dom_map.values())
    return passed / total, weighted_score / total


def compare_reports(
    baseline_input: Any,
    candidate_input: Any,
    *,
    stability_tolerance: float = DEFAULT_STABILITY_TOLERANCE,
) -> dict[str, Any]:
    """Bandingkan baseline vs candidate dan hitung delta per domain + stabilitas seed."""
    baseline_reports = _normalize_collection(baseline_input, "baseline")
    candidate_reports = _normalize_collection(candidate_input, "candidate")

    base_by_seed: dict[int, dict[str, dict[str, float]]] = {}
    cand_by_seed: dict[int, dict[str, dict[str, float]]] = {}
    base_overall_pass: list[float] = []
    base_overall_score: list[float] = []
    cand_overall_pass: list[float] = []
    cand_overall_score: list[float] = []

    all_domains: set[str] = set()
    base_dom_list: list[dict[str, dict[str, float]]] = []
    cand_dom_list: list[dict[str, dict[str, float]]] = []

    for idx, rep in enumerate(baseline_reports):
        seed = int(rep.get("seed", idx))
        dmap = _domain_metrics_from_report(rep)
        base_dom_list.append(dmap)
        base_by_seed[seed] = dmap
        all_domains.update(dmap.keys())
        op, os_ = _summary_metrics(rep, dmap)
        base_overall_pass.append(op)
        base_overall_score.append(os_)

    for idx, rep in enumerate(candidate_reports):
        seed = int(rep.get("seed", idx))
        dmap = _domain_metrics_from_report(rep)
        cand_dom_list.append(dmap)
        cand_by_seed[seed] = dmap
        all_domains.update(dmap.keys())
        op, os_ = _summary_metrics(rep, dmap)
        cand_overall_pass.append(op)
        cand_overall_score.append(os_)

    shared_seeds = sorted(set(base_by_seed) & set(cand_by_seed))

    domains_out: dict[str, dict[str, Any]] = {}
    improved_domains: list[str] = []
    regressed_domains: list[str] = []
    unchanged_domains: list[str] = []
    unstable_domains: list[str] = []

    for domain in sorted(all_domains):
        b_rates = [d[domain]["pass_rate"] for d in base_dom_list if domain in d]
        c_rates = [d[domain]["pass_rate"] for d in cand_dom_list if domain in d]
        b_scores = [d[domain]["avg_score"] for d in base_dom_list if domain in d]
        c_scores = [d[domain]["avg_score"] for d in cand_dom_list if domain in d]

        b_mean_rate = _mean(b_rates) if b_rates else 0.0
        c_mean_rate = _mean(c_rates) if c_rates else 0.0
        b_mean_score = _mean(b_scores) if b_scores else 0.0
        c_mean_score = _mean(c_scores) if c_scores else 0.0

        rate_delta = round(c_mean_rate - b_mean_rate, 6)
        score_delta = round(c_mean_score - b_mean_score, 6)

        paired_deltas: list[dict[str, Any]] = []
        paired_values: list[float] = []
        for seed in shared_seeds:
            if domain in base_by_seed[seed] and domain in cand_by_seed[seed]:
                dv = round(
                    cand_by_seed[seed][domain]["pass_rate"]
                    - base_by_seed[seed][domain]["pass_rate"],
                    6,
                )
                paired_values.append(dv)
                paired_deltas.append({"seed": seed, "pass_rate_delta": dv})

        pos_count = sum(1 for v in paired_values if v > 1e-9)
        neg_count = sum(1 for v in paired_values if v < -1e-9)
        sign_flips = min(pos_count, neg_count)
        delta_stdev = round(_pstdev(paired_values), 6) if paired_values else 0.0
        delta_range = (
            round(max(paired_values) - min(paired_values), 6) if paired_values else 0.0
        )

        # Kriteria stabil: arah antar-seed tidak berbalik tanda dan rentang deviasi kecil.
        is_stable = sign_flips == 0 and delta_range <= stability_tolerance

        if sign_flips > 0:
            direction = "mixed_across_seeds"
        elif rate_delta > 1e-9:
            direction = "improved"
        elif rate_delta < -1e-9:
            direction = "regressed"
        else:
            direction = "unchanged"

        if direction == "improved":
            improved_domains.append(domain)
        elif direction == "regressed":
            regressed_domains.append(domain)
        elif direction == "unchanged":
            unchanged_domains.append(domain)
        if not is_stable:
            unstable_domains.append(domain)

        domains_out[domain] = {
            "baseline_mean_pass_rate": round(b_mean_rate, 6),
            "candidate_mean_pass_rate": round(c_mean_rate, 6),
            "pass_rate_delta": rate_delta,
            "baseline_mean_avg_score": round(b_mean_score, 6),
            "candidate_mean_avg_score": round(c_mean_score, 6),
            "avg_score_delta": score_delta,
            "baseline_seed_stdev": round(_pstdev(b_rates), 6) if b_rates else 0.0,
            "candidate_seed_stdev": round(_pstdev(c_rates), 6) if c_rates else 0.0,
            "paired_seed_deltas": paired_deltas,
            "paired_delta_stdev": delta_stdev,
            "paired_delta_range": delta_range,
            "sign_flips": sign_flips,
            "direction": direction,
            "stable": is_stable,
        }

    base_pass_mean = _mean(base_overall_pass)
    cand_pass_mean = _mean(cand_overall_pass)
    base_score_mean = _mean(base_overall_score)
    cand_score_mean = _mean(cand_overall_score)

    return {
        "schema": SCHEMA,
        "baseline_seeds": sorted(base_by_seed.keys()),
        "candidate_seeds": sorted(cand_by_seed.keys()),
        "shared_seeds": shared_seeds,
        "stability_tolerance": stability_tolerance,
        "overall": {
            "baseline_mean_pass_rate": round(base_pass_mean, 6),
            "candidate_mean_pass_rate": round(cand_pass_mean, 6),
            "pass_rate_delta": round(cand_pass_mean - base_pass_mean, 6),
            "baseline_mean_avg_score": round(base_score_mean, 6),
            "candidate_mean_avg_score": round(cand_score_mean, 6),
            "avg_score_delta": round(cand_score_mean - base_score_mean, 6),
        },
        "summary": {
            "domain_count": len(domains_out),
            "improved_domains": improved_domains,
            "regressed_domains": regressed_domains,
            "unchanged_domains": unchanged_domains,
            "unstable_domains": unstable_domains,
            "all_domains_stable": len(unstable_domains) == 0,
        },
        "by_domain": domains_out,
    }


def _load_paths_as_reports(paths: Sequence[str]) -> list[dict[str, Any]]:
    collected: list[dict[str, Any]] = []
    for raw_path in paths:
        obj = json.loads(Path(raw_path).read_text(encoding="utf-8"))
        collected.extend(_normalize_collection(obj, raw_path))
    return collected


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Bandingkan dua laporan/seri benchmark AG39 dan hitung delta spesialisasi per domain."
    )
    parser.add_argument(
        "--baseline",
        nargs="+",
        required=True,
        help="Satu atau lebih file JSON laporan baseline (atau file berisi daftar laporan multi-seed).",
    )
    parser.add_argument(
        "--candidate",
        nargs="+",
        required=True,
        help="Satu atau lebih file JSON laporan candidate (atau file berisi daftar laporan multi-seed).",
    )
    parser.add_argument(
        "--stability-tolerance",
        type=float,
        default=DEFAULT_STABILITY_TOLERANCE,
        help=f"Toleransi rentang delta lintas-seed agar dianggap stabil (default: {DEFAULT_STABILITY_TOLERANCE}).",
    )
    parser.add_argument("--out", help="Path output JSON opsional (default stdout).")
    args = parser.parse_args(argv)

    try:
        base_reports = _load_paths_as_reports(args.baseline)
        cand_reports = _load_paths_as_reports(args.candidate)
        result = compare_reports(
            base_reports,
            cand_reports,
            stability_tolerance=args.stability_tolerance,
        )
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    payload = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(payload, encoding="utf-8")
    else:
        sys.stdout.write(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
