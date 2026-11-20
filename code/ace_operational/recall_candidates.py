"""Pembangkit kandidat retrieval hibrida (leksikal, embedding, provenance) (AG58).

Beroperasi murni sebagai pustaka atas ``Protocol`` store tanpa mengimpor engine:
1. Leksikal: tumpang tindih token antara kueri dan konten rekaman.
2. Embedding: kemiripan kosinus via fungsi ``embedder`` yang diinjeksi.
3. Provenance: telusur rantai referensi (``source.ref``, ``evidence_refs``, ``based_on``).
4. Gabung deterministik antar-jalur menjadi satu daftar peringkat terurut stabil.
"""

from __future__ import annotations

from collections import deque
import json
import math
import re
from typing import Any, Callable, Mapping, Protocol, Sequence


_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")


class CandidateMemoryStore(Protocol):
    def list_records(self) -> Sequence[Mapping[str, Any]]: ...


def _tokenize(text: str) -> set[str]:
    return {tok.lower() for tok in _TOKEN_RE.findall(text)}


def _record_text(record: Mapping[str, Any]) -> str:
    content = record.get("content", "")
    if isinstance(content, str):
        body = content
    else:
        body = json.dumps(content, sort_keys=True, ensure_ascii=False)
    kind = str(record.get("kind") or "")
    return f"{kind} {body}".strip()


def _record_refs(record: Mapping[str, Any]) -> list[str]:
    refs: list[str] = []
    src = record.get("source")
    if isinstance(src, Mapping):
        s_ref = src.get("ref")
        if isinstance(s_ref, str) and s_ref.strip():
            refs.append(s_ref.strip())
    for field in ("evidence_refs", "based_on"):
        vals = record.get(field)
        if isinstance(vals, Sequence) and not isinstance(vals, (str, bytes)):
            for item in vals:
                if isinstance(item, str) and item.strip():
                    refs.append(item.strip())
    return list(dict.fromkeys(refs))


def _cosine(vec_a: Sequence[float], vec_b: Sequence[float]) -> float:
    if len(vec_a) != len(vec_b) or not vec_a:
        raise ValueError("Dimensi vektor embedding tidak cocok atau kosong")
    dot = sum(float(a) * float(b) for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(float(a) * float(a) for a in vec_a))
    norm_b = math.sqrt(sum(float(b) * float(b) for b in vec_b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def lexical_candidates(
    query: str,
    store: CandidateMemoryStore,
    *,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Hasilkan kandidat dari tumpang tindih token kueri terhadap rekaman store."""
    q_tokens = _tokenize(query)
    if not q_tokens or limit <= 0:
        return []
    scored: list[tuple[float, str, dict[str, Any]]] = []
    for rec in store.list_records():
        rid = str(rec.get("id") or "")
        if not rid:
            continue
        r_tokens = _tokenize(_record_text(rec))
        overlap = q_tokens & r_tokens
        if not overlap:
            continue
        coverage = len(overlap) / len(q_tokens)
        jaccard = len(overlap) / len(q_tokens | r_tokens)
        score = round(0.7 * coverage + 0.3 * jaccard, 6)
        scored.append(
            (
                score,
                rid,
                {
                    "id": rid,
                    "channel": "lexical",
                    "score": score,
                    "matched_tokens": sorted(overlap),
                    "record": dict(rec),
                },
            )
        )
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [item[2] for item in scored[:limit]]


def embedding_candidates(
    query: str,
    store: CandidateMemoryStore,
    embedder: Callable[[str], Sequence[float]],
    *,
    limit: int = 10,
    min_score: float = 0.0,
) -> list[dict[str, Any]]:
    """Hasilkan kandidat berdasarkan kemiripan kosinus dari ``embedder`` yang diinjeksi."""
    if not callable(embedder):
        raise ValueError("embedder wajib berupa callable")
    if not query.strip() or limit <= 0:
        return []
    q_vec = list(embedder(query))
    scored: list[tuple[float, str, dict[str, Any]]] = []
    for rec in store.list_records():
        rid = str(rec.get("id") or "")
        if not rid:
            continue
        raw_vec = rec.get("embedding")
        r_vec = list(raw_vec) if isinstance(raw_vec, Sequence) and not isinstance(raw_vec, (str, bytes)) else list(embedder(_record_text(rec)))
        sim = round(_cosine(q_vec, r_vec), 6)
        if sim <= min_score:
            continue
        scored.append(
            (
                sim,
                rid,
                {
                    "id": rid,
                    "channel": "embedding",
                    "score": sim,
                    "record": dict(rec),
                },
            )
        )
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [item[2] for item in scored[:limit]]


def provenance_candidates(
    query: str,
    store: CandidateMemoryStore,
    *,
    seed_refs: Sequence[str] = (),
    max_hops: int = 2,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Telusuri kandidat lewat rantai referensi bersama (ref graph BFS terbatas)."""
    if max_hops < 0 or limit <= 0:
        return []
    records_by_id: dict[str, Mapping[str, Any]] = {}
    ref_to_records: dict[str, list[str]] = {}
    record_to_refs: dict[str, list[str]] = {}

    for rec in store.list_records():
        rid = str(rec.get("id") or "")
        if not rid:
            continue
        records_by_id[rid] = rec
        refs = _record_refs(rec)
        record_to_refs[rid] = refs
        for ref in refs:
            ref_to_records.setdefault(ref, []).append(rid)

    active_seeds: list[str] = [str(r).strip() for r in seed_refs if str(r).strip()]
    q_tokens = _tokenize(query)
    for ref in ref_to_records:
        if ref.lower() in q_tokens or ref in query:
            if ref not in active_seeds:
                active_seeds.append(ref)

    if not active_seeds:
        return []

    visited_records: dict[str, tuple[int, list[str]]] = {}
    visited_refs: set[str] = set()
    queue: deque[tuple[str, int, str]] = deque()
    for sref in active_seeds:
        visited_refs.add(sref)
        for rid in ref_to_records.get(sref, []):
            queue.append((rid, 0, sref))

    while queue:
        rid, hop, via_ref = queue.popleft()
        if rid not in visited_records:
            visited_records[rid] = (hop, [via_ref])
            if hop < max_hops:
                for next_ref in record_to_refs.get(rid, []):
                    if next_ref not in visited_refs:
                        visited_refs.add(next_ref)
                        for next_rid in ref_to_records.get(next_ref, []):
                            if next_rid not in visited_records:
                                queue.append((next_rid, hop + 1, next_ref))
        elif hop == visited_records[rid][0] and via_ref not in visited_records[rid][1]:
            visited_records[rid][1].append(via_ref)

    scored: list[tuple[float, str, dict[str, Any]]] = []
    for rid, (hop, via_refs) in visited_records.items():
        score = round(1.0 / (1.0 + hop), 6)
        scored.append(
            (
                score,
                rid,
                {
                    "id": rid,
                    "channel": "provenance",
                    "score": score,
                    "hop": hop,
                    "via_refs": sorted(via_refs),
                    "record": dict(records_by_id[rid]),
                },
            )
        )
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [item[2] for item in scored[:limit]]


def merge_candidates(
    channels: Mapping[str, Sequence[Mapping[str, Any]]],
    *,
    weights: Mapping[str, float] | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Gabungkan kandidat dari beberapa jalur secara deterministik (bobot + RRF ringan)."""
    if limit <= 0:
        return []
    default_weights = {"lexical": 1.0, "embedding": 1.0, "provenance": 0.9}
    active_weights = {**default_weights, **(dict(weights) if weights is not None else {})}

    merged: dict[str, dict[str, Any]] = {}
    for ch_name in sorted(channels):
        weight = float(active_weights.get(ch_name, 1.0))
        for rank, item in enumerate(channels[ch_name], 1):
            rid = str(item["id"])
            raw_score = float(item.get("score", 0.0))
            rrf_bonus = 0.1 / (10.0 + rank)
            contrib = weight * (raw_score + rrf_bonus)

            entry = merged.setdefault(
                rid,
                {
                    "id": rid,
                    "score": 0.0,
                    "channels": [],
                    "channel_scores": {},
                    "record": item.get("record"),
                },
            )
            entry["score"] = round(entry["score"] + contrib, 6)
            if ch_name not in entry["channels"]:
                entry["channels"].append(ch_name)
            entry["channel_scores"][ch_name] = round(raw_score, 6)
            if entry["record"] is None and item.get("record") is not None:
                entry["record"] = item["record"]

    ranked = sorted(
        merged.values(),
        key=lambda row: (-row["score"], -len(row["channels"]), row["id"]),
    )
    for row in ranked:
        row["channels"].sort()
    return ranked[:limit]
