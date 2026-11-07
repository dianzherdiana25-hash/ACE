"""Isolated evaluator process worker for ACE Host Boundary V2.

Executes untrusted candidate code inside a separate OS process:
- Receives ONLY task input queries: NO holdout ground-truth labels and NO signing keys.
- Audits AST against forbidden calls, forbidden imports, and reflection escapes.
- Compiles candidate code in a sandbox namespace with safe builtins only.
- Returns only boolean candidate predictions to stdout; parent process evaluates accuracy and signs receipts.
"""
from __future__ import annotations

import ast
import json
import sys
import time
from typing import Any, Callable, Dict, List

SAFE_BUILTINS = {
    "abs": abs,
    "all": all,
    "any": any,
    "bool": bool,
    "enumerate": enumerate,
    "int": int,
    "len": len,
    "max": max,
    "min": min,
    "range": range,
    "sorted": sorted,
    "str": str,
    "sum": sum,
    "tuple": tuple,
    "zip": zip,
    "None": None,
    "True": True,
    "False": False,
}

FORBIDDEN_CALLS = frozenset({
    "eval",
    "exec",
    "__import__",
    "open",
    "compile",
    "globals",
    "locals",
    "vars",
    "dir",
    "input",
    "breakpoint",
    "exit",
    "quit",
    "getattr",
    "setattr",
    "delattr",
})

FORBIDDEN_ATTRIBUTES = frozenset({
    "__class__",
    "__subclasses__",
    "__bases__",
    "__mro__",
    "__globals__",
    "__code__",
    "__closure__",
    "__dict__",
    "__builtins__",
    "__import__",
})


def audit_candidate_ast(source_code: str) -> None:
    """Strict AST validator disallowing imports, reflection, and unsafe calls."""
    try:
        tree = ast.parse(source_code)
    except SyntaxError as e:
        raise ValueError(f"Candidate source syntax error: {e}") from e

    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            raise ValueError("Imports are forbidden in isolated candidate execution")
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_CALLS:
                raise ValueError(f"Forbidden function call '{node.func.id}()'")
        if isinstance(node, ast.Attribute):
            if node.attr in FORBIDDEN_ATTRIBUTES:
                raise ValueError(f"Forbidden attribute access '{node.attr}'")


def compile_candidate_safe(source_code: str) -> Callable[..., bool]:
    """Audit AST and compile candidate source code in restricted namespace."""
    audit_candidate_ast(source_code)
    namespace: Dict[str, Any] = {"__builtins__": SAFE_BUILTINS}
    compiled = compile(source_code, "<candidate_isolated>", "exec")
    exec(compiled, namespace)

    if "candidate_fn" not in namespace or not callable(namespace["candidate_fn"]):
        raise ValueError("Candidate source must define callable 'candidate_fn'")
    return namespace["candidate_fn"]


def run_isolated_prediction(
    candidate_id: str,
    source_code: str,
    inputs_by_task: Dict[str, List[str]],
) -> Dict[str, Any]:
    """Execute candidate function on inputs without any ground-truth holdout labels."""
    t_start = time.monotonic()
    cand_fn = compile_candidate_safe(source_code)

    predictions_by_task: Dict[str, List[bool]] = {}
    for task_name, inputs in inputs_by_task.items():
        task_preds: List[bool] = []
        for inp in inputs:
            try:
                try:
                    pred = bool(cand_fn(inp, task_name))
                except TypeError:
                    pred = bool(cand_fn(inp))
            except Exception:
                pred = False
            task_preds.append(pred)
        predictions_by_task[task_name] = task_preds

    elapsed = time.monotonic() - t_start

    return {
        "candidate_id": candidate_id,
        "predictions_by_task": predictions_by_task,
        "execution_seconds": round(elapsed, 4),
        "isolation_mode": "SUBPROCESS_AST_RESTRICTED",
    }


def main() -> int:
    """CLI entrypoint reading candidate payload from stdin."""
    try:
        raw_input = sys.stdin.read()
        if not raw_input:
            print(json.dumps({"error": "Empty input payload"}))
            return 1
        data = json.loads(raw_input)

        candidate_id = data["candidate_id"]
        source_code = data["source_code"]
        inputs_by_task = data["inputs_by_task"]

        # Note: data MUST NOT contain signing_key_hex or holdout labels
        if "signing_key_hex" in data:
            print(json.dumps({"error": "Signing key leaked to isolated worker! Security boundary violation."}))
            return 1
        if "holdout_banks" in data:
            print(json.dumps({"error": "Holdout labels leaked to isolated worker! Security boundary violation."}))
            return 1

        result = run_isolated_prediction(
            candidate_id=candidate_id,
            source_code=source_code,
            inputs_by_task=inputs_by_task,
        )
        print(json.dumps(result))
        return 0
    except Exception as exc:
        print(json.dumps({"error": str(exc), "failed": True}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
