"""Tes perbaikan wiring Kelompok 2 (10 paket agen, misi, dunia luar).

Tiap step harus fail-closed: tanpa flag ACE_WIRING_<PAKET>=1 step
mengembalikan {"status": "disabled"} dan tidak menulis artefak;
dengan flag, step menulis katalog API ke
workspace/wiring_kelompok2/<paket>.json dan melaporkan ok.
Step bersifat baca/katalog saja (smoke impor + enumerasi API),
bukan eksekusi aksi paket.
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
    "ace_code_agent", "ace_autonomy", "ace_host_controller",
    "ace_host_exchange", "ace_mcp", "ace_real_world",
    "ace_candidate_search", "ace_loop", "ace_chat", "ace_visual_bridge",
]


class WiringKelompok2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self._tmp.name)
        self.engine = _StubEngine(self.ws)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_registry_covers_all_10_packages(self) -> None:
        self.assertEqual(sorted(leap_wiring._WIRING_K2_MODULES),
                         sorted(_PACKAGES))

    def test_all_steps_disabled_without_flag(self) -> None:
        env = {k: v for k, v in os.environ.items()
               if not k.startswith("ACE_WIRING_")}
        with mock.patch.dict(os.environ, env, clear=True):
            for pkg in _PACKAGES:
                step = getattr(leap_wiring, f"step_wiring_{pkg}")
                self.assertEqual(step(self.engine),
                                 {"status": "disabled"}, pkg)
        self.assertFalse((self.ws / "wiring_kelompok2").exists())

    def test_all_steps_ok_with_flag_and_write_artifact(self) -> None:
        for pkg in _PACKAGES:
            flag = "ACE_WIRING_" + pkg.upper()
            with mock.patch.dict(os.environ, {flag: "1"}):
                step = getattr(leap_wiring, f"step_wiring_{pkg}")
                out = step(self.engine)
            self.assertEqual(out["status"], "ok", pkg)
            self.assertEqual(out["package"], pkg)
            self.assertEqual(out["modules"],
                             len(leap_wiring._WIRING_K2_MODULES[pkg]), pkg)
            artifact = self.ws / "wiring_kelompok2" / f"{pkg}.json"
            payload = json.loads(artifact.read_text(encoding="utf-8"))
            self.assertEqual(payload["package"], pkg)
            self.assertEqual(sorted(payload["modules"]),
                             sorted(leap_wiring._WIRING_K2_MODULES[pkg]),
                             pkg)


if __name__ == "__main__":
    unittest.main()
