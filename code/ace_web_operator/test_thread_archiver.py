"""Verifier reply chain dan redaksi sebelum byte archive diterbitkan."""
import unittest

from ace_web_operator import thread_archiver
from ace_web_operator._contracts import ContractError,decode,identity


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.snapshot={"schema":"ace.web.thread-snapshot.v1","id":"closed","source_ref":"fixture/thread","entries":[
            {"id":"first","parent":None,"actor":"writer_one","at":"2026-01-01T00:00:00Z",
             "text":"Hello writer_one with marker", "source_ref":"fixture/first"},
            {"id":"reply","parent":"first","actor":"writer_two","at":"2026-01-01T00:00:01Z",
             "text":"Reply for writer_one", "source_ref":"fixture/reply"}]}
        self.plan={"schema":"ace.web.thread-archive-plan.v1","thread":"closed","source_ref":"fixture/settings",
                   "permission_ref":"fixture/approved","consent":"archive_redacted","redact_terms":["marker"]}

    def pack(self):
        self.plan["snapshot_sha256"]=identity(self.snapshot)
        return thread_archiver.archive(self.snapshot,self.plan,identity(self.plan))

    def test_redacts_actor_and_term_before_building_verified_chain(self):
        data,proof=self.pack()
        self.assertNotIn(b"writer_one",data)
        self.assertNotIn(b"marker",data)
        first,second=decode(data)["entries"]
        self.assertEqual(second["parent_sha256"],first["sha256"])
        self.assertEqual(proof["redactions"],3)
        self.assertEqual(thread_archiver.verify(data,proof["archive_sha256"])["entries"],2)

    def test_dangling_reply_rejected_before_any_archive(self):
        self.snapshot["entries"][1]["parent"]="missing"
        with self.assertRaisesRegex(ContractError,"parent"):
            self.pack()
