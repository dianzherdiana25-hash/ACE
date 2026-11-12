"""OMEGA-07 tests for Persistent Cognitive Memory.

The test list follows the OMEGA-07 line of the execution programme:
cross-restart task recall, false-memory injection, stale semantic
knowledge, negative transfer detection, privacy and contamination
controls — plus conflict, retention and forgetting discipline.
"""
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from ace_operational.cognitive_memory import (
    CognitiveMemory,
    ContaminationError,
    NotFoundError,
    ProvenanceError,
)

EVIDENCE = b"sealed evaluator log: threshold check failed at exactly 500000"


def make_memory(test: unittest.TestCase, **kwargs) -> CognitiveMemory:
    temp = tempfile.TemporaryDirectory(prefix="ace-mem-")
    test.addCleanup(temp.cleanup)
    return CognitiveMemory(Path(temp.name) / "memory", **kwargs)


class RecallTests(unittest.TestCase):
    def test_cross_restart_task_recall(self):
        temp = tempfile.TemporaryDirectory(prefix="ace-mem-")
        self.addCleanup(temp.cleanup)
        root = Path(temp.name) / "memory"
        first = CognitiveMemory(root)
        digest = first.anchor_evidence(EVIDENCE)
        first.remember(
            kind="episodic",
            content={"task": "perbaiki harga", "outcome": "attempt 2 fixed VAT only"},
            source_kind="evidence", source_ref=digest, confidence=0.9)
        # A brand-new instance on the same directory = a process restart.
        second = CognitiveMemory(root)
        found = second.recall("perbaiki harga VAT")
        self.assertEqual(found["returned"], 1)
        self.assertEqual(found["results"][0]["content"]["outcome"],
                         "attempt 2 fixed VAT only")
        self.assertTrue(second.audit()["chain_ok"])

    def test_kinds_are_recallable_separately(self):
        mem = make_memory(self)
        mem.remember(kind="episodic", content={"task": "t", "what": "ran tests"},
                     source_kind="operator")
        mem.remember(kind="procedural",
                     content={"name": "run tests", "steps": ["unittest"]},
                     source_kind="operator")
        only_proc = mem.recall("tests", kinds=["procedural"])
        self.assertEqual(only_proc["returned"], 1)
        self.assertEqual(only_proc["results"][0]["kind"], "procedural")

    def test_bounded_retrieval_reports_truncation(self):
        mem = make_memory(self)
        for i in range(6):
            mem.remember(kind="episodic",
                         content={"task": "harga", "note": f"entry {i}"},
                         source_kind="operator")
        limited = mem.recall("harga", limit=2)
        self.assertEqual(limited["returned"], 2)
        self.assertTrue(limited["truncated"])
        starved = mem.recall("harga", token_budget=1)
        self.assertEqual(starved["returned"], 0)
        self.assertTrue(starved["truncated"])


class ProvenanceTests(unittest.TestCase):
    def test_evidence_source_requires_anchor(self):
        mem = make_memory(self)
        with self.assertRaises(ProvenanceError):
            mem.remember(kind="semantic",
                         content={"subject": "harga", "predicate": "threshold",
                                  "object": ">=500000"},
                         source_kind="evidence", source_ref="f" * 64)

    def test_model_guess_is_labeled_and_ranks_below_evidence(self):
        mem = make_memory(self)
        digest = mem.anchor_evidence(EVIDENCE)
        mem.remember(kind="episodic", content={"task": "harga threshold result"},
                     source_kind="model", confidence=0.9)
        mem.remember(kind="episodic", content={"task": "harga threshold result"},
                     source_kind="evidence", source_ref=digest, confidence=0.4)
        found = mem.recall("harga threshold result")
        self.assertEqual(found["results"][0]["source"]["kind"], "evidence")
        self.assertFalse(found["results"][0]["guess"])
        self.assertTrue(found["results"][1]["guess"])


class ConflictTests(unittest.TestCase):
    def setUp(self):
        self.mem = make_memory(self)
        self.digest = self.mem.anchor_evidence(EVIDENCE)

    def fact(self, obj, **kw):
        args = dict(kind="semantic",
                    content={"subject": "harga", "predicate": "threshold",
                             "object": obj},
                    source_kind="evidence", source_ref=self.digest,
                    confidence=0.9)
        args.update(kw)
        return self.mem.remember(**args)

    def test_false_memory_injection_cannot_displace_evidence(self):
        truth = self.fact(">=500000")
        self.mem.remember(
            kind="semantic",
            content={"subject": "harga", "predicate": "threshold",
                     "object": ">500000"},
            source_kind="model", confidence=1.0)  # confident guess, still a guess
        found = self.mem.recall("harga threshold")
        active = [r for r in found["results"] if r["status"] == "active"]
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0]["id"], truth)
        audit = self.mem.audit()
        self.assertEqual(audit["superseded_records"], 1)

    def test_newer_evidence_supersedes_older(self):
        old = self.fact(">500000")
        new = self.fact(">=500000")
        found = self.mem.recall("harga threshold")
        self.assertEqual([r["id"] for r in found["results"]], [new])
        with_old = self.mem.recall("harga threshold", include_superseded=True)
        ids = {r["id"]: r["status"] for r in with_old["results"]}
        self.assertEqual(ids[old], "superseded")
        self.assertEqual(ids[new], "active")

    def test_stale_semantic_knowledge_is_flagged(self):
        rid = self.mem.remember(
            kind="semantic",
            content={"subject": "llama.cpp", "predicate": "flag for kv cache",
                     "object": "--kv-type-k"},
            source_kind="operator", confidence=0.8, valid_until_seq=2)
        self.mem.remember(kind="episodic", content={"task": "unrelated work"},
                          source_kind="operator")
        found = self.mem.recall("llama.cpp kv cache flag")
        self.assertEqual(found["results"][0]["id"], rid)
        self.assertTrue(found["results"][0]["stale"])


class RetentionTests(unittest.TestCase):
    def test_expired_records_leave_recall_but_stay_in_audit(self):
        mem = make_memory(self)
        rid = mem.remember(kind="episodic", content={"task": "harga sementara"},
                           source_kind="operator", expires_after_events=1)
        mem.remember(kind="episodic", content={"task": "masak nasi"},
                     source_kind="operator")
        found = mem.recall("harga sementara")
        self.assertEqual(found["returned"], 0)
        self.assertIn(rid, mem.audit()["expired_record_ids"])

    def test_forgetting_destroys_content_and_leaves_a_tombstone(self):
        mem = make_memory(self)
        rid = mem.remember(
            kind="episodic",
            content={"task": "harga", "secret_note": "kode-rahasia-123"},
            source_kind="operator", sensitivity="private")
        mem.forget(rid, reason="mengandung catatan pribadi")
        self.assertEqual(mem.recall("harga", include_private=True)["returned"], 0)
        raw = mem.log_path.read_text(encoding="utf-8")
        self.assertNotIn("kode-rahasia-123", raw)
        tombstones = mem.audit()["tombstones"]
        self.assertEqual(len(tombstones), 1)
        self.assertEqual(tombstones[0]["reason"], "mengandung catatan pribadi")
        self.assertTrue(mem.audit()["chain_ok"])
        with self.assertRaises(NotFoundError):
            mem.forget(rid, reason="lagi")


class PrivacyAndContaminationTests(unittest.TestCase):
    def test_private_records_need_explicit_flag(self):
        mem = make_memory(self)
        mem.remember(kind="episodic", content={"task": "harga pribadi"},
                     source_kind="operator", sensitivity="private")
        self.assertEqual(mem.recall("harga pribadi")["returned"], 0)
        self.assertEqual(
            mem.recall("harga pribadi", include_private=True)["returned"], 1)

    def test_canary_content_is_rejected(self):
        mem = make_memory(self, canary_tokens=["CANARY-9z"])
        with self.assertRaises(ContaminationError):
            mem.remember(kind="episodic",
                         content={"task": "harga", "leak": "CANARY-9z"},
                         source_kind="operator")

    def test_tampered_log_breaks_the_chain(self):
        mem = make_memory(self)
        mem.remember(kind="episodic", content={"task": "harga"},
                     source_kind="operator")
        text = mem.log_path.read_text(encoding="utf-8")
        mem.log_path.write_text(text.replace("harga", "hargaX"),
                                encoding="utf-8")
        reopened = CognitiveMemory(mem.root)
        self.assertFalse(reopened.audit()["chain_ok"])


class NegativeTransferTests(unittest.TestCase):
    def test_procedure_failing_in_context_is_flagged_and_demoted(self):
        mem = make_memory(self)
        risky = mem.remember(
            kind="procedural",
            content={"name": "patch harga", "steps": ["edit", "test"]},
            source_kind="operator", confidence=0.9)
        safe = mem.remember(
            kind="procedural",
            content={"name": "patch harga", "steps": ["read README", "edit", "test"]},
            source_kind="operator", confidence=0.5)
        mem.record_outcome(risky, context="repo-asing", success=True)
        mem.record_outcome(risky, context="repo-asing", success=True)
        for _ in range(3):
            mem.record_outcome(risky, context="fixture-harga", success=False)
        mem.record_outcome(safe, context="fixture-harga", success=True)
        found = mem.recall("patch harga", kinds=["procedural"],
                           context="fixture-harga")
        by_id = {r["id"]: r for r in found["results"]}
        self.assertTrue(by_id[risky]["negative_transfer_risk"])
        self.assertFalse(by_id[safe]["negative_transfer_risk"])


if __name__ == "__main__":
    unittest.main()
