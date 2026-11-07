"""Compositional Mechanism Grammar (G_mech) for ACE F14.

Defines an expressive space of candidate structural extractors over string sequences:
- Slicing, striding, prefix/suffix half-splitting
- Symbol counting and length operations
- Dyck bracket balance, prefix non-negativity, and depth bounds
- Modular congruence and relational equality predicates
- Boolean combinators (AND, OR, NOT)

Every AST node produces compilable, safe Python code and evaluates deterministically.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
import hashlib
from typing import Any, Callable, Dict, List, Optional, Tuple


class ASTNode(ABC):
    """Abstract base class for all mechanism grammar AST expressions."""

    @abstractmethod
    def evaluate(self, w: str) -> Any:
        """Evaluate node on input string."""
        pass

    @abstractmethod
    def to_code(self) -> str:
        """Emit pure Python code expression."""
        pass

    @abstractmethod
    def complexity(self) -> int:
        """Structural complexity weight."""
        pass

    @abstractmethod
    def signature(self) -> str:
        """Deterministic canonical signature."""
        pass

    def __hash__(self) -> int:
        return hash(self.signature())

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, ASTNode) and self.signature() == other.signature()


# 1. String-level expressions
class InputString(ASTNode):
    def evaluate(self, w: str) -> str:
        return w

    def to_code(self) -> str:
        return "w"

    def complexity(self) -> int:
        return 1

    def signature(self) -> str:
        return "InputString()"


@dataclass(frozen=True)
class SliceOp(ASTNode):
    src: ASTNode
    offset: int
    stride: int

    def evaluate(self, w: str) -> str:
        s = str(self.src.evaluate(w))
        return s[self.offset :: self.stride]

    def to_code(self) -> str:
        return f"{self.src.to_code()}[{self.offset}::{self.stride}]"

    def complexity(self) -> int:
        return self.src.complexity() + 2

    def signature(self) -> str:
        return f"SliceOp({self.src.signature()},{self.offset},{self.stride})"


@dataclass(frozen=True)
class HalfSplitOp(ASTNode):
    src: ASTNode
    half: str  # "left" or "right"

    def evaluate(self, w: str) -> str:
        s = str(self.src.evaluate(w))
        mid = len(s) // 2
        return s[:mid] if self.half == "left" else s[mid:]

    def to_code(self) -> str:
        if self.half == "left":
            return f"{self.src.to_code()}[:len({self.src.to_code()}) // 2]"
        return f"{self.src.to_code()}[len({self.src.to_code()}) // 2:]"

    def complexity(self) -> int:
        return self.src.complexity() + 2

    def signature(self) -> str:
        return f"HalfSplitOp({self.src.signature()},{self.half})"


# 2. Integer-level expressions
@dataclass(frozen=True)
class CountOp(ASTNode):
    src: ASTNode
    char: str

    def evaluate(self, w: str) -> int:
        s = str(self.src.evaluate(w))
        return s.count(self.char)

    def to_code(self) -> str:
        return f"{self.src.to_code()}.count('{self.char}')"

    def complexity(self) -> int:
        return self.src.complexity() + 1

    def signature(self) -> str:
        return f"CountOp({self.src.signature()},{self.char})"


@dataclass(frozen=True)
class LengthOp(ASTNode):
    src: ASTNode

    def evaluate(self, w: str) -> int:
        return len(str(self.src.evaluate(w)))

    def to_code(self) -> str:
        return f"len({self.src.to_code()})"

    def complexity(self) -> int:
        return self.src.complexity() + 1

    def signature(self) -> str:
        return f"LengthOp({self.src.signature()})"


# 3. Dyck / Context-Free bracket expressions
@dataclass(frozen=True)
class DyckBalanceOp(ASTNode):
    """Evaluates prefix non-negativity and total balance for 'a' (open) and 'b' (close)."""
    src: ASTNode
    max_depth: int = 100

    def evaluate(self, w: str) -> bool:
        s = str(self.src.evaluate(w))
        depth = 0
        for ch in s:
            depth += 1 if ch == "a" else -1
            if depth < 0 or depth > self.max_depth:
                return False
        return depth == 0

    def to_code(self) -> str:
        return (
            f"(lambda s: all(c in 'ab' for c in s) and "
            f"all(sum(1 if c == 'a' else -1 for c in s[:i]) >= 0 and "
            f"sum(1 if c == 'a' else -1 for c in s[:i]) <= {self.max_depth} for i in range(len(s) + 1)) and "
            f"sum(1 if c == 'a' else -1 for c in s) == 0)({self.src.to_code()})"
        )


    def complexity(self) -> int:
        return self.src.complexity() + 4

    def signature(self) -> str:
        return f"DyckBalanceOp({self.src.signature()},{self.max_depth})"


# 4. Predicate (Boolean) expressions
@dataclass(frozen=True)
class ModEqPred(ASTNode):
    src: ASTNode  # Integer expression
    mod: int
    target: int

    def evaluate(self, w: str) -> bool:
        val = int(self.src.evaluate(w))
        return (val % self.mod) == self.target

    def to_code(self) -> str:
        return f"({self.src.to_code()} % {self.mod} == {self.target})"

    def complexity(self) -> int:
        return self.src.complexity() + 2

    def signature(self) -> str:
        return f"ModEqPred({self.src.signature()},{self.mod},{self.target})"


@dataclass(frozen=True)
class RelationalEqPred(ASTNode):
    left: ASTNode
    right: ASTNode
    mod: int = 1

    def evaluate(self, w: str) -> bool:
        l_val = self.left.evaluate(w)
        r_val = self.right.evaluate(w)
        if self.mod > 1:
            return (int(l_val) % self.mod) == (int(r_val) % self.mod)
        return l_val == r_val

    def to_code(self) -> str:
        if self.mod > 1:
            return f"(({self.left.to_code()} % {self.mod}) == ({self.right.to_code()} % {self.mod}))"
        return f"({self.left.to_code()} == {self.right.to_code()})"

    def complexity(self) -> int:
        return self.left.complexity() + self.right.complexity() + 1


    def signature(self) -> str:
        return f"RelationalEqPred({self.left.signature()},{self.right.signature()},{self.mod})"



@dataclass(frozen=True)
class AndPred(ASTNode):
    p1: ASTNode
    p2: ASTNode

    def evaluate(self, w: str) -> bool:
        return bool(self.p1.evaluate(w)) and bool(self.p2.evaluate(w))

    def to_code(self) -> str:
        return f"({self.p1.to_code()} and {self.p2.to_code()})"

    def complexity(self) -> int:
        return self.p1.complexity() + self.p2.complexity() + 1

    def signature(self) -> str:
        return f"AndPred({self.p1.signature()},{self.p2.signature()})"


@dataclass(frozen=True)
class OrPred(ASTNode):
    p1: ASTNode
    p2: ASTNode

    def evaluate(self, w: str) -> bool:
        return bool(self.p1.evaluate(w)) or bool(self.p2.evaluate(w))

    def to_code(self) -> str:
        return f"({self.p1.to_code()} or {self.p2.to_code()})"

    def complexity(self) -> int:
        return self.p1.complexity() + self.p2.complexity() + 1

    def signature(self) -> str:
        return f"OrPred({self.p1.signature()},{self.p2.signature()})"


@dataclass(frozen=True)
class NotPred(ASTNode):
    p: ASTNode

    def evaluate(self, w: str) -> bool:
        return not bool(self.p.evaluate(w))

    def to_code(self) -> str:
        return f"(not {self.p.to_code()})"

    def complexity(self) -> int:
        return self.p.complexity() + 1

    def signature(self) -> str:
        return f"NotPred({self.p.signature()})"


def compile_ast_to_callable(node: ASTNode) -> Tuple[Callable[[str], bool], str]:
    """Compile AST node into a standalone Python callable and source code string."""
    code_expr = node.to_code()
    source_code = f"def candidate_fn(w: str) -> bool:\n    return bool({code_expr})\n"
    local_env: Dict[str, Any] = {}
    exec(source_code, {"__builtins__": {"all": all, "any": any, "len": len, "range": range, "sum": sum, "next": next, "int": int, "bool": bool, "str": str}}, local_env)
    return local_env["candidate_fn"], source_code
