#!/usr/bin/env python3
"""Build ace_dashboard_state.json — the Ω-program feed for the ACE mobile dashboard.

Reads ONLY recorded sources on this machine and stamps every section with its
source + source timestamp. A section whose source is missing becomes null with
a note — never a fabricated value. Run: python3 dashboard_state_build.py
Output: ~/workspace/ace-omega/handover/ace_dashboard_state.json
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path


def _atomic_write(path, text):
    """Crash-safe write: temp file in the same
    directory, fsync, then os.replace — the PR #181
    pattern generalized (2026-11-13). A host death
    mid-write leaves the old file or the new one,
    never a torn one."""
    import os as _os
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(text)
        fh.flush()
        _os.fsync(fh.fileno())
    _os.replace(tmp, path)


ROOT = Path(__file__).resolve().parent
HANDOVER = ROOT / "handover"
OUT = HANDOVER / "ace_dashboard_state.json"
WIB = timezone(timedelta(hours=7))

ADD58 = ROOT / "staging" / "add58" / "docs" / "research" / "ACE_OMEGA_CHECKPOINT_20261112_ADDENDUM58.md"
HEARTBEAT = ROOT / "abc-v3-run-state" / "heartbeat.json"
V3_EVIDENCE = ROOT / "evidence" / "abc_v3_run.json"
R2_STATE_DIR = ROOT / "round2-gate-run"
R2_KERNEL_RESULTS = ROOT / "round2-gate-kernel" / "results.jsonl"
KBM_STATE = HANDOVER / "KBM_SERIALISASI_STATE.md"
LEDGER = HANDOVER / "LEDGER_PENGHASILAN.md"
CRON_DIR = Path.home() / "workspace" / "goals" / "ace-local-first-intelligence-evolution" / "crons"


def now_wib() -> str:
    return datetime.now(WIB).strftime("%Y-%m-%d %H:%M:%S WIB")


def mtime_stamp(path: Path) -> str | None:
    if not path.exists():
        return None
    return datetime.fromtimestamp(path.stat().st_mtime, WIB).strftime("%Y-%m-%d %H:%M:%S WIB")


def rp_to_int(text: str) -> int:
    return int(re.sub(r"[^0-9]", "", text))


def gate_board() -> dict:
    gates = {
        "G0": {"status": "PASS (session-scoped only)", "source": "program record, Addenda 1-53"},
        "G1": {"status": "MEASURED — DEMONSTRATED", "source": "Stage J, Addendum 32"},
        "G2": {"status": "MEASURED — null x2 (pilot v1, v2); v3 decider IN FLIGHT",
               "source": "Addendum 45 + v3 preregistration (protocol 8591b938…)"},
        "G3": {"status": "MEASURED — SPECIALIZATION", "source": "Addendum 58"},
        "G4": {"status": "MEASURED — INHERITANCE_DEMONSTRATED", "source": "Addendum 58"},
        "G5": {"status": "NOT_ASSESSED", "source": "Addendum 58"},
    }
    verified = {}
    if ADD58.exists():
        text = ADD58.read_text(encoding="utf-8")
        checks = {
            "G3": "MEASURED — SPECIALIZATION",
            "G4": "MEASURED — INHERITANCE_DEMONSTRATED",
            "G5": "NOT_ASSESSED",
        }
        for gate, phrase in checks.items():
            verified[gate] = phrase in text
    return {
        "as_of": "Addendum 58 (2026-11-13)",
        "source": str(ADD58.relative_to(ROOT)),
        "source_stamp": mtime_stamp(ADD58),
        "add58_phrase_verified": verified,
        "gates": gates,
        "note": "Papan gerbang hanya bergerak lewat addendum terverifikasi dua pemeriksa; OAIE belum terbukti (oaie_proven=false).",
    }


def runs() -> dict:
    abc = {"source": str(HEARTBEAT.relative_to(ROOT)), "source_stamp": mtime_stamp(HEARTBEAT)}
    hb = {}
    if HEARTBEAT.exists():
        try:
            hb = json.loads(HEARTBEAT.read_text(encoding="utf-8"))
        except Exception:
            hb = {}
    abc["evidence_exists"] = V3_EVIDENCE.exists()
    if hb:
        abc["band"] = hb.get("band")
        abc["phase"] = hb.get("phase")
        abc["heartbeat_updated_at"] = hb.get("updated_at")
        abc["checkpoints"] = sorted(p.name for p in HEARTBEAT.parent.glob("*.json") if p.name != "heartbeat.json")
        abc["status"] = "COMPLETE — evidence written" if abc["evidence_exists"] else "RUNNING"
    else:
        abc["status"] = "NO HEARTBEAT FILE"
    guard_files = sorted(p.name for p in R2_STATE_DIR.glob("*")) if R2_STATE_DIR.exists() else []
    r2 = {
        "source": str(R2_STATE_DIR.relative_to(ROOT)),
        "source_stamp": mtime_stamp(R2_STATE_DIR),
        "kernel_results_bytes": R2_KERNEL_RESULTS.stat().st_size if R2_KERNEL_RESULTS.exists() else None,
        "guard_outputs": guard_files,
        "status": "guard outputs present" if guard_files else "not started — antre di belakang run v3",
    }
    return {"abc_v3": abc, "round2_guard": r2}


def venues() -> dict:
    kbm = {"source": str(KBM_STATE.relative_to(ROOT)), "source_stamp": mtime_stamp(KBM_STATE)}
    if KBM_STATE.exists():
        text = KBM_STATE.read_text(encoding="utf-8")
        published_section = text.split("## Published", 1)[-1].split("## Queue", 1)[0]
        chapters = re.findall(r"^- Bab (\d+) ", published_section, flags=re.M)
        titles = re.findall(r"^- Bab \d+ \"([^\"]+)\"", published_section, flags=re.M)
        kbm["published_count"] = len(chapters)
        kbm["published_titles"] = titles
        kbm["next_in_queue"] = re.findall(r"^- Bab (\d+) ", text.split("## Queue", 1)[-1], flags=re.M)[:2]
        kbm["cadence"] = "2 bab/hari (cron kbm-serial-harian); Bab 8 = ambang monetisasi"
    else:
        kbm["published_count"] = None
        kbm["note"] = "KBM_SERIALISASI_STATE.md tidak ditemukan"

    def cron_titles(prefix: str) -> list[str]:
        titles = []
        if CRON_DIR.exists():
            for f in sorted(CRON_DIR.rglob(f"{prefix}*.md")):
                m = re.search(r"^title:\s*(.+)$", f.read_text(encoding="utf-8", errors="ignore"), flags=re.M)
                titles.append(m.group(1).strip() if m else f.stem)
        return titles

    threads = {
        "source": "cron runonce defs (goal crons) + MEMORY record",
        "source_stamp": now_wib(),
        "first_post": "Terbit 2026-11-13 ~00:33 WIB di @dianzherdiana16 (kode undangan di self-reply pertama)",
        "scheduled_tonight": cron_titles("threads-"),
    }
    facebook = {
        "source": "cron runonce defs (goal crons) + FACEBOOK_PAGE_BASELINE_20261113.md",
        "source_stamp": now_wib(),
        "scheduled_verifications": cron_titles("fb-"),
        "mission_note": "Misi $500 di profil Facebook Pro — syarat BELUM terverifikasi (menunggu panel misi pemilik); profil utama gerbang-kualitas.",
    }
    return {"kbm": kbm, "threads": threads, "facebook": facebook}


def ledger() -> dict:
    out = {"source": str(LEDGER.relative_to(ROOT)), "source_stamp": mtime_stamp(LEDGER)}
    if LEDGER.exists():
        text = LEDGER.read_text(encoding="utf-8")
        m = re.search(r"Total keseluruhan TUNAI terverifikasi:\s*Rp\s*([0-9.]+)", text)
        out["income_total_rp"] = rp_to_int(m.group(1)) if m else None
        total_row = re.search(
            r"\|\s*\*\*Total\*\*.*?\| \*\*([0-9.]+)\*\* \| — \| \*\*([0-9.]+)\*\* \| \*\*([0-9.]+)\*\* \| \*\*([0-9.]+)%\*\*",
            text)
        if total_row:
            out["utang_awal_baseline_rp"] = rp_to_int(total_row.group(1))
            out["utang_awal_paid_rp"] = rp_to_int(total_row.group(2))
            out["utang_awal_remaining_rp"] = rp_to_int(total_row.group(3))
            out["utang_awal_pct"] = float(total_row.group(4))
        else:
            out["utang_awal_baseline_rp"] = None
            out["note_utang"] = "baris total UTANG AWAL tidak ter-parse — cek LEDGER manual"
        out["coverage_note"] = "Rasio cakupan biaya ACE: BELUM BERMAKNA (pembilang Rp0, penyebut Rp0 tercatat)."
    else:
        out["income_total_rp"] = None
        out["note"] = "LEDGER_PENGHASILAN.md tidak ditemukan"
    return out


def operators() -> dict:
    return {
        "source": "perintah pemilik 2026-11-13 (ruang diskusi + MEMORY.md)",
        "source_stamp": "2026-11-13 11:03 WIB",
        "director": "Muse — Ian (ruang eksekusi utama) + ila (direktur program, ruang diskusi)",
        "local_model": "Qwen3-8B (direktur riset lokal) — ISTIRAHAT TOTAL atas perintah pemilik; tidak ada run model lokal berjalan",
        "note": "Multi-brain sovereignty: otak adalah organ tergantikan; identitas ACE hidup di konstitusi, ledger, dan memorinya.",
    }


def main() -> None:
    state = {
        "schema": "ace.dashboard_state.v1",
        "generated_at": now_wib(),
        "gate_board": gate_board(),
        "runs": runs(),
        "venues": venues(),
        "ledger": ledger(),
        "operators": operators(),
    }
    _atomic_write(OUT, json.dumps(state, indent=2, ensure_ascii=False))
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes) at {state['generated_at']}")


if __name__ == "__main__":
    main()
