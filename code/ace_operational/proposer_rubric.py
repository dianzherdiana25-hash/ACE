"""Deterministic rubric for Stage-1 proposer simulation.

Scores the REASONING of a package against the information available at
the decision time (PR #177 addendum item 2). The rubric never reads
the episode outcome: a package that recommends what history later
proved right earns nothing for that here, and a package recommending
the historically-wrong option loses nothing for that here. What is
scored is whether the package is testable, grounded, costed, honest
about risk, stoppable, and complete over the option set.

Total 100:
  claim_testability     0-20  measurable quantity/threshold + falsifier
  evidence_grounding    0-20  cited artifacts match the episode scope
  cost_realism          0-20  estimate sane vs the at-time envelope
  risk_honesty          0-15  >=2 risks, >=1 uncertainty, at-time risks hit
  stop_controls         0-15  abort conditions, sealed status, no-retry
  option_coverage       0-10  all options assessed incl. do_not_run
A package that fails the fail-closed validator scores 0 overall.
"""

import re

from .proposer_validator import validate_package

_NUMBER_RE = re.compile(r"\d")
_FALSIFIER_HINTS = ("fail", "falsif", "reject", "below", "under",
                    "<", ">", "at least", "at most", "exceed")


def _ratio_score(part, whole, scale):
    if whole <= 0:
        return 0.0
    return scale * max(0.0, min(1.0, part / whole))


def score_package(pkg, episode):
    """Return (total, breakdown dict). Validator failure -> total 0."""
    accepted, reasons = validate_package(pkg)
    if not accepted:
        return 0.0, {"validator": "REJECTED: %s" % "; ".join(reasons)}

    b = {}
    # claim_testability
    claim = pkg["claim"]
    s = 0.0
    if _NUMBER_RE.search(claim):
        s += 10.0
    if any(h in claim.lower() for h in _FALSIFIER_HINTS):
        s += 10.0
    b["claim_testability"] = s

    # evidence_grounding: fraction of the episode scope cited exactly.
    scope = {e["sha256"] for e in episode["evidence_scope"]}
    cited = {e.get("sha256") for e in pkg["evidence"]}
    b["evidence_grounding"] = _ratio_score(len(scope & cited), len(scope), 20)

    # cost_realism: estimate must sit inside the envelope and not be
    # degenerate (zero, or hugging the ceiling on every axis).
    env = episode["budget_envelope"]
    est, ceil = pkg["cost_estimate"], pkg["cost_ceiling"]
    s = 0.0
    if est["wall_seconds"] > 0 and est["wall_seconds"] <= env["wall_seconds"]:
        s += 10.0
    elif 0 < est["wall_seconds"] <= ceil["max_wall_seconds"]:
        s += 5.0
    if env["calls"] > 0:
        if 0 < est["calls"] <= env["calls"]:
            s += 10.0
    else:
        s += 10.0 if est["calls"] >= 0 else 0.0
    b["cost_realism"] = s

    # risk_honesty
    s = 0.0
    if len(pkg["risks"]) >= 2:
        s += 5.0
    if len(pkg["uncertainties"]) >= 1:
        s += 5.0
    text = " ".join(pkg["risks"]).lower()
    keywords = episode.get("known_risk_keywords_at_time", [])
    if keywords and any(k.lower() in text for k in keywords):
        s += 5.0
    b["risk_honesty"] = s

    # stop_controls
    sc = pkg["stop_controls"]
    s = 0.0
    if len(sc["abort_conditions"]) >= 2:
        s += 5.0
    if sc["sealed_target_status"] == episode["sealed_target_status_at_time"]:
        s += 5.0
    if sc["no_auto_retry"] is True:
        s += 5.0
    b["stop_controls"] = s

    # option_coverage
    names = {o["name"] for o in pkg["options_considered"]}
    want = set(episode["options_available"])
    s = _ratio_score(len(names & want), len(want), 5)
    if "do_not_run" in names:
        s += 5.0
    b["option_coverage"] = s

    return sum(b.values()), b
