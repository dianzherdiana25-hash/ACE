"""Fail-closed validator for proposer packages.

A package that lacks a cost ceiling, lacks enforced stop controls, or
lacks evidence hashes is MECHANICALLY REJECTED - no discretionary
override exists in this module. Every rejection carries named reasons
so a package can be "rejected with reasons" (PR #173 section 9).

Pure function, no I/O, no dispatch: validation never executes the
proposed work (Stage 1 is simulation-first).
"""

import re

from .proposer_schema import (
    CEILING_FIELDS,
    COST_FIELDS,
    FORBIDDEN_RATIFICATION_TERMS,
    PACKAGE_FIELDS,
    PACKAGE_VERSION,
    RATIFICATION_AUDIENCE,
    RATIFICATION_TYPE,
    STOP_CONTROL_FIELDS,
    TASK_KINDS,
)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _is_number(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _nonempty_str(x):
    return isinstance(x, str) and bool(x.strip())


def validate_package(pkg):
    """Return (accepted: bool, reasons: list[str]).

    accepted is True only when reasons is empty. Fail-closed: any
    structural surprise (wrong types, unknown fields, forbidden
    ratification vocabulary) is a rejection reason.
    """
    reasons = []
    if not isinstance(pkg, dict):
        return False, ["package is not a JSON object"]

    unknown = sorted(set(pkg) - set(PACKAGE_FIELDS))
    if unknown:
        reasons.append("unknown top-level fields: %s" % ", ".join(unknown))
    missing = [f for f in PACKAGE_FIELDS if f not in pkg]
    if missing:
        reasons.append("missing fields: %s" % ", ".join(missing))
        # Cannot meaningfully check the rest of a partial package.
        return False, reasons

    if pkg["package_version"] != PACKAGE_VERSION:
        reasons.append("package_version must be %r" % PACKAGE_VERSION)
    if not _nonempty_str(pkg["proposal_id"]):
        reasons.append("proposal_id must be a non-empty string")
    if pkg["task_kind"] not in TASK_KINDS:
        reasons.append("task_kind must be one of %s" % (TASK_KINDS,))
    if not _nonempty_str(pkg["claim"]):
        reasons.append("claim must be a non-empty string")
    if not _nonempty_str(pkg["rationale"]):
        reasons.append("rationale must be a non-empty string")

    # Options: the do-not-run option must be present and assessed.
    opts = pkg["options_considered"]
    if not isinstance(opts, list) or len(opts) < 2:
        reasons.append("options_considered must list at least 2 options")
        opts = []
    names = []
    for i, opt in enumerate(opts):
        if not isinstance(opt, dict) or not _nonempty_str(opt.get("name")):
            reasons.append("options_considered[%d] lacks a name" % i)
            continue
        names.append(opt["name"])
        if not _nonempty_str(opt.get("assessment")):
            reasons.append(
                "options_considered[%d] (%s) lacks an assessment"
                % (i, opt["name"])
            )
    if "do_not_run" not in names:
        reasons.append("options_considered must include 'do_not_run'")
    if pkg["recommended_option"] not in names:
        reasons.append("recommended_option must be one of options_considered")

    # Cost estimate vs ceiling: both required, estimate within ceiling.
    est, ceil = pkg["cost_estimate"], pkg["cost_ceiling"]
    if not isinstance(est, dict) or sorted(est) != sorted(COST_FIELDS):
        reasons.append("cost_estimate must have exactly %s" % (COST_FIELDS,))
        est = {}
    if not isinstance(ceil, dict) or sorted(ceil) != sorted(CEILING_FIELDS):
        reasons.append("cost_ceiling must have exactly %s" % (CEILING_FIELDS,))
        ceil = {}
    for f in COST_FIELDS:
        if f in est and (not _is_number(est[f]) or est[f] < 0):
            reasons.append("cost_estimate.%s must be a number >= 0" % f)
    for f in CEILING_FIELDS:
        if f in ceil and (not _is_number(ceil[f]) or ceil[f] <= 0):
            reasons.append(
                "cost_ceiling.%s must be a number > 0 (a package without "
                "a positive ceiling is rejected)" % f
            )
    pairs = (
        ("calls", "max_calls"),
        ("wall_seconds", "max_wall_seconds"),
        ("cost_units", "max_cost_units"),
    )
    for ef, cf in pairs:
        if _is_number(est.get(ef)) and _is_number(ceil.get(cf)):
            if est[ef] > ceil[cf]:
                reasons.append(
                    "cost_estimate.%s (%s) exceeds cost_ceiling.%s (%s)"
                    % (ef, est[ef], cf, ceil[cf])
                )

    # Evidence: at least one artifact, every artifact hash-pinned.
    ev = pkg["evidence"]
    if not isinstance(ev, list) or not ev:
        reasons.append("evidence must be a non-empty list")
    else:
        for i, item in enumerate(ev):
            if not isinstance(item, dict) or not _nonempty_str(item.get("artifact")):
                reasons.append("evidence[%d] lacks an artifact name" % i)
            elif not _SHA256_RE.match(str(item.get("sha256", ""))):
                reasons.append(
                    "evidence[%d] (%s) lacks a valid sha256 hash"
                    % (i, item.get("artifact"))
                )

    # Preregistration link + hash of the locked artifact.
    prereg = pkg["preregistration"]
    if not isinstance(prereg, dict):
        reasons.append("preregistration must be an object")
    else:
        if not _nonempty_str(prereg.get("link")):
            reasons.append("preregistration.link must be non-empty")
        if not _SHA256_RE.match(str(prereg.get("artifact_sha256", ""))):
            reasons.append("preregistration.artifact_sha256 must be a sha256")

    # Risks / uncertainties: the main ones, named, not empty.
    if not (isinstance(pkg["risks"], list) and pkg["risks"]
            and all(_nonempty_str(r) for r in pkg["risks"])):
        reasons.append("risks must be a non-empty list of strings")
    if not (isinstance(pkg["uncertainties"], list) and pkg["uncertainties"]
            and all(_nonempty_str(u) for u in pkg["uncertainties"])):
        reasons.append("uncertainties must be a non-empty list of strings")

    # Stop controls: visible and enforced - the heart of fail-closed.
    sc = pkg["stop_controls"]
    if not isinstance(sc, dict) or sorted(sc) != sorted(STOP_CONTROL_FIELDS):
        reasons.append(
            "stop_controls must have exactly %s" % (STOP_CONTROL_FIELDS,))
    else:
        if not (isinstance(sc["abort_conditions"], list)
                and sc["abort_conditions"]
                and all(_nonempty_str(a) for a in sc["abort_conditions"])):
            reasons.append(
                "stop_controls.abort_conditions must be a non-empty list")
        if not _nonempty_str(sc["sealed_target_status"]):
            reasons.append(
                "stop_controls.sealed_target_status must be non-empty")
        if sc["no_auto_retry"] is not True:
            reasons.append(
                "stop_controls.no_auto_retry must be true "
                "(no-auto-retry guarantee is mandatory)")
        if sc["stop_visible"] is not True:
            reasons.append("stop_controls.stop_visible must be true")

    # Ratification: internal only; owner-approval vocabulary rejects.
    rat = pkg["ratification"]
    flat = str(rat).lower()
    for term in FORBIDDEN_RATIFICATION_TERMS:
        if term in flat:
            reasons.append(
                "ratification uses forbidden term %r: packages request "
                "internal ratification, not owner approval" % term)
    if not isinstance(rat, dict) or rat.get("type") != RATIFICATION_TYPE:
        reasons.append("ratification.type must be %r" % RATIFICATION_TYPE)
    elif sorted(rat.get("audience", [])) != sorted(RATIFICATION_AUDIENCE):
        reasons.append(
            "ratification.audience must be %s" % (list(RATIFICATION_AUDIENCE),))

    return (not reasons), reasons
