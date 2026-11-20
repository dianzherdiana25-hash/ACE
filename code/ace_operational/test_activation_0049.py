"""Tes integrasi & cadangan aktivasi EVO 0049 (Ilmu, Sitasi, Software Factory)."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from ace_operational import leap_wiring
from ace_operational.test_leap_wiring import _StubEngine, _episode

_REQUIRED_STEPS = (
    "step_experiment_designer",
    "step_corpus_novelty",
    "step_teaching_program",
    "step_citation_validator",
    "step_catalog_audit",
    "step_preaudit_oracle",
    "step_proposer_v2",
    "step_software_factory",
)

_ALL_WIRED = all(callable(getattr(leap_wiring, name, None)) for name in _REQUIRED_STEPS)
_REPO_ROOT = Path(__file__).resolve().parents[2]


class Activation0049Tests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self._tmp.name)
        self.engine = _StubEngine(self.ws)
        mem_dir = self.ws / "cognitive_memory"
        mem_dir.mkdir(parents=True, exist_ok=True)
        (mem_dir / "memory.jsonl").write_text(
            _episode(1, "ep1", "ilmu", "uji replikasi sitasi") + "\n",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.engine.store.close()
        self._tmp.cleanup()

    def test_baseline_step_self_runs_cleanly(self) -> None:
        res = leap_wiring.step_self(self.engine)
        self.assertEqual(res["status"], "ok")
        self.assertTrue((self.ws / "hypotheses.json").is_file())

    @unittest.skipUnless(_ALL_WIRED, "Membutuhkan seluruh cabang AG181-AG187 & AG189 dalam overlay")
    def test_overlay_all_evo0049_steps_end_to_end(self) -> None:
        self.engine.cycle_count = 1000
        self_res = leap_wiring.step_self(self.engine)
        self.assertEqual(self_res["status"], "ok")
        self.assertEqual(self_res["corpus_novelty"]["status"], "ok")

        # Default ACE_PROPOSER_V2 nonaktif -> skipped
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ACE_PROPOSER_V2", None)
            self.assertEqual(leap_wiring.step_proposer_v2(self.engine)["status"], "skipped")

        with mock.patch.dict(os.environ, {"ACE_PROPOSER_V2": "1"}):
            for name in _REQUIRED_STEPS:
                out = getattr(leap_wiring, name)(self.engine)
                self.assertEqual(out["status"], "ok", f"{name} gagal: {out}")

        for rel in (
            "experiment_designs.json",
            "corpus_novelty.json",
            "teaching_program.json",
            "citation_validation.json",
            "operator_catalog.json",
            "catalog_audit.json",
            "preaudit_oracle.json",
            "proposer_v2_report.json",
            "software_factory_status.json",
        ):
            self.assertTrue((self.ws / rel).is_file(), f"Artefak hilang: {rel}")

    @unittest.skipUnless(_ALL_WIRED, "Membutuhkan seluruh cabang AG181-AG187 & AG189 dalam overlay")
    def test_overlay_dispatch_wiring_audit_and_section3_admission_quarantine(self) -> None:
        engine_src = (_REPO_ROOT / "code" / "ace_operational" / "autonomous_engine.py").read_text(encoding="utf-8")
        for token in (
            "leap_wiring.step_experiment_designer",
            "leap_wiring.step_teaching_program",
            "leap_wiring.step_citation_validator",
            "leap_wiring.step_catalog_audit",
            "leap_wiring.step_preaudit_oracle",
            "leap_wiring.step_proposer_v2",
            "leap_wiring.step_software_factory",
        ):
            self.assertIn(token, engine_src)

        raw = subprocess.check_output(
            [sys.executable, str(_REPO_ROOT / "tools" / "wiring_audit.py"), "--format", "json"],
            cwd=str(_REPO_ROOT),
            text=True,
        )
        by_mod = {m["module"]: m for m in json.loads(raw)["modules"]}
        for mod in (
            "tools.experiment_designer",
            "tools.corpus_novelty",
            "tools.teaching_program",
            "ace_operational.citation_validator",
            "ace_operational.catalog_artifact",
            "ace_operational.catalog_gap",
            "ace_operational.preaudit_oracle",
            "ace_operational.proposer_stage1_v2",
            "ace_operational.software_factory",
        ):
            self.assertEqual(by_mod[mod]["status"], "WIRED", f"{mod} belum WIRED: {by_mod[mod]}")

        # AG188 admission_hygiene.py mengimpor abc_v3_scorer (wilayah terlarang §3) -> tidak di-wire ke leap_wiring
        self.assertNotIn("code/ace_operational/leap_wiring.py", by_mod["ace_operational.admission_hygiene"]["non_test_callers"])
        self.assertNotIn("code/ace_operational/leap_wiring.py", by_mod["ace_operational.abc_v3_scorer"]["non_test_callers"])


if __name__ == "__main__":
    unittest.main()
