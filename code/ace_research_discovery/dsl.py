"""Closed typed stack/frame/scan combinator DSL over binary `{a, b}` strings.

Contains ONLY elementary sequence/frame selectors, a single linear Dyck stack
node-stream trace `(depth, out_degree)`, node predicates, generic aggregators,
surface string checks, modular arithmetic, and boolean/relational combinators.
Zero named task primitives, zero `eval`/`exec`, and zero imports of `evaluator`
or `tasks`.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import itertools
from typing import Any

from . import digest

ALPHABET = ("a", "b")
FRAMES = ("Whole", "LeftF", "RightF", "SlotF")
NODE_ATTRS = ("depth", "deg")
PATTERNS_1_TO_3: tuple[str, ...] = tuple(
    "".join(p) for n in (1, 2, 3) for p in itertools.product(ALPHABET, repeat=n)
)
MODULI = (2, 3, 4)


@dataclass
class WorkMeter:
    """Deterministic compute counter independent of wall-clock jitter."""

    ast_nodes_evaluated: int = 0
    symbol_steps: int = 0
    candidates_evaluated: int = 0

    def charge_expr(self, ast_size: int, scan_count: int, total_chars: int, n_inputs: int) -> None:
        self.ast_nodes_evaluated += ast_size * n_inputs
        self.symbol_steps += scan_count * total_chars
        self.candidates_evaluated += 1

    def to_dict(self) -> dict[str, int]:
        return {
            "ast_nodes_evaluated": self.ast_nodes_evaluated,
            "symbol_steps": self.symbol_steps,
            "candidates_evaluated": self.candidates_evaluated,
        }


@dataclass(frozen=True)
class FrameSlice:
    """Resolved string slice and popped `(depth, deg)` node stream for one frame."""

    text: str
    nodes: tuple[tuple[int, int], ...]
    valid: bool
    max_depth: int = 0
    max_deg: int = 0


@dataclass(frozen=True)
class ParsedInput:
    """Pre-traced Dyck stack components of a binary `{a, b}` string."""

    word: str
    valid_dyck: bool
    num_components: int
    whole: FrameSlice
    left: FrameSlice
    right: FrameSlice

    def get_frame(self, frame: str) -> FrameSlice:
        if frame == "Whole" or frame == "SlotF":
            return self.whole
        if frame == "LeftF":
            return self.left
        if frame == "RightF":
            return self.right
        raise ValueError(f"unknown frame: {frame}")


def _make_frame_slice(text: str, nodes: tuple[tuple[int, int], ...], valid: bool) -> FrameSlice:
    if not valid or not nodes:
        return FrameSlice(text=text, nodes=nodes, valid=valid, max_depth=0, max_deg=0)
    return FrameSlice(
        text=text,
        nodes=nodes,
        valid=True,
        max_depth=max(n[0] for n in nodes),
        max_deg=max(n[1] for n in nodes),
    )


@lru_cache(maxsize=65536)
def _parse_dyck_cached(word: str) -> ParsedInput:
    if (set(word) - {"a", "b"}) or len(word) > 100:
        raise ValueError("bounded binary a/b input required")

    stack: list[list[int]] = []
    comp_nodes: list[tuple[int, int]] = []
    all_nodes: list[tuple[int, int]] = []
    components: list[tuple[str, tuple[tuple[int, int], ...]]] = []
    comp_start = 0
    underflow = False

    for idx, ch in enumerate(word):
        if ch == "a":
            if not stack:
                comp_start = idx
                comp_nodes = []
            else:
                stack[-1][1] += 1
            stack.append([len(stack) + 1, 0])
        else:
            if not stack:
                underflow = True
                break
            depth, deg = stack.pop()
            rec = (depth, deg)
            comp_nodes.append(rec)
            all_nodes.append(rec)
            if not stack:
                components.append((word[comp_start : idx + 1], tuple(comp_nodes)))

    valid_dyck = (not underflow) and (len(stack) == 0)
    n_comp = len(components) if valid_dyck else 0
    whole_valid = bool(valid_dyck and n_comp >= 1)
    whole = _make_frame_slice(
        text=word,
        nodes=tuple(all_nodes) if whole_valid else (),
        valid=whole_valid,
    )
    if valid_dyck and n_comp == 2:
        left = _make_frame_slice(text=components[0][0], nodes=components[0][1], valid=True)
        right = _make_frame_slice(text=components[1][0], nodes=components[1][1], valid=True)
    else:
        left = _make_frame_slice(text="", nodes=(), valid=False)
        right = _make_frame_slice(text="", nodes=(), valid=False)
    return ParsedInput(
        word=word,
        valid_dyck=valid_dyck,
        num_components=n_comp,
        whole=whole,
        left=left,
        right=right,
    )


def parse_dyck_input(word: str, meter: WorkMeter | None = None) -> ParsedInput:
    """Run elementary linear-time Dyck stack machine over `{a, b}` string."""
    if type(word) is not str:
        raise ValueError("bounded binary a/b input required")
    parsed = _parse_dyck_cached(word)
    if meter is not None:
        meter.symbol_steps += len(word)
    return parsed


@dataclass(frozen=True)
class NodePred:
    """Closed node-level predicate over `(depth, deg)`."""

    op: str  # "eq" | "ge" | "mod_eq"
    attr: str  # "depth" | "deg"
    val: int
    rem: int = 0

    def __post_init__(self) -> None:
        if self.attr not in NODE_ATTRS:
            raise ValueError(f"invalid node attr: {self.attr}")
        if type(self.val) is not int or type(self.rem) is not int:
            raise ValueError("node predicate parameters must be exact ints")
        if self.op not in ("eq", "ge", "mod_eq"):
            raise ValueError(f"invalid node predicate op: {self.op}")

    @property
    def ast_size(self) -> int:
        return 2

    def matches(self, node: tuple[int, int]) -> bool:
        v = node[0] if self.attr == "depth" else node[1]
        if self.op == "eq":
            return v == self.val
        if self.op == "ge":
            return v >= self.val
        return v % self.val == self.rem

    def to_data(self) -> dict[str, Any]:
        return {"type": "npred", "op": self.op, "attr": self.attr, "val": self.val, "rem": self.rem}


def enumerate_node_preds() -> tuple[NodePred, ...]:
    preds: list[NodePred] = []
    for attr in NODE_ATTRS:
        for c in (0, 1, 2, 3):
            if attr == "depth" and c == 0:
                continue  # depth is always >= 1
            preds.append(NodePred("eq", attr, c))
        for c in (1, 2, 3, 4):
            if attr == "depth" and c == 1:
                continue  # depth >= 1 is tautological
            preds.append(NodePred("ge", attr, c))
        for m in (2, 3):
            for r in range(m):
                preds.append(NodePred("mod_eq", attr, m, r))
    return tuple(preds)


NODE_PREDS: tuple[NodePred, ...] = enumerate_node_preds()
_NODE_PRED_INDEX: dict[NodePred, int] = {np: idx for idx, np in enumerate(NODE_PREDS)}


@lru_cache(maxsize=32768)
def _cached_node_pred_counts(nodes: tuple[tuple[int, int], ...]) -> tuple[int, ...]:
    return tuple(sum(1 for n in nodes if np.matches(n)) for np in NODE_PREDS)


@dataclass(frozen=True)
class IntExpr:
    """Closed integer-valued expression over a frame or sub-expression."""

    kind: str
    frame: str | None = None
    attr: str | None = None
    npred: NodePred | None = None
    ch: str | None = None
    mod: int | None = None
    sub: IntExpr | None = None
    left: IntExpr | None = None
    right: IntExpr | None = None

    @property
    def ast_size(self) -> int:
        if self.kind == "str_len":
            return 2
        if self.kind in ("max_nodes", "char_count"):
            return 3
        if self.kind in ("count_nodes", "signed_balance"):
            assert self.npred is not None
            return 2 + self.npred.ast_size
        if self.kind == "mod":
            assert self.sub is not None
            return 1 + self.sub.ast_size
        if self.kind == "sub":
            assert self.left is not None and self.right is not None
            return 1 + self.left.ast_size + self.right.ast_size
        raise ValueError(f"unknown IntExpr kind: {self.kind}")

    @property
    def scan_count(self) -> int:
        if self.kind in ("str_len", "max_nodes", "char_count", "count_nodes", "signed_balance"):
            return 1
        if self.kind == "mod":
            assert self.sub is not None
            return self.sub.scan_count
        if self.kind == "sub":
            assert self.left is not None and self.right is not None
            return self.left.scan_count + self.right.scan_count
        return 0

    def eval_parsed(self, parsed: ParsedInput, meter: WorkMeter | None = None) -> int | None:
        if self.kind == "str_len":
            assert self.frame is not None
            if meter is not None:
                meter.ast_nodes_evaluated += 2
            fs = parsed.get_frame(self.frame)
            if self.frame in ("LeftF", "RightF") and not fs.valid:
                return None
            return len(fs.text)
        if self.kind == "char_count":
            assert self.frame is not None and self.ch is not None
            if meter is not None:
                meter.ast_nodes_evaluated += 3
            fs = parsed.get_frame(self.frame)
            if self.frame in ("LeftF", "RightF") and not fs.valid:
                return None
            return fs.text.count(self.ch)
        if self.kind == "max_nodes":
            assert self.frame is not None and self.attr is not None
            if meter is not None:
                meter.ast_nodes_evaluated += 3
            fs = parsed.get_frame(self.frame)
            if not fs.valid:
                return None
            return fs.max_depth if self.attr == "depth" else fs.max_deg
        if self.kind == "count_nodes":
            assert self.frame is not None and self.npred is not None
            if meter is not None:
                meter.ast_nodes_evaluated += 2 + self.npred.ast_size
            fs = parsed.get_frame(self.frame)
            if not fs.valid:
                return None
            np_idx = _NODE_PRED_INDEX.get(self.npred)
            if np_idx is not None:
                return _cached_node_pred_counts(fs.nodes)[np_idx]
            return sum(1 for n in fs.nodes if self.npred.matches(n))
        if self.kind == "signed_balance":
            assert self.frame is not None and self.npred is not None
            if meter is not None:
                meter.ast_nodes_evaluated += 2 + self.npred.ast_size
            fs = parsed.get_frame(self.frame)
            if not fs.valid:
                return None
            np_idx = _NODE_PRED_INDEX.get(self.npred)
            if np_idx is not None:
                return 2 * _cached_node_pred_counts(fs.nodes)[np_idx] - len(fs.nodes)
            return sum(1 if self.npred.matches(n) else -1 for n in fs.nodes)
        if self.kind == "mod":
            assert self.sub is not None and self.mod is not None
            if meter is not None:
                meter.ast_nodes_evaluated += 1
            val = self.sub.eval_parsed(parsed, meter)
            return None if val is None else (val % self.mod)
        if self.kind == "sub":
            assert self.left is not None and self.right is not None
            if meter is not None:
                meter.ast_nodes_evaluated += 1
            lv = self.left.eval_parsed(parsed, meter)
            rv = self.right.eval_parsed(parsed, meter)
            return None if (lv is None or rv is None) else (lv - rv)
        raise ValueError(f"unknown IntExpr kind: {self.kind}")

    def bind_frame(self, target_frame: str) -> IntExpr:
        if target_frame not in FRAMES:
            raise ValueError(f"invalid frame: {target_frame}")
        new_frame = target_frame if self.frame in ("Whole", "SlotF") else self.frame
        return IntExpr(
            kind=self.kind,
            frame=new_frame,
            attr=self.attr,
            npred=self.npred,
            ch=self.ch,
            mod=self.mod,
            sub=self.sub.bind_frame(target_frame) if self.sub is not None else None,
            left=self.left.bind_frame(target_frame) if self.left is not None else None,
            right=self.right.bind_frame(target_frame) if self.right is not None else None,
        )

    def to_data(self) -> dict[str, Any]:
        return {
            "type": "int",
            "kind": self.kind,
            "frame": self.frame,
            "attr": self.attr,
            "npred": self.npred.to_data() if self.npred is not None else None,
            "ch": self.ch,
            "mod": self.mod,
            "sub": self.sub.to_data() if self.sub is not None else None,
            "left": self.left.to_data() if self.left is not None else None,
            "right": self.right.to_data() if self.right is not None else None,
        }

    @property
    def identity(self) -> str:
        return digest(self.to_data())


@dataclass(frozen=True)
class BoolExpr:
    """Closed boolean-valued classifier AST over binary `{a, b}` strings."""

    kind: str
    const_val: bool | None = None
    frame_kind: str | None = None
    frame: str | None = None
    pat: str | None = None
    idx: int | None = None
    ch: str | None = None
    int_sub: IntExpr | None = None
    int_left: IntExpr | None = None
    int_right: IntExpr | None = None
    threshold: int | None = None
    bool_sub: BoolExpr | None = None
    bool_left: BoolExpr | None = None
    bool_right: BoolExpr | None = None

    @property
    def ast_size(self) -> int:
        if self.kind == "const":
            return 1
        if self.kind == "valid_frame":
            return 2
        if self.kind in ("starts_with", "ends_with", "contains", "char_at_eq"):
            return 3
        if self.kind in ("int_eq_const", "int_ge_const", "int_le_const"):
            assert self.int_sub is not None
            return 1 + self.int_sub.ast_size
        if self.kind in ("int_eq", "int_ge"):
            assert self.int_left is not None and self.int_right is not None
            return 1 + self.int_left.ast_size + self.int_right.ast_size
        if self.kind == "not":
            assert self.bool_sub is not None
            return 1 + self.bool_sub.ast_size
        if self.kind in ("and", "or", "bool_eq"):
            assert self.bool_left is not None and self.bool_right is not None
            return 1 + self.bool_left.ast_size + self.bool_right.ast_size
        raise ValueError(f"unknown BoolExpr kind: {self.kind}")

    @property
    def scan_count(self) -> int:
        if self.kind == "const":
            return 0
        if self.kind in ("valid_frame", "starts_with", "ends_with", "contains", "char_at_eq"):
            return 1
        if self.kind in ("int_eq_const", "int_ge_const", "int_le_const"):
            assert self.int_sub is not None
            return self.int_sub.scan_count
        if self.kind in ("int_eq", "int_ge"):
            assert self.int_left is not None and self.int_right is not None
            return self.int_left.scan_count + self.int_right.scan_count
        if self.kind == "not":
            assert self.bool_sub is not None
            return self.bool_sub.scan_count
        if self.kind in ("and", "or", "bool_eq"):
            assert self.bool_left is not None and self.bool_right is not None
            return self.bool_left.scan_count + self.bool_right.scan_count
        return 0

    def eval_parsed(self, parsed: ParsedInput, meter: WorkMeter | None = None) -> bool:
        if self.kind == "const":
            assert self.const_val is not None
            if meter is not None:
                meter.ast_nodes_evaluated += 1
            return self.const_val
        if self.kind == "valid_frame":
            if meter is not None:
                meter.ast_nodes_evaluated += 2
            if self.frame_kind == "single":
                return parsed.valid_dyck and parsed.num_components == 1
            if self.frame_kind == "paired":
                return parsed.valid_dyck and parsed.num_components == 2
            raise ValueError(f"invalid frame_kind: {self.frame_kind}")
        if self.kind in ("starts_with", "ends_with", "contains"):
            assert self.frame is not None and self.pat is not None
            if meter is not None:
                meter.ast_nodes_evaluated += 3
            fs = parsed.get_frame(self.frame)
            if self.frame in ("LeftF", "RightF") and not fs.valid:
                return False
            if self.kind == "starts_with":
                return fs.text.startswith(self.pat)
            if self.kind == "ends_with":
                return fs.text.endswith(self.pat)
            return self.pat in fs.text
        if self.kind == "char_at_eq":
            assert self.frame is not None and self.idx is not None and self.ch is not None
            if meter is not None:
                meter.ast_nodes_evaluated += 3
            fs = parsed.get_frame(self.frame)
            if self.frame in ("LeftF", "RightF") and not fs.valid:
                return False
            return len(fs.text) > self.idx and fs.text[self.idx] == self.ch
        if self.kind in ("int_eq_const", "int_ge_const", "int_le_const"):
            assert self.int_sub is not None and self.threshold is not None
            if meter is not None:
                meter.ast_nodes_evaluated += 1
            val = self.int_sub.eval_parsed(parsed, meter)
            if val is None:
                return False
            if self.kind == "int_eq_const":
                return val == self.threshold
            if self.kind == "int_ge_const":
                return val >= self.threshold
            return val <= self.threshold
        if self.kind in ("int_eq", "int_ge"):
            assert self.int_left is not None and self.int_right is not None
            if meter is not None:
                meter.ast_nodes_evaluated += 1
            lv = self.int_left.eval_parsed(parsed, meter)
            rv = self.int_right.eval_parsed(parsed, meter)
            if lv is None or rv is None:
                return False
            return (lv == rv) if self.kind == "int_eq" else (lv >= rv)
        if self.kind == "not":
            assert self.bool_sub is not None
            if meter is not None:
                meter.ast_nodes_evaluated += 1
            return not self.bool_sub.eval_parsed(parsed, meter)
        if self.kind in ("and", "or", "bool_eq"):
            assert self.bool_left is not None and self.bool_right is not None
            if meter is not None:
                meter.ast_nodes_evaluated += 1
            # Evaluate both branches deterministically for invariant work accounting
            lb = self.bool_left.eval_parsed(parsed, meter)
            rb = self.bool_right.eval_parsed(parsed, meter)
            if self.kind == "and":
                return lb and rb
            if self.kind == "or":
                return lb or rb
            return lb == rb
        raise ValueError(f"unknown BoolExpr kind: {self.kind}")

    def predict(self, word: str, meter: WorkMeter | None = None) -> bool:
        parsed = parse_dyck_input(word, meter=None)
        if meter is not None:
            meter.symbol_steps += self.scan_count * len(word)
        return self.eval_parsed(parsed, meter)

    def bind_frame(self, target_frame: str) -> BoolExpr:
        if target_frame not in FRAMES:
            raise ValueError(f"invalid frame: {target_frame}")
        new_frame = target_frame if self.frame in ("Whole", "SlotF") else self.frame
        return BoolExpr(
            kind=self.kind,
            const_val=self.const_val,
            frame_kind=self.frame_kind,
            frame=new_frame,
            pat=self.pat,
            idx=self.idx,
            ch=self.ch,
            int_sub=self.int_sub.bind_frame(target_frame) if self.int_sub is not None else None,
            int_left=self.int_left.bind_frame(target_frame) if self.int_left is not None else None,
            int_right=self.int_right.bind_frame(target_frame) if self.int_right is not None else None,
            threshold=self.threshold,
            bool_sub=self.bool_sub.bind_frame(target_frame) if self.bool_sub is not None else None,
            bool_left=self.bool_left.bind_frame(target_frame) if self.bool_left is not None else None,
            bool_right=self.bool_right.bind_frame(target_frame) if self.bool_right is not None else None,
        )

    def to_data(self) -> dict[str, Any]:
        return {
            "type": "bool",
            "kind": self.kind,
            "const_val": self.const_val,
            "frame_kind": self.frame_kind,
            "frame": self.frame,
            "pat": self.pat,
            "idx": self.idx,
            "ch": self.ch,
            "int_sub": self.int_sub.to_data() if self.int_sub is not None else None,
            "int_left": self.int_left.to_data() if self.int_left is not None else None,
            "int_right": self.int_right.to_data() if self.int_right is not None else None,
            "threshold": self.threshold,
            "bool_sub": self.bool_sub.to_data() if self.bool_sub is not None else None,
            "bool_left": self.bool_left.to_data() if self.bool_left is not None else None,
            "bool_right": self.bool_right.to_data() if self.bool_right is not None else None,
        }

    @property
    def identity(self) -> str:
        return digest(self.to_data())


def extract_subexpressions(expr: BoolExpr) -> tuple[list[IntExpr], list[BoolExpr]]:
    """Collect all `IntExpr` and `BoolExpr` subtrees inside `expr`."""
    ints: list[IntExpr] = []
    bools: list[BoolExpr] = []

    def walk_int(ie: IntExpr) -> None:
        ints.append(ie)
        if ie.sub is not None:
            walk_int(ie.sub)
        if ie.left is not None:
            walk_int(ie.left)
        if ie.right is not None:
            walk_int(ie.right)

    def walk_bool(be: BoolExpr) -> None:
        bools.append(be)
        if be.int_sub is not None:
            walk_int(be.int_sub)
        if be.int_left is not None:
            walk_int(be.int_left)
        if be.int_right is not None:
            walk_int(be.int_right)
        if be.bool_sub is not None:
            walk_bool(be.bool_sub)
        if be.bool_left is not None:
            walk_bool(be.bool_left)
        if be.bool_right is not None:
            walk_bool(be.bool_right)

    walk_bool(expr)
    return ints, bools


def node_pred_from_data(data: Any) -> NodePred:
    if type(data) is not dict or data.get("type") != "npred":
        raise ValueError("invalid NodePred schema")
    return NodePred(
        op=data["op"],
        attr=data["attr"],
        val=data["val"],
        rem=data["rem"],
    )


def int_expr_from_data(data: Any) -> IntExpr:
    if type(data) is not dict or data.get("type") != "int":
        raise ValueError("invalid IntExpr schema")
    kind = data.get("kind")
    if kind not in ("str_len", "char_count", "max_nodes", "count_nodes", "signed_balance", "mod", "sub"):
        raise ValueError(f"forbidden IntExpr kind: {kind}")
    if data.get("frame") is not None and data["frame"] not in FRAMES:
        raise ValueError("invalid IntExpr frame")
    if data.get("mod") is not None and (type(data["mod"]) is not int or data["mod"] not in MODULI):
        raise ValueError("invalid IntExpr modulus")
    expr = IntExpr(
        kind=kind,
        frame=data["frame"],
        attr=data["attr"],
        npred=node_pred_from_data(data["npred"]) if data["npred"] is not None else None,
        ch=data["ch"],
        mod=data["mod"],
        sub=int_expr_from_data(data["sub"]) if data["sub"] is not None else None,
        left=int_expr_from_data(data["left"]) if data["left"] is not None else None,
        right=int_expr_from_data(data["right"]) if data["right"] is not None else None,
    )
    if expr.identity != digest(data):
        raise ValueError("noncanonical IntExpr data")
    return expr


def bool_expr_from_data(data: Any) -> BoolExpr:
    """Decode only closed `BoolExpr` trees; reject bool/int aliases and arbitrary code."""
    if type(data) is not dict or data.get("type") != "bool":
        raise ValueError("invalid BoolExpr schema")
    kind = data.get("kind")
    allowed = (
        "const", "valid_frame", "starts_with", "ends_with", "contains", "char_at_eq",
        "int_eq_const", "int_ge_const", "int_le_const", "int_eq", "int_ge",
        "not", "and", "or", "bool_eq",
    )
    if kind not in allowed:
        raise ValueError(f"forbidden BoolExpr kind: {kind}")
    if data.get("const_val") is not None and type(data["const_val"]) is not bool:
        raise ValueError("const_val must be strict bool")
    if data.get("threshold") is not None and type(data["threshold"]) is not int:
        raise ValueError("threshold must be strict int")
    if data.get("idx") is not None and type(data["idx"]) is not int:
        raise ValueError("idx must be strict int")
    if data.get("frame") is not None and data["frame"] not in FRAMES:
        raise ValueError("invalid BoolExpr frame")
    expr = BoolExpr(
        kind=kind,
        const_val=data["const_val"],
        frame_kind=data["frame_kind"],
        frame=data["frame"],
        pat=data["pat"],
        idx=data["idx"],
        ch=data["ch"],
        int_sub=int_expr_from_data(data["int_sub"]) if data["int_sub"] is not None else None,
        int_left=int_expr_from_data(data["int_left"]) if data["int_left"] is not None else None,
        int_right=int_expr_from_data(data["int_right"]) if data["int_right"] is not None else None,
        threshold=data["threshold"],
        bool_sub=bool_expr_from_data(data["bool_sub"]) if data["bool_sub"] is not None else None,
        bool_left=bool_expr_from_data(data["bool_left"]) if data["bool_left"] is not None else None,
        bool_right=bool_expr_from_data(data["bool_right"]) if data["bool_right"] is not None else None,
    )
    if expr.identity != digest(data):
        raise ValueError("noncanonical BoolExpr data")
    return expr


def _pack_bools(vec: tuple[bool, ...]) -> int:
    mask = 0
    for i, b in enumerate(vec):
        if b:
            mask |= 1 << i
    return mask


def _unpack_bools(mask: int, n_inputs: int) -> tuple[bool, ...]:
    return tuple(bool((mask >> i) & 1) for i in range(n_inputs))


def synthesize_bottom_up(
    parsed_inputs: tuple[ParsedInput, ...] | list[ParsedInput],
    frames_allowed: tuple[str, ...],
    max_bool_candidates: int,
    meter: WorkMeter,
    max_ast_size: int = 9,
    checkpoints: tuple[int, ...] = (),
    checkpoint_store: dict[int, tuple[list[tuple[BoolExpr, tuple[bool, ...]]], dict[str, int]]] | None = None,
) -> list[tuple[BoolExpr, tuple[bool, ...]]]:
    """Bottom-up observational-equivalence enumerative synthesis over `parsed_inputs`.

    Charges every generated candidate's exact AST size and character scan count to `meter`,
    deduplicating functional equivalence classes on `parsed_inputs` in canonical size order.
    """
    n_inputs = len(parsed_inputs)
    total_chars = sum(len(p.word) for p in parsed_inputs)
    all_ones = (1 << n_inputs) - 1
    checkpoint_set = set(checkpoints) if checkpoint_store is not None else set()

    int_by_size: dict[int, list[tuple[IntExpr, tuple[int | None, ...]]]] = {}
    seen_int_sigs: set[tuple[int | None, ...]] = set()

    bool_by_size: dict[int, list[tuple[BoolExpr, tuple[bool, ...], int, int]]] = {}
    seen_bool_masks: set[int] = set()
    bool_all: list[tuple[BoolExpr, tuple[bool, ...]]] = []

    def _finish() -> list[tuple[BoolExpr, tuple[bool, ...]]]:
        if checkpoint_store is not None:
            for cp in checkpoints:
                if cp not in checkpoint_store:
                    checkpoint_store[cp] = (list(bool_all), meter.to_dict())
        return bool_all

    def try_add_int(ie: IntExpr, vec: tuple[int | None, ...]) -> None:
        meter.charge_expr(ie.ast_size, ie.scan_count, total_chars, n_inputs)
        if vec in seen_int_sigs:
            return
        seen_int_sigs.add(vec)
        int_by_size.setdefault(ie.ast_size, []).append((ie, vec))

    def try_add_bool(be: BoolExpr, vec: tuple[bool, ...]) -> bool:
        meter.charge_expr(be.ast_size, be.scan_count, total_chars, n_inputs)
        mask = _pack_bools(vec)
        if mask in seen_bool_masks:
            return len(bool_all) >= max_bool_candidates
        seen_bool_masks.add(mask)
        bool_by_size.setdefault(be.ast_size, []).append((be, vec, mask, be.scan_count))
        bool_all.append((be, vec))
        if checkpoint_store is not None and len(bool_all) in checkpoint_set:
            checkpoint_store[len(bool_all)] = (list(bool_all), meter.to_dict())
        return len(bool_all) >= max_bool_candidates

    for size in range(1, max_ast_size + 1):
        # 1. Enumerate IntExprs of exact `size` (up to size - 1 needed for Bool readouts)
        if size == 2:
            for f in frames_allowed:
                ie = IntExpr(kind="str_len", frame=f)
                vec = tuple(ie.eval_parsed(p) for p in parsed_inputs)
                try_add_int(ie, vec)
        elif size == 3:
            for f in frames_allowed:
                for ch in ALPHABET:
                    ie = IntExpr(kind="char_count", frame=f, ch=ch)
                    try_add_int(ie, tuple(ie.eval_parsed(p) for p in parsed_inputs))
                for attr in NODE_ATTRS:
                    ie = IntExpr(kind="max_nodes", frame=f, attr=attr)
                    try_add_int(ie, tuple(ie.eval_parsed(p) for p in parsed_inputs))
            for sub_ie, sub_vec in int_by_size.get(2, ()):
                for m in MODULI:
                    ie = IntExpr(kind="mod", mod=m, sub=sub_ie)
                    vec = tuple(None if v is None else (v % m) for v in sub_vec)
                    try_add_int(ie, vec)
        elif size == 4:
            for f in frames_allowed:
                for np in NODE_PREDS:
                    ie_c = IntExpr(kind="count_nodes", frame=f, npred=np)
                    try_add_int(ie_c, tuple(ie_c.eval_parsed(p) for p in parsed_inputs))
                    ie_s = IntExpr(kind="signed_balance", frame=f, npred=np)
                    try_add_int(ie_s, tuple(ie_s.eval_parsed(p) for p in parsed_inputs))
            for sub_ie, sub_vec in int_by_size.get(3, ()):
                for m in MODULI:
                    ie = IntExpr(kind="mod", mod=m, sub=sub_ie)
                    vec = tuple(None if v is None else (v % m) for v in sub_vec)
                    try_add_int(ie, vec)
        elif size >= 5:
            for sub_ie, sub_vec in int_by_size.get(size - 1, ()):
                if sub_ie.kind != "mod":
                    for m in MODULI:
                        ie = IntExpr(kind="mod", mod=m, sub=sub_ie)
                        vec = tuple(None if v is None else (v % m) for v in sub_vec)
                        try_add_int(ie, vec)

        # 2. Enumerate BoolExprs of exact `size`
        if size == 1:
            for cv in (False, True):
                if try_add_bool(BoolExpr(kind="const", const_val=cv), (cv,) * n_inputs):
                    return _finish()
        elif size == 2:
            for fk in ("single", "paired"):
                be = BoolExpr(kind="valid_frame", frame_kind=fk)
                if try_add_bool(be, tuple(be.eval_parsed(p) for p in parsed_inputs)):
                    return _finish()
        elif size == 3:
            for f in frames_allowed:
                for pat in PATTERNS_1_TO_3:
                    for kind in ("starts_with", "ends_with", "contains"):
                        be = BoolExpr(kind=kind, frame=f, pat=pat)
                        if try_add_bool(be, tuple(be.eval_parsed(p) for p in parsed_inputs)):
                            return _finish()
                for idx in (0, 1, 2, 3):
                    for ch in ALPHABET:
                        be = BoolExpr(kind="char_at_eq", frame=f, idx=idx, ch=ch)
                        if try_add_bool(be, tuple(be.eval_parsed(p) for p in parsed_inputs)):
                            return _finish()
            for sub_ie, sub_vec in int_by_size.get(2, ()):
                for c in (0, 1, 2, 3, 4):
                    if try_add_bool(
                        BoolExpr(kind="int_eq_const", int_sub=sub_ie, threshold=c),
                        tuple(v is not None and v == c for v in sub_vec),
                    ):
                        return _finish()

        if size >= 4:
            # 2a. Int threshold & modular constant comparisons (`1 + |int_sub| == size`)
            for sub_ie, sub_vec in int_by_size.get(size - 1, ()):
                eq_consts = tuple(range(sub_ie.mod)) if sub_ie.kind == "mod" and sub_ie.mod else (0, 1, 2, 3, 4)
                for c in eq_consts:
                    if try_add_bool(
                        BoolExpr(kind="int_eq_const", int_sub=sub_ie, threshold=c),
                        tuple(v is not None and v == c for v in sub_vec),
                    ):
                        return _finish()
                if sub_ie.kind != "mod":
                    for c in (1, 2, 3, 4):
                        if try_add_bool(
                            BoolExpr(kind="int_ge_const", int_sub=sub_ie, threshold=c),
                            tuple(v is not None and v >= c for v in sub_vec),
                        ):
                            return _finish()
                    for c in (0, 1, 2, 3):
                        if try_add_bool(
                            BoolExpr(kind="int_le_const", int_sub=sub_ie, threshold=c),
                            tuple(v is not None and v <= c for v in sub_vec),
                        ):
                            return _finish()

            # 2b. Binary integer relations `IntEq(e1, e2)` (`1 + s1 + s2 == size`)
            for s1 in range(2, size - 2):
                s2 = size - 1 - s1
                if s2 < s1:
                    continue
                list1 = int_by_size.get(s1, ())
                list2 = int_by_size.get(s2, ())
                for i1, (ie1, vec1) in enumerate(list1):
                    start2 = (i1 + 1) if s1 == s2 else 0
                    for ie2, vec2 in list2[start2:]:
                        be_eq = BoolExpr(kind="int_eq", int_left=ie1, int_right=ie2)
                        vec_eq = tuple(a is not None and b is not None and a == b for a, b in zip(vec1, vec2))
                        if try_add_bool(be_eq, vec_eq):
                            return _finish()

            # 2c. Negations `BoolNot(sub)` (`1 + |sub| == size`)
            for sub_be, sub_vec, sub_mask, sub_scans in bool_by_size.get(size - 1, ()):
                if sub_be.kind != "not":
                    meter.charge_expr(size, sub_scans, total_chars, n_inputs)
                    mask_not = all_ones ^ sub_mask
                    if mask_not not in seen_bool_masks:
                        be_not = BoolExpr(kind="not", bool_sub=sub_be)
                        vec_not = tuple(not b for b in sub_vec)
                        seen_bool_masks.add(mask_not)
                        bool_by_size.setdefault(size, []).append((be_not, vec_not, mask_not, sub_scans))
                        bool_all.append((be_not, vec_not))
                        if checkpoint_store is not None and len(bool_all) in checkpoint_set:
                            checkpoint_store[len(bool_all)] = (list(bool_all), meter.to_dict())
                    if len(bool_all) >= max_bool_candidates:
                        return _finish()

            # 2d. Boolean conjunctions / disjunctions (`1 + s1 + s2 == size`)
            for s1 in range(2, size - 2):
                s2 = size - 1 - s1
                if s2 < s1:
                    continue
                blist1 = bool_by_size.get(s1, ())
                blist2 = bool_by_size.get(s2, ())
                for i1, (be1, _bvec1, m1, sc1) in enumerate(blist1):
                    start2 = (i1 + 1) if s1 == s2 else 0
                    for be2, _bvec2, m2, sc2 in blist2[start2:]:
                        comb_scans = sc1 + sc2

                        meter.charge_expr(size, comb_scans, total_chars, n_inputs)
                        m_and = m1 & m2
                        if m_and not in seen_bool_masks:
                            be_and = BoolExpr(kind="and", bool_left=be1, bool_right=be2)
                            vec_and = _unpack_bools(m_and, n_inputs)
                            seen_bool_masks.add(m_and)
                            bool_by_size.setdefault(size, []).append((be_and, vec_and, m_and, comb_scans))
                            bool_all.append((be_and, vec_and))
                            if checkpoint_store is not None and len(bool_all) in checkpoint_set:
                                checkpoint_store[len(bool_all)] = (list(bool_all), meter.to_dict())
                        if len(bool_all) >= max_bool_candidates:
                            return _finish()

                        meter.charge_expr(size, comb_scans, total_chars, n_inputs)
                        m_or = m1 | m2
                        if m_or not in seen_bool_masks:
                            be_or = BoolExpr(kind="or", bool_left=be1, bool_right=be2)
                            vec_or = _unpack_bools(m_or, n_inputs)
                            seen_bool_masks.add(m_or)
                            bool_by_size.setdefault(size, []).append((be_or, vec_or, m_or, comb_scans))
                            bool_all.append((be_or, vec_or))
                            if checkpoint_store is not None and len(bool_all) in checkpoint_set:
                                checkpoint_store[len(bool_all)] = (list(bool_all), meter.to_dict())
                        if len(bool_all) >= max_bool_candidates:
                            return _finish()

    return _finish()
