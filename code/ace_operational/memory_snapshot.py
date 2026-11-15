"""Portable Git-backed memory, lexicon, and dialogue corpus snapshot for ACE.

Exports ACE's learned Indonesian lexicon, non-private OMEGA-07 long-term memories,
and dynamic dialogue corpus into `data/ace_seed_snapshot.json` inside the repository,
and automatically seeds fresh workspaces (such as Manus or new VMs) idempotently.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

from .memory_bridge import ConversationalMemoryManager
from .speech_acquisition import SpeechDevelopmentEngine
from .store import OperationalStore

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SNAPSHOT_PATH = REPO_ROOT / "data" / "ace_seed_snapshot.json"


def _default_workspace() -> Path:
    return Path.home() / ".local" / "share" / "ace" / "workspace"


def export_snapshot(
    workspace: Path | None = None,
    snapshot_path: Path | None = None,
) -> dict[str, Any]:
    """Export lexicon, non-private memories, and dialogue corpus to a portable JSON file."""
    ws = Path(workspace or _default_workspace())
    out_path = Path(snapshot_path or DEFAULT_SNAPSHOT_PATH)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    store = OperationalStore(ws)
    speech = SpeechDevelopmentEngine(store)
    mem_mgr = ConversationalMemoryManager(store)

    lexicon = [
        {
            "word": str(item.get("word") or "").strip().lower(),
            "meaning_id": str(item.get("meaning_id") or "").strip(),
            "role": str(item.get("role") or "").strip(),
        }
        for item in speech.list_lexicon()
        if item.get("word") and item.get("meaning_id")
    ]

    snap = mem_mgr.list_snapshot()
    memories: list[dict[str, Any]] = []
    for rec in snap.get("active_records", []):
        if str(rec.get("sensitivity") or "").lower() == "private":
            continue
        text = mem_mgr.format_record_line(rec).strip()
        if text:
            memories.append(
                {
                    "text": text,
                    "kind": str(rec.get("kind") or "semantic"),
                    "confidence": float(rec.get("confidence") or 0.9),
                }
            )

    corpus_entries: list[dict[str, Any]] = []
    corpus_file = ws / "projects" / "bahasa" / "dialog_corpus.jsonl"
    if corpus_file.exists():
        for raw in corpus_file.read_text(encoding="utf-8").splitlines()[-250:]:
            if not raw.strip():
                continue
            try:
                corpus_entries.append(json.loads(raw))
            except ValueError:
                continue

    payload = {
        "schema": "ace.seed_snapshot.v1",
        "exported_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "vocab_count": len(lexicon),
        "memories_count": len(memories),
        "dialog_corpus_count": len(corpus_entries),
        "lexicon": lexicon,
        "memories": memories,
        "dialog_corpus": corpus_entries,
    }
    digest = hashlib.sha256(
        json.dumps(
            {"lexicon": lexicon, "memories": memories, "corpus": len(corpus_entries)},
            sort_keys=True,
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()[:16]
    payload["snapshot_version"] = digest

    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "snapshot_path": str(out_path),
        "snapshot_version": digest,
        "vocab_count": len(lexicon),
        "memories_count": len(memories),
        "dialog_corpus_count": len(corpus_entries),
    }


def import_snapshot_if_needed(
    store: OperationalStore,
    snapshot_path: Path | None = None,
) -> dict[str, Any]:
    """Idempotently seed a workspace from the Git-backed snapshot if not yet applied."""
    src = Path(snapshot_path or DEFAULT_SNAPSHOT_PATH)
    if not src.is_file():
        return {"applied": False, "reason": "snapshot_not_found"}

    try:
        data = json.loads(src.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"applied": False, "reason": "snapshot_unreadable"}

    version = str(data.get("snapshot_version") or "")
    if version and store.get_meta("seed_snapshot_version", "") == version:
        return {"applied": False, "reason": "already_applied", "snapshot_version": version}

    speech = SpeechDevelopmentEngine(store)
    existing_words = {str(w.get("word") or "").lower() for w in speech.list_lexicon()}
    words_added = 0
    for item in data.get("lexicon", []):
        word = str(item.get("word") or "").strip().lower()
        meaning = str(item.get("meaning_id") or "").strip()
        role = str(item.get("role") or "").strip()
        if not word or not meaning or word in existing_words:
            continue
        res = speech.teach_word(word, meaning, role=role)
        if res.get("accepted"):
            existing_words.add(word)
            words_added += 1

    mem_mgr = ConversationalMemoryManager(store)
    existing_mem_texts = {
        mem_mgr.format_record_line(rec).strip()
        for rec in mem_mgr.list_snapshot().get("active_records", [])
    }
    memories_added = 0
    for mem in data.get("memories", []):
        text = str(mem.get("text") or "").strip()
        if not text or text in existing_mem_texts:
            continue
        res = mem_mgr.remember_statement(
            text,
            confidence=float(mem.get("confidence") or 0.9),
            sensitivity="internal",
            source_kind="operator",
        )
        if res.get("stored"):
            existing_mem_texts.add(text)
            memories_added += 1

    corpus_added = 0
    corpus_entries = data.get("dialog_corpus", [])
    if corpus_entries:
        corpus_file = Path(store.workspace) / "projects" / "bahasa" / "dialog_corpus.jsonl"
        if not corpus_file.exists():
            corpus_file.parent.mkdir(parents=True, exist_ok=True)
            corpus_file.write_text(
                "\n".join(json.dumps(entry, ensure_ascii=False) for entry in corpus_entries) + "\n",
                encoding="utf-8",
            )
            corpus_added = len(corpus_entries)

    if version:
        store.set_meta("seed_snapshot_version", version)

    return {
        "applied": True,
        "snapshot_version": version,
        "words_added": words_added,
        "memories_added": memories_added,
        "corpus_added": corpus_added,
    }


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Export or import ACE seed snapshot")
    parser.add_argument("action", choices=["export", "import"], default="export", nargs="?")
    parser.add_argument("--workspace", default=None)
    parser.add_argument("--snapshot", default=None)
    args = parser.parse_args()
    ws = Path(args.workspace) if args.workspace else _default_workspace()
    snap = Path(args.snapshot) if args.snapshot else DEFAULT_SNAPSHOT_PATH
    if args.action == "export":
        print(json.dumps(export_snapshot(ws, snap), ensure_ascii=False, indent=2))
    else:
        print(json.dumps(import_snapshot_if_needed(OperationalStore(ws), snap), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
