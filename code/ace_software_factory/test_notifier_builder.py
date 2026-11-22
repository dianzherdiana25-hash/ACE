"""Verifier pesan lokal, placeholder ketat, dan penanganan duplikat."""
from hashlib import sha256
import unittest

from ace_software_factory import notifier_builder
from ace_software_factory._contracts import ContractError, decode, identity


class Notifications(unittest.TestCase):
    def setUp(self):
        self.templates = {"schema": "ace.factory-notifier.v1", "source_ref": "fixture/spec", "max_message_bytes": 1000,
                          "templates": [{"id": "stock", "channel": "email_draft", "fields": ["item"],
                                         "subject": "Stok {item}", "body": "Barang {item}\nAda pembaruan.",
                                         "source_ref": "fixture/stock"}]}
        self.row = {"id": "message_1", "template": "stock", "recipient_ref": "stock_owner",
                    "values": {"item": "Pupuk"}, "source_ref": "fixture/command"}
        self.requests = {"schema": "ace.factory-notifier-requests.v1", "templates_sha256": identity(self.templates),
                         "requests": [self.row]}

    def build(self):
        self.requests["templates_sha256"] = identity(self.templates)
        return notifier_builder.prepare(self.templates, self.requests, self.requests["templates_sha256"])

    def test_renders_local_drafts_once_with_content_hash(self):
        self.requests["requests"].append({**self.row})
        files, report = self.build()
        path = "messages/message_1.json"
        result = decode(files[path])
        self.assertEqual(result["subject"], "Stok Pupuk")
        self.assertEqual(result["body"], "Barang Pupuk\nAda pembaruan.")
        self.assertEqual(result["status"], "draft")
        self.assertEqual(report["drafts"], [{"path": path, "sha256": sha256(files[path]).hexdigest()}])
        self.assertEqual(report["identical_replays"], ["message_1"])

    def test_rejects_injected_header_and_unregistered_placeholder(self):
        self.row["values"]["item"] = "barang\nnext header"
        with self.assertRaises(ContractError):
            self.build()
        self.row["values"]["item"] = "barang"
        self.templates["templates"][0]["body"] = "{item.__class__}"
        with self.assertRaisesRegex(ContractError, "placeholder"):
            self.build()

    def test_different_payload_cannot_reuse_message_id(self):
        self.requests["requests"].append({**self.row, "values": {"item": "Ember"}})
        with self.assertRaisesRegex(ContractError, "berbeda"):
            self.build()
