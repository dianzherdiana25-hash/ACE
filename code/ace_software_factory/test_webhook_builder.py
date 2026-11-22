"""Verifier request yang ditandatangani, usia, replay dan perubahan byte."""
from pathlib import Path
import secrets
from tempfile import TemporaryDirectory
import unittest

from ace_software_factory import webhook_builder as model
from ace_software_factory._contracts import identity


class WebhookTests(unittest.TestCase):
    def setUp(self):
        self.path=Path(self.enterContext(TemporaryDirectory()))/"replay.sqlite"
        model.receiver_database(self.path)
        self.key=secrets.token_bytes(32)
        self.policy={"schema":"ace.factory-webhook-policy.v1","id":"fixture_product","source_ref":"fixture/policy",
                     "ttl_seconds":60,"max_clock_lead":3,"max_bytes":256,
                     "topics":[{"id":"listed","source_ref":"fixture/topic"}]}
        self.sha=identity(self.policy)
        self.data={"id":"event_one","topic":"listed","payload":{"count":4}}

    def emit(self,at=100):
        return model.prepare(self.policy,self.sha,self.data,at,self.key)

    def receive(self,body,headers,now):
        return model.accept(self.policy,self.sha,body,headers,now,self.key,self.path)

    def test_outbound_bytes_authenticate_once_and_conflict_is_detected(self):
        first=self.emit()
        record=self.receive(*first,101)
        self.assertEqual(record["payload"],{"count":4})
        self.assertEqual(record["topic_ref"],"fixture/topic")
        self.assertEqual(self.receive(*first,102)["reason"],"replay")
        self.data["payload"]["count"]=5
        self.assertEqual(self.receive(*self.emit(102),103)["reason"],"event_identity_conflict")

    def test_wrong_bytes_or_window_fail_before_replay_ledger_changes(self):
        body,headers=self.emit()
        self.assertEqual(self.receive(body+b" ",headers,102)["reason"],"signature_mismatch")
        self.assertEqual(self.receive(body,headers,160)["reason"],"timestamp_outside_window")
        self.assertEqual(self.receive(*self.emit(106),100)["reason"],"timestamp_outside_window")
        self.assertEqual(self.receive(body,headers,103)["status"],"accepted")
