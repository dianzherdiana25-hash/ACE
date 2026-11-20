#!/usr/bin/env python3
"""Buat inventaris successor agar klaim dapat dirunut ke berkas repo.

`--claims` menerima larik JSON dengan id, evidence (path relatif repo)
dan status teruji atau belum. Peta membedakan bukti hilang dan klaim belum
teruji dengan bukti yang tersedia. Klaim yang berpindah dapat memuat
relocated_to (path relatif repo) dan sha256 bukti asli (64 digit hex).
Lokasi antara dapat berupa objek JSON dengan schema ace.successor-relocation.v1
dan relocated_to relatif root. Maksimal tiga lompatan termasuk penunjuk
pertama. Bila ada, blob terakhir dari riwayat HEAD di path asli ikut diperiksa.
"""

import argparse
import hashlib
from html import escape
import json
import os
from pathlib import Path
import re
import subprocess


RELOCATION_SCHEMA = "ace.successor-relocation.v1"
MAX_RELOCATION_HOPS = 3


PATTERN = re.compile(r"(?<![A-Za-z0-9])(?:successor-0006|successor_6|s0006)(?![A-Za-z0-9])", re.I)


def _git(root, *args, quiet=False):
    return subprocess.check_output(["git", "-C", str(root), *args],
                                   stderr=subprocess.DEVNULL if quiet else None,
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


def _classify_symlink(root_resolved: Path, link_path: Path) -> str:
    visited: set[Path] = set()
    cur = link_path
    link_parent = link_path.parent.resolve()
    for _ in range(32):
        norm_cur = Path(os.path.abspath(cur))
        if norm_cur in visited:
            return "symlink_cycle"
        visited.add(norm_cur)
        raw_target = os.readlink(cur)
        candidate = Path(raw_target) if os.path.isabs(raw_target) else cur.parent / raw_target
        norm_target = Path(os.path.abspath(candidate))
        if not norm_target.is_relative_to(root_resolved):
            return "symlink_outside_root"
        if norm_target == link_parent or link_parent.is_relative_to(norm_target):
            return "symlink_cycle"
        if not norm_target.is_symlink():
            return "symlink_internal"
        cur = norm_target
    return "symlink_cycle"


def _scan_symlinks(root: Path, tree_name: str) -> list[dict]:
    root_resolved = root.resolve()
    findings: list[dict] = []
    for cur_dir, dirnames, filenames in os.walk(root_resolved, followlinks=False):
        cur = Path(cur_dir)
        kept_dirs = []
        for name in sorted(dirnames):
            candidate = cur / name
            rel = candidate.relative_to(root_resolved)
            if not _allowed(rel):
                continue
            if candidate.is_symlink():
                findings.append({
                    "tree": tree_name,
                    "path": rel.as_posix(),
                    "kind": _classify_symlink(root_resolved, candidate),
                    "target": os.readlink(candidate),
                })
            else:
                kept_dirs.append(name)
        dirnames[:] = kept_dirs
        for name in sorted(filenames):
            candidate = cur / name
            rel = candidate.relative_to(root_resolved)
            if not _allowed(rel):
                continue
            if candidate.is_symlink():
                findings.append({
                    "tree": tree_name,
                    "path": rel.as_posix(),
                    "kind": _classify_symlink(root_resolved, candidate),
                    "target": os.readlink(candidate),
                })
    findings.sort(key=lambda item: (item["tree"], item["path"]))
    return findings


def inventory(repo: Path, snapshot: Path) -> dict:
    if not snapshot.is_dir():
        raise ValueError("Snapshot harus berupa direktori.")
    branches = sorted(line for line in _git(repo, "branch", "-a", "--format=%(refname:short)")
                      .decode().splitlines() if PATTERN.search(line))
    files = []
    paths = _git(repo, "ls-files", "-z").decode().split("\0")
    for name in sorted(set(paths)):
        if not name:
            continue
        rel = Path(name)
        path = repo / rel
        if path.is_symlink():
            continue
        if (PATTERN.search(name) and _allowed(rel) and path.is_file()
                and path.resolve() == repo.resolve() / rel):
            files.append({"path": name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    records = []
    snapshot_resolved = snapshot.resolve()
    for cur_dir, dirnames, filenames in os.walk(snapshot_resolved, followlinks=False):
        cur = Path(cur_dir)
        kept_dirs = []
        for name in sorted(dirnames):
            candidate = cur / name
            rel = candidate.relative_to(snapshot_resolved)
            if _allowed(rel) and not candidate.is_symlink():
                kept_dirs.append(name)
        dirnames[:] = kept_dirs
        for name in sorted(filenames):
            path = cur / name
            if path.is_symlink():
                continue
            rel = path.relative_to(snapshot_resolved)
            if (not _allowed(rel) or not path.is_file() or path.suffix not in {".json", ".jsonl"}
                    or path.resolve() != snapshot_resolved / rel):
                continue
            data = path.read_bytes()
            digest = hashlib.sha256(data).hexdigest()
            for number, record in _record_entries(data, path.suffix):
                if PATTERN.search(rel.as_posix()) or PATTERN.search(json.dumps(record, ensure_ascii=False)):
                    records.append({"path": rel.as_posix(), "entry": number, "sha256": digest})
    symlink_findings = _scan_symlinks(repo, "repo") + _scan_symlinks(snapshot, "snapshot")
    symlink_findings.sort(key=lambda item: (item["tree"], item["path"]))
    report = {"schema": "ace.successor-inventory.v1",
              "counts": {"branches": len(branches), "files": len(files), "records": len(records)},
              "branches": branches, "files": files, "records": records}
    if symlink_findings:
        report["symlink_findings"] = symlink_findings
    return report


def _claim_path(repo, raw_path, index):
    if not isinstance(raw_path, str):
        raise ValueError(f"Path bukti klaim {index} tidak sah.")
    rel = Path(raw_path)
    if (not rel.parts or rel.is_absolute() or ".." in rel.parts
            or "\\" in raw_path or ":" in raw_path or not raw_path.isprintable()
            or not _allowed(rel)):
        raise ValueError(f"Path bukti klaim {index} di luar ruang inventaris.")
    path = (repo / rel).resolve()
    if not path.is_relative_to(repo) or not _allowed(path.relative_to(repo)):
        raise ValueError(f"Path bukti klaim {index} di luar ruang inventaris.")
    return rel, path


def _relocation_pointer(data):
    if not data.lstrip().startswith(b"{"):
        return None
    try:
        value = json.loads(data)
    except (ValueError, UnicodeError):
        return None
    if isinstance(value, dict) and value.get("schema") == RELOCATION_SCHEMA:
        return value
    return None


def _follow_relocation(repo, origin, target, index):
    rel, path = origin
    chain = [rel.as_posix()]
    visited = {path}
    for hop in range(1, MAX_RELOCATION_HOPS + 1):
        rel, path = target
        chain.append(rel.as_posix())
        if path in visited:
            return chain, None, "relocation_cycle"
        visited.add(path)
        if not path.is_file():
            return chain, None, "file_missing"
        data = path.read_bytes()
        pointer = _relocation_pointer(data)
        if pointer is None:
            return chain, hashlib.sha256(data).hexdigest(), None
        target = _claim_path(repo, pointer.get("relocated_to"), index)
        if hop == MAX_RELOCATION_HOPS:
            chain.append(target[0].as_posix())
            return chain, None, "relocation_hop_limit"


def _git_origin(repo, rel, expected):
    try:
        revision = _git(repo, "--literal-pathspecs", "log", "-1", "--diff-filter=AMCRT",
                        "--format=%H", "HEAD", "--", rel.as_posix(), quiet=True).decode().strip()
        if revision:
            data = _git(repo, "cat-file", "blob", f"{revision}:{rel.as_posix()}", quiet=True)
            digest = hashlib.sha256(data).hexdigest()
            return {"state": "match" if digest == expected else "mismatch",
                    "commit": revision, "sha256": digest}
    except subprocess.CalledProcessError:
        pass
    return {"state": "unavailable"}


def map_claims(repo, claims, result):
    """Periksa path klaim dan hubungkan dengan daftar berkas inventaris."""
    if not isinstance(claims, list):
        raise ValueError("Manifest klaim wajib berupa larik JSON.")
    repo = repo.resolve()
    inventoried = {item["path"] for item in result["files"]}
    missing, untested = [], []
    verified, unverified = [], []
    seen = set()
    for index, claim in enumerate(claims, 1):
        if (not isinstance(claim, dict) or not isinstance(claim.get("id"), str)
                or not claim["id"].strip() or claim["id"] in seen
                or claim.get("status") not in ("teruji", "belum")
                or not isinstance(claim.get("evidence"), str) or not claim["evidence"].strip()):
            raise ValueError(f"Klaim {index} tidak sah atau ID ganda.")
        claim_id = claim["id"]
        seen.add(claim_id)
        rel, path = _claim_path(repo, claim["evidence"], index)
        relocated = _claim_path(repo, claim["relocated_to"], index) if "relocated_to" in claim else None
        row = {"id": claim_id, "evidence": rel.as_posix(), "status": claim["status"],
               "in_successor_inventory": rel.as_posix() in inventoried}
        if relocated is not None:
            digest = claim.get("sha256")
            if not isinstance(digest, str) or not re.fullmatch(r"[a-fA-F0-9]{64}", digest):
                raise ValueError(f"SHA-256 bukti asli klaim {index} tidak sah.")
            digest = digest.lower()
            chain, final_digest, reason = _follow_relocation(repo, (rel, path), relocated, index)
            origin = _git_origin(repo, rel, digest)
            relocation = {**row, "relocated_to": chain[-1], "sha256": digest,
                          "relocation_chain": chain, "git_origin": origin}
            if reason is None and final_digest != digest:
                reason = "sha256_mismatch"
            if reason is None and origin["state"] == "mismatch":
                reason = "origin_blob_mismatch"
            if reason is not None:
                unverified.append({**relocation, "reason": reason})
                missing.append(row)
            else:
                verified.append(relocation)
                if claim["status"] == "belum":
                    untested.append({**row, "evidence": chain[-1],
                                     "in_successor_inventory": chain[-1] in inventoried})
            continue
        if not path.is_file():
            missing.append(row)
        elif claim["status"] == "belum":
            untested.append(row)
    mapped = {"missing_evidence": sorted(missing, key=lambda row: row["id"]),
              "untested_with_evidence": sorted(untested, key=lambda row: row["id"])}
    if verified or unverified:
        mapped["relocated_verified"] = sorted(verified, key=lambda row: row["id"])
        mapped["relocation_unverified"] = sorted(unverified, key=lambda row: row["id"])
    return mapped


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
        for key, heading in (("relocated_verified", "Bukti terverifikasi di lokasi baru"),
                             ("relocation_unverified", "Bukti relokasi belum terverifikasi")):
            if key not in result["claims"]:
                continue
            rows = result["claims"][key]
            lines.extend([f"## {heading} ({len(rows)})", ""])
            for row in rows:
                suffix = f" · {row['reason']}" if "reason" in row else ""
                chain = " → ".join(escape(path) for path in row["relocation_chain"])
                lines.append(f"- {escape(row['id'])} · {chain} · `{row['sha256']}`{suffix}"
                             f" · blob Git {row['git_origin']['state']}")
            lines.append("")
    if "symlink_findings" in result:
        rows = result["symlink_findings"]
        lines.extend([f"## Temuan symlink ({len(rows)})", ""])
        for row in rows:
            lines.append(
                f"- {escape(row['tree'])}/{escape(row['path'])} · {escape(row['kind'])} → {escape(row['target'])}"
            )
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
