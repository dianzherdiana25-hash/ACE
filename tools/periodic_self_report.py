#!/usr/bin/env python3
"""C5 — Generator Laporan-Diri Berkala untuk Pemilik (Lapis 3, read-only).

Menghasilkan laporan singkat siap-pemilik (Markdown & JSON terstruktur) dari
sumber-sumber model-diri naratif (C1) secara read-only:
1. Gerbang (``gates``)
2. Vonis terbaru (``latest_verdicts``)
3. Antrean aktif (``queue``)
4. Utang bukti bernama (``named_evidence_debt``)

Aturan kejujuran: setiap butir membawa pointer berkas sumber + SHA-256. Berkas
keadaan operasional yang tidak ada di disk dicatat eksplisit sebagai
``SOURCE_NOT_PRESENT`` — tidak pernah diisi nilai tebakan.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys
from typing import Any


SCHEMA = "ace.periodic-self-report.v1"


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


def _find_line(lines: list[str], pattern: str | re.Pattern[str]) -> tuple[int, str] | None:
    if isinstance(pattern, str):
        for idx, ln in enumerate(lines, start=1):
            if pattern in ln:
                return idx, ln.strip()
        return None
    for idx, ln in enumerate(lines, start=1):
        if pattern.search(ln):
            return idx, ln.strip()
    return None


def _read_memory_counts_readonly(memory_path: Path | None, root: Path) -> dict[str, Any]:
    if memory_path is None:
        default_seed = root / "data" / "ace_seed_snapshot.json"
        if not default_seed.is_file():
            return {"present": False, "path": None, "sha256": None, "evidence_count": 0, "operator_count": 0, "model_guess_count": 0, "chain_ok": None}
        memory_path = default_seed

    target = Path(memory_path)
    if target.is_dir():
        cand = target / "memory.jsonl"
        if not cand.is_file():
            return {"present": False, "path": _rel_or_posix(cand, root), "sha256": None, "evidence_count": 0, "operator_count": 0, "model_guess_count": 0, "chain_ok": None}
        target = cand
    if not target.is_file():
        return {"present": False, "path": _rel_or_posix(target, root), "sha256": None, "evidence_count": 0, "operator_count": 0, "model_guess_count": 0, "chain_ok": None}

    rel = _rel_or_posix(target, root)
    sha = _sha256_file(target)
    if target.suffix.lower() == ".json":
        try:
            data = json.loads(target.read_text(encoding="utf-8", errors="replace"))
        except json.JSONDecodeError:
            return {"present": True, "path": rel, "sha256": sha, "evidence_count": 0, "operator_count": 0, "model_guess_count": 0, "chain_ok": False}
        mem_cnt = len(data.get("memories") or []) if isinstance(data, dict) else 0
        return {"present": True, "path": rel, "sha256": sha, "evidence_count": 0, "operator_count": mem_cnt, "model_guess_count": 0, "chain_ok": None}

    recs: dict[str, dict[str, Any]] = {}
    prev = "GENESIS"
    chain_ok = True
    saw_env = False
    for line in target.read_text(encoding="utf-8", errors="replace").splitlines():
        s = line.strip()
        if not s:
            continue
        try:
            obj = json.loads(s)
        except json.JSONDecodeError:
            chain_ok = False
            continue
        if isinstance(obj, dict) and "event" in obj and isinstance(obj["event"], dict):
            saw_env = True
            exp_hash = hashlib.sha256(_canonical_json({"prev": prev, "event": obj.get("event")}).encode("utf-8")).hexdigest()
            if obj.get("prev") != prev or obj.get("hash") != exp_hash:
                chain_ok = False
            prev = str(obj.get("hash") or prev)
            ev = obj["event"]
            if ev.get("type") == "record" and isinstance(ev.get("record"), dict):
                r = dict(ev["record"])
                recs[str(r.get("id") or "")] = r
            elif ev.get("type") == "supersede":
                rid = str(ev.get("record_id") or "")
                if rid in recs:
                    recs[rid]["status"] = "superseded"
            elif ev.get("type") == "tombstone":
                recs.pop(str(ev.get("record_id") or ""), None)
        elif isinstance(obj, dict):
            recs[str(obj.get("id") or len(recs))] = obj

    active = [r for r in recs.values() if r.get("status", "active") == "active"]
    ev_cnt = sum(1 for r in active if (r.get("source") or {}).get("kind") == "evidence")
    op_cnt = sum(1 for r in active if (r.get("source") or {}).get("kind") == "operator")
    mdl_cnt = sum(1 for r in active if (r.get("source") or {}).get("kind") == "model")
    return {
        "present": True,
        "path": rel,
        "sha256": sha,
        "evidence_count": ev_cnt,
        "operator_count": op_cnt,
        "model_guess_count": mdl_cnt,
        "chain_ok": chain_ok if saw_env else None,
    }


def _collect_gates(root: Path, narrative_model: dict[str, Any] | None) -> list[dict[str, Any]]:
    gates: dict[str, dict[str, Any]] = {}

    if narrative_model and isinstance(narrative_model.get("sections"), dict):
        for sec in ("identity", "proven", "unproven"):
            for clm in narrative_model["sections"].get(sec) or []:
                fk = str(clm.get("fact_key") or "")
                if fk.startswith("gate:") or fk in ("oaie_established", "governance_release_gate"):
                    gname = fk.split(":", 1)[1] if fk.startswith("gate:") else fk
                    srcs = clm.get("sources") or []
                    if srcs:
                        gates[gname] = {
                            "gate": gname,
                            "status": str(clm.get("fact_value")),
                            "bucket": sec,
                            "source": srcs[0],
                        }

    add60 = root / "docs" / "research" / "ACE_OMEGA_CHECKPOINT_20261113_ADDENDUM60.md"
    add59 = root / "docs" / "research" / "ACE_OMEGA_CHECKPOINT_20261113_ADDENDUM59.md"
    add58 = root / "docs" / "research" / "ACE_OMEGA_CHECKPOINT_20261112_ADDENDUM58.md"
    status_md = root / "STATUS.md"

    if add60.is_file() and "round2-gate-01" not in gates:
        lines = add60.read_text(encoding="utf-8").splitlines()
        hit = _find_line(lines, "round2-gate-01 PASSES") or _find_line(lines, "LIFT_DEMONSTRATED")
        if hit:
            gates["round2-gate-01"] = {
                "gate": "round2-gate-01",
                "status": "PASS (LIFT_DEMONSTRATED, index=0.0)",
                "bucket": "proven",
                "source": {"path": _rel_or_posix(add60, root), "sha256": _sha256_file(add60), "line": hit[0]},
            }

    if add59.is_file() and "G2" not in gates:
        lines = add59.read_text(encoding="utf-8").splitlines()
        hit = _find_line(lines, "G2 board: MEASURED — NOT_DEMONSTRATED") or _find_line(lines, "NOT_DEMONSTRATED")
        if hit:
            gates["G2"] = {
                "gate": "G2",
                "status": "MEASURED — NOT_DEMONSTRATED (abc_v3 DI=-1.98pp)",
                "bucket": "unproven",
                "source": {"path": _rel_or_posix(add59, root), "sha256": _sha256_file(add59), "line": hit[0]},
            }

    if add58.is_file():
        lines = add58.read_text(encoding="utf-8").splitlines()
        sha = _sha256_file(add58)
        rel = _rel_or_posix(add58, root)
        for gname, pat, bucket in (
            ("G3", "G3: MEASURED — SPECIALIZATION", "proven"),
            ("G4", "G4: MEASURED — INHERITANCE_DEMONSTRATED", "proven"),
            ("G5", "G5: NOT_ASSESSED", "unproven"),
        ):
            if gname not in gates:
                hit = _find_line(lines, pat)
                if hit:
                    gates[gname] = {
                        "gate": gname,
                        "status": hit[1].lstrip("- ").strip("*"),
                        "bucket": bucket,
                        "source": {"path": rel, "sha256": sha, "line": hit[0]},
                    }

    if status_md.is_file():
        lines = status_md.read_text(encoding="utf-8").splitlines()
        sha = _sha256_file(status_md)
        rel = _rel_or_posix(status_md, root)
        if "G1" not in gates:
            hit_g1 = _find_line(lines, re.compile(r"^\|\s*G1\s*\|")) or _find_line(lines, "G1:")
            if hit_g1:
                parts = [p.strip() for p in hit_g1[1].strip("|").split("|")]
                g1_val = parts[1].strip("` ") if len(parts) >= 2 else hit_g1[1][:100]
                gates["G1"] = {
                    "gate": "G1",
                    "status": g1_val,
                    "bucket": "proven",
                    "source": {"path": rel, "sha256": sha, "line": hit_g1[0]},
                }
        if "governance_release_gate" not in gates:
            hit_rel = _find_line(lines, "release_gate=BLOCK_RELEASE")
            if hit_rel:
                gates["release_gate"] = {
                    "gate": "release_gate",
                    "status": "BLOCK_RELEASE",
                    "bucket": "identity",
                    "source": {"path": rel, "sha256": sha, "line": hit_rel[0]},
                }
        if "oaie_established" not in gates:
            hit_oaie = _find_line(lines, "oaie_established=False")
            if hit_oaie:
                gates["oaie_established"] = {
                    "gate": "oaie_established",
                    "status": "False",
                    "bucket": "unproven",
                    "source": {"path": rel, "sha256": sha, "line": hit_oaie[0]},
                }
    if "G1" not in gates:
        peta = root / "handover" / "PETA_ARAH_SERIBU_TAHUN.md"
        if peta.is_file():
            plines = peta.read_text(encoding="utf-8").splitlines()
            hit_g1 = _find_line(plines, "G1 DEMONSTRATED")
            if hit_g1:
                gates["G1"] = {
                    "gate": "G1",
                    "status": "DEMONSTRATED",
                    "bucket": "proven",
                    "source": {"path": _rel_or_posix(peta, root), "sha256": _sha256_file(peta), "line": hit_g1[0]},
                }

    order = {"G1": 1, "G2": 2, "G3": 3, "G4": 4, "G5": 5, "round2-gate-01": 6, "oaie_established": 7, "governance_release_gate": 8, "release_gate": 8}
    return sorted(gates.values(), key=lambda g: (order.get(g["gate"], 99), g["gate"]))


def _collect_latest_verdicts(root: Path) -> list[dict[str, Any]]:
    verdicts: list[dict[str, Any]] = []
    handover_dir = root / "handover"
    if handover_dir.is_dir():
        for p in sorted(handover_dir.glob("*VERDICT*.md")):
            lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
            sha = _sha256_file(p)
            rel = _rel_or_posix(p, root)
            hit = _find_line(
                lines,
                re.compile(r"(VERDICT|TAHAN|ADOPTED|PASS|NOT_SUSCEPTIBLE|GO|HOLD|FAIL)", re.IGNORECASE),
            )
            title = lines[0].lstrip("# ").strip() if lines else p.stem
            if hit:
                verdicts.append(
                    {
                        "subject": title[:90],
                        "verdict_excerpt": hit[1][:140],
                        "source": {"path": rel, "sha256": sha, "line": hit[0]},
                    }
                )

    for p in (
        root / "docs" / "research" / "ACE_OMEGA_CHECKPOINT_20261113_ADDENDUM60.md",
        root / "docs" / "research" / "ACE_OMEGA_CHECKPOINT_20261113_ADDENDUM59.md",
        root / "docs" / "ACE_SELFMODEL_RESULTS_V1.md",
    ):
        if not p.is_file():
            continue
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        sha = _sha256_file(p)
        rel = _rel_or_posix(p, root)
        hit = _find_line(
            lines,
            re.compile(r"(LIFT_DEMONSTRATED|NOT_DEMONSTRATED|SCIENTIFIC_CAPABILITY_VALIDATED)", re.IGNORECASE),
        )
        title = lines[0].lstrip("# ").strip() if lines else p.stem
        if hit:
            verdicts.append(
                {
                    "subject": title[:90],
                    "verdict_excerpt": hit[1][:140],
                    "source": {"path": rel, "sha256": sha, "line": hit[0]},
                }
            )
    return verdicts


def _collect_queue(root: Path, queue_files: list[Path] | None = None) -> list[dict[str, Any]]:
    queue: list[dict[str, Any]] = []

    next_act = root / "NEXT_ACTION.md"
    if next_act.is_file():
        lines = next_act.read_text(encoding="utf-8", errors="replace").splitlines()
        hit = _find_line(lines, re.compile(r"W[0-5]|STATUS\.md"))
        queue.append(
            {
                "item_id": "repo_next_action",
                "title": "Arah antrean aktif merujuk STATUS.md",
                "status": "ACTIVE_POINTER",
                "detail": hit[1][:120] if hit else "Lihat STATUS.md",
                "source": {"path": _rel_or_posix(next_act, root), "sha256": _sha256_file(next_act), "line": hit[0] if hit else 1},
            }
        )

    add58 = root / "docs" / "research" / "ACE_OMEGA_CHECKPOINT_20261112_ADDENDUM58.md"
    if add58.is_file():
        lines = add58.read_text(encoding="utf-8", errors="replace").splitlines()
        hit = _find_line(lines, "G5: NOT_ASSESSED")
        if hit:
            queue.append(
                {
                    "item_id": "g5_harvest_cutoff",
                    "title": "Penilaian gerbang G5 (menunggu cutoff praregistrasi periode panen)",
                    "status": "PENDING_ASSESSMENT",
                    "detail": hit[1],
                    "source": {"path": _rel_or_posix(add58, root), "sha256": _sha256_file(add58), "line": hit[0]},
                }
            )

    kbm_path = root / "handover" / "KBM_SERIALISASI_STATE.md"
    if kbm_path.is_file():
        lines = kbm_path.read_text(encoding="utf-8", errors="replace").splitlines()
        sha = _sha256_file(kbm_path)
        rel = _rel_or_posix(kbm_path, root)
        queued = [ln.strip() for ln in lines if ln.strip().startswith("- Bab ")][:4]
        queue.append(
            {
                "item_id": "kbm_serialization_queue",
                "title": f"Antrean serialisasi KBM ({len(queued)} entri terdekat)",
                "status": "ACTIVE",
                "detail": "; ".join(queued) if queued else "Berkas state KBM terbaca.",
                "source": {"path": rel, "sha256": sha, "line": 1},
            }
        )
    else:
        queue.append(
            {
                "item_id": "kbm_serialization_queue",
                "title": "Antrean serialisasi KBM",
                "status": "SOURCE_NOT_PRESENT",
                "detail": "handover/KBM_SERIALISASI_STATE.md tidak ada di checkout ini; status tidak ditebak.",
                "source": {"path": "tools/dashboard_state_build.py", "sha256": _sha256_file(root / "tools" / "dashboard_state_build.py"), "line": 42}
                if (root / "tools" / "dashboard_state_build.py").is_file()
                else None,
            }
        )

    for qf in queue_files or []:
        if not qf.is_file():
            continue
        rel = _rel_or_posix(qf, root)
        sha = _sha256_file(qf)
        for line_no, raw in enumerate(qf.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
            s = raw.strip()
            if s.startswith("- ") or s.startswith("* "):
                queue.append(
                    {
                        "item_id": f"custom_queue_{line_no}",
                        "title": s[2:].strip()[:120],
                        "status": "QUEUED",
                        "detail": s[2:].strip(),
                        "source": {"path": rel, "sha256": sha, "line": line_no},
                    }
                )
    return queue


def _collect_named_evidence_debt(
    root: Path,
    mem_counts: dict[str, Any],
    ledger_paths: list[Path] | None = None,
) -> list[dict[str, Any]]:
    debt: list[dict[str, Any]] = []

    add59 = root / "docs" / "research" / "ACE_OMEGA_CHECKPOINT_20261113_ADDENDUM59.md"
    if add59.is_file():
        lines = add59.read_text(encoding="utf-8").splitlines()
        hit = _find_line(lines, "G2 board: MEASURED — NOT_DEMONSTRATED") or _find_line(lines, "NOT_DEMONSTRATED")
        if hit:
            debt.append(
                {
                    "debt_id": "DEBT_G2_NOT_DEMONSTRATED",
                    "severity": "HIGH",
                    "title": "Gerbang G2 masih NOT_DEMONSTRATED (3 bentuk hasil nol, terakhir abc_v3 DI=-1.98pp)",
                    "missing_evidence": "Rancangan diferensiasi baru tanpa regresi kontrol pada band bersih.",
                    "source": {"path": _rel_or_posix(add59, root), "sha256": _sha256_file(add59), "line": hit[0]},
                }
            )

    add58 = root / "docs" / "research" / "ACE_OMEGA_CHECKPOINT_20261112_ADDENDUM58.md"
    if add58.is_file():
        lines = add58.read_text(encoding="utf-8").splitlines()
        sha = _sha256_file(add58)
        rel = _rel_or_posix(add58, root)
        hit_g5 = _find_line(lines, "G5: NOT_ASSESSED")
        if hit_g5:
            debt.append(
                {
                    "debt_id": "DEBT_G5_NOT_ASSESSED",
                    "severity": "HIGH",
                    "title": "Gerbang G5 berstatus NOT_ASSESSED",
                    "missing_evidence": "Evaluasi panen setelah penutupan periode praregistrasi.",
                    "source": {"path": rel, "sha256": sha, "line": hit_g5[0]},
                }
            )
        hit_g4_lim = _find_line(lines, "never kernel-submitted") or _find_line(lines, "dossier-integrity audit")
        if hit_g4_lim:
            debt.append(
                {
                    "debt_id": "DEBT_G4_DRAFT_ONLY_PREREG",
                    "severity": "MEDIUM",
                    "title": "Batas baca G4: praregistrasi berupa draf terkunci hash (belum disubmit ke kernel)",
                    "missing_evidence": "Audit kernel penuh atas eksekusi G4 terpraregistrasi.",
                    "source": {"path": rel, "sha256": sha, "line": hit_g4_lim[0]},
                }
            )

    status_md = root / "STATUS.md"
    if status_md.is_file():
        lines = status_md.read_text(encoding="utf-8").splitlines()
        hit = _find_line(lines, "oaie_established=False")
        if hit:
            debt.append(
                {
                    "debt_id": "DEBT_OAIE_AND_SCIENTIFIC_SEAL",
                    "severity": "HIGH",
                    "title": "oaie_established=False dan scientific_status=NOT_ASSESSED",
                    "missing_evidence": "Penilaian eksternal tersegel atas seluruh klaim evolusi terbuka.",
                    "source": {"path": _rel_or_posix(status_md, root), "sha256": _sha256_file(status_md), "line": hit[0]},
                }
            )

    if mem_counts.get("present") and mem_counts.get("path") and mem_counts.get("sha256"):
        if int(mem_counts.get("evidence_count") or 0) == 0:
            debt.append(
                {
                    "debt_id": "DEBT_MEMORY_ZERO_EVIDENCE_RECORDS",
                    "severity": "MEDIUM",
                    "title": "Snapshot memori belum memuat record bersumber `evidence`",
                    "missing_evidence": "Rekaman peristiwa terverifikasi dengan digest artefak terjangkar.",
                    "source": {"path": mem_counts["path"], "sha256": mem_counts["sha256"]},
                }
            )
        if int(mem_counts.get("model_guess_count") or 0) > 0:
            debt.append(
                {
                    "debt_id": "DEBT_MEMORY_UNVERIFIED_GUESSES",
                    "severity": "LOW",
                    "title": f"{mem_counts['model_guess_count']} rekaman memori masih berstatus tebakan `model`",
                    "missing_evidence": "Verifikasi bukti atau ratifikasi atas klaim tebakan model.",
                    "source": {"path": mem_counts["path"], "sha256": mem_counts["sha256"]},
                }
            )
        if mem_counts.get("chain_ok") is False:
            debt.append(
                {
                    "debt_id": "DEBT_MEMORY_CHAIN_BROKEN",
                    "severity": "CRITICAL",
                    "title": "Rantai hash log memori gagal verifikasi",
                    "missing_evidence": "Audit integritas log hash-chained dan pemulihan checkpoint bersih.",
                    "source": {"path": mem_counts["path"], "sha256": mem_counts["sha256"]},
                }
            )

    for lp in ledger_paths or []:
        if not lp.is_file():
            continue
        lines = lp.read_text(encoding="utf-8", errors="replace").splitlines()
        hit_rp = _find_line(lines, re.compile(r"Rp\s*0\b"))
        if hit_rp:
            debt.append(
                {
                    "debt_id": "DEBT_REVENUE_BASELINE_RP0",
                    "severity": "MEDIUM",
                    "title": "Penghasilan tunai terverifikasi masih Rp 0",
                    "missing_evidence": "Bukti transaksi rail terverifikasi pada ledger tunggal.",
                    "source": {"path": _rel_or_posix(lp, root), "sha256": _sha256_file(lp), "line": hit_rp[0]},
                }
            )

    return debt


def build_periodic_self_report(
    root: str | Path,
    *,
    memory_path: str | Path | None = None,
    narrative_json_path: str | Path | None = None,
    queue_files: list[str | Path] | None = None,
    ledger_paths: list[str | Path] | None = None,
) -> dict[str, Any]:
    """Bangun laporan-diri berkala pemilik dari sumber-sumber model-diri secara read-only."""
    repo_root = Path(root).resolve()
    narrative_model: dict[str, Any] | None = None
    if narrative_json_path is not None:
        npath = Path(narrative_json_path)
        if npath.is_file():
            narrative_model = json.loads(npath.read_text(encoding="utf-8"))

    mem_resolved = Path(memory_path).resolve() if memory_path is not None else None
    mem_counts = _read_memory_counts_readonly(mem_resolved, repo_root)

    gates = _collect_gates(repo_root, narrative_model)
    verdicts = _collect_latest_verdicts(repo_root)
    queue = _collect_queue(repo_root, [Path(q).resolve() for q in (queue_files or [])])
    debts = _collect_named_evidence_debt(
        repo_root,
        mem_counts,
        [Path(lp).resolve() for lp in (ledger_paths or [])],
    )

    return {
        "schema": SCHEMA,
        "read_only": True,
        "root": repo_root.as_posix(),
        "memory_overview": mem_counts,
        "gates": gates,
        "latest_verdicts": verdicts,
        "queue": queue,
        "named_evidence_debt": debts,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Laporan-Diri Berkala ACE Ω (C5)",
        "",
        f"- **Skema**: `{report['schema']}` (`read_only={report['read_only']}`)",
        f"- **Ringkasan Memori**: `present={report['memory_overview']['present']}`, "
        f"`evidence={report['memory_overview']['evidence_count']}`, "
        f"`operator={report['memory_overview']['operator_count']}`, "
        f"`model_guess={report['memory_overview']['model_guess_count']}`",
        "",
        "## 1. Papan Gerbang",
        "",
        "| Gerbang | Status | Kategori | Sumber |",
        "| --- | --- | --- | --- |",
    ]
    for g in report["gates"]:
        src = g.get("source") or {}
        cite = f"`{src.get('path', '?')}`" + (f"#L{src['line']}" if src.get("line") else "")
        lines.append(f"| **{g['gate']}** | {g['status']} | `{g['bucket']}` | {cite} |")

    lines.extend(["", "## 2. Vonis Terbaru", ""])
    if not report["latest_verdicts"]:
        lines.append("- _(Tidak ada berkas vonis ditemukan.)_")
    else:
        for v in report["latest_verdicts"]:
            s = v["source"]
            lines.append(f"- **{v['subject']}**: `{v['verdict_excerpt']}` (`{s['path']}#L{s['line']}`)")

    lines.extend(["", "## 3. Antrean Aktif", ""])
    for q in report["queue"]:
        src = q.get("source")
        cite = f" (`{src['path']}#L{src.get('line', 1)}`)" if src else ""
        lines.append(f"- **[{q['status']}] {q['title']}**: {q['detail']}{cite}")

    lines.extend(["", "## 4. Utang Bukti Bernama", ""])
    if not report["named_evidence_debt"]:
        lines.append("- _(Tidak ada utang bukti terbuka.)_")
    else:
        for d in report["named_evidence_debt"]:
            s = d["source"]
            loc = f"{s['path']}#L{s['line']}" if s.get("line") else s["path"]
            lines.append(
                f"- **[{d['severity']}] `{d['debt_id']}`** — {d['title']} "
                f"(butuh: {d['missing_evidence']}; sumber: `{loc}`)"
            )
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Akar repositori ACE")
    parser.add_argument("--memory", default=None, help="Path snapshot memori (baca-saja)")
    parser.add_argument("--narrative-json", default=None, help="Opsional: keluaran JSON dari C1 narrative_self_model.py")
    parser.add_argument("--queue-file", action="append", default=[], help="Opsional: berkas antrean tambahan")
    parser.add_argument("--ledger", action="append", default=[], help="Opsional: berkas ledger pendapatan")
    parser.add_argument("--format", choices=("json", "markdown"), default="markdown")
    parser.add_argument("--out", default=None)
    args = parser.parse_args(argv)

    report = build_periodic_self_report(
        args.root,
        memory_path=args.memory,
        narrative_json_path=args.narrative_json,
        queue_files=args.queue_file,
        ledger_paths=args.ledger,
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
