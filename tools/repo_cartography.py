#!/usr/bin/env python3
"""Kartografer AST statis repositori ACE (subsistem, tepi impor, siklus, zona aman/terlindung).

Memetakan struktur subsistem (`tools/`, `code/*`, `handover/`, `docs/`, `projects/`,
`tests/`, dll.) murni lewat pemindaian AST & pohon berkas tanpa mengimpor atau
mengeksekusi satu modul pun di `code/`. Menghasilkan ringkasan JSON maupun dokumen
Markdown dengan diagram Mermaid `flowchart LR` yang deterministik.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
import re
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools import repo_index as _repo_index

CARTOGRAPHY_SCHEMA = "ace.repo-cartography.v1"
DEFAULT_OUTPUT_REL = "docs/REPO_CARTOGRAPHY.md"

PROTECTED_MODULES_PATHS = frozenset(
    {
        "code/ace_operational/evo0007_run.py",
        "code/ace_operational/abc_v3_scorer.py",
        "code/ace_operational/g1_instrument.py",
        "code/ace_operational/g3_instrument.py",
        "code/ace_operational/g4_instrument.py",
        "code/ace_operational/g5_instrument.py",
        "code/ace_operational/round2_instrument.py",
        "code/ace_operational/memory_writeback.py",
        "code/ace_operational/cognitive_memory.py",
        "code/ace_operational/memory_bridge.py",
        "tools/memory_writeback.py",
        "tools/round2_gate_run.py",
        "tools/abc_v3_run.py",
    }
)


def _subsystem_for_relpath(rel_posix: str) -> str:
    parts = Path(rel_posix).parts
    if len(parts) <= 1:
        return "root"
    top = parts[0]
    if top == "code" and len(parts) >= 3:
        return f"code/{parts[1]}"
    return top


def _zone_for_subsystem(subsystem: str, paths_in_sub: list[str]) -> tuple[str, str]:
    if subsystem == "code/ace_evaluator":
        return ("PROTECTED_INSTRUMENT", "Wilayah evaluator / judge (Engineer Utama saja)")
    if subsystem == "handover":
        return ("FROZEN_CORPUS_SPEC", "Corpus beku, preregistrasi, & custody spec (read-only)")
    if any(p in PROTECTED_MODULES_PATHS for p in paths_in_sub):
        return ("MIXED_PROTECTED", "Memuat instrumen/scorer/memory-write terlindung + modul lain")
    return ("SAFE_WORKSPACE", "Wilayah kerja aman (read-only AST / build tooling)")


def _find_cycles(nodes: list[str], adjacency: dict[str, set[str]]) -> list[list[str]]:
    """Temukan komponen terhubung kuat non-trivial (siklus antar subsistem) secara deterministik."""
    index = 0
    indices: dict[str, int] = {}
    lowlink: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    cycles: list[list[str]] = []

    def strongconnect(start: str) -> None:
        nonlocal index
        call_stack: list[tuple[str, list[str], int]] = []

        def push_node(v: str) -> None:
            nonlocal index
            indices[v] = index
            lowlink[v] = index
            index += 1
            stack.append(v)
            on_stack.add(v)
            neighbors = sorted(adjacency.get(v, set()))
            call_stack.append((v, neighbors, 0))

        push_node(start)
        while call_stack:
            v, neighbors, pos = call_stack[-1]
            if pos < len(neighbors):
                call_stack[-1] = (v, neighbors, pos + 1)
                w = neighbors[pos]
                if w not in indices:
                    push_node(w)
                elif w in on_stack:
                    lowlink[v] = min(lowlink[v], indices[w])
            else:
                call_stack.pop()
                if call_stack:
                    parent = call_stack[-1][0]
                    lowlink[parent] = min(lowlink[parent], lowlink[v])
                if lowlink[v] == indices[v]:
                    scc: list[str] = []
                    while True:
                        w = stack.pop()
                        on_stack.remove(w)
                        scc.append(w)
                        if w == v:
                            break
                    if len(scc) > 1 or (len(scc) == 1 and scc[0] in adjacency.get(scc[0], set())):
                        cycles.append(sorted(scc))

    for node in sorted(nodes):
        if node not in indices:
            strongconnect(node)

    cycles.sort()
    return cycles


def _mermaid_node_id(name: str) -> str:
    clean = re.sub(r"[^a-zA-Z0-9_]", "_", name)
    if not clean or not clean[0].isalpha():
        clean = f"s_{clean}"
    return clean


def build_cartography(
    repo_root: Path,
    *,
    exclude_paths: set[str] | None = None,
) -> dict[str, Any]:
    """Bangun peta kartografi AST deterministik dari `repo_root` tanpa impor modul."""
    root = repo_root.resolve()
    idx = _repo_index.build_repo_index(root)

    excludes = {DEFAULT_OUTPUT_REL}
    if exclude_paths:
        for item in exclude_paths:
            excludes.add(item.lstrip("./"))

    sub_files: dict[str, list[str]] = defaultdict(list)
    for d in idx["directories"]:
        for f in d["files"]:
            rel = f["path"]
            if rel in excludes:
                continue
            sub_files[_subsystem_for_relpath(rel)].append(rel)

    mod_to_sub: dict[str, str] = {}
    sub_prod_mods: dict[str, list[dict[str, Any]]] = defaultdict(list)
    sub_test_mods: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for m in idx["python_modules"]:
        rel = m["path"]
        if rel in excludes:
            continue
        sub = _subsystem_for_relpath(rel)
        mod_to_sub[m["module"]] = sub
        fname = Path(rel).name
        if fname.startswith("test_") or "/tests/" in rel or rel.startswith("tests/"):
            sub_test_mods[sub].append(m)
        else:
            sub_prod_mods[sub].append(m)

    edge_weights: dict[tuple[str, str], int] = defaultdict(int)
    edge_examples: dict[tuple[str, str], set[str]] = defaultdict(set)
    in_degree: dict[str, int] = defaultdict(int)
    out_degree: dict[str, int] = defaultdict(int)
    adjacency: dict[str, set[str]] = defaultdict(set)

    for m in idx["python_modules"]:
        src_rel = m["path"]
        if src_rel in excludes:
            continue
        src_fname = Path(src_rel).name
        if src_fname.startswith("test_"):
            continue
        src_sub = _subsystem_for_relpath(src_rel)
        seen_targets_from_file: set[str] = set()
        for dep_mod in m["internal_deps"]:
            dst_sub = mod_to_sub.get(dep_mod)
            if dst_sub is None or dst_sub == src_sub:
                continue
            pair = (src_sub, dst_sub)
            edge_weights[pair] += 1
            if len(edge_examples[pair]) < 3:
                edge_examples[pair].add(dep_mod)
            if dst_sub not in seen_targets_from_file:
                seen_targets_from_file.add(dst_sub)
            adjacency[src_sub].add(dst_sub)

    edges: list[dict[str, Any]] = []
    for (src, dst), weight in sorted(edge_weights.items(), key=lambda kv: (-kv[1], kv[0][0], kv[0][1])):
        out_degree[src] += 1
        in_degree[dst] += 1
        edges.append(
            {
                "source": src,
                "target": dst,
                "weight": weight,
                "sample_targets": sorted(edge_examples[(src, dst)]),
            }
        )

    all_subsystems = sorted(sub_files)
    subsystems: list[dict[str, Any]] = []
    protected_detected: list[str] = []
    for sub in all_subsystems:
        files = sorted(sub_files[sub])
        zone, zone_note = _zone_for_subsystem(sub, files)
        for p in files:
            if p in PROTECTED_MODULES_PATHS or sub == "code/ace_evaluator":
                if p.endswith(".py") and not Path(p).name.startswith("test_"):
                    protected_detected.append(p)
        subsystems.append(
            {
                "subsystem": sub,
                "zone": zone,
                "zone_note": zone_note,
                "file_count": len(files),
                "prod_module_count": len(sub_prod_mods[sub]),
                "test_module_count": len(sub_test_mods[sub]),
                "in_edge_count": in_degree.get(sub, 0),
                "out_edge_count": out_degree.get(sub, 0),
            }
        )

    cycles = _find_cycles(all_subsystems, adjacency)
    return {
        "schema": CARTOGRAPHY_SCHEMA,
        "repo_name": idx["repo_name"],
        "summary": {
            "subsystem_count": len(subsystems),
            "total_files": sum(s["file_count"] for s in subsystems),
            "total_prod_modules": sum(s["prod_module_count"] for s in subsystems),
            "total_test_modules": sum(s["test_module_count"] for s in subsystems),
            "cross_subsystem_edge_count": len(edges),
            "cycle_scc_count": len(cycles),
            "protected_zone_subsystems": sum(1 for s in subsystems if s["zone"] != "SAFE_WORKSPACE"),
        },
        "subsystems": subsystems,
        "edges": edges,
        "cycles": cycles,
        "protected_sample_paths": sorted(set(protected_detected)),
    }


def render_markdown(carto: dict[str, Any], *, max_diagram_edges: int = 35) -> str:
    """Render hasil kartografi ke dokumen Markdown deterministik dengan Mermaid."""
    s = carto["summary"]
    lines = [
        f"# Kartografi Repositori ACE — {carto['repo_name']}",
        "",
        f"> Peta AST statis deterministik oleh `tools/repo_cartography.py` (`{carto['schema']}`; zero import/eksekusi `code/`).",
        "",
        "## 1. Ringkasan Makro",
        "",
        f"- Schema: `{carto['schema']}`",
        f"- Total subsistem: **{s['subsystem_count']}** (termasuk `{s['protected_zone_subsystems']}` subsistem zona terlindung/beku)",
        f"- Total berkas terpetakan: **{s['total_files']}**",
        f"- Modul Python produksi: **{s['total_prod_modules']}** | Modul tes: **{s['total_test_modules']}**",
        f"- Tepi dependensi lintas subsistem (produksi): **{s['cross_subsystem_edge_count']}**",
        f"- Siklus SCC lintas subsistem: **{s['cycle_scc_count']}**",
        "",
        "## 2. Diagram Dependensi Lintas Subsistem (Top Bobot Impor)",
        "",
    ]

    top_edges = carto["edges"][:max_diagram_edges]
    if top_edges:
        lines.extend(["```mermaid", "flowchart LR"])
        used_nodes: dict[str, str] = {}
        zone_map = {item["subsystem"]: item["zone"] for item in carto["subsystems"]}
        for edge in top_edges:
            for endpoint in (edge["source"], edge["target"]):
                if endpoint not in used_nodes:
                    nid = _mermaid_node_id(endpoint)
                    z = zone_map.get(endpoint, "SAFE_WORKSPACE")
                    tag = "SAFE" if z == "SAFE_WORKSPACE" else z
                    used_nodes[endpoint] = nid
                    lines.append(f'    {nid}["{endpoint} ({tag})"]')
        for edge in top_edges:
            sid = used_nodes[edge["source"]]
            tid = used_nodes[edge["target"]]
            lines.append(f"    {sid} -->|{edge['weight']}| {tid}")
        lines.append("```")
    else:
        lines.append("_Tidak ada tepi impor lintas subsistem yang terdeteksi._")

    lines.extend(
        [
            "",
            "## 3. Inventaris Subsistem & Klasifikasi Zona",
            "",
            "| Subsistem | Zona | Berkas | Modul Prod | Modul Tes | Masuk | Keluar | Catatan |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |",
        ]
    )
    for sub in carto["subsystems"]:
        note = sub["zone_note"].replace("|", "\\|")
        lines.append(
            f"| `{sub['subsystem']}` | `{sub['zone']}` | {sub['file_count']} "
            f"| {sub['prod_module_count']} | {sub['test_module_count']} "
            f"| {sub['in_edge_count']} | {sub['out_edge_count']} | {note} |"
        )

    lines.extend(
        [
            "",
            "## 4. Tepi Ketergantungan Lintas Subsistem (Semua)",
            "",
            "| Asal | Tujuan | Bobot Impor | Contoh Target Modul |",
            "| --- | --- | ---: | --- |",
        ]
    )
    if carto["edges"]:
        for e in carto["edges"]:
            samples = ", ".join(f"`{t}`" for t in e["sample_targets"]) or "-"
            lines.append(f"| `{e['source']}` | `{e['target']}` | {e['weight']} | {samples} |")
    else:
        lines.append("| - | - | 0 | Tidak ada tepi lintas subsistem |")

    lines.extend(["", "## 5. Deteksi Siklus SCC Lintas Subsistem", ""])
    if carto["cycles"]:
        for idx, scc in enumerate(carto["cycles"], start=1):
            joined = " <-> ".join(f"`{n}`" for n in scc)
            lines.append(f"{idx}. {joined}")
    else:
        lines.append("- **Tidak ada siklus** antar subsistem (graf tingkat subsistem asiklik).")

    return "\n".join(lines) + "\n"


def check_cartography(repo_root: Path, target_file: Path) -> tuple[bool, str]:
    root = repo_root.resolve()
    target = target_file if target_file.is_absolute() else (root / target_file)
    excludes: set[str] = set()
    try:
        excludes.add(target.resolve().relative_to(root).as_posix())
    except ValueError:
        pass
    expected = render_markdown(build_cartography(root, exclude_paths=excludes))
    if not target.is_file():
        return False, f"STALE: berkas kartografi tidak ditemukan: {target}"
    actual = target.read_text(encoding="utf-8")
    if actual != expected:
        return False, f"STALE: {target} berbeda dari kondisi repositori saat ini."
    return True, f"FRESH: {target} mutakhir dan cocok persis ({len(expected)} karakter)."


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Kartografer AST statis subsistem ACE (Markdown/Mermaid/JSON + --check)."
    )
    parser.add_argument("--root", type=Path, default=REPO_ROOT, help="Direktori akar repo target.")
    parser.add_argument(
        "--format",
        choices=("markdown", "json"),
        default="markdown",
        help="Format keluaran (default: markdown).",
    )
    parser.add_argument("--output", type=Path, default=None, help="Tulis keluaran ke berkas.")
    parser.add_argument(
        "--check",
        type=Path,
        default=None,
        help="Periksa kesegaran berkas Markdown target (exit 0 segar, 1 usang).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
        if args.check is not None:
            fresh, message = check_cartography(args.root, args.check)
            print(message, file=sys.stdout if fresh else sys.stderr)
            return 0 if fresh else 1

        excludes: set[str] = set()
        if args.output is not None:
            out_abs = args.output if args.output.is_absolute() else (args.root.resolve() / args.output)
            try:
                excludes.add(out_abs.resolve().relative_to(args.root.resolve()).as_posix())
            except ValueError:
                pass
        carto = build_cartography(args.root, exclude_paths=excludes)
        rendered = (
            json.dumps(carto, ensure_ascii=False, indent=2) + "\n"
            if args.format == "json"
            else render_markdown(carto)
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
