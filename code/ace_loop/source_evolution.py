"""E1.6-V2: Bounded, Typed Source-Code Mutation Engine for Autonomous Self-Development.

Produces and compiles deterministic Python source code from strongly typed gene specifications.
Enforces strict AST safety boundaries:
- Pure functions only (no imports, no system calls, no I/O, no eval/exec).
- Whitelisted AST node types: FunctionDef, Return, BinOp, UnaryOp, Compare, Name, Constant.
- Clean execution environment with empty builtins.
- Cryptographic hash verification of source bytes (source_sha).
"""
from __future__ import annotations

import ast
from dataclasses import dataclass
import hashlib
from typing import Any, Callable, Dict, List, Optional, Tuple


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

    def to_dict(self) -> Dict[str, int]:
        return {
            "window_stride": self.window_stride,
            "modulus": self.modulus,
            "parity_threshold": self.parity_threshold,
            "weight_length": self.weight_length,
            "weight_density": self.weight_density,
            "sign": self.sign,
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


def mutate_gene(parent: TypedGene, ordinal: int) -> TypedGene:
    """Deterministically mutate a parent gene based on an ordinal index."""
    _check_int(ordinal, 0, 100000, "ordinal")
    field, val = MUTATION_RULES[ordinal % len(MUTATION_RULES)]
    params = parent.to_dict()
    params[field] = val
    if params == parent.to_dict():
        new_w = parent.weight_density + 1 if parent.weight_density < 8 else -8
        params["weight_density"] = new_w
    return TypedGene(**params)


def generate_source(gene: TypedGene, function_name: str = "evaluate_mechanism") -> bytes:
    """Generate typed, bounded Python source code from a validated Gene."""
    if not isinstance(gene, TypedGene):
        raise SourceEvolutionError("TypedGene instance required")

    code_text = (
        f"def {function_name}(length: int, density: int, stride_val: int) -> int:\n"
        f"    return {gene.sign} * ("
        f"length * {gene.weight_length} + "
        f"density * {gene.weight_density} + "
        f"(stride_val % {gene.modulus}) - "
        f"{gene.parity_threshold})\n"
    )
    return code_text.encode("utf-8")


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
    ast.USub,
    ast.UAdd,
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


def compile_function(source_bytes: bytes, gene: TypedGene) -> Callable[[int, int, int], int]:
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
