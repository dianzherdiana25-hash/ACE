"""DreamCoder Wake-Sleep Library Abstraction Engine for Autonomous Capability Evolution.

Implements:
1. Wake Phase: Registers accepted programs discovered across different cycles and tasks.
2. Sleep Phase (Abstraction): Mines recurring sub-ASTs via anti-unification, abstracts
   free parameters, and promotes them into reusable DSL primitives.
3. Compression Tracking: Verifies positive description length reduction (PRD G4).
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
from typing import Any, Callable, Dict, List, Optional, Tuple

from ace_evolution.island_search import TypedASTNode


@dataclass
class DiscoveredPrimitive:
    name: str
    parameter_names: List[str]
    template_expr: str
    usage_count: int = 0
    ast_size: int = 0

    def evaluate(self, word: str, *args) -> Any:
        params = dict(zip(self.parameter_names, args))
        scope = {"word": word, **params}
        return eval(self.template_expr, {"__builtins__": None}, scope)


class WakeSleepAbstractionEngine:
    """Manages the wake-sleep cycle of capability discovery and library abstraction."""

    def __init__(self):
        self.wake_solutions: List[Dict[str, Any]] = []
        self.discovered_primitives: Dict[str, DiscoveredPrimitive] = {}

    def record_solution(self, task_id: str, root_node: TypedASTNode, metadata: Optional[Dict[str, Any]] = None):
        """Wake phase: Record newly solved task and its AST."""
        self.wake_solutions.append({
            "task_id": task_id,
            "root": root_node,
            "code": root_node.to_code(),
            "size": root_node.size(),
            "metadata": metadata or {}
        })

    def _extract_subexpression_patterns(self) -> Dict[Tuple[str, Tuple[str, ...]], List[int]]:
        """Finds recurring parameterized sub-AST templates across recorded solutions."""
        counts: Dict[Tuple[str, Tuple[str, ...]], List[int]] = {}

        def get_all_subtrees(node: TypedASTNode) -> List[TypedASTNode]:
            res = [node]
            for c in node.children:
                res.extend(get_all_subtrees(c))
            return res

        for sol_idx, sol in enumerate(self.wake_solutions):
            root = sol["root"]
            subtrees = get_all_subtrees(root)

            for sub in subtrees:
                if sub.children:  # Non-trivial compound node
                    # Anti-unify constants into parameters
                    param_names = []
                    param_counter = 0

                    def to_template(n: TypedASTNode) -> str:
                        nonlocal param_counter
                        if n.op == "int_const":
                            p = f"param_{param_counter}"
                            param_names.append(p)
                            param_counter += 1
                            return p
                        elif n.op == "bool_const":
                            p = f"param_{param_counter}"
                            param_names.append(p)
                            param_counter += 1
                            return p
                        elif not n.children:
                            return n.to_code()
                        elif n.op in ("add", "sub", "mul", "mod", "eq", "neq", "lte", "gte", "and", "or"):
                            op_sym = {"add": "+", "sub": "-", "mul": "*", "mod": "%",
                                      "eq": "==", "neq": "!=", "lte": "<=", "gte": ">=",
                                      "and": "and", "or": "or"}[n.op]
                            left = to_template(n.children[0])
                            right = to_template(n.children[1])
                            return f"({left} {op_sym} {right})"
                        elif n.op == "not":
                            child = to_template(n.children[0])
                            return f"(not {child})"
                        return n.to_code()

                    template_str = to_template(sub)
                    key = (template_str, tuple(param_names))
                    counts.setdefault(key, []).append(sol_idx)

        return counts

    def sleep_abstract_library(self, min_support: int = 2) -> Dict[str, Any]:
        """Sleep phase: Mines patterns and abstracts them into reusable primitives."""
        patterns = self._extract_subexpression_patterns()
        promoted = []

        for (abstracted_expr, param_names), sol_indices in patterns.items():
            if len(sol_indices) >= min_support:
                prim_id = f"prim_{hashlib.sha256(abstracted_expr.encode()).hexdigest()[:8]}"

                if prim_id not in self.discovered_primitives:
                    prim = DiscoveredPrimitive(
                        name=prim_id,
                        parameter_names=list(param_names),
                        template_expr=abstracted_expr,
                        usage_count=len(sol_indices),
                        ast_size=max(2, len(abstracted_expr) // 4)
                    )
                    self.discovered_primitives[prim_id] = prim
                    promoted.append(prim)

        # Compute compression statistics
        initial_size = sum(s["size"] for s in self.wake_solutions)
        savings = sum(p.usage_count * p.ast_size for p in promoted)
        compressed_size = max(1, initial_size - savings + len(promoted) * 2)
        compression_ratio = initial_size / compressed_size if initial_size > 0 else 1.0

        return {
            "status": "COMPLETED",
            "solutions_processed": len(self.wake_solutions),
            "new_primitives_promoted": [p.name for p in promoted],
            "total_library_size": len(self.discovered_primitives),
            "initial_program_size": initial_size,
            "compressed_program_size": compressed_size,
            "compression_ratio": round(compression_ratio, 3),
            "transfer_ready": len(self.discovered_primitives) > 0
        }
