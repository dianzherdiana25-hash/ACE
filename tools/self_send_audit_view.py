#!/usr/bin/env python3
"""Read-only viewer untuk audit JSONL self-send ACE (WS-F #17).

Membaca log JSONL dari `code/ace_operational/self_send.py` (mis. berkas repo
`handover/self_send_audit.jsonl` dan/atau log lokal `self_send_audit.jsonl`),
merangkum pengiriman (`sent`), penolakan (`refused:*`), status parsial/pending
(`prepared` tanpa finalisasi), hitungan per pemicu/alasan/tanggal, serta
mendeteksi anomali integritas rantai audit.
"""

from __future__ import annotations

import argparse
import gzip
import json
import sys
import zlib
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple


SCHEMA_VERSION = "ace.self-send-audit-view.v1"
REQUIRED_KEYS = ("ts", "outcome")


class AuditViewError(RuntimeError):
    """Error masukan berkas audit tidak ditemukan atau tidak bisa dibaca."""


def classify_outcome(outcome: str) -> Tuple[str, Optional[str]]:
    if outcome == "sent":
        return "delivered", None
    if outcome in ("sent_unverified", "sent_audit_finalize_failed", "pushed_pr_failed"):
        return "partial", outcome
    if outcome == "prepared":
        return "prepared", None
    if outcome.startswith("refused:"):
        reason = outcome.split(":", 1)[1] or "unspecified"
        return "refused", reason
    return "unknown", outcome


def parse_audit_jsonl(path: Path) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Parse satu berkas JSONL audit (polos atau .gz) menjadi (rows, parse_anomalies)."""
    if not path.exists() or not path.is_file():
        raise AuditViewError(f"Berkas audit tidak ditemukan: {path}")

    rows: List[Dict[str, Any]] = []
    anomalies: List[Dict[str, Any]] = []
    if path.name.endswith(".gz"):
        try:
            raw_bytes = gzip.decompress(path.read_bytes())
            raw_lines = raw_bytes.decode("utf-8").splitlines()
        except (OSError, EOFError, zlib.error, UnicodeDecodeError) as exc:
            anomalies.append(
                {
                    "kind": "corrupt_gzip_shard",
                    "source": str(path),
                    "line": 0,
                    "detail": f"Shard .gz rusak ({type(exc).__name__}): {exc}",
                }
            )
            return rows, anomalies
    else:
        try:
            raw_lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError) as exc:
            raise AuditViewError(f"Gagal membaca berkas audit '{path}': {exc}") from exc

    for idx, line in enumerate(raw_lines, start=1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            obj = json.loads(stripped)
        except json.JSONDecodeError as exc:
            anomalies.append(
                {
                    "kind": "malformed_json",
                    "source": str(path),
                    "line": idx,
                    "detail": str(exc),
                }
            )
            continue

        if not isinstance(obj, dict):
            anomalies.append(
                {
                    "kind": "non_object_row",
                    "source": str(path),
                    "line": idx,
                    "detail": f"Tipe baris bukan JSON object ({type(obj).__name__})",
                }
            )
            continue

        missing = [k for k in REQUIRED_KEYS if not isinstance(obj.get(k), str) or not obj.get(k, "").strip()]
        if missing:
            anomalies.append(
                {
                    "kind": "missing_required_fields",
                    "source": str(path),
                    "line": idx,
                    "detail": f"Field wajib hilang/kosong: {', '.join(missing)}",
                }
            )
            continue

        enriched = dict(obj)
        enriched["_source"] = str(path)
        enriched["_line"] = idx
        rows.append(enriched)

    return rows, anomalies


def inspect_audit_files(paths: Sequence[Path], *, allow_missing_extra: bool = False) -> Dict[str, Any]:
    """Analisis satu atau lebih berkas audit self-send secara baca-saja."""
    if not paths:
        raise AuditViewError("Minimal satu --audit-file wajib diberikan.")

    all_rows: List[Dict[str, Any]] = []
    anomalies: List[Dict[str, Any]] = []
    loaded_sources: List[str] = []
    missing_sources: List[str] = []

    for idx, p in enumerate(paths):
        if not p.exists():
            if allow_missing_extra and idx > 0:
                missing_sources.append(str(p))
                continue
            raise AuditViewError(f"Berkas audit tidak ditemukan: {p}")
        rows, parse_anom = parse_audit_jsonl(p)
        loaded_sources.append(str(p))
        all_rows.extend(rows)
        anomalies.extend(parse_anom)

    category_counts: Counter[str] = Counter()
    refusal_reasons: Counter[str] = Counter()
    trigger_counts: Counter[str] = Counter()
    daily_counts: Dict[str, Counter[str]] = defaultdict(Counter)
    pr_numbers: List[int] = []

    # Lacak prepared vs finalisasi dan deteksi duplikasi / branch asing / timestamp mundur
    prepared_pending: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    sent_keys: Counter[Tuple[str, str]] = Counter()
    prev_ts_by_source: Dict[str, str] = {}

    entries_summary: List[Dict[str, Any]] = []
    for row in all_rows:
        ts = str(row["ts"])
        day = ts[:10]
        outcome = str(row["outcome"])
        trigger = str(row.get("trigger") or "unknown")
        branch = str(row.get("branch") or "")
        digest = str(row.get("content_digest") or "")
        pr_number = row.get("pr_number")
        files = row.get("files") if isinstance(row.get("files"), list) else []
        source = row["_source"]
        line_no = row["_line"]

        category, detail = classify_outcome(outcome)
        category_counts[category] += 1
        trigger_counts[trigger] += 1
        daily_counts[day][category] += 1

        if category == "refused" and detail:
            reason_head = detail.split(":", 1)[0]
            refusal_reasons[reason_head] += 1
        elif category == "unknown":
            anomalies.append(
                {
                    "kind": "unknown_outcome",
                    "source": source,
                    "line": line_no,
                    "detail": f"Outcome tidak dikenal: {outcome!r}",
                }
            )

        if branch and not branch.startswith("ace-auto/"):
            anomalies.append(
                {
                    "kind": "unexpected_branch_namespace",
                    "source": source,
                    "line": line_no,
                    "detail": f"Branch di luar namespace ace-auto/: {branch!r}",
                }
            )

        prev_ts = prev_ts_by_source.get(source)
        if prev_ts is not None and ts < prev_ts:
            anomalies.append(
                {
                    "kind": "non_monotonic_timestamp",
                    "source": source,
                    "line": line_no,
                    "detail": f"Timestamp mundur ({ts} < {prev_ts})",
                }
            )
        prev_ts_by_source[source] = ts

        key = (branch, digest)
        if outcome == "prepared":
            prepared_pending[key].append(row)
        elif category in ("delivered", "partial"):
            if key in prepared_pending and prepared_pending[key]:
                prepared_pending[key].pop(0)
            if category == "delivered":
                sent_keys[key] += 1
                if sent_keys[key] > 1:
                    anomalies.append(
                        {
                            "kind": "duplicate_delivered_send",
                            "source": source,
                            "line": line_no,
                            "detail": f"Pengiriman 'sent' ganda untuk branch={branch!r}, digest={digest[:12]}",
                        }
                    )

        if isinstance(pr_number, int):
            pr_numbers.append(pr_number)

        entries_summary.append(
            {
                "ts": ts,
                "trigger": trigger,
                "branch": branch,
                "pr_number": pr_number,
                "outcome": outcome,
                "category": category,
                "file_count": len(files),
                "source": source,
                "line": line_no,
            }
        )

    for (branch, digest), leftover in prepared_pending.items():
        for row in leftover:
            anomalies.append(
                {
                    "kind": "unclosed_prepared_row",
                    "source": row["_source"],
                    "line": row["_line"],
                    "detail": (
                        f"Baris 'prepared' tanpa finalisasi untuk branch={branch!r} "
                        f"digest={digest[:12]}"
                    ),
                }
            )

    timestamps = sorted(str(r["ts"]) for r in all_rows)
    return {
        "schema": SCHEMA_VERSION,
        "read_only": True,
        "sources": loaded_sources,
        "missing_optional_sources": missing_sources,
        "summary": {
            "total_rows": len(all_rows),
            "delivered_count": category_counts["delivered"],
            "partial_count": category_counts["partial"],
            "prepared_count": category_counts["prepared"],
            "refused_count": category_counts["refused"],
            "unknown_count": category_counts["unknown"],
            "anomaly_count": len(anomalies),
            "unique_prs": sorted(set(pr_numbers)),
            "first_ts": timestamps[0] if timestamps else None,
            "last_ts": timestamps[-1] if timestamps else None,
        },
        "refusal_reasons": dict(sorted(refusal_reasons.items())),
        "triggers": dict(sorted(trigger_counts.items())),
        "daily_breakdown": {
            day: dict(sorted(cnt.items())) for day, cnt in sorted(daily_counts.items())
        },
        "anomalies": anomalies,
        "recent_entries": entries_summary[-20:],
    }


def render_markdown(report: Dict[str, Any]) -> str:
    s = report["summary"]
    lines: List[str] = [
        "# Ringkasan Audit Self-Send ACE",
        "",
        f"- Sumber audit: {', '.join(f'`{src}`' for src in report['sources'])}",
        f"- Total baris valid: **{s['total_rows']}** "
        f"(sent={s['delivered_count']}, partial={s['partial_count']}, "
        f"prepared={s['prepared_count']}, refused={s['refused_count']}, unknown={s['unknown_count']})",
        f"- Rentang waktu: `{s['first_ts'] or '-'}` s.d. `{s['last_ts'] or '-'}`",
        f"- PR tercatat: {', '.join(f'#{n}' for n in s['unique_prs']) if s['unique_prs'] else '-'}",
        f"- Anomali terdeteksi: **{s['anomaly_count']}**",
    ]

    if report["refusal_reasons"]:
        lines.extend(["", "## Alasan Penolakan"])
        for reason, cnt in report["refusal_reasons"].items():
            lines.append(f"- `{reason}`: {cnt}")

    if report["anomalies"]:
        lines.extend(["", "## Anomali Audit"])
        for anom in report["anomalies"]:
            lines.append(
                f"- **{anom['kind']}** (`{anom['source']}:{anom['line']}`): {anom['detail']}"
            )

    if report["recent_entries"]:
        lines.extend(["", "## Entri Terbaru"])
        for item in report["recent_entries"]:
            pr_label = f"PR #{item['pr_number']}" if item["pr_number"] is not None else "no-PR"
            lines.append(
                f"- `{item['ts']}` [{item['category']}] `{item['outcome']}` "
                f"trigger=`{item['trigger']}` branch=`{item['branch'] or '-'}` ({pr_label})"
            )

    lines.append("")
    return "\n".join(lines)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read-only viewer audit JSONL self-send ACE."
    )
    parser.add_argument(
        "--audit-file",
        action="append",
        required=True,
        help="Path berkas self_send_audit.jsonl (bisa diberikan lebih dari sekali)",
    )
    parser.add_argument(
        "--allow-missing-extra",
        action="store_true",
        help="Izinkan berkas audit ke-2 dst tidak ada tanpa error",
    )
    parser.add_argument("--format", choices=("json", "md"), default="json", help="Format stdout")
    parser.add_argument("--out-json", default=None, help="Simpan ringkasan JSON ke berkas")
    parser.add_argument("--out-md", default=None, help="Simpan ringkasan Markdown ke berkas")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Kembalikan exit code 1 apabila ditemukan anomali audit",
    )

    args = parser.parse_args(argv)
    try:
        report = inspect_audit_files(
            [Path(p) for p in args.audit_file],
            allow_missing_extra=args.allow_missing_extra,
        )
    except AuditViewError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    json_text = json.dumps(report, indent=2, ensure_ascii=False)
    md_text = render_markdown(report)

    if args.out_json:
        Path(args.out_json).write_text(json_text + "\n", encoding="utf-8")
    if args.out_md:
        Path(args.out_md).write_text(md_text, encoding="utf-8")

    print(json_text if args.format == "json" else md_text)
    if args.strict and report["summary"]["anomaly_count"] > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
