"""Closed typed Python AST mutation and repair operator catalog.

Contains ZERO ground-truth labels, ZERO unit-ID branching, and NEVER imports `evaluator.py`.
Every candidate patch is synthesized by cloning the parsed `ast.Module`, applying a single
typed AST schema transformation, unparsing deterministically via `ast.unparse`, and
re-validating syntactic well-formedness via `ast.parse`.
"""
from __future__ import annotations

import ast
import copy
from dataclasses import dataclass
from typing import Any

from .corpus import DevTestCase, sha256_digest

OPERATOR_FAMILIES = (
    "boundary_index",
    "parsing",
    "state_invariant",
    "data_dependency",
    "overfit_probe",
)

STATIC_FAMILY_ORDER = {name: idx for idx, name in enumerate(OPERATOR_FAMILIES)}


@dataclass(frozen=True)
class CandidatePatch:
    patch_id: str
    operator_family: str
    operator_name: str
    target_lineno: int
    in_entrypoint: bool
    ast_node_kind: str
    edit_complexity: int
    patched_source: str

    def summary(self) -> dict[str, Any]:
        return {
            "patch_id": self.patch_id,
            "operator_family": self.operator_family,
            "operator_name": self.operator_name,
            "target_lineno": self.target_lineno,
            "in_entrypoint": self.in_entrypoint,
            "ast_node_kind": self.ast_node_kind,
            "edit_complexity": self.edit_complexity,
        }


def _infer_empty_return_exprs(func: ast.FunctionDef) -> list[ast.expr]:
    """Infer plausible typed empty-input return expressions from existing `return` nodes."""
    candidates: list[ast.expr] = []
    seen: set[str] = set()
    for node in ast.walk(func):
        if isinstance(node, ast.Return) and node.value is not None:
            val = node.value
            inferred: list[ast.expr] = []
            if isinstance(val, ast.List):
                inferred.append(ast.List(elts=[], ctx=ast.Load()))
            elif isinstance(val, ast.Dict):
                inferred.append(ast.Dict(keys=[], values=[]))
            elif isinstance(val, ast.Tuple):
                inferred.append(ast.Constant(value=None))
            elif isinstance(val, ast.Constant) and isinstance(val.value, bool):
                inferred.append(ast.Constant(value=False))
            elif isinstance(val, ast.Constant) and isinstance(val.value, int):
                inferred.extend([ast.Constant(value=0), ast.Constant(value=val.value)])
            elif isinstance(val, ast.UnaryOp) and isinstance(val.op, ast.USub):
                inferred.extend([ast.UnaryOp(op=ast.USub(), operand=ast.Constant(value=1)), ast.Constant(value=0)])
            else:
                inferred.extend([ast.Constant(value=0), ast.List(elts=[], ctx=ast.Load())])
            for expr in inferred:
                key = ast.unparse(expr)
                if key not in seen:
                    seen.add(key)
                    candidates.append(expr)
    if not candidates:
        candidates.append(ast.Constant(value=0))
    return candidates[:2]


def _literal_ast(value: Any) -> ast.expr | None:
    if isinstance(value, (bool, int, str)) or value is None:
        return ast.Constant(value=value)
    if isinstance(value, list):
        elts = [_literal_ast(v) for v in value]
        if any(e is None for e in elts):
            return None
        return ast.List(elts=[e for e in elts if e is not None], ctx=ast.Load())
    if isinstance(value, tuple):
        elts = [_literal_ast(v) for v in value]
        if any(e is None for e in elts):
            return None
        return ast.Tuple(elts=[e for e in elts if e is not None], ctx=ast.Load())
    if isinstance(value, dict):
        keys, vals = [], []
        for k, v in value.items():
            ka, va = _literal_ast(k), _literal_ast(v)
            if ka is None or va is None:
                return None
            keys.append(ka)
            vals.append(va)
        return ast.Dict(keys=keys, values=vals)
    return None


def _node_by_index(tree: ast.AST, target_idx: int) -> ast.AST:
    for idx, node in enumerate(ast.walk(tree)):
        if idx == target_idx:
            return node
    raise IndexError("AST walk index out of range")


def generate_candidates(
    source_code: str,
    entrypoint: str,
    dev_tests: tuple[DevTestCase, ...] | list[DevTestCase] = (),
    failing_test_names: set[str] | None = None,
) -> list[CandidatePatch]:
    """Enumerate closed typed AST candidate patches for `source_code`."""
    base_tree = ast.parse(source_code)
    canonical_orig = ast.unparse(copy.deepcopy(base_tree))
    seen_sources: set[str] = {canonical_orig}
    patches: list[CandidatePatch] = []

    def add_candidate(
        mutated_tree: ast.Module,
        family: str,
        op_name: str,
        lineno: int,
        in_entry: bool,
        node_kind: str,
        complexity: int,
    ) -> None:
        ast.fix_missing_locations(mutated_tree)
        try:
            rendered = ast.unparse(mutated_tree)
            ast.parse(rendered)
        except SyntaxError:
            return
        if rendered in seen_sources:
            return
        seen_sources.add(rendered)
        patches.append(
            CandidatePatch(
                patch_id=sha256_digest(rendered),
                operator_family=family,
                operator_name=op_name,
                target_lineno=max(1, int(lineno)),
                in_entrypoint=bool(in_entry),
                ast_node_kind=node_kind,
                edit_complexity=int(complexity),
                patched_source=rendered + "\n",
            )
        )

    # Map walk indices to enclosing FunctionDef name for scope metadata
    enclosing_func: dict[int, str] = {}
    walk_nodes = list(ast.walk(base_tree))
    id_to_idx = {id(node): idx for idx, node in enumerate(walk_nodes)}
    for node in base_tree.body:
        if isinstance(node, ast.FunctionDef):
            for sub in ast.walk(node):
                enclosing_func[id_to_idx[id(sub)]] = node.name

    # ------------------------------------------------------------------
    # 1. Function-level operators: OP_EMPTY_GUARD_INSERT & OP_DEFAULT_NONE_INIT
    # ------------------------------------------------------------------
    for body_idx, top_node in enumerate(base_tree.body):
        if not isinstance(top_node, ast.FunctionDef):
            continue
        in_entry = top_node.name == entrypoint

        # OP_EMPTY_GUARD_INSERT
        if top_node.args.args:
            first_param = top_node.args.args[0].arg
            already_guarded = (
                len(top_node.body) > 0
                and isinstance(top_node.body[0], ast.If)
                and isinstance(top_node.body[0].test, ast.UnaryOp)
                and isinstance(top_node.body[0].test.op, ast.Not)
                and isinstance(top_node.body[0].test.operand, ast.Name)
                and top_node.body[0].test.operand.id == first_param
            )
            if not already_guarded:
                for ret_expr in _infer_empty_return_exprs(top_node):
                    cloned = copy.deepcopy(base_tree)
                    fn_clone = cloned.body[body_idx]
                    assert isinstance(fn_clone, ast.FunctionDef)
                    guard_stmt = ast.If(
                        test=ast.UnaryOp(op=ast.Not(), operand=ast.Name(id=first_param, ctx=ast.Load())),
                        body=[ast.Return(value=copy.deepcopy(ret_expr))],
                        orelse=[],
                    )
                    fn_clone.body.insert(0, guard_stmt)
                    add_candidate(
                        cloned,
                        "boundary_index",
                        "OP_EMPTY_GUARD_INSERT",
                        top_node.lineno,
                        in_entry,
                        "FunctionDef:EmptyGuard",
                        2,
                    )

        # OP_DEFAULT_NONE_INIT
        num_args = len(top_node.args.args)
        num_defs = len(top_node.args.defaults)
        for def_idx, def_node in enumerate(top_node.args.defaults):
            if isinstance(def_node, (ast.List, ast.Dict, ast.Set)):
                arg_pos = num_args - num_defs + def_idx
                param_name = top_node.args.args[arg_pos].arg
                cloned = copy.deepcopy(base_tree)
                fn_clone = cloned.body[body_idx]
                assert isinstance(fn_clone, ast.FunctionDef)
                fresh_container = copy.deepcopy(def_node)
                fn_clone.args.defaults[def_idx] = ast.Constant(value=None)
                init_guard = ast.If(
                    test=ast.Compare(
                        left=ast.Name(id=param_name, ctx=ast.Load()),
                        ops=[ast.Is()],
                        comparators=[ast.Constant(value=None)],
                    ),
                    body=[
                        ast.Assign(
                            targets=[ast.Name(id=param_name, ctx=ast.Store())],
                            value=fresh_container,
                        )
                    ],
                    orelse=[],
                )
                fn_clone.body.insert(0, init_guard)
                add_candidate(
                    cloned,
                    "data_dependency",
                    "OP_DEFAULT_NONE_INIT",
                    top_node.lineno,
                    in_entry,
                    "FunctionDef:MutableDefault",
                    3,
                )

    # ------------------------------------------------------------------
    # 2. Expression/Call/Compare/Slice AST node operators
    # ------------------------------------------------------------------
    for walk_idx, node in enumerate(walk_nodes):
        func_name = enclosing_func.get(walk_idx, "")
        in_entry = func_name == entrypoint
        lineno = getattr(node, "lineno", 1)

        # OP_RANGE_STOP_ADJUST
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "range"
            and len(node.args) in (1, 2)
        ):
            stop_pos = len(node.args) - 1
            stop_expr = node.args[stop_pos]
            variants: list[ast.expr] = []
            if (
                isinstance(stop_expr, ast.BinOp)
                and isinstance(stop_expr.op, ast.Sub)
                and isinstance(stop_expr.right, ast.Constant)
                and isinstance(stop_expr.right.value, int)
            ):
                k_val = stop_expr.right.value
                if k_val == 1:
                    variants.append(copy.deepcopy(stop_expr.left))
                elif k_val > 1:
                    variants.append(
                        ast.BinOp(
                            left=copy.deepcopy(stop_expr.left),
                            op=ast.Sub(),
                            right=ast.Constant(value=k_val - 1),
                        )
                    )
                variants.append(
                    ast.BinOp(
                        left=copy.deepcopy(stop_expr.left),
                        op=ast.Sub(),
                        right=ast.Constant(value=k_val + 1),
                    )
                )
            else:
                variants.append(ast.BinOp(left=copy.deepcopy(stop_expr), op=ast.Add(), right=ast.Constant(value=1)))
                variants.append(ast.BinOp(left=copy.deepcopy(stop_expr), op=ast.Sub(), right=ast.Constant(value=1)))

            for new_stop in variants:
                cloned = copy.deepcopy(base_tree)
                call_clone = _node_by_index(cloned, walk_idx)
                assert isinstance(call_clone, ast.Call)
                call_clone.args[stop_pos] = new_stop
                add_candidate(
                    cloned,
                    "boundary_index",
                    "OP_RANGE_STOP_ADJUST",
                    lineno,
                    in_entry,
                    "Call:range",
                    1,
                )

        # OP_CMP_BOUNDARY_FLIP
        if isinstance(node, ast.Compare) and len(node.ops) == 1:
            op = node.ops[0]
            replacement_op: ast.cmpop | None = None
            if isinstance(op, ast.Lt):
                replacement_op = ast.LtE()
            elif isinstance(op, ast.LtE):
                replacement_op = ast.Lt()
            elif isinstance(op, ast.Gt):
                replacement_op = ast.GtE()
            elif isinstance(op, ast.GtE):
                replacement_op = ast.Gt()
            if replacement_op is not None:
                cloned = copy.deepcopy(base_tree)
                cmp_clone = _node_by_index(cloned, walk_idx)
                assert isinstance(cmp_clone, ast.Compare)
                cmp_clone.ops = [replacement_op]
                add_candidate(
                    cloned,
                    "boundary_index",
                    "OP_CMP_BOUNDARY_FLIP",
                    lineno,
                    in_entry,
                    "Compare:Boundary",
                    1,
                )

        # OP_SLICE_BOUND_ADJUST
        if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Slice):
            sl = node.slice
            if sl.lower is not None and isinstance(sl.lower, ast.Constant) and sl.lower.value == 1:
                cloned = copy.deepcopy(base_tree)
                sub_clone = _node_by_index(cloned, walk_idx)
                assert isinstance(sub_clone, ast.Subscript) and isinstance(sub_clone.slice, ast.Slice)
                sub_clone.slice.lower = ast.Constant(value=0)
                add_candidate(cloned, "boundary_index", "OP_SLICE_BOUND_ADJUST", lineno, in_entry, "Subscript:Slice", 1)
            if sl.upper is not None:
                cloned = copy.deepcopy(base_tree)
                sub_clone = _node_by_index(cloned, walk_idx)
                assert isinstance(sub_clone, ast.Subscript) and isinstance(sub_clone.slice, ast.Slice)
                sub_clone.slice.upper = ast.BinOp(
                    left=copy.deepcopy(sl.upper),
                    op=ast.Add(),
                    right=ast.Constant(value=1),
                )
                add_candidate(cloned, "boundary_index", "OP_SLICE_BOUND_ADJUST", lineno, in_entry, "Subscript:Slice", 1)

        # OP_STR_STRIP_NORMALIZE & OP_SPLIT_MAXSPLIT_ONE
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "split"
        ):
            recv = node.func.value
            if isinstance(recv, ast.Name):
                cloned = copy.deepcopy(base_tree)
                call_clone = _node_by_index(cloned, walk_idx)
                assert isinstance(call_clone, ast.Call) and isinstance(call_clone.func, ast.Attribute)
                call_clone.func.value = ast.Call(
                    func=ast.Attribute(value=copy.deepcopy(recv), attr="strip", ctx=ast.Load()),
                    args=[],
                    keywords=[],
                )
                add_candidate(
                    cloned,
                    "parsing",
                    "OP_STR_STRIP_NORMALIZE",
                    lineno,
                    in_entry,
                    "Call:strip_split",
                    2,
                )
            if len(node.args) == 1 and not node.keywords:
                cloned = copy.deepcopy(base_tree)
                call_clone = _node_by_index(cloned, walk_idx)
                assert isinstance(call_clone, ast.Call)
                call_clone.args.append(ast.Constant(value=1))
                add_candidate(
                    cloned,
                    "parsing",
                    "OP_SPLIT_MAXSPLIT_ONE",
                    lineno,
                    in_entry,
                    "Call:split_maxsplit",
                    1,
                )

        # OP_SIGN_GUARD_EXPAND: expr.isdigit() -> (expr.lstrip("+-").isdigit() and expr.lstrip("+-") != "")
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "isdigit"
            and not node.args
        ):
            recv = node.func.value
            stripped_expr = ast.Call(
                func=ast.Attribute(value=copy.deepcopy(recv), attr="lstrip", ctx=ast.Load()),
                args=[ast.Constant(value="+-")],
                keywords=[],
            )
            expanded = ast.BoolOp(
                op=ast.And(),
                values=[
                    ast.Call(
                        func=ast.Attribute(value=copy.deepcopy(stripped_expr), attr="isdigit", ctx=ast.Load()),
                        args=[],
                        keywords=[],
                    ),
                    ast.Compare(
                        left=copy.deepcopy(stripped_expr),
                        ops=[ast.NotEq()],
                        comparators=[ast.Constant(value="")],
                    ),
                ],
            )
            cloned = copy.deepcopy(base_tree)
            cloned_walk = list(ast.walk(cloned))
            target_clone_node = cloned_walk[walk_idx]
            for parent in cloned_walk:
                for field_name, field_val in ast.iter_fields(parent):
                    if field_val is target_clone_node:
                        setattr(parent, field_name, expanded)
                    elif isinstance(field_val, list):
                        for item_i, item_v in enumerate(field_val):
                            if item_v is target_clone_node:
                                field_val[item_i] = expanded
            add_candidate(
                cloned,
                "parsing",
                "OP_SIGN_GUARD_EXPAND",
                lineno,
                in_entry,
                "Call:signed_isdigit",
                2,
            )

        # OP_MUTABLE_COPY_WRAP: `lhs = rhs` or `seq.append(obj)`
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and isinstance(node.value, ast.Name)
        ):
            cloned = copy.deepcopy(base_tree)
            assign_clone = _node_by_index(cloned, walk_idx)
            assert isinstance(assign_clone, ast.Assign)
            assign_clone.value = ast.Call(
                func=ast.Attribute(value=copy.deepcopy(node.value), attr="copy", ctx=ast.Load()),
                args=[],
                keywords=[],
            )
            add_candidate(
                cloned,
                "data_dependency",
                "OP_MUTABLE_COPY_WRAP",
                lineno,
                in_entry,
                "Assign:copy",
                2,
            )

        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "append"
            and len(node.args) == 1
            and isinstance(node.args[0], ast.Name)
        ):
            cloned = copy.deepcopy(base_tree)
            call_clone = _node_by_index(cloned, walk_idx)
            assert isinstance(call_clone, ast.Call)
            call_clone.args[0] = ast.Call(
                func=ast.Attribute(value=copy.deepcopy(node.args[0]), attr="copy", ctx=ast.Load()),
                args=[],
                keywords=[],
            )
            add_candidate(
                cloned,
                "data_dependency",
                "OP_MUTABLE_COPY_WRAP",
                lineno,
                in_entry,
                "Call:append_copy",
                2,
            )

    # ------------------------------------------------------------------
    # 3. Block/Statement-level state & dataflow operators
    # ------------------------------------------------------------------
    for body_idx, top_node in enumerate(base_tree.body):
        if not isinstance(top_node, ast.FunctionDef):
            continue
        in_entry = top_node.name == entrypoint

        # Collect zero-initialized scalar counters at function top level
        zero_inits: list[str] = []
        for stmt in top_node.body:
            if (
                isinstance(stmt, ast.Assign)
                and len(stmt.targets) == 1
                and isinstance(stmt.targets[0], ast.Name)
                and isinstance(stmt.value, ast.Constant)
                and stmt.value.value == 0
                and type(stmt.value.value) is int
            ):
                zero_inits.append(stmt.targets[0].id)

        # OP_STATE_RESET_ON_FLUSH & OP_LOOP_TAIL_FLUSH on loops in FunctionDef.body
        for stmt_idx, stmt in enumerate(top_node.body):
            if isinstance(stmt, (ast.For, ast.While)):
                for loop_sub_idx, loop_stmt in enumerate(stmt.body):
                    if isinstance(loop_stmt, ast.If):
                        has_append_or_flush = any(
                            isinstance(sub, ast.Call)
                            and isinstance(sub.func, ast.Attribute)
                            and sub.func.attr == "append"
                            for sub in ast.walk(loop_stmt)
                        )
                        assigned_in_if = {
                            sub.targets[0].id
                            for sub in loop_stmt.body
                            if isinstance(sub, ast.Assign)
                            and len(sub.targets) == 1
                            and isinstance(sub.targets[0], ast.Name)
                        }
                        if has_append_or_flush:
                            for counter_var in zero_inits:
                                if counter_var not in assigned_in_if:
                                    cloned = copy.deepcopy(base_tree)
                                    fn_c = cloned.body[body_idx]
                                    assert isinstance(fn_c, ast.FunctionDef)
                                    loop_c = fn_c.body[stmt_idx]
                                    assert isinstance(loop_c, (ast.For, ast.While))
                                    if_c = loop_c.body[loop_sub_idx]
                                    assert isinstance(if_c, ast.If)
                                    if_c.body.append(
                                        ast.Assign(
                                            targets=[ast.Name(id=counter_var, ctx=ast.Store())],
                                            value=ast.Constant(value=0),
                                        )
                                    )
                                    add_candidate(
                                        cloned,
                                        "state_invariant",
                                        "OP_STATE_RESET_ON_FLUSH",
                                        loop_stmt.lineno,
                                        in_entry,
                                        "If:StateReset",
                                        2,
                                    )

                            # OP_LOOP_TAIL_FLUSH: if next top-level stmt is Return without post-loop append
                            if stmt_idx + 1 < len(top_node.body) and isinstance(top_node.body[stmt_idx + 1], ast.Return):
                                append_stmts = [
                                    s_item
                                    for s_item in loop_stmt.body
                                    if isinstance(s_item, ast.Expr)
                                    and isinstance(s_item.value, ast.Call)
                                    and isinstance(s_item.value.func, ast.Attribute)
                                    and s_item.value.func.attr == "append"
                                ]
                                for app_stmt in append_stmts:
                                    cloned = copy.deepcopy(base_tree)
                                    fn_c = cloned.body[body_idx]
                                    assert isinstance(fn_c, ast.FunctionDef)
                                    fn_c.body.insert(stmt_idx + 1, copy.deepcopy(app_stmt))
                                    add_candidate(
                                        cloned,
                                        "state_invariant",
                                        "OP_LOOP_TAIL_FLUSH",
                                        top_node.body[stmt_idx + 1].lineno,
                                        in_entry,
                                        "Loop:TailFlush",
                                        2,
                                    )

        # OP_SWAP_ADJACENT_STATE_STMTS across blocks inside top_node
        def _enumerate_block_paths(curr: ast.AST, path: tuple[tuple[str, int], ...]) -> list[tuple[tuple[str, int], ...]]:
            found: list[tuple[tuple[str, int], ...]] = []
            for attr_name in ("body", "orelse"):
                block = getattr(curr, attr_name, None)
                if isinstance(block, list) and len(block) >= 2:
                    found.append((*path, (attr_name, -1)))
                if isinstance(block, list):
                    for idx_b, child in enumerate(block):
                        if isinstance(child, ast.AST):
                            found.extend(_enumerate_block_paths(child, (*path, (attr_name, idx_b))))
            return found

        def _resolve_block(root_fn: ast.AST, path: tuple[tuple[str, int], ...]) -> list[ast.stmt]:
            cur: Any = root_fn
            for attr_name, idx_b in path:
                cur = getattr(cur, attr_name)
                if idx_b >= 0:
                    cur = cur[idx_b]
            return cur

        swappable_types = (ast.Assign, ast.AugAssign, ast.Expr, ast.If)
        forbidden_Jump = (ast.Return, ast.Raise, ast.Break, ast.Continue)
        for bpath in _enumerate_block_paths(top_node, ()):
            orig_block = _resolve_block(top_node, bpath)
            for idx_s in range(len(orig_block) - 1):
                s1, s2 = orig_block[idx_s], orig_block[idx_s + 1]
                if not isinstance(s1, swappable_types) or not isinstance(s2, swappable_types):
                    continue
                if any(isinstance(n, forbidden_Jump) for n in ast.walk(s1)) or any(
                    isinstance(n, forbidden_Jump) for n in ast.walk(s2)
                ):
                    continue
                cloned = copy.deepcopy(base_tree)
                fn_c = cloned.body[body_idx]
                target_block = _resolve_block(fn_c, bpath)
                target_block[idx_s], target_block[idx_s + 1] = target_block[idx_s + 1], target_block[idx_s]
                add_candidate(
                    cloned,
                    "state_invariant",
                    "OP_SWAP_ADJACENT_STATE_STMTS",
                    s1.lineno,
                    in_entry,
                    "Block:SwapAdjacent",
                    2,
                )

        # OP_RHS_VAR_REBIND: rebind stale variable argument in Assign Call to recent local variable
        prior_locals: list[str] = []
        for stmt_idx, stmt in enumerate(top_node.body):
            if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
                lhs_name = stmt.targets[0].id
                if isinstance(stmt.value, ast.Call) and prior_locals:
                    for arg_idx, arg_node in enumerate(stmt.value.args):
                        if isinstance(arg_node, ast.Name) and arg_node.id in prior_locals:
                            for recent_var in reversed(prior_locals[-3:]):
                                if recent_var != arg_node.id and recent_var != lhs_name:
                                    cloned = copy.deepcopy(base_tree)
                                    fn_c = cloned.body[body_idx]
                                    assert isinstance(fn_c, ast.FunctionDef)
                                    assign_c = fn_c.body[stmt_idx]
                                    assert isinstance(assign_c, ast.Assign) and isinstance(assign_c.value, ast.Call)
                                    assign_c.value.args[arg_idx] = ast.Name(id=recent_var, ctx=ast.Load())
                                    add_candidate(
                                        cloned,
                                        "data_dependency",
                                        "OP_RHS_VAR_REBIND",
                                        stmt.lineno,
                                        in_entry,
                                        "Call:RebindLocalVar",
                                        2,
                                    )
                if lhs_name not in prior_locals:
                    prior_locals.append(lhs_name)

        # ------------------------------------------------------------------
        # 4. Overfit probe operators (generate-and-validate weak-test traps)
        # ------------------------------------------------------------------
        if in_entry and dev_tests:
            # OP_OVERFIT_CONSTANT_RETURN: replace final top-level Return expr with dev expected scalar
            if top_node.body and isinstance(top_node.body[-1], ast.Return):
                scalar_consts: list[Any] = []
                for tc in dev_tests:
                    if tc.mode == "call" and tc.expected_exc is None and isinstance(tc.expected, (int, bool, str)):
                        if not any(type(x) is type(tc.expected) and x == tc.expected for x in scalar_consts):
                            scalar_consts.append(tc.expected)
                for const_val in scalar_consts[:2]:
                    cloned = copy.deepcopy(base_tree)
                    fn_c = cloned.body[body_idx]
                    assert isinstance(fn_c, ast.FunctionDef)
                    ret_c = fn_c.body[-1]
                    assert isinstance(ret_c, ast.Return)
                    ret_c.value = ast.Constant(value=const_val)
                    add_candidate(
                        cloned,
                        "overfit_probe",
                        "OP_OVERFIT_CONSTANT_RETURN",
                        top_node.body[-1].lineno,
                        True,
                        "Return:DevConstant",
                        1,
                    )

            # OP_OVERFIT_DEV_INPUT_GUARD: special-case early return for failing dev call case
            param_names = [a.arg for a in top_node.args.args]
            guard_candidates_added = 0
            for tc in dev_tests:
                if guard_candidates_added >= 2:
                    break
                if failing_test_names is not None and tc.name not in failing_test_names:
                    continue
                if tc.mode != "call" or tc.expected_exc is not None or len(tc.args) != len(param_names) or not param_names:
                    continue
                args_ast = _literal_ast(tc.args[0]) if len(param_names) == 1 else _literal_ast(tuple(tc.args))
                exp_ast = _literal_ast(tc.expected)
                if args_ast is None or exp_ast is None:
                    continue
                lhs_ast: ast.expr = (
                    ast.Name(id=param_names[0], ctx=ast.Load())
                    if len(param_names) == 1
                    else ast.Tuple(elts=[ast.Name(id=p, ctx=ast.Load()) for p in param_names], ctx=ast.Load())
                )
                cloned = copy.deepcopy(base_tree)
                fn_c = cloned.body[body_idx]
                assert isinstance(fn_c, ast.FunctionDef)
                special_if = ast.If(
                    test=ast.Compare(left=lhs_ast, ops=[ast.Eq()], comparators=[args_ast]),
                    body=[ast.Return(value=exp_ast)],
                    orelse=[],
                )
                fn_c.body.insert(0, special_if)
                add_candidate(
                    cloned,
                    "overfit_probe",
                    "OP_OVERFIT_DEV_INPUT_GUARD",
                    top_node.lineno,
                    True,
                    "FunctionDef:DevInputGuard",
                    1,
                )
                guard_candidates_added += 1

    return patches
