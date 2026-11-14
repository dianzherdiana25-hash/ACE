"""G5 measurement instrument (design: PR #136 Part II
and the ratified application dossier design, bench
Task 09, decisions D-G5-1..5; build brief: bench
Task 12a).

PRD v0.1 defines G5 — Akses: is the system's reporting
actually *used* by its owner, on the record? This module
is the instrument that design specifies. It scores a
*sealed harvest dossier* — harvested records of the
discussion room's consolidated summaries and the
owner's recorded responses to them — mechanically and
fail-closed, following the G1/G3 instruments' shape.
It never contacts the owner, never reads live chats,
and manufactures no evidence: it scores a dossier that
a harvest (a separate, preregistered step under the
dossier design's harvest axiom) assembled and sealed.

Clauses:

- C1 — reporting completeness (rubric FR-09): a counted
  unit is complete when all four rubric fields are true.
  The clause passes when the complete fraction meets
  the report's own threshold AND every counted unit
  carries a true HASIL field — that floor is absolute,
  not a threshold: a summary without a result is not a
  report.
- C2 — delivery without a technical detour: a counted
  unit passes when it was delivered in the channel and
  is self-contained; the passing fraction must meet
  the report's threshold.
- C3 — recorded use: a candidate event qualifies when
  it references an existing unit, is timestamped after
  that unit, and bears one of the action-bearing action
  types. The clause passes when the qualifying count,
  the distinct-domain count, and (when the report
  requires it) the presence of a correction all meet
  the report's bars. A failure here records use as
  *not evidenced* at the required level — a property
  of the record, never of the person.

Every bar is read from the dossier's harvest report,
never hard-coded here; a missing or non-numeric bar is
a named failure of the affected clause, never a
default. The digest fence binds the *record*: each
sealed file's canonical digest is recomputed at one
code site and compared with the harvest report's
sealed digests, and the per-record content digests
ride under that file seal, so any post-sealing edit —
to a file or to a single record inside it — breaks the
seal and is named exactly once as an integrity
failure, forcing NOT_DEMONSTRATED whatever the
contents claim. The harvester may never be a summary
author (D-G5-5); that two-hats fence is enforced
mechanically here.

Dossier schema (the implementation's contract):

    <dossier dir>/dossier.json:
        {"harvest": "harvest_report.json",
         "units": "units.json",
         "use_events": "use_events.json"}

    harvest_report.json:
        {"period_start": iso8601, "period_end": iso8601,
         "c1_threshold": number, "c2_threshold": number,
         "c3_min_events": number, "c3_min_domains": number,
         "c3_requires_correction": bool,
         "harvester_id": str, "summary_author_ids": [str],
         "sealed_digests": {"units": sha256 hex,
                            "use_events": sha256 hex}}
        # a file's canonical digest is the SHA-256 of its
        # canonical JSON form: keys sorted, compact
        # separators, UTF-8.

    units.json:
        {"units": [{"unit_id": str, "message_ref": str,
                    "timestamp": iso8601, "author_id": str,
                    "content_digest": sha256 hex,
                    "fields": {"dicoba": bool, "hasil": bool,
                               "keyakinan": bool,
                               "batas": bool},
                    "delivered_in_channel": bool,
                    "self_contained": bool}]}

    use_events.json:
        {"events": [{"event_id": str, "message_ref": str,
                     "timestamp": iso8601,
                     "content_digest": sha256 hex,
                     "references_unit": str | null,
                     "action_type": str, "domain": str}]}

Outcome vocabulary (the design's, exactly):
ACCESS_DEMONSTRATED / DELIVERY_ONLY / NOT_DEMONSTRATED.

This instrument scores dossiers; it harvests none and
asserts no G5 result. G5 remains NOT_ASSESSED until a
dossier is harvested under preregistration and scored.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

CRITERIA_VERSION = 1

_FIELDS = ("dicoba", "hasil", "keyakinan", "batas")
_ACTION_BEARING = ("decision", "direction", "correction",
                   "resource_commitment")


def _number(value: Any) -> bool:
    return isinstance(value, (int, float)) \
        and not isinstance(value, bool)


def _canonical_digest(data: Any) -> str:
    blob = json.dumps(data, sort_keys=True,
                      separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _load_json(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _resolve(root: Path, ref: Any) -> Path | None:
    if not isinstance(ref, str) or not ref:
        return None
    path = Path(ref)
    return path if path.is_absolute() else root / path


def _parse_ts(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        moment = datetime.fromisoformat(
            value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return moment if moment.tzinfo is not None else None


def _clause() -> dict[str, Any]:
    return {"verdict": "FAIL", "missing": [], "warnings": []}


def _build_result(clauses: dict[str, Any],
                  integrity_failures: list[str]) -> dict[str, Any]:
    """Single construction point: every path returns
    through here, and the overall is derived from the
    clause verdicts and the integrity fence alone."""
    if integrity_failures:
        overall = "NOT_DEMONSTRATED"
    elif clauses["C1"]["verdict"] != "PASS" \
            or clauses["C2"]["verdict"] != "PASS":
        overall = "NOT_DEMONSTRATED"
    elif clauses["C3"]["verdict"] != "PASS":
        overall = "DELIVERY_ONLY"
    else:
        overall = "ACCESS_DEMONSTRATED"
    return {
        "gate": "G5",
        "criteria_version": CRITERIA_VERSION,
        "overall": overall,
        "clauses": clauses,
        "integrity_failures": integrity_failures,
    }


def assess_g5(*, dossier: str | Path | None) -> dict[str, Any]:
    """Score a sealed G5 harvest dossier against clauses
    C1-C3. Fail-closed: missing, malformed, or
    non-numeric content is a named failure, never a
    default and never an exception."""
    clauses = {"C1": _clause(), "C2": _clause(), "C3": _clause()}
    integrity_failures: list[str] = []

    def fail_all(name: str) -> dict[str, Any]:
        for clause in clauses.values():
            clause["missing"].append(name)
        return _build_result(clauses, integrity_failures)

    # ---- locate and load the dossier (fail-closed) ---------------
    if dossier is None:
        return fail_all("dossier.missing")
    root = Path(dossier)
    index_path = root if root.is_file() else root / "dossier.json"
    if root.is_file():
        root = root.parent
    index = _load_json(index_path)
    if index is None:
        return fail_all("dossier.index_missing_or_malformed")
    harvest = _load_json(_resolve(root, index.get("harvest")))
    units_data = _load_json(_resolve(root, index.get("units")))
    events_data = _load_json(_resolve(root, index.get("use_events")))
    if harvest is None:
        return fail_all("harvest.report_missing_or_malformed")
    if units_data is None:
        return fail_all("units.file_missing_or_malformed")
    if events_data is None:
        return fail_all("use_events.file_missing_or_malformed")

    # ---- two-hats fence (D-G5-5), mechanical ---------------------
    harvester = harvest.get("harvester_id")
    authors = harvest.get("summary_author_ids")
    if isinstance(harvester, str) and isinstance(authors, list) \
            and harvester in authors:
        integrity_failures.append("harvest.harvester_is_author")

    # ---- digest fence: one code site, named exactly once ---------
    sealed = harvest.get("sealed_digests")
    if not isinstance(sealed, dict):
        integrity_failures.append("harvest.sealed_digests_missing")
    else:
        for key, data in (("units", units_data),
                          ("use_events", events_data)):
            expected = sealed.get(key)
            if not isinstance(expected, str):
                integrity_failures.append(
                    f"{key}.sealed_digest_missing")
            elif _canonical_digest(data) != expected:
                integrity_failures.append(f"{key}.digest_mismatch")

    # ---- bars, read from the harvest report (never owned) --------
    def bar(name: str, clause: dict[str, Any],
            kind: str) -> Any:
        value = harvest.get(name)
        if value is None:
            clause["missing"].append(f"harvest.{name}:missing")
            return None
        if kind == "number" and not _number(value):
            clause["missing"].append(f"harvest.{name}:not_numeric")
            return None
        if kind == "bool" and not isinstance(value, bool):
            clause["missing"].append(f"harvest.{name}:not_boolean")
            return None
        return value

    c1_threshold = bar("c1_threshold", clauses["C1"], "number")
    c2_threshold = bar("c2_threshold", clauses["C2"], "number")
    c3_min_events = bar("c3_min_events", clauses["C3"], "number")
    c3_min_domains = bar("c3_min_domains", clauses["C3"], "number")
    c3_needs_correction = bar("c3_requires_correction",
                              clauses["C3"], "bool")

    period_start = _parse_ts(harvest.get("period_start"))
    period_end = _parse_ts(harvest.get("period_end"))
    period_ok = period_start is not None and period_end is not None
    if not period_ok:
        for clause in clauses.values():
            clause["missing"].append("harvest.period_invalid")

    def in_period(moment: datetime | None) -> bool:
        return period_ok and moment is not None \
            and period_start <= moment <= period_end

    # ---- prepare units: period fence, then record shape ----------
    raw_units = units_data.get("units")
    if not isinstance(raw_units, list):
        clauses["C1"]["missing"].append("units.records_missing")
        clauses["C2"]["missing"].append("units.records_missing")
        raw_units = []
    unit_moments: dict[str, datetime | None] = {}
    counted: list[dict[str, Any]] = []
    for position, raw in enumerate(raw_units):
        if not isinstance(raw, dict) \
                or not isinstance(raw.get("unit_id"), str):
            for key in ("C1", "C2"):
                clauses[key]["warnings"].append(
                    f"units[{position}]:malformed_record")
            continue
        unit_id = raw["unit_id"]
        moment = _parse_ts(raw.get("timestamp"))
        unit_moments[unit_id] = moment
        if moment is None:
            for key in ("C1", "C2"):
                clauses[key]["warnings"].append(
                    f"{unit_id}:timestamp_invalid")
            continue
        if period_ok and not in_period(moment):
            for key in ("C1", "C2"):
                clauses[key]["warnings"].append(
                    f"{unit_id}:out_of_period")
            continue
        if period_ok:
            counted.append(raw)

    # ---- C1: FR-09 completeness + the absolute HASIL floor -------
    c1 = clauses["C1"]
    complete = 0
    hasil_floor_ok = True
    c1_malformed = False
    for unit in counted:
        unit_id = unit["unit_id"]
        fields = unit.get("fields")
        if not isinstance(fields, dict):
            fields = {}
        unit_complete = True
        for field in _FIELDS:
            value = fields.get(field)
            if value is True:
                continue
            unit_complete = False
            if field in fields and not isinstance(value, bool):
                c1["missing"].append(
                    f"{unit_id}.fields.{field}:not_boolean")
                c1_malformed = True
            else:
                c1["missing"].append(f"{unit_id}.fields.{field}")
            if field == "hasil":
                hasil_floor_ok = False
        if unit_complete:
            complete += 1
    c1_fraction_ok = False
    if not counted:
        c1["missing"].append("c1.no_counted_units")
    elif c1_threshold is not None:
        c1_fraction_ok = complete / len(counted) >= c1_threshold
        if not c1_fraction_ok:
            c1["missing"].append(
                f"c1.fraction_below_threshold:"
                f"{complete}/{len(counted)}<{c1_threshold}")
    if not hasil_floor_ok:
        c1["missing"].append("c1.hasil_floor")
    if period_ok and counted and c1_threshold is not None \
            and c1_fraction_ok and hasil_floor_ok \
            and not c1_malformed:
        c1["verdict"] = "PASS"

    # ---- C2: delivery without a technical detour ------------------
    c2 = clauses["C2"]
    delivered = 0
    c2_malformed = False
    for unit in counted:
        unit_id = unit["unit_id"]
        unit_passes = True
        for flag in ("delivered_in_channel", "self_contained"):
            value = unit.get(flag)
            if value is True:
                continue
            unit_passes = False
            if flag in unit and not isinstance(value, bool):
                c2["missing"].append(f"{unit_id}.{flag}:not_boolean")
                c2_malformed = True
            else:
                c2["missing"].append(f"{unit_id}.{flag}")
        if unit_passes:
            delivered += 1
    c2_fraction_ok = False
    if not counted:
        c2["missing"].append("c2.no_counted_units")
    elif c2_threshold is not None:
        c2_fraction_ok = delivered / len(counted) >= c2_threshold
        if not c2_fraction_ok:
            c2["missing"].append(
                f"c2.fraction_below_threshold:"
                f"{delivered}/{len(counted)}<{c2_threshold}")
    if period_ok and counted and c2_threshold is not None \
            and c2_fraction_ok and not c2_malformed:
        c2["verdict"] = "PASS"

    # ---- C3: recorded use, three ratified tests per candidate -----
    c3 = clauses["C3"]
    raw_events = events_data.get("events")
    if not isinstance(raw_events, list):
        c3["missing"].append("use_events.records_missing")
        raw_events = []
    qualifying: list[dict[str, Any]] = []
    for position, raw in enumerate(raw_events):
        if not isinstance(raw, dict) \
                or not isinstance(raw.get("event_id"), str):
            c3["warnings"].append(
                f"events[{position}]:malformed_record")
            continue
        event_id = raw["event_id"]
        moment = _parse_ts(raw.get("timestamp"))
        if moment is None:
            c3["warnings"].append(
                f"{event_id}:not_qualifying:sequence")
            continue
        if period_ok and not in_period(moment):
            c3["warnings"].append(f"{event_id}:out_of_period")
            continue
        if not period_ok:
            continue
        failed: list[str] = []
        reference = raw.get("references_unit")
        if not isinstance(reference, str) \
                or reference not in unit_moments:
            failed.append("reference")
        else:
            unit_moment = unit_moments[reference]
            if unit_moment is None or moment <= unit_moment:
                failed.append("sequence")
        if raw.get("action_type") not in _ACTION_BEARING:
            failed.append("action")
        if failed:
            c3["warnings"].append(
                f"{event_id}:not_qualifying:{'+'.join(failed)}")
        else:
            qualifying.append(raw)
    domains = {event["domain"] for event in qualifying
               if isinstance(event.get("domain"), str)}
    c3_ok = period_ok and c3_min_events is not None \
        and c3_min_domains is not None \
        and c3_needs_correction is not None
    if c3_ok and len(qualifying) < c3_min_events:
        c3["missing"].append(
            f"c3.events_below_min:{len(qualifying)}"
            f"<{c3_min_events} (use not evidenced at the "
            f"required level)")
        c3_ok = False
    if c3_ok and len(domains) < c3_min_domains:
        c3["missing"].append(
            f"c3.domains_below_min:{len(domains)}"
            f"<{c3_min_domains} (use not evidenced at the "
            f"required breadth)")
        c3_ok = False
    if c3_ok and c3_needs_correction and not any(
            event.get("action_type") == "correction"
            for event in qualifying):
        c3["missing"].append(
            "c3.correction_absent (use not evidenced "
            "including a correction)")
        c3_ok = False
    if c3_ok:
        c3["verdict"] = "PASS"

    return _build_result(clauses, integrity_failures)
