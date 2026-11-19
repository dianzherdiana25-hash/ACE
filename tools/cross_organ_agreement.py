#!/usr/bin/env python3
"""Bench kesepakatan silang multi-organ offline dari fixture JSONL (0 panggilan HTTP).

Mengevaluasi keluaran berbagai organ (mis. `groq/qwen/qwen3.8-27b`,
`groq/openai/gpt-oss-120b`, `gemini/gemini-3-flash-preview`, `gonka/DeepSeek-V4-Flash`)
pada daftar `task_id` yang sama:
- Menormalkan jawaban (JSON kanonik, angka, boolean, atau teks terpotong spasi).
- Memisahkan panggilan valid (`ok`) dari `abstain`/`error`/`unavailable`.
- Menghitung `raw_agreement`, Cohen's kappa (`cohen_kappa`) berpasangan beserta penanda
  `cross_provider` untuk audit aturan heterogenitas.
- Melaporkan ketidaksepakatan (`disagreement_cases`), tugas tak lengkap, serta anomali JSONL.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from itertools import combinations
import json
from pathlib import Path
import sys
from typing import Any

AGREEMENT_SCHEMA = "ace.cross-organ-agreement.v1"

_VALID_STATUSES = frozenset({"ok", "abstain", "error", "unavailable"})


def normalize_answer(value: Any, *, case_insensitive: bool = True) -> str:
    """Kanonikalisasi jawaban heterogen menjadi kunci string deterministik."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool:true" if value else "bool:false"
    if isinstance(value, int):
        return f"num:{value}"
    if isinstance(value, float):
        if value.is_integer():
            return f"num:{int(value)}"
        return f"num:{round(value, 9)}"
    if isinstance(value, (dict, list)):
        return "json:" + json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))

    text = str(value).strip()
    if text.startswith("{") or text.startswith("["):
        try:
            parsed = json.loads(text)
            if isinstance(parsed, (dict, list)):
                return "json:" + json.dumps(parsed, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        except json.JSONDecodeError:
            pass

    collapsed = " ".join(text.split())
    return "str:" + (collapsed.casefold() if case_insensitive else collapsed)


def _organ_provider(organ: str) -> str:
    return organ.split("/", 1)[0].strip().lower() if "/" in organ else organ.strip().lower()


def compute_cohen_kappa(pairs: list[tuple[str, str]]) -> tuple[float, float | None]:
    """Hitung `(raw_agreement, cohen_kappa)` untuk daftar label `(label_a, label_b)`."""
    n = len(pairs)
    if n == 0:
        return 0.0, None
    agree = sum(1 for a, b in pairs if a == b)
    po = agree / n

    counts_a = Counter(a for a, _ in pairs)
    counts_b = Counter(b for _, b in pairs)
    labels = set(counts_a) | set(counts_b)
    pe = sum((counts_a[lbl] / n) * (counts_b[lbl] / n) for lbl in labels)

    if pe >= 1.0 - 1e-12:
        kappa = 1.0 if abs(po - 1.0) <= 1e-12 else 0.0
    else:
        kappa = (po - pe) / (1.0 - pe)
    return round(po, 4), round(kappa, 4)


def parse_fixture_records(records: list[Any]) -> tuple[dict[str, dict[str, dict[str, Any]]], list[dict[str, Any]]]:
    """Muat daftar baris fixture menjadi matriks `task_id -> organ -> record`."""
    matrix: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    anomalies: list[dict[str, Any]] = []

    for idx, row in enumerate(records, start=1):
        if not isinstance(row, dict):
            anomalies.append({"row": idx, "code": "non_object_row", "detail": f"Tipe bukan dict: {type(row).__name__}"})
            continue
        task_id = str(row.get("task_id") or "").strip()
        organ = str(row.get("brain_of_origin") or row.get("organ") or "").strip()
        if not task_id or not organ:
            anomalies.append({"row": idx, "code": "missing_task_or_organ", "detail": "task_id atau brain_of_origin/organ kosong"})
            continue

        status = str(row.get("status") or "ok").strip().lower()
        if status not in _VALID_STATUSES:
            anomalies.append({"row": idx, "code": "unknown_status", "detail": f"Status tidak dikenal: {status!r}"})
            continue

        if organ in matrix[task_id]:
            anomalies.append({"row": idx, "code": "duplicate_task_organ", "detail": f"Duplikat ({task_id}, {organ})"})
            continue

        matrix[task_id][organ] = {
            "task_id": task_id,
            "organ": organ,
            "status": status,
            "raw_answer": row.get("answer") if "answer" in row else row.get("verdict"),
        }
    return matrix, anomalies


def load_fixture_jsonl(path: Path) -> tuple[dict[str, dict[str, dict[str, Any]]], list[dict[str, Any]]]:
    """Baca fixture JSONL multi-organ secara toleran atas baris rusak."""
    target = Path(path)
    if not target.is_file():
        raise ValueError(f"Berkas fixture JSONL tidak ditemukan: {path}")

    raw_rows: list[Any] = []
    parse_anomalies: list[dict[str, Any]] = []
    for lineno, raw_line in enumerate(target.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
        stripped = raw_line.strip()
        if not stripped:
            continue
        try:
            raw_rows.append(json.loads(stripped))
        except json.JSONDecodeError as exc:
            parse_anomalies.append({"row": lineno, "code": "malformed_json", "detail": str(exc)})

    matrix, row_anomalies = parse_fixture_records(raw_rows)
    return matrix, parse_anomalies + row_anomalies


def evaluate_cross_organ_agreement(
    matrix: dict[str, dict[str, dict[str, Any]]],
    *,
    anomalies: list[dict[str, Any]] | None = None,
    case_insensitive: bool = True,
) -> dict[str, Any]:
    """Hitung kesepakatan silang, Cohen's kappa, rasio absten, dan konsensus tugas."""
    organs = sorted({organ for task_map in matrix.values() for organ in task_map})
    if len(organs) < 2:
        raise ValueError(f"Minimal dibutuhkan 2 organ berbeda untuk kesepakatan silang (ditemukan {len(organs)}).")

    all_anomalies = list(anomalies or [])
    organ_stats: dict[str, dict[str, int]] = {
        o: {"total": 0, "ok": 0, "abstain": 0, "error": 0, "unavailable": 0} for o in organs
    }
    normalized_by_task: dict[str, dict[str, str]] = {}

    unanimous_count = 0
    majority_count = 0
    split_count = 0
    all_abstained_count = 0
    incomplete_tasks: list[str] = []
    disagreement_cases: list[dict[str, Any]] = []

    for task_id in sorted(matrix):
        task_rows = matrix[task_id]
        if len(task_rows) < len(organs):
            incomplete_tasks.append(task_id)

        norm_answers: dict[str, str] = {}
        for organ, rec in sorted(task_rows.items()):
            st = rec["status"]
            organ_stats[organ]["total"] += 1
            organ_stats[organ][st] += 1
            if st == "ok":
                norm_answers[organ] = normalize_answer(rec["raw_answer"], case_insensitive=case_insensitive)
        normalized_by_task[task_id] = norm_answers

        if not norm_answers:
            all_abstained_count += 1
            continue

        counts = Counter(norm_answers.values())
        if len(counts) == 1:
            if len(task_rows) == len(organs) and len(norm_answers) == len(organs):
                unanimous_count += 1
        else:
            top_label, top_votes = counts.most_common(1)[0]
            has_strict_majority = top_votes > len(norm_answers) / 2.0 and list(counts.values()).count(top_votes) == 1
            if has_strict_majority:
                majority_count += 1
            else:
                split_count += 1
            disagreement_cases.append(
                {
                    "task_id": task_id,
                    "responses": dict(sorted(norm_answers.items())),
                    "plurality_winner": top_label if has_strict_majority else None,
                    "distinct_answers": len(counts),
                }
            )

    pairwise: list[dict[str, Any]] = []
    for org_a, org_b in combinations(organs, 2):
        shared_pairs: list[tuple[str, str]] = []
        for task_id in sorted(matrix):
            n_map = normalized_by_task[task_id]
            if org_a in n_map and org_b in n_map:
                shared_pairs.append((n_map[org_a], n_map[org_b]))
        raw_ag, kappa = compute_cohen_kappa(shared_pairs)
        pairwise.append(
            {
                "organ_a": org_a,
                "organ_b": org_b,
                "cross_provider": _organ_provider(org_a) != _organ_provider(org_b),
                "shared_ok_tasks": len(shared_pairs),
                "raw_agreement": raw_ag,
                "cohen_kappa": kappa,
            }
        )

    organ_summary = {
        o: {
            **st,
            "abstention_rate": round((st["abstain"] + st["error"] + st["unavailable"]) / st["total"], 4)
            if st["total"]
            else 0.0,
        }
        for o, st in organ_stats.items()
    }

    total_tasks = len(matrix)
    kappas = [p["cohen_kappa"] for p in pairwise if p["cohen_kappa"] is not None]
    mean_kappa = round(sum(kappas) / len(kappas), 4) if kappas else None

    return {
        "schema": AGREEMENT_SCHEMA,
        "network_calls": 0,
        "summary": {
            "organ_count": len(organs),
            "task_count": total_tasks,
            "unanimous_tasks": unanimous_count,
            "majority_tasks": majority_count,
            "split_tasks": split_count,
            "all_abstained_tasks": all_abstained_count,
            "incomplete_task_count": len(incomplete_tasks),
            "disagreement_count": len(disagreement_cases),
            "mean_pairwise_kappa": mean_kappa,
            "anomaly_count": len(all_anomalies),
        },
        "organs": organ_summary,
        "pairwise": pairwise,
        "incomplete_tasks": incomplete_tasks,
        "disagreement_cases": disagreement_cases,
        "anomalies": all_anomalies,
    }


def render_markdown(report: dict[str, Any]) -> str:
    s = report["summary"]
    lines = [
        "# Bench Kesepakatan Silang Multi-Organ (Offline)",
        "",
        f"- Schema: `{report['schema']}` (network_calls={report['network_calls']})",
        f"- Total organ: {s['organ_count']} | Total tugas: {s['task_count']}",
        f"- Konsensus bulat (`unanimous`): {s['unanimous_tasks']} | Mayoritas: {s['majority_tasks']} | Pecah (`split`): {s['split_tasks']}",
        f"- Rerata Cohen's kappa berpasangan: `{s['mean_pairwise_kappa']}` | Anomali JSONL: {s['anomaly_count']}",
        "",
        "## Statistik per Organ",
        "",
        "| Organ | Total | OK | Abstain | Error/Unavail | Rasio Non-OK |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for organ, st in sorted(report["organs"].items()):
        lines.append(
            f"| `{organ}` | {st['total']} | {st['ok']} | {st['abstain']} | "
            f"{st['error'] + st['unavailable']} | {st['abstention_rate'] * 100:.1f}% |"
        )

    lines.extend(
        [
            "",
            "## Matriks Kesepakatan Berpasangan",
            "",
            "| Organ A | Organ B | Lintas Provider | Tugas Bersama | Raw Agreement | Cohen's Kappa |",
            "| --- | --- | --- | ---: | ---: | ---: |",
        ]
    )
    for pair in report["pairwise"]:
        kappa_str = f"{pair['cohen_kappa']:.4f}" if pair["cohen_kappa"] is not None else "N/A"
        lines.append(
            f"| `{pair['organ_a']}` | `{pair['organ_b']}` | {'YA' if pair['cross_provider'] else 'TIDAK'} | "
            f"{pair['shared_ok_tasks']} | {pair['raw_agreement'] * 100:.1f}% | {kappa_str} |"
        )
    return "\n".join(lines) + "\n"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Bench kesepakatan silang multi-organ offline dari JSONL.")
    parser.add_argument("--input", type=Path, required=True, help="Berkas fixture JSONL hasil respons organ.")
    parser.add_argument("--case-sensitive", action="store_true", help="Bandingkan teks secara case-sensitive.")
    parser.add_argument("--format", choices=("json", "markdown"), default="json", help="Format keluaran.")
    parser.add_argument("--output", type=Path, default=None, help="Tulis hasil ke berkas.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
        matrix, anomalies = load_fixture_jsonl(args.input)
        report = evaluate_cross_organ_agreement(
            matrix,
            anomalies=anomalies,
            case_insensitive=not args.case_sensitive,
        )
        rendered = (
            json.dumps(report, indent=2, ensure_ascii=False) + "\n"
            if args.format == "json"
            else render_markdown(report)
        )
        if args.output is not None:
            out_path = args.output.resolve()
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(rendered, encoding="utf-8")
        else:
            sys.stdout.write(rendered)
    except (OSError, ValueError, TypeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
