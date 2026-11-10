"""Replay actual closed IR bytes; never turn a caller's claim into acceptance.

This is development evidence within one trust domain, not an independent oracle
or deployment authority. Unsupported source is stored without executing it.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from ace_cognition.reasoning import (BudgetExhausted, Meter, Problem, digest,
                                     implementation_digest, predict)

ARTIFACT_SCHEMA = "ace.mission.reasoning-candidate.v1"
MAX_ARTIFACT_BYTES = 65_536
REQUESTS = {"ACCEPTED", "STAGED_EMPIRICAL", "PENDING_EVALUATION", "INCONCLUSIVE",
            "REJECTED", "STAGNATED", "DUPLICATE_PATCH_SKIPPED"}
SPEC_FIELDS = ("schema_version", "id", "goal", "hypothesis", "task_family_ids",
               "inputs", "budget", "acceptance", "forbidden", "deadline",
               "reasoning_problem")


def evaluator_digest():
    """Local implementation identity, NOT a signature or independence claim."""
    return digest({"reasoning": implementation_digest(),
                   "admission": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                   "bus": hashlib.sha256(Path(__file__).with_name("bus.py").read_bytes()).hexdigest()})


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def evaluate_submission(mission, artifact_bytes, requested_decision):
    """Return a fresh receipt. No caller-provided receipt or callable is accepted."""
    if type(requested_decision) is not str or requested_decision not in REQUESTS:
        raise ValueError("unsupported mission decision")
    receipt = {
        "schema": "ace.mission.admission.v1", "mission_id": mission["id"],
        "mission_digest": digest({k: mission[k] for k in SPEC_FIELDS if k in mission}),
        "artifact_sha": hashlib.sha256(artifact_bytes).hexdigest(),
        "evaluator_digest": evaluator_digest(), "requested_decision": requested_decision,
        "decision": "PENDING_EVALUATION", "reason": "NO_BEHAVIORAL_EVALUATOR_FOR_SOURCE",
        "scope": "PROVIDED_DEVELOPMENT_ONLY", "scientific_status": "NOT_ASSESSED",
        "release_gate": "BLOCK_RELEASE", "independent_confirmation": False,
        "candidate_python_executed": False, "external_ai_calls": 0,
        "problem_digest": None, "program_digest": None,
        "primitive_operations": 0, "observations_evaluated": 0,
        "counterexample": None, "predictions": [],
    }
    if len(artifact_bytes) > MAX_ARTIFACT_BYTES:
        receipt.update(decision="REJECTED", reason="ARTIFACT_SIZE_LIMIT")
        return receipt
    if requested_decision not in {"ACCEPTED", "STAGED_EMPIRICAL"}:
        receipt.update(decision=requested_decision, reason="NO_SUCCESS_REQUESTED")
        return receipt
    if "reasoning_problem" not in mission:
        return receipt

    meter = None
    try:
        problem_data = mission["reasoning_problem"]
        problem = Problem.from_data(problem_data)
        receipt["problem_digest"] = digest(problem_data)
        # This gate cannot certify gains, graph tasks or other metrics.
        acceptance = mission["acceptance"]
        if (acceptance.get("metric") != "exact_development_fit" or
                type(acceptance.get("threshold")) not in (int, float) or
                acceptance["threshold"] != 1 or acceptance.get("comparator") != "none"):
            receipt["reason"] = "UNSUPPORTED_ACCEPTANCE_CRITERION"
            return receipt
        budget = mission["budget"]
        seconds = budget["time_sec"]
        if (type(seconds) not in (int, float) or not math.isfinite(seconds) or seconds <= 0 or
                type(budget["max_candidates"]) is not int or budget["max_candidates"] < 1):
            raise ValueError("invalid evaluation budget")
        meter = Meter(budget.get("max_primitive_operations", 300_000), min(seconds, 5.0))
        receipt["budget"] = {"max_primitive_operations": meter.limit,
                              "time_sec": min(seconds, 5.0), "candidate_evaluations": 1}
        artifact = json.loads(artifact_bytes, object_pairs_hook=_unique_object)
        if (type(artifact) is not dict or
                set(artifact) != {"schema", "problem_digest", "program"} or
                artifact["schema"] != ARTIFACT_SCHEMA or
                artifact["problem_digest"] != receipt["problem_digest"]):
            raise ValueError("artifact schema/problem binding mismatch")
        receipt["program_digest"] = digest(artifact["program"])
        receipt["program"] = artifact["program"]
        for split, rows in (("train", problem.train), ("validation", problem.validation)):
            for env, expected in rows:
                actual = predict(artifact["program"], env, meter)
                receipt["observations_evaluated"] += 1
                receipt["predictions"].append({"split": split, "inputs": env,
                                                "expected": expected, "actual": actual})
                if type(actual) is not type(expected) or actual != expected:
                    receipt.update(decision="REJECTED", reason="DEVELOPMENT_COUNTEREXAMPLE",
                                   counterexample=receipt["predictions"][-1])
                    return receipt
        receipt.update(decision="STAGED_EMPIRICAL", reason="EXACT_PROVIDED_DEVELOPMENT_FIT_ONLY")
    except BudgetExhausted as exc:
        receipt.update(decision="INCONCLUSIVE", reason=str(exc))
    except (ValueError, TypeError, KeyError, ArithmeticError, RecursionError) as exc:
        receipt.update(decision="REJECTED", reason="INVALID_CANDIDATE_OR_CONTRACT:" + str(exc)[:200])
    finally:
        if meter is not None:
            receipt["primitive_operations"] = meter.used
    return receipt
