#!/usr/bin/env python3
"""Generator dashboard HTML tunggal (tanpa dependensi luar) untuk status repo ACE.

Membaca secara dinamis seluruh angka dan status langsung dari berkas repositori
(tanpa angka hardcoded dan tanpa kueri daftar PR GitHub):
1. Papan gate dari berkas Markdown di `docs/` dan `handover/`.
2. Corpus beku di `handover/` (memakai `tools.corpus_registry` bila tersedia).
3. Linimasa evo/checkpoint/verdict dari `handover/` dan `docs/`.
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

DASHBOARD_SCHEMA = "ace.repo-status-dashboard.v1"
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

    corpora = list(data.get("corpora", []))
    total_lines = sum(int(c.get("line_count", 0)) for c in corpora)
    total_bytes = sum(int(c.get("size_bytes", 0)) for c in corpora)
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


def collect_repo_status(repo_root: Path) -> dict[str, Any]:
    """Kumpulkan seluruh status repositori secara dinamis dari disk."""
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
    }


def render_dashboard_html(status: dict[str, Any]) -> str:
    """Render HTML tunggal mandiri (tanpa JS/CSS eksternal) dari objek status."""
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
        f"<td class='num'>{int(c['line_count'])}</td>"
        f"<td class='num'>{int(c['size_bytes'])}</td>"
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
        f"<td class='num'>{int(t['lines'])}</td>"
        "</tr>"
        for t in timeline
    ) or "<tr><td colspan='4' class='empty'>Belum ada dokumen evo/checkpoint/addendum terdeteksi.</td></tr>"

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
  main {{ max-width:1040px; margin:0 auto; padding:24px 16px 48px; }}
  h1 {{ margin:0 0 6px; font-size:1.5rem; }}
  .sub {{ color:var(--muted); margin:0 0 20px; font-size:0.9rem; }}
  .cards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(170px,1fr)); gap:12px; margin-bottom:24px; }}
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
  <h1>Dashboard Status Repo — {esc(str(status['repo_name']))}</h1>
  <p class="sub">Dibangun luring dari berkas lokal (<code>{esc(DASHBOARD_SCHEMA)}</code>; tanpa PR list GitHub).</p>

  <div class="cards">
    <div class="card"><div class="k">Gate Terdeteksi</div><div class="v" id="stat-gates">{int(status['gate_count'])}</div></div>
    <div class="card"><div class="k">Corpus Beku</div><div class="v" id="stat-corpora">{int(corpora['corpus_count'])}</div></div>
    <div class="card"><div class="k">Total Baris Corpus</div><div class="v" id="stat-corpus-lines">{int(corpora['total_lines'])}</div></div>
    <div class="card"><div class="k">Dokumen Evo / Docs</div><div class="v" id="stat-timeline">{int(status['timeline_count'])}</div></div>
  </div>

  <section>
    <h2>Papan Gate</h2>
    <table>
      <thead><tr><th>Gate</th><th>Status Terbaca</th><th>Sumber</th></tr></thead>
      <tbody>{gate_rows}</tbody>
    </table>
  </section>

  <section>
    <h2>Corpus Beku (handover/)</h2>
    <table>
      <thead><tr><th>Berkas</th><th>Baris</th><th>Byte</th><th>SHA-256</th><th>Sebaran task_kind</th></tr></thead>
      <tbody>{corpus_rows}</tbody>
    </table>
  </section>

  <section>
    <h2>Linimasa Evo &amp; Dokumen</h2>
    <table>
      <thead><tr><th>Area</th><th>Berkas</th><th>Judul</th><th>Baris</th></tr></thead>
      <tbody>{timeline_rows}</tbody>
    </table>
  </section>
</main>
</body>
</html>
"""


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Bangun dashboard HTML status repo ACE tanpa dependensi luar."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=REPO_ROOT,
        help="Direktori akar repo target (default: akar repo ACE).",
    )
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
        status = collect_repo_status(args.root)
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
