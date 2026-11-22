"""Verifier append idempoten, perubahan log, dan anchor tail eksternal."""
import unittest

from ace_software_factory import auditlog_builder as model
from ace_software_factory._contracts import ContractError, identity


def event(key,status,when="2026-01-01T12:00:00Z"):
    return {"id":key,"at":when,"actor_ref":"operator","operation":"read_report",
            "target_ref":"item","status":status,"evidence_ref":"receipt"}


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.policy={"schema":"ace.factory-audit-policy.v1","id":"fixture_product","source_ref":"fixture/contract",
                     "operations":[{"id":"read_report","source_ref":"fixture/read"}]}
        self.anchor=identity(self.policy)

    def build(self):
        return model.extend(b"",self.policy,self.anchor,model.GENESIS,[event("a","allowed"),event("b","denied")])

    def test_appends_without_rewriting_existing_lines_and_counts_denials(self):
        before,summary=self.build()
        next_event=event("c","failed","2026-01-01T12:00:01Z")
        after,result=model.extend(before,self.policy,self.anchor,summary["tail_sha256"],[event("a","allowed"),next_event])
        self.assertTrue(after.startswith(before))
        self.assertEqual(result["events"],3)
        self.assertEqual(result["by_status"],{"allowed":1,"denied":1,"failed":1})
        self.assertEqual(len(after.splitlines()),3)

    def test_tamper_truncation_and_conflicting_replay_are_rejected(self):
        log,summary=self.build()
        tail=summary["tail_sha256"]
        with self.assertRaisesRegex(ContractError,"baris 1"):
            model.verify(log.replace(b'"allowed"',b'"denied"',1),self.policy,self.anchor,tail)
        with self.assertRaisesRegex(ContractError,"Tail"):
            model.verify(log.splitlines(keepends=True)[0],self.policy,self.anchor,tail)
        with self.assertRaisesRegex(ContractError,"berbeda"):
            model.extend(log,self.policy,self.anchor,tail,[event("a","denied")])

    def test_late_event_without_clock_provenance_is_rejected(self):
        log,summary=self.build()
        with self.assertRaisesRegex(ContractError,"mundur"):
            model.extend(log,self.policy,self.anchor,summary["tail_sha256"],[event("x","failed","2026-01-01T00:00:00Z")])
