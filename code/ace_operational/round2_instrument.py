"""Round-2 gate instrument (design: this branch,
docs/research/ACE_ROUND2_GATE_DESIGN_20261113.md).

The gate asks whether the lifted mechanism (frozen
discovery mechanism + statement-motion schema space,
lifted into the core behind the replication guard)
holds its effect on a fresh order-sensitive
universe. This module scores a *dossier* — sealed
evidence files, never self-declared claims —
mechanically and fail-closed, following the G3
instrument's shape:

- C1 — an identified improvement with a measured
  source effect: the dossier names the improvement
  artifact (name + digest, the lift manifest) and
  the source-family report is preregistered
  (protocol hash present), kernel-audited CLEAN,
  identity-matching, and shows a positive effect
  over its named baseline.
- C2 — the same improvement evaluated in >= 2
  distinct families: the target family
  (statement_order) and the stability family
  (grid). Each family report is preregistered,
  audited CLEAN, held out, and its artifact
  identity matches C1's exactly. The same family
  twice is one family.
- C3 — positive lift effect on the target family:
  (improvement score - baseline score) meets the
  margin fixed in that family's own preregistered
  report (``margin_pp``, read from the dossier's
  evidence, never hardcoded here). For the target
  family the driver encodes the preregistered
  H1 bar (arm B >= 80% of shown-discriminating
  tasks) as margin_pp = 80 - baseline_score, so
  the check reads improvement - baseline >=
  margin, i.e. arm B >= 80%.
- Stability — the grid family must not regress:
  improvement score >= baseline score (its
  report carries margin_pp = 0). A regression
  is a named failure of its own, never folded
  into C3's count.

Identity discipline is a HARD fence: any
name/digest mismatch in any report forces
NOT_DEMONSTRATED with the mismatch named (which
family, which digests), however the other
families score.

Outcome vocabulary (the design's section 5,
exactly): LIFT_DEMONSTRATED / LIFT_WITH_REGRESSION
/ NOT_DEMONSTRATED.

Dossier schema (the implementation's contract):

    {"improvement": {"name": str, "digest": str},
     "source": {"family": str, "report": <path>},
     "evaluations": [{"family": str, "report": <path>}, ...]}

Report paths are absolute or relative to the
dossier file's directory. Each report:

    {"protocol_hash": str, "audit_status": "CLEAN",
     "improvement_name": str, "improvement_digest": str,
     "held_out": true,
     "baseline_score": number, "improvement_score": number,
     "margin_pp": number}  # scores and margin share units
    # (percentage points in the ratified design)

The source report is also a family evaluation: if
it is held out and carries a margin, the source
family can be one of the two families C2 counts.

This instrument scores dossiers; it assembles
none and asserts no round-2 result. The gate
remains unassessed until a dossier is assembled
under preregistration and scored.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CRITERIA_VERSION = 1
FAMILIES = ("statement_order", "grid")
TARGET_FAMILY = "statement_order"
STABILITY_FAMILY = "grid"


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


def assess_round2(*, dossier: str | Path | None) -> dict[str, Any]:
    """Score a round-2 gate dossier file against clauses
    C1-C3 plus the stability check. Every clause lists,
    on failure, the exact missing or failed items. The
    outcome object always carries the criteria version."""
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

    # ---- C3: positive lift effect on the target family ----------
    c3_rejected: list[str] = []
    target_ok = False
    target_report = family_records.get(TARGET_FAMILY)
    if target_report is None:
        c3_rejected.append(
            f"{TARGET_FAMILY}: no valid family evaluation")
    else:
        base, score = target_report.get("baseline_score"), \
            target_report.get("improvement_score")
        margin = target_report.get("margin_pp")
        if not _number(base) or not _number(score):
            c3_rejected.append(f"{TARGET_FAMILY}: scores are not numeric")
        elif not _number(margin):
            c3_rejected.append(
                f"{TARGET_FAMILY}: no preregistered margin_pp in the "
                f"family report — the effect cannot be counted")
        elif score - base >= margin:
            target_ok = True
    c3_missing = []
    if not target_ok:
        c3_missing.append(
            f"positive lift effect not shown on {TARGET_FAMILY}")
    clauses["C3_positive_lift_effect"] = {
        "verdict": "PASS" if target_ok else "FAIL",
        "missing": c3_missing,
        "warnings": c3_rejected,
        "evidence": {"target_family": TARGET_FAMILY,
                     "effect_shown": target_ok}}

    # ---- stability: the grid family must not regress ------------
    stab_missing: list[str] = []
    stab_ok = False
    stab_report = family_records.get(STABILITY_FAMILY)
    if stab_report is None:
        stab_missing.append(
            f"{STABILITY_FAMILY}: no valid family evaluation")
    else:
        base, score = stab_report.get("baseline_score"), \
            stab_report.get("improvement_score")
        if not _number(base) or not _number(score):
            stab_missing.append(f"{STABILITY_FAMILY}: scores are not numeric")
        elif score < base:
            stab_missing.append(
                f"{STABILITY_FAMILY}: regression "
                f"({score} < {base}) — the lift degrades the "
                f"frozen mechanism's grid effect")
        else:
            stab_ok = True
    clauses["stability_no_regression"] = {
        "verdict": "PASS" if stab_ok else "FAIL",
        "missing": stab_missing,
        "evidence": {"stability_family": STABILITY_FAMILY,
                     "regression_free": stab_ok}}

    # ---- outcome (single construction point) --------------------
    c1_pass = clauses["C1_identified_improvement"]["verdict"] == "PASS"
    c2_pass = clauses["C2_two_distinct_families"]["verdict"] == "PASS"
    c3_pass = clauses["C3_positive_lift_effect"]["verdict"] == "PASS"
    if mismatches:
        overall = "NOT_DEMONSTRATED"
        qualification = ("Identity fence: at least one report's artifact "
                         "identity differs from the dossier's declared "
                         "improvement; a re-authored or retuned artifact "
                         "is a new improvement, not a lift.")
    elif c1_pass and c2_pass and c3_pass and stab_ok:
        overall = "LIFT_DEMONSTRATED"
        qualification = ("none — the lifted mechanism shows a positive "
                         "audited effect on the target family with no "
                         "regression on the stability family.")
    elif c1_pass and c2_pass and c3_pass and not stab_ok:
        overall = "LIFT_WITH_REGRESSION"
        qualification = ("The target effect is shown, but the stability "
                         "family regressed — the lift is unsafe as a "
                         "core change whatever its target effect.")
    else:
        overall = "NOT_DEMONSTRATED"
        qualification = ("One or more clauses failed; see the named "
                         "missing items.")
    return {
        "gate": "ROUND2",
        "criteria_version": CRITERIA_VERSION,
        "definition": ("a core lift holds its effect on a fresh "
                       "order-sensitive universe without regressing "
                       "the frozen mechanism's home family"),
        "clauses": clauses,
        "identity_mismatches": mismatches,
        "overall": overall,
        "qualification": qualification,
    }
