#!/usr/bin/env python3
"""Buat inventaris successor agar klaim dapat dirunut ke berkas repo.

`--claims` menerima larik JSON dengan id, evidence (path relatif repo)
dan status teruji atau belum. Peta membedakan bukti hilang dan klaim belum
teruji dengan bukti yang tersedia.
"""

import argparse
import hashlib
from html import escape
import json
import os
from pathlib import Path
import re
import subprocess


PATTERN = re.compile(r"(?<![A-Za-z0-9])(?:successor-0006|successor_6|s0006)(?![A-Za-z0-9])", re.I)


def _git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args],
                                   env={**os.environ, "GIT_OPTIONAL_LOCKS": "0", "GIT_NO_LAZY_FETCH": "1"})


def _allowed(path):
    return not any(part in {".git", "secrets", "__pycache__"} or part.startswith(".env")
                   for part in path.parts)


def _record_entries(data, suffix):
    if suffix == ".jsonl":
        return [(number, json.loads(line)) for number, line in enumerate(data.splitlines(), 1)
                if line.strip()]
    payload = json.loads(data)
    if isinstance(payload, dict) and isinstance(payload.get("records"), list):
        payload = payload["records"]
    return enumerate(payload if isinstance(payload, list) else [payload], 1)


def inventory(repo: Path, snapshot: Path) -> dict:
    if not snapshot.is_dir():
        raise ValueError("Snapshot harus berupa direktori.")
    branches = sorted(line for line in _git(repo, "branch", "-a", "--format=%(refname:short)")
                      .decode().splitlines() if PATTERN.search(line))
    files = []
    paths = _git(repo, "ls-files", "-z").decode().split("\0")
    for name in sorted(set(paths)):
        rel = Path(name)
        path = repo / rel
        if (PATTERN.search(name) and _allowed(rel) and path.is_file()
                and path.resolve() == repo.resolve() / rel):
            files.append({"path": name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    records = []
    for path in sorted(snapshot.rglob("*")):
        rel = path.relative_to(snapshot)
        if (not _allowed(rel) or not path.is_file() or path.suffix not in {".json", ".jsonl"}
                or path.resolve() != snapshot.resolve() / rel):
            continue
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        for number, record in _record_entries(data, path.suffix):
            if PATTERN.search(rel.as_posix()) or PATTERN.search(json.dumps(record, ensure_ascii=False)):
                records.append({"path": rel.as_posix(), "entry": number, "sha256": digest})
    return {"schema": "ace.successor-inventory.v1",
            "counts": {"branches": len(branches), "files": len(files), "records": len(records)},
            "branches": branches, "files": files, "records": records}


def map_claims(repo, claims, result):
    """Periksa path klaim dan hubungkan dengan daftar berkas inventaris."""
    if not isinstance(claims, list):
        raise ValueError("Manifest klaim wajib berupa larik JSON.")
    repo = repo.resolve()
    inventoried = {item["path"] for item in result["files"]}
    missing, untested = [], []
    seen = set()
    for index, claim in enumerate(claims, 1):
        if (not isinstance(claim, dict) or not isinstance(claim.get("id"), str)
                or not claim["id"].strip() or claim["id"] in seen
                or claim.get("status") not in ("teruji", "belum")
                or not isinstance(claim.get("evidence"), str) or not claim["evidence"].strip()):
            raise ValueError(f"Klaim {index} tidak sah atau ID ganda.")
        claim_id = claim["id"]
        seen.add(claim_id)
        raw_path = claim["evidence"]
        rel = Path(raw_path)
        if (not rel.parts or rel.is_absolute() or ".." in rel.parts
                or "\\" in raw_path or ":" in raw_path or not raw_path.isprintable()
                or not _allowed(rel)):
            raise ValueError(f"Path bukti klaim {index} di luar ruang inventaris.")
        path = (repo / rel).resolve()
        if not path.is_relative_to(repo) or not _allowed(path.relative_to(repo)):
            raise ValueError(f"Path bukti klaim {index} di luar ruang inventaris.")
        row = {"id": claim_id, "evidence": rel.as_posix(), "status": claim["status"],
               "in_successor_inventory": rel.as_posix() in inventoried}
        if not path.is_file():
            missing.append(row)
        elif claim["status"] == "belum":
            untested.append(row)
    return {"missing_evidence": sorted(missing, key=lambda row: row["id"]),
            "untested_with_evidence": sorted(untested, key=lambda row: row["id"])}


def markdown(result):
    lines = ["# Inventaris successor-0006", ""]
    for key in ("branches", "files", "records"):
        lines.extend([f"## {key} ({result['counts'][key]})", ""])
        for item in result[key]:
            if isinstance(item, str):
                lines.append(f"- {escape(item)}")
            else:
                suffix = f" · entri {item['entry']}" if "entry" in item else ""
                lines.append(f"- {escape(item['path'])}{suffix} · `{item['sha256']}`")
        lines.append("")
    if "claims" in result:
        for key, heading in (("missing_evidence", "Klaim dengan bukti hilang"),
                             ("untested_with_evidence", "Klaim belum teruji dengan berkas bukti")):
            rows = result["claims"][key]
            lines.extend([f"## {heading} ({len(rows)})", ""])
            lines.extend(f"- {escape(row['id'])} · {escape(row['evidence'])}" for row in rows)
            lines.append("")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--snapshot", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--claims", type=Path, help="Manifest klaim JSON.")
    args = parser.parse_args(argv)
    try:
        target = args.output_dir.resolve()
        for source in (args.repo.resolve(), args.snapshot.resolve()):
            if target.is_relative_to(source) or source.is_relative_to(target):
                raise ValueError("Direktori keluaran harus terpisah dari masukan.")
        result = inventory(args.repo, args.snapshot)
        if args.claims:
            claims = json.loads(args.claims.read_text(encoding="utf-8"))
            result["claims"] = map_claims(args.repo, claims, result)
        args.output_dir.mkdir()
        (args.output_dir / "inventory.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        (args.output_dir / "inventory.md").write_text(markdown(result), encoding="utf-8")
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
