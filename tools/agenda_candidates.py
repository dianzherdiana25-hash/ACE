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
CLOSURE_SCHEMA = "ace.agenda-closure.v1"
BRAIN_OF_ORIGIN = "codex-proposal"
ASSET_KINDS = frozenset({"tool", "corpus", "engine"})
PRIORITY = {"blocked": 1, "failure": 2, "null": 3, "asset_pair": 4}
DECISION_STATUS_MAP = {
    "APPROVED": ("CLOSED_APPROVED", True),
    "COMPLETED": ("CLOSED_COMPLETED", True),
    "REJECTED": ("CLOSED_REJECTED", True),
    "DEFERRED": ("OPEN_DEFERRED", False),
}
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_COMMIT_RE = re.compile(r"^[0-9a-f]{7,40}$")
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


def _candidate_id(row: dict) -> str:
    pid = row.get("proposal_id")
    if _text(pid):
        return pid
    cid = row.get("candidate_id")
    if _text(cid):
        return cid
    raise ValueError("Kandidat wajib memiliki proposal_id atau candidate_id.")


def _verify_pointer(pointer: object, repo_root: Path | None) -> tuple[dict | None, list[str]]:
    if not isinstance(pointer, dict):
        return None, ["pointer keputusan wajib berupa objek JSON."]
    errors: list[str] = []
    raw_path = pointer.get("path")
    try:
        rel_path = _repo_name(raw_path)
    except ValueError as exc:
        return None, [str(exc)]

    line = pointer.get("line")
    if line is not None and (type(line) is not int or line < 1):
        errors.append("pointer.line wajib bilangan bulat >= 1.")

    sha = pointer.get("sha256") or pointer.get("content_sha256")
    if sha is not None and (not isinstance(sha, str) or not _SHA256_RE.fullmatch(sha)):
        errors.append("pointer.sha256 wajib 64 hex huruf kecil.")

    commit = pointer.get("commit")
    if commit is not None and (not isinstance(commit, str) or not _COMMIT_RE.fullmatch(commit)):
        errors.append("pointer.commit wajib hash hex 7-40 karakter.")

    excerpt = pointer.get("excerpt")
    if excerpt is not None and not _text(excerpt):
        errors.append("pointer.excerpt wajib teks non-kosong jika disertakan.")

    if errors:
        return None, errors

    verified = {"path": rel_path}
    if line is not None:
        verified["line"] = line
    if sha is not None:
        verified["sha256"] = sha
    if commit is not None:
        verified["commit"] = commit

    if repo_root is not None:
        root = repo_root.resolve(strict=True)
        try:
            _, file_path = _source_file(root, rel_path)
        except (OSError, ValueError):
            return None, [f"Berkas pointer '{rel_path}' tidak ditemukan di dalam repo."]
        raw_bytes = file_path.read_bytes()
        actual_sha = hashlib.sha256(raw_bytes).hexdigest()
        if sha is not None and actual_sha != sha:
            return None, [f"SHA-256 pointer '{rel_path}' tidak cocok (harapan {sha}, aktual {actual_sha})."]
        verified["observed_sha256"] = actual_sha
        lines = raw_bytes.decode("utf-8", errors="replace").splitlines()
        if line is not None and line > len(lines):
            return None, [f"Baris pointer '{rel_path}:{line}' melampaui jumlah baris ({len(lines)})."]
        if excerpt is not None:
            haystack = lines[line - 1] if line is not None else "\n".join(lines)
            if excerpt.strip() not in haystack:
                return None, [f"Kutipan pointer tidak ditemukan pada '{rel_path}'."]
            verified["excerpt"] = excerpt.strip()
    elif excerpt is not None:
        verified["excerpt"] = excerpt.strip()

    return verified, []


def _normalize_decision_record(row: object) -> dict:
    if not isinstance(row, dict):
        raise ValueError("Entri keputusan wajib berupa objek JSON.")
    cid = _candidate_id(row)
    decision_raw = row.get("decision")
    if not _text(decision_raw):
        raise ValueError(f"Keputusan untuk '{cid}' wajib memiliki field 'decision'.")
    decision_norm = decision_raw.strip().upper()
    if decision_norm not in DECISION_STATUS_MAP:
        raise ValueError(f"Token keputusan '{decision_raw}' untuk '{cid}' tidak dikenali.")
    decided_by = row.get("decided_by")
    if not _text(decided_by):
        raise ValueError(f"Keputusan untuk '{cid}' wajib mencantumkan 'decided_by'.")

    raw_ptr = row.get("decision_pointer")
    if raw_ptr is None and "decision_pointers" in row:
        raw_ptr = row.get("decision_pointers")
    if raw_ptr is None:
        pointers = []
    elif isinstance(raw_ptr, list):
        pointers = list(raw_ptr)
    else:
        pointers = [raw_ptr]
    return {
        "candidate_id": cid,
        "decision": decision_norm,
        "decided_by": decided_by.strip(),
        "raw_pointers": pointers,
    }


def build_closure_report(
    proposals: Iterable[dict],
    decisions: Iterable[dict],
    *,
    repo_root: Path | None = None,
) -> dict:
    """Buktikan status penutupan tiap kandidat agenda memakai ID dan pointer keputusan terverifikasi."""
    candidates: dict[str, dict] = {}
    for row in proposals:
        if not isinstance(row, dict) or row.get("schema") != SCHEMA:
            raise ValueError("Setiap usulan wajib ber-schema ace.agenda-proposal.v1.")
        cid = _candidate_id(row)
        cleaned = {field: value for field, value in row.items() if field != "priority_rank"}
        if cid in candidates and candidates[cid] != cleaned:
            raise ValueError(f"Tabrakan ID kandidat usulan dengan isi berbeda: {cid}.")
        candidates[cid] = cleaned

    grouped_decisions: dict[str, list[dict]] = defaultdict(list)
    for row in decisions:
        rec = _normalize_decision_record(row)
        canonical_key = json.dumps(rec, ensure_ascii=False, sort_keys=True)
        existing_keys = {
            json.dumps(item, ensure_ascii=False, sort_keys=True)
            for item in grouped_decisions[rec["candidate_id"]]
        }
        if canonical_key not in existing_keys:
            grouped_decisions[rec["candidate_id"]].append(rec)

    items = []
    counts_by_status = defaultdict(int)
    for cid in sorted(candidates):
        prop = candidates[cid]
        dec_list = grouped_decisions.get(cid, [])
        verified_pointers = []
        validation_errors = []
        decision_val = None
        decided_by = None

        if not dec_list:
            status = "OPEN_PENDING_DECISION"
            closed = False
        elif len(dec_list) > 1:
            status = "CONFLICTING_DECISION"
            closed = False
            validation_errors.append(
                f"Ditemukan {len(dec_list)} keputusan bertentangan untuk kandidat '{cid}'."
            )
        else:
            rec = dec_list[0]
            decision_val = rec["decision"]
            decided_by = rec["decided_by"]
            if not rec["raw_pointers"]:
                status = "INVALID_DECISION_POINTER"
                closed = False
                validation_errors.append("Keputusan tidak menyertakan decision_pointer.")
            else:
                for ptr in rec["raw_pointers"]:
                    ver_ptr, ptr_errs = _verify_pointer(ptr, repo_root)
                    if ptr_errs:
                        validation_errors.extend(ptr_errs)
                    else:
                        verified_pointers.append(ver_ptr)
                if validation_errors or not verified_pointers:
                    status = "INVALID_DECISION_POINTER"
                    closed = False
                    verified_pointers = []
                else:
                    status, closed = DECISION_STATUS_MAP[decision_val]

        counts_by_status[status] += 1
        proof_payload = json.dumps(
            {
                "candidate_id": cid,
                "status": status,
                "decision": decision_val,
                "decided_by": decided_by,
                "verified_pointers": verified_pointers,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        items.append({
            "candidate_id": cid,
            "kind": prop["kind"],
            "title": prop["title"],
            "sources": prop["sources"],
            "status": status,
            "closed": closed,
            "decision": decision_val,
            "decided_by": decided_by,
            "verified_pointers": verified_pointers,
            "validation_errors": validation_errors,
            "proof_sha256": hashlib.sha256(proof_payload.encode("utf-8")).hexdigest(),
        })

    orphan_decisions = []
    for cid in sorted(grouped_decisions.keys() - candidates.keys()):
        for rec in grouped_decisions[cid]:
            orphan_decisions.append({
                "candidate_id": cid,
                "decision": rec["decision"],
                "decided_by": rec["decided_by"],
                "raw_pointers": rec["raw_pointers"],
            })

    closed_count = sum(1 for item in items if item["closed"])
    return {
        "schema": CLOSURE_SCHEMA,
        "summary": {
            "total_candidates": len(items),
            "closed_count": closed_count,
            "open_or_invalid_count": len(items) - closed_count,
            "orphan_decision_count": len(orphan_decisions),
            "counts_by_status": {key: counts_by_status[key] for key in sorted(counts_by_status)},
        },
        "items": items,
        "orphan_decisions": orphan_decisions,
    }


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


def _read_json_or_jsonl(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    if text.startswith("["):
        data = json.loads(text, object_pairs_hook=_unique_fields)
        if not isinstance(data, list):
            raise ValueError("Snapshot keputusan JSON wajib berupa array objek.")
        return data
    if text.startswith("{"):
        parsed = json.loads(text, object_pairs_hook=_unique_fields)
        if isinstance(parsed, dict) and "decisions" in parsed and isinstance(parsed["decisions"], list):
            return parsed["decisions"]
    return _read_jsonl(path)


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
    closure = commands.add_parser("closure", help="Laporan status penutupan kandidat agenda.")
    closure.add_argument("--proposals", nargs="+", required=True)
    closure.add_argument("--decisions", nargs="+", required=True)
    args = parser.parse_args(argv)
    try:
        root = args.repo.resolve(strict=True)
        if args.command == "closure":
            prop_rows = [entry for name in args.proposals for entry in _read_jsonl(_source_file(root, name)[1])]
            dec_rows = [entry for name in args.decisions for entry in _read_json_or_jsonl(_source_file(root, name)[1])]
            report = build_closure_report(prop_rows, dec_rows, repo_root=root)
            print(json.dumps(report, ensure_ascii=False, sort_keys=True))
            return 0
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
