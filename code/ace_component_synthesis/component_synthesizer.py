"""SyGuS-style Type-Directed Component-Based Program Synthesizer.

Mathematical Foundation & Synthesis Architecture:
1. Type-Directed Component Library:
   Typed functional components with explicit signatures:
   - Integer Arithmetic: (+, -, *, mod, count, len)
   - Boolean Logic: (and, or, not, startswith, endswith, contains)
   - Relational Predicates: (==, !=, <, >, <=, >=)
   - Conditional Multiplexing: (ite_int, ite_bool, ite_str)

2. Forward Valuation:
   Given input environments E = [in_1, in_2, ..., in_m], each candidate expression e
   is evaluated to produce a valuation vector:
     V(e) = (e(in_1), e(in_2), ..., e(in_m))
   Expressions producing runtime undefinedness (e.g., division by zero) are rejected.

3. Observational Equivalence (OE) Pruning:
   Two expressions e_1 and e_2 of the same type are observationally equivalent over E iff:
     V(e_1) == V(e_2)
   Only one canonical representative of each semantic equivalence class is retained.
   All redundant syntactic variations (e.g. x + 0, x * 1, y + x vs x + y, sub(x, x))
   are aggressively pruned, collapsing combinatorial explosion into a compact tractable set.

4. Stratified Component Composition:
   Constructs programs level-by-level:
   - Level 0: Terminal inputs (typed variables and constant pool).
   - Level k: Combinations of library components where at least one sub-expression
     originates from Level k-1, evaluated and filtered via OE pruning until 100%
     of the target I/O specification is satisfied.

Provenance: ADVISOR_AGENT
"""
from __future__ import annotations

from dataclasses import dataclass, field
import itertools
import time
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Set, Tuple, Union

TYPE_INT = "int"
TYPE_BOOL = "bool"
TYPE_STR = "str"


@dataclass(frozen=True)
class Component:
    """A strongly-typed primitive operator in the component library."""

    name: str
    arg_types: Tuple[str, ...]
    return_type: str
    fn: Callable[..., Any]
    to_code_fn: Optional[Callable[[List[str]], str]] = None
    description: str = ""

    def evaluate(self, args: Sequence[Any]) -> Any:
        return self.fn(*args)

    def to_code(self, arg_codes: List[str]) -> str:
        if self.to_code_fn:
            return self.to_code_fn(arg_codes)
        return f"{self.name}({', '.join(arg_codes)})"


class ComponentNode:
    """AST node in the synthesized component program."""

    def __init__(
        self,
        name: str,
        return_type: str,
        node_type: str = "OP",  # "VAR", "CONST", "OP"
        children: Optional[List[ComponentNode]] = None,
        val: Any = None,
        component: Optional[Component] = None,
    ):
        self.name = name
        self.return_type = return_type
        self.node_type = node_type
        self.children = children or []
        self.val = val
        self.component = component

    def evaluate(self, env: Dict[str, Any]) -> Any:
        if self.node_type == "VAR":
            if self.val not in env:
                raise KeyError(f"Variable '{self.val}' not present in evaluation environment")
            return env[self.val]
        elif self.node_type == "CONST":
            return self.val
        elif self.node_type == "OP":
            if not self.component:
                raise ValueError(f"Operator node '{self.name}' has no bound Component")
            arg_vals = [child.evaluate(env) for child in self.children]
            return self.component.evaluate(arg_vals)
        raise ValueError(f"Unknown node type: {self.node_type}")

    def size(self) -> int:
        return 1 + sum(child.size() for child in self.children)

    def depth(self) -> int:
        if not self.children:
            return 1
        return 1 + max(child.depth() for child in self.children)

    def to_code(self) -> str:
        if self.node_type == "VAR":
            return str(self.val)
        elif self.node_type == "CONST":
            return repr(self.val)
        elif self.node_type == "OP":
            child_codes = [c.to_code() for c in self.children]
            if self.component:
                return self.component.to_code(child_codes)
            return f"{self.name}({', '.join(child_codes)})"
        return self.name

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "return_type": self.return_type,
            "node_type": self.node_type,
            "val": self.val,
            "code": self.to_code(),
            "size": self.size(),
            "depth": self.depth(),
            "children": [c.to_dict() for c in self.children],
        }

    def compile_to_callable(self, var_names: List[str]) -> Callable[..., Any]:
        """Compiles this AST node into a high-performance native Python callable."""
        code_str = f"def synthesized_fn({', '.join(var_names)}):\n    return {self.to_code()}"
        local_ns: Dict[str, Any] = {}
        exec(code_str, local_ns)
        return local_ns["synthesized_fn"]

    def to_typed_ast(self) -> Any:
        """Converts to TypedASTNode compatible with ace_evolution.island_search."""
        try:
            from ace_evolution.island_search import TypedASTNode
        except ImportError:
            return None

        ret_type_map = {TYPE_INT: "INT", TYPE_BOOL: "BOOL"}
        target_ret = ret_type_map.get(self.return_type, "INT")

        if self.node_type == "CONST":
            if self.return_type == TYPE_INT:
                return TypedASTNode("int_const", "INT", val=self.val)
            elif self.return_type == TYPE_BOOL:
                return TypedASTNode("bool_const", "BOOL", val=self.val)
            return TypedASTNode("macro_const", target_ret, val=self.val)

        if self.node_type == "VAR":
            if self.val in ("word", "s"):
                return TypedASTNode("len", "INT")  # default fallback
            return TypedASTNode(f"var_{self.val}", target_ret, val=self.val)

        # OP nodes
        op_map = {
            "add": "add",
            "sub": "sub",
            "mul": "mul",
            "mod": "mod",
            "eq": "eq",
            "neq": "neq",
            "lt": "lt",
            "gt": "gt",
            "lte": "lte",
            "gte": "gte",
            "and": "and",
            "or": "or",
            "not": "not",
            "len": "len",
        }
        child_nodes = [c.to_typed_ast() for c in self.children]
        mapped_op = op_map.get(self.name)
        if mapped_op:
            return TypedASTNode(mapped_op, target_ret, children=child_nodes)

        if self.name == "startswith" and len(self.children) == 2 and self.children[1].node_type == "CONST":
            return TypedASTNode("starts_with", "BOOL", val=self.children[1].val)
        if self.name == "endswith" and len(self.children) == 2 and self.children[1].node_type == "CONST":
            return TypedASTNode("ends_with", "BOOL", val=self.children[1].val)
        if self.name == "contains" and len(self.children) == 2 and self.children[1].node_type == "CONST":
            return TypedASTNode("contains", "BOOL", val=self.children[1].val)
        if self.name == "count" and len(self.children) == 2 and self.children[1].node_type == "CONST":
            if self.children[1].val == "a":
                return TypedASTNode("count_a", "INT")
            elif self.children[1].val == "b":
                return TypedASTNode("count_b", "INT")

        return TypedASTNode(f"macro_{self.name}", target_ret, children=child_nodes, val=self.evaluate)

    def __repr__(self) -> str:
        return f"ComponentNode({self.to_code()}:{self.return_type})"


def _safe_mod(a: int, b: int) -> int:
    if b == 0:
        raise ZeroDivisionError("Modulo by zero")
    return a % b


class ComponentLibrary:
    """Registry of strongly-typed primitives for component-based synthesis."""

    def __init__(self):
        self._components: Dict[str, Component] = {}

    def register(self, component: Component) -> None:
        self._components[component.name] = component

    def get(self, name: str) -> Component:
        return self._components[name]

    def all_components(self) -> List[Component]:
        return list(self._components.values())

    def components_for_types(self, arg_types: Tuple[str, ...]) -> List[Component]:
        return [c for c in self._components.values() if c.arg_types == arg_types]

    def components_by_return_type(self, ret_type: str) -> List[Component]:
        return [c for c in self._components.values() if c.return_type == ret_type]

    @classmethod
    def default(cls) -> ComponentLibrary:
        """Constructs the standard SyGuS type-directed component library."""
        lib = cls()

        # 1. Integer Arithmetic Operators
        lib.register(Component(
            name="add",
            arg_types=(TYPE_INT, TYPE_INT),
            return_type=TYPE_INT,
            fn=lambda a, b: a + b,
            to_code_fn=lambda c: f"({c[0]} + {c[1]})",
            description="Integer addition",
        ))
        lib.register(Component(
            name="sub",
            arg_types=(TYPE_INT, TYPE_INT),
            return_type=TYPE_INT,
            fn=lambda a, b: a - b,
            to_code_fn=lambda c: f"({c[0]} - {c[1]})",
            description="Integer subtraction",
        ))
        lib.register(Component(
            name="mul",
            arg_types=(TYPE_INT, TYPE_INT),
            return_type=TYPE_INT,
            fn=lambda a, b: a * b,
            to_code_fn=lambda c: f"({c[0]} * {c[1]})",
            description="Integer multiplication",
        ))
        lib.register(Component(
            name="mod",
            arg_types=(TYPE_INT, TYPE_INT),
            return_type=TYPE_INT,
            fn=_safe_mod,
            to_code_fn=lambda c: f"({c[0]} % {c[1]})",
            description="Integer modulo with zero protection",
        ))
        lib.register(Component(
            name="count",
            arg_types=(TYPE_STR, TYPE_STR),
            return_type=TYPE_INT,
            fn=lambda s, sub: s.count(sub),
            to_code_fn=lambda c: f"{c[0]}.count({c[1]})",
            description="Count substring occurrences in string",
        ))
        lib.register(Component(
            name="len",
            arg_types=(TYPE_STR,),
            return_type=TYPE_INT,
            fn=lambda s: len(s),
            to_code_fn=lambda c: f"len({c[0]})",
            description="String length",
        ))

        # 2. Boolean Logic Operators
        lib.register(Component(
            name="and",
            arg_types=(TYPE_BOOL, TYPE_BOOL),
            return_type=TYPE_BOOL,
            fn=lambda a, b: bool(a and b),
            to_code_fn=lambda c: f"({c[0]} and {c[1]})",
            description="Logical conjunction",
        ))
        lib.register(Component(
            name="or",
            arg_types=(TYPE_BOOL, TYPE_BOOL),
            return_type=TYPE_BOOL,
            fn=lambda a, b: bool(a or b),
            to_code_fn=lambda c: f"({c[0]} or {c[1]})",
            description="Logical disjunction",
        ))
        lib.register(Component(
            name="not",
            arg_types=(TYPE_BOOL,),
            return_type=TYPE_BOOL,
            fn=lambda a: not a,
            to_code_fn=lambda c: f"(not {c[0]})",
            description="Logical negation",
        ))
        lib.register(Component(
            name="startswith",
            arg_types=(TYPE_STR, TYPE_STR),
            return_type=TYPE_BOOL,
            fn=lambda s, prefix: s.startswith(prefix),
            to_code_fn=lambda c: f"{c[0]}.startswith({c[1]})",
            description="String prefix predicate",
        ))
        lib.register(Component(
            name="endswith",
            arg_types=(TYPE_STR, TYPE_STR),
            return_type=TYPE_BOOL,
            fn=lambda s, suffix: s.endswith(suffix),
            to_code_fn=lambda c: f"{c[0]}.endswith({c[1]})",
            description="String suffix predicate",
        ))
        lib.register(Component(
            name="contains",
            arg_types=(TYPE_STR, TYPE_STR),
            return_type=TYPE_BOOL,
            fn=lambda s, sub: sub in s,
            to_code_fn=lambda c: f"({c[1]} in {c[0]})",
            description="Substring containment predicate",
        ))

        # 3. Relational Comparison Operators
        lib.register(Component(
            name="eq",
            arg_types=(TYPE_INT, TYPE_INT),
            return_type=TYPE_BOOL,
            fn=lambda a, b: a == b,
            to_code_fn=lambda c: f"({c[0]} == {c[1]})",
            description="Integer equality comparison",
        ))
        lib.register(Component(
            name="eq_str",
            arg_types=(TYPE_STR, TYPE_STR),
            return_type=TYPE_BOOL,
            fn=lambda a, b: a == b,
            to_code_fn=lambda c: f"({c[0]} == {c[1]})",
            description="String equality comparison",
        ))
        lib.register(Component(
            name="neq",
            arg_types=(TYPE_INT, TYPE_INT),
            return_type=TYPE_BOOL,
            fn=lambda a, b: a != b,
            to_code_fn=lambda c: f"({c[0]} != {c[1]})",
            description="Integer inequality comparison",
        ))
        lib.register(Component(
            name="neq_str",
            arg_types=(TYPE_STR, TYPE_STR),
            return_type=TYPE_BOOL,
            fn=lambda a, b: a != b,
            to_code_fn=lambda c: f"({c[0]} != {c[1]})",
            description="String inequality comparison",
        ))
        lib.register(Component(
            name="lt",
            arg_types=(TYPE_INT, TYPE_INT),
            return_type=TYPE_BOOL,
            fn=lambda a, b: a < b,
            to_code_fn=lambda c: f"({c[0]} < {c[1]})",
            description="Strictly less than comparison",
        ))
        lib.register(Component(
            name="gt",
            arg_types=(TYPE_INT, TYPE_INT),
            return_type=TYPE_BOOL,
            fn=lambda a, b: a > b,
            to_code_fn=lambda c: f"({c[0]} > {c[1]})",
            description="Strictly greater than comparison",
        ))
        lib.register(Component(
            name="lte",
            arg_types=(TYPE_INT, TYPE_INT),
            return_type=TYPE_BOOL,
            fn=lambda a, b: a <= b,
            to_code_fn=lambda c: f"({c[0]} <= {c[1]})",
            description="Less than or equal comparison",
        ))
        lib.register(Component(
            name="gte",
            arg_types=(TYPE_INT, TYPE_INT),
            return_type=TYPE_BOOL,
            fn=lambda a, b: a >= b,
            to_code_fn=lambda c: f"({c[0]} >= {c[1]})",
            description="Greater than or equal comparison",
        ))

        # 4. Conditional (ITE) Primitives
        lib.register(Component(
            name="ite_int",
            arg_types=(TYPE_BOOL, TYPE_INT, TYPE_INT),
            return_type=TYPE_INT,
            fn=lambda cond, t, f: t if cond else f,
            to_code_fn=lambda c: f"({c[1]} if {c[0]} else {c[2]})",
            description="Integer conditional multiplexer",
        ))
        lib.register(Component(
            name="ite_bool",
            arg_types=(TYPE_BOOL, TYPE_BOOL, TYPE_BOOL),
            return_type=TYPE_BOOL,
            fn=lambda cond, t, f: t if cond else f,
            to_code_fn=lambda c: f"({c[1]} if {c[0]} else {c[2]})",
            description="Boolean conditional multiplexer",
        ))
        lib.register(Component(
            name="ite_str",
            arg_types=(TYPE_BOOL, TYPE_STR, TYPE_STR),
            return_type=TYPE_STR,
            fn=lambda cond, t, f: t if cond else f,
            to_code_fn=lambda c: f"({c[1]} if {c[0]} else {c[2]})",
            description="String conditional multiplexer",
        ))

        return lib


def compute_forward_valuation(
    node: ComponentNode,
    inputs: Sequence[Dict[str, Any]],
) -> Optional[Tuple[Any, ...]]:
    """Evaluates node across all input environments to produce the valuation signature vector.
    
    Returns None if any evaluation triggers an exception (e.g. division by zero).
    """
    valuation: List[Any] = []
    for env in inputs:
        try:
            val = node.evaluate(env)
            # Ensure boolean values are strict booleans
            if node.return_type == TYPE_BOOL:
                val = bool(val)
            valuation.append(val)
        except Exception:
            return None
    return tuple(valuation)


class ObservationalEquivalenceStore:
    """Tracks and partitions semantic equivalence classes over sample input observations.
    
    Prunes redundant candidate expressions that produce identical output behavior
    to an already registered program.
    """

    def __init__(self):
        self.classes: Dict[Tuple[str, Tuple[Any, ...]], ComponentNode] = {}
        self.pruned_count: int = 0
        self.retained_count: int = 0

    def is_equivalent(self, return_type: str, valuation: Tuple[Any, ...]) -> bool:
        return (return_type, valuation) in self.classes

    def register(self, node: ComponentNode, valuation: Tuple[Any, ...]) -> bool:
        """Registers a node if its valuation is novel.
        Returns True if retained, False if observationally equivalent and pruned.
        """
        key = (node.return_type, valuation)
        if key in self.classes:
            self.pruned_count += 1
            return False
        self.classes[key] = node
        self.retained_count += 1
        return True

    def get_representative(self, return_type: str, valuation: Tuple[Any, ...]) -> Optional[ComponentNode]:
        return self.classes.get((return_type, valuation))

    def equivalence_classes_count(self) -> int:
        return len(self.classes)


@dataclass
class SynthesisResult:
    """Result of component-based program synthesis."""

    status: str  # "SUCCESS", "TIMEOUT", "UNSAT"
    program: Optional[ComponentNode]
    code: str
    candidates_generated: int
    candidates_pruned_oe: int
    candidates_retained: int
    levels_explored: int
    runtime_sec: float
    equivalence_classes: int
    provenance: str = "ADVISOR_AGENT"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "code": self.code,
            "candidates_generated": self.candidates_generated,
            "candidates_pruned_oe": self.candidates_pruned_oe,
            "candidates_retained": self.candidates_retained,
            "levels_explored": self.levels_explored,
            "runtime_sec": self.runtime_sec,
            "equivalence_classes": self.equivalence_classes,
            "provenance": self.provenance,
            "program": self.program.to_dict() if self.program else None,
        }


def _infer_type(val: Any) -> str:
    if isinstance(val, bool):
        return TYPE_BOOL
    elif isinstance(val, int):
        return TYPE_INT
    elif isinstance(val, str):
        return TYPE_STR
    raise TypeError(f"Unsupported synthesis type for value: {val!r}")


def _normalize_spec(
    spec: Sequence[Tuple[Union[Dict[str, Any], Any], Any]],
    var_name: str = "x",
) -> Tuple[List[Dict[str, Any]], Tuple[Any, ...], Dict[str, str], str]:
    """Normalizes input/output pairs into standard environment dictionaries and target vectors."""
    if not spec:
        raise ValueError("Specification cannot be empty")

    envs: List[Dict[str, Any]] = []
    outputs: List[Any] = []
    var_types: Dict[str, str] = {}

    first_in, first_out = spec[0]
    target_type = _infer_type(first_out)

    for in_val, out_val in spec:
        if isinstance(in_val, dict):
            env = in_val
            for k, v in env.items():
                v_type = _infer_type(v)
                if k in var_types and var_types[k] != v_type:
                    raise TypeError(f"Inconsistent types for variable '{k}': {var_types[k]} vs {v_type}")
                var_types[k] = v_type
        else:
            env = {var_name: in_val}
            v_type = _infer_type(in_val)
            var_types[var_name] = v_type

        # Ensure boolean output normalization
        if target_type == TYPE_BOOL:
            out_val = bool(out_val)
        envs.append(env)
        outputs.append(out_val)

    return envs, tuple(outputs), var_types, target_type


class ComponentSynthesizer:
    """SyGuS-style Stratified Type-Directed Component Synthesizer with Observational Equivalence Pruning."""

    def __init__(
        self,
        library: Optional[ComponentLibrary] = None,
        max_level: int = 4,
        max_candidates: int = 50000,
        timeout_sec: float = 30.0,
    ):
        self.library = library or ComponentLibrary.default()
        self.max_level = max_level
        self.max_candidates = max_candidates
        self.timeout_sec = timeout_sec

    def synthesize(
        self,
        specification: Sequence[Tuple[Union[Dict[str, Any], Any], Any]],
        constants: Optional[Sequence[Union[Any, Tuple[Any, str]]]] = None,
        custom_components: Optional[Sequence[Component]] = None,
        default_var_name: str = "x",
    ) -> SynthesisResult:
        """Synthesizes a typed component expression satisfying 100% of the given I/O specification."""
        start_time = time.time()

        # 1. Normalize specifications & inputs
        envs, target_vector, var_types, target_type = _normalize_spec(specification, var_name=default_var_name)

        # 2. Setup Library and Components
        active_library = self.library
        if custom_components:
            active_library = ComponentLibrary()
            for comp in self.library.all_components():
                active_library.register(comp)
            for comp in custom_components:
                active_library.register(comp)

        # 3. Setup Observational Equivalence Store
        oe_store = ObservationalEquivalenceStore()
        candidates_generated = 0

        # 4. Prepare Constants
        processed_constants: List[Tuple[Any, str]] = []
        # Built-in sensible constants
        default_consts = [
            (0, TYPE_INT),
            (1, TYPE_INT),
            (2, TYPE_INT),
            (True, TYPE_BOOL),
            (False, TYPE_BOOL),
            ("", TYPE_STR),
        ]
        # Auto-extract string constants from envs and outputs
        auto_strings: Set[str] = set()
        for env in envs:
            for v in env.values():
                if isinstance(v, str):
                    for char in v:
                        auto_strings.add(char)
        for s in auto_strings:
            default_consts.append((s, TYPE_STR))

        seen_consts: Set[Tuple[Any, str]] = set()
        for c in default_consts:
            if c not in seen_consts:
                seen_consts.add(c)
                processed_constants.append(c)

        if constants:
            for item in constants:
                if isinstance(item, tuple) and len(item) == 2:
                    c_val, c_type = item
                else:
                    c_val = item
                    c_type = _infer_type(c_val)
                c_pair = (c_val, c_type)
                if c_pair not in seen_consts:
                    seen_consts.add(c_pair)
                    processed_constants.append(c_pair)

        # 5. Stratification Data Structures:
        # pool_by_level[k][type] = list of ComponentNode
        # all_nodes[type] = list of ComponentNode from all levels
        pool_by_level: Dict[int, Dict[str, List[ComponentNode]]] = {}
        all_nodes: Dict[str, List[ComponentNode]] = {TYPE_INT: [], TYPE_BOOL: [], TYPE_STR: []}

        # Initialize Level 0
        pool_by_level[0] = {TYPE_INT: [], TYPE_BOOL: [], TYPE_STR: []}

        # Level 0: Variables
        for v_name, v_type in var_types.items():
            candidates_generated += 1
            node = ComponentNode(name=v_name, return_type=v_type, node_type="VAR", val=v_name)
            valuation = compute_forward_valuation(node, envs)
            if valuation is not None:
                if v_type == target_type and valuation == target_vector:
                    runtime = time.time() - start_time
                    oe_store.register(node, valuation)
                    return SynthesisResult(
                        status="SUCCESS",
                        program=node,
                        code=node.to_code(),
                        candidates_generated=candidates_generated,
                        candidates_pruned_oe=oe_store.pruned_count,
                        candidates_retained=oe_store.retained_count,
                        levels_explored=1,
                        runtime_sec=runtime,
                        equivalence_classes=oe_store.equivalence_classes_count(),
                        provenance="ADVISOR_AGENT",
                    )
                if oe_store.register(node, valuation):
                    pool_by_level[0][v_type].append(node)
                    all_nodes[v_type].append(node)

        # Level 0: Constants
        for c_val, c_type in processed_constants:
            candidates_generated += 1
            node = ComponentNode(name=str(c_val), return_type=c_type, node_type="CONST", val=c_val)
            valuation = compute_forward_valuation(node, envs)
            if valuation is not None:
                if c_type == target_type and valuation == target_vector:
                    runtime = time.time() - start_time
                    oe_store.register(node, valuation)
                    return SynthesisResult(
                        status="SUCCESS",
                        program=node,
                        code=node.to_code(),
                        candidates_generated=candidates_generated,
                        candidates_pruned_oe=oe_store.pruned_count,
                        candidates_retained=oe_store.retained_count,
                        levels_explored=1,
                        runtime_sec=runtime,
                        equivalence_classes=oe_store.equivalence_classes_count(),
                        provenance="ADVISOR_AGENT",
                    )
                if oe_store.register(node, valuation):
                    pool_by_level[0][c_type].append(node)
                    all_nodes[c_type].append(node)

        # 6. Stratified Composition Loop (Levels 1 to max_level)
        for level in range(1, self.max_level + 1):
            if time.time() - start_time > self.timeout_sec:
                break

            pool_by_level[level] = {TYPE_INT: [], TYPE_BOOL: [], TYPE_STR: []}
            prev_level_nodes = pool_by_level[level - 1]

            # If previous level produced no new novel expressions, we reached a fixed point
            if not any(len(nodes) > 0 for nodes in prev_level_nodes.values()):
                break

            # Prior nodes strictly from levels 0 .. level-2
            prior_nodes: Dict[str, List[ComponentNode]] = {
                t: [n for l in range(level - 1) for n in pool_by_level[l][t]]
                for t in (TYPE_INT, TYPE_BOOL, TYPE_STR)
            }

            for comp in active_library.all_components():
                if time.time() - start_time > self.timeout_sec or candidates_generated >= self.max_candidates:
                    break

                arity = len(comp.arg_types)
                if arity == 0:
                    continue

                # Generate argument combinations where AT LEAST ONE argument is from level - 1
                # To partition cleanly without generating duplicates:
                # We iterate over which argument positions must be from prev_level_nodes
                # Specifically: for a fixed index 'pivot' (the first argument coming from level - 1):
                #   args[0 .. pivot-1] come from prior_nodes
                #   args[pivot] comes from prev_level_nodes
                #   args[pivot+1 .. arity-1] come from all_nodes (prior + prev_level)
                for pivot in range(arity):
                    pivot_type = comp.arg_types[pivot]
                    pivot_choices = prev_level_nodes.get(pivot_type, [])
                    if not pivot_choices:
                        continue

                    # Preceding choices
                    preceding_pools = [prior_nodes.get(comp.arg_types[i], []) for i in range(pivot)]
                    if any(len(p) == 0 for p in preceding_pools):
                        continue

                    # Succeeding choices
                    succeeding_pools = [all_nodes.get(comp.arg_types[i], []) for i in range(pivot + 1, arity)]
                    if any(len(p) == 0 for p in succeeding_pools):
                        continue

                    # Form cartesian product
                    all_arg_pools = preceding_pools + [pivot_choices] + succeeding_pools

                    for arg_tuple in itertools.product(*all_arg_pools):
                        candidates_generated += 1
                        if candidates_generated % 500 == 0:
                            if time.time() - start_time > self.timeout_sec or candidates_generated >= self.max_candidates:
                                break

                        cand_node = ComponentNode(
                            name=comp.name,
                            return_type=comp.return_type,
                            node_type="OP",
                            children=list(arg_tuple),
                            component=comp,
                        )

                        # Forward valuation
                        cand_valuation = compute_forward_valuation(cand_node, envs)
                        if cand_valuation is None:
                            continue

                        # Check 100% specification satisfaction
                        if comp.return_type == target_type and cand_valuation == target_vector:
                            runtime = time.time() - start_time
                            oe_store.register(cand_node, cand_valuation)
                            return SynthesisResult(
                                status="SUCCESS",
                                program=cand_node,
                                code=cand_node.to_code(),
                                candidates_generated=candidates_generated,
                                candidates_pruned_oe=oe_store.pruned_count,
                                candidates_retained=oe_store.retained_count,
                                levels_explored=level + 1,
                                runtime_sec=runtime,
                                equivalence_classes=oe_store.equivalence_classes_count(),
                                provenance="ADVISOR_AGENT",
                            )

                        # Observational Equivalence Pruning
                        if oe_store.register(cand_node, cand_valuation):
                            pool_by_level[level][comp.return_type].append(cand_node)

            # Update all_nodes with newly retained nodes from this level
            for t in (TYPE_INT, TYPE_BOOL, TYPE_STR):
                all_nodes[t].extend(pool_by_level[level][t])

        runtime = time.time() - start_time
        status = "TIMEOUT" if runtime > self.timeout_sec or candidates_generated >= self.max_candidates else "UNSAT"
        return SynthesisResult(
            status=status,
            program=None,
            code="",
            candidates_generated=candidates_generated,
            candidates_pruned_oe=oe_store.pruned_count,
            candidates_retained=oe_store.retained_count,
            levels_explored=len(pool_by_level),
            runtime_sec=runtime,
            equivalence_classes=oe_store.equivalence_classes_count(),
            provenance="ADVISOR_AGENT",
        )
