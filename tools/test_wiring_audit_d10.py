"""Tes konsistensi laporan backlog D10 terhadap hasil langsung `tools/wiring_audit.py`.

Dokumen D10 adalah potret audit pada `ba7f4b9` (sebelum penyambungan);
tes ini mengunci dua hal: daftar 23 modul `MENUNGGU_ENGINEER_UTAMA` tetap
utuh dan terdokumentasi, dan keempat target prioritas D10 kini berstatus
`WIRED` sesudah PR #425–#428 tergabung (penyegaran pasca-wiring oleh
engineer utama, 20 Nov 2026).
"""
from __future__ import annotations

from pathlib import Path
import unittest

from tools import wiring_audit as wa


class WiringAuditD10DocTests(unittest.TestCase):
    def test_d10_report_mentions_all_waiting_modules_and_targets_now_wired(self) -> None:
        repo = Path(__file__).resolve().parents[1]
        doc_path = repo / "docs" / "research" / "ACE_WIRING_AUDIT_WAVE_D10.md"
        text = doc_path.read_text(encoding="utf-8")

        report = wa.audit_wiring(repo)
        waiting = [m for m in report["modules"] if m["status"] == "MENUNGGU_ENGINEER_UTAMA"]
        safe_tools = {m["path"] for m in report["tools_unwired_safe"]}
        status_by_path = {m["path"]: m["status"] for m in report["modules"]}

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
            # Pasca-wiring (#425–#428): target tidak lagi "unwired safe",
            # melainkan WIRED (dipakai pemanggil non-tes).
            self.assertNotIn(target, safe_tools)
            self.assertEqual(status_by_path.get(target), "WIRED")
            self.assertNotIn(target, {m["path"] for m in waiting})


if __name__ == "__main__":
    unittest.main()
