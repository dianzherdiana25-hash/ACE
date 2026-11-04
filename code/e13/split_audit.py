"""Flag rule and task overlap before any episode is exposed to a solver."""

from collections.abc import Callable
from dataclasses import dataclass

from .contract import Output, canonical_json


@dataclass(frozen=True)
class RuleBlock:
    family: str
    split: str
    # The benchmark supplies a shape with identifiers and literals normalized,
    # and task payloads with routing metadata and seeds removed.
    shape: object
    tasks: tuple[object, ...]
    reference: Callable[[object], Output]


def audit_splits(blocks, probe_inputs):
    """Reject cross-split matches within a family using a common probe suite."""
    first_split = {}
    for block in blocks:
        if block.family not in ("S", "G") or block.split not in (
            "development", "selection", "sealed_evaluation"
        ):
            raise ValueError("unknown bank family or split")
        probes = probe_inputs.get(block.family)
        if not probes or not block.tasks:
            raise ValueError("each block needs common probes and task payloads")

        behavior = [block.reference(probe) for probe in probes]
        keys = [("rule shape", block.shape), ("probe behavior", behavior)]
        keys.extend(("task payload", task) for task in block.tasks)
        for kind, value in keys:
            key = (block.family, kind, canonical_json(value))
            split = first_split.setdefault(key, block.split)
            if split != block.split:
                raise ValueError(f"{kind} overlap in {block.family}: {split} / {block.split}")
