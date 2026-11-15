"""Lineage-Guard default-on regression tests.

The sealed confirmation run (PR #230) returned GUARD_ADOPTED.
The guard implementation already lived in
`operator_discovery.solve_task` behind an opt-in flag
(PR #206); this module pins the absorbed state:

- the guard is the DEFAULT behaviour of `solve_task` and
  `run_discovery` (absorption audit PR #231, item #12);
- explicit `guard=False` still reproduces the unguarded
  solver (measurement baselines pin it deliberately);
- on the development band 20261501, the DEFAULT solver
  recovers both registered distractor witnesses
  (catalog_control-020 / -021) under the registered 'nc'
  distractor, while the unguarded solver loses both —
  the same fact the sealed run's L1/L2 gates established
  with the external harness (PR #193 / PR #230), now
  guarded by a repo test against the production code.
"""

import importlib.util
import inspect
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ace_operational.distractor_inoculation import load_registry
from ace_operational.grid_adapter import GRID_ADAPTER
from ace_operational.grid_generalization import build_universe
from ace_operational.operator_discovery import run_discovery, solve_task

REPO = Path(__file__).resolve().parents[2]
DEV_SEED = 20261501
DISTRACTOR_ID = "name-swap-523014-nc-band20261501"
WITNESSES = ("catalog_control-020", "catalog_control-021")


def _load_driver():
    spec = importlib.util.spec_from_file_location(
        "abc_v3_run", REPO / "tools" / "abc_v3_run.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _holdout_solved(task, code) -> bool:
    cases = [tuple(c) for c in task["holdout_cases"]]
    return GRID_ADAPTER.passes(code, cases,
                               task["holdout_truth"]) == len(cases)


class DefaultOnSignatureTests(unittest.TestCase):
    def test_solve_task_defaults_guard_on(self):
        default = inspect.signature(solve_task).parameters["guard"].default
        self.assertIs(default, True)

    def test_run_discovery_defaults_guard_on(self):
        default = inspect.signature(run_discovery).parameters["guard"].default
        self.assertIs(default, True)


class DevBandWitnessTests(unittest.TestCase):
    """Default solver vs explicit-off on the real dev catalog."""

    @classmethod
    def setUpClass(cls):
        drv = _load_driver()
        universe = build_universe(seed=DEV_SEED)
        split = drv.split_universe(universe["tasks"])
        control = {t["task_id"]: t for t in split["control"]}
        cls.tasks = {wid: control[wid] for wid in WITNESSES}
        discovery = json.loads(
            (REPO / "evidence" / "abc-v3-run-state"
             / f"discovery_{DEV_SEED}.json").read_text())
        keys, chains = drv._extract_admitted(discovery)
        records = load_registry(
            Path(__file__).resolve().parent / "distractor_registry.json")
        rec = next(r for r in records if r["id"] == DISTRACTOR_ID)
        causal = rec["_key_tuple"]
        # The dev band is the witness band precisely because its
        # own discovery admits the causal 'nc' key naturally: the
        # natural catalog is already the infected catalog (the
        # registry's other bands receive the same key by
        # injection). No injection step applies here.
        assert causal in keys, "causal key missing from dev catalog"
        cls.infected_keys = keys
        cls.chains = chains

    def test_default_solver_recovers_both_witnesses(self):
        for wid, task in self.tasks.items():
            with self.subTest(witness=wid):
                returned = solve_task(task, GRID_ADAPTER,
                                      self.infected_keys, self.chains)
                self.assertTrue(
                    _holdout_solved(task, returned),
                    f"default (guarded) solver lost {wid}")

    def test_explicit_off_loses_both_witnesses(self):
        for wid, task in self.tasks.items():
            with self.subTest(witness=wid):
                returned = solve_task(task, GRID_ADAPTER,
                                      self.infected_keys, self.chains,
                                      guard=False)
                self.assertFalse(
                    _holdout_solved(task, returned),
                    f"unguarded solver unexpectedly solved {wid}")


if __name__ == "__main__":
    unittest.main()
