#!/usr/bin/env python3
"""C4 — Permukaan CLI Recall & Introspeksi Lapis 3 (strictly read-only).

Menjawab kueri atau soal introspeksi di atas snapshot memori (``memory.jsonl``,
``ace_seed_snapshot.json``, snapshot datar JSONL) dan korpus dokumen
``handover/`` + ledger repo secara baca-saja.

Aturan integritas:
1. Setiap jawaban WAJIB membawa pointer sumber terverifikasi (``path``,
   ``line_start``/``line_end`` atau ``record_id``, ``sha256``, ``excerpt``).
2. Bukti terjangkar (``evidence``/``operator``/dokumen handover) selalu
   diprioritaskan di atas rekaman ``model`` (*guess*); tebakan ``model`` ditandai
   ``guess_only=True`` dan ``status="GUESS_ONLY_UNVERIFIED"``.
3. Bila tak ada kecocokan memadai, perkakas wajib abstain secara jujur
   (``status="NO_VERIFIED_EVIDENCE"``) tanpa memfabrikasi sitasi.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys
from typing import Any


SCHEMA = "ace.introspect-recall.v1"

_STOPWORDS = frozenset(
    {
        "apa", "apakah", "bagaimana", "berapa", "bila", "bisa", "adalah", "akan",
        "atau", "dan", "dari", "dengan", "di", "dalam", "ini", "itu", "ke",
        "pada", "untuk", "yang", "sebagai", "status", "ace",
        "what", "when", "where", "which", "who", "whom", "why", "how", "is",
        "are", "was", "were", "can", "could", "the", "and", "for", "with",
        "from", "into", "that", "this", "of", "in", "on", "to", "a", "an",
    }
)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _rel_or_posix(path: Path, root: Path) -> str:
    try:
        return PurePosixPath(path.resolve().relative_to(root.resolve())).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _tokenize(text: str) -> list[str]:
    norm = text.lower().replace("-", "_").replace(".", "_")
    raw = re.findall(r"[a-z0-9_]+", norm)
    tokens: list[str] = []
    for tok in raw:
        if len(tok) < 2 or tok in _STOPWORDS:
            continue
        tokens.append(tok)
        if "_" in tok:
            for sub in tok.split("_"):
                if len(sub) >= 2 and sub not in _STOPWORDS:
                    tokens.append(sub)
    return tokens


# ---------------------------------------------------------------------------
# Read-only corpus & memory indexers
# ---------------------------------------------------------------------------

def _index_memory_entries(
    memory_paths: list[Path],
    root: Path,
    *,
    include_superseded: bool,
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for raw_p in memory_paths:
        p = raw_p.resolve()
        if p.is_dir():
            cand = p / "memory.jsonl"
            if not cand.is_file():
                continue
            p = cand
        elif not p.is_file():
            continue

        rel = _rel_or_posix(p, root)
        sha = _sha256_file(p)

        if p.suffix.lower() == ".json":
            try:
                data = json.loads(p.read_text(encoding="utf-8", errors="replace"))
            except json.JSONDecodeError:
                continue
            if isinstance(data, dict) and data.get("schema") == "ace.seed_snapshot.v1":
                for idx, item in enumerate(data.get("memories") or [], start=1):
                    if not isinstance(item, dict):
                        continue
                    txt = str(item.get("text") or "").strip()
                    if not txt:
                        continue
                    entries.append(
                        {
                            "corpus_kind": "memory",
                            "record_id": f"seed_{idx:03d}",
                            "kind": str(item.get("kind") or "semantic"),
                            "source_kind": "operator",
                            "status": "active",
                            "confidence": float(item.get("confidence") or 0.9),
                            "text": txt,
                            "title": f"seed_snapshot:{item.get('kind', 'memory')}",
                            "pointer": {"path": rel, "sha256": sha, "record_id": f"seed_{idx:03d}", "excerpt": txt[:140]},
                        }
                    )
            continue

        # JSONL: support CognitiveMemory event log and flat snapshot lines
        records_by_id: dict[str, dict[str, Any]] = {}
        saw_events = False
        flat_items: list[dict[str, Any]] = []
        for line_no, raw in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
            stripped = raw.strip()
            if not stripped:
                continue
            try:
                obj = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            if not isinstance(obj, dict):
                continue
            if "event" in obj and isinstance(obj.get("event"), dict):
                saw_events = True
                ev = obj["event"]
                etype = ev.get("type")
                if etype == "record" and isinstance(ev.get("record"), dict):
                    rec = dict(ev["record"])
                    rec["_line"] = line_no
                    records_by_id[str(rec.get("id") or f"line_{line_no}")] = rec
                elif etype == "supersede":
                    rid = str(ev.get("record_id") or "")
                    if rid in records_by_id:
                        records_by_id[rid]["status"] = "superseded"
                elif etype == "tombstone":
                    records_by_id.pop(str(ev.get("record_id") or ""), None)
            else:
                flat_items.append((line_no, obj))

        if saw_events:
            for rec in sorted(records_by_id.values(), key=lambda r: (int(r.get("written_seq") or 0), str(r.get("id") or ""))):
                st = str(rec.get("status") or "active")
                if st == "superseded" and not include_superseded:
                    continue
                content = rec.get("content") if isinstance(rec.get("content"), dict) else {}
                skind = str((rec.get("source") or {}).get("kind") or "model")
                text = " | ".join(f"{k}: {v}" for k, v in sorted(content.items()) if v is not None)
                summary = str(content.get("event") or content.get("text") or content.get("name") or text)
                rid = str(rec.get("id") or "")
                entries.append(
                    {
                        "corpus_kind": "memory",
                        "record_id": rid,
                        "kind": str(rec.get("kind") or "episodic"),
                        "source_kind": skind,
                        "status": st,
                        "confidence": float(rec.get("confidence") or 0.5),
                        "text": f"{summary} ({text})",
                        "title": f"memory[{rec.get('kind')}/{skind}] {rid}",
                        "pointer": {
                            "path": rel,
                            "sha256": sha,
                            "line": rec.get("_line"),
                            "record_id": rid,
                            "seq": rec.get("written_seq"),
                            "excerpt": summary[:140],
                        },
                    }
                )
        else:
            for line_no, obj in flat_items:
                st = str(obj.get("status") or "active")
                if st == "superseded" and not include_superseded:
                    continue
                content = obj.get("content") if isinstance(obj.get("content"), dict) else obj
                skind = str((obj.get("source") or {}).get("kind") or obj.get("source_kind") or "operator")
                summary = str(obj.get("summary") or content.get("event") or content.get("text") or _canonical_json(content))
                rid = str(obj.get("id") or obj.get("episode_id") or f"line_{line_no}")
                entries.append(
                    {
                        "corpus_kind": "memory",
                        "record_id": rid,
                        "kind": str(obj.get("kind") or "episodic"),
                        "source_kind": skind,
                        "status": st,
                        "confidence": float(obj.get("confidence") or 0.5),
                        "text": f"{summary} {_canonical_json(content)}",
                        "title": f"snapshot[{skind}] {rid}",
                        "pointer": {"path": rel, "sha256": sha, "line": line_no, "record_id": rid, "excerpt": summary[:140]},
                    }
                )
    return entries


def _chunk_markdown_doc(path: Path, root: Path, *, max_chunk_lines: int = 18) -> list[dict[str, Any]]:
    rel = _rel_or_posix(path, root)
    sha = _sha256_file(path)
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    if not lines:
        return []

    doc_title = ""
    for line in lines[:5]:
        if line.strip().startswith("#"):
            doc_title = line.strip().lstrip("#").strip()
            break
    stem_words = path.stem.replace("_", " ").replace("-", " ")

    chunks: list[dict[str, Any]] = []
    cur_heading = doc_title or path.stem
    buf: list[tuple[int, str]] = []

    def flush() -> None:
        if not buf:
            return
        non_empty = [ln for _, ln in buf if ln.strip()]
        if not non_empty:
            buf.clear()
            return
        start_ln = buf[0][0]
        end_ln = buf[-1][0]
        body_text = "\n".join(ln for _, ln in buf)
        excerpt = non_empty[0].strip()[:140]
        chunks.append(
            {
                "corpus_kind": "handover_doc",
                "record_id": f"{rel}#L{start_ln}-L{end_ln}",
                "kind": "document",
                "source_kind": "evidence_doc",
                "status": "active",
                "confidence": 0.95,
                "title": f"{path.name} — {cur_heading}",
                "head_text": f"{stem_words} {doc_title} {cur_heading}",
                "text": body_text,
                "pointer": {
                    "path": rel,
                    "sha256": sha,
                    "line_start": start_ln,
                    "line_end": end_ln,
                    "line": start_ln,
                    "excerpt": excerpt,
                },
            }
        )
        buf.clear()

    for line_no, raw in enumerate(lines, start=1):
        if raw.strip().startswith("#"):
            flush()
            cur_heading = raw.strip().lstrip("#").strip()
            buf.append((line_no, raw))
        else:
            buf.append((line_no, raw))
            if len(buf) >= max_chunk_lines:
                flush()
    flush()
    return chunks


def _collect_handover_docs(root: Path) -> list[dict[str, Any]]:
    doc_paths: list[Path] = []
    for fixed in ("STATUS.md", "RESEARCH_LEDGER.md"):
        p = root / fixed
        if p.is_file():
            doc_paths.append(p)
    handover_dir = root / "handover"
    if handover_dir.is_dir():
        doc_paths.extend(sorted(handover_dir.glob("*.md")))
    research_dir = root / "docs" / "research"
    if research_dir.is_dir():
        for p in sorted(research_dir.glob("ACE_OMEGA_CHECKPOINT_2026111*_ADDENDUM5[89].md")):
            doc_paths.append(p)
        for p in sorted(research_dir.glob("ACE_OMEGA_CHECKPOINT_2026111*_ADDENDUM60.md")):
            doc_paths.append(p)
    selfmodel_res = root / "docs" / "ACE_SELFMODEL_RESULTS_V1.md"
    if selfmodel_res.is_file():
        doc_paths.append(selfmodel_res)

    seen: set[Path] = set()
    chunks: list[dict[str, Any]] = []
    for p in doc_paths:
        res = p.resolve()
        if res in seen:
            continue
        seen.add(res)
        chunks.extend(_chunk_markdown_doc(res, root))
    return chunks


# ---------------------------------------------------------------------------
# Scoring & Query Engine
# ---------------------------------------------------------------------------

_TIER_BONUS = {
    "evidence": 3.0,
    "evidence_doc": 2.5,
    "operator": 2.0,
    "external": 1.0,
    "model": -2.0,
}


def query_introspection(
    query: str,
    *,
    root: str | Path = ".",
    memory_paths: list[str | Path] | None = None,
    scope: str = "all",
    include_superseded: bool = False,
    top_k: int = 5,
    min_token_hits: int = 1,
) -> dict[str, Any]:
    """Jalankan satu kueri recall/introspeksi baca-saja dengan pointer sumber wajib."""
    repo_root = Path(root).resolve()
    q_tokens = list(dict.fromkeys(_tokenize(query)))

    if not q_tokens:
        return {
            "schema": SCHEMA,
            "read_only": True,
            "query": query,
            "status": "NO_VERIFIED_EVIDENCE",
            "reason": "Kueri tidak memiliki token informatif.",
            "answer": "Tidak ada bukti terverifikasi karena kueri kosong atau hanya kata umum.",
            "hits": [],
            "citations": [],
        }

    candidates: list[dict[str, Any]] = []
    if scope in ("all", "memory"):
        resolved_mem: list[Path] = [Path(p) for p in (memory_paths or [])]
        if not resolved_mem:
            seed = repo_root / "data" / "ace_seed_snapshot.json"
            if seed.is_file():
                resolved_mem.append(seed)
        candidates.extend(_index_memory_entries(resolved_mem, repo_root, include_superseded=include_superseded))
    if scope in ("all", "handover"):
        candidates.extend(_collect_handover_docs(repo_root))

    q_set = set(q_tokens)
    scored: list[tuple[float, int, dict[str, Any]]] = []
    for entry in candidates:
        head_toks = set(_tokenize(str(entry.get("head_text") or entry.get("title") or "")))
        body_toks = set(_tokenize(str(entry.get("text") or "")))
        all_toks = head_toks | body_toks
        overlap = q_set & all_toks
        hit_cnt = len(overlap)
        if hit_cnt < min_token_hits:
            continue
        if len(q_set) >= 3 and hit_cnt < 2 and len(overlap & head_toks) == 0:
            continue

        head_hits = len(q_set & head_toks)
        coverage = hit_cnt / len(q_set)
        tier_score = _TIER_BONUS.get(str(entry.get("source_kind") or ""), 0.0)
        status_penalty = -4.0 if entry.get("status") == "superseded" else 0.0
        mem_bonus = 1.5 if entry["corpus_kind"] == "memory" else 0.0
        score = round(coverage * 10.0 + hit_cnt * 1.2 + head_hits * 2.5 + tier_score + mem_bonus + status_penalty, 4)
        scored.append((score, hit_cnt, entry))

    scored.sort(
        key=lambda item: (
            -item[0],
            -item[1],
            str(item[2]["pointer"]["path"]),
            int(item[2]["pointer"].get("line") or 0),
        )
    )
    selected = scored[:top_k]

    if not selected:
        return {
            "schema": SCHEMA,
            "read_only": True,
            "query": query,
            "status": "NO_VERIFIED_EVIDENCE",
            "reason": "Tidak ditemukan rekaman memori atau dokumen handover yang cocok memadai.",
            "answer": f"Abstain jujur: tidak ditemukan bukti terverifikasi untuk '{query}'.",
            "hits": [],
            "citations": [],
        }

    verified_hits = [e for _, _, e in selected if e["source_kind"] != "model"]
    only_guesses = len(verified_hits) == 0
    status = "GUESS_ONLY_UNVERIFIED" if only_guesses else "VERIFIED_ANSWER"

    hits_out: list[dict[str, Any]] = []
    citations: list[dict[str, Any]] = []
    seen_cites: set[tuple[str, int | None, str | None]] = set()
    for score, hit_cnt, entry in selected:
        is_guess = entry["source_kind"] == "model"
        ptr = dict(entry["pointer"])
        hits_out.append(
            {
                "record_id": entry["record_id"],
                "corpus_kind": entry["corpus_kind"],
                "source_kind": entry["source_kind"],
                "status": entry["status"],
                "guess_only": is_guess,
                "score": score,
                "matched_tokens": hit_cnt,
                "title": entry["title"],
                "excerpt": ptr.get("excerpt") or "",
                "source": ptr,
            }
        )
        ckey = (ptr["path"], ptr.get("line"), ptr.get("record_id"))
        if ckey not in seen_cites:
            seen_cites.add(ckey)
            citations.append(ptr)

    top_entry = selected[0][2]
    prefix = "[PERINGATAN: HANYA TEBAKAN MODEL BELUM TERVERIFIKASI] " if only_guesses else ""
    answer = f"{prefix}{top_entry['title']}: {top_entry['pointer']['excerpt']} [sumber: {top_entry['pointer']['path']}]"

    return {
        "schema": SCHEMA,
        "read_only": True,
        "query": query,
        "status": status,
        "guess_only": only_guesses,
        "answer": answer,
        "hits": hits_out,
        "citations": citations,
    }


def render_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Introspeksi & Recall ACE (C4)",
        "",
        f"- **Kueri**: `{result['query']}`",
        f"- **Status**: `{result['status']}` (`read_only={result['read_only']}`)",
        f"- **Ringkasan jawaban**: {result['answer']}",
        "",
        "## Bukti & Sitasi Terverifikasi",
        "",
    ]
    if not result["hits"]:
        lines.append("- _(Tidak ada bukti cocok — abstain jujur.)_")
    else:
        for h in result["hits"]:
            src = h["source"]
            loc = f"{src['path']}#L{src['line']}" if src.get("line") is not None else src["path"]
            guess_flag = " `[GUESS_ONLY]`" if h["guess_only"] else ""
            lines.append(
                f"- **{h['title']}**{guess_flag} (skor={h['score']}, sumber=`{loc}` sha=`{src['sha256'][:12]}`): {h['excerpt']}"
            )
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Akar repositori ACE")
    parser.add_argument("--memory", action="append", default=[], help="Path ke memory.jsonl/direktori/snapshot JSON")
    parser.add_argument("--query", default=None, help="Satu pertanyaan atau kueri recall")
    parser.add_argument("--questions-file", default=None, help="Berkas JSON/JSONL berisi daftar pertanyaan")
    parser.add_argument("--scope", choices=("all", "memory", "handover"), default="all")
    parser.add_argument("--include-superseded", action="store_true")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    args = parser.parse_args(argv)

    if not args.query and not args.questions_file:
        parser.error("Wajib memberi --query atau --questions-file.")

    if args.questions_file:
        raw_q = Path(args.questions_file).read_text(encoding="utf-8")
        queries = [
            item["query"] if isinstance(item, dict) else str(item)
            for item in json.loads(raw_q)
        ]
        results = [
            query_introspection(
                q,
                root=args.root,
                memory_paths=args.memory or None,
                scope=args.scope,
                include_superseded=args.include_superseded,
                top_k=args.top_k,
            )
            for q in queries
        ]
        print(json.dumps(results, indent=2, ensure_ascii=False))
        return 0

    res = query_introspection(
        args.query,
        root=args.root,
        memory_paths=args.memory or None,
        scope=args.scope,
        include_superseded=args.include_superseded,
        top_k=args.top_k,
    )
    if args.format == "markdown":
        print(render_markdown(res))
    else:
        print(json.dumps(res, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
