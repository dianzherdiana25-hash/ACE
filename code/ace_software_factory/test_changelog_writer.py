"""Verifier riwayat Git fixture, kategori dan template rilis."""
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory
import unittest

from ace_software_factory import changelog_writer
from ace_software_factory._contracts import ContractError,identity


class ChangelogTests(unittest.TestCase):
    def setUp(self):
        if shutil.which("git") is None:
            self.skipTest("Git tidak tersedia")
        self.root=Path(self.enterContext(TemporaryDirectory()))
        self.git("init","-q")
        self.commit("base")
        self.base=self.git("rev-parse","HEAD")
        self.commit("feat(ui): Tambahkan tombol")
        self.commit("fix!: Perbarui bentuk <record>","BREAKING CHANGE: Kolom lama dilepas.")
        self.commit("Pesan tak bertipe")
        self.head=self.git("rev-parse","HEAD")

    def git(self,*args):
        result=subprocess.run(["git","-C",str(self.root),"-c","user.name=Fixture",
                               "-c","user.email=local@fixture.invalid","-c","commit.gpgsign=false",
                               "-c","core.hooksPath=/dev/null",*args],capture_output=True,timeout=6,check=True)
        return result.stdout.decode().strip()

    def commit(self,title,note=None):
        command=["commit","--allow-empty","-q","-m",title]
        if note:
            command.extend(["-m",note])
        self.git(*command)

    def plan(self,base,head):
        return {"schema":"ace.factory-changelog-plan.v1","source_ref":"fixture/git","version":"2.0.0",
                "base":base,"head":head}

    def test_real_git_range_with_breaking_notes_and_dates(self):
        plan=self.plan(self.base,self.head)
        report=changelog_writer.inspect(self.root,plan,identity(plan))
        self.assertEqual(report["commits"],3)
        self.assertEqual(report["sections"]["feat"][0]["scope"],"ui")
        self.assertEqual(report["breaking"][0]["breaking_notes"],["Kolom lama dilepas."])
        self.assertEqual(len(report["sections"]["other"]),1)
        document=changelog_writer.markdown(report)
        self.assertIn("&lt;record&gt;",document)
        self.assertNotIn("local@fixture.invalid",document)

    def test_equal_range_is_empty_and_reverse_is_not_a_release(self):
        plan=self.plan(self.head,self.head)
        self.assertEqual(changelog_writer.inspect(self.root,plan,identity(plan))["commits"],0)
        plan["head"]=self.base
        with self.assertRaises(ContractError):
            changelog_writer.inspect(self.root,plan,identity(plan))
