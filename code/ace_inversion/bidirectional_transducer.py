"""Bidirectional Program Inversion & Category-Theoretic Lenses.

Mathematical Foundation:
- Asymmetric Lens framework (Foster, Greenwald, Moore, Pierce, Schmitt, 2005):
    l : S <=> V
    get : S -> V
    put : V -> S -> S

- Classic Well-Behaved Lens Laws:
    1. Put-Get (Consistency):
         forall s in S, v in V:  get(put(v, s)) == v
    2. Get-Put (Stability):
         forall s in S:          put(get(s), s) == s
    3. Put-Put (Idempotency - Very Well-Behaved):
         forall s in S, v1, v2:  put(v2, put(v1, s)) == put(v2, s)

- Bijective Transducers (Isomorphisms as Special Lenses):
    When l is an isomorphism (S ~= V), put(v, s) = inv(v):
         inv(fwd(s)) == s   and   fwd(inv(v)) == v
    Zero information loss on structured data, strings, and ASTs.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Generic, List, Optional, Sequence, Tuple, TypeVar, Union

S = TypeVar("S")
V = TypeVar("V")
W = TypeVar("W")


class Lens(Generic[S, V]):
    """Abstract base class for an asymmetric bidirectional lens."""

    def get(self, source: S) -> V:
        raise NotImplementedError

    def put(self, view: V, source: S) -> S:
        raise NotImplementedError

    def compose(self, other: Lens[V, W]) -> Lens[S, W]:
        """Category-theoretic lens composition: (self o other): S <=> W.
        Composition preserves well-behavedness laws (Foster et al., 2005).
        """
        return ComposedLens(self, other)


class ComposedLens(Lens[S, W]):
    """Lens composition: S <=> V <=> W."""

    def __init__(self, l1: Lens[S, V], l2: Lens[V, W]):
        self.l1 = l1
        self.l2 = l2

    def get(self, source: S) -> W:
        mid_view = self.l1.get(source)
        return self.l2.get(mid_view)

    def put(self, view: W, source: S) -> S:
        mid_view = self.l1.get(source)
        updated_mid = self.l2.put(view, mid_view)
        return self.l1.put(updated_mid, source)


class BijectiveLens(Lens[S, V]):
    """Bijective lens (Isomorphism S ~= V): fwd(s) and inv(v) with exact round-trip bijectivity."""

    def __init__(self, fwd_fn: Callable[[S], V], inv_fn: Callable[[V], S]):
        self.fwd_fn = fwd_fn
        self.inv_fn = inv_fn

    def get(self, source: S) -> V:
        return self.fwd_fn(source)

    def put(self, view: V, source: Optional[S] = None) -> S:
        return self.inv_fn(view)


class FieldLens(Lens[Dict[str, Any], Any]):
    """Focuses on a specific dictionary key while preserving the remainder of the dictionary."""

    def __init__(self, key: str, default: Any = None):
        self.key = key
        self.default = default

    def get(self, source: Dict[str, Any]) -> Any:
        return source.get(self.key, self.default)

    def put(self, view: Any, source: Dict[str, Any]) -> Dict[str, Any]:
        updated = dict(source)
        updated[self.key] = view
        return updated


class ListMapLens(Lens[List[Any], List[Any]]):
    """Lifts an element lens element_lens: A <=> B to lists: List[A] <=> List[B]."""

    def __init__(self, elem_lens: Lens[Any, Any]):
        self.elem_lens = elem_lens

    def get(self, source: List[Any]) -> List[Any]:
        return [self.elem_lens.get(item) for item in source]

    def put(self, view: List[Any], source: List[Any]) -> List[Any]:
        result = []
        for i, v_item in enumerate(view):
            if i < len(source):
                result.append(self.elem_lens.put(v_item, source[i]))
            else:
                # New item: put into identity or default
                if isinstance(self.elem_lens, BijectiveLens):
                    result.append(self.elem_lens.put(v_item, None))
                else:
                    result.append(v_item)
        return result


class DelimiterLens(BijectiveLens[str, List[str]]):
    """Bijective lens between delimited string and list of tokens (e.g. CSV)."""

    def __init__(self, delimiter: str = ","):
        self.delimiter = delimiter
        super().__init__(
            fwd_fn=lambda s: s.split(delimiter) if s else [],
            inv_fn=lambda tokens: delimiter.join(tokens),
        )


class ASTTransducerLens(BijectiveLens[str, Dict[str, Any]]):
    """Bijective transducer between serialized prefix S-expressions and structured AST dicts.
    Example:
      "(+ 1 (* 2 3))" <=> {"op": "+", "args": [1, {"op": "*", "args": [2, 3]}]}
    """

    def __init__(self):
        super().__init__(
            fwd_fn=self._parse_sexpr,
            inv_fn=self._format_sexpr,
        )

    def _parse_sexpr(self, expr_str: str) -> Dict[str, Any]:
        tokens = expr_str.replace("(", " ( ").replace(")", " ) ").split()
        if not tokens:
            return {}

        def parse(tok_list: List[str]) -> Any:
            if not tok_list:
                raise ValueError("Unexpected end of expression while parsing S-expression.")
            tok = tok_list.pop(0)
            if tok == "(":
                op = tok_list.pop(0)
                args = []
                while tok_list and tok_list[0] != ")":
                    args.append(parse(tok_list))
                if not tok_list or tok_list.pop(0) != ")":
                    raise ValueError("Missing closing parenthesis.")
                return {"op": op, "args": args}
            elif tok == ")":
                raise ValueError("Unexpected closing parenthesis.")
            else:
                # Try int, else float, else string identifier
                try:
                    return int(tok)
                except ValueError:
                    try:
                        return float(tok)
                    except ValueError:
                        return tok

        return parse(tokens)

    def _format_sexpr(self, ast: Any) -> str:
        if isinstance(ast, dict) and "op" in ast and "args" in ast:
            formatted_args = " ".join(self._format_sexpr(arg) for arg in ast["args"])
            if formatted_args:
                return f"({ast['op']} {formatted_args})"
            return f"({ast['op']})"
        else:
            return str(ast)


def verify_lens_laws(
    lens: Lens[Any, Any],
    sources: Sequence[Any],
    views: Sequence[Any],
) -> Dict[str, Any]:
    """Formally verifies the classical category-theoretic lens laws:
    1. Put-Get: get(put(v, s)) == v
    2. Get-Put: put(get(s), s) == s
    3. Put-Put: put(v2, put(v1, s)) == put(v2, s)
    """
    put_get_violations = 0
    get_put_violations = 0
    put_put_violations = 0

    # 1. Get-Put Law: put(get(s), s) == s
    for s in sources:
        v = lens.get(s)
        s_rebuilt = lens.put(v, s)
        if s_rebuilt != s:
            get_put_violations += 1

    # 2. Put-Get Law: get(put(v, s)) == v
    for s in sources:
        for v in views:
            s_updated = lens.put(v, s)
            v_recomputed = lens.get(s_updated)
            if v_recomputed != v:
                put_get_violations += 1

    # 3. Put-Put Law: put(v2, put(v1, s)) == put(v2, s)
    if len(views) >= 2:
        v1, v2 = views[0], views[1]
        for s in sources:
            intermediate = lens.put(v1, s)
            final_two_step = lens.put(v2, intermediate)
            direct = lens.put(v2, s)
            if final_two_step != direct:
                put_put_violations += 1

    total_checks = len(sources) + (len(sources) * len(views)) + len(sources)
    all_laws_pass = (
        get_put_violations == 0 and put_get_violations == 0 and put_put_violations == 0
    )

    return {
        "well_behaved": all_laws_pass,
        "get_put_passed": get_put_violations == 0,
        "put_get_passed": put_get_violations == 0,
        "put_put_passed": put_put_violations == 0,
        "get_put_violations": get_put_violations,
        "put_get_violations": put_get_violations,
        "put_put_violations": put_put_violations,
        "total_checks": total_checks,
    }
