"""Reranker kandidat retrieval berjangkar peta bukti frontier & skor kepercayaan (AG59).

Beroperasi sebagai pustaka murni (tanpa impor engine) untuk menyusun ulang
peringkat kandidat berdasarkan:
1. Status peta bukti frontier (wajib ``KNOWN_AND_TESTED`` beserta ``evidence_ref``
   tak-kosong agar dinilai teruji & tertambat),
2. Skor kepercayaan (``confidence``) per record,
3. Skor kemiripan awal kandidat.

Pada kemiripan yang setara, kandidat yang belum teruji (atau tanpa ``evidence_ref``)
wajib turun peringkat di bawah kandidat yang telah teruji.
"""

from __future__ import annotations

from typing import Any, Mapping, Protocol, Sequence


TESTED_STATUS = "KNOWN_AND_TESTED"


class FrontierEvidenceLookup(Protocol):
    def get_frontier_entry(self, key: str) -> Mapping[str, Any] | None: ...


def _extract_candidate_keys_and_refs(candidate: Mapping[str, Any]) -> tuple[list[str], list[str]]:
    rec = candidate.get("record")
    rec_map = rec if isinstance(rec, Mapping) else {}
    keys: list[str] = []
    refs: list[str] = []

    for src in (candidate, rec_map):
        for kf in ("frontier_key", "skill_name", "topic", "id"):
            val = src.get(kf)
            if isinstance(val, str) and val.strip():
                keys.append(val.strip())
        ev_refs = src.get("evidence_refs")
        if isinstance(ev_refs, Sequence) and not isinstance(ev_refs, (str, bytes)):
            for item in ev_refs:
                if isinstance(item, str) and item.strip():
                    refs.append(item.strip())
        ev_single = src.get("evidence_ref")
        if isinstance(ev_single, str) and ev_single.strip():
            refs.append(ev_single.strip())
        source_obj = src.get("source")
        if isinstance(source_obj, Mapping):
            sref = source_obj.get("ref")
            if isinstance(sref, str) and sref.strip():
                refs.append(sref.strip())

    return list(dict.fromkeys(keys)), list(dict.fromkeys(refs))


def _lookup_frontier(
    frontier: Mapping[str, Mapping[str, Any]] | FrontierEvidenceLookup,
    keys: Sequence[str],
    refs: Sequence[str],
) -> tuple[bool, str | None, str | None]:
    def _get(k: str) -> Mapping[str, Any] | None:
        if isinstance(frontier, Mapping):
            entry = frontier.get(k)
            return entry if isinstance(entry, Mapping) else None
        return frontier.get_frontier_entry(k)

    best_status: str | None = None
    best_ref: str | None = None

    for key in list(keys) + list(refs):
        entry = _get(key)
        if not entry:
            continue
        status = str(entry.get("status") or "").strip()
        ev_ref = entry.get("evidence_ref")
        ev_str = ev_ref.strip() if isinstance(ev_ref, str) and ev_ref.strip() else None
        if status == TESTED_STATUS and ev_str is not None:
            # Bila kandidat membawa refs eksplisit, cocokkan minimal satu atau terima bukti frontier terikat.
            if not refs or ev_str in refs or key in refs or key in keys:
                return True, status, ev_str
        if best_status is None:
            best_status = status or None
            best_ref = ev_str

    return False, best_status, best_ref


def rerank_candidates(
    candidates: Sequence[Mapping[str, Any]],
    frontier: Mapping[str, Mapping[str, Any]] | FrontierEvidenceLookup,
    *,
    similarity_weight: float = 0.55,
    confidence_weight: float = 0.15,
    tested_bonus: float = 0.30,
    untested_penalty: float = 0.20,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Peringkat ulang kandidat memakai status frontier teruji+evidence dan confidence."""
    if not candidates:
        return []

    scored_rows: list[tuple[bool, float, str, dict[str, Any]]] = []
    for item in candidates:
        cid = str(item.get("id") or "")
        if not cid:
            raise ValueError("Setiap kandidat reranker wajib memiliki 'id'")
        rec = item.get("record")
        rec_map = rec if isinstance(rec, Mapping) else {}

        sim_raw = item.get("score", item.get("similarity", 0.0))
        similarity = float(sim_raw)
        conf_raw = item.get("confidence", rec_map.get("confidence", 0.5))
        confidence = max(0.0, min(1.0, float(conf_raw)))

        keys, refs = _extract_candidate_keys_and_refs(item)
        frontier_verified, frontier_status, matched_ref = _lookup_frontier(
            frontier, keys, refs
        )

        rerank_score = (
            similarity_weight * similarity
            + confidence_weight * confidence
            + (tested_bonus if frontier_verified else -untested_penalty)
        )
        rerank_score = round(rerank_score, 6)

        enriched = dict(item)
        enriched.update(
            {
                "id": cid,
                "base_similarity": round(similarity, 6),
                "confidence": round(confidence, 6),
                "frontier_verified": frontier_verified,
                "frontier_status": frontier_status,
                "frontier_evidence_ref": matched_ref,
                "rerank_score": rerank_score,
            }
        )
        # Kunci urutan: skor akhir rerank (bonus/penalti sudah menggeser yg belum teruji ke bawah)
        scored_rows.append((frontier_verified, rerank_score, cid, enriched))

    scored_rows.sort(key=lambda row: (-row[1], not row[0], row[2]))
    ranked = [row[3] for row in scored_rows]
    return ranked[:limit] if limit is not None else ranked
