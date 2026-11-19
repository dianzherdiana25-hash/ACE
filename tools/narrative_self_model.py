#!/usr/bin/env python3
"""C1 — Model-Diri Naratif (Lapis 3) ACE berbasis bukti baca-saja.

Membaca ledger, snapshot memori (baca-saja, tanpa menulis ke store atau membuat
berkas/direktori), dan papan gerbang/status yang ada di repo untuk menyusun
narasi deterministik atas tiga kategori:

- ``identity`` : identitas konstitusional & keadaan terjangkar ACE
- ``proven``   : kemampuan/gerbang/fakta dengan sumber bukti terverifikasi
- ``unproven`` : hasil nol, belum dinilai, atau tebakan ``model`` tanpa bukti

Invarian keras:
1. Read-only total terhadap memory store (termasuk jika path belum ada).
2. Setiap klaim yang keluar WAJIB menunjuk >= 1 berkas sumber yang ada di disk
   dan cocok SHA-256-nya; klaim tanpa sumber atau bersumber rusak disaring
   keluar dan dicatat ke ``rejected_sourceless_claims`` (tak pernah terbit).
3. Multi-brain sovereignty: konfigurasi label organ hanya berada di metadata
   ``organ_context`` terpisah dan tidak mencemari fakta identitas/bukti ACE.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys
from typing import Any


SCHEMA = "ace.narrative-self-model.v1"


class SourcelessClaimError(ValueError):
    """Dilempar saat validasi ketat menemukan klaim tanpa pointer sumber sah."""


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest_obj(value: Any) -> str:
    if isinstance(value, (bytes, bytearray)):
        return hashlib.sha256(bytes(value)).hexdigest()
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _rel_or_posix(path: Path, root: Path) -> str:
    resolved = path.resolve()
    root_res = root.resolve()
    try:
        rel = resolved.relative_to(root_res)
        return PurePosixPath(rel).as_posix()
    except ValueError:
        return resolved.as_posix()


def _resolve_source_path(source_path: str, roots: list[Path]) -> Path | None:
    if not isinstance(source_path, str) or not source_path.strip():
        return None
    cand = Path(source_path)
    if cand.is_absolute():
        res = cand.resolve()
        if any(res == r.resolve() or res.is_relative_to(r.resolve()) for r in roots):
            return res if res.is_file() else None
        return None
    for base in roots:
        res = (base / cand).resolve()
        if res.is_relative_to(base.resolve()) and res.is_file():
            return res
    return None


@dataclass(frozen=True)
class SourcePointer:
    path: str
    sha256: str
    line: int | None = None
    record_id: str | None = None
    seq: int | None = None
    excerpt: str = ""

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "path": self.path,
            "sha256": self.sha256,
        }
        if self.line is not None:
            out["line"] = self.line
        if self.record_id is not None:
            out["record_id"] = self.record_id
        if self.seq is not None:
            out["seq"] = self.seq
        if self.excerpt:
            out["excerpt"] = self.excerpt
        return out


@dataclass(frozen=True)
class NarrativeClaim:
    claim_id: str
    section: str  # "identity" | "proven" | "unproven"
    fact_key: str
    fact_value: Any
    statement: str
    sources: tuple[SourcePointer, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "section": self.section,
            "fact_key": self.fact_key,
            "fact_value": self.fact_value,
            "statement": self.statement,
            "sources": [s.to_dict() for s in self.sources],
        }


def _claim_id(section: str, fact_key: str, fact_value: Any) -> str:
    payload = _canonical_json({"section": section, "fact_key": fact_key, "fact_value": fact_value})
    return f"clm_{hashlib.sha256(payload.encode('utf-8')).hexdigest()[:12]}"


def _find_line(lines: list[str], pattern: str | re.Pattern[str]) -> tuple[int, str] | None:
    if isinstance(pattern, str):
        for idx, line in enumerate(lines, start=1):
            if pattern in line:
                return idx, line.strip()
        return None
    for idx, line in enumerate(lines, start=1):
        if pattern.search(line):
            return idx, line.strip()
    return None


# ---------------------------------------------------------------------------
# Pure read-only Memory Snapshot loader (NO CognitiveMemory write side-effects)
# ---------------------------------------------------------------------------

def read_memory_snapshot_readonly(
    memory_path: Path | None,
    root: Path,
) -> dict[str, Any]:
    """Baca snapshot memori secara strictly read-only.

    Mendukung:
    1) Direktori ``cognitive_memory`` berisi ``memory.jsonl`` (hash-chained event log)
       atau berkas ``.jsonl`` langsung (event log maupun record datar).
    2) Berkas JSON ``ace.seed_snapshot.v1`` (``data/ace_seed_snapshot.json``).
    3) Path tidak ada: mengembalikan ``present=False`` tanpa membuat berkas/direktori.
    """
    if memory_path is None:
        return {
            "present": False,
            "format": "none",
            "path": None,
            "sha256": None,
            "chain_ok": None,
            "events_count": 0,
            "active_records": [],
            "superseded_records": [],
            "tombstones": [],
            "anchored_evidence_count": 0,
            "malformed_lines": 0,
        }

    target = Path(memory_path)
    if target.is_dir():
        jsonl_file = target / "memory.jsonl"
        if jsonl_file.is_file():
            target = jsonl_file
        else:
            return {
                "present": False,
                "format": "missing_memory_jsonl",
                "path": _rel_or_posix(target, root),
                "sha256": None,
                "chain_ok": None,
                "events_count": 0,
                "active_records": [],
                "superseded_records": [],
                "tombstones": [],
                "anchored_evidence_count": 0,
                "malformed_lines": 0,
            }

    if not target.is_file():
        return {
            "present": False,
            "format": "missing_file",
            "path": _rel_or_posix(target, root),
            "sha256": None,
            "chain_ok": None,
            "events_count": 0,
            "active_records": [],
            "superseded_records": [],
            "tombstones": [],
            "anchored_evidence_count": 0,
            "malformed_lines": 0,
        }

    file_sha = _sha256_file(target)
    rel_path = _rel_or_posix(target, root)
    raw_text = target.read_text(encoding="utf-8", errors="replace")

    if target.suffix.lower() == ".json":
        try:
            payload = json.loads(raw_text)
        except json.JSONDecodeError:
            return {
                "present": True,
                "format": "malformed_json",
                "path": rel_path,
                "sha256": file_sha,
                "chain_ok": False,
                "events_count": 0,
                "active_records": [],
                "superseded_records": [],
                "tombstones": [],
                "anchored_evidence_count": 0,
                "malformed_lines": 1,
            }
        if isinstance(payload, dict) and payload.get("schema") == "ace.seed_snapshot.v1":
            records: list[dict[str, Any]] = []
            for idx, item in enumerate(payload.get("memories") or [], start=1):
                if not isinstance(item, dict):
                    continue
                records.append(
                    {
                        "id": f"seed_{idx:03d}",
                        "kind": str(item.get("kind") or "semantic"),
                        "content": {"text": str(item.get("text") or "")},
                        "source": {"kind": "operator", "ref": rel_path},
                        "confidence": float(item.get("confidence") or 0.9),
                        "status": "active",
                        "written_seq": idx,
                    }
                )
            return {
                "present": True,
                "format": "ace.seed_snapshot.v1",
                "path": rel_path,
                "sha256": file_sha,
                "chain_ok": None,
                "events_count": len(records),
                "vocab_count": int(payload.get("vocab_count") or 0),
                "dialog_corpus_count": int(payload.get("dialog_corpus_count") or 0),
                "active_records": records,
                "superseded_records": [],
                "tombstones": [],
                "anchored_evidence_count": 0,
                "malformed_lines": 0,
            }

        raw_recs = payload if isinstance(payload, list) else payload.get("records") or payload.get("memories") or []
        norm_recs = []
        for idx, item in enumerate(raw_recs, start=1):
            if isinstance(item, dict):
                norm_recs.append(
                    {
                        "id": str(item.get("id") or f"rec_{idx:03d}"),
                        "kind": str(item.get("kind") or "episodic"),
                        "content": item.get("content") if isinstance(item.get("content"), dict) else {"summary": str(item)},
                        "source": item.get("source") if isinstance(item.get("source"), dict) else {"kind": str(item.get("source_kind") or "operator"), "ref": item.get("source_ref")},
                        "confidence": float(item.get("confidence") or 0.5),
                        "status": str(item.get("status") or "active"),
                        "written_seq": int(item.get("written_seq") or idx),
                    }
                )
        return {
            "present": True,
            "format": "json_records",
            "path": rel_path,
            "sha256": file_sha,
            "chain_ok": None,
            "events_count": len(norm_recs),
            "active_records": [r for r in norm_recs if r["status"] == "active"],
            "superseded_records": [r for r in norm_recs if r["status"] == "superseded"],
            "tombstones": [],
            "anchored_evidence_count": 0,
            "malformed_lines": 0,
        }

    # JSONL path: support hash-chained CognitiveMemory event log or flat JSONL records
    prev = "GENESIS"
    chain_ok = True
    seq_count = 0
    anchors: set[str] = set()
    records_by_id: dict[str, dict[str, Any]] = {}
    tombstones: list[dict[str, Any]] = []
    flat_records: list[dict[str, Any]] = []
    malformed = 0
    saw_event_envelope = False
    saw_flat_record = False

    for line_no, raw in enumerate(raw_text.splitlines(), start=1):
        stripped = raw.strip()
        if not stripped:
            continue
        try:
            entry = json.loads(stripped)
        except json.JSONDecodeError:
            malformed += 1
            chain_ok = False
            continue
        if not isinstance(entry, dict):
            malformed += 1
            chain_ok = False
            continue

        if "event" in entry and isinstance(entry.get("event"), dict):
            saw_event_envelope = True
            seq_count += 1
            expected_hash = _digest_obj({"prev": prev, "event": entry.get("event")})
            if entry.get("prev") != prev or entry.get("hash") != expected_hash:
                chain_ok = False
            prev = str(entry.get("hash") or prev)
            ev = entry["event"]
            etype = ev.get("type")
            if etype == "anchor":
                digest = ev.get("digest")
                if isinstance(digest, str):
                    anchors.add(digest)
            elif etype == "record":
                rec = ev.get("record")
                if isinstance(rec, dict) and rec.get("id"):
                    rec_copy = dict(rec)
                    rec_copy.setdefault("_line", line_no)
                    records_by_id[str(rec["id"])] = rec_copy
            elif etype == "supersede":
                rid = ev.get("record_id")
                if rid in records_by_id:
                    records_by_id[rid]["status"] = "superseded"
                    records_by_id[rid]["superseded_by"] = ev.get("by")
            elif etype == "outcome":
                rid = ev.get("record_id")
                if rid in records_by_id:
                    outcomes = dict(records_by_id[rid].get("outcomes") or {})
                    ctx = str(ev.get("context") or "default")
                    bucket = dict(outcomes.get(ctx) or {"success": 0, "fail": 0})
                    key = "success" if ev.get("success") else "fail"
                    bucket[key] = int(bucket.get(key, 0)) + 1
                    outcomes[ctx] = bucket
                    records_by_id[rid]["outcomes"] = outcomes
            elif etype == "tombstone":
                rid = ev.get("record_id")
                removed = records_by_id.pop(rid, None)
                tombstones.append(
                    {
                        "record_id": rid,
                        "reason": ev.get("reason"),
                        "content_hash": ev.get("content_hash"),
                        "kind": removed.get("kind") if removed else None,
                        "_line": line_no,
                    }
                )
        else:
            saw_flat_record = True
            seq_count += 1
            rec_id = str(entry.get("id") or f"line_{line_no}")
            src = entry.get("source")
            if not isinstance(src, dict):
                src = {
                    "kind": str(entry.get("source_kind") or "operator"),
                    "ref": entry.get("source_ref"),
                }
            content = entry.get("content")
            if not isinstance(content, dict):
                content = {
                    k: v
                    for k, v in entry.items()
                    if k not in ("id", "kind", "source", "source_kind", "source_ref", "confidence", "status")
                }
            flat_records.append(
                {
                    "id": rec_id,
                    "kind": str(entry.get("kind") or "episodic"),
                    "content": content,
                    "source": src,
                    "confidence": float(entry.get("confidence") or 0.5),
                    "status": str(entry.get("status") or "active"),
                    "written_seq": int(entry.get("written_seq") or line_no),
                    "_line": line_no,
                }
            )

    if saw_event_envelope and not saw_flat_record:
        all_recs = sorted(records_by_id.values(), key=lambda r: (int(r.get("written_seq") or 0), str(r.get("id") or "")))
        return {
            "present": True,
            "format": "cognitive_memory.jsonl",
            "path": rel_path,
            "sha256": file_sha,
            "chain_ok": chain_ok,
            "events_count": seq_count,
            "active_records": [r for r in all_recs if r.get("status", "active") == "active"],
            "superseded_records": [r for r in all_recs if r.get("status") == "superseded"],
            "tombstones": tombstones,
            "anchored_evidence_count": len(anchors),
            "malformed_lines": malformed,
        }

    return {
        "present": True,
        "format": "snapshot.jsonl",
        "path": rel_path,
        "sha256": file_sha,
        "chain_ok": None if malformed == 0 else False,
        "events_count": seq_count,
        "active_records": [r for r in flat_records if r.get("status", "active") == "active"],
        "superseded_records": [r for r in flat_records if r.get("status") == "superseded"],
        "tombstones": tombstones,
        "anchored_evidence_count": 0,
        "malformed_lines": malformed,
    }


# ---------------------------------------------------------------------------
# Provenance Verification Gate
# ---------------------------------------------------------------------------

def verify_claim_sources(
    claims: list[NarrativeClaim],
    allowed_roots: list[Path],
) -> tuple[list[NarrativeClaim], list[dict[str, Any]]]:
    """Filter fail-closed: klaim tanpa >= 1 sumber valid ditolak & dicatat."""
    accepted: list[NarrativeClaim] = []
    rejected: list[dict[str, Any]] = []
    for claim in claims:
        if not claim.sources:
            rejected.append({"claim_id": claim.claim_id, "fact_key": claim.fact_key, "reason": "NO_SOURCES"})
            continue
        all_valid = True
        bad_reason = ""
        for src in claim.sources:
            resolved = _resolve_source_path(src.path, allowed_roots)
            if resolved is None:
                all_valid = False
                bad_reason = f"MISSING_SOURCE_FILE:{src.path}"
                break
            actual_sha = _sha256_file(resolved)
            if actual_sha != src.sha256:
                all_valid = False
                bad_reason = f"SHA_MISMATCH:{src.path}"
                break
            if src.line is not None:
                text_lines = resolved.read_text(encoding="utf-8", errors="replace").splitlines()
                if src.line < 1 or src.line > len(text_lines):
                    all_valid = False
                    bad_reason = f"LINE_OUT_OF_RANGE:{src.path}#L{src.line}"
                    break
        if all_valid:
            accepted.append(claim)
        else:
            rejected.append({"claim_id": claim.claim_id, "fact_key": claim.fact_key, "reason": bad_reason})
    return accepted, rejected


def assert_no_sourceless_claims(model: dict[str, Any], allowed_roots: list[Path]) -> None:
    """Validasi ketat bahwa seluruh klaim pada model terbit memiliki sumber sah."""
    sections = model.get("sections") or {}
    roots = [Path(r).resolve() for r in allowed_roots]
    for section_name in ("identity", "proven", "unproven"):
        items = sections.get(section_name)
        if not isinstance(items, list):
            raise SourcelessClaimError(f"Bagian '{section_name}' hilang atau bukan list")
        for item in items:
            raw_sources = item.get("sources") if isinstance(item, dict) else None
            if not raw_sources:
                raise SourcelessClaimError(f"Klaim tanpa sumber pada '{section_name}': {item!r}")
            for raw in raw_sources:
                resolved = _resolve_source_path(str(raw.get("path") or ""), roots)
                if resolved is None:
                    raise SourcelessClaimError(f"Berkas sumber tidak ditemukan: {raw!r}")
                if _sha256_file(resolved) != raw.get("sha256"):
                    raise SourcelessClaimError(f"Digest sumber tidak cocok: {raw!r}")


# ---------------------------------------------------------------------------
# Repo & Snapshot Extractors
# ---------------------------------------------------------------------------

def _extract_identity_claims(root: Path, mem_snap: dict[str, Any]) -> list[NarrativeClaim]:
    claims: list[NarrativeClaim] = []

    peta = root / "handover" / "PETA_ARAH_SERIBU_TAHUN.md"
    if peta.is_file():
        sha = _sha256_file(peta)
        rel = _rel_or_posix(peta, root)
        lines = peta.read_text(encoding="utf-8").splitlines()
        hit_cont = _find_line(lines, "Kontinuitas adalah intinya")
        if hit_cont:
            claims.append(
                NarrativeClaim(
                    claim_id=_claim_id("identity", "continuity_principle", "cross_brain_continuity"),
                    section="identity",
                    fact_key="continuity_principle",
                    fact_value="cross_brain_continuity",
                    statement="Identitas ACE terjaga lintas otak, lintas rumah, dan lintas operator berdasar rantai bukti.",
                    sources=(SourcePointer(path=rel, sha256=sha, line=hit_cont[0], excerpt=hit_cont[1]),),
                )
            )
        hit_birth = _find_line(lines, "Tidak ada klaim tanpa surat kelahiran")
        if hit_birth:
            claims.append(
                NarrativeClaim(
                    claim_id=_claim_id("identity", "birth_certificate_rule", True),
                    section="identity",
                    fact_key="birth_certificate_rule",
                    fact_value=True,
                    statement="Setiap klaim kemampuan ACE wajib menyertakan surat kelahiran (instrumen, praregistrasi, rantai bukti).",
                    sources=(SourcePointer(path=rel, sha256=sha, line=hit_birth[0], excerpt=hit_birth[1]),),
                )
            )

    dash_builder = root / "tools" / "dashboard_state_build.py"
    if dash_builder.is_file():
        sha = _sha256_file(dash_builder)
        rel = _rel_or_posix(dash_builder, root)
        lines = dash_builder.read_text(encoding="utf-8").splitlines()
        hit = _find_line(lines, "Multi-brain sovereignty")
        if hit:
            claims.append(
                NarrativeClaim(
                    claim_id=_claim_id("identity", "multi_brain_sovereignty", "organs_replaceable"),
                    section="identity",
                    fact_key="multi_brain_sovereignty",
                    fact_value="organs_replaceable",
                    statement="Kedaulatan multi-otak: model/otak adalah organ tergantikan; identitas berada di konstitusi, ledger, dan memori.",
                    sources=(SourcePointer(path=rel, sha256=sha, line=hit[0], excerpt=hit[1]),),
                )
            )

    status_md = root / "STATUS.md"
    if status_md.is_file():
        sha = _sha256_file(status_md)
        rel = _rel_or_posix(status_md, root)
        lines = status_md.read_text(encoding="utf-8").splitlines()
        hit_rel = _find_line(lines, "release_gate=BLOCK_RELEASE")
        if hit_rel:
            claims.append(
                NarrativeClaim(
                    claim_id=_claim_id("identity", "governance_release_gate", "BLOCK_RELEASE"),
                    section="identity",
                    fact_key="governance_release_gate",
                    fact_value="BLOCK_RELEASE",
                    statement="Gerbang tata kelola rilis aktif tetap BLOCK_RELEASE sampai verifikasi penilai tersegel selesai.",
                    sources=(SourcePointer(path=rel, sha256=sha, line=hit_rel[0], excerpt=hit_rel[1]),),
                )
            )

    if mem_snap.get("present") and mem_snap.get("path") and mem_snap.get("sha256"):
        mpath = mem_snap["path"]
        msha = mem_snap["sha256"]
        active_cnt = len(mem_snap.get("active_records") or [])
        chain_val = mem_snap.get("chain_ok")
        claims.append(
            NarrativeClaim(
                claim_id=_claim_id("identity", "memory_snapshot_state", {"active": active_cnt, "chain_ok": chain_val}),
                section="identity",
                fact_key="memory_snapshot_state",
                fact_value={
                    "format": mem_snap.get("format"),
                    "active_records": active_cnt,
                    "superseded_records": len(mem_snap.get("superseded_records") or []),
                    "tombstones": len(mem_snap.get("tombstones") or []),
                    "chain_ok": chain_val,
                },
                statement=(
                    f"Snapshot memori ({mem_snap.get('format')}) memuat {active_cnt} record aktif, "
                    f"{len(mem_snap.get('superseded_records') or [])} tergantikan, "
                    f"{len(mem_snap.get('tombstones') or [])} tombstone (chain_ok={chain_val})."
                ),
                sources=(SourcePointer(path=mpath, sha256=msha, excerpt=f"format={mem_snap.get('format')}"),),
            )
        )

    return claims


def _extract_gate_and_status_claims(root: Path) -> tuple[list[NarrativeClaim], list[NarrativeClaim]]:
    proven: list[NarrativeClaim] = []
    unproven: list[NarrativeClaim] = []

    # Latest authoritative gate readings: scan Addenda 60, 59, 58 then STATUS.md
    add60 = root / "docs" / "research" / "ACE_OMEGA_CHECKPOINT_20261113_ADDENDUM60.md"
    add59 = root / "docs" / "research" / "ACE_OMEGA_CHECKPOINT_20261113_ADDENDUM59.md"
    add58 = root / "docs" / "research" / "ACE_OMEGA_CHECKPOINT_20261112_ADDENDUM58.md"
    status_md = root / "STATUS.md"
    selfmodel_res = root / "docs" / "ACE_SELFMODEL_RESULTS_V1.md"

    seen_gates: set[str] = set()

    if add60.is_file():
        sha = _sha256_file(add60)
        rel = _rel_or_posix(add60, root)
        lines = add60.read_text(encoding="utf-8").splitlines()
        hit = _find_line(lines, "round2-gate-01 PASSES") or _find_line(lines, "LIFT_DEMONSTRATED")
        if hit:
            seen_gates.add("round2-gate-01")
            proven.append(
                NarrativeClaim(
                    claim_id=_claim_id("proven", "gate:round2-gate-01", "LIFT_DEMONSTRATED"),
                    section="proven",
                    fact_key="gate:round2-gate-01",
                    fact_value="LIFT_DEMONSTRATED",
                    statement="round2-gate-01 berstatus PASS dengan hasil LIFT_DEMONSTRATED (round2_index = 0.0).",
                    sources=(SourcePointer(path=rel, sha256=sha, line=hit[0], excerpt=hit[1]),),
                )
            )

    if add59.is_file():
        sha = _sha256_file(add59)
        rel = _rel_or_posix(add59, root)
        lines = add59.read_text(encoding="utf-8").splitlines()
        hit = _find_line(lines, "G2 board: MEASURED — NOT_DEMONSTRATED") or _find_line(lines, "NOT_DEMONSTRATED")
        if hit:
            seen_gates.add("G2")
            unproven.append(
                NarrativeClaim(
                    claim_id=_claim_id("unproven", "gate:G2", "MEASURED_NOT_DEMONSTRATED"),
                    section="unproven",
                    fact_key="gate:G2",
                    fact_value="MEASURED_NOT_DEMONSTRATED",
                    statement="Gerbang G2 terukur dengan vonis NOT_DEMONSTRATED pada abc_v3 (DI = -1.98pp < 0; 3 bentuk hasil nol).",
                    sources=(SourcePointer(path=rel, sha256=sha, line=hit[0], excerpt=hit[1]),),
                )
            )

    if add58.is_file():
        sha = _sha256_file(add58)
        rel = _rel_or_posix(add58, root)
        lines = add58.read_text(encoding="utf-8").splitlines()
        for gate_name, pat, bucket, val in (
            ("G3", "G3: MEASURED — SPECIALIZATION", proven, "MEASURED_SPECIALIZATION"),
            ("G4", "G4: MEASURED — INHERITANCE_DEMONSTRATED", proven, "MEASURED_INHERITANCE_DEMONSTRATED"),
            ("G5", "G5: NOT_ASSESSED", unproven, "NOT_ASSESSED"),
        ):
            hit = _find_line(lines, pat)
            if hit and gate_name not in seen_gates:
                seen_gates.add(gate_name)
                sec = "proven" if bucket is proven else "unproven"
                bucket.append(
                    NarrativeClaim(
                        claim_id=_claim_id(sec, f"gate:{gate_name}", val),
                        section=sec,
                        fact_key=f"gate:{gate_name}",
                        fact_value=val,
                        statement=f"Gerbang {gate_name} tercatat sebagai {val}.",
                        sources=(SourcePointer(path=rel, sha256=sha, line=hit[0], excerpt=hit[1]),),
                    )
                )

    if status_md.is_file():
        sha = _sha256_file(status_md)
        rel = _rel_or_posix(status_md, root)
        lines = status_md.read_text(encoding="utf-8").splitlines()
        hit_oaie = _find_line(lines, "oaie_established=False")
        if hit_oaie:
            unproven.append(
                NarrativeClaim(
                    claim_id=_claim_id("unproven", "oaie_established", False),
                    section="unproven",
                    fact_key="oaie_established",
                    fact_value=False,
                    statement="Klaim OAIE secara menyeluruh belum ditetapkan (oaie_established=False).",
                    sources=(SourcePointer(path=rel, sha256=sha, line=hit_oaie[0], excerpt=hit_oaie[1]),),
                )
            )
        hit_sci = _find_line(lines, "scientific_status=NOT_ASSESSED")
        if hit_sci:
            unproven.append(
                NarrativeClaim(
                    claim_id=_claim_id("unproven", "scientific_status", "NOT_ASSESSED"),
                    section="unproven",
                    fact_key="scientific_status",
                    fact_value="NOT_ASSESSED",
                    statement="Status ilmiah menyeluruh masih NOT_ASSESSED di luar bukti benchmark lokal.",
                    sources=(SourcePointer(path=rel, sha256=sha, line=hit_sci[0], excerpt=hit_sci[1]),),
                )
            )

    if selfmodel_res.is_file():
        sha = _sha256_file(selfmodel_res)
        rel = _rel_or_posix(selfmodel_res, root)
        lines = selfmodel_res.read_text(encoding="utf-8").splitlines()
        for key, pat, bucket, val in (
            ("functional_self_model", "FUNCTIONAL_SELF_MODEL", proven, "ESTABLISHED_BOUNDED"),
            ("metacognitive_awareness", "METACOGNITIVE_AWARENESS", proven, "MEASURED_BOUNDED"),
            ("phenomenal_consciousness", "PHENOMENAL_CONSCIOUSNESS_UNKNOWN", unproven, "PHENOMENAL_CONSCIOUSNESS_UNKNOWN"),
        ):
            hit = _find_line(lines, pat)
            if hit:
                sec = "proven" if bucket is proven else "unproven"
                bucket.append(
                    NarrativeClaim(
                        claim_id=_claim_id(sec, key, val),
                        section=sec,
                        fact_key=key,
                        fact_value=val,
                        statement=f"Status kapabilitas diri `{key}` tercatat sebagai `{val}`.",
                        sources=(SourcePointer(path=rel, sha256=sha, line=hit[0], excerpt=hit[1]),),
                    )
                )

    return proven, unproven


def _extract_ledger_claims(root: Path, extra_ledgers: list[Path] | None = None) -> tuple[list[NarrativeClaim], list[NarrativeClaim]]:
    proven: list[NarrativeClaim] = []
    unproven: list[NarrativeClaim] = []

    research_ledger = root / "RESEARCH_LEDGER.md"
    if research_ledger.is_file():
        sha = _sha256_file(research_ledger)
        rel = _rel_or_posix(research_ledger, root)
        lines = research_ledger.read_text(encoding="utf-8").splitlines()
        table_rows: list[tuple[int, str, str, str]] = []
        hold_count = 0
        for idx, line in enumerate(lines, start=1):
            stripped = line.strip()
            if not stripped.startswith("|") or stripped.startswith("| Tahap ") or stripped.startswith("| ---"):
                continue
            parts = [p.strip() for p in stripped.strip("|").split("|")]
            if len(parts) >= 3:
                tahap, hipotesis, temuan = parts[0], parts[1], parts[2]
                table_rows.append((idx, tahap, hipotesis, temuan))
                if any(tok in temuan.upper() for tok in ("HOLD", "NO-GO", "BELUM", "INCONCLUSIVE", "INKONKLUSIF", "NOT CONCLUSIVE")):
                    hold_count += 1
        proven.append(
            NarrativeClaim(
                claim_id=_claim_id("proven", "research_ledger_entries", len(table_rows)),
                section="proven",
                fact_key="research_ledger_entries",
                fact_value=len(table_rows),
                statement=f"Ledger riset memuat {len(table_rows)} entri tabel tahapan historis F0 s.d. E1.4s terindeks.",
                sources=(SourcePointer(path=rel, sha256=sha, line=1, excerpt=lines[0] if lines else ""),),
            )
        )
        if hold_count > 0:
            unproven.append(
                NarrativeClaim(
                    claim_id=_claim_id("unproven", "research_ledger_open_or_hold_rows", hold_count),
                    section="unproven",
                    fact_key="research_ledger_open_or_hold_rows",
                    fact_value=hold_count,
                    statement=f"Terdapat {hold_count} baris ledger dengan vonis HOLD/NO-GO/inkonklusif atau pembuktian terbuka.",
                    sources=(SourcePointer(path=rel, sha256=sha, line=table_rows[0][0], excerpt=table_rows[0][1]),),
                )
            )
        hit_e14t = _find_line(lines, "E1.4t")
        if hit_e14t:
            unproven.append(
                NarrativeClaim(
                    claim_id=_claim_id("unproven", "e14t_finding", "DIAGNOSTIC_HOLD"),
                    section="unproven",
                    fact_key="e14t_finding",
                    fact_value="DIAGNOSTIC_HOLD",
                    statement="Tahap E1.4t berakhir dengan temuan diagnostic HOLD dan klaim OAIE/generalisasi independen ditahan.",
                    sources=(SourcePointer(path=rel, sha256=sha, line=hit_e14t[0], excerpt=hit_e14t[1]),),
                )
            )

    for lpath in extra_ledgers or []:
        if not lpath.is_file():
            continue
        sha = _sha256_file(lpath)
        rel = _rel_or_posix(lpath, root)
        lines = lpath.read_text(encoding="utf-8", errors="replace").splitlines()
        hit_rp = _find_line(lines, re.compile(r"Total.*?Rp\s*[0-9.]+", re.IGNORECASE))
        if hit_rp:
            m = re.search(r"Rp\s*([0-9.]+)", hit_rp[1])
            val = m.group(0) if m else hit_rp[1]
            section = "unproven" if val in ("Rp0", "Rp 0") else "proven"
            target_bucket = unproven if section == "unproven" else proven
            target_bucket.append(
                NarrativeClaim(
                    claim_id=_claim_id(section, f"ledger_total:{rel}", val),
                    section=section,
                    fact_key=f"ledger_total:{rel}",
                    fact_value=val,
                    statement=f"Ledger pendapatan ({rel}) mencatat total terverifikasi {val}.",
                    sources=(SourcePointer(path=rel, sha256=sha, line=hit_rp[0], excerpt=hit_rp[1]),),
                )
            )

    return proven, unproven


def _extract_memory_claims(mem_snap: dict[str, Any]) -> tuple[list[NarrativeClaim], list[NarrativeClaim]]:
    proven: list[NarrativeClaim] = []
    unproven: list[NarrativeClaim] = []
    if not mem_snap.get("present") or not mem_snap.get("path") or not mem_snap.get("sha256"):
        return proven, unproven

    mpath = str(mem_snap["path"])
    msha = str(mem_snap["sha256"])

    active = list(mem_snap.get("active_records") or [])
    verified_recs: list[dict[str, Any]] = []
    guess_recs: list[dict[str, Any]] = []
    for rec in active:
        skind = str((rec.get("source") or {}).get("kind") or "model")
        if skind in ("evidence", "operator"):
            verified_recs.append(rec)
        else:
            guess_recs.append(rec)

    if verified_recs:
        for rec in verified_recs:
            rid = str(rec.get("id") or "")
            skind = str((rec.get("source") or {}).get("kind") or "")
            rkind = str(rec.get("kind") or "episodic")
            content = rec.get("content") or {}
            summary = content.get("event") or content.get("text") or content.get("task") or _canonical_json(content)
            proven.append(
                NarrativeClaim(
                    claim_id=_claim_id("proven", f"memory_record:{rid}", {"kind": rkind, "source_kind": skind}),
                    section="proven",
                    fact_key=f"memory_record:{rid}",
                    fact_value={"id": rid, "kind": rkind, "source_kind": skind, "summary": str(summary)},
                    statement=f"Ingatan terjangkar [{rkind}/{skind}] ({rid}): {summary}",
                    sources=(
                        SourcePointer(
                            path=mpath,
                            sha256=msha,
                            line=rec.get("_line"),
                            record_id=rid,
                            seq=rec.get("written_seq"),
                            excerpt=str(summary)[:120],
                        ),
                    ),
                )
            )

    if guess_recs:
        for rec in guess_recs:
            rid = str(rec.get("id") or "")
            skind = str((rec.get("source") or {}).get("kind") or "model")
            content = rec.get("content") or {}
            summary = content.get("event") or content.get("text") or _canonical_json(content)
            unproven.append(
                NarrativeClaim(
                    claim_id=_claim_id("unproven", f"memory_unverified_guess:{rid}", skind),
                    section="unproven",
                    fact_key=f"memory_unverified_guess:{rid}",
                    fact_value={"id": rid, "source_kind": skind, "summary": str(summary)},
                    statement=f"Ingatan berstatus belum terverifikasi [{skind}] ({rid}): {summary}",
                    sources=(
                        SourcePointer(
                            path=mpath,
                            sha256=msha,
                            line=rec.get("_line"),
                            record_id=rid,
                            seq=rec.get("written_seq"),
                            excerpt=str(summary)[:120],
                        ),
                    ),
                )
            )

    if mem_snap.get("chain_ok") is False:
        unproven.append(
            NarrativeClaim(
                claim_id=_claim_id("unproven", "memory_chain_integrity", False),
                section="unproven",
                fact_key="memory_chain_integrity",
                fact_value=False,
                statement=f"Integritas rantai hash pada snapshot memori ({mpath}) mengalami kegagalan verifikasi.",
                sources=(SourcePointer(path=mpath, sha256=msha, excerpt="chain_ok=False"),),
            )
        )

    return proven, unproven


# ---------------------------------------------------------------------------
# Public Builder + Fact Extractor + Markdown Renderer
# ---------------------------------------------------------------------------

def extract_facts(model: dict[str, Any]) -> list[dict[str, Any]]:
    """Ekstrak fakta ternormalisasi dari narasi tanpa bergantung gaya kalimat."""
    facts: list[dict[str, Any]] = []
    sections = model.get("sections") or {}
    for sec in ("identity", "proven", "unproven"):
        for item in sections.get(sec) or []:
            facts.append(
                {
                    "section": sec,
                    "fact_key": item["fact_key"],
                    "fact_value": item["fact_value"],
                    "source_paths": sorted({s["path"] for s in item.get("sources") or []}),
                }
            )
    facts.sort(key=lambda f: (f["section"], f["fact_key"]))
    return facts


def render_markdown(model: dict[str, Any]) -> str:
    """Render model-diri naratif menjadi Markdown ringkas dengan sitasi per baris."""
    lines: list[str] = [
        "# Model-Diri Naratif ACE Ω (Lapis 3)",
        "",
        f"- **Skema**: `{model['schema']}`",
        f"- **Mode baca-saja**: `{model['read_only']}`",
        f"- **Klaim ditolak karena tanpa sumber**: `{len(model['rejected_sourceless_claims'])}`",
        f"- **Konteks organ aktif (metadata non-identitas)**: `{_canonical_json(model.get('organ_context') or {})}`",
        "",
    ]
    headings = (
        ("identity", "## 1. Identitas & Konstitusi (`identity`)"),
        ("proven", "## 2. Kemampuan & Hasil Terbukti (`proven`)"),
        ("unproven", "## 3. Belum Terbukti, Hasil Nol, & Tebakan (`unproven`)"),
    )
    sections = model.get("sections") or {}
    for sec_key, heading in headings:
        lines.append(heading)
        lines.append("")
        items = sections.get(sec_key) or []
        if not items:
            lines.append("- _(Tidak ada klaim bersumber untuk kategori ini.)_")
            lines.append("")
            continue
        for clm in items:
            cites = ", ".join(
                f"`{s['path']}"
                + (f"#L{s['line']}" if s.get("line") is not None else "")
                + f"` (`{s['sha256'][:12]}`)"
                for s in clm["sources"]
            )
            lines.append(f"- **{clm['fact_key']}**: {clm['statement']} [sumber: {cites}]")
        lines.append("")
    return "\n".join(lines)


def build_narrative_self_model(
    root: str | Path,
    *,
    memory_path: str | Path | None = None,
    extra_ledgers: list[str | Path] | None = None,
    organ_context: dict[str, Any] | None = None,
    inject_unverified_claims: list[NarrativeClaim] | None = None,
    narrative_style: str = "standard",
) -> dict[str, Any]:
    """Bangun model-diri naratif deterministik & terverifikasi sumber (read-only)."""
    repo_root = Path(root).resolve()
    mem_resolved = Path(memory_path).resolve() if memory_path is not None else None
    if mem_resolved is None:
        default_seed = repo_root / "data" / "ace_seed_snapshot.json"
        if default_seed.is_file():
            mem_resolved = default_seed

    allowed_roots = [repo_root]
    if mem_resolved is not None:
        allowed_roots.append(mem_resolved if mem_resolved.is_dir() else mem_resolved.parent)

    ledger_paths = [Path(p).resolve() for p in (extra_ledgers or [])]
    for lp in ledger_paths:
        allowed_roots.append(lp.parent)

    mem_snap = read_memory_snapshot_readonly(mem_resolved, repo_root)

    cand_identity = _extract_identity_claims(repo_root, mem_snap)
    gate_proven, gate_unproven = _extract_gate_and_status_claims(repo_root)
    ledg_proven, ledg_unproven = _extract_ledger_claims(repo_root, ledger_paths)
    mem_proven, mem_unproven = _extract_memory_claims(mem_snap)

    cand_proven = gate_proven + ledg_proven + mem_proven
    cand_unproven = gate_unproven + ledg_unproven + mem_unproven

    for extra in inject_unverified_claims or []:
        if extra.section == "identity":
            cand_identity.append(extra)
        elif extra.section == "proven":
            cand_proven.append(extra)
        else:
            cand_unproven.append(extra)

    if narrative_style == "concise_en":
        def _rephrase(lst: list[NarrativeClaim]) -> list[NarrativeClaim]:
            return [
                NarrativeClaim(
                    claim_id=c.claim_id,
                    section=c.section,
                    fact_key=c.fact_key,
                    fact_value=c.fact_value,
                    statement=f"[{c.section.upper()}] {c.fact_key} = {_canonical_json(c.fact_value)}",
                    sources=c.sources,
                )
                for c in lst
            ]
        cand_identity = _rephrase(cand_identity)
        cand_proven = _rephrase(cand_proven)
        cand_unproven = _rephrase(cand_unproven)

    acc_id, rej_id = verify_claim_sources(cand_identity, allowed_roots)
    acc_pr, rej_pr = verify_claim_sources(cand_proven, allowed_roots)
    acc_un, rej_un = verify_claim_sources(cand_unproven, allowed_roots)

    acc_id.sort(key=lambda c: (c.fact_key, c.claim_id))
    acc_pr.sort(key=lambda c: (c.fact_key, c.claim_id))
    acc_un.sort(key=lambda c: (c.fact_key, c.claim_id))

    model = {
        "schema": SCHEMA,
        "read_only": True,
        "narrative_style": narrative_style,
        "organ_context": dict(organ_context or {"role": "default", "label": "unspecified"}),
        "memory_summary": {
            "present": mem_snap.get("present"),
            "format": mem_snap.get("format"),
            "path": mem_snap.get("path"),
            "sha256": mem_snap.get("sha256"),
            "chain_ok": mem_snap.get("chain_ok"),
            "active_count": len(mem_snap.get("active_records") or []),
            "superseded_count": len(mem_snap.get("superseded_records") or []),
            "tombstone_count": len(mem_snap.get("tombstones") or []),
            "anchored_evidence_count": mem_snap.get("anchored_evidence_count", 0),
        },
        "sections": {
            "identity": [c.to_dict() for c in acc_id],
            "proven": [c.to_dict() for c in acc_pr],
            "unproven": [c.to_dict() for c in acc_un],
        },
        "rejected_sourceless_claims": rej_id + rej_pr + rej_un,
    }
    assert_no_sourceless_claims(model, allowed_roots)
    model["facts"] = extract_facts(model)
    return model


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Akar repositori ACE")
    parser.add_argument("--memory", default=None, help="Path ke snapshot memori atau direktori memory.jsonl (baca-saja)")
    parser.add_argument("--ledger", action="append", default=[], help="Ledger tambahan untuk dibaca")
    parser.add_argument("--organ-label", default="unspecified", help="Metadata label organ aktif (bukan bagian identitas)")
    parser.add_argument("--style", choices=("standard", "concise_en"), default="standard")
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    parser.add_argument("--out", default=None, help="Simpan hasil ke berkas terpisah (opsional)")
    args = parser.parse_args(argv)

    model = build_narrative_self_model(
        args.root,
        memory_path=args.memory,
        extra_ledgers=args.ledger,
        organ_context={"label": args.organ_label},
        narrative_style=args.style,
    )
    rendered = json.dumps(model, indent=2, ensure_ascii=False) if args.format == "json" else render_markdown(model)
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(rendered, encoding="utf-8")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
