"""Verifier dua profil terpisah dan penolakan marker/symlink yang berpindah."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_web_operator import multi_account_guard
from ace_web_operator._contracts import identity


class GuardTests(unittest.TestCase):
    def setUp(self):
        self.root=Path(self.enterContext(TemporaryDirectory()))/"profiles"
        self.policy={"schema":"ace.web.account-separation.v1","source_ref":"fixture/policy",
                     "accounts":[{"ref":key,"origin":f"http://127.0.0.1:{port}","namespace":"scope_"+key,
                                  "owner_ref":"fixture/"+key} for key,port in (("alpha",9008),("beta",9010))]}
        self.sha=identity(self.policy)

    def test_account_is_bound_to_its_own_origin(self):
        report=multi_account_guard.initialize(self.root,self.policy,self.sha)
        self.assertEqual(report["status"],"isolated_markers")
        target=multi_account_guard.permit(self.root,self.policy,self.sha,"alpha","http://127.0.0.1:9008")
        self.assertEqual(target["namespace"],"scope_alpha")
        self.assertEqual(multi_account_guard.permit(self.root,self.policy,self.sha,"alpha","http://127.0.0.1:9010")["status"],"held")

    def test_swapped_marker_and_symlink_profile_are_held(self):
        multi_account_guard.initialize(self.root,self.policy,self.sha)
        left,right=(self.root/f"scope_{key}" for key in ("alpha","beta"))
        (right/"scope.json").write_bytes((left/"scope.json").read_bytes())
        result=multi_account_guard.inspect(self.root,self.policy,self.sha)
        self.assertEqual(result["profiles"][1]["reason"],"profile_marker_mismatch_or_race")
        (right/"scope.json").unlink()
        right.rmdir()
        right.symlink_to(left,target_is_directory=True)
        self.assertEqual(multi_account_guard.inspect(self.root,self.policy,self.sha)["profiles"][1]["reason"],"profile_not_isolated")
