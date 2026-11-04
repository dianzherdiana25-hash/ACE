"""Evaluator-side lock admission and transaction-backed execution."""

import hashlib
import json
from collections import Counter
from dataclasses import dataclass, replace
from pathlib import Path

from ..contract import canonical_json, parse_fit_request, read_json, require_fields, integer
from ..isolation import CandidateWallTimeout, InvalidCandidateAST, _SOLVER_FILES
from .bank import Episode
from .reference_arm import POLICY as REFERENCE, evaluate_reference
from .run_ledger import Arm, CandidateFailure, RunPlan, run_arms
from .selection_budget import CPU_US, WALL_US, evaluate_arm

POLICIES = ("fixed", "structured", "enumerative", "beam", "c_extend", "c_no_extend",
            "c_no_transfer", "c_sham", REFERENCE)
MODES = ("public_dry_run", "sealed_evaluation")
ORDER_SEED = 131510
REPO = Path(__file__).resolve().parents[3]
PACKAGE = Path(__file__).resolve().parents[1]
EVALUATOR_FILES = (
    "isolation.py", "informed_reference.py", "patterns.py", "evaluator/locked_runner.py",
    "evaluator/reference_arm.py", "evaluator/run_ledger.py", "evaluator/selection_budget.py",
    "evaluator/paired_analysis.py",
)


@dataclass(frozen=True)
class StudyEpisode:
    block: str
    episode: str
    fixture: Episode
    hypotheses: tuple[dict, ...]


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def _source_digest(names):
    return digest(canonical_json({name: digest((PACKAGE / name).read_bytes()) for name in names}))


def candidate_digest():
    return _source_digest(_SOLVER_FILES)


def evaluator_digest():
    return _source_digest(EVALUATOR_FILES)


def _key(item):
    return item.fixture.family, item.fixture.regime, item.block, item.episode


def bank_digest(episodes):
    return digest(canonical_json([
        [_key(item), json.loads(item.fixture.fit_request), item.hypotheses,
         [[(json.loads(probe.input), probe.expected) for probe in probes]
          for probes in (item.fixture.in_distribution, item.fixture.extrapolation)]]
        for item in sorted(episodes, key=_key)
    ]))


def make_plan(episodes, oracle, protocol, *, mode):
    if mode not in MODES:
        raise ValueError("unknown lock mode")
    if not episodes or len({_key(item) for item in episodes}) != len(episodes):
        raise ValueError("missing or duplicated study episodes")
    by_block = Counter(_key(item)[:3] for item in episodes)
    if mode == "sealed_evaluation":
        expected = Counter({(f, r): 48 for f in ("S", "G") for r in ("related", "unrelated")})
        if any(n != 2 for n in by_block.values()) or Counter(key[:2] for key in by_block) != expected:
            raise ValueError("sealed bank does not match the prespecified block design")
    for item in episodes:
        request = parse_fit_request(item.fixture.fit_request)
        if (request.family != item.fixture.family or len(item.fixture.in_distribution) != 4
                or len(item.fixture.extrapolation) != 4 or not 2 <= len(item.hypotheses) <= 64):
            raise ValueError("invalid study episode shape")
    arms = tuple(Arm(*_key(item), seed, policy) for item in sorted(episodes, key=_key)
                 for seed in (0, 1, 2) for policy in POLICIES)
    return RunPlan(candidate_digest(), bank_digest(episodes), digest(oracle), digest(protocol),
                   ORDER_SEED, 8, arms)


def verify_lock(raw, expected_digest, plan, audit_raw, *, mode):
    if digest(raw) != expected_digest:
        raise ValueError("lock digest does not match the external anchor")
    lock = read_json(raw, 16_384)
    require_fields(lock, "version", "mode", "plan_sha256", "evaluator_sha256",
                   "audit_sha256", "cpu_us", "wall_us", "overhead_cpu_us", "overhead_wall_us")
    integer(lock["version"], 1, 1)
    if (lock["mode"] != mode or lock["plan_sha256"] != plan.sha256
            or lock["evaluator_sha256"] != evaluator_digest()
            or lock["audit_sha256"] != digest(audit_raw)):
        raise ValueError("lock does not bind the live plan, evaluator and audit")

    audit = read_json(audit_raw, 16_384)
    require_fields(audit, "mode", "bank_sha256", "oracle_sha256", "integrity", "novelty",
                   "ambiguity", "independence", "custody")
    if (audit["mode"] != mode or audit["bank_sha256"] != plan.bank_sha256
            or audit["oracle_sha256"] != plan.oracle_sha256
            or any(audit[gate] != "pass" for gate in
                   ("integrity", "novelty", "ambiguity", "independence", "custody"))):
        raise ValueError("bank audit gates did not pass")

    for name, limit in (("cpu_us", CPU_US), ("wall_us", WALL_US)):
        overhead = integer(lock[f"overhead_{name}"], 1, 10**12)
        available = integer(lock[name], 1, 10**12)
        if available < len(plan.arms) * limit + overhead:
            raise ValueError("declared compute does not cover the locked arm ceiling and overhead")


def _evaluate(arm, item):
    seed = int.from_bytes(hashlib.sha256(canonical_json(
        ["ACE-E13-v1", arm.family, arm.block, arm.episode, arm.seed_slot],
    )).digest()[:4], "big")
    request = json.loads(item.fixture.fit_request)
    request["seed"] = seed
    episode = replace(item.fixture, fit_request=canonical_json(request))
    try:
        row = (evaluate_reference(episode, item.hypotheses) if arm.policy == REFERENCE
               else evaluate_arm(episode, arm.policy, keep_trace=True))
    except CandidateWallTimeout as error:
        raise CandidateFailure("candidate_timeout") from error
    except InvalidCandidateAST as error:
        raise CandidateFailure("invalid_ast") from error
    return {**row, "status": "scored", "algorithm_seed": seed,
            "correct": sum(score["correct"] for score in row["scores"].values()),
            "total": sum(score["total"] for score in row["scores"].values())}


def run_locked(path, episodes, oracle_path, protocol, audit_raw, lock_raw, lock_sha256, *, mode):
    """Run a precommitted plan. The external lock anchor comes from evaluator custody."""
    oracle_path = oracle_path.resolve(strict=True)
    if mode == "sealed_evaluation" and (oracle_path.is_relative_to(REPO)
                                          or path.resolve().is_relative_to(REPO)):
        raise ValueError("sealed evaluator and ledger must be outside candidate checkout")
    plan = make_plan(episodes, oracle_path.read_bytes(), protocol, mode=mode)
    verify_lock(lock_raw, lock_sha256, plan, audit_raw, mode=mode)
    by_key = {_key(item): item for item in episodes}
    return run_arms(path, plan, lambda arm: _evaluate(
        arm, by_key[arm.family, arm.regime, arm.block, arm.episode],
    ))
