#!/usr/bin/env python3
"""Generator checklist Markdown pendirian rumah kedua (instance baru) berbasis berkas sumber.

Kenapa modul ini ada:
`tools/instance_kit.py` dan `tools/migration_rehearsal.py` sudah menyediakan
isolasi konfigurasi dan latihan pemulihan bundel, tetapi operator tetap
memerlukan checklist pendirian langkah demi langkah yang seluruh isinya
(aset repo, prasyarat, langkah, dan verifikasi) dibaca langsung dari berkas
inventaris repo serta berkas kebutuhan bernama — bukan dikarang secara manual
agar tidak ada langkah atau berkas fiktif saat memindahkan ACE ke mesin baru.

Exit code:
- 0: checklist berhasil dibangun (dan seluruh aset ditemukan bila `--strict`)
- 1: `--strict` aktif dan ada aset kebutuhan yang tidak tercatat di inventaris
- 2: argumen CLI atau berkas masukan tidak sah
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath
import re
import sys
from typing import Any

SECOND_HOME_SCHEMA = "ace.second-home-checklist.v1"

_MD_DIR_HEADING_RE = re.compile(r"^###\s+`([^`]+)`")
_MD_FILE_BULLET_RE = re.compile(r"^-\s+`([^`]+)`")
_SLUG_RE = re.compile(r"[^a-z0-9]+")


class SecondHomeError(ValueError):
    """Kesalahan berkas inventaris, berkas kebutuhan, atau parameter CLI."""


def _norm_posix(raw: str) -> str:
    cleaned = raw.strip().replace("\\", "/")
    while cleaned.startswith("./"):
        cleaned = cleaned[2:]
    cleaned = cleaned.rstrip("/")
    if not cleaned:
        return ""
    return PurePosixPath(cleaned).as_posix()


def _as_str_list(value: Any, field_name: str) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        s = value.strip()
        return [s] if s else []
    if isinstance(value, list):
        out: list[str] = []
        for idx, item in enumerate(value):
            if not isinstance(item, str) or not item.strip():
                raise SecondHomeError(f"Elemen '{field_name}[{idx}]' wajib string tidak kosong.")
            out.append(item.strip())
        return out
    raise SecondHomeError(f"Field '{field_name}' wajib string atau list string.")


def _slugify(name: str) -> str:
    slug = _SLUG_RE.sub("-", name.strip().lower()).strip("-")
    return slug or "step"


def load_inventory(path: Path) -> set[str]:
    """Muat daftar jalur berkas repo dari berkas inventaris JSON atau Markdown (`REPO_INDEX.md`)."""
    if not path.is_file():
        raise SecondHomeError(f"Berkas inventaris tidak ditemukan: {path}")
    try:
        raw_text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise SecondHomeError(f"Gagal membaca berkas inventaris '{path}': {exc}") from exc

    stripped = raw_text.lstrip()
    paths: set[str] = set()

    if path.suffix.lower() == ".json" or stripped.startswith("{") or stripped.startswith("["):
        try:
            data = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            raise SecondHomeError(f"Inventaris JSON tidak sah '{path}': {exc.msg}") from exc
        paths.update(_extract_paths_from_json_inventory(data))
    else:
        current_dir: str | None = None
        for line in raw_text.splitlines():
            m_dir = _MD_DIR_HEADING_RE.match(line.strip())
            if m_dir:
                current_dir = m_dir.group(1).strip()
                continue
            m_file = _MD_FILE_BULLET_RE.match(line.strip())
            if m_file:
                entry = m_file.group(1).strip()
                if current_dir and current_dir != "." and "/" not in entry:
                    joined = f"{current_dir.rstrip('/')}/{entry}"
                else:
                    joined = entry
                norm = _norm_posix(joined)
                if norm:
                    paths.add(norm)

    if not paths:
        raise SecondHomeError(f"Inventaris '{path}' tidak memuat satu pun jalur berkas.")
    return paths


def _extract_paths_from_json_inventory(data: Any) -> set[str]:
    paths: set[str] = set()
    if isinstance(data, list):
        for item in data:
            if isinstance(item, str) and item.strip():
                paths.add(_norm_posix(item))
            elif isinstance(item, dict):
                p = item.get("path") or item.get("file") or item.get("name")
                if isinstance(p, str) and p.strip():
                    paths.add(_norm_posix(p))
        return paths

    if not isinstance(data, dict):
        raise SecondHomeError("Inventaris JSON wajib berupa objek atau array.")

    for key in ("files", "assets", "entries", "paths"):
        val = data.get(key)
        if isinstance(val, list):
            paths.update(_extract_paths_from_json_inventory(val))

    dirs = data.get("directories")
    if isinstance(dirs, dict):
        for dname, items in dirs.items():
            if not isinstance(items, list):
                continue
            for entry in items:
                if isinstance(entry, str):
                    fname = entry
                elif isinstance(entry, dict):
                    fname = str(entry.get("path") or entry.get("name") or "")
                else:
                    continue
                if not fname:
                    continue
                if dname != "." and "/" not in fname:
                    paths.add(_norm_posix(f"{dname}/{fname}"))
                else:
                    paths.add(_norm_posix(fname))

    modules = data.get("modules")
    if isinstance(modules, list):
        for mod in modules:
            if isinstance(mod, dict) and isinstance(mod.get("path"), str):
                paths.add(_norm_posix(mod["path"]))

    return {p for p in paths if p}


def load_requirements(path: Path) -> dict[str, Any]:
    """Muat daftar kebutuhan bernama pendirian instance dari berkas JSON."""
    if not path.is_file():
        raise SecondHomeError(f"Berkas kebutuhan tidak ditemukan: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SecondHomeError(f"Gagal membaca berkas kebutuhan '{path}': {exc}") from exc

    if isinstance(data, list):
        target_name = path.stem
        raw_reqs = data
    elif isinstance(data, dict) and isinstance(data.get("requirements"), list):
        target_name = str(data.get("target_name") or data.get("target") or path.stem).strip()
        raw_reqs = data["requirements"]
    else:
        raise SecondHomeError("Berkas kebutuhan wajib array JSON atau objek dengan daftar 'requirements'.")

    if not raw_reqs:
        raise SecondHomeError("Daftar kebutuhan tidak boleh kosong.")

    parsed: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for idx, item in enumerate(raw_reqs):
        if not isinstance(item, dict):
            raise SecondHomeError(f"Kebutuhan indeks {idx} wajib berupa objek JSON.")
        name = item.get("name")
        if not isinstance(name, str) or not name.strip():
            raise SecondHomeError(f"Kebutuhan indeks {idx} wajib memiliki 'name' string tidak kosong.")
        req_id = str(item.get("id") or _slugify(name)).strip()
        if req_id in seen_ids:
            raise SecondHomeError(f"ID kebutuhan ganda ditemukan: '{req_id}'.")
        seen_ids.add(req_id)

        prerequisites = _as_str_list(
            item.get("prerequisites", item.get("prerequisite")),
            f"{req_id}.prerequisites",
        )
        depends_on = _as_str_list(item.get("depends_on"), f"{req_id}.depends_on")
        steps = _as_str_list(item.get("steps", item.get("step")), f"{req_id}.steps")
        if not steps:
            raise SecondHomeError(f"Kebutuhan '{req_id}' wajib memiliki minimal satu langkah pada 'steps'.")
        verifications = _as_str_list(
            item.get("verification", item.get("verifications", item.get("verify"))),
            f"{req_id}.verification",
        )
        if not verifications:
            raise SecondHomeError(f"Kebutuhan '{req_id}' wajib memiliki minimal satu 'verification'.")
        required_assets = [
            _norm_posix(a)
            for a in _as_str_list(
                item.get("required_assets", item.get("assets", item.get("files"))),
                f"{req_id}.required_assets",
            )
            if _norm_posix(a)
        ]

        parsed.append(
            {
                "id": req_id,
                "name": name.strip(),
                "description": str(item.get("description") or "").strip(),
                "prerequisites": prerequisites,
                "depends_on": depends_on,
                "required_assets": required_assets,
                "steps": steps,
                "verifications": verifications,
            }
        )

    # Validasi referensi depends_on agar menunjuk ID yang ada di berkas kebutuhan.
    for req in parsed:
        for dep in req["depends_on"]:
            if dep not in seen_ids:
                raise SecondHomeError(
                    f"Kebutuhan '{req['id']}' merujuk depends_on '{dep}' yang tidak ada di berkas kebutuhan."
                )

    return {"target_name": target_name or "second-home", "requirements": parsed}


def build_checklist(
    inventory_paths: set[str],
    requirements_doc: dict[str, Any],
    *,
    inventory_source: str = "<memory>",
    requirements_source: str = "<memory>",
) -> dict[str, Any]:
    """Susun objek checklist terstruktur dengan verifikasi aset terhadap inventaris repo."""
    reqs = requirements_doc["requirements"]
    by_id = {r["id"]: r for r in reqs}

    sections: list[dict[str, Any]] = []
    total_steps = 0
    matched_assets = 0
    missing_assets: list[dict[str, str]] = []

    for order, req in enumerate(reqs, start=1):
        asset_checks: list[dict[str, Any]] = []
        for asset in req["required_assets"]:
            present = asset in inventory_paths
            if present:
                matched_assets += 1
            else:
                missing_assets.append({"requirement_id": req["id"], "asset": asset})
            asset_checks.append({"path": asset, "in_inventory": present})

        dep_labels = [f"{dep} ({by_id[dep]['name']})" for dep in req["depends_on"]]
        combined_prereqs = [*dep_labels, *req["prerequisites"]]
        total_steps += len(req["steps"])

        sections.append(
            {
                "order": order,
                "id": req["id"],
                "name": req["name"],
                "description": req["description"],
                "prerequisites": combined_prereqs,
                "depends_on": req["depends_on"],
                "assets": asset_checks,
                "steps": req["steps"],
                "verifications": req["verifications"],
                "all_assets_present": all(a["in_inventory"] for a in asset_checks),
            }
        )

    return {
        "schema": SECOND_HOME_SCHEMA,
        "foundation_only": True,
        "activation_authorized": False,
        "target_name": requirements_doc["target_name"],
        "sources": {
            "inventory": inventory_source,
            "requirements": requirements_source,
            "inventory_file_count": len(inventory_paths),
        },
        "summary": {
            "requirement_count": len(sections),
            "total_steps": total_steps,
            "matched_asset_count": matched_assets,
            "missing_asset_count": len(missing_assets),
            "all_assets_present": len(missing_assets) == 0,
        },
        "missing_assets": missing_assets,
        "sections": sections,
    }


def render_markdown(plan: dict[str, Any]) -> str:
    """Render checklist pendirian rumah kedua sebagai Markdown deterministik."""
    s = plan["summary"]
    lines = [
        f"# Checklist Pendirian Rumah Kedua ACE — {plan['target_name']}",
        "",
        f"> Dihasilkan secara deterministik dari berkas sumber oleh `tools/second_home.py` (`{plan['schema']}`).",
        "> Status fondasi: `foundation_only: true`, `activation_authorized: false` (pendirian nyata dilakukan operator).",
        "",
        "## Sumber & Ringkasan",
        "",
        f"- **Berkas inventaris repo:** `{plan['sources']['inventory']}` ({plan['sources']['inventory_file_count']} berkas tercatat)",
        f"- **Berkas kebutuhan:** `{plan['sources']['requirements']}`",
        f"- **Jumlah kelompok kebutuhan:** {s['requirement_count']}",
        f"- **Total langkah checklist:** {s['total_steps']}",
        f"- **Aset sumber cocok / hilang di inventaris:** {s['matched_asset_count']} / {s['missing_asset_count']}",
        "",
        "## Daftar Ringkas Tahapan",
        "",
        "| # | ID | Kebutuhan | Prasyarat | Langkah | Aset Inventaris |",
        "| ---: | --- | --- | ---: | ---: | --- |",
    ]

    for sec in plan["sections"]:
        asset_status = "LENGKAP" if sec["all_assets_present"] else "ADA YANG HILANG"
        lines.append(
            f"| {sec['order']} | `{sec['id']}` | {sec['name']} | {len(sec['prerequisites'])} | {len(sec['steps'])} | {asset_status} |"
        )

    lines.append("")
    for sec in plan["sections"]:
        lines.append(f"## {sec['order']}. {sec['name']} (`{sec['id']}`)")
        lines.append("")
        if sec["description"]:
            lines.append(sec["description"])
            lines.append("")

        lines.append("### Prasyarat")
        if sec["prerequisites"]:
            for pre in sec["prerequisites"]:
                lines.append(f"- {pre}")
        else:
            lines.append("- (tidak ada prasyarat khusus tercatat pada sumber)")
        lines.append("")

        if sec["assets"]:
            lines.append("### Aset Sumber dari Inventaris")
            for a in sec["assets"]:
                tag = "ADA" if a["in_inventory"] else "HILANG_DI_INVENTARIS"
                lines.append(f"- [{tag}] `{a['path']}`")
            lines.append("")

        lines.append("### Langkah Eksekusi")
        for step in sec["steps"]:
            lines.append(f"- [ ] {step}")
        lines.append("")

        lines.append("### Verifikasi")
        for ver in sec["verifications"]:
            lines.append(f"- [ ] Verifikasi: `{ver}`")
        lines.append("")

    if plan["missing_assets"]:
        lines.append("## Peringatan Aset Tidak Ditemukan di Inventaris")
        lines.append("")
        for miss in plan["missing_assets"]:
            lines.append(f"- Kebutuhan `{miss['requirement_id']}` merujuk `{miss['asset']}` yang tidak ada di berkas inventaris.")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Bangun checklist Markdown pendirian rumah kedua (instance baru) dari inventaris repo + daftar kebutuhan."
    )
    parser.add_argument("--inventory", required=True, help="Berkas inventaris repo (JSON atau Markdown REPO_INDEX.md).")
    parser.add_argument("--requirements", required=True, help="Berkas JSON daftar kebutuhan bernama.")
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    parser.add_argument("--output", help="Tulis checklist Markdown ke berkas ini.")
    parser.add_argument("--json-out", help="Tulis struktur checklist JSON ke berkas ini.")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Keluar dengan kode 1 bila ada aset kebutuhan yang tidak ditemukan di berkas inventaris.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        inv_path = Path(args.inventory)
        req_path = Path(args.requirements)
        inv_paths = load_inventory(inv_path)
        req_doc = load_requirements(req_path)
        plan = build_checklist(
            inv_paths,
            req_doc,
            inventory_source=str(inv_path),
            requirements_source=str(req_path),
        )
    except SecondHomeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    md_text = render_markdown(plan)
    json_text = json.dumps(plan, ensure_ascii=False, indent=2) + "\n"

    if args.output:
        out_p = Path(args.output)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(md_text, encoding="utf-8")
    if args.json_out:
        jp = Path(args.json_out)
        jp.parent.mkdir(parents=True, exist_ok=True)
        jp.write_text(json_text, encoding="utf-8")

    sys.stdout.write(json_text if args.format == "json" else md_text)
    if args.strict and not plan["summary"]["all_assets_present"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
