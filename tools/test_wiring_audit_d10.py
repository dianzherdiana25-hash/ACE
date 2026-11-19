"""Tes konsistensi laporan backlog D10 terhadap hasil langsung `tools/wiring_audit.py`."""
from __future__ import annotations

from pathlib import Path
import unittest

from tools import wiring_audit as wa


class WiringAuditD10DocTests(unittest.TestCase):
    def test_d10_report_mentions_all_waiting_modules_and_excludes_them_from_queue(self) -> None:
        repo = Path(__file__).resolve().parents[1]
        doc_path = repo / "docs" / "research" / "ACE_WIRING_AUDIT_WAVE_D10.md"
        text = doc_path.read_text(encoding="utf-8")

        report = wa.audit_wiring(repo)
        waiting = [m for m in report["modules"] if m["status"] == "MENUNGGU_ENGINEER_UTAMA"]
        safe_tools = {m["path"] for m in report["tools_unwired_safe"]}

        self.assertEqual(len(waiting), 23)
        for mod in waiting:
            self.assertIn(mod["path"], text)

        for target in (
            "tools/kbm_qc.py",
            "tools/kbm_suite_v2.py",
            "tools/organ_quota_ledger.py",
            "tools/writeback_diagnose.py",
        ):
            self.assertIn(target, text)
            self.assertIn(target, safe_tools)
            self.assertNotIn(target, {m["path"] for m in waiting})


if __name__ == "__main__":
    unittest.main()
