"""Acceptance tests for the cognitive-memory write path (v1).

Implements the five acceptance tests named in the design
(handover/MEMORY_WRITE_PATH_DESIGN_20261115.md §6), plus
the read-loop closure and the evolution-verifier wiring.
All stores are temporary; the live store is never touched.
"""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from ace_operational.cognitive_memory import (
    CognitiveMemory,
    ProvenanceError,
    _digest,
)
from ace_operational.memory_writeback import (
    recall_context,
    record_event_outcomes,
    record_verified_event,
)

EVIDENCE = b'{"receipt_id": "rcpt_test_1", "skill_id": "parse_positive"}'


def _records(root) -> list[dict]:
    return list(CognitiveMemory(root)._records.values())


class WritePathAcceptanceTests(unittest.TestCase):
    def test_1_skill_verified_writes_one_procedural_record(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "mem"
            rid = record_verified_event(
                root, event="skill_verified",
                summary="Skill parse_positive verified (rcpt_test_1)",
                evidence_bytes=EVIDENCE)
            self.assertIsNotNone(rid)
            records = _records(root)
            self.assertEqual(len(records), 1)
            rec = records[0]
            self.assertEqual(rec["id"], rid)
            self.assertEqual(rec["kind"], "procedural")
            self.assertEqual(rec["source"]["kind"], "evidence")
            self.assertEqual(rec["source"]["ref"], _digest(EVIDENCE))
            self.assertEqual(rec["confidence"], 0.90)
            self.assertEqual(rec["content"]["class"], "skill_verified")

    def test_2_replay_is_idempotent(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "mem"
            kwargs = dict(event="verdict_sealed",
                          summary="GUARD_ADOPTED (act 60fc25e1)",
                          evidence_bytes=b"act-bytes")
            rid1 = record_verified_event(root, **kwargs)
            log_after_first = (root / "memory.jsonl").read_bytes()
            rid2 = record_verified_event(root, **kwargs)
            self.assertEqual(rid1, rid2)
            self.assertEqual(len(_records(root)), 1)
            self.assertEqual((root / "memory.jsonl").read_bytes(),
                             log_after_first)

    def test_3_newer_semantic_verdict_supersedes(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "mem"
            extra = {"subject": "lineage_guard", "predicate": "status"}
            rid_old = record_verified_event(
                root, event="verdict_sealed", summary="guard adopted",
                evidence_bytes=b"v1", content_extra={**extra, "object": "adopted"})
            rid_new = record_verified_event(
                root, event="verdict_sealed", summary="guard revoked",
                evidence_bytes=b"v2", content_extra={**extra, "object": "revoked"})
            by_id = {r["id"]: r for r in _records(root)}
            self.assertEqual(by_id[rid_old]["status"], "superseded")
            self.assertEqual(by_id[rid_new]["status"], "active")
            audit = CognitiveMemory(root).audit()
            self.assertEqual(audit["superseded_records"], 1)
            self.assertTrue(audit["chain_ok"])

    def test_4_unanchored_evidence_write_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "mem"
            memory = CognitiveMemory(root)
            with self.assertRaises(ProvenanceError):
                memory.remember(
                    kind="episodic", content={"event": "forged"},
                    source_kind="evidence", source_ref="ab" * 32)
            self.assertEqual(len(_records(root)), 0)
            with self.assertRaises(ValueError):
                record_verified_event(
                    root, event="not_a_class", summary="x",
                    evidence_bytes=b"y")

    def test_5_seed_records_survive_and_chain_audits(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "mem"
            memory = CognitiveMemory(root)
            seed_ids = {
                memory.remember(
                    kind="episodic",
                    content={"event": "bahasa utama komunikasi kita"},
                    source_kind="operator", confidence=0.95),
                memory.remember(
                    kind="episodic",
                    content={"event": "pengguna memakai ACE di Termux"},
                    source_kind="operator", confidence=0.95),
            }
            for event, summary in [
                ("skill_verified", "skill x verified"),
                ("verdict_sealed", "verdict y sealed"),
                ("mission_ratified", "mission z ratified"),
                ("finding_high_opened", "HIGH finding opened: f1"),
                ("finding_high_closed", "HIGH finding closed: f1"),
            ]:
                rid = record_verified_event(
                    root, event=event, summary=summary,
                    evidence_bytes=summary.encode())
                self.assertIsNotNone(rid, msg=event)
            audit = CognitiveMemory(root).audit()
            self.assertTrue(audit["chain_ok"])
            self.assertEqual(audit["active_records"], 7)
            active_ids = {r["id"] for r in _records(root)
                          if r["status"] == "active"}
            self.assertTrue(seed_ids <= active_ids)

    def test_6_read_loop_outcomes_attach_to_procedural(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "mem"
            record_verified_event(
                root, event="skill_verified",
                summary="Skill parse_positive verified (rcpt_test_1)",
                evidence_bytes=EVIDENCE)
            record_verified_event(
                root, event="mission_ratified",
                summary="Mission m1 ratified", evidence_bytes=b"spore")
            recalled = recall_context(root, "parse_positive")
            self.assertEqual(len(recalled), 1)
            self.assertEqual(recalled[0]["kind"], "procedural")
            recorded = record_event_outcomes(
                root, recalled, context="repair_cycle_1", success=True)
            self.assertEqual(recorded, 1)
            rec = _records(root)[0] if _records(root)[0]["kind"] == "procedural" else _records(root)[1]
            self.assertEqual(rec["outcomes"]["repair_cycle_1"],
                             {"success": 1, "fail": 0})
            # Episodic records are context only: outcomes skip them.
            episodic = recall_context(root, "Mission m1 ratified")
            self.assertEqual(record_event_outcomes(
                root, episodic, context="repair_cycle_1", success=True), 0)


class VerifierWiringTests(unittest.TestCase):
    def test_ratification_writes_episodic_record(self):
        from ace_operational.evolution_mission_loop import (
            EvolutionPatchVerifier,
            PassiveEvolutionPlanner,
        )
        from ace_operational.test_evolution_mission_loop import (
            _create_sandbox_repo,
        )

        initial_target = (
            "def parse_positive(raw: str) -> int:\n"
            "    try:\n"
            "        val = int(raw)\n"
            "        return max(0, val)\n"
            "    except Exception:\n"
            "        pass\n"
            "    return 0\n"
        )
        initial_test = (
            "import unittest\n"
            "from ace_operational.target_mod import parse_positive\n\n"
            "class TargetTests(unittest.TestCase):\n"
            "    def test_parse(self) -> None:\n"
            "        self.assertEqual(parse_positive('5'), 5)\n"
            "        self.assertEqual(parse_positive('bad'), 0)\n"
        )
        with tempfile.TemporaryDirectory(prefix="ace_memwrite_") as d:
            base = Path(d)
            repo, ws = base / "repo", base / "ws"
            mem_root = base / "memory"
            _create_sandbox_repo(repo, target_src=initial_target,
                                 test_src=initial_test)
            planner = PassiveEvolutionPlanner(
                ws, repo, scan_subpath="code/ace_operational")
            plan = planner.plan_next_evolution(
                test_modules=["ace_operational.test_target_mod"])
            self.assertEqual(plan["status"], "MISSION_EMITTED")
            fixed = initial_target.replace(
                "    except Exception:\n        pass\n",
                "    except ValueError:\n        return 0\n")
            (repo / "code" / "ace_operational" / "target_mod.py").write_text(
                fixed, encoding="utf-8")
            res = EvolutionPatchVerifier(
                ws, repo, memory_root=mem_root).verify_and_ratify_evolution()
            self.assertTrue(res["accepted"], msg=str(res))
            writeback = res["memory_writeback"]
            self.assertEqual(writeback["recalled"], 0)
            self.assertIsNotNone(writeback["record_id"])
            records = _records(mem_root)
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["kind"], "episodic")
            self.assertEqual(records[0]["content"]["class"],
                             "mission_ratified")
            self.assertEqual(records[0]["source"]["kind"], "evidence")


class AuditProbeClassTests(unittest.TestCase):
    """EVO 0004 Blok B: the dedicated write-path audit probe
    class is registered, round-trips, replays idempotently,
    and the fail-closed boundary for unregistered classes is
    unchanged."""

    def test_probe_class_registered_with_episodic_mapping(self):
        from ace_operational.memory_writeback import EVENT_CLASSES
        self.assertEqual(EVENT_CLASSES["writepath_audit_probe"],
                         ("episodic", 0.90))

    def test_probe_write_read_back_and_replay(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "mem"
            rid = record_verified_event(
                root, event="writepath_audit_probe",
                summary="writepath audit probe (test)",
                evidence_bytes=EVIDENCE,
                content_extra={"probe": "test"})
            self.assertIsNotNone(rid)
            again = record_verified_event(
                root, event="writepath_audit_probe",
                summary="writepath audit probe (test)",
                evidence_bytes=EVIDENCE,
                content_extra={"probe": "test"})
            self.assertEqual(again, rid)
            records = _records(root)
            self.assertEqual(len(records), 1)
            rec = records[0]
            self.assertEqual(rec["id"], rid)
            self.assertEqual(rec["kind"], "episodic")
            self.assertEqual(rec["content"]["class"],
                             "writepath_audit_probe")
            self.assertEqual(rec["source"]["ref"], _digest(EVIDENCE))

    def test_unregistered_class_still_raises(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                record_verified_event(
                    Path(d) / "mem",
                    event="evo0003_blast_b4_probe",
                    summary="the B4 probe class stays unregistered",
                    evidence_bytes=EVIDENCE)


if __name__ == "__main__":
    unittest.main()


class PatternDistilledClassTests(unittest.TestCase):
    """EVO 0007 preregistration S9.1: the pattern_distilled
    class is registered as semantic, round-trips with its
    pattern fields, and replays idempotently."""

    PATTERN = {"task_shape": "code:fix failing parser test",
               "approach": "read the failing assertion first",
               "pitfalls": ["patching the test instead of the code"],
               "source_episode": "w2-code-003"}

    def test_pattern_class_registered_semantic(self):
        from ace_operational.memory_writeback import EVENT_CLASSES
        self.assertEqual(EVENT_CLASSES["pattern_distilled"],
                         ("semantic", 0.90))

    def test_pattern_write_read_back_and_replay(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "mem"
            rid = record_verified_event(
                root, event="pattern_distilled",
                summary="pattern distilled from w2-code-003",
                evidence_bytes=EVIDENCE,
                content_extra=dict(self.PATTERN))
            self.assertIsNotNone(rid)
            again = record_verified_event(
                root, event="pattern_distilled",
                summary="pattern distilled from w2-code-003",
                evidence_bytes=EVIDENCE,
                content_extra=dict(self.PATTERN))
            self.assertEqual(again, rid)
            records = _records(root)
            self.assertEqual(len(records), 1)
            rec = records[0]
            self.assertEqual(rec["id"], rid)
            self.assertEqual(rec["kind"], "semantic")
            self.assertEqual(rec["content"]["class"],
                             "pattern_distilled")
            self.assertEqual(rec["content"]["task_shape"],
                             self.PATTERN["task_shape"])
            self.assertEqual(rec["content"]["pitfalls"],
                             self.PATTERN["pitfalls"])
            self.assertEqual(rec["content"]["source_episode"],
                             "w2-code-003")
            self.assertEqual(rec["source"]["ref"], _digest(EVIDENCE))
