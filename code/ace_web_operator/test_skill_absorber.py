"""Verifier kutipan, hash, lisensi dan cakupan tujuan latihan."""
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_web_operator import skill_absorber
from ace_web_operator._contracts import ContractError,identity


def package_input(root,suite_anchor):
    body=b"Catatan.\nGunakan dua operand untuk contoh sederhana.\nRujukan akhir.\n"
    (root/"lesson.md").write_bytes(body)
    return {"schema":"ace.web.skill-absorb-plan.v1","id":"two_values","cluster":"k01","version":1,
            "source_ref":"fixture/catalog","heldout_sha256":suite_anchor,
            "sources":[{"id":"notes","path":"lesson.md","sha256":sha256(body).hexdigest(),"license":"CC0-1.0",
                        "license_ref":"fixture/license","source_ref":"fixture/lesson-file"}],
            "objectives":[{"id":"sum","statement":"Jumlahkan dua bilangan","source_ref":"fixture/objective"}],
            "lessons":[{"id":"examples","source":"notes","first_line":2,"last_line":2,
                        "objectives":["sum"],"source_ref":"fixture/line"}],
            "practice":[{"id":"pair_1","objective":"sum","prompt":"Jumlahkan enam dan dua.","op":"int_exact",
                         "expected":8,"source_ref":"fixture/practice"}]}


class AbsorbTests(unittest.TestCase):
    def setUp(self):
        self.root=Path(self.enterContext(TemporaryDirectory()))
        self.plan=package_input(self.root,"a"*64)

    def assemble(self):
        return skill_absorber.absorb(self.root,self.plan,identity(self.plan))

    def test_lesson_quote_and_training_verify_policy_without_heldout_contents(self):
        package,receipt=self.assemble()
        self.assertEqual(package["lessons"][0]["excerpt"],"Gunakan dua operand untuk contoh sederhana.")
        self.assertEqual(receipt["package_sha256"],identity(package))
        self.assertEqual(package["heldout_sha256"],"a"*64)
        self.assertEqual(receipt["status"],"curriculum_prepared")

    def test_refuses_bad_license_and_tampered_source(self):
        self.plan["sources"][0]["license"]="unlicensed"
        with self.assertRaisesRegex(ContractError,"lisensi"):
            self.assemble()
        self.plan["sources"][0]["license"]="CC0-1.0"
        (self.root/"lesson.md").write_text("different")
        with self.assertRaisesRegex(ContractError,"SHA-256"):
            self.assemble()
