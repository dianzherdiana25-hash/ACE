"""Verifier email local-only, FIFO MIME, dan batas header/draf."""
from email import policy
from email.parser import BytesParser
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_software_factory import mail_queue_builder as model
from ace_software_factory._contracts import ContractError,identity


class MailTests(unittest.TestCase):
    def setUp(self):
        self.plan={"schema":"ace.factory-mail-policy.v1","id":"inbox","source_ref":"fixture/mail",
                   "sender":"sender@sample.invalid","recipients":[{"ref":"desk","address":"desk@sink.invalid"}],
                   "limit":2,"max_bytes":2500,"template_sha256":"a"*64}
        self.anchor=identity(self.plan)
        self.path=Path(self.enterContext(TemporaryDirectory()))/"queue.sqlite"
        model.initialize(self.path,self.plan,self.anchor)

    def submit(self,key,subject="Catatan bulan"):
        message={"schema":"ace.factory-notification-draft.v1","id":key,
                 "channel":"email_draft","recipient_ref":"desk","subject":subject,"body":"Kafe dan alat.\n",
                 "template":"just_local","template_ref":"fixture/template","request_sha256":"b"*64,
                 "request_ref":"fixture/request","status":"draft"}
        return model.enqueue(self.path,self.plan,self.anchor,message,"a"*64,100)

    def test_fifo_replay_mime_integrity_without_send(self):
        self.submit("first")
        self.assertTrue(self.submit("first")["duplicate"])
        self.submit("second")
        receipt=model.draft_next(self.path,self.plan,self.anchor)
        self.assertEqual(receipt["id"],"first")
        data=model.read_draft(self.path,self.anchor,"first")
        parsed=BytesParser(policy=policy.default).parsebytes(data)
        self.assertEqual(parsed["To"],"desk@sink.invalid")
        self.assertEqual(parsed["Subject"],"Catatan bulan")
        self.assertEqual(model.draft_next(self.path,self.plan,self.anchor)["id"],"second")
        self.assertEqual(model.draft_next(self.path,self.plan,self.anchor),{"status":"empty"})

    def test_header_controls_and_off_fixture_destination_are_rejected(self):
        with self.assertRaises(ContractError):
            self.submit("first","Bad\r\nX-Test: appended")
        self.plan["recipients"][0]["address"]="desk@example.com"
        with self.assertRaisesRegex(ContractError,"invalid"):
            model._policy(self.plan,identity(self.plan))
