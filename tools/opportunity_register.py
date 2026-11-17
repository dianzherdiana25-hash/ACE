#!/usr/bin/env python3
"""Pipeline register peluang lintas-aset (WS-G #19).

Memindai aset/perkakas repositori yang belum dipasangkan (serta opsional
menyelaraskan dengan registri `ace_operational.opportunity_register`) dan
mengeluarkan proposal JSONL ber-atribusi asal (`ACE-origin` vs `human-origin`)
dengan deklarasi non-klaim eksplisit (`claim_made: false`,
`requires_human_validation: true`).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


SCHEMA_VERSION = "ace.opportunity-register.v1"
VALID_ORIGIN_ATTRIBUTIONS = ("ACE-origin", "human-origin")


class OpportunityRegisterToolError(ValueError):
    """Error konfigurasi aset, file register, atau atribut asal."""


def _load_builtin_assets() -> Dict[str, Dict[str, Any]]:
    repo_code_dir = Path(__file__).resolve().parent.parent / "code"
    if repo_code_dir.is_dir() and str(repo_code_dir) not in sys.path:
        sys.path.insert(0, str(repo_code_dir))
    try:
        from ace_operational import opportunity_register as core_reg  # type: ignore

        assets = getattr(core_reg, "ASSETS", None)
        if isinstance(assets, dict):
            return {k: dict(v) for k, v in assets.items()}
    except Exception:
        pass
    return {
        "venue_kbm": {
            "kind": "venue",
            "name": "KBM App",
            "role": "serialized-fiction storefront",
            "status": "account_active_writer_mode",
            "evidence": "registry baseline",
        },
        "venue_threads": {
            "kind": "venue",
            "name": "Threads",
            "role": "promotion / invite channel",
            "status": "active_first_post_live",
            "evidence": "registry baseline",
        },
        "cap_serial_fiction": {
            "kind": "capability",
            "name": "Serial fiction production",
            "role": "story authoring and editorial checks",
            "status": "unvalidated_as_product",
            "evidence": "registry baseline",
        },
    }


def load_assets(assets_file: Optional[Path] = None) -> Dict[str, Dict[str, Any]]:
    if assets_file is None:
        return _load_builtin_assets()
    if not assets_file.is_file():
        raise OpportunityRegisterToolError(f"Berkas aset tidak ditemukan: {assets_file}")
    try:
        raw = json.loads(assets_file.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OpportunityRegisterToolError(f"Gagal membaca JSON aset '{assets_file}': {exc}") from exc
    if not isinstance(raw, dict):
        raise OpportunityRegisterToolError("Berkas aset harus berupa JSON object.")
    cleaned: Dict[str, Dict[str, Any]] = {}
    for asset_id, meta in raw.items():
        if not isinstance(asset_id, str) or not isinstance(meta, dict):
            raise OpportunityRegisterToolError(f"Entri aset tidak sah: {asset_id!r}")
        if not isinstance(meta.get("kind"), str) or not isinstance(meta.get("name"), str):
            raise OpportunityRegisterToolError(f"Aset '{asset_id}' wajib memiliki 'kind' dan 'name'.")
        cleaned[asset_id] = dict(meta)
    return cleaned


def scan_repo_underused_assets(repo_dir: Path) -> Dict[str, Dict[str, Any]]:
    """Pindai perkakas/dokumen/proyek di repositori sebagai kandidat aset tambahan."""
    root = Path(repo_dir)
    if not root.is_dir():
        raise OpportunityRegisterToolError(f"Direktori repo tidak ditemukan: {root}")
    discovered: Dict[str, Dict[str, Any]] = {}
    for folder, kind in (("tools", "tool"), ("projects", "project"), ("docs", "doc")):
        sub = root / folder
        if not sub.is_dir():
            continue
        for item in sorted(sub.iterdir()):
            if item.name.startswith(".") or item.name.startswith("__"):
                continue
            if folder == "tools" and (item.name.startswith("test_") or item.suffix != ".py"):
                continue
            asset_id = f"{kind}_{item.stem.replace('-', '_').lower()}"
            discovered[asset_id] = {
                "kind": kind,
                "name": item.name,
                "role": f"repo {kind} at {folder}/{item.name}",
                "status": "present_in_repo",
                "evidence": f"path:{folder}/{item.name}",
            }
    return discovered


def load_registered_entries(register_path: Optional[Path]) -> List[Dict[str, Any]]:
    if register_path is None or not register_path.exists():
        return []
    entries: List[Dict[str, Any]] = []
    try:
        lines = register_path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        raise OpportunityRegisterToolError(f"Gagal membaca register '{register_path}': {exc}") from exc
    for idx, line in enumerate(lines, start=1):
        s = line.strip()
        if not s:
            continue
        try:
            obj = json.loads(s)
        except json.JSONDecodeError as exc:
            raise OpportunityRegisterToolError(
                f"Baris JSONL tidak sah pada {register_path}:{idx}: {exc}"
            ) from exc
        if not isinstance(obj, dict):
            raise OpportunityRegisterToolError(f"Baris {idx} pada {register_path} bukan objek JSON.")
        entries.append(obj)
    return entries


def _attribution_for_entry(entry: Dict[str, Any]) -> str:
    explicit = entry.get("origin_attribution")
    if explicit in VALID_ORIGIN_ATTRIBUTIONS:
        return str(explicit)
    origin = str(entry.get("origin") or "").strip().upper()
    if origin in ("FOUNDER", "HUMAN", "OWNER"):
        return "human-origin"
    return "ACE-origin"


def _proposal_id(combo: Sequence[str], origin_attribution: str) -> str:
    digest = hashlib.sha256(
        json.dumps({"combination": list(combo), "origin": origin_attribution}, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return f"opp-{digest[:12]}"


def generate_proposals(
    assets: Dict[str, Dict[str, Any]],
    existing_entries: Optional[Iterable[Dict[str, Any]]] = None,
    *,
    origin_attribution: str = "ACE-origin",
    origin_detail: str = "deterministic_pair_scan",
    max_proposals: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Hasilkan proposal kombinasi aset yang belum ada pada register."""
    if origin_attribution not in VALID_ORIGIN_ATTRIBUTIONS:
        raise OpportunityRegisterToolError(
            f"origin_attribution tidak sah ({origin_attribution!r}); pilih {VALID_ORIGIN_ATTRIBUTIONS}"
        )

    registered_combos = set()
    for entry in existing_entries or ():
        combo = entry.get("combination")
        if isinstance(combo, list) and len(combo) >= 2:
            registered_combos.add(tuple(sorted(str(x) for x in combo)))

    venues = sorted(k for k, v in assets.items() if v.get("kind") == "venue")
    anchors = venues if venues else sorted(assets.keys())
    all_keys = sorted(assets.keys())

    seen_combos = set(registered_combos)
    proposals: List[Dict[str, Any]] = []

    for a_key in anchors:
        for b_key in all_keys:
            if a_key == b_key:
                continue
            combo = tuple(sorted((a_key, b_key)))
            if combo in seen_combos:
                continue
            seen_combos.add(combo)
            a_meta = assets[combo[0]]
            b_meta = assets[combo[1]]
            proposals.append(
                {
                    "schema": SCHEMA_VERSION,
                    "proposal_id": _proposal_id(combo, origin_attribution),
                    "combination": list(combo),
                    "asset_kinds": [a_meta.get("kind"), b_meta.get("kind")],
                    "rationale": (
                        f"{a_meta.get('name')} ({a_meta.get('kind')}; {a_meta.get('status', '-')}) "
                        f"x {b_meta.get('name')} ({b_meta.get('kind')}; {b_meta.get('status', '-')}) "
                        "— belum tercatat pada register peluang."
                    ),
                    "origin_attribution": origin_attribution,
                    "origin_detail": origin_detail,
                    "claim_made": False,
                    "requires_human_validation": True,
                    "status": "proposal_only",
                }
            )
            if max_proposals is not None and len(proposals) >= max_proposals:
                return proposals
    return proposals


def summarize_register(
    proposals: Sequence[Dict[str, Any]],
    existing_entries: Sequence[Dict[str, Any]] = (),
) -> Dict[str, Any]:
    existing_by_origin = {"ACE-origin": 0, "human-origin": 0}
    for entry in existing_entries:
        attr = _attribution_for_entry(entry)
        existing_by_origin[attr] = existing_by_origin.get(attr, 0) + 1

    proposal_by_origin = {"ACE-origin": 0, "human-origin": 0}
    for prop in proposals:
        attr = prop.get("origin_attribution")
        if attr in proposal_by_origin:
            proposal_by_origin[attr] += 1

    total_existing = len(existing_entries)
    return {
        "schema": SCHEMA_VERSION,
        "claim_made": False,
        "requires_human_validation": True,
        "existing_count": total_existing,
        "existing_by_origin": existing_by_origin,
        "existing_ace_origin_share": (
            existing_by_origin["ACE-origin"] / total_existing if total_existing else 0.0
        ),
        "proposal_count": len(proposals),
        "proposal_by_origin": proposal_by_origin,
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Hasilkan proposal register peluang lintas-aset (JSONL) dengan atribusi asal eksplisit."
    )
    parser.add_argument("--assets-file", default=None, help="JSON registri aset kustom (opsional)")
    parser.add_argument(
        "--scan-repo",
        default=None,
        help="Opsional: pindai tools/projects/docs pada direktori repo untuk memperkaya aset",
    )
    parser.add_argument("--register-file", default=None, help="JSONL register peluang yang sudah ada")
    parser.add_argument(
        "--origin-attribution",
        choices=VALID_ORIGIN_ATTRIBUTIONS,
        default="ACE-origin",
        help="Atribusi asal untuk proposal baru (default: ACE-origin)",
    )
    parser.add_argument(
        "--origin-detail",
        default="deterministic_pair_scan",
        help="Detail pemicu/otak asal proposal",
    )
    parser.add_argument("--max-proposals", type=int, default=None, help="Batas maksimum proposal JSONL")
    parser.add_argument("--out-jsonl", default=None, help="Tulis proposal ke berkas JSONL ini")
    parser.add_argument("--summary-out", default=None, help="Tulis ringkasan JSON ke berkas ini")

    args = parser.parse_args(argv)
    try:
        assets = load_assets(Path(args.assets_file) if args.assets_file else None)
        if args.scan_repo:
            assets.update(scan_repo_underused_assets(Path(args.scan_repo)))
        existing = load_registered_entries(Path(args.register_file) if args.register_file else None)
        if args.max_proposals is not None and args.max_proposals < 0:
            raise OpportunityRegisterToolError("--max-proposals harus >= 0")
        proposals = generate_proposals(
            assets,
            existing,
            origin_attribution=args.origin_attribution,
            origin_detail=args.origin_detail,
            max_proposals=args.max_proposals,
        )
        summary = summarize_register(proposals, existing)
    except OpportunityRegisterToolError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    jsonl_text = "\n".join(json.dumps(p, ensure_ascii=False) for p in proposals)
    if jsonl_text:
        jsonl_text += "\n"

    if args.out_jsonl:
        Path(args.out_jsonl).write_text(jsonl_text, encoding="utf-8")
    if args.summary_out:
        Path(args.summary_out).write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    if jsonl_text:
        sys.stdout.write(jsonl_text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
