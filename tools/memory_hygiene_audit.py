"""Audit kebersihan cognitive memory JSONL secara baca-saja (AG42).

Memeriksa rantai hash sesuai spesifikasi ``code/ace_operational/cognitive_memory.py``,
mendeteksi rekaman duplikat persis, referensi bukti (evidence ref) yatim/menggantung,
serta statistik kelengkapan provenance tanpa memodifikasi berkas memori sedikit pun.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Collection, Mapping, Sequence


SCHEMA = "ace.memory-hygiene-audit.v1"
GENESIS_PREV = "GENESIS"


def canonical_json(value: Any) -> str:
    """Serialisasi kanonis identik dengan _canonical di cognitive_memory.py."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def compute_entry_hash(prev: str, event: Any) -> str:
    """Hitung SHA-256 entri rantai hash kognitif dari ``prev`` dan ``event``."""
    raw = canonical_json({"prev": prev, "event": event}).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _content_key(kind: str, content: Any) -> tuple[str, str]:
    if isinstance(content, str):
        serialized = content
    else:
        serialized = canonical_json(content)
    return kind, hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _resolve_ref(
    ref: str,
    *,
    known_refs: Collection[str] | None,
    evidence_root: Path | None,
) -> bool:
    if known_refs is not None:
        if ref in known_refs:
            return True
    if evidence_root is not None:
        candidate = Path(ref)
        target = candidate if candidate.is_absolute() else (evidence_root / candidate)
        if target.exists():
            return True
    if known_refs is not None:
        return False
    # Tanpa known_refs eksplisit, path berkas (mengandung "/" atau ekstensi) diverifikasi di disk.
    if "/" in ref or ref.endswith((".json", ".jsonl", ".md", ".txt", ".py")):
        candidate = Path(ref)
        if candidate.exists():
            return True
        return False
    return True


def audit_memory_log(
    memory_path: Path,
    *,
    known_refs: Collection[str] | None = None,
    evidence_root: Path | None = None,
) -> dict[str, Any]:
    """Audit berkas log cognitive_memory JSONL secara read-only."""
    path = Path(memory_path)
    if evidence_root is None and path.parent.exists():
        evidence_root = path.parent
    known_set = set(known_refs) if known_refs is not None else None

    raw_lines = path.read_text(encoding="utf-8").splitlines()

    expected_prev = GENESIS_PREV
    expected_seq = 1
    chain_errors: list[dict[str, Any]] = []
    verified_entries = 0
    total_lines = 0

    seen_record_ids: set[str] = set()
    seen_anchors: set[str] = set()
    duplicate_ids: list[dict[str, Any]] = []
    content_buckets: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)

    orphan_evidence_refs: list[dict[str, Any]] = []
    orphan_event_refs: list[dict[str, Any]] = []

    total_records = 0
    with_source_dict = 0
    with_source_kind_and_ref = 0
    with_evidence_refs = 0
    with_confidence = 0
    provenance_complete = 0
    incomplete_records: list[dict[str, Any]] = []

    for line_no, raw_line in enumerate(raw_lines, 1):
        stripped = raw_line.strip()
        if not stripped:
            continue
        total_lines += 1
        try:
            entry = json.loads(stripped)
        except json.JSONDecodeError as exc:
            chain_errors.append(
                {"line": line_no, "reason": "invalid_json", "detail": str(exc)}
            )
            continue

        if not isinstance(entry, dict):
            chain_errors.append(
                {"line": line_no, "reason": "entry_not_object", "detail": type(entry).__name__}
            )
            continue

        seq = entry.get("seq")
        prev = entry.get("prev")
        event = entry.get("event")
        digest = entry.get("hash")

        line_ok = True
        if not isinstance(seq, int) or isinstance(seq, bool):
            chain_errors.append({"line": line_no, "reason": "invalid_seq", "seq": seq})
            line_ok = False
        elif seq != expected_seq:
            chain_errors.append(
                {
                    "line": line_no,
                    "reason": "seq_gap_or_mismatch",
                    "expected_seq": expected_seq,
                    "actual_seq": seq,
                }
            )
            line_ok = False

        if not isinstance(prev, str) or prev != expected_prev:
            chain_errors.append(
                {
                    "line": line_no,
                    "seq": seq,
                    "reason": "prev_mismatch",
                    "expected_prev": expected_prev,
                    "actual_prev": prev,
                }
            )
            line_ok = False

        if not isinstance(event, dict) or not isinstance(digest, str):
            chain_errors.append(
                {"line": line_no, "seq": seq, "reason": "missing_event_or_hash"}
            )
            line_ok = False
        else:
            expected_digest = compute_entry_hash(prev if isinstance(prev, str) else "", event)
            if digest != expected_digest:
                chain_errors.append(
                    {
                        "line": line_no,
                        "seq": seq,
                        "reason": "hash_mismatch",
                        "expected_hash": expected_digest,
                        "actual_hash": digest,
                    }
                )
                line_ok = False

        if line_ok:
            verified_entries += 1
        if isinstance(seq, int) and not isinstance(seq, bool):
            expected_seq = seq + 1
        else:
            expected_seq += 1
        if isinstance(digest, str) and digest:
            expected_prev = digest

        if not isinstance(event, dict):
            continue

        etype = event.get("type")
        if etype == "anchor":
            digest_val = event.get("digest")
            if isinstance(digest_val, str) and digest_val.strip():
                seen_anchors.add(digest_val.strip())
        elif etype == "record":
            rec = event.get("record")
            if not isinstance(rec, Mapping):
                chain_errors.append(
                    {"line": line_no, "seq": seq, "reason": "record_payload_not_object"}
                )
                continue
            total_records += 1
            rec_id = str(rec.get("id") or f"line-{line_no}")
            kind = str(rec.get("kind") or "")
            content = rec.get("content")

            if rec_id in seen_record_ids:
                duplicate_ids.append({"record_id": rec_id, "line": line_no, "seq": seq})
            seen_record_ids.add(rec_id)

            content_buckets[_content_key(kind, content)].append(
                {"record_id": rec_id, "line": line_no, "seq": seq}
            )

            missing_prov: list[str] = []
            source = rec.get("source")
            has_source_kr = False
            refs_to_check: list[tuple[str, str]] = []

            if isinstance(source, Mapping):
                with_source_dict += 1
                s_kind = source.get("kind")
                s_ref = source.get("ref")
                if isinstance(s_kind, str) and s_kind.strip() and isinstance(s_ref, str) and s_ref.strip():
                    with_source_kind_and_ref += 1
                    has_source_kr = True
                    refs_to_check.append(("source.ref", s_ref.strip()))
                else:
                    missing_prov.append("source.kind_or_ref")
            else:
                missing_prov.append("source")

            ev_refs = rec.get("evidence_refs")
            if isinstance(ev_refs, list) and ev_refs:
                with_evidence_refs += 1
                for raw_ref in ev_refs:
                    if isinstance(raw_ref, str) and raw_ref.strip():
                        refs_to_check.append(("evidence_refs", raw_ref.strip()))
                    else:
                        orphan_evidence_refs.append(
                            {
                                "record_id": rec_id,
                                "line": line_no,
                                "field": "evidence_refs",
                                "ref": raw_ref,
                                "reason": "empty_or_non_string_ref",
                            }
                        )

            conf = rec.get("confidence")
            has_conf = _is_number(conf) and 0.0 <= float(conf) <= 1.0
            if has_conf:
                with_confidence += 1
            else:
                missing_prov.append("confidence")

            if has_source_kr and has_conf:
                provenance_complete += 1
            else:
                incomplete_records.append(
                    {"record_id": rec_id, "line": line_no, "missing": missing_prov}
                )

            effective_known = (
                (known_set | seen_anchors) if known_set is not None else None
            )
            for field_name, ref_str in refs_to_check:
                if ref_str in seen_anchors:
                    continue
                if not _resolve_ref(ref_str, known_refs=effective_known, evidence_root=evidence_root):
                    orphan_evidence_refs.append(
                        {
                            "record_id": rec_id,
                            "line": line_no,
                            "field": field_name,
                            "ref": ref_str,
                            "reason": "dangling_ref",
                        }
                    )

        elif etype in {"supersede", "outcome", "tombstone"}:
            target_id = event.get("record_id")
            if not isinstance(target_id, str) or target_id not in seen_record_ids:
                orphan_event_refs.append(
                    {
                        "line": line_no,
                        "seq": seq,
                        "event_type": etype,
                        "target_record_id": target_id,
                        "reason": "unknown_target_record_id",
                    }
                )

    exact_duplicates = [
        {
            "kind": kind,
            "content_sha256": content_sha,
            "count": len(items),
            "record_ids": [i["record_id"] for i in items],
            "lines": [i["line"] for i in items],
        }
        for (kind, content_sha), items in sorted(content_buckets.items())
        if len(items) > 1
    ]

    prov_rate = (
        round(provenance_complete / total_records, 4) if total_records > 0 else 0.0
    )

    clean = (
        len(chain_errors) == 0
        and len(exact_duplicates) == 0
        and len(duplicate_ids) == 0
        and len(orphan_evidence_refs) == 0
        and len(orphan_event_refs) == 0
        and len(incomplete_records) == 0
    )

    return {
        "schema": SCHEMA,
        "memory_path": str(path),
        "hygiene_ok": clean,
        "hash_chain": {
            "total_entries": total_lines,
            "verified_entries": verified_entries,
            "valid": len(chain_errors) == 0,
            "error_count": len(chain_errors),
            "errors": chain_errors,
        },
        "duplicates": {
            "exact_duplicate_groups": exact_duplicates,
            "exact_duplicate_group_count": len(exact_duplicates),
            "duplicate_record_ids": duplicate_ids,
            "duplicate_record_id_count": len(duplicate_ids),
        },
        "orphan_refs": {
            "dangling_evidence_refs": orphan_evidence_refs,
            "dangling_evidence_count": len(orphan_evidence_refs),
            "orphan_event_refs": orphan_event_refs,
            "orphan_event_count": len(orphan_event_refs),
        },
        "provenance": {
            "total_records": total_records,
            "with_source_dict": with_source_dict,
            "with_source_kind_and_ref": with_source_kind_and_ref,
            "with_evidence_refs": with_evidence_refs,
            "with_confidence": with_confidence,
            "provenance_complete_records": provenance_complete,
            "provenance_completeness_rate": prov_rate,
            "incomplete_records": incomplete_records,
        },
    }


def load_refs_file(refs_path: Path) -> set[str]:
    """Muat himpunan ref terverifikasi dari berkas JSON, JSONL, atau teks per baris."""
    raw = Path(refs_path).read_text(encoding="utf-8").strip()
    if not raw:
        return set()
    if raw.startswith("{") or raw.startswith("["):
        data = json.loads(raw)
        if isinstance(data, list):
            return {str(x).strip() for x in data if str(x).strip()}
        if isinstance(data, dict):
            if isinstance(data.get("refs"), list):
                return {str(x).strip() for x in data["refs"] if str(x).strip()}
            return {str(k).strip() for k in data.keys() if str(k).strip()}
    refs: set[str] = set()
    for line in raw.splitlines():
        s = line.strip()
        if not s:
            continue
        if s.startswith("{"):
            obj = json.loads(s)
            ref = obj.get("ref") or obj.get("id")
            if ref:
                refs.add(str(ref).strip())
        else:
            refs.add(s)
    return refs


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Audit kebersihan log cognitive memory JSONL secara read-only."
    )
    parser.add_argument("--memory", required=True, help="Path berkas cognitive memory JSONL.")
    parser.add_argument("--refs", help="Path opsional daftar ref terverifikasi (JSON/JSONL/teks).")
    parser.add_argument(
        "--evidence-root",
        help="Direktori dasar opsional untuk mengecek keberadaan path bukti di disk.",
    )
    parser.add_argument("--out", help="Path output JSON opsional (default stdout).")
    args = parser.parse_args(argv)

    try:
        known_refs = load_refs_file(Path(args.refs)) if args.refs else None
        ev_root = Path(args.evidence_root) if args.evidence_root else None
        report = audit_memory_log(
            Path(args.memory),
            known_refs=known_refs,
            evidence_root=ev_root,
        )
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

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
