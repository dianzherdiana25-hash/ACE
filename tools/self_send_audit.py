#!/usr/bin/env python3
"""Ringkas kiriman yang tercatat dan tunjukkan pelanggaran amplop per baris."""

import argparse
from collections import Counter, defaultdict, deque
from datetime import datetime, timezone
import json
from pathlib import Path
import re

if __package__:
    from .self_send_audit_view import AuditViewError, classify_outcome, parse_audit_jsonl
else:
    from self_send_audit_view import AuditViewError, classify_outcome, parse_audit_jsonl


_BRANCH = re.compile(r"ace-auto/[0-9]{8}-[a-z0-9][a-z0-9-]{0,40}")


def envelope_violations(row, category):
    """Pakai aturan amplop yang sama di audit satu log dan laporan berkala."""
    reasons = []
    branch = row.get("branch")
    if branch or category in {"prepared", "partial", "delivered"}:
        if not isinstance(branch, str) or not _BRANCH.fullmatch(branch):
            reasons.append("target_branch_refused")
    if row.get("merge_authority", False) is not False:
        reasons.append("merge_authority_not_absent")
    if category == "unknown":
        reasons.append("unknown_outcome")
    return reasons


def delivery_key(row):
    branch, digest = row.get("branch"), row.get("content_digest")
    if isinstance(branch, str) and isinstance(digest, str) and digest:
        return branch, digest
    return None


def _shard_sort_key(path: Path) -> tuple[str, str]:
    stem = path.name[:-3] if path.name.endswith(".gz") else path.name
    return stem, path.name


def iter_audit_shards(target: Path) -> list[Path]:
    """Kembalikan daftar berkas shard audit (.jsonl atau .gz) secara deterministik."""
    if target.is_dir():
        shards = [
            p for p in target.iterdir()
            if not p.is_symlink() and p.is_file() and (
                p.name.endswith(".jsonl") or p.name.endswith(".jsonl.gz") or p.name.endswith(".gz")
            )
        ]
        return sorted(shards, key=_shard_sort_key)
    return [target]


def audit(path):
    rows = []
    anomalies = []
    for shard in iter_audit_shards(path):
        batch, shard_anomalies = parse_audit_jsonl(shard)
        rows.extend(batch)
        anomalies.extend(shard_anomalies)
    violations = [{"line": item["line"], "reason": item["kind"]} for item in anomalies]
    days = defaultdict(Counter)
    prepared = defaultdict(deque)
    transitions = []
    findings = [
        {"source": item["source"], "line": item["line"], "reason": item["kind"]}
        for item in anomalies if item["kind"] == "corrupt_gzip_shard"
    ]
    for row in rows:
        line = row["_line"]
        branch = row.get("branch")
        category, _ = classify_outcome(row["outcome"])
        violations.extend({"line": line, "reason": reason} for reason in envelope_violations(row, category))
        source = {"source": row["_source"], "line": line}
        key = delivery_key(row)
        if category == "prepared" and key:
            prepared[key].append(source)
        elif category in {"partial", "delivered"}:
            origin = prepared[key].popleft() if key and prepared.get(key) else None
            if category == "delivered":
                if origin:
                    transitions.append({"prepared": origin, "sent": source})
                else:
                    findings.append({**source, "reason": "sent_without_prepared"})
        if category == "delivered":
            try:
                stamp = datetime.fromisoformat(row["ts"])
                if stamp.tzinfo is None:
                    raise ValueError
            except ValueError:
                violations.append({"line": line, "reason": "invalid_timestamp"})
                continue
            day = stamp.astimezone(timezone.utc).date().isoformat()
            days[day][branch if isinstance(branch, str) and _BRANCH.fullmatch(branch) else "(ditolak)"] += 1
    for pending in prepared.values():
        findings.extend({**source, "reason": "prepared_without_terminal"} for source in pending)
    findings.sort(key=lambda item: (item["line"], item["reason"]))
    violations.sort(key=lambda item: (item["line"], item["reason"]))
    return {"schema": "ace.self-send-audit.v1", "sent": sum(sum(day.values()) for day in days.values()),
            "by_day_and_target": {day: dict(sorted(counts.items())) for day, counts in sorted(days.items())},
            "transitions": transitions, "findings": findings,
            "violation_count": len(violations), "violations": violations}


def markdown(result):
    lines = ["# Audit self-send", "", f"- Kiriman bertanggal — {result['sent']}",
             f"- Pelanggaran — {result['violation_count']}", "", "## Hari dan target", ""]
    lines.extend(f"- {day} · {branch} · {count}"
                 for day, targets in result["by_day_and_target"].items()
                 for branch, count in targets.items())
    lines.extend(["", "## Lokasi pelanggaran", ""])
    lines.extend(f"- Baris {row['line']} · {row['reason']}" for row in result["violations"])
    if "transitions" in result:
        lines.extend(["", "## Transisi prepared → sent", ""])
        lines.extend(f"- Baris {item['prepared']['line']} → baris {item['sent']['line']}"
                     for item in result["transitions"])
    if "findings" in result:
        lines.extend(["", "## Temuan audit", ""])
        lines.extend(f"- Baris {row['line']} · {row['reason']}" for row in result["findings"])
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=Path)
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    args = parser.parse_args(argv)
    try:
        result = audit(args.log)
    except AuditViewError as exc:
        parser.exit(2, f"Error: {exc}\n")
    print(markdown(result) if args.format == "markdown" else json.dumps(result, indent=2), end="\n")
    return 1 if result["violation_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
