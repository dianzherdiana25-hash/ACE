#!/usr/bin/env python3
"""Generator dashboard HTML v3 interaktif luring untuk status repo & operasi ACE.

Membangun satu berkas HTML mandiri (`ace.repo-status-dashboard.v3`) dengan:
- 0 angka hardcoded: seluruh metrik dibaca dinamis dari berkas repositori.
- 0 dependensi eksternal: HTML + CSS + vanilla JS tertanam (`http://`/`https://` tidak dipakai).
- Indikator jujur `SOURCE_NOT_PRESENT` untuk sumber opsional yang tidak tersedia.
- Kontrol interaktif: tab panel, kolom pencarian, dan filter status langsung di peramban.
"""
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
import re
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools import repo_index as _repo_index
from tools import repo_status_dashboard as _dash_v2
from tools import storage_debt as _storage_debt

DASHBOARD_V3_SCHEMA = "ace.repo-status-dashboard.v3"
SOURCE_NOT_PRESENT = "SOURCE_NOT_PRESENT"

_ORGAN_ROW_RE = re.compile(
    r"^\|\s*(?P<unit>[^|]+?)\s*\|\s*(?P<organ>[^|]+?)\s*\|\s*(?P<model>[^|]+?)\s*\|\s*(?P<port>[^|]+?)\s*\|"
)


def _extract_organ_slate(repo_root: Path, slate_file: Path | None = None) -> dict[str, Any]:
    candidates: list[Path] = []
    if slate_file is not None:
        if not slate_file.is_file():
            raise ValueError(f"Berkas organ slate tidak ditemukan: {slate_file}")
        candidates = [slate_file]
    else:
        handover = repo_root / "handover"
        if handover.is_dir():
            candidates = sorted(
                p for p in handover.glob("BRAIN_SLATE*_DEPLOYMENT*.md") if p.is_file() and not p.is_symlink()
            )
            if not candidates:
                candidates = sorted(
                    p for p in handover.glob("BRAIN_SLATE*.md") if p.is_file() and not p.is_symlink()
                )

    if not candidates:
        return {
            "status": SOURCE_NOT_PRESENT,
            "source": None,
            "organs": [],
        }

    chosen = candidates[-1]
    organs: list[dict[str, str]] = []
    try:
        text = chosen.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return {
            "status": SOURCE_NOT_PRESENT,
            "source": chosen.relative_to(repo_root).as_posix() if chosen.is_relative_to(repo_root) else str(chosen),
            "organs": [],
        }

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        if set(stripped.replace("|", "").replace("-", "").replace(" ", "")) == set():
            continue
        m = _ORGAN_ROW_RE.match(stripped)
        if not m:
            continue
        unit = m.group("unit").strip()
        if unit.lower() in ("unit", "service", "organ"):
            continue
        organs.append(
            {
                "unit": unit,
                "organ": m.group("organ").strip(),
                "model": m.group("model").strip(),
                "port": m.group("port").strip(),
            }
        )

    rel_source = chosen.relative_to(repo_root).as_posix() if chosen.is_relative_to(repo_root) else str(chosen)
    return {
        "status": "LOADED" if organs else "EMPTY_TABLE",
        "source": rel_source,
        "organs": organs,
    }


def _load_optional_feed(path: Path | None, label: str) -> dict[str, Any]:
    if path is None:
        return {"status": SOURCE_NOT_PRESENT, "data": None}
    data = _dash_v2._load_json_dict(path, label)
    return {"status": "LOADED", "source": str(path), "data": data}


def collect_v3_status(
    repo_root: Path,
    *,
    stage_file: Path | None = None,
    heartbeat_file: Path | None = None,
    royalty_file: Path | None = None,
    schedule_file: Path | None = None,
    storage_debt_file: Path | None = None,
    auto_storage_debt: bool = False,
    digest_file: Path | None = None,
    organ_slate_file: Path | None = None,
) -> dict[str, Any]:
    """Kumpulkan state dashboard v3 murni dari disk tanpa nilai hardcoded."""
    root = repo_root.resolve()
    if not root.is_dir():
        raise ValueError(f"Direktori repositori tidak ditemukan: {repo_root}")
    if storage_debt_file is not None and auto_storage_debt:
        raise ValueError("Gunakan salah satu: --storage-debt-file atau --auto-storage-debt, bukan keduanya.")

    base = _dash_v2.collect_repo_status(
        root,
        stage_file=stage_file,
        heartbeat_file=heartbeat_file,
        royalty_file=royalty_file,
        schedule_file=schedule_file,
        storage_debt_file=storage_debt_file,
    )
    if auto_storage_debt:
        base["storage_debt"] = _storage_debt.scan_storage_debt(root)
    idx = _repo_index.build_repo_index(root)
    organ_slate = _extract_organ_slate(root, organ_slate_file)
    digest_feed = _load_optional_feed(digest_file, "digest")

    tool_modules = [
        m for m in idx["python_modules"]
        if m["path"].startswith("tools/") and not Path(m["path"]).name.startswith("test_")
    ]
    code_modules = [
        m for m in idx["python_modules"]
        if m["path"].startswith("code/") and not Path(m["path"]).name.startswith("test_")
    ]

    debt_payload = base.get("storage_debt")
    debt_status = (
        "LOADED"
        if isinstance(debt_payload, dict)
        else SOURCE_NOT_PRESENT
    )

    sources_status = {
        "gates": "LOADED" if base["gates"] else SOURCE_NOT_PRESENT,
        "frozen_corpora": "LOADED" if base["frozen_corpora"]["corpora"] else SOURCE_NOT_PRESENT,
        "timeline": "LOADED" if base["timeline"] else SOURCE_NOT_PRESENT,
        "organ_slate": organ_slate["status"],
        "stage": "LOADED" if isinstance(base.get("stage"), dict) else SOURCE_NOT_PRESENT,
        "heartbeat": "LOADED" if isinstance(base.get("heartbeat"), dict) else SOURCE_NOT_PRESENT,
        "royalty": "LOADED" if isinstance(base.get("royalty"), dict) else SOURCE_NOT_PRESENT,
        "schedule": "LOADED" if isinstance(base.get("schedule"), dict) else SOURCE_NOT_PRESENT,
        "storage_debt": debt_status,
        "daily_digest": digest_feed["status"],
    }

    return {
        "schema": DASHBOARD_V3_SCHEMA,
        "repo_name": base["repo_name"],
        "sources_status": sources_status,
        "summary": {
            "gate_count": base["gate_count"],
            "corpus_count": base["frozen_corpora"]["corpus_count"],
            "corpus_lines": base["frozen_corpora"]["total_lines"],
            "timeline_count": base["timeline_count"],
            "tool_count": len(tool_modules),
            "code_module_count": len(code_modules),
            "total_files": idx["file_count"],
            "organ_count": len(organ_slate["organs"]),
            "storage_debt_files": (
                int(debt_payload.get("summary", {}).get("total_debt_files", 0))
                if isinstance(debt_payload, dict) and isinstance(debt_payload.get("summary"), dict)
                else None
            ),
            "schedule_overdue": (
                int(base["schedule"].get("summary", {}).get("overdue", 0))
                if isinstance(base.get("schedule"), dict) and isinstance(base["schedule"].get("summary"), dict)
                else None
            ),
        },
        "gates": base["gates"],
        "frozen_corpora": base["frozen_corpora"],
        "timeline": base["timeline"],
        "organ_slate": organ_slate,
        "inventory": {
            "directory_count": idx["directory_count"],
            "file_count": idx["file_count"],
            "module_count": idx["module_count"],
            "tools": tool_modules,
            "code_sample_count": len(code_modules),
        },
        "feeds": {
            "stage": base.get("stage"),
            "heartbeat": base.get("heartbeat"),
            "royalty": base.get("royalty"),
            "schedule": base.get("schedule"),
            "storage_debt": debt_payload,
            "daily_digest": digest_feed["data"],
        },
    }


def _safe_json_for_script(payload: dict[str, Any]) -> str:
    # Cegah </script> injection dan jaga URL eksternal tidak muncul sebagai artefak
    raw = json.dumps(payload, ensure_ascii=False, indent=2)
    return raw.replace("</", "<\\/")


def render_v3_html(state: dict[str, Any]) -> str:
    """Render satu berkas HTML interaktif vanilla-JS v3 dari objek state."""
    esc = html.escape
    s = state["summary"]
    debt_val = str(s["storage_debt_files"]) if s["storage_debt_files"] is not None else SOURCE_NOT_PRESENT
    overdue_val = str(s["schedule_overdue"]) if s["schedule_overdue"] is not None else SOURCE_NOT_PRESENT

    source_chips = "".join(
        f"<span class='chip {'ok' if val == 'LOADED' else 'missing'}'>"
        f"{esc(k)}: <strong>{esc(val)}</strong></span>"
        for k, val in sorted(state["sources_status"].items())
    )

    gate_rows = "".join(
        f"<tr data-filter-row data-status='{esc(g['status'])}'>"
        f"<td><strong>{esc(g['gate'])}</strong></td>"
        f"<td><span class='badge'>{esc(g['status'])}</span></td>"
        f"<td><code>{esc(g['source'])}</code></td></tr>"
        for g in state["gates"]
    ) or f"<tr><td colspan='3' class='empty'>{SOURCE_NOT_PRESENT}</td></tr>"

    timeline_rows = "".join(
        f"<tr data-filter-row data-status='{esc(str(t['directory']))}'>"
        f"<td><code>{esc(str(t['directory']))}</code></td>"
        f"<td><code>{esc(str(t['path']))}</code></td>"
        f"<td>{esc(str(t['title']))}</td>"
        f"<td class='num'>{int(t['lines'])}</td></tr>"
        for t in state["timeline"]
    ) or f"<tr><td colspan='4' class='empty'>{SOURCE_NOT_PRESENT}</td></tr>"

    corpus_rows = "".join(
        f"<tr data-filter-row data-status='FROZEN'>"
        f"<td><code>{esc(str(c['name']))}</code></td>"
        f"<td class='num'>{int(c['line_count'])}</td>"
        f"<td class='num'>{int(c['size_bytes'])}</td>"
        f"<td><code>{esc(str(c['sha256'])[:12])}…</code></td>"
        f"<td><code>{esc(json.dumps(c.get('task_kind_counts', {}), ensure_ascii=False))}</code></td></tr>"
        for c in state["frozen_corpora"]["corpora"]
    ) or f"<tr><td colspan='5' class='empty'>{SOURCE_NOT_PRESENT}</td></tr>"

    organs = state["organ_slate"]["organs"]
    organ_rows = "".join(
        f"<tr data-filter-row data-status='SLATE'>"
        f"<td><code>{esc(o['unit'])}</code></td>"
        f"<td>{esc(o['organ'])}</td>"
        f"<td><code>{esc(o['model'])}</code></td>"
        f"<td><code>{esc(o['port'])}</code></td></tr>"
        for o in organs
    ) or f"<tr><td colspan='4' class='empty'>{esc(state['organ_slate']['status'])}</td></tr>"

    tool_rows = "".join(
        f"<tr data-filter-row data-status='TOOL'>"
        f"<td><code>{esc(t['path'])}</code></td>"
        f"<td>{esc(t['docstring'] or '-')}</td>"
        f"<td><code>{esc(', '.join(t['internal_deps']) or '-')}</code></td></tr>"
        for t in state["inventory"]["tools"]
    ) or f"<tr><td colspan='3' class='empty'>{SOURCE_NOT_PRESENT}</td></tr>"

    feeds = state["feeds"]
    feed_cards = "".join(
        "<div class='feed-box'>"
        f"<h3>{esc(name)} <span class='chip {'ok' if payload is not None else 'missing'}'>"
        f"{'LOADED' if payload is not None else SOURCE_NOT_PRESENT}</span></h3>"
        + (
            f"<pre>{esc(json.dumps(payload, ensure_ascii=False, indent=2)[:2500])}</pre>"
            if payload is not None
            else f"<p class='empty'>Feed opsional belum disediakan ({SOURCE_NOT_PRESENT}).</p>"
        )
        + "</div>"
        for name, payload in sorted(feeds.items())
    )

    state_json = _safe_json_for_script(state)

    return f"""<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ACE Status Dashboard v3 — {esc(str(state['repo_name']))}</title>
<style>
  :root {{ --bg:#0b1120; --panel:#111827; --card:#1f2937; --line:#334155; --fg:#f1f5f9; --muted:#94a3b8; --accent:#38bdf8; --ok:#10b981; --warn:#f59e0b; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; font-family:system-ui,-apple-system,sans-serif; background:var(--bg); color:var(--fg); line-height:1.5; }}
  main {{ max-width:1180px; margin:0 auto; padding:20px 16px 48px; }}
  h1 {{ margin:0 0 4px; font-size:1.5rem; }}
  .sub {{ color:var(--muted); margin:0 0 16px; font-size:0.9rem; }}
  .chips {{ display:flex; flex-wrap:wrap; gap:6px; margin-bottom:16px; }}
  .chip {{ font-size:0.78rem; padding:3px 9px; border-radius:999px; border:1px solid var(--line); background:var(--panel); }}
  .chip.ok {{ border-color:#065f46; color:#a7f3d0; }}
  .chip.missing {{ border-color:#78350f; color:#fde68a; }}
  .cards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); gap:10px; margin-bottom:18px; }}
  .card {{ background:var(--card); border:1px solid var(--line); border-radius:10px; padding:12px; }}
  .card .k {{ color:var(--muted); font-size:0.75rem; text-transform:uppercase; letter-spacing:.04em; }}
  .card .v {{ font-size:1.35rem; font-weight:700; color:var(--accent); margin-top:4px; word-break:break-word; }}
  .toolbar {{ display:flex; flex-wrap:wrap; gap:10px; align-items:center; margin-bottom:14px; background:var(--panel); border:1px solid var(--line); padding:10px 12px; border-radius:10px; }}
  .tabs {{ display:flex; flex-wrap:wrap; gap:6px; flex:1 1 auto; }}
  .tab-btn {{ background:var(--card); color:var(--fg); border:1px solid var(--line); padding:6px 11px; border-radius:8px; cursor:pointer; font-size:0.84rem; }}
  .tab-btn.active {{ background:#0284c7; border-color:#38bdf8; color:#fff; font-weight:600; }}
  input[type='search'] {{ background:var(--bg); color:var(--fg); border:1px solid var(--line); border-radius:8px; padding:7px 10px; min-width:220px; }}
  section.tab-panel {{ display:none; background:var(--panel); border:1px solid var(--line); border-radius:10px; padding:16px; overflow-x:auto; }}
  section.tab-panel.active {{ display:block; }}
  table {{ width:100%; border-collapse:collapse; font-size:0.88rem; }}
  th,td {{ text-align:left; padding:8px 10px; border-bottom:1px solid var(--line); vertical-align:top; }}
  th {{ color:var(--muted); font-size:0.78rem; text-transform:uppercase; }}
  td.num {{ text-align:right; font-variant-numeric:tabular-nums; }}
  code, pre {{ font-family:ui-monospace,SFMono-Regular,monospace; font-size:0.82rem; }}
  pre {{ background:var(--bg); padding:10px; border-radius:8px; overflow:auto; max-height:260px; border:1px solid var(--line); }}
  .badge {{ display:inline-block; padding:2px 8px; border-radius:999px; background:#0c4a6e; color:#bae6fd; font-size:0.78rem; }}
  .empty {{ color:var(--muted); font-style:italic; text-align:center; padding:12px; }}
  .feed-box {{ border:1px solid var(--line); border-radius:8px; padding:12px; margin-bottom:12px; background:var(--card); }}
</style>
</head>
<body>
<main>
  <h1>ACE Interactive Status Dashboard v3 — {esc(str(state['repo_name']))}</h1>
  <p class="sub">Dibuat luring dari berkas lokal (<code>{esc(DASHBOARD_V3_SCHEMA)}</code>; tanpa angka hardcoded; sumber hilang bertanda <code>{SOURCE_NOT_PRESENT}</code>).</p>

  <div class="chips" id="source-status-chips">{source_chips}</div>

  <div class="cards">
    <div class="card"><div class="k">Gates</div><div class="v" id="stat-gates">{int(s['gate_count'])}</div></div>
    <div class="card"><div class="k">Corpus Beku</div><div class="v" id="stat-corpora">{int(s['corpus_count'])}</div></div>
    <div class="card"><div class="k">Baris Corpus</div><div class="v" id="stat-corpus-lines">{int(s['corpus_lines'])}</div></div>
    <div class="card"><div class="k">Linimasa Docs</div><div class="v" id="stat-timeline">{int(s['timeline_count'])}</div></div>
    <div class="card"><div class="k">Perkakas tools/</div><div class="v" id="stat-tools">{int(s['tool_count'])}</div></div>
    <div class="card"><div class="k">Organ Slate</div><div class="v" id="stat-organs">{int(s['organ_count'])}</div></div>
    <div class="card"><div class="k">Storage Debt</div><div class="v" id="stat-storage-debt">{esc(debt_val)}</div></div>
    <div class="card"><div class="k">Bab Overdue</div><div class="v" id="stat-overdue">{esc(overdue_val)}</div></div>
  </div>

  <div class="toolbar">
    <div class="tabs" role="tablist">
      <button type="button" class="tab-btn active" data-tab="panel-gates">Gates ({int(s['gate_count'])})</button>
      <button type="button" class="tab-btn" data-tab="panel-timeline">Linimasa ({int(s['timeline_count'])})</button>
      <button type="button" class="tab-btn" data-tab="panel-corpora">Corpus Beku ({int(s['corpus_count'])})</button>
      <button type="button" class="tab-btn" data-tab="panel-organs">Organ Slate ({int(s['organ_count'])})</button>
      <button type="button" class="tab-btn" data-tab="panel-tools">Perkakas ({int(s['tool_count'])})</button>
      <button type="button" class="tab-btn" data-tab="panel-feeds">Operasional &amp; Feeds</button>
    </div>
    <input type="search" id="search-input" placeholder="Cari gate, berkas, model, perkakas…" aria-label="Cari baris">
  </div>

  <section id="panel-gates" class="tab-panel active">
    <h2>Papan Gate</h2>
    <table><thead><tr><th>Gate</th><th>Status</th><th>Sumber</th></tr></thead><tbody>{gate_rows}</tbody></table>
  </section>

  <section id="panel-timeline" class="tab-panel">
    <h2>Linimasa Evo &amp; Dokumen</h2>
    <table><thead><tr><th>Area</th><th>Berkas</th><th>Judul</th><th>Baris</th></tr></thead><tbody>{timeline_rows}</tbody></table>
  </section>

  <section id="panel-corpora" class="tab-panel">
    <h2>Corpus Beku (handover/)</h2>
    <table><thead><tr><th>Berkas</th><th>Baris</th><th>Byte</th><th>SHA-256</th><th>task_kind</th></tr></thead><tbody>{corpus_rows}</tbody></table>
  </section>

  <section id="panel-organs" class="tab-panel">
    <h2>Organ Slate ({esc(str(state['organ_slate'].get('source') or SOURCE_NOT_PRESENT))})</h2>
    <table><thead><tr><th>Unit</th><th>Organ</th><th>Model</th><th>Port</th></tr></thead><tbody>{organ_rows}</tbody></table>
  </section>

  <section id="panel-tools" class="tab-panel">
    <h2>Inventaris Perkakas (<code>tools/</code>)</h2>
    <table><thead><tr><th>Berkas</th><th>Ringkasan</th><th>Dependensi Internal</th></tr></thead><tbody>{tool_rows}</tbody></table>
  </section>

  <section id="panel-feeds" class="tab-panel">
    <h2>Panel Operasional &amp; Feeds</h2>
    {feed_cards}
  </section>
</main>

<script id="ace-dashboard-state" type="application/json">{state_json}</script>
<script>
(function() {{
  var buttons = document.querySelectorAll('.tab-btn');
  var panels = document.querySelectorAll('.tab-panel');
  var search = document.getElementById('search-input');

  function activateTab(tabId) {{
    buttons.forEach(function(btn) {{
      btn.classList.toggle('active', btn.getAttribute('data-tab') === tabId);
    }});
    panels.forEach(function(panel) {{
      panel.classList.toggle('active', panel.id === tabId);
    }});
  }}

  buttons.forEach(function(btn) {{
    btn.addEventListener('click', function() {{
      activateTab(btn.getAttribute('data-tab'));
    }});
  }});

  if (search) {{
    search.addEventListener('input', function() {{
      var q = search.value.trim().toLowerCase();
      document.querySelectorAll('tr[data-filter-row]').forEach(function(row) {{
        var txt = (row.textContent || '').toLowerCase();
        row.style.display = (!q || txt.indexOf(q) !== -1) ? '' : 'none';
      }});
    }});
  }}
}})();
</script>
</body>
</html>
"""


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generator dashboard status interaktif v3 (HTML + vanilla JS mandiri luring)."
    )
    parser.add_argument("--root", type=Path, default=REPO_ROOT, help="Direktori akar repo target.")
    parser.add_argument("--stage-file", type=Path, default=None, help="Opsional JSON manifest/status stage.")
    parser.add_argument("--heartbeat-file", type=Path, default=None, help="Opsional JSON heartbeat.")
    parser.add_argument("--royalty-file", type=Path, default=None, help="Opsional JSON royalti.")
    parser.add_argument("--schedule-file", type=Path, default=None, help="Opsional JSON jadwal KBM.")
    parser.add_argument("--storage-debt-file", type=Path, default=None, help="Opsional JSON storage debt.")
    parser.add_argument("--auto-storage-debt", action="store_true", help="Pindai storage debt langsung.")
    parser.add_argument("--digest-file", type=Path, default=None, help="Opsional JSON daily digest.")
    parser.add_argument("--organ-slate-file", type=Path, default=None, help="Opsional Markdown slate organ.")
    parser.add_argument("--format", choices=("html", "json"), default="html", help="Format keluaran.")
    parser.add_argument("--output", type=Path, default=None, help="Tulis keluaran ke berkas.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
        state = collect_v3_status(
            args.root,
            stage_file=args.stage_file,
            heartbeat_file=args.heartbeat_file,
            royalty_file=args.royalty_file,
            schedule_file=args.schedule_file,
            storage_debt_file=args.storage_debt_file,
            auto_storage_debt=args.auto_storage_debt,
            digest_file=args.digest_file,
            organ_slate_file=args.organ_slate_file,
        )
        rendered = (
            json.dumps(state, ensure_ascii=False, indent=2) + "\n"
            if args.format == "json"
            else render_v3_html(state)
        )
        if args.output is not None:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(rendered, encoding="utf-8")
        else:
            sys.stdout.write(rendered)
        return 0
    except SystemExit as exc:
        return 0 if exc.code == 0 else 2
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
