"""ACE Omega — Proposer Engine Stage 1 v2 (Grammar + Bounded 1-Shot Repair).

Answers PR #199 section 3 reopening protocol under a new preregistration
BEFORE reading outcomes.json:
  1. Grammar-constrained decoding via OpenAI json_schema enforcing
     ace.proposal.v1 structure, list types (notably uncertainties/risks),
     strict object fields, and stop_controls booleans at generation time.
  2. Closed validator-feedback repair loop (max 1 repair turn using ONLY
     validate_package rejection reasons; no outcomes, no rubric scores).

Evaluates BOTH locked arms cleanly over frozen generations:
  - grammar_only (Attempt 0 only, zero retries)
  - grammar_plus_1_repair (Attempt 0; optional 1 validator repair if rejected)
"""
from __future__ import annotations

import hashlib
import json
import os
import statistics
import time
import urllib.request

from .proposer_episodes import build_prompt, load_episodes
from .proposer_rubric import score_package
from .proposer_schema import (
    PACKAGE_FIELDS,
    PACKAGE_VERSION,
    RATIFICATION_AUDIENCE,
    RATIFICATION_TYPE,
    TASK_KINDS,
)
from .proposer_simulation import (
    CI_LOWER_FLOOR,
    NONINFERIORITY_MARGIN,
    bootstrap_ci_lower,
    extract_package,
)
from .proposer_validator import validate_package

PROPOSER_JSON_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": list(PACKAGE_FIELDS),
    "properties": {
        "package_version": {"type": "string", "enum": [PACKAGE_VERSION]},
        "proposal_id": {"type": "string", "minLength": 1},
        "task_kind": {"type": "string", "enum": list(TASK_KINDS)},
        "claim": {"type": "string", "minLength": 10},
        "rationale": {"type": "string", "minLength": 10},
        "options_considered": {
            "type": "array",
            "minItems": 2,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["name", "assessment"],
                "properties": {
                    "name": {"type": "string", "minLength": 1},
                    "assessment": {"type": "string", "minLength": 5},
                },
            },
        },
        "recommended_option": {"type": "string", "minLength": 1},
        "cost_estimate": {
            "type": "object",
            "additionalProperties": False,
            "required": ["calls", "wall_seconds", "cost_units"],
            "properties": {
                "calls": {"type": "integer", "minimum": 0},
                "wall_seconds": {"type": "integer", "minimum": 1},
                "cost_units": {"type": "number", "minimum": 0},
            },
        },
        "cost_ceiling": {
            "type": "object",
            "additionalProperties": False,
            "required": ["max_calls", "max_wall_seconds", "max_cost_units"],
            "properties": {
                "max_calls": {"type": "integer", "minimum": 1},
                "max_wall_seconds": {"type": "integer", "minimum": 1},
                "max_cost_units": {"type": "number", "minimum": 0.001},
            },
        },
        "evidence": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["artifact", "sha256"],
                "properties": {
                    "artifact": {"type": "string", "minLength": 1},
                    "sha256": {"type": "string"},
                },
            },
        },
        "preregistration": {
            "type": "object",
            "additionalProperties": False,
            "required": ["link", "artifact_sha256"],
            "properties": {
                "link": {"type": "string", "minLength": 1},
                "artifact_sha256": {"type": "string"},
            },
        },
        "risks": {
            "type": "array",
            "minItems": 2,
            "items": {"type": "string", "minLength": 3},
        },
        "uncertainties": {
            "type": "array",
            "minItems": 1,
            "items": {"type": "string", "minLength": 3},
        },
        "stop_controls": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "abort_conditions",
                "sealed_target_status",
                "no_auto_retry",
                "stop_visible",
            ],
            "properties": {
                "abort_conditions": {
                    "type": "array",
                    "minItems": 2,
                    "items": {"type": "string", "minLength": 3},
                },
                "sealed_target_status": {"type": "string", "minLength": 1},
                "no_auto_retry": {"type": "boolean", "enum": [True]},
                "stop_visible": {"type": "boolean", "enum": [True]},
            },
        },
        "ratification": {
            "type": "object",
            "additionalProperties": False,
            "required": ["type", "audience"],
            "properties": {
                "type": {"type": "string", "enum": [RATIFICATION_TYPE]},
                "audience": {
                    "type": "array",
                    "minItems": 3,
                    "maxItems": 3,
                    "items": {"type": "string", "enum": list(RATIFICATION_AUDIENCE)},
                },
            },
        },
    },
}


STAGE1_V2_SYSTEM = (
    "Output ONE compact minified single-line JSON object matching ace.proposal.v1. "
    "Copy EVERY evidence artifact name and 64-hex sha256 string verbatim from the prompt, "
    "include ALL listed options including do_not_run, set no_auto_retry=true and stop_visible=true, "
    "and keep cost_estimate within cost_ceiling."
)


def schema_digest() -> str:
    canonical = json.dumps(PROPOSER_JSON_SCHEMA, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_v2_messages(episode):
    return [
        {"role": "system", "content": STAGE1_V2_SYSTEM},
        {"role": "user", "content": build_prompt(episode)},
    ]


def build_repair_messages(episode, failed_raw, reasons):
    return [
        {"role": "system", "content": STAGE1_V2_SYSTEM},
        {"role": "user", "content": build_prompt(episode)},
        {"role": "assistant", "content": failed_raw},
        {
            "role": "user",
            "content": (
                "Fail-closed validator REJECTED your package with reasons:\n- "
                + "\n- ".join(reasons)
                + "\nFix ONLY these validation failures and output ONE compact minified JSON object."
            ),
        },
    ]


def call_local_brain(messages, *, url, token, model_alias,
                     max_tokens=1300, temperature=0.0, seed=42, timeout=900):
    payload = {
        "model": model_alias,
        "messages": messages,
        "temperature": temperature,
        "seed": seed,
        "max_tokens": max_tokens,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "ace_proposal_v1",
                "strict": True,
                "schema": PROPOSER_JSON_SCHEMA,
            },
        },
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
    )
    t0 = time.monotonic()
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read())
    wall = round(time.monotonic() - t0, 2)
    text = data["choices"][0]["message"]["content"]
    return {
        "text": text,
        "wall_seconds": wall,
        "usage": data.get("usage"),
        "timings": data.get("timings"),
    }


def evaluate_arm(generations_dir, outcomes_path, walls_path=None,
                 *, arm_label="grammar_only"):
    episodes = load_episodes()
    with open(outcomes_path, encoding="utf-8") as fh:
        outcomes = json.load(fh)["outcomes"]
    walls = {}
    if walls_path and os.path.exists(walls_path):
        with open(walls_path, encoding="utf-8") as fh:
            walls = json.load(fh)
    per_episode = []
    for ep in episodes:
        eid = ep["episode_id"]
        raw_path = os.path.join(generations_dir, eid + ".txt")
        raw = open(raw_path, encoding="utf-8").read() if os.path.exists(raw_path) else ""
        pkg = extract_package(raw) if raw else None
        gen_sha = hashlib.sha256(raw.encode("utf-8")).hexdigest() if raw else None
        if pkg is None:
            p_score, p_break = 0.0, {"generation": "UNPARSEABLE_OR_MISSING"}
            accepted, v_reasons = False, ["no parseable package"]
        else:
            accepted, v_reasons = validate_package(pkg)
            p_score, p_break = score_package(pkg, ep)
        hist_pkg = outcomes[eid]["historical_package"]
        h_score, h_break = score_package(hist_pkg, ep)
        per_episode.append({
            "episode_id": eid,
            "generation_sha256": gen_sha,
            "generation_wall_seconds": walls.get(eid),
            "validator_accepted": accepted,
            "validator_reasons": v_reasons,
            "proposer_score": p_score,
            "proposer_breakdown": p_break,
            "historical_score": h_score,
            "historical_breakdown": h_break,
            "diff": p_score - h_score,
            "outcome_revealed_after_scoring": outcomes[eid]["outcome"],
        })
    diffs = [r["diff"] for r in per_episode]
    mean_diff = statistics.fmean(diffs) if diffs else None
    ci_lower = bootstrap_ci_lower(diffs)
    quality_pass = (
        mean_diff is not None
        and mean_diff >= NONINFERIORITY_MARGIN
        and ci_lower is not None
        and ci_lower >= CI_LOWER_FLOOR
    )
    return {
        "simulation": "proposer_stage1_v2",
        "arm": arm_label,
        "review_type": "SIMULATION - no proposal was dispatched or executed",
        "schema_digest": schema_digest(),
        "episodes": per_episode,
        "mean_diff": mean_diff,
        "bootstrap_ci_lower_95": ci_lower,
        "noninferiority_margin": NONINFERIORITY_MARGIN,
        "ci_lower_floor": CI_LOWER_FLOOR,
        "quality_clause": "PASS" if quality_pass else "FAIL",
        "time_clause": "NOT_ASSESSABLE - no historical drafting-time baseline exists in the official record",
        "exit_gate_verdict": "PARTIAL" if quality_pass else "NOT_PASSED",
    }
