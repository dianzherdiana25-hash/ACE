#!/usr/bin/env python3
"""Lacak prepared yang belum ditutup saat log self-send berganti berkas.

Periode meliputi hari UTC yang muncul dalam berkas *.jsonl langsung di
direktori. Laporan menghitung yatim sebagai prepared yang masih terbuka pada
akhir hari. Terminal tanpa prepared dilaporkan terpisah. Log tanpa task_id
menggunakan branch dan content_digest sebagai identitas dari amplop. Baris
tanpa timestamp sah menambah pelanggaran tanpa tanggal.
"""
import argparse
from collections import defaultdict, deque
from datetime import datetime, timezone
import json
from pathlib import Path

if __package__:
    from .self_send_audit import delivery_key, envelope_violations
    from .self_send_audit_view import AuditViewError, classify_outcome, parse_audit_jsonl
else:
    from self_send_audit import delivery_key, envelope_violations
    from self_send_audit_view import AuditViewError, classify_outcome, parse_audit_jsonl


def standing_audit(directory):
    if not directory.is_dir():
        raise ValueError("Direktori log tidak tersedia.")
    rows = []
    undated = 0
    for path in sorted(directory.glob("*.jsonl")):
        if path.is_symlink() or not path.is_file():
            continue
        batch, anomalies = parse_audit_jsonl(path)
        undated += len(anomalies)
        for row in batch:
            try:
                stamp = datetime.fromisoformat(row["ts"])
                if stamp.utcoffset() is None:
                    raise ValueError
                utc = stamp.astimezone(timezone.utc)
            except (OverflowError, ValueError):
                undated += 1
                continue
            rows.append((utc, path.name, row["_line"], row))

    current = None
    days = []
    pending = defaultdict(deque)
    open_count = 0
    for stamp, source, line, row in sorted(rows, key=lambda event: event[:3]):
        day = stamp.date().isoformat()
        if current is None or current["day_utc"] != day:
            current = {"day_utc": day, "prepared": 0, "sent": 0, "orphans": open_count,
                       "sent_without_prepared": 0, "envelope_violations": 0}
            days.append(current)
        category, _ = classify_outcome(row["outcome"])
        current["envelope_violations"] += len(envelope_violations(row, category))
        key = delivery_key(row)
        if category == "prepared":
            current["prepared"] += 1
            task_id = row.get("task_id")
            if not isinstance(task_id, str) or not task_id.strip():
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

    return {"schema": "ace.self-send-standing-audit.v1", "days": days,
            "open_orphan_task_ids": sorted(task_id for queue in pending.values() for task_id in queue),
            "undated_violations": undated}


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
                    or any(day["envelope_violations"] for day in report["days"])))


if __name__ == "__main__":
    raise SystemExit(main())
