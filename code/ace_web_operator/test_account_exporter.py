"""Verifier projection, scope pemilik, dan grant yang kedaluwarsa."""
from hashlib import sha256
import unittest

from ace_web_operator import account_exporter
from ace_web_operator._contracts import ContractError,decode,identity


class AccountTests(unittest.TestCase):
    def setUp(self):
        self.data={"schema":"ace.web.owner-snapshot.v1","account":"sample","source_ref":"fixture/profile","kind":"activity",
                   "records":[{"id":"record","source_ref":"fixture/first",
                               "values":{"public_alias":"Fixture","activity_count":3,"secret_marker":"fixture-only"}}]}
        self.auth={"schema":"ace.web.self-export-authorization.v1","source_ref":"fixture/owner",
                   "scope":"own_account_export","account":"sample","snapshot_sha256":identity(self.data),
                   "expires_at":"2026-01-02T00:00:00Z","fields":["public_alias","activity_count"]}
        self.plan={"schema":"ace.web.account-export-plan.v1","source_ref":"fixture/order","account":"sample",
                   "snapshot_sha256":identity(self.data),"grant_sha256":identity(self.auth),"at":"2026-01-01T00:00:00Z"}

    def run_export(self):
        self.plan["grant_sha256"]=identity(self.auth)
        return account_exporter.export(self.plan,identity(self.plan),self.auth,self.data)

    def test_exports_only_granted_safe_fields_and_matches_artifact_hash(self):
        output,report=self.run_export()
        self.assertNotIn(b"fixture-only",output)
        self.assertEqual(decode(output)["records"][0]["values"],{"public_alias":"Fixture","activity_count":3})
        self.assertEqual(report["omitted_fields"],1)
        self.assertEqual(report["export_sha256"],sha256(output).hexdigest())

    def test_refuses_expired_cross_account_or_sensitive_scope(self):
        self.plan["at"]=self.auth["expires_at"]
        with self.assertRaisesRegex(ContractError,"Grant"):
            self.run_export()
        self.plan["at"]="2026-01-01T00:00:00Z"
        self.plan["account"]="other"
        with self.assertRaisesRegex(ContractError,"Grant"):
            self.run_export()
        self.plan["account"]="sample"
        self.auth["fields"].append("secret_marker")
        with self.assertRaisesRegex(ContractError,"Field"):
            self.run_export()
