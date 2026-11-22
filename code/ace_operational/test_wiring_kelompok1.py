"""Tes perbaikan wiring Kelompok 1 (20 paket penalaran & pengetahuan).

Tiap step harus fail-closed: tanpa flag ACE_WIRING_<PAKET>=1 step
mengembalikan {"status": "disabled"} dan tidak menulis artefak;
dengan flag, step menulis katalog API ke
workspace/wiring_kelompok1/<paket>.json dan melaporkan ok.
"""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ace_operational import leap_wiring


class _StubEngine:
    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace
        self.cycle_count = 200


_PACKAGES = [
    "ace_cognition", "ace_mcts", "ace_causal", "ace_neurosymbolic",
    "ace_smt", "ace_ilp", "ace_egraph", "ace_automata",
    "ace_abstract_interp", "ace_interpolation", "ace_inversion",
    "ace_abstraction", "ace_epistemic", "ace_conformal", "ace_pac_bayes",
    "ace_game_theory", "ace_synthesis", "ace_component_synthesis",
    "ace_dsl_growth", "ace_gnn",
]


class WiringKelompok1Tests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self._tmp.name)
        self.engine = _StubEngine(self.ws)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_registry_covers_all_20_packages(self) -> None:
        self.assertEqual(sorted(leap_wiring._WIRING_K1_MODULES),
                         sorted(_PACKAGES))

    def test_all_steps_disabled_without_flag(self) -> None:
        env = {k: v for k, v in os.environ.items()
               if not k.startswith("ACE_WIRING_")}
        with mock.patch.dict(os.environ, env, clear=True):
            for pkg in _PACKAGES:
                step = getattr(leap_wiring, f"step_wiring_{pkg}")
                self.assertEqual(step(self.engine),
                                 {"status": "disabled"}, pkg)
        self.assertFalse((self.ws / "wiring_kelompok1").exists())

    def test_all_steps_ok_with_flag_and_write_artifact(self) -> None:
        for pkg in _PACKAGES:
            flag = "ACE_WIRING_" + pkg.upper()
            with mock.patch.dict(os.environ, {flag: "1"}):
                step = getattr(leap_wiring, f"step_wiring_{pkg}")
                out = step(self.engine)
            self.assertEqual(out["status"], "ok", pkg)
            self.assertEqual(out["package"], pkg)
            self.assertEqual(out["modules"],
                             len(leap_wiring._WIRING_K1_MODULES[pkg]), pkg)
            artifact = self.ws / "wiring_kelompok1" / f"{pkg}.json"
            payload = json.loads(artifact.read_text(encoding="utf-8"))
            self.assertEqual(payload["package"], pkg)
            self.assertEqual(sorted(payload["modules"]),
                             sorted(leap_wiring._WIRING_K1_MODULES[pkg]),
                             pkg)


if __name__ == "__main__":
    unittest.main()
