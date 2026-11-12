"""G3 measurement instrument (design: PR #135,
docs/research/ACE_G3_INSTRUMENT_DESIGN_20261112.md).

PRD v0.1 defines G3 — Generalisasi: does an improvement
transfer to at least two different problem families?
Improvement confined to one family is recorded as
*specialization*.

This module is the instrument the design specifies. It
scores a *dossier* — sealed evidence files, never
self-declared claims — mechanically and fail-closed (a
missing or unparseable item is a named failure, never a
default pass), following the G1 instrument's shape:

- C1 — an identified improvement with a measured source
  effect: the dossier names the improvement artifact
  (name + digest) and the source-family report is
  preregistered (protocol hash present), kernel-audited
  CLEAN, identity-matching, and shows a positive effect
  over its named baseline.
- C2 — the same improvement evaluated in >= 2 distinct
  families: each family report is preregistered, audited
  CLEAN, held out from the improvement's development, and
  its artifact identity (name + digest) matches C1's
  exactly. Families are the design's three: pricing,
  shipping, grid (generators/mechanisms per the design's
  section 2); the same family twice is one family.
- C3 — positive transfer effect in >= 2 families: per
  family, (improvement score - baseline score) meets the
  margin fixed in that family's own preregistered report
  (``margin_pp``, read from the dossier's evidence, never
  hardcoded here), counting only C2-valid families.

Identity discipline is the reward-hacking guard, and it
is a HARD fence: any name/digest mismatch in any report
forces NOT_DEMONSTRATED with the mismatch named (which
family, which digests), however the other families score.

Outcome vocabulary (the design's section 4, exactly):
TRANSFER_DEMONSTRATED / SPECIALIZATION / NOT_DEMONSTRATED.

Dossier schema (the implementation's contract, per the
design's section 7 — a future application assembles its
dossier to this schema):

    {"improvement": {"name": str, "digest": str},
     "source": {"family": str, "report": <path>},
     "evaluations": [{"family": str, "report": <path>}, ...]}

Report paths are absolute or relative to the dossier
file's directory. Each report:

    {"protocol_hash": str, "audit_status": "CLEAN",
     "improvement_name": str, "improvement_digest": str,
     "held_out": true,
     "baseline_score": number, "improvement_score": number,
     "margin_pp": number}  # scores and margin share units
    # (percentage points in the ratified application design)

The source report is also a family evaluation: if it is
held out and carries a margin, the source family can be
one of the two families C3 counts.

This instrument scores dossiers; it assembles none and
asserts no G3 result. G3 remains NOT_ASSESSED until a
dossier is assembled under preregistration and scored.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CRITERIA_VERSION = 1
FAMILIES = ("pricing", "shipping", "grid")


def _load(path: str | Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _resolve(dossier_dir: Path, ref: Any) -> Path | None:
    if not isinstance(ref, str) or not ref:
        return None
    path = Path(ref)
    return path if path.is_absolute() else dossier_dir / path


def _check_report(report: dict[str, Any], *, label: str,
                  improvement: dict[str, Any],
                  mismatches: list[str]) -> list[str]:
    """Shared per-report checks: preregistration, audit,
    identity. Returns named problems; identity mismatches
    are additionally recorded in ``mismatches`` (hard fence)."""
    problems: list[str] = []
    if not report.get("protocol_hash"):
        problems.append(f"{label}: no preregistration protocol_hash")
    if report.get("audit_status") != "CLEAN":
        problems.append(
            f"{label}: kernel audit status is "
            f"{report.get('audit_status')!r}, not 'CLEAN'")
    name = report.get("improvement_name")
    digest = report.get("improvement_digest")
    if name != improvement.get("name") or digest != improvement.get("digest"):
        mismatches.append(
            f"{label}: artifact identity mismatch — dossier declares "
            f"{improvement.get('name')!r} / {improvement.get('digest')!r}, "
            f"report carries {name!r} / {digest!r}")
        problems.append(f"{label}: artifact identity mismatch (see "
                        f"identity_mismatches)")
    return problems


def assess_g3(*, dossier: str | Path | None) -> dict[str, Any]:
    """Score a G3 dossier file against clauses C1-C3.
    Every clause lists, on failure, the exact missing or
    failed items. The outcome object always carries the
    criteria version."""
    dossier_path = Path(dossier) if dossier is not None else None
    dossier_data = _load(dossier_path)
    dossier_dir = dossier_path.parent if dossier_path else Path(".")

    clauses: dict[str, Any] = {}
    mismatches: list[str] = []
    improvement = (dossier_data or {}).get("improvement")
    if not isinstance(improvement, dict):
        improvement = {}

    # ---- load all reports (fail-closed) -------------------------
    def load_entry(entry: Any, label: str) -> tuple[str | None, dict | None]:
        if not isinstance(entry, dict):
            return None, None
        family = entry.get("family")
        path = _resolve(dossier_dir, entry.get("report"))
        return family, (_load(path) if path is not None else None)

    source_entry = (dossier_data or {}).get("source")
    source_family, source_report = load_entry(source_entry, "source")
    evaluations = (dossier_data or {}).get("evaluations")
    eval_entries: list[tuple[str | None, dict | None]] = []
    if isinstance(evaluations, list):
        for i, entry in enumerate(evaluations):
            eval_entries.append(load_entry(entry, f"evaluation {i}"))

    # ---- C1: identified improvement, measured source effect -----
    missing: list[str] = []
    if dossier_data is None:
        missing.append("dossier file missing/unparseable")
    if not improvement.get("name"):
        missing.append("improvement artifact has no name")
    if not improvement.get("digest"):
        missing.append("improvement artifact has no digest")
    source_check: list[str] = []
    if source_report is None:
        missing.append("source report file missing/unparseable")
    else:
        source_check = _check_report(source_report,
                                     label="source report",
                                     improvement=improvement,
                                     mismatches=mismatches)
        missing += source_check
        base, score = source_report.get("baseline_score"), \
            source_report.get("improvement_score")
        if not _number(base) or not _number(score):
            missing.append("source report scores are not numeric")
        elif score <= base:
            missing.append(
                f"source effect is not positive ({score} <= {base})")
    clauses["C1_identified_improvement"] = {
        "verdict": "PASS" if not missing else "FAIL",
        "missing": missing,
        "evidence": ({"improvement": improvement,
                      "source_family": source_family}
                     if dossier_data else None)}

    # ---- per-family evaluation validity (shared by C2/C3) -------
    family_records: dict[str, dict[str, Any]] = {}
    c2_rejected: list[str] = []
    all_entries = [(source_family, source_report, "source report",
                    source_check)] + \
        [(fam, rep, f"evaluation ({fam})", None)
         for fam, rep in eval_entries]
    for family, report, label, prechecked in all_entries:
        if report is None:
            c2_rejected.append(f"{label}: report file missing/unparseable")
            continue
        if family not in FAMILIES:
            c2_rejected.append(f"{label}: family {family!r} is not one of "
                               f"the design's families {list(FAMILIES)}")
            continue
        problems = prechecked if prechecked is not None else \
            _check_report(report, label=label,
                          improvement=improvement,
                          mismatches=mismatches)
        if report.get("held_out") is not True:
            problems.append(f"{label}: tasks not attested held out")
        if problems:
            c2_rejected += problems
            continue
        if family in family_records:
            c2_rejected.append(
                f"{label}: family {family!r} evaluated twice — the same "
                f"family twice is one family")
            continue
        family_records[family] = report

    # ---- C2: same improvement in >= 2 distinct families ---------
    # Entry-level problems are named WARNINGS (the
    # "warnings" list); the clause verdict turns only on the
    # requirement itself — at least two distinct valid
    # families — so a PASS verdict and a non-empty rejection
    # list cohere (verification finding 2, Addendum 42 §2).
    c2_missing = []
    if len(family_records) < 2:
        c2_missing.append(
            f"only {len(family_records)} distinct valid family "
            f"evaluation(s); at least 2 required")
    clauses["C2_two_distinct_families"] = {
        "verdict": "PASS" if not c2_missing else "FAIL",
        "missing": c2_missing,
        "warnings": c2_rejected,
        "evidence": {"valid_families": sorted(family_records)}}

    # ---- C3: positive transfer effect in >= 2 families ----------
    c3_rejected: list[str] = []
    positive: list[str] = []
    for family in sorted(family_records):
        report = family_records[family]
        base, score = report.get("baseline_score"), \
            report.get("improvement_score")
        margin = report.get("margin_pp")
        if not _number(base) or not _number(score):
            c3_rejected.append(f"{family}: scores are not numeric")
            continue
        if not _number(margin):
            c3_rejected.append(
                f"{family}: no preregistered margin_pp in the family "
                f"report — the effect cannot be counted")
            continue
        if score - base >= margin:
            positive.append(family)
    c3_missing = []
    if len(positive) < 2:
        c3_missing.append(
            f"positive transfer effect in {len(positive)} famil"
            f"{'y' if len(positive) == 1 else 'ies'}; 2 required for "
            f"TRANSFER_DEMONSTRATED")
    clauses["C3_positive_transfer"] = {
        "verdict": "PASS" if len(positive) >= 2 else "FAIL",
        "missing": c3_missing,
        "warnings": c3_rejected,
        "evidence": {"positive_families": positive}}

    # ---- outcome (single construction point) --------------------
    c1_pass = clauses["C1_identified_improvement"]["verdict"] == "PASS"
    if mismatches:
        overall = "NOT_DEMONSTRATED"
        qualification = ("Identity fence: at least one report's artifact "
                         "identity differs from the dossier's declared "
                         "improvement; a re-authored or retuned artifact "
                         "is a new improvement, not transfer.")
    elif c1_pass and len(positive) >= 2:
        overall = "TRANSFER_DEMONSTRATED"
        qualification = ("none — the same improvement shows a positive "
                         "audited effect in at least two families.")
    elif c1_pass and len(positive) == 1:
        overall = "SPECIALIZATION"
        qualification = ("The improvement is real (C1 passes) and exactly "
                         "one family shows a positive transfer effect — "
                         "the PRD's own category for one-family gains.")
    else:
        overall = "NOT_DEMONSTRATED"
        qualification = ("One or more clauses failed, or no family shows "
                         "a positive transfer effect; see the named "
                         "missing items.")
    return {
        "gate": "G3",
        "criteria_version": CRITERIA_VERSION,
        "definition": ("an improvement transfers to at least two "
                       "different problem families; one family is "
                       "specialization (PRD v0.1)"),
        "clauses": clauses,
        "positive_families": positive,
        "identity_mismatches": mismatches,
        "overall": overall,
        "qualification": qualification,
    }
