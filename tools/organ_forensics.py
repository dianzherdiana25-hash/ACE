#!/usr/bin/env python3
"""Analisator forensik log/journal baca-saja untuk kejadian jatuh & restart organ ACE.

Kenapa modul ini ada:
Ketika organ lokal atau bridge (`llama-server`, `brain_bridge`, worker) jatuh
atau restart berulang kali, operator membutuhkan cara deterministik untuk
mengekstrak setiap kejadian jatuh beserta cap waktunya, pola jarak waktu
antar-kejadian (mis. burst crash-loop vs sporadis), dan baris konteks terakhir
tepat sebelum jatuh — murni dari berkas snapshot log/journal secara baca-saja
tanpa menyentuh proses hidup.

Exit code:
- 0: analisis selesai (baik ada kejadian maupun bersih)
- 2: argumen CLI atau berkas log tidak dapat dibaca
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import statistics
import sys
from typing import Any

ORGAN_FORENSICS_SCHEMA = "ace.organ-forensics.v1"

# Pola cap waktu yang umum ditemui pada log systemd/journalctl, Python logging,
# ISO-8601, dan format waktu relatif `llama-server` (`M.SS.mmm.uuu`).
_ISO_TS_RE = re.compile(
    r"(?P<ts>\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:[.,]\d{1,6})?(?:Z|[+-]\d{2}:?\d{2})?)"
)
_SYSLOG_TS_RE = re.compile(
    r"^(?P<ts>(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})\b"
)
_LLAMA_REL_TS_RE = re.compile(r"^(?P<min>\d+)\.(?P<sec>\d{2})\.(?P<ms>\d{3})\.(?P<us>\d{3})\b")

_ORGAN_HINT_RE = re.compile(
    r"\b(ace-[a-z0-9_.-]+(?:\.service)?|llama[-_]server|brain[-_]bridge(?:[-_](?:relay|pump))?|"
    r"organ[-_][a-z0-9_]+|systemd(?:\[\d+\])?|worker[-_][a-z0-9_]+)\b",
    re.IGNORECASE,
)

# Aturan klasifikasi baris kejadian jatuh/restart dari yang paling spesifik.
_INCIDENT_RULES: tuple[tuple[str, str, re.Pattern[str]], ...] = (
    (
        "oom_kill",
        "crash",
        re.compile(
            r"\b(?:out of memory|oom[- ]killer|oom_kill|killed process|status=9/kill|signal 9\b|sigkill)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "crash_signal",
        "crash",
        re.compile(
            r"\b(?:sigsegv|sigabrt|sigbus|sigfpe|segmentation fault|core dumped|"
            r"terminated with signal|fatal error|panic:)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "exit_failure",
        "crash",
        re.compile(
            r"\b(?:main process exited|exited with (?:code|status)\s+[1-9]\d*|"
            r"failed with result|status=failure|process exited unexpectedly|"
            r"returncode=[1-9]\d*|worker died|server died|organ crashed|organ down)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "exception_crash",
        "crash",
        re.compile(
            r"\b(?:unhandled exception|traceback \(most recent call last\)|"
            r"critical:.*(?:crash|down|abort))\b",
            re.IGNORECASE,
        ),
    ),
    (
        "restart",
        "restart",
        re.compile(
            r"\b(?:scheduled restart job|automatic restart|restarting service|"
            r"service restarted|organ restarted|restarted successfully|restart counter is at)\b",
            re.IGNORECASE,
        ),
    ),
)


class OrganForensicsError(ValueError):
    """Kesalahan pembacaan berkas log atau parameter CLI forensik organ."""


def parse_timestamp(line: str, *, default_year: int = 2026) -> tuple[str | None, float | None]:
    """Ekstrak cap waktu mentah dan epoch/detik numerik dari satu baris log."""
    m_iso = _ISO_TS_RE.search(line)
    if m_iso:
        raw = m_iso.group("ts")
        norm = raw.replace(",", ".").replace(" ", "T")
        if norm.endswith("Z"):
            norm = norm[:-1] + "+00:00"
        elif re.search(r"[+-]\d{4}$", norm):
            norm = norm[:-2] + ":" + norm[-2:]
        try:
            dt = datetime.fromisoformat(norm)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return raw, dt.timestamp()
        except ValueError:
            return raw, None

    m_sys = _SYSLOG_TS_RE.match(line)
    if m_sys:
        raw = m_sys.group("ts")
        cleaned = re.sub(r"\s+", " ", raw)
        try:
            dt = datetime.strptime(f"{default_year} {cleaned}", "%Y %b %d %H:%M:%S").replace(
                tzinfo=timezone.utc
            )
            return raw, dt.timestamp()
        except ValueError:
            return raw, None

    m_rel = _LLAMA_REL_TS_RE.match(line)
    if m_rel:
        raw = m_rel.group(0)
        secs = (
            int(m_rel.group("min")) * 60.0
            + int(m_rel.group("sec"))
            + int(m_rel.group("ms")) / 1000.0
            + int(m_rel.group("us")) / 1_000_000.0
        )
        return raw, round(secs, 6)

    return None, None


def classify_incident(line: str) -> tuple[str, str] | None:
    """Klasifikasikan apakah baris menandakan jatuh (`crash`) atau `restart` organ."""
    for category, severity, pattern in _INCIDENT_RULES:
        if pattern.search(line):
            return category, severity
    return None


def extract_organ_hint(line: str) -> str | None:
    """Ambil petunjuk nama organ/layanan bila tercantum pada baris log."""
    match = _ORGAN_HINT_RE.search(line)
    if not match:
        return None
    token = match.group(1)
    return re.sub(r"\[\d+\]$", "", token)


def _compute_inter_failure_pattern(epochs: list[float]) -> dict[str, Any]:
    if len(epochs) < 2:
        return {
            "timed_event_count": len(epochs),
            "interval_count": 0,
            "intervals_seconds": [],
            "min_seconds": None,
            "max_seconds": None,
            "mean_seconds": None,
            "median_seconds": None,
            "pattern_label": "insufficient_events",
        }

    intervals = [round(epochs[i] - epochs[i - 1], 3) for i in range(1, len(epochs))]
    non_negative = [iv for iv in intervals if iv >= 0]
    if not non_negative:
        return {
            "timed_event_count": len(epochs),
            "interval_count": len(intervals),
            "intervals_seconds": intervals,
            "min_seconds": min(intervals),
            "max_seconds": max(intervals),
            "mean_seconds": round(statistics.fmean(intervals), 3),
            "median_seconds": round(float(statistics.median(intervals)), 3),
            "pattern_label": "non_monotonic_timestamps",
        }

    min_s = min(non_negative)
    max_s = max(non_negative)
    mean_s = statistics.fmean(non_negative)
    median_s = float(statistics.median(non_negative))

    if min_s <= 60.0:
        label = "burst_crash_loop"
    elif len(non_negative) >= 2 and mean_s > 0:
        stdev_s = statistics.pstdev(non_negative)
        label = "periodic_recurring" if (stdev_s / mean_s) <= 0.25 else "sporadic"
    else:
        label = "isolated_pair"

    return {
        "timed_event_count": len(epochs),
        "interval_count": len(intervals),
        "intervals_seconds": intervals,
        "min_seconds": round(min_s, 3),
        "max_seconds": round(max_s, 3),
        "mean_seconds": round(mean_s, 3),
        "median_seconds": round(median_s, 3),
        "pattern_label": label,
    }


def analyze_log_lines(
    lines: list[str],
    *,
    source_name: str = "<memory>",
    context_lines: int = 5,
    default_year: int = 2026,
) -> dict[str, Any]:
    """Analisis daftar baris snapshot log/journal secara baca-saja."""
    if context_lines < 0:
        raise OrganForensicsError("--context-lines tidak boleh negatif.")

    # Infer tahun dari baris ISO pertama bila tersedia agar syslog ikut konsisten.
    inferred_year = default_year
    for raw_line in lines:
        m_iso = _ISO_TS_RE.search(raw_line)
        if m_iso:
            inferred_year = int(m_iso.group("ts")[:4])
            break

    incidents: list[dict[str, Any]] = []
    category_counts: Counter[str] = Counter()
    severity_counts: Counter[str] = Counter()
    organ_counts: Counter[str] = Counter()

    last_ts_raw: str | None = None
    last_ts_epoch: float | None = None

    for idx, line in enumerate(lines):
        line_no = idx + 1
        ts_raw, ts_epoch = parse_timestamp(line, default_year=inferred_year)
        if ts_raw is not None:
            last_ts_raw = ts_raw
            last_ts_epoch = ts_epoch

        classified = classify_incident(line)
        if classified is None:
            continue

        category, severity = classified
        organ = extract_organ_hint(line)
        start_ctx = max(0, idx - context_lines)
        ctx = [
            {"line_number": c_idx + 1, "text": lines[c_idx]}
            for c_idx in range(start_ctx, idx)
        ]

        # Jika nama organ tidak muncul pada baris jatuh, cek baris konteks terakhir.
        if organ is None:
            for item in reversed(ctx):
                hint = extract_organ_hint(item["text"])
                if hint is not None:
                    organ = hint
                    break

        event_ts_raw = ts_raw if ts_raw is not None else last_ts_raw
        event_ts_epoch = ts_epoch if ts_epoch is not None else last_ts_epoch

        incidents.append(
            {
                "index": len(incidents) + 1,
                "line_number": line_no,
                "category": category,
                "severity": severity,
                "timestamp_raw": event_ts_raw,
                "timestamp_inherited": ts_raw is None and event_ts_raw is not None,
                "epoch_seconds": event_ts_epoch,
                "organ": organ or "unknown",
                "line": line,
                "context_before": ctx,
            }
        )
        category_counts[category] += 1
        severity_counts[severity] += 1
        organ_counts[organ or "unknown"] += 1

    all_epochs = [ev["epoch_seconds"] for ev in incidents if ev["epoch_seconds"] is not None]
    crash_epochs = [
        ev["epoch_seconds"]
        for ev in incidents
        if ev["severity"] == "crash" and ev["epoch_seconds"] is not None
    ]

    return {
        "schema": ORGAN_FORENSICS_SCHEMA,
        "source": source_name,
        "total_lines": len(lines),
        "context_lines": context_lines,
        "incident_count": len(incidents),
        "crash_count": severity_counts.get("crash", 0),
        "restart_count": severity_counts.get("restart", 0),
        "category_counts": dict(sorted(category_counts.items())),
        "organ_counts": dict(sorted(organ_counts.items())),
        "inter_failure_pattern_all": _compute_inter_failure_pattern(all_epochs),
        "inter_failure_pattern_crashes": _compute_inter_failure_pattern(crash_epochs),
        "incidents": incidents,
    }


def analyze_log_file(
    path: Path,
    *,
    context_lines: int = 5,
    default_year: int = 2026,
) -> dict[str, Any]:
    """Baca satu berkas snapshot log/journal secara baca-saja dan ekstraksi insiden."""
    if not path.is_file():
        raise OrganForensicsError(f"Berkas log tidak ditemukan: {path}")
    try:
        raw_text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise OrganForensicsError(f"Gagal membaca berkas log '{path}': {exc}") from exc
    return analyze_log_lines(
        raw_text.splitlines(),
        source_name=str(path),
        context_lines=context_lines,
        default_year=default_year,
    )


def render_markdown(report: dict[str, Any]) -> str:
    """Render laporan forensik jatuh/restart organ dalam Markdown deterministik."""
    pat_crash = report["inter_failure_pattern_crashes"]
    pat_all = report["inter_failure_pattern_all"]
    lines = [
        "# Laporan Forensik Jatuh & Restart Organ ACE",
        "",
        f"> Dihasilkan secara baca-saja oleh `tools/organ_forensics.py` (`{report['schema']}`).",
        "",
        "## Ringkasan",
        "",
        f"- **Sumber log:** `{report['source']}` ({report['total_lines']} baris)",
        f"- **Total kejadian terdeteksi:** {report['incident_count']} (jatuh/crash: {report['crash_count']}, restart: {report['restart_count']})",
        f"- **Pola waktu-antar-jatuh (crash):** `{pat_crash['pattern_label']}` "
        f"(interval detik: {pat_crash['intervals_seconds'] or '[]'}, "
        f"median={pat_crash['median_seconds']}, mean={pat_crash['mean_seconds']})",
        f"- **Pola waktu-antar-kejadian (semua):** `{pat_all['pattern_label']}` "
        f"(interval detik: {pat_all['intervals_seconds'] or '[]'})",
        "",
    ]

    if report["incidents"]:
        lines.extend(
            [
                "## Daftar Kejadian",
                "",
                "| # | Baris | Cap Waktu | Organ | Jenis | Ringkasan Baris |",
                "| ---: | ---: | --- | --- | --- | --- |",
            ]
        )
        for ev in report["incidents"]:
            ts = ev["timestamp_raw"] or "-"
            preview = ev["line"].replace("|", "\\|")
            if len(preview) > 100:
                preview = preview[:97] + "..."
            lines.append(
                f"| {ev['index']} | {ev['line_number']} | `{ts}` | `{ev['organ']}` | `{ev['category']}` ({ev['severity']}) | `{preview}` |"
            )
        lines.append("")
        lines.append("## Konteks Sebelum Kejadian")
        lines.append("")
        for ev in report["incidents"]:
            lines.append(
                f"### Kejadian #{ev['index']} — `{ev['category']}` pada baris {ev['line_number']} (`{ev['timestamp_raw'] or '-'}`)"
            )
            lines.append("")
            lines.append("```text")
            for c in ev["context_before"]:
                lines.append(f"L{c['line_number']}: {c['text']}")
            lines.append(f">> L{ev['line_number']}: {ev['line']}")
            lines.append("```")
            lines.append("")
    else:
        lines.append("Tidak ditemukan kejadian jatuh atau restart pada snapshot log ini.")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Analisis forensik baca-saja atas snapshot log/journal jatuh & restart organ."
    )
    parser.add_argument("log_file", help="Path berkas snapshot log/journal teks.")
    parser.add_argument(
        "--context-lines",
        type=int,
        default=5,
        help="Jumlah baris konteks sebelum kejadian jatuh yang disertakan (default: 5).",
    )
    parser.add_argument(
        "--year",
        type=int,
        default=2026,
        help="Tahun bawaan untuk cap waktu syslog tanpa tahun (default: 2026).",
    )
    parser.add_argument(
        "--format",
        choices=("json", "markdown"),
        default="json",
        help="Format keluaran ke stdout (default: json).",
    )
    parser.add_argument("--json-out", help="Simpan laporan JSON ke berkas ini.")
    parser.add_argument("--markdown-out", help="Simpan laporan Markdown ke berkas ini.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        report = analyze_log_file(
            Path(args.log_file),
            context_lines=args.context_lines,
            default_year=args.year,
        )
    except OrganForensicsError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    md_text = render_markdown(report)
    json_text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"

    if args.json_out:
        out_p = Path(args.json_out)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(json_text, encoding="utf-8")
    if args.markdown_out:
        md_p = Path(args.markdown_out)
        md_p.parent.mkdir(parents=True, exist_ok=True)
        md_p.write_text(md_text, encoding="utf-8")

    sys.stdout.write(md_text if args.format == "markdown" else json_text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
