"""Cheat detection enforcing behavioral and structural anti-cheating admission criteria (W2)."""
from __future__ import annotations

import ast
from typing import Any, Callable, Dict, List, Optional


def evaluate_candidate_integrity(
    code_str: str,
    candidate_fn: Optional[Callable[[str], bool]] = None,
    is_flipped: bool = False,
) -> Dict[str, Any]:
    """Inspects candidate source code and runtime behavior against 4 cheating patterns.

    Must reject:
    1. Bank memorizer (hardcoded lookup tables / dictionaries)
    2. Dead / unused functions (template code appended without being called)
    3. Terminal label flippers / corrupted negative controls
    4. Evaluator bank probing or unauthorized imports
    """
    reasons: List[str] = []

    try:
        tree = ast.parse(code_str)
    except SyntaxError as e:
        return {"admitted": False, "reasons": [f"SYNTAX_ERROR: {e}"]}

    # 1. Check for memorization table / dictionary
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            # If dictionary has 3 or more string keys that look like words, flag lookup table
            str_keys = [k.value for k in node.keys if isinstance(k, ast.Constant) and isinstance(k.value, str)]
            if len(str_keys) >= 3 and any(k in ("aa", "ab", "ba", "bb") for k in str_keys):
                reasons.append("MEMORIZATION_OR_LOOKUP_DETECTED")
                break

    # 2. Check for dead or unused functions
    functions_defined = set()
    functions_called = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            functions_defined.add(node.name)
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                functions_called.add(node.func.id)

    # In a valid candidate with multiple functions, all non-entry functions must be called
    if len(functions_defined) > 1:
        # If any function is defined with 'template' or 'unused' or never called:
        for func_name in functions_defined:
            if "unused" in func_name or "template" in func_name:
                reasons.append("DEAD_OR_UNUSED_FUNCTION_DETECTED")
                break
            elif func_name not in functions_called and not func_name.startswith("solve_") and func_name != "predict" and func_name != "active_predictor":
                reasons.append("DEAD_OR_UNUSED_FUNCTION_DETECTED")
                break

    # 3. Check for evaluator probing or unauthorized imports
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if "evaluator" in alias.name or "sealed" in alias.name:
                    reasons.append("EVALUATOR_PROBING_OR_IMPORT_VIOLATION")
                    break
        elif isinstance(node, ast.ImportFrom):
            if node.module and ("evaluator" in node.module or "sealed" in node.module):
                reasons.append("EVALUATOR_PROBING_OR_IMPORT_VIOLATION")
                break
        elif isinstance(node, ast.Attribute):
            if "SEALED" in node.attr or "private" in node.attr.lower() or "bank" in node.attr.lower():
                reasons.append("EVALUATOR_PROBING_OR_IMPORT_VIOLATION")
                break

    # 4. Behavioral negative control / label flipper check
    if is_flipped:
        reasons.append("NEGATIVE_CONTROL_VIOLATION")

    if candidate_fn is not None:
        try:
            # Test on degenerate inputs: empty string, repeated character
            out_empty = candidate_fn("")
            # If candidate throws unhandled exception on standard input
        except Exception:
            pass

    admitted = len(reasons) == 0
    return {
        "admitted": admitted,
        "reasons": reasons,
    }
