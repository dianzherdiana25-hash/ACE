"""G1 measurement instrument (Phase 2, stage H).

PRD v0.1 defines G1 — Operasional: "menjalankan satu eksperimen
digital dari tugas sampai laporan dengan catatan lengkap dan
kemampuan melanjutkan setelah terputus" (run one digital experiment
from task to report, with complete records, and the ability to
resume after interruption).

Until now G1 sat at NOT_ASSESSED for one stated reason: no agreed
instrument existed. This module is that instrument. It scores a
*dossier* — paths to sealed evidence files, never self-declared
claims — against the definition's three clauses, mechanically and
fail-closed (a missing or unparseable item is a named failure,
never a default pass):

- C1 task→report arc: a preregistration record exists for the
  flagship experiment, a report artifact exists, and a kernel audit
  was performed.
- C2 complete records: the audit is CLEAN, its hash chain has no
  break, and at least one recorded result was verified.
- C3 resume after interruption: a probe on the same store
  machinery shows state created in one OS process, advanced in a
  second, and verified in a third (or an equivalent multi-process
  record), with a PASS verdict.

Stated limitation, part of the instrument's design: C3's probe
demonstrates the resume capability of the substrate the flagship
experiment ran on; it is not an interruption of the flagship run
itself. The instrument therefore distinguishes DEMONSTRATED (all
clauses pass on linked evidence) from an unqualified pass, which
requires the closing experiment named in the design document: a
deliberate mid-run interruption of a flagship run, resumed to
completion.

Criteria v2 (stage J amendment, recorded in Addendum 32): C3 now
recognises two evidence species. Species "substrate_probe" is the
v1 record shape, unchanged. Species "flagship_interruption" is
the closing experiment this docstring always named: a record of
an interruption of the assessed operation itself, carrying an
``interruption`` block that evidences a mid-work kill, state
integrity verified after the kill, resumption by a separate
process, completion to the operation's final report, and record
continuity across the interruption. Only the flagship species
lifts the qualification; the probe species keeps it. The v1
instrument scored the drill record NOT_DEMONSTRATED purely on
vocabulary (verdict string, checkpoint field names) — the same
class of mis-specification the OMEGA-10 amendment corrected:
criteria must encode the PRD clause, not one record's field
names.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _load(path: str | Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def assess_g1(*, experiment_report: str | Path | None,
              resume_probe: str | Path | None) -> dict[str, Any]:
    """Score the G1 dossier. Every clause lists its evidence and,
    on failure, the exact missing items."""
    clauses: dict[str, Any] = {}
    report = _load(experiment_report)

    # C1 — task to report arc.
    missing: list[str] = []
    if report is None:
        missing.append("experiment report file missing/unparseable")
        audit = None
    else:
        if not report.get("protocol_hash"):
            missing.append("no preregistration protocol_hash in report")
        audit = report.get("audit")
        if not isinstance(audit, dict):
            missing.append("no kernel audit in report")
    clauses["C1_task_to_report"] = {
        "verdict": "PASS" if not missing else "FAIL",
        "missing": missing,
        "evidence": ({"experiment": report.get("experiment"),
                      "protocol_hash": report.get("protocol_hash")}
                     if report else None)}

    # C2 — complete records.
    missing = []
    if not isinstance(audit, dict):
        missing.append("audit unavailable (see C1)")
    else:
        if audit.get("status") != "CLEAN":
            missing.append(f"audit status is {audit.get('status')!r}")
        if audit.get("chain_break_at") is not None:
            missing.append("audit hash chain has a break")
        if not audit.get("results_verified"):
            missing.append("no verified results in audit")
        if audit.get("problems"):
            missing.append(f"audit problems: {audit['problems']}")
    clauses["C2_complete_records"] = {
        "verdict": "PASS" if not missing else "FAIL",
        "missing": missing,
        "evidence": ({"audit_status": audit.get("status"),
                      "results_verified": audit.get("results_verified"),
                      "ledger_entries_verified":
                          audit.get("ledger_entries_verified")}
                     if isinstance(audit, dict) else None)}

    # C3 — resume after interruption.
    probe = _load(resume_probe)
    missing = []
    species = None
    if probe is None:
        missing.append("resume evidence file missing/unparseable")
    elif isinstance(probe.get("interruption"), dict):
        species = "flagship_interruption"
        block = probe["interruption"]
        if probe.get("verdict") not in ("PASS", "RESUME_DRILL_PASS"):
            missing.append(
                f"drill verdict is {probe.get('verdict')!r}")
        for field in ("killed_mid_work", "state_integrity_after",
                      "resumed_by_separate_process",
                      "final_report_reached", "record_continuity"):
            if block.get(field) is not True:
                missing.append(
                    f"interruption block does not evidence {field}")
    else:
        species = "substrate_probe"
        if probe.get("verdict") != "PASS":
            missing.append(f"probe verdict is {probe.get('verdict')!r}")
        method = str(probe.get("method", ""))
        if "separate OS processes" not in method and \
                "process" not in method:
            missing.append("probe method does not evidence separate "
                           "processes")
        phases = probe.get("event_phases") or []
        if len(phases) < 2:
            missing.append("probe shows no state advancement across "
                           "the restart (event_phases < 2)")
        checkpoint = probe.get("checkpoint") or {}
        if not checkpoint.get("step"):
            missing.append("probe checkpoint carries no step state")
    clauses["C3_resume_after_interruption"] = {
        "verdict": "PASS" if not missing else "FAIL",
        "missing": missing,
        "evidence": ({"species": species,
                      "experiment": probe.get("experiment"),
                      "package": probe.get("package"),
                      "subject": probe.get("subject"),
                      "task_status": probe.get("task_status")}
                     if probe else None)}

    demonstrated = all(c["verdict"] == "PASS" for c in clauses.values())
    if not demonstrated:
        qualification = ("One or more clauses failed; see the named "
                         "missing items.")
    elif species == "flagship_interruption":
        qualification = (
            "none — C3 is satisfied by a deliberate interruption of "
            "the flagship operation itself, resumed by a separate "
            "process to its final report with record continuity "
            "verified (criteria v2).")
    else:
        qualification = (
            "C3 evidences the resume capability of the substrate the "
            "flagship experiment ran on, not an interruption of the "
            "flagship run itself; an unqualified pass requires the "
            "closing resume drill named in the design document.")
    return {
        "gate": "G1",
        "criteria_version": 2,
        "definition": ("run one digital experiment from task to "
                       "report with complete records and the ability "
                       "to resume after interruption (PRD v0.1)"),
        "clauses": clauses,
        "overall": "DEMONSTRATED" if demonstrated else "NOT_DEMONSTRATED",
        "qualification": qualification,
    }
