"""A/B/C v3 measurement instrument (design: PR #147,
docs/research/ACE_ABC_V3_DESIGN_20261113.md; decision
rule fixed in the preregistration draft
ACE_ABC_V3_PREREGISTRATION_DRAFT_20261113.md §4).

This module is the instrument the draft specifies. It
scores a *run report* — per-arm solve rates and the
two run-condition flags, never self-declared claims —
mechanically and fail-closed (a missing or malformed
field is a named failure, never a default pass),
following the G3 instrument's shape:

- Report validity — the report carries arms A/B/C and
  control A/B/C as percentages in [0, 100], and the
  flags calibration_gate_passed / complete as real
  booleans. Anything missing, non-numeric, out of
  range, or non-boolean is a named failure.
- Calibration gate — the draft's anti-saturation gate
  reads on the POOLED denominator (evaluation +
  control), arm A strictly between 10% and 90%. If
  the gate fails on a run band's own calibration
  re-check, the outcome is SATURATED_BY_DESIGN, never
  a false null.
- Completeness — the run finished every band; a
  partial run is INCONCLUSIVE, never completed
  silently.
- Differentiation index (ONE composite metric, §4):

      DI = min( (C - A) - 15pp , (B - A) - 5pp ,
                control_margin )
      control_margin = min over arms of
          (S3 solve rate of the arm - S3 solve rate
           of arm A), in pp
          (0 if no arm regresses below A; negative
           if any — arm A itself contributes 0)

  DI >= 0 -> DIFFERENTIATION_DEMONSTRATED
  DI <  0 -> NOT_DEMONSTRATED

Note the arithmetic, because it is easy to misread:
control_margin is 0 AT BEST — arm A itself
contributes (control_A - control_A) = 0 to the min —
so DI <= 0 always. DI is a SHORTFALL index: 0 means
every margin is met (pass), negative means the worst
shortfall in pp. DI >= 0 is therefore DI == 0, not a
positive surplus; a test expecting a positive DI from
equal control rates is wrong, not the scorer.

Outcome vocabulary (the draft's §4/§7, exactly):
DIFFERENTIATION_DEMONSTRATED / NOT_DEMONSTRATED /
SATURATED_BY_DESIGN / INCONCLUSIVE.

Precedence, stated once: a malformed report is
NOT_DEMONSTRATED (fail-closed); a failed calibration
gate is SATURATED_BY_DESIGN even if the run is also
incomplete (a broken universe decides before a partial
run does); an incomplete run with a passed gate is
INCONCLUSIVE; otherwise DI decides. When the gate
fails, DI is still computed and reported as telemetry
only — it never drives the outcome.

Report schema (the implementation's contract, per the
draft's §6 — the run driver assembles its report to
this schema):

    {"arms": {"A": number, "B": number, "C": number},
     "control": {"A": number, "B": number, "C": number},
     "calibration_gate_passed": bool,
     "complete": bool}

Arms/control values are solve-rate percentages. This
instrument scores reports; it assembles none and
asserts no G2 result. G2 remains NOT_ASSESSED until a
v3 run is preregistered, executed, and its dossier
scored.
"""
from __future__ import annotations

from typing import Any

CRITERIA_VERSION = 1
ARMS = ("A", "B", "C")
MARGIN_C_MINUS_A_PP = 15.0
MARGIN_B_MINUS_A_PP = 5.0


def _number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _validate(report: Any) -> tuple[dict[str, Any] | None, list[str]]:
    """Fail-closed shape check. Returns (cleaned report,
    named problems). The cleaned report is the report
    itself when valid, else None."""
    problems: list[str] = []
    if not isinstance(report, dict):
        return None, ["report is not a mapping"]
    arms = report.get("arms")
    if not isinstance(arms, dict):
        problems.append("arms is missing or not a mapping")
        arms = {}
    control = report.get("control")
    if not isinstance(control, dict):
        problems.append("control is missing or not a mapping")
        control = {}
    for arm in ARMS:
        for label, section in (("arms", arms), ("control", control)):
            value = section.get(arm) if isinstance(section, dict) else None
            if not _number(value):
                problems.append(
                    f"{label}.{arm} is missing or not a number: "
                    f"{value!r}")
            elif not 0.0 <= value <= 100.0:
                problems.append(
                    f"{label}.{arm} is out of range [0, 100]: {value!r}")
    for flag in ("calibration_gate_passed", "complete"):
        if not isinstance(report.get(flag), bool):
            problems.append(
                f"{flag} is missing or not a boolean: "
                f"{report.get(flag)!r}")
    if problems:
        return None, problems
    return report, problems


def differentiation_index(*, arms: dict[str, float],
                          control: dict[str, float]) -> dict[str, float]:
    """The draft's §4 composite, pure arithmetic. Returns
    DI and its three terms, in percentage points."""
    c_minus_a = arms["C"] - arms["A"] - MARGIN_C_MINUS_A_PP
    b_minus_a = arms["B"] - arms["A"] - MARGIN_B_MINUS_A_PP
    control_margin = min(control[arm] - control["A"] for arm in ARMS)
    return {
        "differentiation_index_pp": min(c_minus_a, b_minus_a,
                                        control_margin),
        "c_minus_a_minus_15pp": c_minus_a,
        "b_minus_a_minus_5pp": b_minus_a,
        "control_margin_pp": control_margin,
    }


def assess_abc_v3(*, report: dict[str, Any] | None) -> dict[str, Any]:
    """Score an A/B/C v3 run report against the draft's
    §4 decision rule. Every clause lists, on failure,
    the exact missing or failed items. The outcome
    object always carries the criteria version."""
    valid, problems = _validate(report)

    clauses: dict[str, Any] = {}
    clauses["report_validity"] = {
        "verdict": "PASS" if valid is not None else "FAIL",
        "missing": problems,
        "evidence": ({"arms": valid["arms"],
                      "control": valid["control"]}
                     if valid is not None else None)}

    # ---- calibration gate (read from the report flag) ---------
    gate_missing: list[str] = []
    gate_passed: bool | None = None
    if valid is not None:
        gate_passed = valid["calibration_gate_passed"]
        if not gate_passed:
            gate_missing.append(
                "calibration gate failed on the run band's own "
                "re-check (arm A pooled solve rate outside "
                "10-90%); the universe is saturated by design, "
                "not a null")
    clauses["calibration_gate"] = {
        "verdict": ("PASS" if gate_passed else "FAIL"),
        "missing": gate_missing,
        "evidence": ({"calibration_gate_passed": gate_passed}
                     if valid is not None else None)}

    # ---- completeness ------------------------------------------
    complete_missing: list[str] = []
    complete: bool | None = None
    if valid is not None:
        complete = valid["complete"]
        if not complete:
            complete_missing.append(
                "run did not complete every band; the report is "
                "partial")
    clauses["completeness"] = {
        "verdict": ("PASS" if complete else "FAIL"),
        "missing": complete_missing,
        "evidence": ({"complete": complete}
                     if valid is not None else None)}

    # ---- differentiation index (arithmetic; telemetry when
    # the gate or completeness decides the outcome) --------
    di_missing: list[str] = []
    terms: dict[str, float] | None = None
    if valid is not None:
        terms = differentiation_index(arms=valid["arms"],
                                      control=valid["control"])
        if terms["differentiation_index_pp"] < 0:
            di_missing.append(
                "differentiation index is negative "
                f"({terms['differentiation_index_pp']:.2f}pp < 0)")
    clauses["differentiation_index"] = {
        "verdict": ("PASS" if terms is not None and
                    terms["differentiation_index_pp"] >= 0 else "FAIL"),
        "missing": di_missing,
        "evidence": terms}

    # ---- outcome (single construction point) --------------------
    if valid is None:
        overall = "NOT_DEMONSTRATED"
        qualification = ("The report is malformed; a malformed "
                         "report can never demonstrate "
                         "differentiation — see the named missing "
                         "items.")
    elif not gate_passed:
        overall = "SATURATED_BY_DESIGN"
        qualification = ("The calibration gate failed on the run "
                         "band's own re-check; the universe is "
                         "saturated by design. The differentiation "
                         "index is reported as telemetry only and "
                         "does not drive this outcome.")
    elif not complete:
        overall = "INCONCLUSIVE"
        qualification = ("The run did not complete every band; "
                         "a partial run is inconclusive, never "
                         "completed silently.")
    elif terms is not None and terms["differentiation_index_pp"] >= 0:
        overall = "DIFFERENTIATION_DEMONSTRATED"
        qualification = ("none — the composite index meets its "
                         "bar with the calibration gate passed and "
                         "the run complete.")
    else:
        overall = "NOT_DEMONSTRATED"
        qualification = ("The composite index is negative; see the "
                         "differentiation-index terms for which "
                         "margin binds.")
    return {
        "gate": "G2",
        "criteria_version": CRITERIA_VERSION,
        "definition": ("strategy differentiation is real, not a "
                       "universe artefact: arms differentiated by "
                       "strategy over one substrate and one "
                       "score-call budget (PR #147)"),
        "clauses": clauses,
        "differentiation_index_pp": (
            terms["differentiation_index_pp"] if terms else None),
        "overall": overall,
        "qualification": qualification,
    }
