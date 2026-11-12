"""Grid family adapter for the discovery core (P1).

Delegates byte-for-byte to the grid machinery that
`operator_discovery` used to import directly
(`grid_generalization._budget_for` / `_passes`,
`grid_substrate.grid_variants` / `_OPERATORS`, and the
'#' wall-character seed). Behaviour is identical by
construction; the v4 replication guard is the empirical
check. New families implement the same protocol in their
own adapter module — the core never learns their names.
"""
from __future__ import annotations

import hashlib

from .grid_generalization import _budget_for, _passes
from .grid_substrate import _OPERATORS, grid_variants


class GridAdapter:
    family_id = "grid"

    def make_budget(self, task):
        return _budget_for(task)

    def passes(self, code, cases, truth) -> int:
        return _passes(code, cases, truth)

    def baseline_variants(self, code) -> list:
        return grid_variants(code, _OPERATORS)

    def baseline_catalog_id(self) -> str:
        digest = hashlib.sha256(
            repr(_OPERATORS).encode()).hexdigest()[:16]
        return f"grid-operators-{digest}"

    def extra_string_candidates(self, code) -> set:
        # The grid family's spec fixes '#' as the wall
        # character; the case grids contain it.
        return {"#"}


GRID_ADAPTER = GridAdapter()
