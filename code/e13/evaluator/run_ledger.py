"""Transactional arm checkpoints for an evaluator process."""

import fcntl
import hashlib
import json
import os
import random
import re
import sqlite3
from contextlib import contextmanager
from dataclasses import asdict, dataclass

from ..contract import canonical_json


@dataclass(frozen=True)
class Arm:
    family: str
    regime: str
    block: str
    episode: str
    seed_slot: int
    policy: str

    @property
    def key(self):
        return canonical_json(asdict(self)).decode()


@dataclass(frozen=True)
class RunPlan:
    candidate_sha256: str
    bank_sha256: str
    oracle_sha256: str
    protocol_sha256: str
    order_seed: int
    probes_per_arm: int
    arms: tuple[Arm, ...]

    def __post_init__(self):
        bindings = (self.candidate_sha256, self.bank_sha256, self.oracle_sha256, self.protocol_sha256)
        if any(type(value) is not str or not re.fullmatch(r"[0-9a-f]{64}", value)
               for value in bindings):
            raise ValueError("plan digests must be lowercase SHA-256")
        if type(self.order_seed) is not int or not 0 <= self.order_seed < 2**32:
            raise ValueError("invalid arm order seed")
        if type(self.probes_per_arm) is not int or not 1 <= self.probes_per_arm <= 64:
            raise ValueError("invalid probe count")
        if not self.arms or len(set(self.arms)) != len(self.arms):
            raise ValueError("plan requires distinct arms")
        for arm in self.arms:
            if (arm.family not in ("S", "G") or arm.regime not in ("related", "unrelated")
                    or type(arm.seed_slot) is not int or arm.seed_slot not in (0, 1, 2)
                    or not all(type(value) is str and value for value in
                               (arm.block, arm.episode, arm.policy))):
                raise ValueError("invalid arm key")

    @property
    def sha256(self):
        return hashlib.sha256(canonical_json(asdict(self))).hexdigest()


class CandidateFailure(RuntimeError):
    """An adapter has attributed a failure to the candidate, with evidence."""

    def __init__(self, reason):
        if reason not in ("candidate_timeout", "invalid_ast"):
            raise ValueError("unclassified candidate failure")
        self.reason = reason
        super().__init__(reason)


@contextmanager
def _open(path):
    # Serialize whole runners while committing each finished arm independently.
    lock_path = path.with_name(path.name + ".lock")
    lock_fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError("run ledger is already in use") from error
        db_fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
        os.close(db_fd)
        connection = sqlite3.connect(path)
        try:
            yield connection
        finally:
            connection.close()
    finally:
        os.close(lock_fd)


def _bind(connection, plan):
    with connection:
        connection.execute("CREATE TABLE IF NOT EXISTS metadata (slot INTEGER PRIMARY KEY, digest TEXT)")
        connection.execute("CREATE TABLE IF NOT EXISTS result (arm TEXT PRIMARY KEY, score TEXT)")
        connection.execute("CREATE TABLE IF NOT EXISTS interruption (arm TEXT, kind TEXT)")
        saved = connection.execute("SELECT digest FROM metadata WHERE slot = 1").fetchone()
        if saved is None:
            connection.execute("INSERT INTO metadata VALUES (1, ?)", (plan.sha256,))
        elif saved != (plan.sha256,):
            raise ValueError("run plan does not match the ledger")


def _score(evaluate, arm, total):
    try:
        score = evaluate(arm)
    except CandidateFailure as error:
        return {"status": "candidate_failure", "correct": 0, "total": total, "reason": error.reason}
    if (type(score) is not dict or score.get("status") != "scored"
            or type(score.get("correct")) is not int or not 0 <= score["correct"] <= total
            or type(score.get("total")) is not int or score["total"] != total):
        raise ValueError("invalid evaluator score")
    return score


def run_arms(path, plan, evaluate):
    """Resume unresolved arms only, and return terminal rows in planned order.

    The evaluator adapter owns split custody and classification of candidate faults.
    An unclassified failure leaves its arm unresolved and stops the run.
    """
    schedule = list(plan.arms)
    random.Random(plan.order_seed).shuffle(schedule)
    allowed = {arm.key for arm in schedule}
    with _open(path) as connection:
        _bind(connection, plan)
        rows = {key: json.loads(score) for key, score in connection.execute("SELECT arm, score FROM result")}
        if not rows.keys() <= allowed:
            raise ValueError("ledger contains an unknown arm")
        for arm in schedule:
            key = arm.key
            if key in rows:
                continue
            try:
                score = _score(evaluate, arm, plan.probes_per_arm)
                with connection:
                    connection.execute("INSERT INTO result VALUES (?, ?)",
                                       (key, canonical_json(score).decode()))
            except (Exception, KeyboardInterrupt) as error:
                with connection:
                    connection.execute("INSERT INTO interruption VALUES (?, ?)",
                                       (key, type(error).__name__))
                raise
            rows[key] = score
        return [{**rows[arm.key], **asdict(arm)} for arm in schedule]
