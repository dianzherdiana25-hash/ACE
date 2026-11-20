"""Probe presisi dan recall retrieval memori berbasis kueri berlabel relevansi (AG43).

Menjalankan sekumpulan kueri dengan label ground-truth ``relevant_ids`` atas
store ``CognitiveMemory`` secara read-only (salinan sementara di memori/tmp)
atau retriever kustom untuk menghitung precision, recall, F1 per kueri maupun
agregat makro/mikro.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys
import tempfile
from typing import Any, Callable, Mapping, Sequence

from ace_operational.cognitive_memory import CognitiveMemory


SCHEMA = "ace.recall-precision-probe.v1"
DEFAULT_LIMIT = 10


def _compute_prf(tp: int, retrieved_n: int, relevant_n: int) -> tuple[float, float, float]:
    if retrieved_n == 0 and relevant_n == 0:
        return 1.0, 1.0, 1.0
    precision = (tp / retrieved_n) if retrieved_n > 0 else 0.0
    recall = (tp / relevant_n) if relevant_n > 0 else 0.0
    if precision + recall > 0.0:
        f1 = 2.0 * precision * recall / (precision + recall)
    else:
        f1 = 0.0
    return round(precision, 6), round(recall, 6), round(f1, 6)


def make_cognitive_memory_retriever(
    memory_path: Path,
) -> Callable[[Mapping[str, Any], int], list[str]]:
    """Buat adaptor retriever read-only di atas berkas/direktori CognitiveMemory."""
    src = Path(memory_path)
    jsonl_src = src / "memory.jsonl" if src.is_dir() else src
    if not jsonl_src.is_file():
        raise FileNotFoundError(f"Berkas memory JSONL tidak ditemukan: {jsonl_src}")
    raw_bytes = jsonl_src.read_bytes()

    def _retrieve(query_spec: Mapping[str, Any], default_limit: int) -> list[str]:
        with tempfile.TemporaryDirectory() as scratch:
            scratch_dir = Path(scratch)
            (scratch_dir / "memory.jsonl").write_bytes(raw_bytes)
            mem = CognitiveMemory(scratch_dir)
            limit = int(query_spec.get("limit", default_limit))
            kinds = query_spec.get("kinds")
            context = query_spec.get("context")
            res = mem.recall(
                str(query_spec.get("query") or ""),
                kinds=list(kinds) if isinstance(kinds, list) else None,
                context=str(context) if context is not None else None,
                limit=limit,
            )
            return [str(item["id"]) for item in res.get("results", [])]

    return _retrieve


def make_cognitive_memory_cached_retriever(
    memory_path: Path,
) -> Callable[[Mapping[str, Any], int], list[str]]:
    """Versi efisien yang menyalin sekali lalu memakai ulang instansi CognitiveMemory read-only."""
    src = Path(memory_path)
    jsonl_src = src / "memory.jsonl" if src.is_dir() else src
    if not jsonl_src.is_file():
        raise FileNotFoundError(f"Berkas memory JSONL tidak ditemukan: {jsonl_src}")

    tmpdir = tempfile.mkdtemp(prefix="ace_recall_probe_")
    mem_dir = Path(tmpdir)
    shutil.copy2(jsonl_src, mem_dir / "memory.jsonl")
    mem = CognitiveMemory(mem_dir)

    def _retrieve(query_spec: Mapping[str, Any], default_limit: int) -> list[str]:
        limit = int(query_spec.get("limit", default_limit))
        kinds = query_spec.get("kinds")
        context = query_spec.get("context")
        res = mem.recall(
            str(query_spec.get("query") or ""),
            kinds=list(kinds) if isinstance(kinds, list) else None,
            context=str(context) if context is not None else None,
            limit=limit,
        )
        return [str(item["id"]) for item in res.get("results", [])]

    setattr(_retrieve, "_cleanup_dir", mem_dir)
    return _retrieve


def evaluate_recall_precision(
    queries: Sequence[Mapping[str, Any]],
    retriever: Callable[[Mapping[str, Any], int], Sequence[str]],
    *,
    default_limit: int = DEFAULT_LIMIT,
) -> dict[str, Any]:
    """Hitung precision, recall, dan F1 per kueri serta agregat makro/mikro."""
    if not queries:
        raise ValueError("Daftar kueri tidak boleh kosong")

    per_query: list[dict[str, Any]] = []
    zero_recall_queries: list[str] = []
    total_tp = 0
    total_retrieved = 0
    total_relevant = 0

    for idx, q in enumerate(queries):
        qid = str(q.get("query_id") or q.get("id") or f"q-{idx + 1}")
        qtext = str(q.get("query") or "")
        raw_rel = q.get("relevant_ids")
        if not isinstance(raw_rel, Sequence) or isinstance(raw_rel, (str, bytes)):
            raise ValueError(f"Kueri '{qid}' wajib memiliki daftar 'relevant_ids'")
        relevant_ordered = list(dict.fromkeys(str(r) for r in raw_rel))
        relevant_set = set(relevant_ordered)

        raw_retrieved = retriever(q, default_limit)
        limit = int(q.get("limit", default_limit))
        retrieved_ordered = list(dict.fromkeys(str(r) for r in raw_retrieved))[:limit]
        retrieved_set = set(retrieved_ordered)

        tp_ids = [rid for rid in retrieved_ordered if rid in relevant_set]
        fp_ids = [rid for rid in retrieved_ordered if rid not in relevant_set]
        fn_ids = [rid for rid in relevant_ordered if rid not in retrieved_set]

        precision, recall, f1 = _compute_prf(
            len(tp_ids), len(retrieved_ordered), len(relevant_ordered)
        )
        if len(relevant_ordered) > 0 and len(tp_ids) == 0:
            zero_recall_queries.append(qid)

        total_tp += len(tp_ids)
        total_retrieved += len(retrieved_ordered)
        total_relevant += len(relevant_ordered)

        per_query.append(
            {
                "query_id": qid,
                "query": qtext,
                "limit": limit,
                "relevant_ids": relevant_ordered,
                "retrieved_ids": retrieved_ordered,
                "true_positives": tp_ids,
                "false_positives": fp_ids,
                "false_negatives": fn_ids,
                "tp_count": len(tp_ids),
                "fp_count": len(fp_ids),
                "fn_count": len(fn_ids),
                "precision": precision,
                "recall": recall,
                "f1": f1,
            }
        )

    n = len(per_query)
    macro_precision = round(sum(row["precision"] for row in per_query) / n, 6)
    macro_recall = round(sum(row["recall"] for row in per_query) / n, 6)
    macro_f1 = round(sum(row["f1"] for row in per_query) / n, 6)
    micro_precision, micro_recall, micro_f1 = _compute_prf(
        total_tp, total_retrieved, total_relevant
    )

    return {
        "schema": SCHEMA,
        "summary": {
            "query_count": n,
            "total_tp": total_tp,
            "total_retrieved": total_retrieved,
            "total_relevant": total_relevant,
            "macro_precision": macro_precision,
            "macro_recall": macro_recall,
            "macro_f1": macro_f1,
            "micro_precision": micro_precision,
            "micro_recall": micro_recall,
            "micro_f1": micro_f1,
            "zero_recall_query_count": len(zero_recall_queries),
            "zero_recall_queries": zero_recall_queries,
        },
        "queries": per_query,
    }


def _load_queries(path: Path) -> list[dict[str, Any]]:
    raw = Path(path).read_text(encoding="utf-8").strip()
    if not raw:
        raise ValueError(f"Berkas kueri kosong: {path}")
    if raw.startswith("["):
        data = json.loads(raw)
        if not isinstance(data, list):
            raise ValueError("Berkas kueri JSON harus berupa daftar")
        return [dict(item) for item in data]
    if raw.startswith("{") and "\n" not in raw:
        obj = json.loads(raw)
        if isinstance(obj, dict) and isinstance(obj.get("queries"), list):
            return [dict(item) for item in obj["queries"]]
        return [dict(obj)]
    items: list[dict[str, Any]] = []
    for line in raw.splitlines():
        s = line.strip()
        if s:
            items.append(json.loads(s))
    return items


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Ukur precision & recall retrieval CognitiveMemory atas kueri berlabel relevansi."
    )
    parser.add_argument("--memory", required=True, help="Path berkas atau direktori CognitiveMemory.")
    parser.add_argument("--queries", required=True, help="Path kueri JSON/JSONL berlabel relevant_ids.")
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
        help=f"Batas default hasil recall per kueri (default: {DEFAULT_LIMIT}).",
    )
    parser.add_argument("--out", help="Path output JSON opsional (default stdout).")
    args = parser.parse_args(argv)

    retriever = None
    try:
        queries = _load_queries(Path(args.queries))
        retriever = make_cognitive_memory_cached_retriever(Path(args.memory))
        report = evaluate_recall_precision(
            queries,
            retriever,
            default_limit=args.limit,
        )
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    finally:
        cleanup_dir = getattr(retriever, "_cleanup_dir", None)
        if cleanup_dir is not None:
            shutil.rmtree(cleanup_dir, ignore_errors=True)

    payload = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(payload, encoding="utf-8")
    else:
        sys.stdout.write(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
