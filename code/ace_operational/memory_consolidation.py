"""Distiler konsolidasi memori episodik menjadi rekaman semantik tertambat (AG61).

Membaca log ``CognitiveMemory`` secara read-only, mengelompokkan episode
terkait, menyimpan snapshot pra-distilasi untuk kebutuhan rollback, serta
menerbitkan kandidat rekaman semantik yang setiap klaimnya wajib menunjuk
ID episode sumber yang sah (klaim tanpa sumber ditolak fail-closed).
Tanpa impor maupun wiring ke engine.
"""

from __future__ import annotations

from collections import defaultdict
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Callable, Collection, Mapping, Sequence


SCHEMA = "ace.memory-consolidation.v1"


def load_active_episodes(log_path: Path) -> tuple[list[dict[str, Any]], bytes]:
    """Muat semua rekaman ``episodic`` aktif dari memory.jsonl tanpa mengubah log."""
    path = Path(log_path)
    raw_bytes = path.read_bytes()
    records: dict[str, dict[str, Any]] = {}
    superseded: set[str] = set()

    for line in raw_bytes.decode("utf-8").splitlines():
        s = line.strip()
        if not s:
            continue
        entry = json.loads(s)
        ev = entry.get("event") if isinstance(entry, Mapping) else None
        if not isinstance(ev, Mapping):
            continue
        etype = ev.get("type")
        if etype == "record" and isinstance(ev.get("record"), Mapping):
            rec = dict(ev["record"])
            rid = str(rec.get("id") or "")
            if rid:
                records[rid] = rec
        elif etype == "supersede":
            superseded.add(str(ev.get("record_id") or ""))
        elif etype == "tombstone":
            records.pop(str(ev.get("record_id") or ""), None)

    episodes = [
        records[rid]
        for rid in sorted(records)
        if rid not in superseded and records[rid].get("kind") == "episodic"
    ]
    return episodes, raw_bytes


def default_cluster_key(episode: Mapping[str, Any]) -> str:
    content = episode.get("content")
    if isinstance(content, Mapping):
        for field in ("topic", "domain", "cluster", "family"):
            val = content.get(field)
            if isinstance(val, str) and val.strip():
                return val.strip()
    return str(episode.get("kind") or "episodic")


def validate_consolidated_claims(
    claims: Sequence[Mapping[str, Any]],
    valid_episode_ids: Collection[str],
) -> None:
    """Pastikan tiap klaim semantik menunjuk minimal satu ID episode sumber yang sah."""
    if not isinstance(claims, Sequence) or isinstance(claims, (str, bytes)) or not claims:
        raise ValueError("Daftar klaim semantik tidak boleh kosong.")
    valid_set = set(valid_episode_ids)
    for idx, claim in enumerate(claims):
        if not isinstance(claim, Mapping):
            raise ValueError(f"Klaim[{idx}] wajib berupa mapping.")
        stmt = claim.get("statement") or claim.get("claim")
        if not isinstance(stmt, str) or not stmt.strip():
            raise ValueError(f"Klaim[{idx}] wajib memiliki statement tak-kosong.")
        sources = claim.get("source_episodes")
        if not isinstance(sources, list) or not sources or not all(
            isinstance(ep_id, str) and ep_id.strip() for ep_id in sources
        ):
            raise ValueError(
                f"Klaim[{idx}] wajib memiliki daftar 'source_episodes' tak-kosong (klaim tanpa sumber ditolak)."
            )
        unknown = [ep_id for ep_id in sources if ep_id not in valid_set]
        if unknown:
            raise ValueError(
                f"Klaim[{idx}] menunjuk source_episodes tidak dikenal: {unknown}"
            )


def build_semantic_record(
    cluster: str,
    claims: Sequence[Mapping[str, Any]],
    valid_episode_ids: Collection[str],
) -> dict[str, Any]:
    """Validasi seluruh klaim lalu kembalikan struktur kandidat rekaman semantik."""
    validate_consolidated_claims(claims, valid_episode_ids)
    all_sources = sorted(
        {
            ep_id
            for claim in claims
            for ep_id in claim["source_episodes"]
        }
    )
    return {
        "kind": "semantic",
        "cluster": cluster,
        "content": {
            "topic": cluster,
            "claims": [dict(c) for c in claims],
            "consolidated_from_episodes": all_sources,
        },
        "source": {
            "kind": "consolidation",
            "ref": f"episodes:{','.join(all_sources)}",
        },
        "source_episodes": all_sources,
    }


def save_pre_distillation_snapshot(
    raw_bytes: bytes,
    snapshot_dir: Path,
    *,
    source_name: str = "memory.jsonl",
) -> dict[str, Any]:
    """Simpan snapshot biner log pra-distilasi + manifes SHA-256 secara atomik."""
    sdir = Path(snapshot_dir)
    sdir.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(raw_bytes).hexdigest()
    backup_file = sdir / f"{source_name}.{digest[:12]}.bak"
    tmp_bak = sdir / f".{backup_file.name}.tmp"
    tmp_bak.write_bytes(raw_bytes)
    os.replace(tmp_bak, backup_file)

    manifest = {
        "schema": SCHEMA,
        "source_name": source_name,
        "source_sha256": digest,
        "bytes": len(raw_bytes),
        "snapshot_file": backup_file.name,
    }
    manifest_file = sdir / "snapshot_manifest.json"
    tmp_man = sdir / ".snapshot_manifest.json.tmp"
    tmp_man.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp_man, manifest_file)
    return {**manifest, "snapshot_path": str(backup_file), "manifest_path": str(manifest_file)}


def restore_pre_distillation_snapshot(snapshot_dir: Path, target_path: Path) -> dict[str, Any]:
    """Pulihkan isi log dari snapshot pra-distilasi setelah memverifikasi SHA-256."""
    sdir = Path(snapshot_dir)
    manifest = json.loads((sdir / "snapshot_manifest.json").read_text(encoding="utf-8"))
    bak_bytes = (sdir / manifest["snapshot_file"]).read_bytes()
    actual_sha = hashlib.sha256(bak_bytes).hexdigest()
    if actual_sha != manifest["source_sha256"]:
        raise ValueError("Hash snapshot pra-distilasi tidak cocok, rollback dibatalkan.")
    target = Path(target_path)
    tmp = target.parent / f".{target.name}.rollback.tmp"
    tmp.write_bytes(bak_bytes)
    os.replace(tmp, target)
    return {"restored_path": str(target), "sha256": actual_sha, "bytes": len(bak_bytes)}


def _default_synthesizer(cluster: str, cluster_episodes: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    claims: list[dict[str, Any]] = []
    # Satukan episode berkesimpulan identik; atau catat setiap ringkasan bertambat episode sumbernya.
    by_fact: dict[str, list[str]] = defaultdict(list)
    for ep in cluster_episodes:
        content = ep.get("content")
        if isinstance(content, Mapping):
            text = str(
                content.get("fact")
                or content.get("observation")
                or content.get("summary")
                or json.dumps(content, sort_keys=True, ensure_ascii=False)
            )
        else:
            text = str(content)
        by_fact[text].append(str(ep["id"]))

    for text in sorted(by_fact):
        ep_ids = sorted(by_fact[text])
        claims.append(
            {
                "statement": f"[{cluster}] {text}",
                "source_episodes": ep_ids,
                "support_count": len(ep_ids),
            }
        )
    return claims


def distill_memory_log(
    log_path: Path,
    *,
    snapshot_dir: Path,
    cluster_fn: Callable[[Mapping[str, Any]], str] = default_cluster_key,
    synthesizer: Callable[[str, Sequence[Mapping[str, Any]]], Sequence[Mapping[str, Any]]] = _default_synthesizer,
    min_cluster_size: int = 2,
) -> dict[str, Any]:
    """Distilasi episode dari CognitiveMemory JSONL menjadi rekaman semantik bertambat."""
    if min_cluster_size < 1:
        raise ValueError("min_cluster_size minimal 1")
    episodes, raw_bytes = load_active_episodes(Path(log_path))
    snapshot_info = save_pre_distillation_snapshot(
        raw_bytes, Path(snapshot_dir), source_name=Path(log_path).name
    )

    valid_ep_ids = {str(ep["id"]) for ep in episodes}
    clusters: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for ep in episodes:
        clusters[cluster_fn(ep)].append(ep)

    semantic_records: list[dict[str, Any]] = []
    skipped_small_clusters: list[dict[str, Any]] = []
    for cluster in sorted(clusters):
        eps = clusters[cluster]
        if len(eps) < min_cluster_size:
            skipped_small_clusters.append({"cluster": cluster, "episode_count": len(eps)})
            continue
        raw_claims = synthesizer(cluster, eps)
        semantic_records.append(build_semantic_record(cluster, raw_claims, valid_ep_ids))

    return {
        "schema": SCHEMA,
        "source_log": str(log_path),
        "source_sha256": snapshot_info["source_sha256"],
        "snapshot": snapshot_info,
        "total_active_episodes": len(episodes),
        "consolidated_cluster_count": len(semantic_records),
        "skipped_small_clusters": skipped_small_clusters,
        "semantic_records": semantic_records,
    }
