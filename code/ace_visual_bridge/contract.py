"""Evidence-first adapter contract for ACE <-> Autonomous Visual Agent.

This is NOT a generator, image recognizer, identity verifier or moderation model.
It accepts explicit observations about returned image assets; it never invents them.
Only standard-library dependencies are used.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Mapping

LOCKED = frozenset({
    "subject_count", "face_identity", "headwear", "glasses",
    "wardrobe_coverage", "body_proportions", "pose", "camera",
    "background", "lighting", "micro_detail",
})
ALLOWED_CHANGE = frozenset({"pose", "camera", "wardrobe_coverage", "background", "lighting", "micro_detail"})
WEIGHTS = {
    "identity": .35, "wardrobe": .25, "pose": .15,
    "camera": .10, "anatomy": .10, "composition": .05,
}


@dataclass(frozen=True)
class Anchor:
    asset_id: str
    provenance: str  # USER_ORIGINAL or GENERATED_RESULT
    approved_by_user: bool
    real_or_possible_person: bool

    def __post_init__(self) -> None:
        if not self.asset_id.strip():
            raise ValueError("anchor asset_id required")
        if self.provenance not in {"USER_ORIGINAL", "GENERATED_RESULT"}:
            raise ValueError("unknown image provenance")
        # Exact boolean validation: dataclasses do not enforce
        # declared types, and a JSON string "false" is truthy —
        # without this, an unadopted generated result passes
        # the adoption check in plan_edit (PR #105 finding).
        if not isinstance(self.approved_by_user, bool):
            raise ValueError(
                "approved_by_user must be a boolean, got "
                f"{self.approved_by_user!r}")
        if not isinstance(self.real_or_possible_person, bool):
            raise ValueError(
                "real_or_possible_person must be a boolean, got "
                f"{self.real_or_possible_person!r}")


@dataclass(frozen=True)
class EditPlan:
    source_asset_id: str
    change_axis: str
    locked_axes: frozenset[str]


def plan_edit(anchor: Anchor, axis: str = "micro_detail") -> EditPlan:
    """Ambiguous 'next' maps to micro_detail, never more exposed clothing."""
    if axis not in ALLOWED_CHANGE:
        raise ValueError("unrecognized or disallowed edit axis")
    if anchor.provenance == "GENERATED_RESULT" and not anchor.approved_by_user:
        raise ValueError("generated result was not adopted as the source anchor")
    return EditPlan(anchor.asset_id, axis, LOCKED - {axis})


@dataclass(frozen=True)
class Observation:
    slot: int
    asset_id: str | None
    image_type: str  # SINGLE_PHOTO, COMPOSITE, DOCUMENT, UNKNOWN
    safety: str  # SAFE, BLOCKED, UNKNOWN; supplied by actual external review
    evidence: str  # SOURCE_COMPARE, OBSERVED_IMAGE, UNKNOWN
    identity: str  # MATCH, MISMATCH, UNKNOWN; only visual consistency observation
    drifted_axes: frozenset[str]
    scores: Mapping[str, float] | None
    independently_reviewed: bool = False
    accepted_by_user: bool = False


    def __post_init__(self) -> None:
        # Exact collection validation: a bare string here is
        # split into characters by frozenset(...) at the CLI
        # boundary, so drift on a locked axis evades the
        # intersection check in assess (PR #105 finding).
        # Every element must be a known axis name.
        if not isinstance(self.drifted_axes, (set, frozenset)):
            raise ValueError(
                "drifted_axes must be a set of axis names, got "
                f"{self.drifted_axes!r}")
        unknown = sorted(
            axis for axis in self.drifted_axes
            if not isinstance(axis, str) or axis not in LOCKED)
        if unknown:
            raise ValueError(
                f"unknown drifted axis name(s): {unknown}")


@dataclass(frozen=True)
class CandidateReview:
    slot: int
    asset_id: str | None
    status: str  # QUALIFIED, BLOCKED, REJECTED, NOT_ASSESSED
    reason: str
    score: float | None


@dataclass(frozen=True)
class BatchReview:
    expected: int
    observed_original_assets: int
    qualified: int
    status: str
    selected_asset_id: str | None
    reviews: tuple[CandidateReview, ...]


def assess(anchor: Anchor, plan: EditPlan, obs: Observation) -> CandidateReview:
    """No scores based solely on prompt text or an unavailable image."""
    if obs.safety == "BLOCKED":
        return CandidateReview(obs.slot, obs.asset_id, "BLOCKED", "host or reviewer refusal: stop this branch", None)
    if obs.asset_id is None or obs.image_type == "UNKNOWN":
        return CandidateReview(obs.slot, obs.asset_id, "NOT_ASSESSED", "no inspectable original output", None)
    if obs.image_type != "SINGLE_PHOTO":
        return CandidateReview(obs.slot, obs.asset_id, "REJECTED", "OUTPUT_TYPE_MISMATCH", None)
    if obs.safety != "SAFE":
        return CandidateReview(obs.slot, obs.asset_id, "NOT_ASSESSED", "safety not reviewed", None)
    if obs.drifted_axes & plan.locked_axes:
        return CandidateReview(obs.slot, obs.asset_id, "REJECTED", "locked visual dimension drift", None)
    if anchor.real_or_possible_person:
        if obs.evidence != "SOURCE_COMPARE":
            return CandidateReview(obs.slot, obs.asset_id, "NOT_ASSESSED", "real-photo edit lacks source comparison", None)
        if obs.identity == "MISMATCH":
            return CandidateReview(obs.slot, obs.asset_id, "REJECTED", "visible identity mismatch", None)
        if obs.identity != "MATCH":
            return CandidateReview(obs.slot, obs.asset_id, "NOT_ASSESSED", "identity consistency unknown", None)
    elif obs.evidence not in {"SOURCE_COMPARE", "OBSERVED_IMAGE"}:
        return CandidateReview(obs.slot, obs.asset_id, "NOT_ASSESSED", "no visual observations", None)

    if obs.scores is None or set(obs.scores) != set(WEIGHTS):
        return CandidateReview(obs.slot, obs.asset_id, "NOT_ASSESSED", "complete observable rubric missing", None)
    if any(
        isinstance(value, bool) or not isinstance(value, (float, int))
        or not isfinite(value) or not 0 <= value <= 5
        for value in obs.scores.values()
    ):
        return CandidateReview(obs.slot, obs.asset_id, "NOT_ASSESSED", "invalid rubric evidence", None)
    score = round(sum(obs.scores[key] * weight for key, weight in WEIGHTS.items()), 4)
    return CandidateReview(obs.slot, obs.asset_id, "QUALIFIED", "observational, not biometric verification", score)


def review_batch(anchor: Anchor, plan: EditPlan, observations: list[Observation], expected: int = 5) -> BatchReview:
    if expected < 1:
        raise ValueError("expected must be positive")
    if plan.source_asset_id != anchor.asset_id:
        raise ValueError("plan anchor differs from evaluation anchor")
    slots = [o.slot for o in observations]
    if len(set(slots)) != len(slots):
        raise ValueError("duplicate candidate slots")
    asset_ids = [o.asset_id for o in observations if o.asset_id is not None]
    if len(asset_ids) != len(set(asset_ids)):
        raise ValueError("one image asset reused in multiple slots")

    reviews = tuple(assess(anchor, plan, o) for o in observations)
    originals = sum(o.asset_id is not None for o in observations)
    qualified = sorted(
        (r for r in reviews if r.status == "QUALIFIED"),
        key=lambda r: (-float(r.score), r.slot),
    )
    if any(r.status == "BLOCKED" for r in reviews):
        return BatchReview(expected, originals, len(qualified), "BLOCKED", None, reviews)
    if not qualified:
        status = "PARTIAL" if originals < expected else "NOT_ASSESSED"
        return BatchReview(expected, originals, 0, status, None, reviews)
    if len(qualified) > 1 and float(qualified[0].score) - float(qualified[1].score) < .10:
        return BatchReview(expected, originals, len(qualified), "TIE_REVIEW_REQUIRED", None, reviews)

    selected = qualified[0]
    selected_obs = next(o for o in observations if o.asset_id == selected.asset_id)
    if originals < expected:
        status = "PARTIAL"
    elif selected_obs.accepted_by_user and selected_obs.independently_reviewed:
        status = "USER_ACCEPTED"
    else:
        status = "PROVISIONAL_SELECTION"
    return BatchReview(expected, originals, len(qualified), status, selected.asset_id, reviews)
