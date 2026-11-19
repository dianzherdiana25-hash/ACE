#!/usr/bin/env python3
"""C6 — Permukaan Agenda dari Kegagalan & Konsolidasi (Lapis 3, read-only).

Memindai dokumen vonis/ledger (``handover/*VERDICT*.md``, ``RESEARCH_LEDGER.md``,
Addendum gerbang) dan keluaran konsolidasi C3 (``ace.metacog-consolidation.v1``)
atau snapshot ``memory.jsonl`` secara strictly read-only, menamai kegagalan nyata,
dan menerbitkan kandidat agenda berformat register dengan:
- ``brain_of_origin = "gravity-proposal"``
- ``decision_owner = "Ian"``
- ``decision_status = "PROPOSED_AWAITING_IAN"``

Tidak pernah mengubah ``OpportunityRegister`` maupun store hidup.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys
from typing import Any


SCHEMA = "ace.failure-to-agenda.v1"
DRAFT_SCHEMA = "ace.register-agenda-draft.v1"
BRAIN_OF_ORIGIN = "gravity-proposal"
DECISION_OWNER = "Ian"

_SEVERITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}

_FAILURE_TOKENS = re.compile(
    r"\b(NOT_DEMONSTRATED|NOT_PASSED|NO-GO|FAIL|FAILED|GAGAL|PARTIAL|HOLD|BLOCKED|DIAGNOSTIC HOLD)\b",
    re.IGNORECASE,
)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


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
    try:
        return PurePosixPath(path.resolve().relative_to(root.resolve())).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _slug(text: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return re.sub(r"_+", "_", cleaned)[:64] or "unnamed"


def _make_draft(
    *,
    title: str,
    combination_hints: list[str],
    rationale: str,
    fences: list[str],
) -> dict[str, Any]:
    body = {
        "schema": DRAFT_SCHEMA,
        "title": title,
        "combination": combination_hints,
        "rationale": rationale,
        "origin": BRAIN_OF_ORIGIN,
        "status": "proposed",
        "fences": fences,
    }
    draft_hash = hashlib.sha256(_canonical_json(body).encode("utf-8")).hexdigest()
    body["draft_hash"] = draft_hash
    return body


def _scan_verdict_markdown(path: Path, root: Path) -> list[dict[str, Any]]:
    rel = _rel_or_posix(path, root)
    sha = _sha256_file(path)
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    raw_items: list[dict[str, Any]] = []

    if path.name == "RESEARCH_LEDGER.md":
        for line_no, raw in enumerate(lines, start=1):
            stripped = raw.strip()
            if not stripped.startswith("|") or stripped.startswith("| Tahap ") or stripped.startswith("| ---"):
                continue
            parts = [p.strip() for p in stripped.strip("|").split("|")]
            if len(parts) < 3:
                continue
            stage, _, finding = parts[0], parts[1], parts[2]
            m = _FAILURE_TOKENS.search(finding)
            if not m:
                continue
            tok = m.group(1).upper()
            sev = "HIGH" if tok in {"NO-GO", "FAIL", "FAILED", "NOT_PASSED", "NOT_DEMONSTRATED"} else "MEDIUM"
            raw_items.append(
                {
                    "dedup_key": ("ledger", _slug(stage)),
                    "failure_kind": "ledger_hold",
                    "severity": sev,
                    "subject": stage,
                    "verdict_label": tok,
                    "title": f"Tindak lanjut temuan {tok} pada tahap {stage}",
                    "rationale": f"Ledger mencatat `{tok}` pada {stage}: {finding[:180]}",
                    "fences": ["preregistration_before_execution", "no_instrument_edit"],
                    "combination_hints": ["cap_sealed_evaluation", "research_ledger_diagnosis"],
                    "source": {"path": rel, "sha256": sha, "line": line_no, "excerpt": stripped[:140]},
                }
            )
        return raw_items

    # Generic verdict/addendum markdown document
    doc_title = lines[0].lstrip("# ").strip() if lines else path.stem
    m_head = _FAILURE_TOKENS.search(doc_title)
    if m_head:
        tok = m_head.group(1).upper()
        sev = "HIGH" if tok in {"NOT_PASSED", "NOT_DEMONSTRATED", "FAILED", "FAIL", "NO-GO"} else "MEDIUM"
        subj = path.stem
        raw_items.append(
            {
                "dedup_key": ("verdict_doc", _slug(subj)),
                "failure_kind": "gate_or_verdict_failure",
                "severity": sev,
                "subject": subj,
                "verdict_label": tok,
                "title": f"Investigasi & perbaikan gap vonis {tok} ({path.name})",
                "rationale": f"Dokumen vonis `{doc_title}` berhenti pada status `{tok}`.",
                "fences": ["split_custody_preserved", "require_ian_ratification"],
                "combination_hints": ["cap_sealed_evaluation", _slug(subj)],
                "source": {"path": rel, "sha256": sha, "line": 1, "excerpt": doc_title[:140]},
            }
        )
        return raw_items

    # Otherwise scan body for named gate failures (e.g. Addendum 59 G2 NOT_DEMONSTRATED)
    for line_no, raw in enumerate(lines, start=1):
        s = raw.strip()
        if "G2 board: MEASURED — NOT_DEMONSTRATED" in s or "abc_v3" in s and "NOT_DEMONSTRATED" in s:
            raw_items.append(
                {
                    "dedup_key": ("gate_failure", "g2_not_demonstrated"),
                    "failure_kind": "gate_or_verdict_failure",
                    "severity": "HIGH",
                    "subject": "G2 / abc_v3",
                    "verdict_label": "NOT_DEMONSTRATED",
                    "title": "Atasi kegagalan diferensiasi G2 (control margin negatif pada abc_v3)",
                    "rationale": f"Addendum mencatat G2 NOT_DEMONSTRATED: {s[:160]}",
                    "fences": ["fresh_preregistered_band", "zero_control_regression"],
                    "combination_hints": ["cap_operator_discovery", "cap_sealed_evaluation"],
                    "source": {"path": rel, "sha256": sha, "line": line_no, "excerpt": s[:140]},
                }
            )
            break
    return raw_items


def _scan_consolidation_json(path: Path, root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rel = _rel_or_posix(path, root)
    sha = _sha256_file(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except json.JSONDecodeError as exc:
        return [], [{"path": rel, "error": str(exc)}]
    if not isinstance(data, dict):
        return [], [{"path": rel, "error": "consolidation root must be an object"}]

    raw_items: list[dict[str, Any]] = []
    for cl in data.get("failure_clusters") or []:
        if not isinstance(cl, dict):
            continue
        ckey = str(cl.get("cluster_key") or cl.get("cluster_id") or "unknown")
        cnt = int(cl.get("count") or 1)
        recurring = bool(cl.get("recurring"))
        sev = "HIGH" if recurring else "MEDIUM"
        sample = (cl.get("sample_summaries") or [ckey])[0]
        raw_items.append(
            {
                "dedup_key": ("cluster", _slug(ckey)),
                "failure_kind": "recurring_failure_cluster" if recurring else "single_failure_cluster",
                "severity": sev,
                "subject": ckey,
                "verdict_label": "RECURRING_FAILURE" if recurring else "FAILURE_CLUSTER",
                "title": f"Audit & remediasi kluster kegagalan `{ckey}` ({cnt} kejadian)",
                "rationale": f"Konsolidasi C3 menandai `{ckey}` (konteks={cl.get('contexts')}, contoh='{sample}').",
                "fences": ["replay_idempotence", "diagnostic_isolation_first"],
                "combination_hints": ["cap_official_path_repair", _slug(str(cl.get("domain") or "memory"))],
                "source": {
                    "path": rel,
                    "sha256": sha,
                    "cluster_id": cl.get("cluster_id"),
                    "excerpt": f"{ckey} count={cnt}: {str(sample)[:90]}",
                },
            }
        )

    for nt in data.get("negative_transfer_alerts") or []:
        if not isinstance(nt, dict):
            continue
        rid = str(nt.get("record_id") or "unknown")
        fctx = str(nt.get("failing_context") or "unknown")
        raw_items.append(
            {
                "dedup_key": ("neg_transfer", f"{_slug(rid)}_{_slug(fctx)}"),
                "failure_kind": "negative_transfer",
                "severity": "HIGH",
                "subject": f"{rid} @ {fctx}",
                "verdict_label": "NEGATIVE_TRANSFER_RISK",
                "title": f"Pagar ulang konteks prosedur `{rid}` yang gagal di `{fctx}`",
                "rationale": (
                    f"Prosedur `{nt.get('summary')}` gagal {nt.get('context_fail')}x di `{fctx}` "
                    f"meski berhasil di {nt.get('succeeded_elsewhere')}."
                ),
                "fences": ["abstain_on_mismatch_context", "admission_guard"],
                "combination_hints": ["cap_procurement_director", "cap_operator_discovery"],
                "source": {
                    "path": rel,
                    "sha256": sha,
                    "record_id": rid,
                    "excerpt": f"negative_transfer {rid} fail={nt.get('context_fail')} ctx={fctx}",
                },
            }
        )

    for hf in data.get("open_high_findings") or []:
        if not isinstance(hf, dict):
            continue
        fkey = str(hf.get("finding_key") or hf.get("record_id") or "high_finding")
        raw_items.append(
            {
                "dedup_key": ("open_high", _slug(fkey)),
                "failure_kind": "open_high_finding",
                "severity": "CRITICAL",
                "subject": fkey,
                "verdict_label": "HIGH_FINDING_OPEN",
                "title": f"Tutup temuan HIGH terbuka `{fkey}`",
                "rationale": f"Temuan HIGH `{fkey}` belum memiliki event penutupan: {hf.get('summary')}",
                "fences": ["evidence_anchored_closure", "independent_verifier_check"],
                "combination_hints": ["cap_sealed_evaluation", _slug(fkey)],
                "source": {
                    "path": rel,
                    "sha256": sha,
                    "record_id": hf.get("record_id"),
                    "excerpt": str(hf.get("summary") or fkey)[:120],
                },
            }
        )

    return raw_items, []


def _scan_raw_memory_failures_readonly(mem_path: Path, root: Path) -> list[dict[str, Any]]:
    target = mem_path / "memory.jsonl" if mem_path.is_dir() else mem_path
    if not target.is_file():
        return []
    rel = _rel_or_posix(target, root)
    sha = _sha256_file(target)

    opened: dict[str, tuple[int, dict[str, Any]]] = {}
    closed: set[str] = set()
    for line_no, raw in enumerate(target.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
        s = raw.strip()
        if not s:
            continue
        try:
            obj = json.loads(s)
        except json.JSONDecodeError:
            continue
        ev = obj.get("event") if isinstance(obj, dict) else None
        if not isinstance(ev, dict) or ev.get("type") != "record":
            continue
        rec = ev.get("record") or {}
        content = rec.get("content") if isinstance(rec.get("content"), dict) else {}
        cls = str(content.get("class") or "").lower()
        fkey = str(content.get("finding_id") or content.get("subject") or rec.get("id") or f"line_{line_no}")
        if cls == "finding_high_opened":
            opened[fkey] = (line_no, rec)
        elif cls == "finding_high_closed":
            closed.add(fkey)

    out: list[dict[str, Any]] = []
    for fkey, (line_no, rec) in sorted(opened.items()):
        if fkey in closed:
            continue
        summary = str((rec.get("content") or {}).get("event") or fkey)
        out.append(
            {
                "dedup_key": ("open_high", _slug(fkey)),
                "failure_kind": "open_high_finding",
                "severity": "CRITICAL",
                "subject": fkey,
                "verdict_label": "HIGH_FINDING_OPEN",
                "title": f"Tutup temuan HIGH terbuka `{fkey}`",
                "rationale": f"Log memori merekam temuan HIGH terbuka `{summary}` tanpa penutupan.",
                "fences": ["evidence_anchored_closure", "read_only_audit_first"],
                "combination_hints": ["cap_sealed_evaluation", _slug(fkey)],
                "source": {"path": rel, "sha256": sha, "line": line_no, "record_id": rec.get("id"), "excerpt": summary[:120]},
            }
        )
    return out


def generate_failure_agenda_candidates(
    root: str | Path,
    *,
    docs: list[str | Path] | None = None,
    consolidation_paths: list[str | Path] | None = None,
    memory_paths: list[str | Path] | None = None,
    scan_default_repo_docs: bool = True,
) -> dict[str, Any]:
    """Pindai dokumen vonis/konsolidasi dan hasilkan kandidat agenda register."""
    repo_root = Path(root).resolve()
    raw_items: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    scanned_files: list[str] = []

    doc_paths: list[Path] = []
    if scan_default_repo_docs:
        if (repo_root / "RESEARCH_LEDGER.md").is_file():
            doc_paths.append(repo_root / "RESEARCH_LEDGER.md")
        if (repo_root / "handover").is_dir():
            doc_paths.extend(sorted((repo_root / "handover").glob("*VERDICT*.md")))
        add59 = repo_root / "docs" / "research" / "ACE_OMEGA_CHECKPOINT_20261113_ADDENDUM59.md"
        if add59.is_file():
            doc_paths.append(add59)
    for d in docs or []:
        p = Path(d).resolve()
        if p.is_file():
            doc_paths.append(p)

    seen_docs: set[Path] = set()
    for p in doc_paths:
        res = p.resolve()
        if res in seen_docs or not res.is_file():
            continue
        seen_docs.add(res)
        scanned_files.append(_rel_or_posix(res, repo_root))
        raw_items.extend(_scan_verdict_markdown(res, repo_root))

    for cp in consolidation_paths or []:
        p = Path(cp).resolve()
        if not p.is_file():
            errors.append({"path": _rel_or_posix(p, repo_root), "error": "consolidation file not found"})
            continue
        scanned_files.append(_rel_or_posix(p, repo_root))
        items, errs = _scan_consolidation_json(p, repo_root)
        raw_items.extend(items)
        errors.extend(errs)

    for mp in memory_paths or []:
        p = Path(mp).resolve()
        if p.exists():
            scanned_files.append(_rel_or_posix(p, repo_root))
            raw_items.extend(_scan_raw_memory_failures_readonly(p, repo_root))

    # Deduplikasi kanonik berdasarkan dedup_key sambil menggabungkan seluruh pointer sumber
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for item in raw_items:
        grouped[item["dedup_key"]].append(item)

    candidates: list[dict[str, Any]] = []
    for dkey, group in grouped.items():
        group_sorted = sorted(group, key=lambda g: (_SEVERITY_ORDER.get(g["severity"], 9), g["source"]["path"]))
        lead = group_sorted[0]
        cid = "fail_ag_" + hashlib.sha256(_canonical_json(list(dkey)).encode("utf-8")).hexdigest()[:12]
        sources: list[dict[str, Any]] = []
        seen_src: set[str] = set()
        for g in group_sorted:
            s_key = _canonical_json(g["source"])
            if s_key not in seen_src:
                seen_src.add(s_key)
                sources.append(g["source"])

        draft = _make_draft(
            title=lead["title"],
            combination_hints=sorted(set(lead["combination_hints"])),
            rationale=lead["rationale"],
            fences=lead["fences"],
        )
        candidates.append(
            {
                "candidate_id": cid,
                "brain_of_origin": BRAIN_OF_ORIGIN,
                "decision_owner": DECISION_OWNER,
                "decision_status": "PROPOSED_AWAITING_IAN",
                "claim_made": False,
                "requires_ian_decision": True,
                "severity": lead["severity"],
                "failure_kind": lead["failure_kind"],
                "subject": lead["subject"],
                "verdict_label": lead["verdict_label"],
                "title": lead["title"],
                "occurrence_count": len(group),
                "sources": sources,
                "register_entry_draft": draft,
            }
        )

    candidates.sort(
        key=lambda c: (
            _SEVERITY_ORDER.get(c["severity"], 9),
            -c["occurrence_count"],
            c["title"],
            c["candidate_id"],
        )
    )

    return {
        "schema": SCHEMA,
        "read_only": True,
        "brain_of_origin": BRAIN_OF_ORIGIN,
        "decision_owner": DECISION_OWNER,
        "scanned_files_count": len(scanned_files),
        "scanned_files": sorted(set(scanned_files)),
        "candidates_count": len(candidates),
        "candidates": candidates,
        "scan_errors": errors,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Kandidat Agenda dari Kegagalan & Konsolidasi (C6)",
        "",
        f"- **Skema**: `{report['schema']}` (`read_only={report['read_only']}`)",
        f"- **Brain-of-Origin**: `{report['brain_of_origin']}` | **Keputusan di**: `{report['decision_owner']}`",
        f"- **Jumlah berkas dipindai**: {report['scanned_files_count']} | **Jumlah kandidat**: {report['candidates_count']}",
        "",
    ]
    if not report["candidates"]:
        lines.append("- _(Tidak ada kandidat kegagalan terdeteksi.)_")
    else:
        for c in report["candidates"]:
            cites = ", ".join(
                f"`{s['path']}" + (f"#L{s['line']}" if s.get("line") else "") + "`"
                for s in c["sources"]
            )
            lines.append(
                f"- **[{c['severity']}] `{c['candidate_id']}`** — {c['title']} "
                f"(status=`{c['decision_status']}`, origin=`{c['brain_of_origin']}`, sumber={cites})"
            )
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Akar repositori ACE")
    parser.add_argument("--doc", action="append", default=[], help="Dokumen Markdown vonis tambahan")
    parser.add_argument("--consolidation", action="append", default=[], help="Keluaran JSON dari C3 metacog_memory_consolidate.py")
    parser.add_argument("--memory", action="append", default=[], help="Snapshot memory.jsonl baca-saja")
    parser.add_argument("--no-default-docs", action="store_true", help="Jangan pindai dokumen repo default")
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    parser.add_argument("--out", default=None)
    args = parser.parse_args(argv)

    report = generate_failure_agenda_candidates(
        args.root,
        docs=args.doc,
        consolidation_paths=args.consolidation,
        memory_paths=args.memory,
        scan_default_repo_docs=not args.no_default_docs,
    )
    rendered = json.dumps(report, indent=2, ensure_ascii=False) if args.format == "json" else render_markdown(report)
    if args.out:
        out_p = Path(args.out)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(rendered, encoding="utf-8")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
