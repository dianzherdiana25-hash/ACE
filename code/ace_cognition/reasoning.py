"""Bounded data-only reasoning integration; no model calls or Python source execution.

Reuses ComponentSynthesizer and ExperienceMemory. Empirical staging means exact
development fit, never semantic correctness, deployment or scientific promotion.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import time

from ace_component_synthesis import component_synthesizer as upstream
from ace_selfmodel.memory import ExperienceMemory

SCHEMA = "ace.reasoning.xy.v1"
OPS = ("add", "sub", "mul", "eq", "lt")


def canonical(data):
    return json.dumps(data, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(data):
    return hashlib.sha256(canonical(data).encode()).hexdigest()


def implementation_digest():
    return digest([hashlib.sha256(Path(p).read_bytes()).hexdigest()
                   for p in (__file__, upstream.__file__)])


def _scalar(value):
    if type(value) not in (int, bool):
        raise ValueError("only strict integer/Boolean values are supported")
    if type(value) is int and abs(value) > 1_000_000:
        raise ValueError("intermediate magnitude limit exceeded")
    return value


def validate_inputs(env):
    if type(env) is not dict or set(env) != {"x", "y"}:
        raise ValueError("inputs require exactly x and y")
    if any(type(v) is not int or abs(v) > 64 for v in env.values()):
        raise ValueError("x/y must be integers in [-64,64]")


@dataclass(frozen=True)
class Problem:
    problem_id: str
    goal: str
    train: tuple
    validation: tuple

    @classmethod
    def from_data(cls, data):
        if type(data) is not dict or set(data) != {"schema", "id", "goal", "train", "validation"}:
            raise ValueError("invalid problem schema; terminal data is not accepted")
        if data["schema"] != SCHEMA:
            raise ValueError("unsupported problem domain")
        for key, limit in (("id", 80), ("goal", 400)):
            if type(data[key]) is not str or not 1 <= len(data[key]) <= limit:
                raise ValueError("invalid problem id/goal")
        splits = []
        output_types = set()
        for name in ("train", "validation"):
            rows = data[name]
            if type(rows) is not list or not 1 <= len(rows) <= 64:
                raise ValueError("each development split requires 1..64 rows")
            normalized = []
            seen = {}
            for row in rows:
                if type(row) is not dict or set(row) != {"inputs", "output"}:
                    raise ValueError("invalid observation")
                validate_inputs(row["inputs"])
                _scalar(row["output"])
                output_types.add(type(row["output"]))
                k = canonical(row["inputs"])
                if k in seen:
                    raise ValueError("duplicate or contradictory development observation")
                seen[k] = row["output"]
                normalized.append((dict(row["inputs"]), row["output"]))
            splits.append(tuple(normalized))
        if len(output_types) != 1:
            raise ValueError("mixed output types")
        if {canonical(e) for e, _ in splits[0]} & {canonical(e) for e, _ in splits[1]}:
            raise ValueError("training and validation overlap")
        return cls(data["id"], data["goal"], *splits)


# The upstream valuation helper catches Exception. A dedicated control-flow
# exception must escape it so a hard primitive budget cannot become a failed
# candidate followed by more computation. Never catch KeyboardInterrupt/SystemExit.
class BudgetExhausted(BaseException):
    pass


class Meter:
    def __init__(self, operations=300_000, seconds=5.0):
        if type(operations) is not int or not 1 <= operations <= 300_000:
            raise ValueError("operation budget must be 1..300000")
        if type(seconds) not in (int, float) or not 0 < seconds <= 5:
            raise ValueError("wall budget must be in (0,5]")
        self.limit = operations
        self.used = 0
        self.start = time.monotonic()
        self.deadline = self.start + seconds

    def check(self):
        if time.monotonic() >= self.deadline:
            raise BudgetExhausted("WALL_BUDGET")

    def charge(self):
        self.check()
        if self.used >= self.limit:
            raise BudgetExhausted("OPERATION_BUDGET")
        self.used += 1

    def library(self):
        old = upstream.ComponentLibrary.default()
        lib = upstream.ComponentLibrary()
        for name in OPS:
            comp = old.get(name)

            def checked(*args, fn=comp.fn):
                self.charge()
                return _scalar(fn(*args))

            lib.register(upstream.Component(comp.name, comp.arg_types, comp.return_type,
                                            checked, comp.to_code_fn, comp.description))
        return lib


def encode_program(node):
    if node.node_type == "VAR":
        return {"var": node.val}
    if node.node_type == "CONST":
        return {"const": node.val}
    return {"op": node.name, "args": [encode_program(c) for c in node.children]}


def decode_program(data, library):
    """Closed typed IR only. Never deserializes functions, classes or source."""
    remaining = [31]

    def walk(d, depth):
        remaining[0] -= 1
        if remaining[0] < 0 or depth > 4 or type(d) is not dict:
            raise ValueError("program node/depth limit exceeded")
        if set(d) == {"var"} and type(d["var"]) is str and d["var"] in ("x", "y"):
            return upstream.ComponentNode(d["var"], "int", "VAR", val=d["var"])
        if set(d) == {"const"}:
            val = _scalar(d["const"])
            if type(val) is int and abs(val) > 4:
                raise ValueError("constant outside grammar")
            return upstream.ComponentNode(str(val), "bool" if type(val) is bool else "int", "CONST", val=val)
        if (set(d) != {"op", "args"} or type(d["op"]) is not str or
                d["op"] not in OPS or type(d["args"]) is not list):
            raise ValueError("unsupported program syntax/operator")
        comp = library.get(d["op"])
        if len(d["args"]) != len(comp.arg_types):
            raise ValueError("invalid operator arity")
        children = [walk(c, depth + 1) for c in d["args"]]
        if tuple(c.return_type for c in children) != comp.arg_types:
            raise ValueError("operator type mismatch")
        return upstream.ComponentNode(comp.name, comp.return_type, children=children, component=comp)

    return walk(data, 1)


def predict(program, inputs, meter=None):
    validate_inputs(inputs)
    meter = meter or Meter()
    meter.check()
    return _scalar(decode_program(program, meter.library()).evaluate(inputs))


def verify_development(node, problem, meter):
    """Verifier receives only development observations; first counterexample kept."""
    for split, rows in (("train", problem.train), ("validation", problem.validation)):
        for env, expected in rows:
            meter.check()
            try:
                actual = _scalar(node.evaluate(env))
            except (ValueError, ArithmeticError):
                actual = None
            if type(actual) is not type(expected) or actual != expected:
                return {"split": split, "inputs": env, "expected": expected, "actual": actual}
    return None


class ReasoningMemory:
    """Executable knowledge and trial evidence on the existing SQLite memory.

    Checksums detect corruption; they are NOT independent evaluator signatures.
    Each recalled program must pass new development observations before reuse.
    """
    def __init__(self, workspace):
        self.base = ExperienceMemory(Path(workspace))
        self.db = self.base.db
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS reasoning_knowledge(
                digest TEXT PRIMARY KEY, payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS reasoning_trials(
                digest TEXT PRIMARY KEY, payload TEXT NOT NULL);
        """)

    def close(self):
        self.base.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def recall(self):
        self.base.verify()
        count = self.db.execute("SELECT count(*) FROM reasoning_knowledge").fetchone()[0]
        if count > 128:
            raise ValueError("memory budget exceeded")
        records = []
        for row in self.db.execute("SELECT digest,payload FROM reasoning_knowledge ORDER BY digest"):
            body = json.loads(row["payload"])
            if digest(body) != row["digest"]:
                raise ValueError("knowledge checksum mismatch")
            if body["implementation"] != implementation_digest():
                raise ValueError("knowledge implementation changed; explicit migration required")
            decode_program(body["program"], Meter().library())
            records.append(body)
        return records

    def record(self, problem, outcome):
        body = {"problem_id": problem.problem_id, "train": problem.train,
                "validation": problem.validation, "implementation": implementation_digest(),
                "scope": SCHEMA, "outcome": outcome}
        # One transaction commits the decision, support and executable knowledge.
        self.db.execute("BEGIN IMMEDIATE")
        try:
            if self.db.execute("SELECT count(*) FROM reasoning_trials").fetchone()[0] >= 1024:
                raise ValueError("trial storage budget exceeded")
            self.db.execute("INSERT OR IGNORE INTO reasoning_trials VALUES (?,?)", (digest(body), canonical(body)))
            if outcome["status"] == "STAGED_EMPIRICAL":
                knowledge = {k: body[k] for k in ("implementation", "scope", "train", "validation")}
                knowledge.update(program=outcome["program"], origin=outcome["origin"],
                                 problem_id=problem.problem_id, evidence_status="DEVELOPMENT_ONLY")
                key = digest(knowledge)
                if self.db.execute("SELECT count(*) FROM reasoning_knowledge").fetchone()[0] >= 128:
                    raise ValueError("knowledge storage budget exceeded")
                self.db.execute("INSERT OR IGNORE INTO reasoning_knowledge VALUES (?,?)", (key, canonical(knowledge)))
            self.db.commit()
        except BaseException:
            self.db.rollback()
            raise


def solve(problem, *, memory=None, advice=(), max_operations=300_000, seconds=5.0):
    """Represent -> recall/advice -> internal synthesis -> verify -> consolidate.

    Advice is an iterable of CLOSED IR trees, never instructions or executable
    source. No external provider is called. A failed validation abstains.
    """
    if not isinstance(problem, Problem):
        problem = Problem.from_data(problem)
    if not isinstance(advice, (tuple, list)) or len(advice) > 4:
        raise ValueError("at most four advice trees")
    meter = Meter(max_operations, seconds)
    lib = meter.library()
    outcome = {"schema": SCHEMA, "problem_id": problem.problem_id,
               "status": "ABSTAIN", "reason": "NO_DEVELOPMENT_FIT", "program": None,
               "program_digest": None, "origin": None, "counterexamples": [],
               "search_candidates": 0, "primitive_operations": 0, "external_ai_calls": 0,
               "advice_trees_received": len(advice), "scientific_status": "NOT_ASSESSED",
               "release_gate": "BLOCK_RELEASE", "new_primitive_discovered": False,
               "trace": ["REPRESENTED"]}

    def consider(program, origin):
        try:
            node = decode_program(program, lib)
        except (ValueError, TypeError, KeyError):
            outcome["counterexamples"].append({"origin": origin, "reason": "INVALID_IR"})
            return False
        counterexample = verify_development(node, problem, meter)
        if counterexample:
            outcome["counterexamples"].append({"origin": origin, **counterexample})
            return False
        outcome.update(status="STAGED_EMPIRICAL", reason="EXACT_DEVELOPMENT_FIT_ONLY",
                       program=program, program_digest=digest(program), origin=origin)
        return True

    try:
        if memory:
            outcome["trace"].append("RECALL")
            for record in memory.recall():
                if consider(record["program"], "REVALIDATED_MEMORY"):
                    break
        if outcome["program"] is None:
            for tree in advice:
                if consider(tree, "EXTERNAL_ADVICE_UNVERIFIED"):
                    break
        if outcome["program"] is None:
            outcome["trace"].append("INTERNAL_COMPONENT_SYNTHESIS")
            fitted = upstream.ComponentSynthesizer(library=lib, max_level=2,
                                                  max_candidates=5000, timeout_sec=seconds).synthesize(problem.train)
            outcome["search_candidates"] = fitted.candidates_generated
            outcome["solver_status"] = fitted.status
            if fitted.program is not None:
                consider(encode_program(fitted.program), "INTERNAL_SYNTHESIS")
        outcome["trace"].append("DEVELOPMENT_VERIFIED" if outcome["program"] else "ABSTAINED")
    except BudgetExhausted as exc:
        outcome.update(status="ABSTAIN", reason=str(exc), program=None, program_digest=None, origin=None)
        # Upstream may stop before returning its count; never report zero as a
        # measurement of work that did occur. Primitive count remains exact.
        outcome["search_candidates"] = None
    except (ValueError, TypeError, KeyError) as exc:
        outcome.update(status="ABSTAIN", reason="INTEGRITY_OR_DOMAIN_ERROR:" + str(exc),
                       program=None, program_digest=None, origin=None)
        return outcome
    outcome["primitive_operations"] = meter.used
    if memory:
        memory.record(problem, outcome)
    return outcome
