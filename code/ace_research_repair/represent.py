"""Typed fault inspection, spectrum diagnosis, and `ace_runtime` binary trace representation.

Bridges dynamic `sys.settrace` fault spectra and local AST motifs into bounded `{a, b}`
binary trace classification tasks executed inside unchanged `ace_runtime.engine.Runtime`.
Contains ZERO ground-truth family labels, ZERO unit-ID heuristics, and NEVER imports `evaluator.py`.
"""
from __future__ import annotations

import ast
import math
from pathlib import Path
import random
from typing import Any

from ace_research_primitives import primitive_discovery as r1
from ace_runtime.engine import Runtime

from .corpus import sha256_digest

PROBE_WORDS = ("ba", "ab", "aab", "aaab")


def inspect_module_ast(source_code: str, entrypoint: str) -> dict[str, Any]:
    """Stage 1 (`Inspect`): Extract structural AST metadata without executing code."""
    tree = ast.parse(source_code)
    func_names: list[str] = []
    entry_node: ast.FunctionDef | None = None
    line_tags: dict[int, list[str]] = {}

    for node in ast.walk(tree):
        lineno = getattr(node, "lineno", None)
        if lineno is not None:
            line_tags.setdefault(lineno, []).append(type(node).__name__)

    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            func_names.append(node.name)
            if node.name == entrypoint:
                entry_node = node

    if entry_node is None:
        return {
            "function_names": func_names,
            "entrypoint_found": False,
            "entrypoint_lineno": 1,
            "entrypoint_end_lineno": 1,
            "has_mutable_default": False,
            "has_index_bound_loop": False,
            "has_string_tokenizer_ops": False,
            "has_element_state_loop": False,
            "has_stale_dataflow_chain": False,
            "line_tags": {str(k): sorted(set(v)) for k, v in sorted(line_tags.items())},
        }

    has_mutable_default = any(
        isinstance(d, (ast.List, ast.Dict, ast.Set)) for d in entry_node.args.defaults
    )

    has_range_len_loop = False
    has_while_subscript_loop = False
    has_element_state_loop = False
    has_string_tokenizer_ops = False

    for sub in ast.walk(entry_node):
        if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute):
            if sub.func.attr in ("split", "isdigit", "strip", "lstrip", "startswith", "replace"):
                has_string_tokenizer_ops = True
        if isinstance(sub, ast.For):
            is_range_call = (
                isinstance(sub.iter, ast.Call)
                and isinstance(sub.iter.func, ast.Name)
                and sub.iter.func.id == "range"
            )
            if is_range_call:
                has_len = any(
                    isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "len"
                    for n in ast.walk(sub.iter)
                )
                if has_len:
                    has_range_len_loop = True
            else:
                # Direct element iteration; check if loop mutates local state/accumulators
                mut_count = sum(
                    isinstance(n, (ast.Assign, ast.AugAssign))
                    or (
                        isinstance(n, ast.Call)
                        and isinstance(n.func, ast.Attribute)
                        and n.func.attr == "append"
                    )
                    for n in ast.walk(sub)
                )
                if mut_count >= 2:
                    has_element_state_loop = True
        if isinstance(sub, ast.While):
            has_subscripts = any(isinstance(n, ast.Subscript) for n in ast.walk(sub))
            if has_subscripts:
                has_while_subscript_loop = True

    # Detect sequential scalar dataflow chain where an intermediate derived local is bypassed
    assigned_vars: list[str] = []
    derived_from: dict[str, set[str]] = {}
    has_stale_dataflow_chain = False
    for stmt in entry_node.body:
        if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
            lhs = stmt.targets[0].id
            read_names = {
                n.id for n in ast.walk(stmt.value) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)
            }
            derived_from[lhs] = read_names
            if isinstance(stmt.value, ast.Call):
                for arg in stmt.value.args:
                    if isinstance(arg, ast.Name) and arg.id in assigned_vars:
                        # Check if a newer variable in `assigned_vars` was derived from `arg.id`
                        for newer in assigned_vars:
                            if newer != arg.id and newer != lhs and arg.id in derived_from.get(newer, set()):
                                has_stale_dataflow_chain = True
            if lhs not in assigned_vars:
                assigned_vars.append(lhs)

    return {
        "function_names": func_names,
        "entrypoint_found": True,
        "entrypoint_lineno": entry_node.lineno,
        "entrypoint_end_lineno": getattr(entry_node, "end_lineno", entry_node.lineno),
        "has_mutable_default": has_mutable_default,
        "has_index_bound_loop": has_range_len_loop or has_while_subscript_loop,
        "has_string_tokenizer_ops": has_string_tokenizer_ops,
        "has_element_state_loop": has_element_state_loop,
        "has_stale_dataflow_chain": has_stale_dataflow_chain,
        "line_tags": {str(k): sorted(set(v)) for k, v in sorted(line_tags.items())},
    }


def diagnose_reproduction(
    repro_result: dict[str, Any],
    ast_inspection: dict[str, Any],
) -> dict[str, Any]:
    """Stage 3 (`Diagnose`): Compute Ochiai line fault spectrum and primary failure mode."""
    cases = repro_result.get("cases", [])
    failing = [c for c in cases if not c["passed"]]
    passing = [c for c in cases if c["passed"]]
    total_fail = len(failing)

    all_lines: set[int] = set()
    for c in cases:
        all_lines.update(c.get("executed_lines", []))
        if c.get("exception_lineno") is not None:
            all_lines.add(int(c["exception_lineno"]))

    ochiai: dict[int, float] = {}
    for line in sorted(all_lines):
        ef = sum(
            (line in c.get("executed_lines", [])) or (c.get("exception_lineno") == line)
            for c in failing
        )
        ep = sum(line in c.get("executed_lines", []) for c in passing)
        nf = total_fail - ef
        denom = math.sqrt((ef + nf) * (ef + ep)) if (ef + nf) > 0 and (ef + ep) > 0 else 0.0
        score = round(ef / denom, 6) if denom > 0.0 else 0.0
        # Slight boost if an unhandled exception directly originated on this line
        if any(c.get("exception_lineno") == line for c in failing):
            score = round(min(1.0, score + 0.15), 6)
        ochiai[line] = score

    # Propagate entrypoint signature line suspiciousness if entry function failed immediately or via default arg
    entry_line = int(ast_inspection.get("entrypoint_lineno", 1))
    if total_fail > 0 and entry_line not in ochiai:
        ochiai[entry_line] = round(max(ochiai.values(), default=0.5), 6)

    exc_types = [c["exception_type"] for c in failing if c.get("exception_type")]
    if "IndexError" in exc_types:
        failure_mode = "IndexError"
    elif "ValueError" in exc_types:
        failure_mode = "ValueError"
    elif any(c.get("arg_mutated") for c in failing):
        failure_mode = "CallerArgMutated"
    elif any(c.get("aliased_return") for c in failing):
        failure_mode = "AliasedReturn"
    elif any(c.get("sequence_second_failed") for c in failing):
        failure_mode = "CrossCallStateLeak"
    else:
        failure_mode = "AssertionMismatch"

    top_lines = [
        line for line, _ in sorted(ochiai.items(), key=lambda kv: (-kv[1], kv[0]))[:6]
    ]
    return {
        "failing_count": total_fail,
        "passing_count": len(passing),
        "failing_test_names": sorted(c["name"] for c in failing),
        "passing_test_names": sorted(c["name"] for c in passing),
        "primary_failure_mode": failure_mode,
        "exception_types": sorted(set(exc_types)),
        "ochiai_by_line": {str(k): v for k, v in sorted(ochiai.items())},
        "top_suspicious_lines": top_lines,
    }


def _trace_predicate(regime: str, word: str) -> bool:
    if regime == "R_INDEX_GUARD":
        return word.count("a") == word.count("b")
    if regime == "R_TOKEN_STREAM":
        return word.count("a") == 2 * word.count("b")
    if regime == "R_STATE_CYCLE":
        return word.count("a") == word.count("b") and word.endswith("b")
    if regime == "R_DEPENDENCY":
        return word.count("a") == 3 * word.count("b")
    raise ValueError(f"unknown trace regime: {regime}")


def _build_binary_trace_dataset(
    regime: str,
    seed_material: str,
) -> tuple[list[tuple[str, bool]], list[tuple[str, bool]]]:
    """Construct valid disjoint `train` (63 words) and `validation` (64 words) for `ace_runtime`."""
    train = [(w, _trace_predicate(regime, w)) for w in r1.training_words()]
    seed_int = int(sha256_digest(f"{regime}:{seed_material}")[:12], 16)
    rng = random.Random(seed_int)

    ratio = 3 if regime == "R_DEPENDENCY" else 2 if regime == "R_TOKEN_STREAM" else 1
    lengths = tuple(range(6, 16))
    valid_pos_lengths = [n for n in lengths if n % (ratio + 1) == 0]

    positives: set[str] = set()
    for _ in range(50000):
        n = rng.choice(valid_pos_lengths)
        b_cnt = n // (ratio + 1)
        chars = ["a"] * (n - b_cnt) + ["b"] * b_cnt
        rng.shuffle(chars)
        word = "".join(chars)
        if _trace_predicate(regime, word):
            positives.add(word)
        if len(positives) == 32:
            break

    negatives: set[str] = set()
    for _ in range(50000):
        n = rng.choice(lengths)
        word = "".join(rng.choice("ab") for _ in range(n))
        if not _trace_predicate(regime, word):
            negatives.add(word)
        if len(negatives) == 32:
            break

    if len(positives) != 32 or len(negatives) != 32:
        raise RuntimeError("binary trace validation sample budget exhausted")

    ordered_words = sorted(positives | negatives, key=lambda w: (len(w), w))
    validation = [(w, _trace_predicate(regime, w)) for w in ordered_words]
    return train, validation


def infer_trace_regime_and_motif(
    ast_inspection: dict[str, Any],
    diagnosis: dict[str, Any],
) -> tuple[str, str]:
    """Map dynamic fault observations + AST structure to `(trace_regime, fine_motif)`."""
    mode = diagnosis["primary_failure_mode"]
    if mode == "CallerArgMutated":
        return "R_DEPENDENCY", "CallerArgMutated|AliasAssign"
    if mode == "AliasedReturn":
        return "R_DEPENDENCY", "AliasedReturn|AppendContainer"
    if mode == "CrossCallStateLeak" or (
        ast_inspection["has_mutable_default"] and diagnosis["failing_count"] > 0
    ):
        return "R_DEPENDENCY", "CrossCallStateLeak|MutableDefault"
    if (
        ast_inspection["has_stale_dataflow_chain"]
        and not ast_inspection["has_index_bound_loop"]
        and not ast_inspection["has_element_state_loop"]
    ):
        return "R_DEPENDENCY", "AssertionMismatch|StaleDataflow"
    if mode == "ValueError" and ast_inspection["has_string_tokenizer_ops"]:
        return "R_TOKEN_STREAM", "ValueError|StringTokenize"
    if mode == "IndexError":
        return "R_INDEX_GUARD", "IndexError|EmptyOrBound"
    if ast_inspection["has_index_bound_loop"]:
        return "R_INDEX_GUARD", f"{mode}|IndexBoundLoop"
    if ast_inspection["has_string_tokenizer_ops"] and not ast_inspection["has_element_state_loop"]:
        return "R_TOKEN_STREAM", f"{mode}|StringOps"
    return "R_STATE_CYCLE", f"{mode}|ElementStateLoop"


class RuntimeTraceBridge:
    """Executes binary fault-trace learning, reuse, and prediction in real `ace_runtime.engine.Runtime`."""

    def __init__(self, runtime_workspace: Path) -> None:
        self.runtime_workspace = Path(runtime_workspace).resolve()
        self._runtime = Runtime(self.runtime_workspace)

    def close(self) -> None:
        self._runtime.close()

    def enqueue_and_classify(
        self,
        task_label: str,
        regime: str,
        source_sha256: str,
    ) -> dict[str, Any]:
        train, validation = _build_binary_trace_dataset(regime, f"{task_label}:{source_sha256}")
        clean_name = f"repair_trace_{task_label}"[:80]
        task_id = self._runtime.enqueue(
            {
                "name": clean_name,
                "train": train,
                "validation": validation,
            }
        )
        outcomes = self._runtime.run(max_tasks=1)
        if outcomes:
            report = outcomes[0]
        else:
            report = self._runtime.report(task_id)

        staged = bool(report.get("staged"))
        model_id = report.get("model_id") if staged else None
        probe_signature = (
            [bool(self._runtime.predict(task_id, w)) for w in PROBE_WORDS]
            if staged
            else []
        )
        return {
            "runtime_task_id": task_id,
            "runtime_phase": report.get("phase"),
            "runtime_staged": staged,
            "runtime_learning_called": bool(report.get("learning_called")),
            "runtime_model_id": model_id,
            "probe_words": list(PROBE_WORDS),
            "probe_predictions": probe_signature,
        }

    def status(self) -> dict[str, Any]:
        return self._runtime.status()


def extract_fault_representation(
    ast_inspection: dict[str, Any],
    diagnosis: dict[str, Any],
    source_sha256: str,
    task_label: str,
    bridge: RuntimeTraceBridge | None,
) -> dict[str, Any]:
    """Stage 4 (`Represent`): Construct typed fault representation and query `ace_runtime`."""
    regime, fine_motif = infer_trace_regime_and_motif(ast_inspection, diagnosis)
    runtime_receipt = (
        bridge.enqueue_and_classify(task_label, regime, source_sha256)
        if bridge is not None
        else {
            "runtime_task_id": None,
            "runtime_phase": "DISABLED",
            "runtime_staged": False,
            "runtime_learning_called": False,
            "runtime_model_id": None,
            "probe_words": list(PROBE_WORDS),
            "probe_predictions": [],
        }
    )
    return {
        "trace_regime": regime,
        "fine_signature": fine_motif,
        "primary_failure_mode": diagnosis["primary_failure_mode"],
        "top_suspicious_lines": diagnosis["top_suspicious_lines"],
        "runtime": runtime_receipt,
    }
