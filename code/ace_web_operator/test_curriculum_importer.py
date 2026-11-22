"""Verifier commit Git nyata dan penolakan byte, lisensi, serta symlink."""
from hashlib import sha256
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory
import unittest

from ace_web_operator import curriculum_importer
from ace_web_operator._contracts import ContractError,identity


class ImportTests(unittest.TestCase):
    def git(self,*args):
        result=subprocess.run(["git","-C",str(self.repo),"-c","user.name=Fixture",
                               "-c","user.email=local@fixture.invalid","-c","commit.gpgsign=false",
                               "-c","core.hooksPath=/dev/null",*args],capture_output=True,check=True,timeout=5)
        return result.stdout.decode().strip()

    def setUp(self):
        if shutil.which("git") is None:
            self.skipTest("Git lokal tidak tersedia")
        self.repo=Path(self.enterContext(TemporaryDirectory()))
        self.source=b"# Subject\nPembahasan lokal."
        license_file=b"SPDX-License-Identifier: CC0-1.0\nFixture license."
        (self.repo/"lesson.md").write_bytes(self.source)
        (self.repo/"LICENSE.txt").write_bytes(license_file)
        (self.repo/"link.md").symlink_to("lesson.md")
        self.git("init","-q")
        self.git("add","--","lesson.md","LICENSE.txt","link.md")
        self.git("commit","-qm","Publish fixture source snapshot")
        self.plan={"schema":"ace.web.curriculum-import-plan.v1","source_ref":"fixture/import","repository_ref":"fixture/repo",
                   "commit":self.git("rev-parse","HEAD"),
                   "license":{"id":"CC0-1.0","path":"LICENSE.txt","sha256":sha256(license_file).hexdigest(),
                              "source_ref":"fixture/license"},
                   "files":[{"id":"intro","path":"lesson.md","sha256":sha256(self.source).hexdigest(),"source_ref":"fixture/lesson"}]}

    def import_files(self):
        return curriculum_importer.import_sources(self.repo,self.plan,identity(self.plan))

    def test_reads_pinned_blob_even_if_checkout_differs(self):
        (self.repo/"lesson.md").write_bytes(b"working change")
        files,report=self.import_files()
        self.assertEqual(files["sources/intro.md"],self.source)
        self.assertEqual(report["git_commit"],self.plan["commit"])
        self.assertEqual(report["sources"][0]["license"],"CC0-1.0")
        self.assertEqual((self.repo/"lesson.md").read_bytes(),b"working change")

    def test_rejects_license_mismatch_and_link_blob(self):
        self.plan["license"]["id"]="MIT"
        with self.assertRaisesRegex(ContractError,"SPDX"):
            self.import_files()
        self.plan["license"]["id"]="CC0-1.0"
        self.plan["files"][0]["path"]="link.md"
        with self.assertRaisesRegex(ContractError,"reguler"):
            self.import_files()
