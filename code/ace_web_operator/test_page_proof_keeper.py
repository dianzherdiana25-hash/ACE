"""Verifier pembekuan bukti dan perubahan byte setelah capture."""
from hashlib import sha256
import unittest

from ace_web_operator import page_proof_keeper
from ace_web_operator._contracts import ContractError,identity


class ProofTests(unittest.TestCase):
    def setUp(self):
        self.html=b"<section><h1>Bukti fixture</h1></section>"
        self.plan={"schema":"ace.web.proof-plan.v1","site_id":"fixture","origin":"http://127.0.0.1:9010",
                   "path":"/proof","captured_at":"2026-01-01T00:00:01Z","status":200,
                   "source_ref":"fixture/log/1","permission_ref":"fixture/approved",
                   "html_sha256":sha256(self.html).hexdigest()}

    def test_manifest_and_artifact_match_independent_verifier(self):
        files,report=page_proof_keeper.preserve(self.html,self.plan,identity(self.plan))
        self.assertEqual(files[report["artifact"]],self.html)
        self.assertEqual(page_proof_keeper.verify(self.html,files["page_proof.json"],report["manifest_sha256"]),report)
        self.assertEqual(report["url"],"http://127.0.0.1:9010/proof")

    def test_refuses_altered_html_or_manifest(self):
        files,report=page_proof_keeper.preserve(self.html,self.plan,identity(self.plan))
        with self.assertRaisesRegex(ContractError,"HTML"):
            page_proof_keeper.verify(self.html+b" ",files["page_proof.json"],report["manifest_sha256"])
        with self.assertRaisesRegex(ContractError,"Manifest"):
            page_proof_keeper.verify(self.html,files["page_proof.json"]+b" ",report["manifest_sha256"])
