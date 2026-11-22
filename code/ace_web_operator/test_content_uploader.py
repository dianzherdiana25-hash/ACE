"""Verifier aset lokal, jadwal, dan tidak menimpa berkas sumber."""
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_web_operator import content_uploader
from ace_web_operator._contracts import ContractError,decode,identity


class DraftTests(unittest.TestCase):
    def setUp(self):
        self.root=Path(self.enterContext(TemporaryDirectory()))
        self.payload=b"Test content for draft"
        (self.root/"content.txt").write_bytes(self.payload)
        self.plan={"schema":"ace.web.upload-draft-plan.v1","id":"demo","source_ref":"fixture/upload","channel":"owned_channel",
                   "channel_ref":"fixture/channel","intent":"draft","as_of":"2026-01-01T00:00:00Z",
                   "scheduled_at":"2026-01-02T00:00:00Z","title":"Judul","description":"Bahan draft.",
                   "assets":[{"id":"body","path":"content.txt","source_ref":"fixture/body","mime":"text/plain",
                              "sha256":sha256(self.payload).hexdigest(),"bytes":len(self.payload)}]}

    def produce(self):
        return content_uploader.prepare(self.root,self.plan,identity(self.plan))

    def test_local_draft_has_bound_assets_and_explicit_pending_operator(self):
        files,proof=self.produce()
        self.assertEqual(files["assets/body.txt"],self.payload)
        self.assertEqual(decode(files["upload_draft.json"])["status"],"awaiting_operator")
        self.assertFalse(proof["published"])
        self.assertEqual(sorted(p.name for p in self.root.iterdir()),["content.txt"])

    def test_tampered_asset_and_publish_intent_hold(self):
        (self.root/"content.txt").write_bytes(self.payload[:-1]+b"x")
        with self.assertRaisesRegex(ContractError,"SHA-256"):
            self.produce()
        self.plan["intent"]="publish"
        with self.assertRaisesRegex(ContractError,"intent"):
            self.produce()
