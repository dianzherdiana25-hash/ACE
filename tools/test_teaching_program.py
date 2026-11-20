"""Tes unit untuk tools/teaching_program.py (AG97)."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from tools.teaching_program import (
    GAIN_SCHEMA,
    PLAN_SCHEMA,
    build_lesson_plan,
    evaluate_student_gains,
    main,
)


class TeachingProgramTests(unittest.TestCase):
    def test_tiered_plan_and_improving_vs_non_improving_students(self) -> None:
        skill_spec = {
            "skill_id": "sqlite_ro_discipline",
            "title": "Disiplin Akses SQLite Read-Only",
            "concepts": [
                {
                    "concept_id": "uri_ro",
                    "tier": "dasar",
                    "title": "URI mode=ro",
                    "explanation": "Buka berkas SQLite dengan uri=True dan ?mode=ro agar pembukaan gagal bila tidak ada.",
                    "exercise_prompt": "Parameter URI apa yang memaksa mode baca-saja?",
                    "expected_answer": "mode=ro dengan uri=True",
                    "keywords": ["mode", "ro", "uri"],
                },
                {
                    "concept_id": "pragma_query_only",
                    "tier": "menengah",
                    "title": "PRAGMA query_only",
                    "explanation": "Setel PRAGMA query_only = ON segera setelah koneksi dibuka.",
                    "exercise_prompt": "PRAGMA SQLite apa yang menolak pernyataan tulis di sisi koneksi?",
                    "expected_answer": "PRAGMA query_only ON",
                    "keywords": ["pragma", "query_only", "on"],
                },
                {
                    "concept_id": "byte_invariant",
                    "tier": "lanjut",
                    "title": "Bukti tak-berubah byte",
                    "explanation": "Verifikasi SHA-256 berkas DB sumber identik sebelum dan sesudah pembacaan.",
                    "exercise_prompt": "Bagaimana membuktikan pembacaan tidak memutasi berkas sumber?",
                    "expected_answer": "bandingkan sha256 berkas sebelum dan sesudah",
                    "keywords": ["sha256", "sebelum", "sesudah"],
                },
            ],
        }

        plan = build_lesson_plan(skill_spec)
        self.assertEqual(plan["schema"], PLAN_SCHEMA)
        self.assertEqual(len(plan["exercises"]), 3)
        self.assertEqual([e["tier"] for e in plan["exercises"]], ["dasar", "menengah", "lanjut"])

        students = [
            # Murid 1 meningkat signifikan setelah pengajaran.
            {
                "student_id": "murid-maju",
                "pre_answers": {
                    "ex:uri_ro": "buka file biasa saja",
                    "ex:pragma_query_only": "",
                    "ex:byte_invariant": "lihat ukurannya",
                },
                "post_answers": {
                    "ex:uri_ro": "mode=ro dengan uri=True",
                    "ex:pragma_query_only": "PRAGMA query_only ON",
                    "ex:byte_invariant": "bandingkan sha256 berkas sebelum dan sesudah",
                },
            },
            # Murid 2 tidak meningkat (tetap stagnan di nol/rendah).
            {
                "student_id": "murid-stagnan",
                "pre_answers": {
                    "ex:uri_ro": "pakai mode biasa",
                    "ex:pragma_query_only": "tidak tahu",
                    "ex:byte_invariant": "tidak tahu",
                },
                "post_answers": {
                    "ex:uri_ro": "pakai mode biasa",
                    "ex:pragma_query_only": "tidak tahu",
                    "ex:byte_invariant": "tidak tahu",
                },
            },
        ]

        report = evaluate_student_gains(plan, students)
        self.assertEqual(report["schema"], GAIN_SCHEMA)
        self.assertEqual(report["student_count"], 2)
        self.assertEqual(report["improving_count"], 1)
        self.assertEqual(report["non_improving_count"], 1)

        by_id = {row["student_id"]: row for row in report["students"]}
        self.assertTrue(by_id["murid-maju"]["improved"])
        self.assertEqual(by_id["murid-maju"]["status"], "meningkat")
        self.assertGreater(by_id["murid-maju"]["gain"], 0.5)

        self.assertFalse(by_id["murid-stagnan"]["improved"])
        self.assertLessEqual(by_id["murid-stagnan"]["gain"], 0.0)
        self.assertIn(by_id["murid-stagnan"]["status"], {"stagnan", "menurun"})

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            sp = tmp / "skill.json"
            st = tmp / "students.json"
            sp.write_text(json.dumps(skill_spec), encoding="utf-8")
            st.write_text(json.dumps(students), encoding="utf-8")
            self.assertEqual(main(["--skill", str(sp), "--students", str(st)]), 0)


if __name__ == "__main__":
    unittest.main()
