"""E1.6-V3: Bounded, Typed Source-Code Mutation Engine for Autonomous Self-Development.

Produces and compiles deterministic Python source code from strongly typed gene specifications.
Supports:
- Atomic TypedGene expressions: single modular combinations.
- CompositeGene expressions: compositional combinations using algebraic and bitwise operators (ADD, SUB, XOR, MULT).
Enforces strict AST safety boundaries:
- Pure functions only (no imports, no system calls, no I/O, no eval/exec).
- Whitelisted AST node types: FunctionDef, Return, BinOp, UnaryOp, BitXor, Name, Constant.
- Clean execution environment with empty builtins.
- Cryptographic hash verification of source bytes (source_sha).
"""
from __future__ import annotations

import ast
from dataclasses import dataclass
import hashlib
from typing import Any, Callable, Dict, List, Optional, Tuple, Union


class SourceEvolutionError(ValueError):
    """Raised when source mutation or validation violates security or typing bounds."""


def compute_sha(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def _check_int(val: Any, lo: int, hi: int, name: str) -> int:
    if type(val) is not int or not (lo <= val <= hi):
        raise SourceEvolutionError(f"{name} must be integer between {lo} and {hi}, got {val}")
    return val


@dataclass(frozen=True)
class TypedGene:
    """Strongly-typed gene defining algorithmic ranking or classification behavior."""
    window_stride: int       # 1 to 4
    modulus: int             # 2 to 11
    parity_threshold: int    # 0 to 5
    weight_length: int       # -8 to 8
    weight_density: int      # -8 to 8
    sign: int                # -1 or 1

    def __post_init__(self):
        _check_int(self.window_stride, 1, 4, "window_stride")
        _check_int(self.modulus, 2, 11, "modulus")
        _check_int(self.parity_threshold, 0, 5, "parity_threshold")
        _check_int(self.weight_length, -8, 8, "weight_length")
        _check_int(self.weight_density, -8, 8, "weight_density")
        if self.sign not in (-1, 1):
            raise SourceEvolutionError("sign must be -1 or 1")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_composite": False,
            "window_stride": self.window_stride,
            "modulus": self.modulus,
            "parity_threshold": self.parity_threshold,
            "weight_length": self.weight_length,
            "weight_density": self.weight_density,
            "sign": self.sign,
        }


@dataclass(frozen=True)
class CompositeGene:
    """Strongly-typed composite gene combining dual mechanisms via algebraic or bitwise operators."""
    gene_a: TypedGene
    gene_b: TypedGene
    operator: str  # "ADD", "SUB", "XOR", "MULT"

    def __post_init__(self):
        if not isinstance(self.gene_a, TypedGene) or not isinstance(self.gene_b, TypedGene):
            raise SourceEvolutionError("CompositeGene requires two TypedGene instances")
        if self.operator not in ("ADD", "SUB", "XOR", "MULT"):
            raise SourceEvolutionError(f"Unsupported composite operator: {self.operator}")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_composite": True,
            "gene_a": self.gene_a.to_dict(),
            "gene_b": self.gene_b.to_dict(),
            "operator": self.operator,
        }


@dataclass(frozen=True)
class GatedGene:
    """Strongly-typed gated modular gene: conditional length guard and modular congruence."""
    min_length: int = 4
    stride_weight: int = 1
    density_weight: int = 1
    modulus: int = 3
    target_residue: int = 0
    true_val: int = 0
    false_val: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_gated": True,
            "min_length": self.min_length,
            "stride_weight": self.stride_weight,
            "density_weight": self.density_weight,
            "modulus": self.modulus,
            "target_residue": self.target_residue,
            "true_val": self.true_val,
            "false_val": self.false_val,
        }


@dataclass(frozen=True)
class RelationalGene:
    """Strongly-typed relational multi-clause gene for non-linear pattern invariants."""
    ordinal: int = 1
    min_length: int = 4
    stride_weight: int = 2
    density_weight: int = -1
    modulus: int = 0
    op: str = "EQ_ZERO"
    true_val: int = 0
    false_val: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_relational": True,
            "ordinal": self.ordinal,
            "min_length": self.min_length,
            "stride_weight": self.stride_weight,
            "density_weight": self.density_weight,
            "modulus": self.modulus,
            "op": self.op,
            "true_val": self.true_val,
            "false_val": self.false_val,
        }


@dataclass(frozen=True)
class RelationalGatedGene:
    """Strongly-typed multi-clause relational gated gene for expressive non-linear invariants.

    Expresses multi-clause conjunctions or disjunctions across:
    1. Length guard (e.g. length >= length_threshold)
    2. Modular congruence (e.g. ((stride_val * stride_w + density * density_w) % mod) == target_residue)
    3. Relational boundary condition (e.g. boundary_var boundary_op boundary_threshold, such as density <= 4)

    Provides clear distinction between:
    - Parametric coefficient tuning (modifying numeric weights, thresholds, moduli)
    - Structural algorithmic innovation (changing logical combiners AND<->OR, relational operators, or clause topology)
    """
    length_op: str = ">="              # ">=", "<=", "==", "!=", ">", "<"
    length_threshold: int = 4          # 0 to 128
    stride_weight: int = 1             # -16 to 16
    density_weight: int = 1            # -16 to 16
    length_weight: int = 0             # -16 to 16
    modulus: int = 3                   # 2 to 31
    target_residue: int = 0            # 0 to 30
    congruence_op: str = "=="          # "==", "!="
    boundary_var: str = "density"      # "density", "stride_val", "length"
    boundary_op: str = "<="            # "<=", ">=", "==", "!=", "<", ">"
    boundary_threshold: int = 4        # 0 to 128
    combiner: str = "AND"              # "AND" (conjunction) or "OR" (disjunction)
    clause_type: str = "CONJUNCTION_AND" # Structural clause classification tag
    true_val: int = 0
    false_val: int = 1

    def __post_init__(self):
        _check_int(self.length_threshold, 0, 128, "length_threshold")
        _check_int(self.stride_weight, -16, 16, "stride_weight")
        _check_int(self.density_weight, -16, 16, "density_weight")
        _check_int(self.length_weight, -16, 16, "length_weight")
        _check_int(self.modulus, 2, 31, "modulus")
        _check_int(self.target_residue, 0, 30, "target_residue")
        _check_int(self.boundary_threshold, 0, 128, "boundary_threshold")
        _check_int(self.true_val, -100, 100, "true_val")
        _check_int(self.false_val, -100, 100, "false_val")

        valid_rel_ops = (">=", "<=", "==", "!=", ">", "<")
        if self.length_op not in valid_rel_ops:
            raise SourceEvolutionError(f"Invalid length_op: {self.length_op}")
        if self.boundary_op not in valid_rel_ops:
            raise SourceEvolutionError(f"Invalid boundary_op: {self.boundary_op}")
        if self.congruence_op not in ("==", "!="):
            raise SourceEvolutionError(f"Invalid congruence_op: {self.congruence_op}")
        if self.boundary_var not in ("density", "stride_val", "length"):
            raise SourceEvolutionError(f"Invalid boundary_var: {self.boundary_var}")
        if self.combiner.upper() not in ("AND", "OR"):
            raise SourceEvolutionError(f"Invalid combiner: {self.combiner}, must be 'AND' or 'OR'")

    def structural_signature(self) -> Tuple[str, str, str, str, str, str]:
        """Return structural topology signature for algorithmic innovation checks."""
        return (
            self.clause_type,
            self.combiner.upper(),
            self.length_op,
            self.congruence_op,
            self.boundary_var,
            self.boundary_op,
        )

    def coefficient_profile(self) -> Tuple[int, int, int, int, int, int, int, int, int]:
        """Return numeric coefficient vector for parameter tuning checks."""
        return (
            self.length_threshold,
            self.stride_weight,
            self.density_weight,
            self.length_weight,
            self.modulus,
            self.target_residue,
            self.boundary_threshold,
            self.true_val,
            self.false_val,
        )

    def is_structural_innovation(self, other: Any) -> bool:
        """True if other represents structural/topological change rather than coefficient tuning."""
        if not isinstance(other, RelationalGatedGene):
            return True
        return self.structural_signature() != other.structural_signature()

    def is_coefficient_tuning(self, other: Any) -> bool:
        """True if other shares structural topology and only modifies numeric parameters."""
        if not isinstance(other, RelationalGatedGene):
            return False
        return (self.structural_signature() == other.structural_signature()) and (
            self.coefficient_profile() != other.coefficient_profile()
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_relational": True,
            "is_relational_gated": True,
            "clause_type": self.clause_type,
            "combiner": self.combiner.upper(),
            "length_op": self.length_op,
            "length_threshold": self.length_threshold,
            "stride_weight": self.stride_weight,
            "density_weight": self.density_weight,
            "length_weight": self.length_weight,
            "modulus": self.modulus,
            "target_residue": self.target_residue,
            "congruence_op": self.congruence_op,
            "boundary_var": self.boundary_var,
            "boundary_op": self.boundary_op,
            "boundary_threshold": self.boundary_threshold,
            "true_val": self.true_val,
            "false_val": self.false_val,
        }


@dataclass(frozen=True)
class DispatchGene:
    """Strongly-typed multi-task dispatch gene: routes to specialized mechanism branches."""
    ordinal: int = 1
    split_len: int = 5
    mod_a: int = 2
    mod_b: int = 3
    stride_scale: int = 1
    true_val: int = 0
    false_val: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_dispatch": True,
            "ordinal": self.ordinal,
            "split_len": self.split_len,
            "mod_a": self.mod_a,
            "mod_b": self.mod_b,
            "stride_scale": self.stride_scale,
            "true_val": self.true_val,
            "false_val": self.false_val,
        }


SEED_GENE = TypedGene(
    window_stride=2,
    modulus=3,
    parity_threshold=1,
    weight_length=1,
    weight_density=2,
    sign=1,
)

MUTATION_RULES: Tuple[Tuple[str, int], ...] = (
    ("window_stride", 1),
    ("window_stride", 3),
    ("window_stride", 4),
    ("modulus", 2),
    ("modulus", 5),
    ("modulus", 7),
    ("parity_threshold", 0),
    ("parity_threshold", 2),
    ("parity_threshold", 3),
    ("weight_length", 2),
    ("weight_length", -2),
    ("weight_density", 3),
    ("weight_density", -1),
    ("weight_density", 5),
    ("sign", -1),
    ("sign", 1),
)

COMPOSITE_OPERATORS: Tuple[str, ...] = ("ADD", "XOR", "SUB", "MULT")

GATED_MUTATIONS: Tuple[Tuple[int, int, int, int], ...] = (
    # (min_length, stride_weight, density_weight, modulus)
    (4, 1, 1, 3),   # Ordinal 1: (stride + density) % 3 == 0, min_len >= 4
    (3, 1, 0, 2),   # Ordinal 2: stride % 2 == 0, min_len >= 3
    (4, 2, -1, 3),  # Ordinal 3: (2*stride - density) % 3 == 0, min_len >= 4
    (3, 1, -1, 2),  # Ordinal 4: (stride - density) % 2 == 0, min_len >= 3
    (3, 0, 1, 2),   # Ordinal 5: density % 2 == 0, min_len >= 3 (task_j2 parity)
    (3, 2, 0, 3),   # Ordinal 6: (stride * 2) % 3 == 0, min_len >= 3
    (4, 1, 2, 3),   # Ordinal 7: (stride + 2*density) % 3 == 0, min_len >= 4
    (3, 1, 1, 2),   # Ordinal 8: (stride + density) % 2 == 0, min_len >= 3
    (4, 2, 1, 3),   # Ordinal 9: (2*stride + density) % 3 == 0, min_len >= 4
    (3, 2, -2, 3),  # Ordinal 10: (2*stride - 2*density) % 3 == 0, min_len >= 3
)


def gene_from_dict(d: Dict[str, Any]) -> Union[TypedGene, CompositeGene, GatedGene, RelationalGene, DispatchGene]:
    """Reconstruct TypedGene, CompositeGene, GatedGene, RelationalGene, or DispatchGene from dict representation."""
    if d.get("is_dispatch", False):
        return DispatchGene(
            ordinal=d.get("ordinal", 1),
            split_len=d.get("split_len", 5),
            mod_a=d.get("mod_a", 2),
            mod_b=d.get("mod_b", 3),
            stride_scale=d.get("stride_scale", 1),
            true_val=d.get("true_val", 0),
            false_val=d.get("false_val", 1),
        )
    if d.get("is_relational", False):
        return RelationalGene(
            ordinal=d.get("ordinal", 1),
            min_length=d.get("min_length", 4),
            stride_weight=d.get("stride_weight", 2),
            density_weight=d.get("density_weight", -1),
            modulus=d.get("modulus", 0),
            op=d.get("op", "EQ_ZERO"),
            true_val=d.get("true_val", 0),
            false_val=d.get("false_val", 1),
        )
    if d.get("is_gated", False):
        return GatedGene(
            min_length=d.get("min_length", 4),
            stride_weight=d.get("stride_weight", 1),
            density_weight=d.get("density_weight", 1),
            modulus=d.get("modulus", 3),
            target_residue=d.get("target_residue", 0),
            true_val=d.get("true_val", 0),
            false_val=d.get("false_val", 1),
        )
    if d.get("is_composite", False):
        return CompositeGene(
            gene_a=gene_from_dict(d["gene_a"]),
            gene_b=gene_from_dict(d["gene_b"]),
            operator=d.get("operator", "XOR"),
        )
    return TypedGene(
        window_stride=d.get("window_stride", 2),
        modulus=d.get("modulus", 3),
        parity_threshold=d.get("parity_threshold", 1),
        weight_length=d.get("weight_length", 1),
        weight_density=d.get("weight_density", 2),
        sign=d.get("sign", 1),
    )


def mutate_gene(parent: TypedGene, ordinal: int) -> TypedGene:
    """Deterministically mutate a parent gene based on an ordinal index."""
    _check_int(ordinal, 0, 100000, "ordinal")
    field, val = MUTATION_RULES[ordinal % len(MUTATION_RULES)]
    params = dict(parent.to_dict())
    params.pop("is_composite", None)
    params[field] = val
    if params == {k: v for k, v in parent.to_dict().items() if k != "is_composite"}:
        new_w = parent.weight_density + 1 if parent.weight_density < 8 else -8
        params["weight_density"] = new_w
    return TypedGene(**params)


def mutate_composite_gene(
    parent_a: TypedGene,
    parent_b: TypedGene,
    ordinal: int,
) -> CompositeGene:
    """Deterministically mutate and synthesize a composite gene."""
    _check_int(ordinal, 0, 100000, "ordinal")
    mutated_a = mutate_gene(parent_a, ordinal)
    mutated_b = mutate_gene(parent_b, ordinal + 3)
    op = COMPOSITE_OPERATORS[ordinal % len(COMPOSITE_OPERATORS)]
    return CompositeGene(gene_a=mutated_a, gene_b=mutated_b, operator=op)


def mutate_gated_gene(ordinal: int) -> GatedGene:
    """Deterministically synthesize a gated modular gene."""
    _check_int(ordinal, 0, 100000, "ordinal")
    rule = GATED_MUTATIONS[(ordinal - 1) % len(GATED_MUTATIONS)]
    return GatedGene(
        min_length=rule[0],
        stride_weight=rule[1],
        density_weight=rule[2],
        modulus=rule[3],
        target_residue=0,
        true_val=0,
        false_val=1,
    )


RELATIONAL_GENE_RULES: Tuple[Tuple[int, int, int, int, str], ...] = (
    (4, 2, -1, 0, "EQ_ZERO"),
    (3, 1, -1, 0, "EQ_ZERO"),
    (4, 1, 1, 2, "MOD_EQ"),
    (3, 2, 0, 3, "MOD_EQ"),
    (4, 1, -1, 3, "MOD_EQ"),
    (5, 3, -1, 2, "MOD_EQ"),
    (4, 2, 1, 3, "MOD_EQ"),
    (3, 0, 1, 2, "MOD_EQ"),
    (4, 1, 2, 3, "MOD_EQ"),
    (3, 2, -2, 3, "MOD_EQ"),
    (4, 1, 0, 2, "MOD_EQ"),
    (5, 1, -1, 2, "MOD_EQ"),
)

DISPATCH_GENE_RULES: Tuple[Tuple[int, int, int, int], ...] = (
    (5, 2, 3, 1),
    (6, 3, 2, 2),
    (4, 2, 2, 1),
    (5, 3, 3, 2),
    (4, 2, 3, 1),
    (6, 2, 3, 2),
    (5, 3, 2, 1),
    (4, 2, 2, 2),
)


def mutate_relational_gene(ordinal: int) -> RelationalGene:
    """Deterministically synthesize a relational multi-clause gene."""
    _check_int(ordinal, 0, 100000, "ordinal")
    rule = RELATIONAL_GENE_RULES[(ordinal - 1) % len(RELATIONAL_GENE_RULES)]
    return RelationalGene(
        ordinal=ordinal,
        min_length=rule[0],
        stride_weight=rule[1],
        density_weight=rule[2],
        modulus=rule[3],
        op=rule[4],
        true_val=0,
        false_val=1,
    )


def mutate_dispatch_gene(ordinal: int) -> DispatchGene:
    """Deterministically synthesize a multi-task dispatch gene."""
    _check_int(ordinal, 0, 100000, "ordinal")
    rule = DISPATCH_GENE_RULES[(ordinal - 1) % len(DISPATCH_GENE_RULES)]
    return DispatchGene(
        ordinal=ordinal,
        split_len=rule[0],
        mod_a=rule[1],
        mod_b=rule[2],
        stride_scale=rule[3],
        true_val=0,
        false_val=1,
    )


def _render_atomic_expr(g: TypedGene) -> str:
    return (
        f"{g.sign} * ("
        f"length * {g.weight_length} + "
        f"density * {g.weight_density} + "
        f"(stride_val % {g.modulus}) - "
        f"{g.parity_threshold})"
    )


def generate_source(
    gene: Union[TypedGene, CompositeGene, GatedGene, RelationalGene, DispatchGene],
    function_name: str = "evaluate_mechanism",
) -> bytes:
    """Generate typed, bounded Python source code from a validated Gene."""
    if isinstance(gene, DispatchGene):
        branch_true = f"(0 if ((density % {gene.mod_a}) == 0) else 1)"
        branch_false = f"(0 if (((stride_val * {gene.stride_scale}) % {gene.mod_b}) == 0) else 1)"
        code_text = (
            f"def {function_name}(length: int, density: int, stride_val: int) -> int:\n"
            f"    return {branch_true} if (length >= {gene.split_len}) else {branch_false}\n"
        )
        return code_text.encode("utf-8")

    if isinstance(gene, RelationalGene):
        if gene.op == "EQ_ZERO":
            if gene.density_weight < 0:
                inner_expr = f"((stride_val * {gene.stride_weight}) - (density * {abs(gene.density_weight)}))"
            else:
                inner_expr = f"((stride_val * {gene.stride_weight}) + (density * {gene.density_weight}))"
            cond_expr = f"((length >= {gene.min_length}) and ({inner_expr} == 0))"
        else:
            if gene.density_weight < 0:
                inner_expr = f"((stride_val * {gene.stride_weight}) - (density * {abs(gene.density_weight)}))"
            elif gene.density_weight == 0:
                inner_expr = f"(stride_val * {gene.stride_weight})"
            elif gene.stride_weight == 0:
                inner_expr = f"(density * {gene.density_weight})"
            else:
                inner_expr = f"((stride_val * {gene.stride_weight}) + (density * {gene.density_weight}))"
            cond_expr = f"((length >= {gene.min_length}) and (({inner_expr} % {gene.modulus}) == 0))"

        code_text = (
            f"def {function_name}(length: int, density: int, stride_val: int) -> int:\n"
            f"    return {gene.true_val} if {cond_expr} else {gene.false_val}\n"
        )
        return code_text.encode("utf-8")

    if isinstance(gene, GatedGene):
        code_text = (
            f"def {function_name}(length: int, density: int, stride_val: int) -> int:\n"
            f"    return {gene.true_val} if ((length >= {gene.min_length}) and "
            f"(((stride_val * {gene.stride_weight} + density * {gene.density_weight}) % {gene.modulus}) == {gene.target_residue})) "
            f"else {gene.false_val}\n"
        )
        return code_text.encode("utf-8")

    if isinstance(gene, CompositeGene):
        expr_a = _render_atomic_expr(gene.gene_a)
        expr_b = _render_atomic_expr(gene.gene_b)
        if gene.operator == "XOR":
            op_sym = "^"
        elif gene.operator == "MULT":
            op_sym = "*"
        elif gene.operator == "SUB":
            op_sym = "-"
        else:
            op_sym = "+"

        code_text = (
            f"def {function_name}(length: int, density: int, stride_val: int) -> int:\n"
            f"    return ({expr_a}) {op_sym} ({expr_b})\n"
        )
        return code_text.encode("utf-8")

    if isinstance(gene, TypedGene):
        expr = _render_atomic_expr(gene)
        code_text = (
            f"def {function_name}(length: int, density: int, stride_val: int) -> int:\n"
            f"    return {expr}\n"
        )
        return code_text.encode("utf-8")

    raise SourceEvolutionError("TypedGene, CompositeGene, GatedGene, RelationalGene, or DispatchGene required")


ALLOWED_AST_NODES = (
    ast.Module,
    ast.FunctionDef,
    ast.arguments,
    ast.arg,
    ast.Return,
    ast.BinOp,
    ast.UnaryOp,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Mod,
    ast.BitXor,
    ast.USub,
    ast.UAdd,
    ast.IfExp,
    ast.Compare,
    ast.Eq,
    ast.NotEq,
    ast.GtE,
    ast.LtE,
    ast.Gt,
    ast.Lt,
    ast.BoolOp,
    ast.And,
    ast.Or,
    ast.Not,
    ast.Name,
    ast.Constant,
    ast.Load,
)


def validate_ast(source_bytes: bytes, expected_name: str = "evaluate_mechanism") -> ast.FunctionDef:
    """Verify that source code strictly adheres to security boundaries."""
    try:
        tree = ast.parse(source_bytes)
    except SyntaxError as e:
        raise SourceEvolutionError(f"Syntax error in generated source: {e}") from e

    if len(tree.body) != 1 or not isinstance(tree.body[0], ast.FunctionDef):
        raise SourceEvolutionError("Source must contain exactly one top-level function definition")

    func_def = tree.body[0]
    if func_def.name != expected_name:
        raise SourceEvolutionError(f"Function name must be '{expected_name}', got '{func_def.name}'")

    for node in ast.walk(tree):
        if not isinstance(node, ALLOWED_AST_NODES):
            raise SourceEvolutionError(f"Forbidden AST node type: {type(node).__name__}")
        if isinstance(node, ast.Name):
            # Only allowed parameter names or type annotations
            if node.id not in ("length", "density", "stride_val", "int"):
                raise SourceEvolutionError(f"Forbidden variable access: {node.id}")

    return func_def


def compile_function(
    source_bytes: bytes,
    gene: Optional[Union[TypedGene, CompositeGene, Dict[str, Any]]] = None,
) -> Callable[[int, int, int], int]:
    """Safely compile verified source bytes into an isolated callable."""
    validate_ast(source_bytes)
    source_str = source_bytes.decode("utf-8")
    env: Dict[str, Any] = {"__builtins__": {}}
    code_obj = compile(source_str, "<ace_source_mutation>", "exec")
    exec(code_obj, env)
    fn = env.get("evaluate_mechanism")
    if not callable(fn):
        raise SourceEvolutionError("Compiled object did not define callable 'evaluate_mechanism'")
    return fn
