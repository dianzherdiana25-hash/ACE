"""Tes perbaikan wiring Kelompok 3 (15 paket evolusi, riset, evaluasi
+ 2 modul orphan tambahan; story_state dikecualikan by design).

Tiap step harus fail-closed: tanpa flag ACE_WIRING_<PAKET>=1 step
mengembalikan {"status": "disabled"} dan tidak menulis artefak;
dengan flag, step menulis katalog API ke
workspace/wiring_kelompok3/<paket>.json dan melaporkan ok.
Step bersifat bench/observasi/katalog saja (smoke impor +
enumerasi API), bukan jalur keputusan. ace_evaluator tidak
di-wire (wilayah terlarang MENUNGGU_ENGINEER_UTAMA di
wiring_audit) dan tidak punya step di sini. Begitu juga
ace_operational.story_state: tes karantina aktivasi mewajibkan
modul itu tetap ORPHAN dan leap_wiring tidak boleh menjadi
pemanggil non-tesnya, jadi tidak ada step untuknya.
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
    "ace_capability_evolution", "ace_evolution", "ace_selfmodel",
    "ace_research_agenda", "ace_research_discovery",
    "ace_research_hypgen", "ace_research_reptransfer",
    "ace_research_generations", "ace_research_repair",
    "ace_research_f12", "ace_research_f13", "ace_research_f14",
    "ace_red_team", "ace_integration_redteam", "ace_runtime",
]

_EXTRAS = [
    "ace_core_repair_decomposed_library",
    "ace_operational_massive_skills_expansion",
]


class WiringKelompok3Tests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self._tmp.name)
        self.engine = _StubEngine(self.ws)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_registry_covers_all_15_packages(self) -> None:
        self.assertEqual(sorted(leap_wiring._WIRING_K3_MODULES),
                         sorted(_PACKAGES))

    def test_no_step_for_ace_evaluator(self) -> None:
        self.assertFalse(hasattr(leap_wiring, "step_wiring_ace_evaluator"))
        self.assertNotIn("ace_evaluator", leap_wiring._WIRING_K3_MODULES)

    def test_no_step_for_story_state_quarantine(self) -> None:
        self.assertFalse(hasattr(
            leap_wiring, "step_wiring_ace_operational_story_state"))
        self.assertNotIn("ace_operational_story_state",
                         leap_wiring._WIRING_K3_EXTRA_MODULES)

    def test_all_steps_disabled_without_flag(self) -> None:
        env = {k: v for k, v in os.environ.items()
               if not k.startswith("ACE_WIRING_")}
        with mock.patch.dict(os.environ, env, clear=True):
            for pkg in _PACKAGES:
                step = getattr(leap_wiring, f"step_wiring_{pkg}")
                self.assertEqual(step(self.engine),
                                 {"status": "disabled"}, pkg)
            for key in _EXTRAS:
                step = getattr(leap_wiring, f"step_wiring_{key}")
                self.assertEqual(step(self.engine),
                                 {"status": "disabled"}, key)
        self.assertFalse((self.ws / "wiring_kelompok3").exists())

    def test_all_steps_ok_with_flag_and_write_artifact(self) -> None:
        for pkg in _PACKAGES:
            flag = "ACE_WIRING_" + pkg.upper()
            with mock.patch.dict(os.environ, {flag: "1"}):
                step = getattr(leap_wiring, f"step_wiring_{pkg}")
                out = step(self.engine)
            self.assertEqual(out["status"], "ok", pkg)
            self.assertEqual(out["package"], pkg)
            self.assertEqual(out["modules"],
                             len(leap_wiring._WIRING_K3_MODULES[pkg]), pkg)
            artifact = self.ws / "wiring_kelompok3" / f"{pkg}.json"
            payload = json.loads(artifact.read_text(encoding="utf-8"))
            self.assertEqual(payload["package"], pkg)
            self.assertEqual(sorted(payload["modules"]),
                             sorted(leap_wiring._WIRING_K3_MODULES[pkg]),
                             pkg)

    def test_extra_modules_ok_with_flag_and_write_artifact(self) -> None:
        self.assertEqual(sorted(leap_wiring._WIRING_K3_EXTRA_MODULES),
                         sorted(_EXTRAS))
        for key in _EXTRAS:
            flag = "ACE_WIRING_" + key.upper()
            dotted = leap_wiring._WIRING_K3_EXTRA_MODULES[key]
            with mock.patch.dict(os.environ, {flag: "1"}):
                step = getattr(leap_wiring, f"step_wiring_{key}")
                out = step(self.engine)
            self.assertEqual(out["status"], "ok", key)
            self.assertEqual(out["package"], dotted)
            self.assertEqual(out["modules"], 1, key)
            artifact = self.ws / "wiring_kelompok3" / f"{dotted}.json"
            payload = json.loads(artifact.read_text(encoding="utf-8"))
            self.assertEqual(payload["package"], dotted)


if __name__ == "__main__":
    unittest.main()
