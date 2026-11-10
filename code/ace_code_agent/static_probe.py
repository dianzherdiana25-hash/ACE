"""Public, read-only diagnostics for bounded three-input AI predicates.

Never compiles, imports or executes model-provided Python source. A tiny
whitelisted AST is interpreted with explicit node/value budgets. These public
probes are NOT a sealed evaluator and can never authorize ACCEPTED/promotion.
"""
from __future__ import annotations

import ast
import hashlib
from typing import Dict

MAX_NODES = 128
MAX_STEPS = 256
MAX_ABS_VALUE = 1_000_000

_ALLOWED_NODES = (
    ast.Module, ast.FunctionDef, ast.arguments, ast.arg, ast.Assign, ast.If,
    ast.Return, ast.Name, ast.Load, ast.Store, ast.Constant, ast.IfExp, ast.Call,
    ast.BinOp, ast.Add, ast.Sub, ast.Mult, ast.Mod, ast.FloorDiv,
    ast.BoolOp, ast.And, ast.Or, ast.UnaryOp, ast.Not, ast.UAdd, ast.USub,
    ast.Compare, ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE,
)


class UnsafeOrUnsupported(ValueError):
    """Candidate cannot be interpreted under the closed arithmetic grammar."""


class _Budget:
    def __init__(self):
        self.left = MAX_STEPS

    def tick(self):
        self.left -= 1
        if self.left < 0:
            raise UnsafeOrUnsupported("interpreter operation budget exceeded")


def _integer(value):
    if type(value) not in (int, bool) or abs(int(value)) > MAX_ABS_VALUE:
        raise UnsafeOrUnsupported("non-integer or over-budget intermediate value")
    return int(value)


def _expression(node, env, budget):
    budget.tick()
    if isinstance(node, ast.Constant):
        return _integer(node.value)
    if isinstance(node, ast.Call):
        # This is an interpreter primitive, NOT a Python function invocation.
        # Never resolve names, objects, attributes, keywords or callables.
        if (not isinstance(node.func, ast.Name) or node.func.id != "int"
                or len(node.args) != 1 or node.keywords):
            raise UnsafeOrUnsupported("only bounded int(expression) conversion allowed")
        return _integer(_expression(node.args[0], env, budget))
    if isinstance(node, ast.Name):
        if node.id not in env:
            raise UnsafeOrUnsupported("undefined variable")
        return _integer(env[node.id])
    if isinstance(node, ast.IfExp):
        branch = node.body if _expression(node.test, env, budget) else node.orelse
        return _expression(branch, env, budget)
    if isinstance(node, ast.UnaryOp):
        v = _expression(node.operand, env, budget)
        if isinstance(node.op, ast.Not):
            return int(not v)
        if isinstance(node.op, ast.USub):
            return _integer(-v)
        if isinstance(node.op, ast.UAdd):
            return _integer(v)
    if isinstance(node, ast.BoolOp):
        if isinstance(node.op, ast.And):
            for n in node.values:
                v = _expression(n, env, budget)
                if not v:
                    return 0
            return _integer(v)
        if isinstance(node.op, ast.Or):
            for n in node.values:
                v = _expression(n, env, budget)
                if v:
                    return _integer(v)
            return 0
    if isinstance(node, ast.BinOp):
        left = _expression(node.left, env, budget)
        right = _expression(node.right, env, budget)
        if isinstance(node.op, ast.Add):
            return _integer(left + right)
        if isinstance(node.op, ast.Sub):
            return _integer(left - right)
        if isinstance(node.op, ast.Mult):
            return _integer(left * right)
        if isinstance(node.op, (ast.Mod, ast.FloorDiv)):
            if right == 0:
                raise UnsafeOrUnsupported("division by zero")
            return _integer(left % right if isinstance(node.op, ast.Mod) else left // right)
    if isinstance(node, ast.Compare):
        left = _expression(node.left, env, budget)
        for op, comp in zip(node.ops, node.comparators):
            right = _expression(comp, env, budget)
            if isinstance(op, ast.Eq):
                ok = left == right
            elif isinstance(op, ast.NotEq):
                ok = left != right
            elif isinstance(op, ast.Lt):
                ok = left < right
            elif isinstance(op, ast.LtE):
                ok = left <= right
            elif isinstance(op, ast.Gt):
                ok = left > right
            elif isinstance(op, ast.GtE):
                ok = left >= right
            else:
                raise UnsafeOrUnsupported("comparison not allowed")
            if not ok:
                return 0
            left = right
        return 1
    raise UnsafeOrUnsupported("unsupported expression")


def _statements(body, env, budget):
    for statement in body:
        budget.tick()
        if isinstance(statement, ast.Return):
            return True, _integer(_expression(statement.value, env, budget))
        if isinstance(statement, ast.Assign):
            if len(statement.targets) != 1 or not isinstance(statement.targets[0], ast.Name):
                raise UnsafeOrUnsupported("assignment target not allowed")
            name = statement.targets[0].id
            if name in ("length", "density", "stride_val") or name.startswith("__"):
                raise UnsafeOrUnsupported("cannot reassign inputs or internals")
            env[name] = _expression(statement.value, env, budget)
        elif isinstance(statement, ast.If):
            selected = statement.body if _expression(statement.test, env, budget) else statement.orelse
            returned, value = _statements(selected, env, budget)
            if returned:
                return True, value
        else:
            raise UnsafeOrUnsupported("unsupported statement")
    return False, None


def parse_candidate(source: str):
    if not isinstance(source, str) or len(source) > 8000:
        raise UnsafeOrUnsupported("candidate source budget exceeded")
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError, RecursionError) as exc:
        raise UnsafeOrUnsupported("invalid source syntax") from exc
    nodes = list(ast.walk(tree))
    if len(nodes) > MAX_NODES or any(not isinstance(n, _ALLOWED_NODES) for n in nodes):
        raise UnsafeOrUnsupported("candidate outside closed arithmetic grammar")
    if len(tree.body) != 1 or not isinstance(tree.body[0], ast.FunctionDef):
        raise UnsafeOrUnsupported("requires exactly one function")
    for node in nodes:
        if isinstance(node, ast.Call) and (
            not isinstance(node.func, ast.Name) or node.func.id != "int"
            or len(node.args) != 1 or node.keywords
        ):
            raise UnsafeOrUnsupported("only bounded int(expression) conversion allowed")
    fn = tree.body[0]
    if not fn.name.startswith(("ace_ai_synthesized_", "ace_v04_")):
        raise UnsafeOrUnsupported("unknown candidate entrypoint")
    args = fn.args
    if ([a.arg for a in args.args] != ["length", "density", "stride_val"]
            or args.posonlyargs or args.kwonlyargs or args.vararg or args.kwarg
            or args.defaults or any(args.kw_defaults) or fn.decorator_list
            or fn.type_comment or bool(getattr(fn, "type_params", []))):
        raise UnsafeOrUnsupported("candidate signature must be exactly three bounded integers")
    # Annotations never execute; only the literal built-in int annotation is allowed.
    if any(a.annotation is not None and (
            not isinstance(a.annotation, ast.Name) or a.annotation.id != "int")
            for a in args.args):
        raise UnsafeOrUnsupported("unsupported input annotation")
    if fn.returns is not None and (
            not isinstance(fn.returns, ast.Name) or fn.returns.id != "int"):
        raise UnsafeOrUnsupported("unsupported return annotation")
    return fn


def interpret(fn, length: int, density: int, stride_val: int) -> int:
    inputs = (length, density, stride_val)
    if any(type(x) is not int or not 0 <= x <= 32 for x in inputs):
        raise UnsafeOrUnsupported("inputs outside bounded diagnostic domain")
    env = dict(zip(("length", "density", "stride_val"), inputs))
    found, value = _statements(fn.body, env, _Budget())
    if not found or value not in (0, 1):
        raise UnsafeOrUnsupported("candidate must return a binary integer on all probes")
    return value


def public_diagnostic(source: str) -> Dict[str, float]:
    """Score the actual candidate on public tests; never admit or execute code.

    Scores are diagnostic only. Three-input functions cannot independently
    dispatch between distinct tasks, and the strong family-specific upper
    baseline is the rule itself. No hidden labels, release, or capability gain.
    """
    fn = parse_candidate(source)
    probes = [(l, d, s) for l in (3, 4, 5, 6, 8, 11)
              for d in (1, 2, 3, 4) for s in (0, 1, 2, 3)]
    hits = {"modular": 0, "parity": 0, "joint": 0}
    weak = {"modular": 0, "parity": 0, "joint": 0}
    for l, d, s in probes:
        prediction = interpret(fn, l, d, s)
        modular = int((2 * s - d) % 3 == 0)
        parity = int(d % 2 == 0 and l >= 4)
        labels = {"modular": modular, "parity": parity, "joint": int(modular and parity)}
        root_prediction = int(l % 3 == 0)
        for family, label in labels.items():
            hits[family] += prediction == label
            weak[family] += root_prediction == label
    total = len(probes)
    return {
        "public_probe_count": float(total),
        "public_modular_candidate": round(hits["modular"] / total, 4),
        "public_modular_root": round(weak["modular"] / total, 4),
        "public_parity_candidate": round(hits["parity"] / total, 4),
        "public_parity_root": round(weak["parity"] / total, 4),
        "public_joint_candidate": round(hits["joint"] / total, 4),
        "public_joint_root": round(weak["joint"] / total, 4),
        "public_strong_baseline": 1.0,
        "independent_confirmation": 0.0,
        "connected_to_active_algorithm": 0.0,
        "candidate_python_executed": 0.0,
    }


def public_behavior_digest(source: str) -> str:
    """Fingerprint public-probe predictions; matches do NOT prove full equivalence.

    This digest is neither a model-identity check nor an independent test receipt.
    The closed AST interpreter is the sole evaluator of untrusted candidates.
    """
    fn = parse_candidate(source)
    output = bytearray()
    for length in (3, 4, 5, 6, 8, 11):
        for density in (1, 2, 3, 4):
            for stride_val in (0, 1, 2, 3):
                output.append(interpret(fn, length, density, stride_val))
    return hashlib.sha256(bytes(output)).hexdigest()
