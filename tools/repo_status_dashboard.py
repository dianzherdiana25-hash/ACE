#!/usr/bin/env python3
"""Generator dashboard HTML tunggal mandiri v2 untuk status repo & operasi ACE (WS-E #13).

Membaca secara dinamis seluruh angka dan status langsung dari berkas repositori
(tanpa angka hardcoded dan tanpa kueri daftar PR GitHub):
1. Papan gate dari berkas Markdown di `docs/` dan `handover/`.
2. Corpus beku di `handover/` (memakai `tools.corpus_registry` bila tersedia).
3. Linimasa evo/checkpoint/verdict dari `handover/` dan `docs/`.
4. Panel operasional v2 opsional:
   - `--stage-file`: status berkas/manifest staging (`ace.stage-verify.v1` / ringkasan JSON)
   - `--heartbeat-file`: detak jantung proses / daemon lokal JSON
   - `--royalty-file`: rekap royalti KBM (`ace.royalty-summary.v1`, WS-C #9)
   - `--schedule-file`: jadwal produksi serial KBM (`ace.kbm-schedule.v1`, WS-C #10)
   - `--storage-debt-file`: utang artefak belum di-commit/push per program (`ace.storage-debt.v1`, WS-E #14)
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import html
import importlib
import json
import os
from pathlib import Path
import re
import sys
from typing import Any

DASHBOARD_SCHEMA = "ace.repo-status-dashboard.v2"
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

_NATURAL_RE = re.compile(r"(\d+)")
_STATUS_WORD = (
    r"(?:PASS|FAIL|MEASURED|DEMONSTRATED|NOT_DEMONSTRATED|SPECIALIZATION|"
    r"INHERITANCE_DEMONSTRATED|NOT_ASSESSED|BLOCKED|PENDING|IN_FLIGHT|LOCKED|UNVERIFIED)"
)
_GATE_LINE_RE = re.compile(
    rf"(?<![\w-])(G\d+)(?![\w-])\s*(?::|\||—)\s*"
    rf"({_STATUS_WORD}(?:\s*[—\-/]\s*{_STATUS_WORD})*)"
)
_GATE_INLINE_RE = re.compile(rf"(?<![\w-])(G\d+)\s+({_STATUS_WORD})\b")
_TIMELINE_NAME_RE = re.compile(r"(EVO|ADDENDUM|CHECKPOINT|VERDICT|PREREG)", re.IGNORECASE)


def _natural_key(text: str) -> list[Any]:
    return [int(part) if part.isdigit() else part.lower() for part in _NATURAL_RE.split(text)]


def _iter_repo_files(base_dir: Path, suffixes: tuple[str, ...]) -> list[Path]:
    if not base_dir.is_dir():
        return []
    root = base_dir.resolve()
    found: list[Path] = []
    for cur_dir, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames.sort()
        filenames.sort()
        cur = Path(cur_dir)
        for name in filenames:
            p = cur / name
            if p.is_symlink():
                continue
            if p.suffix.lower() in suffixes:
                found.append(p)
    found.sort(key=lambda p: _natural_key(p.relative_to(root).as_posix()))
    return found


def extract_gate_board(repo_root: Path) -> list[dict[str, str]]:
    """Ekstrak papan status gate (`G0`, `G1`, ...) langsung dari Markdown repo."""
    root = repo_root.resolve()
    candidates: list[Path] = []
    for sub in ("docs", "handover"):
        candidates.extend(_iter_repo_files(root / sub, (".md",)))

    gates: dict[str, dict[str, str]] = {}
    for path in candidates:
        rel = path.relative_to(root).as_posix()
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for line in text.splitlines():
            clean_line = re.sub(r"`[^`]*`", "", line)
            clean_line = clean_line.replace("*", "").strip()
            if not clean_line:
                continue
            matched = list(_GATE_LINE_RE.finditer(clean_line))
            if not matched:
                matched = list(_GATE_INLINE_RE.finditer(clean_line))
            for m in matched:
                gate_id = m.group(1).strip()
                status = re.sub(r"\s+", " ", m.group(2)).strip(" .:-")
                if status:
                    gates[gate_id] = {
                        "gate": gate_id,
                        "status": status,
                        "source": rel,
                    }

    return [gates[k] for k in sorted(gates, key=_natural_key)]


def _scan_corpora_fallback(handover_dir: Path) -> dict[str, Any]:
    root = handover_dir.resolve()
    entries: list[dict[str, Any]] = []
    for path in _iter_repo_files(root, (".jsonl",)):
        if "corpus" not in path.name.lower():
            continue
        counts: Counter[str] = Counter()
        line_count = 0
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        for raw_line in lines:
            if not raw_line.strip():
                continue
            line_count += 1
            try:
                obj = json.loads(raw_line)
            except json.JSONDecodeError:
                obj = None
            if isinstance(obj, dict):
                tk = obj.get("task_kind")
                label = tk.strip() if isinstance(tk, str) and tk.strip() else "unknown"
            else:
                label = "unknown"
            counts[label] += 1
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        entries.append(
            {
                "name": path.relative_to(root).as_posix(),
                "line_count": line_count,
                "size_bytes": path.stat().st_size,
                "sha256": digest,
                "task_kind_counts": {k: counts[k] for k in sorted(counts)},
            }
        )
    entries.sort(key=lambda e: e["name"])
    return {"corpus_count": len(entries), "corpora": entries}


def _safe_int(value: Any, default: int = 0) -> int:
    if value is None or isinstance(value, bool):
        return default
    if isinstance(value, float) and (value != value or abs(value) == float("inf")):
        return default
    try:
        return int(value)
    except (ValueError, TypeError, OverflowError):
        return default


def extract_frozen_corpora(repo_root: Path) -> dict[str, Any]:
    """Muat daftar corpus beku dari `handover/` via `corpus_registry` bila ada."""
    handover_dir = repo_root.resolve() / "handover"
    if not handover_dir.is_dir():
        return {"corpus_count": 0, "total_lines": 0, "total_bytes": 0, "corpora": []}

    data: dict[str, Any]
    try:
        reg_mod = importlib.import_module("tools.corpus_registry")
        data = reg_mod.scan_corpora(handover_dir)
    except Exception:
        data = _scan_corpora_fallback(handover_dir)

    corpora = [c for c in (data.get("corpora", []) if isinstance(data.get("corpora"), list) else []) if isinstance(c, dict)]
    total_lines = sum(_safe_int(c.get("line_count", 0)) for c in corpora)
    total_bytes = sum(_safe_int(c.get("size_bytes", 0)) for c in corpora)
    return {
        "corpus_count": len(corpora),
        "total_lines": total_lines,
        "total_bytes": total_bytes,
        "corpora": corpora,
    }


def _extract_doc_title(path: Path) -> str:
    try:
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                return stripped.lstrip("#").strip()
    except OSError:
        pass
    return path.stem


def extract_evo_timeline(repo_root: Path) -> list[dict[str, Any]]:
    """Kumpulkan dokumen evo/addendum/checkpoint/verdict dari `handover/` dan `docs/`."""
    root = repo_root.resolve()
    items: list[dict[str, Any]] = []
    for sub in ("handover", "docs"):
        for path in _iter_repo_files(root / sub, (".md",)):
            if not _TIMELINE_NAME_RE.search(path.name):
                continue
            rel = path.relative_to(root).as_posix()
            text = path.read_text(encoding="utf-8", errors="ignore")
            items.append(
                {
                    "path": rel,
                    "directory": sub,
                    "title": _extract_doc_title(path),
                    "lines": len(text.splitlines()),
                    "bytes": path.stat().st_size,
                }
            )
    items.sort(key=lambda item: _natural_key(item["path"]))
    return items


def _load_json_dict(path: Path | None, label: str) -> dict[str, Any] | None:
    if path is None:
        return None
    if not path.is_file():
        raise ValueError(f"Berkas {label} tidak ditemukan: {path}")
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Gagal membaca JSON {label} '{path}': {exc}") from exc
    if not isinstance(parsed, dict):
        raise ValueError(f"Berkas {label} '{path}' wajib berupa objek JSON.")
    return parsed


def collect_repo_status(
    repo_root: Path,
    *,
    stage_file: Path | None = None,
    heartbeat_file: Path | None = None,
    royalty_file: Path | None = None,
    schedule_file: Path | None = None,
    storage_debt_file: Path | None = None,
) -> dict[str, Any]:
    """Kumpulkan seluruh status repositori + panel operasional v2 dari disk."""
    root = repo_root.resolve()
    if not root.is_dir():
        raise ValueError(f"Direktori repositori tidak ditemukan: {repo_root}")
    gates = extract_gate_board(root)
    corpora = extract_frozen_corpora(root)
    timeline = extract_evo_timeline(root)

    return {
        "schema": DASHBOARD_SCHEMA,
        "repo_name": root.name,
        "gate_count": len(gates),
        "gates": gates,
        "frozen_corpora": corpora,
        "timeline_count": len(timeline),
        "timeline": timeline,
        "stage": _load_json_dict(stage_file, "stage"),
        "heartbeat": _load_json_dict(heartbeat_file, "heartbeat"),
        "royalty": _load_json_dict(royalty_file, "royalty"),
        "schedule": _load_json_dict(schedule_file, "schedule"),
        "storage_debt": _load_json_dict(storage_debt_file, "storage_debt"),
    }


def _render_stage_section(stage: dict[str, Any] | None) -> str:
    esc = html.escape
    if stage is None:
        return "<p class='empty'>Tidak ada berkas staging (`--stage-file`) dimuat.</p>"
    files = stage.get("files") if isinstance(stage.get("files"), list) else []
    status_label = stage.get("status")
    if status_label is None and "passed" in stage:
        status_label = "PASS" if stage["passed"] else "FAIL"
    meta_html = (
        f"<p class='meta'>Schema: <code>{esc(str(stage.get('schema', '-')))}</code> "
        f"| Status: <span class='badge'>{esc(str(status_label or 'LOADED'))}</span> "
        f"| Berkas: <strong>{_safe_int(stage.get('file_count'), len(files))}</strong></p>"
    )
    rows = "".join(
        "<tr>"
        f"<td><code>{esc(str(f.get('path', f.get('name', '-'))))}</code></td>"
        f"<td class='num'>{_safe_int(f.get('size', f.get('size_bytes', 0)))}</td>"
        f"<td><code>{esc(str(f.get('sha256', '-'))[:12])}…</code></td>"
        "</tr>"
        for f in files[:25]
        if isinstance(f, dict)
    ) or "<tr><td colspan='3' class='empty'>Manifest staging kosong (0 berkas).</td></tr>"
    return (
        meta_html
        + "<table><thead><tr><th>Berkas Staging</th><th>Byte</th><th>SHA-256</th></tr></thead>"
        + f"<tbody>{rows}</tbody></table>"
    )


def _render_heartbeat_section(hb: dict[str, Any] | None) -> str:
    esc = html.escape
    if hb is None:
        return "<p class='empty'>Tidak ada berkas heartbeat (`--heartbeat-file`) dimuat.</p>"
    rows = "".join(
        f"<tr><th>{esc(str(k))}</th><td><code>{esc(json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else str(v))}</code></td></tr>"
        for k, v in sorted(hb.items())
    ) or "<tr><td colspan='2' class='empty'>Objek heartbeat kosong.</td></tr>"
    return f"<table><tbody>{rows}</tbody></table>"


def _render_royalty_section(royalty: dict[str, Any] | None) -> str:
    esc = html.escape
    if royalty is None:
        return "<p class='empty'>Tidak ada berkas royalti (`--royalty-file`) dimuat.</p>"
    totals = royalty.get("totals_by_currency", {})
    by_serial = royalty.get("totals_by_serial", {})
    totals_text = ", ".join(f"{cur}: {amt}" for cur, amt in sorted(totals.items())) if isinstance(totals, dict) else "-"
    meta_html = (
        f"<p class='meta'>Total Akumulasi: <strong>{esc(totals_text or '-')}</strong> "
        f"| Baris Valid: <strong>{_safe_int(royalty.get('valid_rows', 0))}</strong> "
        f"(Invalid: {_safe_int(royalty.get('invalid_rows', 0))})</p>"
    )
    serial_items = sorted(by_serial.items()) if isinstance(by_serial, dict) else []
    rows = "".join(
        "<tr>"
        f"<td><code>{esc(str(serial))}</code></td>"
        f"<td><code>{esc(json.dumps(info.get('revenue_by_currency', {}), ensure_ascii=False))}</code></td>"
        f"<td class='num'>{_safe_int(info.get('total_units', 0))}</td>"
        f"<td class='num'>{_safe_int(info.get('row_count', 0))}</td>"
        "</tr>"
        for serial, info in serial_items
        if isinstance(info, dict)
    ) or "<tr><td colspan='4' class='empty'>Belum ada entri penjualan per serial.</td></tr>"
    return (
        meta_html
        + "<table><thead><tr><th>Serial</th><th>Pendapatan</th><th>Unit</th><th>Baris</th></tr></thead>"
        + f"<tbody>{rows}</tbody></table>"
    )


def _render_schedule_section(sched: dict[str, Any] | None) -> str:
    esc = html.escape
    if sched is None:
        return "<p class='empty'>Tidak ada berkas jadwal (`--schedule-file`) dimuat.</p>"
    summary = sched.get("summary", {}) if isinstance(sched.get("summary"), dict) else {}
    serials = sched.get("serials", []) if isinstance(sched.get("serials"), list) else []
    meta_html = (
        f"<p class='meta'>As-of: <code>{esc(str(sched.get('as_of', '-')))}</code> "
        f"| Completed: <strong>{_safe_int(summary.get('completed', 0))}</strong> "
        f"| Scheduled: <strong>{_safe_int(summary.get('scheduled', 0))}</strong> "
        f"| Overdue: <strong>{_safe_int(summary.get('overdue', 0))}</strong></p>"
    )
    rows = "".join(
        "<tr>"
        f"<td><code>{esc(str(s.get('id', '-')))}</code></td>"
        f"<td>{esc(str(s.get('title', '-')))}</td>"
        f"<td class='num'>{_safe_int(s.get('completed_count', 0))}/{_safe_int(s.get('total_chapters', 0))}</td>"
        f"<td class='num'>{_safe_int(s.get('overdue_count', 0))}</td>"
        f"<td><code>{esc(str(s.get('projected_completion_date', '-')))}</code></td>"
        "</tr>"
        for s in serials
        if isinstance(s, dict)
    ) or "<tr><td colspan='5' class='empty'>Belum ada serial pada jadwal.</td></tr>"
    return (
        meta_html
        + "<table><thead><tr><th>ID Serial</th><th>Judul</th><th>Selesai</th><th>Overdue</th><th>Proyeksi Selesai</th></tr></thead>"
        + f"<tbody>{rows}</tbody></table>"
    )


def _render_storage_debt_section(debt: dict[str, Any] | None) -> str:
    esc = html.escape
    if debt is None:
        return "<p class='empty'>Tidak ada berkas storage debt (`--storage-debt-file`) dimuat.</p>"
    summary = debt.get("summary", {}) if isinstance(debt.get("summary"), dict) else {}
    programs = debt.get("programs", {}) if isinstance(debt.get("programs"), dict) else {}
    meta_html = (
        f"<p class='meta'>Total Berkas Belum Ter-commit/Tersinkron: <strong>{_safe_int(summary.get('total_debt_files', 0))}</strong> "
        f"| Total Ukuran: <strong>{_safe_int(summary.get('total_debt_bytes', 0))}</strong> byte</p>"
    )
    rows = "".join(
        "<tr>"
        f"<td><code>{esc(str(prog))}</code></td>"
        f"<td class='num'>{_safe_int(info.get('file_count', 0))}</td>"
        f"<td class='num'>{_safe_int(info.get('total_bytes', 0))}</td>"
        f"<td><code>{esc(', '.join(str(x.get('path', '')) for x in (info.get('files') if isinstance(info.get('files'), list) else [])[:3] if isinstance(x, dict)))}</code></td>"
        "</tr>"
        for prog, info in sorted(programs.items())
        if isinstance(info, dict)
    ) or "<tr><td colspan='4' class='empty'>Tidak ada storage debt tercatat (0 berkas).</td></tr>"
    return (
        meta_html
        + "<table><thead><tr><th>Program / Area</th><th>Jumlah Berkas</th><th>Ukuran (Byte)</th><th>Contoh Path</th></tr></thead>"
        + f"<tbody>{rows}</tbody></table>"
    )


def render_dashboard_html(status: dict[str, Any]) -> str:
    """Render HTML tunggal mandiri v2 (tanpa JS/CSS eksternal) dari objek status."""
    esc = html.escape
    gates = status["gates"]
    corpora = status["frozen_corpora"]
    timeline = status["timeline"]

    gate_rows = "".join(
        f"<tr><td><strong>{esc(g['gate'])}</strong></td>"
        f"<td><span class='badge'>{esc(g['status'])}</span></td>"
        f"<td><code>{esc(g['source'])}</code></td></tr>"
        for g in gates
    ) or "<tr><td colspan='3' class='empty'>Belum ada entri gate terdeteksi.</td></tr>"

    corpus_rows = "".join(
        "<tr>"
        f"<td><code>{esc(str(c['name']))}</code></td>"
        f"<td class='num'>{_safe_int(c.get('line_count', 0))}</td>"
        f"<td class='num'>{_safe_int(c.get('size_bytes', 0))}</td>"
        f"<td><code>{esc(str(c['sha256'])[:12])}…</code></td>"
        f"<td><code>{esc(json.dumps(c.get('task_kind_counts', {}), ensure_ascii=False))}</code></td>"
        "</tr>"
        for c in corpora["corpora"]
    ) or "<tr><td colspan='5' class='empty'>Belum ada berkas corpus beku (*corpus*.jsonl) di handover/.</td></tr>"

    timeline_rows = "".join(
        "<tr>"
        f"<td><code>{esc(str(t['directory']))}</code></td>"
        f"<td><code>{esc(str(t['path']))}</code></td>"
        f"<td>{esc(str(t['title']))}</td>"
        f"<td class='num'>{_safe_int(t.get('lines', 0))}</td>"
        "</tr>"
        for t in timeline
    ) or "<tr><td colspan='4' class='empty'>Belum ada dokumen evo/checkpoint/addendum terdeteksi.</td></tr>"

    debt = status.get("storage_debt") or {}
    debt_files_count = _safe_int(debt.get("summary", {}).get("total_debt_files", 0)) if isinstance(debt.get("summary"), dict) else 0
    sched = status.get("schedule") or {}
    sched_overdue = _safe_int(sched.get("summary", {}).get("overdue", 0)) if isinstance(sched.get("summary"), dict) else 0

    return f"""<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Status Repo {esc(str(status['repo_name']))}</title>
<style>
  :root {{ --bg:#0f172a; --card:#1e293b; --line:#334155; --fg:#e2e8f0; --muted:#94a3b8; --accent:#38bdf8; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; font-family:system-ui,-apple-system,sans-serif; background:var(--bg); color:var(--fg); line-height:1.5; }}
  main {{ max-width:1100px; margin:0 auto; padding:24px 16px 48px; }}
  h1 {{ margin:0 0 6px; font-size:1.5rem; }}
  .sub {{ color:var(--muted); margin:0 0 20px; font-size:0.9rem; }}
  .meta {{ color:var(--muted); margin:0 0 10px; font-size:0.88rem; }}
  .cards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); gap:12px; margin-bottom:24px; }}
  .card {{ background:var(--card); border:1px solid var(--line); border-radius:10px; padding:14px; }}
  .card .k {{ color:var(--muted); font-size:0.8rem; text-transform:uppercase; letter-spacing:.04em; }}
  .card .v {{ font-size:1.5rem; font-weight:700; color:var(--accent); margin-top:4px; }}
  section {{ background:var(--card); border:1px solid var(--line); border-radius:10px; padding:16px; margin-bottom:18px; overflow-x:auto; }}
  h2 {{ margin:0 0 12px; font-size:1.1rem; }}
  table {{ width:100%; border-collapse:collapse; font-size:0.9rem; }}
  th,td {{ text-align:left; padding:8px 10px; border-bottom:1px solid var(--line); vertical-align:top; }}
  th {{ color:var(--muted); font-weight:600; font-size:0.8rem; text-transform:uppercase; }}
  td.num {{ text-align:right; font-variant-numeric:tabular-nums; }}
  code {{ font-family:ui-monospace,SFMono-Regular,monospace; font-size:0.83rem; }}
  .badge {{ display:inline-block; padding:2px 8px; border-radius:999px; background:#0c4a6e; color:#bae6fd; font-size:0.8rem; }}
  .empty {{ color:var(--muted); font-style:italic; text-align:center; }}
</style>
</head>
<body>
<main>
  <h1>Dashboard Status Repo v2 — {esc(str(status['repo_name']))}</h1>
  <p class="sub">Dibangun luring dari berkas lokal (<code>{esc(DASHBOARD_SCHEMA)}</code>; tanpa PR list GitHub).</p>

  <div class="cards">
    <div class="card"><div class="k">Gate Terdeteksi</div><div class="v" id="stat-gates">{_safe_int(status['gate_count'])}</div></div>
    <div class="card"><div class="k">Corpus Beku</div><div class="v" id="stat-corpora">{_safe_int(corpora['corpus_count'])}</div></div>
    <div class="card"><div class="k">Total Baris Corpus</div><div class="v" id="stat-corpus-lines">{_safe_int(corpora['total_lines'])}</div></div>
    <div class="card"><div class="k">Dokumen Evo / Docs</div><div class="v" id="stat-timeline">{_safe_int(status['timeline_count'])}</div></div>
    <div class="card"><div class="k">Bab Overdue</div><div class="v" id="stat-overdue">{sched_overdue}</div></div>
    <div class="card"><div class="k">Storage Debt Berkas</div><div class="v" id="stat-storage-debt">{debt_files_count}</div></div>
  </div>

  <section id="sec-gates">
    <h2>Papan Gate</h2>
    <table>
      <thead><tr><th>Gate</th><th>Status Terbaca</th><th>Sumber</th></tr></thead>
      <tbody>{gate_rows}</tbody>
    </table>
  </section>

  <section id="sec-corpora">
    <h2>Corpus Beku (handover/)</h2>
    <table>
      <thead><tr><th>Berkas</th><th>Baris</th><th>Byte</th><th>SHA-256</th><th>Sebaran task_kind</th></tr></thead>
      <tbody>{corpus_rows}</tbody>
    </table>
  </section>

  <section id="sec-timeline">
    <h2>Linimasa Evo &amp; Dokumen</h2>
    <table>
      <thead><tr><th>Area</th><th>Berkas</th><th>Judul</th><th>Baris</th></tr></thead>
      <tbody>{timeline_rows}</tbody>
    </table>
  </section>

  <section id="sec-stage">
    <h2>Stage Verifikasi / Staging</h2>
    {_render_stage_section(status.get('stage'))}
  </section>

  <section id="sec-heartbeat">
    <h2>Heartbeat Layanan Lokal</h2>
    {_render_heartbeat_section(status.get('heartbeat'))}
  </section>

  <section id="sec-royalty">
    <h2>Ringkasan Royalti KBM</h2>
    {_render_royalty_section(status.get('royalty'))}
  </section>

  <section id="sec-schedule">
    <h2>Jadwal Produksi KBM</h2>
    {_render_schedule_section(status.get('schedule'))}
  </section>

  <section id="sec-storage-debt">
    <h2>Utang Penyimpanan / Artefak Belum Ter-commit</h2>
    {_render_storage_debt_section(status.get('storage_debt'))}
  </section>
</main>
</body>
</html>
"""


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Bangun dashboard HTML v2 status repo dan operasional ACE tanpa dependensi luar."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=REPO_ROOT,
        help="Direktori akar repo target (default: akar repo ACE).",
    )
    parser.add_argument("--stage-file", type=Path, default=None, help="Opsional JSON manifest/status stage.")
    parser.add_argument("--heartbeat-file", type=Path, default=None, help="Opsional JSON heartbeat daemon.")
    parser.add_argument("--royalty-file", type=Path, default=None, help="Opsional JSON ringkasan royalti (`ace.royalty-summary.v1`).")
    parser.add_argument("--schedule-file", type=Path, default=None, help="Opsional JSON jadwal KBM (`ace.kbm-schedule.v1`).")
    parser.add_argument("--storage-debt-file", type=Path, default=None, help="Opsional JSON storage debt (`ace.storage-debt.v1`).")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Tulis keluaran HTML ke berkas (default: cetak ke stdout).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
        status = collect_repo_status(
            args.root,
            stage_file=args.stage_file,
            heartbeat_file=args.heartbeat_file,
            royalty_file=args.royalty_file,
            schedule_file=args.schedule_file,
            storage_debt_file=args.storage_debt_file,
        )
        html_doc = render_dashboard_html(status)
        if args.output is not None:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(html_doc, encoding="utf-8")
        else:
            print(html_doc, end="")
        return 0
    except SystemExit as exc:
        return 0 if exc.code == 0 else 2
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
