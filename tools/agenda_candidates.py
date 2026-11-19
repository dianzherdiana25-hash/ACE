#!/usr/bin/env python3
"""Susun dan urutkan usulan agenda dari snapshot dan bukti handover."""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
from typing import Iterable, Mapping

if __package__:
    from .opportunity_register import generate_proposals
else:
    from opportunity_register import generate_proposals


SCHEMA = "ace.agenda-proposal.v1"
BRAIN_OF_ORIGIN = "codex-proposal"
ASSET_KINDS = frozenset({"tool", "corpus", "engine"})
PRIORITY = {"blocked": 1, "failure": 2, "null": 3, "asset_pair": 4}
VERDICTS = {
    "NOL": ("null", "NOL"),
    "NULL": ("null", "NULL"),
    "NO_EFFECT": ("null", "NO_EFFECT"),
    "FAIL": ("failure", "FAIL"),
    "FAILED": ("failure", "FAIL"),
    "GAGAL": ("failure", "GAGAL"),
    "TIDAK LOLOS": ("failure", "TIDAK LOLOS"),
    "NOT_PASSED": ("failure", "NOT_PASSED"),
    "TIDAK TERDUKUNG": ("failure", "TIDAK TERDUKUNG"),
    "NOT_SUPPORTED": ("failure", "NOT_SUPPORTED"),
    "REFUTED_NEGATIVE_ARCHIVED": ("failure", "REFUTED_NEGATIVE_ARCHIVED"),
    "ERROR": ("blocked", "ERROR"),
    "all_green FALSE": ("failure", "ALL_GREEN_FALSE"),
    "INSTRUMEN_TIDAK_CUKUP": ("blocked", "INSTRUMEN_TIDAK_CUKUP"),
    "NOT_ASSESSABLE": ("blocked", "NOT_ASSESSABLE"),
    "DEFERRED_OR_BLOCKED": ("blocked", "DEFERRED_OR_BLOCKED"),
    "ABSTAINED_UNIDENTIFIABLE": ("blocked", "ABSTAINED_UNIDENTIFIABLE"),
}
_VERDICT = re.compile(
    r"^(?P<label>.+?):\s*(?P<verdict>"
    + "|".join(re.escape(value) for value in sorted(VERDICTS, key=len, reverse=True))
    + r")(?=$|[\s.,;()])"
)
_HEADING = re.compile(r"^ {0,3}(#{1,6})\s+(.+?)\s*#*\s*$")
_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
_LABEL_PREFIX = re.compile(r"^PROGRAM (?:VERDICT|VONIS)\s*[—–-]\s*", re.IGNORECASE)
_INLINE_VERDICT = re.compile(r"\s*\((?:VERDICT|VONIS)\s*:\s*", re.IGNORECASE)


def _identifier(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:20]


def _text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip()) and value.isprintable()


def _repo_name(name: str) -> str:
    if not _text(name) or "\\" in name or ":" in name:
        raise ValueError("Sumber wajib berupa path relatif POSIX di repo.")
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError("Sumber wajib berupa path relatif POSIX di repo.")
    return path.as_posix()


def _source_file(root: Path, name: str) -> tuple[str, Path]:
    name = _repo_name(name)
    path = (root / name).resolve(strict=True)
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError("Sumber harus menunjuk berkas di dalam repo.")
    return name, path


def _draft(proposal_id: str, kind: str, title: str, sources: list[dict], **details) -> dict:
    return {
        "schema": SCHEMA,
        "proposal_id": proposal_id,
        "brain_of_origin": BRAIN_OF_ORIGIN,
        "kind": kind,
        "title": title,
        "sources": sources,
        "status": "proposal_only",
        "claim_made": False,
        "requires_human_validation": True,
        **details,
    }


def propose_asset_pairs(assets: dict, known_entries: Iterable[dict], *,
                        assets_source: str, snapshot_source: str) -> list[dict]:
    """Adaptasi proposal kombinasi dari format snapshot register peluang."""
    assets_source = _repo_name(assets_source)
    snapshot_source = _repo_name(snapshot_source)
    if not isinstance(assets, dict):
        raise ValueError("Snapshot aset wajib berupa objek JSON.")
    scoped = {}
    for asset_id, asset in assets.items():
        if (not _text(asset_id) or not isinstance(asset, dict)
                or not _text(asset.get("kind")) or not _text(asset.get("name"))):
            raise ValueError("Aset wajib memiliki ID, kind, dan name yang sah.")
        if asset["kind"] in ASSET_KINDS:
            scoped[asset_id] = {"kind": asset["kind"], "name": asset_id}

    known = list(known_entries)
    for row in known:
        combo = row.get("combination") if isinstance(row, dict) else None
        if (not isinstance(combo, list) or len(combo) < 2
                or not all(_text(asset_id) for asset_id in combo) or len(set(combo)) != len(combo)):
            raise ValueError("Kombinasi pada snapshot register tidak sah.")

    candidates = []
    for proposal in generate_proposals(scoped, known):
        first, second = proposal["combination"]
        candidates.append(_draft(
            f"agenda-{proposal['proposal_id']}", "asset_pair", f"Telaah kombinasi {first} × {second}",
            [{"path": assets_source, "asset_id": asset_id} for asset_id in (first, second)]
            + [{"path": snapshot_source}],
            combination=[first, second],
            asset_kinds=proposal["asset_kinds"],
        ))
    return candidates


def _declarations(markdown: str, path: str):
    """Temukan label dan verdict tertulis pada struktur deklaratif Markdown."""
    fence = None
    document = Path(path).stem
    for line_no, line in enumerate(markdown.splitlines(), 1):
        boundary = _FENCE.fullmatch(line)
        if fence is not None:
            if boundary and boundary[1].startswith(fence) and not boundary[2].strip():
                fence = None
            continue
        if boundary:
            fence = boundary[1]
            continue

        heading = _HEADING.fullmatch(line)
        if heading:
            label_line = heading[2]
        else:
            bullet = re.match(r"^ {0,3}[-*+]\s+(.+)$", line)
            label_line = bullet[1] if bullet else line
            if not (bullet or label_line.startswith("**")
                    or re.match(r"^(?:VERDICT|VONIS)\s*:", label_line, re.IGNORECASE)):
                continue

        plain = label_line.replace("**", "").replace("`", "")
        plain = _INLINE_VERDICT.sub(": ", plain, count=1)
        match = _VERDICT.match(plain)
        if not match:
            continue
        label = _LABEL_PREFIX.sub("", match["label"]).strip()
        if label.casefold() in {"verdict", "vonis"}:
            label = document
        yield label, match["verdict"], line_no


def scan_failure_documents(documents: Mapping[str, str]) -> list[dict]:
    """Buat kandidat F→I dari verdict eksplisit, dengan rujukan baris."""
    declarations = defaultdict(list)
    labels = {}
    for raw_path, markdown in sorted(documents.items()):
        path = _repo_name(raw_path)
        if not path.lower().endswith(".md") or not isinstance(markdown, str):
            raise ValueError("Laporan bukti wajib berupa teks Markdown (.md).")
        for label, verdict, line_no in _declarations(markdown, path):
            _, canonical = VERDICTS[verdict]
            label_key = " ".join(re.findall(r"\w+", label.casefold()))
            key = (path, label_key, canonical)
            declarations[key].append({"path": path, "line": line_no})
            labels.setdefault(key, (label, verdict))

    followups = {
        "blocked": "Periksa prasyarat ukur",
        "failure": "Telusuri sebab kegagalan",
        "null": "Telaah ulang hipotesis tanpa efek terukur",
    }
    proposals = []
    for key, sources in sorted(declarations.items()):
        label, verdict = labels[key]
        kind, canonical = VERDICTS[verdict]
        key_text = json.dumps(key, ensure_ascii=False)
        proposals.append(_draft(
            f"agenda-fi-{_identifier(key_text)}", kind, f"{followups[kind]} — {label}", sources,
            verdict=canonical,
        ))
    return proposals


def prioritize(items: Iterable[dict]) -> list[dict]:
    """Urutkan kategori tindak lanjut, lalu ID sebagai pemutus seri."""
    entries = {}
    for row in items:
        if (not isinstance(row, dict) or row.get("schema") != SCHEMA
                or not _text(row.get("proposal_id")) or not _text(row.get("brain_of_origin"))
                or not _text(row.get("title")) or not _valid_sources(row.get("sources"))
                or not _text(row.get("kind")) or row["kind"] not in PRIORITY
                or row.get("status") != "proposal_only"
                or row.get("claim_made") is not False
                or row.get("requires_human_validation") is not True):
            raise ValueError("Kandidat agenda atau stempel asal tidak sah.")
        proposal_id = row["proposal_id"]
        row = {field: value for field, value in row.items() if field != "priority_rank"}
        if proposal_id in entries and entries[proposal_id] != row:
            raise ValueError("ID kandidat agenda bertabrakan dengan isi berbeda.")
        entries[proposal_id] = row
    ordered = sorted(entries.values(), key=lambda row: (PRIORITY[row["kind"]], row["proposal_id"]))
    return [{**row, "priority_rank": rank} for rank, row in enumerate(ordered, 1)]


def _valid_sources(sources) -> bool:
    if not isinstance(sources, list) or not sources:
        return False
    for source in sources:
        if not isinstance(source, dict):
            return False
        _repo_name(source.get("path"))
        if "line" in source and (type(source["line"]) is not int or source["line"] < 1):
            return False
    return True


def _unique_fields(pairs):
    result = dict(pairs)
    if len(result) != len(pairs):
        raise ValueError("Field JSON ganda.")
    return result


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line, object_pairs_hook=_unique_fields)
            for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd(), help="Akar repo sumber.")
    commands = parser.add_subparsers(dest="command", required=True)
    assets = commands.add_parser("assets", help="Kombinasi dari snapshot aset dan register.")
    assets.add_argument("--assets-file", required=True)
    assets.add_argument("--register-snapshot", required=True)
    failures = commands.add_parser("failures", help="Tindak lanjut dari dokumen verdict.")
    failures.add_argument("documents", nargs="+")
    rank = commands.add_parser("prioritize", help="Urutkan daftar proposal JSONL.")
    rank.add_argument("proposals", nargs="+")
    args = parser.parse_args(argv)
    try:
        root = args.repo.resolve(strict=True)
        if args.command == "assets":
            assets_name, assets_path = _source_file(root, args.assets_file)
            snapshot, snapshot_path = _source_file(root, args.register_snapshot)
            proposals = propose_asset_pairs(
                json.loads(assets_path.read_text(encoding="utf-8"), object_pairs_hook=_unique_fields),
                _read_jsonl(snapshot_path),
                assets_source=assets_name, snapshot_source=snapshot,
            )
        elif args.command == "failures":
            files = dict(_source_file(root, name) for name in args.documents)
            proposals = scan_failure_documents({
                name: path.read_text(encoding="utf-8") for name, path in files.items()
            })
        else:
            proposals = prioritize(
                entry for name in args.proposals for entry in _read_jsonl(_source_file(root, name)[1])
            )
    except (OSError, ValueError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    for proposal in proposals:
        print(json.dumps(proposal, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
