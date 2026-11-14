"""Frozen-episode loading and prompt building for Stage-1 simulation.

Separation contract (PR #177 addendum item 2):
- The prompt builder reads ONLY the episodes store (at-time snapshots).
- Outcomes live in a separate store that this module never opens.
- A generated package is a SIMULATION artifact: this module has no
  dispatch path and the harness marks every review as simulation.
"""

import json
import os

from .proposer_schema import PACKAGE_VERSION

EPISODES_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..",
    "evidence", "proposer_stage1", "episodes.json")


def load_episodes(path=EPISODES_PATH):
    with open(os.path.normpath(path), encoding="utf-8") as fh:
        data = json.load(fh)
    episodes = data["episodes"]
    for ep in episodes:
        for field in ("episode_id", "information_snapshot",
                      "options_available", "evidence_scope",
                      "budget_envelope", "sealed_target_status_at_time",
                      "prior_exposure_declaration"):
            if field not in ep:
                raise ValueError("episode %s missing %s"
                                 % (ep.get("episode_id", "?"), field))
    return episodes


PROMPT_TEMPLATE = """You are ACE, an autonomous research system, at a past decision point. This is a SIMULATION on a frozen historical episode: nothing you propose will be executed.

DECISION: {title}
TIME: {decision_point}

INFORMATION AVAILABLE AT THE TIME (nothing later is known):
{information_snapshot}

OPTIONS AVAILABLE: {options}
BUDGET ENVELOPE: at most {max_calls} score calls, {max_wall} seconds wall, {max_cost} cost units.
SEALED TARGET STATUS AT THE TIME: {sealed}
EVIDENCE YOU MAY CITE (copy artifact names and sha256 exactly):
{evidence}

Write ONE proposal package as a single JSON object with EXACTLY these fields:
package_version: "{version}"
proposal_id: short string
task_kind: "task"
claim: one testable claim, with a number or threshold and the direction that would falsify it
rationale: why, from the information above only
options_considered: list of {{"name": ..., "assessment": ...}} covering EVERY option above including do_not_run
recommended_option: one of the option names
cost_estimate: {{"calls": int, "wall_seconds": int, "cost_units": number}} within the envelope
cost_ceiling: {{"max_calls": int, "max_wall_seconds": int, "max_cost_units": number}} not above the envelope
evidence: list of {{"artifact": ..., "sha256": ...}} copied exactly from the evidence list
preregistration: {{"link": "evidence/proposer_stage1/episodes.json#{episode_id}", "artifact_sha256": first evidence sha256}}
risks: at least 2 concrete risks
uncertainties: at least 1
stop_controls: {{"abort_conditions": [at least 2], "sealed_target_status": "{sealed}", "no_auto_retry": true, "stop_visible": true}}
ratification: {{"type": "internal_ratification", "audience": ["hub", "kernel", "evidence"]}}

Output ONLY the JSON object. No commentary, no markdown fences."""


def build_prompt(episode):
    """Build the proposer prompt from at-time information ONLY."""
    env = episode["budget_envelope"]
    evidence = "\n".join(
        '- artifact: %s\n  sha256: %s' % (e["artifact"], e["sha256"])
        for e in episode["evidence_scope"])
    return PROMPT_TEMPLATE.format(
        title=episode["title"],
        decision_point=episode["decision_point"],
        information_snapshot=episode["information_snapshot"],
        options=", ".join(episode["options_available"]),
        max_calls=env["calls"] or 100000,
        max_wall=env["wall_seconds"],
        max_cost=env["cost_units"],
        sealed=episode["sealed_target_status_at_time"],
        evidence=evidence,
        version=PACKAGE_VERSION,
        episode_id=episode["episode_id"],
    )
