#!/usr/bin/env python3
"""Lacak prepared yang belum ditutup saat log self-send berganti berkas.

Periode meliputi hari UTC yang muncul dalam berkas *.jsonl langsung di
direktori. Laporan menghitung yatim sebagai prepared yang masih terbuka pada
akhir hari. Terminal tanpa prepared dilaporkan terpisah. Kunci pasangan memakai branch, content_digest, dan task_id bila tersedia. Baris
tanpa timestamp sah menambah pelanggaran tanpa tanggal.
"""
import argparse
from collections import defaultdict, deque
from datetime import datetime, timezone
import json
from pathlib import Path

if __package__:
    from .self_send_audit import delivery_key, envelope_violations, iter_audit_shards
    from .self_send_audit_view import AuditViewError, classify_outcome, parse_audit_jsonl
else:
    from self_send_audit import delivery_key, envelope_violations, iter_audit_shards
    from self_send_audit_view import AuditViewError, classify_outcome, parse_audit_jsonl


def _shard_stem_for_order(source_name: str) -> str:
    return source_name[:-3] if source_name.endswith(".gz") else source_name


def _source_pointer(row):
    explicit = row.get("source") or row.get("source_pointer") or row.get("ref") or ""
    branch = row.get("branch") or ""
    digest = row.get("content_digest") or ""
    return (str(explicit), str(branch), str(digest))


def _event_status(row):
    return str(row.get("status") if row.get("status") is not None else row.get("outcome") or "")


def standing_audit(directory):
    if not directory.is_dir():
        raise ValueError("Direktori log tidak tersedia.")
    rows = []
    undated = 0
    corrupt_shards = []
    for path in iter_audit_shards(directory):
        batch, anomalies = parse_audit_jsonl(path)
        undated += len(anomalies)
        for anom in anomalies:
            if anom["kind"] == "corrupt_gzip_shard":
                corrupt_shards.append({
                    "source": anom["source"],
                    "reason": anom["kind"],
                    "detail": anom["detail"],
                })
        for row in batch:
            try:
                stamp = datetime.fromisoformat(row["ts"])
                if stamp.utcoffset() is None:
                    raise ValueError
                utc = stamp.astimezone(timezone.utc)
            except (OverflowError, ValueError):
                undated += 1
                continue
            rows.append((utc, _shard_stem_for_order(path.name), row["_line"], path.name, row))

    seen_shard_events = {}
    deduped_count = 0
    shard_conflicts = []
    deduped_rows = []
    conflicted_slot_keys = set()

    for utc, order_stem, line, shard_name, row in sorted(rows, key=lambda event: event[:3]):
        task_val = row.get("task_id")
        task_key = task_val.strip() if isinstance(task_val, str) and task_val.strip() else None
        status_val = _event_status(row)
        src_ptr = _source_pointer(row)
        utc_iso = utc.isoformat()

        slot_key = (utc_iso, task_key, src_ptr) if task_key is not None else (utc_iso, None, src_ptr)
        exact_key = (task_key, status_val, utc_iso, src_ptr)

        if slot_key in seen_shard_events:
            prev_shard, prev_status, prev_src, prev_row = seen_shard_events[slot_key]
            if prev_shard != shard_name:
                if exact_key == (
                    prev_row.get("task_id").strip()
                    if isinstance(prev_row.get("task_id"), str) and prev_row.get("task_id").strip()
                    else None,
                    prev_status,
                    utc_iso,
                    prev_src,
                ):
                    deduped_count += 1
                    continue
                conflicted_slot_keys.add(slot_key)
                shard_conflicts.append({
                    "task_id": task_key,
                    "ts_utc": utc_iso,
                    "source_pointer": src_ptr[0] or f"{src_ptr[1]}@{src_ptr[2]}",
                    "reason": "cross_shard_conflicting_event",
                    "entries": [
                        {"shard": prev_shard, "status": prev_status},
                        {"shard": shard_name, "status": status_val},
                    ],
                })
                continue
        seen_shard_events[slot_key] = (shard_name, status_val, src_ptr, row)
        deduped_rows.append((utc, order_stem, line, row, slot_key))

    # Tangkap konflik beda source_pointer atau status untuk task_id + ts_utc yang sama antar shard
    by_task_ts = {}
    for utc, order_stem, line, shard_name, row in sorted(rows, key=lambda event: event[:3]):
        task_val = row.get("task_id")
        if not isinstance(task_val, str) or not task_val.strip():
            continue
        tkey = (task_val.strip(), utc.isoformat())
        status_val = _event_status(row)
        src_ptr = _source_pointer(row)
        if tkey in by_task_ts:
            prev_shard, prev_status, prev_ptr = by_task_ts[tkey]
            if prev_shard != shard_name and (prev_status != status_val or prev_ptr != src_ptr):
                slot_a = (tkey[1], tkey[0], prev_ptr)
                slot_b = (tkey[1], tkey[0], src_ptr)
                if slot_a not in conflicted_slot_keys and slot_b not in conflicted_slot_keys:
                    conflicted_slot_keys.update({slot_a, slot_b})
                    shard_conflicts.append({
                        "task_id": tkey[0],
                        "ts_utc": tkey[1],
                        "reason": "cross_shard_conflicting_event",
                        "entries": [
                            {"shard": prev_shard, "status": prev_status, "source_pointer": prev_ptr},
                            {"shard": shard_name, "status": status_val, "source_pointer": src_ptr},
                        ],
                    })
        else:
            by_task_ts[tkey] = (shard_name, status_val, src_ptr)

    current = None
    days = []
    pending = defaultdict(deque)
    open_count = 0
    for stamp, source, line, row, slot_key in deduped_rows:
        if slot_key in conflicted_slot_keys:
            continue
        day = stamp.date().isoformat()
        if current is None or current["day_utc"] != day:
            current = {"day_utc": day, "prepared": 0, "sent": 0, "orphans": open_count,
                       "sent_without_prepared": 0, "envelope_violations": 0}
            days.append(current)
        category, _ = classify_outcome(row["outcome"])
        current["envelope_violations"] += len(envelope_violations(row, category))
        envelope_key = delivery_key(row)
        task_id = row.get("task_id")
        if not isinstance(task_id, str) or not task_id.strip():
            task_id = None
        key = (*envelope_key, task_id) if envelope_key else None
        if category == "prepared":
            current["prepared"] += 1
            if task_id is None:
                task_id = f"{key[0]}@{key[1]}" if key else f"{source}:{line}"
            pending[key if key else (source, line)].append(task_id)
            open_count += 1
        elif category in {"delivered", "partial"}:
            if category == "delivered":
                current["sent"] += 1
            if key and pending.get(key):
                pending[key].popleft()
                open_count -= 1
            elif category == "delivered":
                current["sent_without_prepared"] += 1
        current["orphans"] = open_count

    report = {"schema": "ace.self-send-standing-audit.v1", "days": days,
              "open_orphan_task_ids": sorted(task_id for queue in pending.values() for task_id in queue),
              "undated_violations": undated}
    if corrupt_shards:
        report["corrupt_shards"] = corrupt_shards
    if deduped_count:
        report["deduped_events"] = deduped_count
    if shard_conflicts:
        report["shard_conflicts"] = shard_conflicts
    return report


def text_summary(report):
    totals = {key: sum(day[key] for day in report["days"])
              for key in ("prepared", "sent", "envelope_violations")}
    return (f"Audit self-send UTC — {len(report['days'])} hari, {totals['prepared']} prepared, "
            f"{totals['sent']} sent, {len(report['open_orphan_task_ids'])} yatim terbuka, "
            f"{totals['envelope_violations']} pelanggaran amplop, "
            f"{report['undated_violations']} pelanggaran tanpa tanggal.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log_directory", type=Path)
    parser.add_argument("--format", choices=("json", "text"), default="json")
    args = parser.parse_args(argv)
    try:
        report = standing_audit(args.log_directory)
    except (AuditViewError, OSError, ValueError):
        parser.exit(2, "Error: direktori log audit tidak dapat dibaca.\n")
    print(json.dumps(report, indent=2, ensure_ascii=False)
          if args.format == "json" else text_summary(report))
    return int(bool(report["undated_violations"]
                    or report.get("shard_conflicts")
                    or any(day["envelope_violations"] for day in report["days"])))


if __name__ == "__main__":
    raise SystemExit(main())
