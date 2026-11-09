"""Inductive data transformation synthesizer (FlashFill style).

Synthesizes deterministic string and dictionary formatting rules from
input-output demonstration pairs.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class TransformRule:
    rule_id: str
    operations: Tuple[str, ...]
    transform_code: str


class DataWranglerSynthesizer:
    """Synthesizes structured data transformation functions from I/O examples."""

    def __init__(self):
        self.rules: Dict[str, TransformRule] = {}

    def synthesize_string_transform(
        self,
        examples: List[Tuple[str, str]],
        func_name: str = "transform_data_field",
    ) -> Optional[TransformRule]:
        """Synthesize string transformation pipeline (split, casing, prefix/suffix, extraction)."""
        if not examples:
            return None

        # Check for simple constant identity
        if all(inp == out for inp, out in examples):
            code = f"def {func_name}(val: str) -> str:\n    return val\n"
            return TransformRule(rule_id="rule_identity", operations=("IDENTITY",), transform_code=code)

        # Check for case transform
        if all(inp.upper() == out for inp, out in examples):
            code = f"def {func_name}(val: str) -> str:\n    return val.upper()\n"
            return TransformRule(rule_id="rule_upper", operations=("UPPER",), transform_code=code)
        if all(inp.lower() == out for inp, out in examples):
            code = f"def {func_name}(val: str) -> str:\n    return val.lower()\n"
            return TransformRule(rule_id="rule_lower", operations=("LOWER",), transform_code=code)
        if all(inp.strip() == out for inp, out in examples):
            code = f"def {func_name}(val: str) -> str:\n    return val.strip()\n"
            return TransformRule(rule_id="rule_strip", operations=("STRIP",), transform_code=code)

        # Check for substring extraction by delimiters
        first_in, first_out = examples[0]
        common_delims = [":", ",", "-", "/", "_", " ", "|"]
        for delim in common_delims:
            if delim in first_in:
                parts = first_in.split(delim)
                for idx, part in enumerate(parts):
                    if part.strip() == first_out.strip():
                        # Verify consistency across all examples
                        if all(len(inp.split(delim)) > idx and inp.split(delim)[idx].strip() == out.strip() for inp, out in examples):
                            code = (
                                f"def {func_name}(val: str) -> str:\n"
                                f"    parts = val.split({repr(delim)})\n"
                                f"    return parts[{idx}].strip() if len(parts) > {idx} else ''\n"
                            )
                            rule = TransformRule(
                                rule_id=f"rule_delim_{delim}_{idx}",
                                operations=(f"SPLIT_{delim}", f"INDEX_{idx}", "STRIP"),
                                transform_code=code,
                            )
                            return rule

        # Fallback: substring slicing
        start_idx = first_in.find(first_out)
        if start_idx != -1:
            end_idx = start_idx + len(first_out)
            if all(inp[start_idx:start_idx + len(out)] == out for inp, out in examples):
                code = (
                    f"def {func_name}(val: str) -> str:\n"
                    f"    return val[{start_idx}:{end_idx}]\n"
                )
                return TransformRule(
                    rule_id=f"rule_slice_{start_idx}_{end_idx}",
                    operations=(f"SLICE_{start_idx}_{end_idx}",),
                    transform_code=code,
                )

        return None
