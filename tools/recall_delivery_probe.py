#!/usr/bin/env python3
"""Probe keteririman recall (G2 / EVO 0005): bedakan memori benar-benar kosong vs gagal antar.

Kenapa: kegagalan recall seperti EVO 0005 mengembalikan 0 record kepada solver
meskipun memori sebenarnya menyimpan tetangga relevan. Menandai tugas 0-record
yang memiliki tetangga di memori memisahkan masalah kualitas retrieval/delivery
dari kasus yang memang belum punya ingatan sama sekali.
"""
from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence
import json
from pathlib import Path
import re
import sys
from typing import Any


SCHEMA = "ace.recall-delivery-probe.v1"

_STOPWORDS = frozenset(
    {
        "a", "an", "and", "apa", "atau", "bagaimana", "buat", "dari", "dengan",
        "di", "for", "from", "in", "ini", "into", "is", "itu", "ke", "of", "on",
        "pada", "that", "the", "this", "to", "untuk", "with", "yang",
    }
)


def _tokenize(text: str) -> set[str]:
    norm = re.sub(r"[-.]", "_", text.lower())
    tokens: set[str] = set()
    for tok in re.findall(r"[a-z0-9_]+", norm):
        if len(tok) >= 2 and tok not in _STOPWORDS:
            tokens.add(tok)
            if "_" in tok:
                for sub in tok.split("_"):
                    if len(sub) >= 2 and sub not in _STOPWORDS:
                        tokens.add(sub)
    return tokens


def _record_text(record: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in ("query", "title", "text", "summary", "domain"):
        val = record.get(key)
        if isinstance(val, str) and val.strip():
            parts.append(val)
    for key in ("tags", "keywords"):
        val = record.get(key)
        if isinstance(val, list):
            parts.extend(str(item) for item in val if isinstance(item, str))
    content = record.get("content")
    if isinstance(content, dict):
        parts.append(json.dumps(content, sort_keys=True, ensure_ascii=False))
    elif isinstance(content, str) and content.strip():
        parts.append(content)
    return " ".join(parts)


def default_fixture_recall(task: dict[str, Any], store: dict[str, Any]) -> list[dict[str, Any]]:
    """Kembalikan record terkirim dari indeks `delivered` pada store fixture."""
    delivered_map = store.get("delivered")
    if not isinstance(delivered_map, dict):
        delivered_map = store.get("recalled")
    if not isinstance(delivered_map, dict):
        return []
    raw_hits = delivered_map.get(task["id"], delivered_map.get(task["query"], []))
    if not isinstance(raw_hits, list):
        return []
    by_id = {
        str(rec.get("id")): rec
        for rec in store.get("records", [])
        if isinstance(rec, dict) and rec.get("id")
    }
    resolved: list[dict[str, Any]] = []
    for item in raw_hits:
        if isinstance(item, dict):
            resolved.append(item)
        elif isinstance(item, str) and item in by_id:
            resolved.append(by_id[item])
        elif isinstance(item, str):
            resolved.append({"id": item, "text": item})
    return resolved


def find_memory_neighbors(
    task: dict[str, Any],
    records: Sequence[dict[str, Any]],
    *,
    min_overlap: int = 1,
) -> list[dict[str, Any]]:
    """Cari record memori yang bertetangga token relevan dengan kueri tugas."""
    q_parts = [str(task.get("query") or "")]
    if isinstance(task.get("tags"), list):
        q_parts.extend(str(t) for t in task["tags"] if isinstance(t, str))
    q_tokens = _tokenize(" ".join(q_parts))
    if not q_tokens:
        return []

    neighbors: list[tuple[int, str, dict[str, Any]]] = []
    for idx, rec in enumerate(records):
        if not isinstance(rec, dict):
            continue
        r_tokens = _tokenize(_record_text(rec))
        overlap = len(q_tokens & r_tokens)
        if overlap >= min_overlap:
            rid = str(rec.get("id") or f"rec_{idx}")
            neighbors.append((overlap, rid, rec))
    neighbors.sort(key=lambda item: (-item[0], item[1]))
    return [
        {"id": rid, "overlap": overlap, "record": rec}
        for overlap, rid, rec in neighbors
    ]


def probe_recall_delivery(
    tasks: Sequence[dict[str, Any]],
    store: dict[str, Any],
    *,
    recall_fn: Callable[[dict[str, Any], dict[str, Any]], list[dict[str, Any]]] | None = None,
    min_overlap: int = 1,
) -> dict[str, Any]:
    """Audit recall per tugas held-out; tandai hanya tugas 0-record yang punya tetangga di memori."""
    if not isinstance(tasks, Sequence) or not tasks:
        raise ValueError("Daftar tugas held-out wajib berisi minimal satu tugas.")
    if not isinstance(store, dict) or not isinstance(store.get("records"), list):
        raise ValueError("Store fixture wajib berupa objek dengan daftar 'records'.")
    if type(min_overlap) is not int or min_overlap <= 0:
        raise ValueError("--min-overlap wajib bilangan bulat positif.")

    recall = recall_fn or default_fixture_recall
    records = store["records"]
    task_reports: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    flagged_ids: list[str] = []
    truly_empty_ids: list[str] = []
    delivered_task_ids: list[str] = []

    for idx, task in enumerate(tasks, 1):
        if (
            not isinstance(task, dict)
            or not isinstance(task.get("id"), str)
            or not task["id"].strip()
            or not isinstance(task.get("query"), str)
            or not task["query"].strip()
        ):
            raise ValueError(f"Tugas ke-{idx} wajib memiliki 'id' dan 'query' string tak-kosong.")
        tid = task["id"]
        if tid in seen_ids:
            raise ValueError(f"ID tugas duplikat: {tid}")
        seen_ids.add(tid)

        delivered = list(recall(task, store))
        neighbors = find_memory_neighbors(task, records, min_overlap=min_overlap)
        delivered_count = len(delivered)
        neighbor_count = len(neighbors)

        missed_with_neighbors = delivered_count == 0 and neighbor_count > 0
        if delivered_count > 0:
            status = "delivered"
            delivered_task_ids.append(tid)
        elif neighbor_count > 0:
            status = "zero_record_with_neighbors"
            flagged_ids.append(tid)
        else:
            status = "zero_record_truly_empty"
            truly_empty_ids.append(tid)

        task_reports.append(
            {
                "task_id": tid,
                "query": task["query"],
                "delivered_count": delivered_count,
                "delivered_ids": [str(r.get("id") or f"delivered_{i}") for i, r in enumerate(delivered)],
                "neighbor_count": neighbor_count,
                "neighbor_ids": [n["id"] for n in neighbors],
                "missed_with_neighbors": missed_with_neighbors,
                "status": status,
            }
        )

    return {
        "schema": SCHEMA,
        "summary": {
            "total_tasks": len(task_reports),
            "delivered_tasks": len(delivered_task_ids),
            "zero_record_tasks": len(flagged_ids) + len(truly_empty_ids),
            "flagged_missed_with_neighbors": len(flagged_ids),
            "truly_empty_unflagged": len(truly_empty_ids),
        },
        "flagged_task_ids": flagged_ids,
        "truly_empty_task_ids": truly_empty_ids,
        "delivered_task_ids": delivered_task_ids,
        "tasks": task_reports,
    }


def _load_json_or_jsonl(path: Path) -> Any:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".jsonl":
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    return json.loads(text)


def render_markdown(report: dict[str, Any]) -> str:
    s = report["summary"]
    lines = [
        "# Probe Keteririman Recall (EVO 0005 / G2)",
        "",
        f"- Schema: `{report['schema']}`",
        f"- Total tugas: **{s['total_tasks']}** (terkirim: **{s['delivered_tasks']}**, 0-record: **{s['zero_record_tasks']}**)",
        f"- 0-record bertetangga di memory (**ditandai**): **{s['flagged_missed_with_neighbors']}** — {report['flagged_task_ids']}",
        f"- 0-record benar-benar kosong (**tidak ditandai**): **{s['truly_empty_unflagged']}** — {report['truly_empty_task_ids']}",
        "",
        "| Task ID | Delivered | Neighbors | Ditandai | Status |",
        "| --- | ---: | ---: | --- | --- |",
    ]
    for row in report["tasks"]:
        lines.append(
            f"| `{row['task_id']}` | {row['delivered_count']} | {row['neighbor_count']} "
            f"| {row['missed_with_neighbors']} | `{row['status']}` |"
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tasks", required=True, type=Path, help="Berkas JSON/JSONL tugas held-out.")
    parser.add_argument("--store", type=Path, default=None, help="Berkas JSON store fixture ({records, delivered}).")
    parser.add_argument("--memory", type=Path, default=None, help="Berkas JSONL records memory (alternatif --store).")
    parser.add_argument("--delivered", type=Path, default=None, help="Berkas JSON peta delivered opsional.")
    parser.add_argument("--min-overlap", type=int, default=1)
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    args = parser.parse_args(argv)
    if (args.store is None) == (args.memory is None):
        parser.error("Berikan tepat salah satu dari --store atau --memory.")
    try:
        tasks = _load_json_or_jsonl(args.tasks)
        if args.store is not None:
            store = _load_json_or_jsonl(args.store)
        else:
            records = _load_json_or_jsonl(args.memory)
            delivered = json.loads(args.delivered.read_text(encoding="utf-8")) if args.delivered else {}
            store = {"records": records, "delivered": delivered}
        report = probe_recall_delivery(tasks, store, min_overlap=args.min_overlap)
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    print(render_markdown(report) if args.format == "markdown" else json.dumps(report, indent=2, ensure_ascii=False), end="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
