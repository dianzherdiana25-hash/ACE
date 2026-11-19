"""Tes dokumen AKTIVASI_SELF_SEND: kutipan konstanta harus cocok dengan kode.

Kenapa: dokumen aktivasi yang melenceng dari self_send.py berbahaya bagi
operator. Tes ini hanya MEMBACA sumber self_send.py (tanpa import/ubah).
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOC = (ROOT / "docs" / "AKTIVASI_SELF_SEND.md").read_text(encoding="utf-8")
SRC = (ROOT / "code" / "ace_operational" / "self_send.py").read_text(encoding="utf-8")

CONSTS = ["MARKER_NAME", "EXPECTED_REPO", "BASE_BRANCH", "BASIS_REF",
          "BRANCH_PREFIX", "AUDIT_REPO_PATH", "ACK_NAME"]
REASONS = ["marker_absent", "fetch_target_mismatch", "push_target_mismatch",
           "gh_auth_unhealthy", "base_main_missing", "worktree_dirty",
           "duplicate_branch", "outgoing_validation_failed"]


class SelfSendDoc(unittest.TestCase):
    def test_constants_match(self):
        for name in CONSTS:
            m = re.search(rf'^{name} = "([^"]+)"', SRC, re.M)
            self.assertIsNotNone(m, name)
            self.assertIn(m.group(1), DOC, name)

    def test_refspec_and_prefixes(self):
        self.assertIn("+refs/heads/main:refs/ace-self-send/base", DOC)
        self.assertIn('ALLOWED_PATH_PREFIXES = ("handover/", "evidence/")', SRC)
        self.assertIn("handover/", DOC)
        self.assertIn("evidence/", DOC)

    def test_refusal_codes_exist_in_source(self):
        for r in REASONS:
            self.assertIn(r, SRC, r)
            self.assertIn(r, DOC, r)

    def test_denylist_and_classes(self):
        for frag in ("ledger_penghasilan", "utang_awal", "secret", "credential",
                     ".env", ".ace-llm-token", "id_rsa", ".pem", ".key"):
            self.assertIn(f'"{frag}"', SRC)
            self.assertIn(frag, DOC)
        for c in ("verdict_sealed", "mission_ratified", "skill_verified"):
            self.assertIn(c, SRC)
            self.assertIn(c, DOC)

    def test_operator_warning_and_sections(self):
        self.assertIn("HANYA OPERATOR", DOC)
        for h in ("Prasyarat", "Aktivasi (terawasi)", "Kondisi berhenti", "Rollback"):
            self.assertIn(h, DOC)
        self.assertIn("--draft", DOC)


if __name__ == "__main__":
    unittest.main()
