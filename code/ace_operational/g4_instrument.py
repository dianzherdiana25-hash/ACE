"""G4 measurement instrument (design: PR #136 Part I;
application dossier design: bench Task 08, decisions
D-G4-1..5 ratified as design; build brief: bench
Task 10).

PRD v0.1 defines G4 — Hereditas: is capability *inherited*
across a lineage (stored, identified, and used by a
successor that did not itself discover it), rather than
re-derived each generation?

This module is the instrument the design specifies. It
scores a *dossier* — sealed evidence files, never
self-declared claims — mechanically and fail-closed,
following the G3 instrument's shape (``assess_g3``):

- C1 — lineage stored and auditable: a lineage record
  links predecessor -> successor (the successor's parent
  list contains the predecessor), a capability digest is
  attached to the link, and the archive's integrity is
  attested (audit CLEAN and the hash chain valid).
- C2 — capability identified with admission evidence:
  the capability record names the artifact by digest,
  and the discovery record — with non-empty measured
  admission evidence — carries the *same* digest.
  Identity is by digest; an equal name never suffices.
- C3 — successor use with attribution control: an
  evaluation report under preregistration (protocol
  hash present, kernel audit CLEAN) shows the lineage's
  successor — which attests it never invoked discovery —
  loading the capability artifact (digest equal) and
  meeting, on held-out capability tasks, all four
  ratified effect conditions against the thresholds
  read from the report itself (``margin_pp``,
  ``with_floor``, ``without_ceiling``,
  ``min_capability_tasks`` — fixed by the preregistration
  that produced the report, never hardcoded here):
  (1) delta (with - without)/n >= margin_pp,
  (2) with/n >= with_floor,
  (3) without/n <= without_ceiling (attribution ceiling),
  (4) no control regression (control with >= without).

Identity discipline is the reward-hacking guard, and it
is a HARD fence: any digest inequality among the
capability record, the discovery record, the digest
attached to the lineage link, and the artifact as loaded
by the successor is recorded ONCE in
``identity_mismatches`` (the check runs once; clauses
reference its result), the affected clause fails, and
the overall outcome is forced to NOT_DEMONSTRATED.

Outcome vocabulary (the design's, exactly):
INHERITANCE_DEMONSTRATED / LINEAGE_ONLY /
NOT_DEMONSTRATED. LINEAGE_ONLY is the honest score when
the lineage and the capability identity are fully
audited but successor use is absent, unrun, or below the
ratified effect conditions.

Dossier schema (the implementation's contract): the
dossier is a *directory* containing ``dossier.json``,
a manifest naming the three records by relative path:

    {"lineage": "lineage_record.json",
     "capability": "capability_record.json",
     "evaluation": "evaluation_report.json"}

    lineage_record.json:
    {"predecessor_id": str, "successor_id": str,
     "successor_parents": [str, ...],
     "capability_digest": str,
     "archive_audit": "CLEAN", "chain_valid": true}

    capability_record.json:
    {"artifact_name": str, "artifact_digest": str,
     "discovery_record": {"artifact_name": str,
                          "artifact_digest": str,
                          "admission_evidence": {...}}}

    evaluation_report.json:
    {"protocol_hash": str, "audit": "CLEAN",
     "successor_id": str, "artifact_digest_loaded": str,
     "discovery_invoked": false,
     "margin_pp": number, "with_floor": number,
     "without_ceiling": number,
     "min_capability_tasks": number,
     "capability": {"n": int, "with_solved": int,
                    "without_solved": int},
     "control": {"with_solved": int, "without_solved": int}}

A record may carry ``superseded_records`` (older versions
listed alongside the current one): superseded entries are
never scored; they are named as warnings and flip nothing
(the coordinator's ruling on the G3 verification).

This instrument scores dossiers; it assembles none and
asserts no G4 result. G4 remains NOT_ASSESSED until a
dossier is assembled under preregistration and scored.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CRITERIA_VERSION = 1
THRESHOLD_FIELDS = ("margin_pp", "with_floor",
                    "without_ceiling", "min_capability_tasks")


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


def assess_g4(*, dossier: str | Path | None) -> dict[str, Any]:
    """Score a G4 dossier directory against clauses
    C1-C3. Every clause lists, on failure, the exact
    missing or failed items. The outcome object always
    carries the criteria version, and is built at a
    single construction point (no early return)."""
    dossier_dir = Path(dossier) if dossier is not None else None
    manifest = _load(dossier_dir / "dossier.json") \
        if dossier_dir is not None else None

    def load_record(key: str) -> dict[str, Any] | None:
        if manifest is None or dossier_dir is None:
            return None
        path = _resolve(dossier_dir, manifest.get(key))
        return _load(path) if path is not None else None

    lineage = load_record("lineage")
    capability = load_record("capability")
    evaluation = load_record("evaluation")

    # ---- identity check (runs ONCE; clauses reference it) -------
    # The four digest sources that must all name the same
    # artifact: the lineage link's attachment, the capability
    # record, its discovery record, and the artifact as
    # loaded by the successor. Any inequality is ONE
    # mismatch, described once, here.
    digests: dict[str, Any] = {}
    if lineage is not None and lineage.get("capability_digest"):
        digests["lineage.capability_digest"] = \
            lineage.get("capability_digest")
    cap_digest = capability.get("artifact_digest") \
        if capability is not None else None
    if cap_digest:
        digests["capability.artifact_digest"] = cap_digest
    discovery = capability.get("discovery_record") \
        if capability is not None else None
    if not isinstance(discovery, dict):
        discovery = None
    disc_digest = discovery.get("artifact_digest") \
        if discovery is not None else None
    if disc_digest:
        digests["discovery.artifact_digest"] = disc_digest
    loaded_digest = evaluation.get("artifact_digest_loaded") \
        if evaluation is not None else None
    if loaded_digest:
        digests["evaluation.artifact_digest_loaded"] = loaded_digest

    mismatches: list[str] = []
    if len(set(digests.values())) > 1:
        detail = ", ".join(f"{src}={val!r}"
                           for src, val in sorted(digests.items()))
        mismatches.append(
            f"capability identity mismatch — the dossier's records "
            f"do not name one artifact: {detail}")

    def identity_pointer(*sources: str) -> bool:
        """True when any of the named sources disagrees with
        the capability digest (the identity reference)."""
        if not mismatches or not cap_digest:
            return False
        return any(digests.get(src) not in (None, cap_digest)
                   for src in sources)

    # ---- superseded entries -> warnings (never scored) ----------
    def superseded_warning(record: dict[str, Any] | None,
                           label: str) -> list[str]:
        if record is None:
            return []
        extra = record.get("superseded_records")
        if isinstance(extra, list) and extra:
            return [f"{label}.superseded_records_ignored: "
                    f"{len(extra)} superseded entr"
                    f"{'y' if len(extra) == 1 else 'ies'} listed "
                    f"alongside the current record; the verdict "
                    f"rests on the current record only"]
        return []

    # ---- C1: lineage stored and auditable ------------------------
    c1_missing: list[str] = []
    if manifest is None:
        c1_missing.append("dossier.manifest_missing_or_unparseable")
    if lineage is None:
        c1_missing.append("lineage.record_missing_or_unparseable")
    else:
        predecessor = lineage.get("predecessor_id")
        successor = lineage.get("successor_id")
        if not predecessor:
            c1_missing.append("lineage.predecessor_id_missing")
        if not successor:
            c1_missing.append("lineage.successor_id_missing")
        parents = lineage.get("successor_parents")
        if predecessor and (not isinstance(parents, list)
                            or predecessor not in parents):
            c1_missing.append("lineage.successor_parent_link_missing")
        if not lineage.get("capability_digest"):
            c1_missing.append("lineage.capability_digest_missing")
        if lineage.get("archive_audit") != "CLEAN":
            c1_missing.append("lineage.archive_audit_not_clean")
        if lineage.get("chain_valid") is not True:
            c1_missing.append("lineage.chain_valid_not_true")
        if identity_pointer("lineage.capability_digest"):
            c1_missing.append("identity_mismatch "
                              "(see identity_mismatches)")
    c1 = {"verdict": "PASS" if not c1_missing else "FAIL",
          "missing": c1_missing,
          "warnings": superseded_warning(lineage, "lineage"),
          "evidence": ({"predecessor_id": lineage.get("predecessor_id"),
                        "successor_id": lineage.get("successor_id")}
                       if lineage is not None else None)}

    # ---- C2: capability identified with admission evidence ------
    c2_missing: list[str] = []
    if capability is None:
        c2_missing.append("capability.record_missing_or_unparseable")
    else:
        if not cap_digest:
            c2_missing.append("capability.artifact_digest_missing")
        if discovery is None:
            c2_missing.append("capability.discovery_record_missing")
        else:
            evidence = discovery.get("admission_evidence")
            if not evidence or (isinstance(evidence, dict)
                                and not evidence):
                c2_missing.append("capability.admission_evidence_empty")
            if not disc_digest:
                c2_missing.append("capability.discovery_digest_missing")
            elif identity_pointer("discovery.artifact_digest"):
                c2_missing.append("identity_mismatch "
                                  "(see identity_mismatches)")
    c2 = {"verdict": "PASS" if not c2_missing else "FAIL",
          "missing": c2_missing,
          "warnings": superseded_warning(capability, "capability"),
          "evidence": ({"artifact_name": capability.get("artifact_name"),
                        "artifact_digest": cap_digest}
                       if capability is not None else None)}

    # ---- C3: successor use with attribution control -------------
    c3_missing: list[str] = []
    c3_evidence: dict[str, Any] = {}
    if evaluation is None:
        c3_missing.append("evaluation.report_missing_or_unparseable")
    else:
        if not evaluation.get("protocol_hash"):
            c3_missing.append("c3.protocol_hash_missing")
        if evaluation.get("audit") != "CLEAN":
            c3_missing.append("c3.audit_not_clean")
        lineage_successor = lineage.get("successor_id") \
            if lineage is not None else None
        if lineage_successor is not None and \
                evaluation.get("successor_id") != lineage_successor:
            c3_missing.append("c3.successor_id_mismatch")
        invoked = evaluation.get("discovery_invoked")
        if invoked is True:
            c3_missing.append("c3.successor_rediscovered")
        elif invoked is not False:
            c3_missing.append("c3.discovery_invoked_not_false")
        if identity_pointer("evaluation.artifact_digest_loaded"):
            c3_missing.append("identity_mismatch "
                              "(see identity_mismatches)")
        thresholds: dict[str, float] = {}
        for field in THRESHOLD_FIELDS:
            value = evaluation.get(field)
            if not _number(value):
                c3_missing.append(f"c3.threshold_field_missing:{field}")
            else:
                thresholds[field] = float(value)
        counts = evaluation.get("capability")
        control = evaluation.get("control")
        n = with_solved = without_solved = None
        if not isinstance(counts, dict):
            c3_missing.append("c3.capability_counts_missing")
        else:
            raw = (counts.get("n"), counts.get("with_solved"),
                   counts.get("without_solved"))
            if any(v is not None and not _number(v) for v in raw):
                c3_missing.append("c3.capability_counts_not_numeric")
            n, with_solved, without_solved = raw
            if with_solved is None:
                c3_missing.append("c3.with_arm_missing")
            if without_solved is None:
                c3_missing.append("c3.control_arm_missing")
        control_with = control_without = None
        if not isinstance(control, dict):
            c3_missing.append("c3.control_counts_missing")
        else:
            raw_c = (control.get("with_solved"),
                     control.get("without_solved"))
            if any(v is not None and not _number(v) for v in raw_c):
                c3_missing.append("c3.control_counts_not_numeric")
            control_with, control_without = raw_c
            if control_with is None or control_without is None:
                c3_missing.append("c3.control_counts_missing")
        # The four ratified effect conditions — computed only
        # when every input is present and numeric.
        if len(thresholds) == len(THRESHOLD_FIELDS) \
                and _number(n) and _number(with_solved) \
                and _number(without_solved):
            if n <= 0:
                c3_missing.append("c3.capability_n_zero")
            else:
                delta_pp = (with_solved - without_solved) / n * 100.0
                with_frac = with_solved / n
                without_frac = without_solved / n
                c3_evidence = {
                    "n": n, "delta_pp": round(delta_pp, 4),
                    "with_fraction": round(with_frac, 4),
                    "without_fraction": round(without_frac, 4)}
                if n < thresholds["min_capability_tasks"]:
                    c3_missing.append(
                        "c3.capability_tasks_below_minimum")
                if delta_pp < thresholds["margin_pp"]:
                    c3_missing.append("c3.margin_not_met")
                if with_frac < thresholds["with_floor"]:
                    c3_missing.append("c3.with_floor_not_met")
                if without_frac > thresholds["without_ceiling"]:
                    c3_missing.append(
                        "c3.attribution_ceiling_exceeded")
        if _number(control_with) and _number(control_without) \
                and control_with < control_without:
            c3_missing.append("c3.control_regression")
    c3 = {"verdict": "PASS" if not c3_missing else "FAIL",
          "missing": c3_missing,
          "warnings": superseded_warning(evaluation, "evaluation"),
          "evidence": c3_evidence or None}

    clauses = {"C1": c1, "C2": c2, "C3": c3}

    # ---- outcome (single construction point) --------------------
    if mismatches:
        overall = "NOT_DEMONSTRATED"
        qualification = ("Identity fence: the dossier's records do "
                         "not name one capability artifact; the "
                         "successor cannot inherit from an artifact "
                         "that is not the one whose discovery is "
                         "recorded.")
    elif c1["verdict"] != "PASS" or c2["verdict"] != "PASS":
        overall = "NOT_DEMONSTRATED"
        qualification = ("The lineage is not auditable or the "
                         "capability is not identified with admission "
                         "evidence; see the named missing items.")
    elif c3["verdict"] == "PASS":
        overall = "INHERITANCE_DEMONSTRATED"
        qualification = ("none — an audited successor that never "
                         "discovered uses the identified inherited "
                         "artifact and meets every ratified effect "
                         "condition under attribution control.")
    else:
        overall = "LINEAGE_ONLY"
        qualification = ("Lineage and capability identity are fully "
                         "audited, but successor use is absent, "
                         "unrun, or below the ratified effect "
                         "conditions — capability is stored, not yet "
                         "demonstrated in use.")
    return {
        "gate": "G4",
        "criteria_version": CRITERIA_VERSION,
        "definition": ("capability is inherited across a lineage — "
                       "stored, identified by digest, and used by a "
                       "successor that did not discover it — rather "
                       "than re-derived each generation (PRD v0.1)"),
        "clauses": clauses,
        "identity_mismatches": mismatches,
        "overall": overall,
        "qualification": qualification,
    }
