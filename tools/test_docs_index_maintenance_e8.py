"""Tes E8: dokumen turunan mutakhir dan catatan audit tautan sesuai kenyataan (TESTS ONLY)."""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import builder_onboarding_pack as bop  # noqa: E402
import handover_decision_extractor as hde  # noqa: E402
import handover_index as hi  # noqa: E402
import platform_requirements_summary as prs  # noqa: E402
import program_glossary as pg  # noqa: E402
import repo_cartography as rc  # noqa: E402

NOTE = ROOT / "docs" / "DOCS_INDEX_MAINTENANCE_20261119.md"
LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")


class TestDocsIndexMaintenanceE8(unittest.TestCase):
    def test_01_all_six_derived_docs_fresh(self):
        for mod in (hi, rc, pg, bop, prs, hde):
            target = ROOT / mod.DEFAULT_OUTPUT_REL
            self.assertTrue(target.is_file(), mod.DEFAULT_OUTPUT_REL)
            self.assertEqual(mod.main(["--root", str(ROOT), "--check", str(target)]), 0, mod.DEFAULT_OUTPUT_REL)

    def test_02_note_lists_every_refreshed_doc(self):
        text = NOTE.read_text(encoding="utf-8")
        for mod in (hi, rc, pg, bop, prs, hde):
            self.assertIn(mod.DEFAULT_OUTPUT_REL, text)

    def test_03_dead_links_in_docs_and_handover_match_note(self):
        dead = set()
        for base in ("docs", "handover"):
            for p in (ROOT / base).rglob("*.md"):
                for m in LINK.finditer(p.read_text(encoding="utf-8", errors="replace")):
                    t = m.group(1).split("#")[0]
                    if not t or re.match(r"^[a-z]+:", t):
                        continue
                    if not (p.parent / t).resolve().exists():
                        dead.add((p.relative_to(ROOT).as_posix(), t))
        note = NOTE.read_text(encoding="utf-8")
        for src, tgt in dead:
            self.assertIn(src, note)
            self.assertIn(tgt, note)
        self.assertEqual(len(dead), 6)  # 7 kejadian, 6 pasangan unik (store.py muncul 2x)


if __name__ == "__main__":
    unittest.main()
