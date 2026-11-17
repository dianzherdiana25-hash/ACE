"""Edge-case unit tests for code/ace_code_agent/static_probe.py (read-only target)."""
from __future__ import annotations

import ast
import unittest
from unittest.mock import patch

from ace_code_agent import static_probe as sp


def _wrap(body_src: str, name: str = "ace_v04_cand", sig: str = "length, density, stride_val") -> str:
    return f"def {name}({sig}):\n{body_src}\n"


class StaticProbeEdgeTests(unittest.TestCase):
    """26+ edge-case tests covering grammar, limits, budget, arithmetic, and diagnostics."""

    def test_01_non_string_and_oversized_source_rejected(self) -> None:
        with self.assertRaises(sp.UnsafeOrUnsupported):
            sp.parse_candidate(None)  # type: ignore[arg-type]
        with self.assertRaises(sp.UnsafeOrUnsupported):
            sp.parse_candidate(123)  # type: ignore[arg-type]
        pad = " " * (8001 - len("def ace_v04_f(length, density, stride_val):\n    return 0"))
        with self.assertRaises(sp.UnsafeOrUnsupported):
            sp.parse_candidate(f"def ace_v04_f(length, density, stride_val):\n    return 0{pad}")

    def test_02_source_at_exact_8000_chars_passes(self) -> None:
        base = "def ace_v04_f(length, density, stride_val):\n    return 0"
        src = base + (" " * (8000 - len(base)))
        self.assertEqual(len(src), 8000)
        fn = sp.parse_candidate(src)
        self.assertEqual(sp.interpret(fn, 1, 2, 3), 0)

    def test_03_syntax_error_and_deep_recursion_syntax_rejected(self) -> None:
        with self.assertRaises(sp.UnsafeOrUnsupported):
            sp.parse_candidate("def ace_v04_f(length, density, stride_val):\n    return (")
        deep = "def ace_v04_f(length, density, stride_val):\n    return " + ("(" * 400) + "1" + (")" * 400)
        with self.assertRaises(sp.UnsafeOrUnsupported):
            sp.parse_candidate(deep)

    def test_04_multiple_top_level_statements_or_non_function_rejected(self) -> None:
        with self.assertRaises(sp.UnsafeOrUnsupported):
            sp.parse_candidate("x = 1\ndef ace_v04_f(length, density, stride_val):\n    return 1\n")
        with self.assertRaises(sp.UnsafeOrUnsupported):
            sp.parse_candidate("x = 1\n")

    def test_05_function_name_prefixes_accepted_and_unknown_rejected(self) -> None:
        fn1 = sp.parse_candidate(_wrap("    return 1", name="ace_v04_rule"))
        fn2 = sp.parse_candidate(_wrap("    return 0", name="ace_ai_synthesized_rule"))
        self.assertEqual(sp.interpret(fn1, 0, 0, 0), 1)
        self.assertEqual(sp.interpret(fn2, 0, 0, 0), 0)
        with self.assertRaises(sp.UnsafeOrUnsupported):
            sp.parse_candidate(_wrap("    return 1", name="other_fn"))

    def test_06_signature_order_defaults_posonly_kwonly_varargs_decorators_rejected(self) -> None:
        bad_sigs = [
            _wrap("    return 0", sig="density, length, stride_val"),
            _wrap("    return 0", sig="length, density"),
            _wrap("    return 0", sig="length, density, stride_val=0"),
            _wrap("    return 0", sig="length, /, density, stride_val"),
            _wrap("    return 0", sig="length, density, *, stride_val"),
            _wrap("    return 0", sig="length, density, stride_val, *args"),
            _wrap("    return 0", sig="length, density, stride_val, **kwargs"),
            "@dec\n" + _wrap("    return 0"),
        ]
        for src in bad_sigs:
            with self.assertRaises(sp.UnsafeOrUnsupported, msg=src):
                sp.parse_candidate(src)

    def test_07_int_annotations_allowed_and_non_int_annotations_rejected(self) -> None:
        fn = sp.parse_candidate(
            "def ace_v04_f(length: int, density: int, stride_val: int) -> int:\n    return 1\n"
        )
        self.assertEqual(sp.interpret(fn, 1, 1, 1), 1)
        for bad in (
            "def ace_v04_f(length: float, density: int, stride_val: int) -> int:\n    return 1\n",
            "def ace_v04_f(length: int, density: int, stride_val: int) -> bool:\n    return 1\n",
            "def ace_v04_f(length: 'int', density, stride_val):\n    return 1\n",
        ):
            with self.assertRaises(sp.UnsafeOrUnsupported):
                sp.parse_candidate(bad)

    def test_08_disallowed_calls_and_malformed_int_calls_rejected(self) -> None:
        for expr in ("abs(length)", "bool(length)", "int()", "int(1, 2)", "int(x=1)", "length.bit_length()"):
            with self.assertRaises(sp.UnsafeOrUnsupported, msg=expr):
                sp.parse_candidate(_wrap(f"    return {expr}"))

    def test_09_docstring_inside_function_body_rejected(self) -> None:
        src = _wrap('    """Docstring."""\n    return 1')
        with self.assertRaises(sp.UnsafeOrUnsupported):
            sp.parse_candidate(src)

    def test_10_node_budget_128_boundary(self) -> None:
        # Build expression with repeated "+ 0" hitting exact MAX_NODES boundary vs MAX_NODES + 1.
        base_count = len(list(ast.walk(ast.parse(_wrap("    return 1")))))
        # Each "+ 0" adds 3 AST nodes: BinOp + Add + Constant.
        remaining_ops = (sp.MAX_NODES - base_count) // 3
        expr_ok = "1" + (" + 0" * remaining_ops)
        src_ok = _wrap(f"    return {expr_ok}")
        self.assertLessEqual(len(list(ast.walk(ast.parse(src_ok)))), sp.MAX_NODES)
        self.assertEqual(sp.interpret(sp.parse_candidate(src_ok), 0, 0, 0), 1)

        expr_over = "1" + (" + 0" * (remaining_ops + 1))
        src_over = _wrap(f"    return {expr_over}")
        self.assertGreater(len(list(ast.walk(ast.parse(src_over)))), sp.MAX_NODES)
        with self.assertRaises(sp.UnsafeOrUnsupported):
            sp.parse_candidate(src_over)

    def test_11_interpret_input_type_and_domain_bounds(self) -> None:
        fn = sp.parse_candidate(_wrap("    return int(length == 32)"))
        self.assertEqual(sp.interpret(fn, 0, 0, 0), 0)
        self.assertEqual(sp.interpret(fn, 32, 32, 32), 1)
        for bad in ((-1, 0, 0), (33, 0, 0), (0, -1, 0), (0, 0, 33), (True, 0, 0), (1.0, 0, 0), ("1", 0, 0)):
            with self.assertRaises(sp.UnsafeOrUnsupported, msg=repr(bad)):
                sp.interpret(fn, *bad)  # type: ignore[arg-type]

    def test_12_non_binary_return_or_missing_return_rejected(self) -> None:
        for body in (
            "    return 2",
            "    return -1",
            "    return 1.0",
            "    x = 1",
            "    if length == 3:\n        return 1",
        ):
            fn = sp.parse_candidate(_wrap(body))
            with self.assertRaises(sp.UnsafeOrUnsupported, msg=body):
                sp.interpret(fn, 4, 1, 0)

    def test_13_boolean_constant_and_bool_int_call_normalized_to_binary(self) -> None:
        fn_true = sp.parse_candidate(_wrap("    return True"))
        fn_false = sp.parse_candidate(_wrap("    return int(False)"))
        self.assertEqual(sp.interpret(fn_true, 0, 0, 0), 1)
        self.assertEqual(sp.interpret(fn_false, 0, 0, 0), 0)

    def test_14_reassignment_of_inputs_or_dunder_or_chained_assign_rejected(self) -> None:
        for stmt in (
            "    length = 5\n    return 1",
            "    density = 2\n    return 1",
            "    stride_val = 1\n    return 1",
            "    __secret = 1\n    return 1",
            "    a = b = 1\n    return 1",
        ):
            fn = sp.parse_candidate(_wrap(stmt))
            with self.assertRaises(sp.UnsafeOrUnsupported):
                sp.interpret(fn, 1, 2, 3)

    def test_15_undefined_variable_rejected_at_interpret(self) -> None:
        fn = sp.parse_candidate(_wrap("    return undeclared"))
        with self.assertRaises(sp.UnsafeOrUnsupported):
            sp.interpret(fn, 1, 1, 1)

    def test_16_max_abs_value_boundary_accepted_and_overflow_rejected(self) -> None:
        ok_fn = sp.parse_candidate(_wrap("    x = 1000000\n    return int(x == 1000000)"))
        self.assertEqual(sp.interpret(ok_fn, 0, 0, 0), 1)
        neg_ok = sp.parse_candidate(_wrap("    x = -1000000\n    return int(x == -1000000)"))
        self.assertEqual(sp.interpret(neg_ok, 0, 0, 0), 1)
        over_fn = sp.parse_candidate(_wrap("    x = 1000000 + 1\n    return 1"))
        with self.assertRaises(sp.UnsafeOrUnsupported):
            sp.interpret(over_fn, 0, 0, 0)

    def test_17_division_and_modulo_by_zero_rejected(self) -> None:
        for op in ("//", "%"):
            fn = sp.parse_candidate(_wrap(f"    x = length {op} stride_val\n    return int(x == 0)"))
            with self.assertRaises(sp.UnsafeOrUnsupported):
                sp.interpret(fn, 5, 1, 0)
            self.assertIn(sp.interpret(fn, 5, 1, 2), (0, 1))

    def test_18_short_circuit_and_or_avoids_div_zero_branch(self) -> None:
        fn_and = sp.parse_candidate(_wrap("    return int((stride_val != 0) and (length // stride_val > 0))"))
        self.assertEqual(sp.interpret(fn_and, 5, 1, 0), 0)
        self.assertEqual(sp.interpret(fn_and, 5, 1, 2), 1)

        fn_or = sp.parse_candidate(_wrap("    return int((stride_val == 0) or (length // stride_val > 0))"))
        self.assertEqual(sp.interpret(fn_or, 5, 1, 0), 1)

    def test_19_unary_ops_and_ifexp_ternary(self) -> None:
        fn = sp.parse_candidate(
            _wrap("    v = +length + (-density)\n    return 1 if (not (v == 0) and v > 0) else 0")
        )
        self.assertEqual(sp.interpret(fn, 5, 3, 0), 1)
        self.assertEqual(sp.interpret(fn, 3, 3, 0), 0)
        self.assertEqual(sp.interpret(fn, 2, 5, 0), 0)

    def test_20_chained_comparisons_evaluated_correctly_without_double_eval(self) -> None:
        fn = sp.parse_candidate(_wrap("    return int(1 <= density < length <= 10)"))
        self.assertEqual(sp.interpret(fn, 6, 3, 0), 1)
        self.assertEqual(sp.interpret(fn, 3, 3, 0), 0)
        self.assertEqual(sp.interpret(fn, 11, 3, 0), 0)
        self.assertEqual(sp.interpret(fn, 6, 0, 0), 0)

    def test_21_disallowed_operators_like_pow_bitops_augassign_rejected(self) -> None:
        for body in (
            "    return int((length ** 2) > 0)",
            "    return int((length & 1) == 1)",
            "    return int(~length == 0)",
            "    x = 1\n    x += 1\n    return 1",
            "    for i in (1, 2):\n        return 1\n    return 0",
        ):
            with self.assertRaises(sp.UnsafeOrUnsupported, msg=body):
                sp.parse_candidate(_wrap(body))

    def test_22_disallowed_compare_is_and_in_rejected(self) -> None:
        for op in ("is", "is not"):
            with self.assertRaises(sp.UnsafeOrUnsupported):
                sp.parse_candidate(_wrap(f"    return int(length {op} density)"))

    def test_23_operation_budget_exhaustion_raises(self) -> None:
        fn = sp.parse_candidate(_wrap("    x = 1 + 2 + 3 + 4 + 5\n    return int(x > 0)"))
        with patch.object(sp, "MAX_STEPS", 4):
            with self.assertRaises(sp.UnsafeOrUnsupported):
                sp.interpret(fn, 1, 2, 3)

    def test_24_if_elif_else_nested_statements_with_early_return(self) -> None:
        src = _wrap(
            "    if length < 4:\n"
            "        return 0\n"
            "    elif density % 2 == 0:\n"
            "        x = (2 * stride_val - density) % 3\n"
            "        if x == 0:\n"
            "            return 1\n"
            "        return 0\n"
            "    else:\n"
            "        return 0"
        )
        fn = sp.parse_candidate(src)
        self.assertEqual(sp.interpret(fn, 3, 2, 1), 0)
        self.assertEqual(sp.interpret(fn, 4, 2, 1), 1)
        self.assertEqual(sp.interpret(fn, 4, 2, 0), 0)

    def test_25_public_diagnostic_perfect_modular_candidate_fields(self) -> None:
        src = _wrap("    return int((2 * stride_val - density) % 3 == 0)")
        diag = sp.public_diagnostic(src)
        self.assertEqual(diag["public_probe_count"], 96.0)
        self.assertEqual(diag["public_modular_candidate"], 1.0)
        self.assertEqual(diag["independent_confirmation"], 0.0)
        self.assertEqual(diag["connected_to_active_algorithm"], 0.0)
        self.assertEqual(diag["candidate_python_executed"], 0.0)

    def test_26_public_behavior_digest_deterministic_and_distinguishes_candidates(self) -> None:
        d_zero = sp.public_behavior_digest(_wrap("    return 0"))
        d_zero_alt = sp.public_behavior_digest(_wrap("    x = 0\n    return x"))
        d_one = sp.public_behavior_digest(_wrap("    return 1"))
        self.assertEqual(len(d_zero), 64)
        self.assertEqual(d_zero, d_zero_alt)
        self.assertNotEqual(d_zero, d_one)


if __name__ == "__main__":
    unittest.main()
