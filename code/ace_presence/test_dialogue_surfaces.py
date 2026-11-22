from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._contracts import PresenceError, canonical, identity
from ._journal import Journal
from .bilingual_mirror import mirror
from .clarification_asker import ask
from .conversation_search import search
from .fact_corrector import corrections
from .group_dialogue import assemble
from .memory_writeback import prepare
from .owner_channel import route
from .promise_extractor import extract
from .session_handoff import issue, receive
from .test_dialogue_server import turn
from .test_rolling_summary import sample, save
from .topic_tracker import track

AT = "2025-05-01T10:04:00Z"
END = "2025-05-01T11:00:00Z"

class DialogSurfaceTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.ref, self.snapshot = sample(self.root)

    def test_06_interrupt_requires_pinned_request_and_is_prioritized(self):
        regular = {"id": "regular", "speaker": "guest", "priority": "normal",
                   "at": AT, "expires": END, "message": "Wait in queue."}
        special = {**regular, "id": "special", "speaker": "owner", "priority": "interrupt"}
        forged = {**special, "id": "forged", "message": "Unknown priority request."}
        plan = {"schema": "ace.presence.priority.v1", "now": AT,
                "grants": [identity(special)], "requests": [regular, forged, special]}
        result = route(plan, identity(plan))
        self.assertEqual([row["id"] for row in result["queue"]], ["special", "regular"])
        self.assertEqual(result["refused"], ["forged"])

    def test_07_topic_requires_quoted_source_for_each_transition(self):
        plan = {"schema": "ace.presence.topic-plan.v1", "dialogue": self.ref, "annotations": [
            {"topic": "sensor", "turn_id": "opening", "status": "open", "quote": "Kalibrasi panel"},
            {"topic": "sensor", "turn_id": "reply", "status": "resolved", "quote": "ada pada tabel"},
        ]}
        report = track(plan, identity(plan), self.root)
        trail = report["topics"]["sensor"]["trail"]
        self.assertEqual([row["status"] for row in trail], ["open", "resolved"])
        self.assertEqual(trail[-1]["sha256"], self.snapshot["events"][1]["sha256"])
        plan["annotations"][1]["quote"] = "bukti tidak ada"
        with self.assertRaises(PresenceError):
            track(plan, identity(plan), self.root)

    def test_08_group_attributes_and_rotates_through_pass(self):
        plan = {"schema": "ace.presence.group-plan.v1", "participants": [
            {"id": name, "consent": True} for name in ("ann", "bea", "cam")], "turns": [
            {"id": "first", "speaker": "ann", "at": AT, "act": "speak", "message": "Open."},
            {"id": "second", "speaker": "bea", "at": AT, "act": "pass", "message": ""},
            {"id": "third", "speaker": "cam", "at": AT, "act": "speak", "message": "Close."},
        ]}
        result = assemble(plan, identity(plan))
        self.assertEqual(result["next_speaker"], "ann")
        self.assertEqual(result["turns"][1]["previous_sha256"], result["turns"][0]["sha256"])
        plan["turns"][1]["speaker"] = "cam"
        with self.assertRaises(PresenceError):
            assemble(plan, identity(plan))

    def test_09_mirror_finds_supported_sentence_and_catches_changed_figures(self):
        pair = {"id": "Sampel 12 lulus.", "en": "Sample 12 passed."}
        plan = {"schema": "ace.presence.mirror-plan.v1",
                "parallel": save(self.root, "pairs.json", canonical([pair])),
                "glossary": [{"id": "sampel", "en": "sample"}], "from": "id",
                "segments": [pair["id"], "Segmen baru."]}
        result = mirror(plan, identity(plan), self.root)
        self.assertEqual(result["segments"], [{"index": 1, "translation": pair["en"], "source_line": 1}])
        self.assertEqual(result["unmatched"], [2])
        plan["parallel"] = save(self.root, "other.json", canonical([{**pair, "en": "Sample 13 passed."}]))
        with self.assertRaises(PresenceError):
            mirror(plan, identity(plan), self.root)

    def test_10_only_explicit_nonconditional_promises_extracted(self):
        journal = Journal(self.root / "promise.sqlite")
        journal.append(turn(message="Saya akan memeriksa panel pada 2025-05-02."))
        journal.append(turn("answer", "assistant", "opening", "Archive noted."))
        journal.append(turn("hedge", "user", "answer", "Saya akan mungkin kembali pada 2025-05-03."))
        snapshot = journal.export("fixture")
        plan = {"schema": "ace.presence.promises-plan.v1",
                "dialogue": save(self.root, "promises.json", canonical(snapshot))}
        result = extract(plan, identity(plan), self.root)["promises"]
        self.assertEqual([(row["id"], row["due_on"]) for row in result], [("opening", "2025-05-02")])
        self.assertEqual(result[0]["turn_sha256"], snapshot["events"][0]["sha256"])

    def test_11_correction_uses_authority_without_overwriting_history(self):
        plan = {"schema": "ace.presence.corrections-plan.v1", "dialogue": self.ref,
                "authority": save(self.root, "facts.json", canonical([{"key": "location", "value": "arsip"}])),
                "claims": [{"turn_id": "reply", "key": "location", "value": "tabel"}]}
        old = (self.root / self.ref["path"]).read_bytes()
        result = corrections(plan, identity(plan), self.root)["claims"][0]
        self.assertEqual((result["status"], result["expected"]), ("review_correction", "arsip"))
        self.assertEqual((self.root / self.ref["path"]).read_bytes(), old)

    def test_12_search_returns_exact_phrase_and_retains_permission_boundary(self):
        plan = {"schema": "ace.presence.search-plan.v1", "exports": [self.ref],
                "allowed_speakers": ["quoted"], "query": "kalibrasi panel", "limit": 2}
        result = search(plan, identity(plan), self.root)["hits"]
        self.assertEqual([hit["turn"] for hit in result], ["opening"])
        self.assertEqual(result[0]["turn_sha256"], self.snapshot["events"][0]["sha256"])

    def test_13_handoff_target_expiry_and_replay_check(self):
        plan = {"schema": "ace.presence.handoff-plan.v1", "dialogue": self.ref, "from": "desk",
                "to": "terminal", "issued_at": AT, "expires_at": END, "nonce": "b" * 64}
        package = issue(plan, identity(plan), self.root)
        case = (package["checkpoint"], package["sha256"])
        self.assertTrue(receive(*case, "terminal", AT, set()))
        self.assertFalse(receive(*case, "terminal", END, set()))
        self.assertFalse(receive(*case, "desk", AT, set()))
        self.assertFalse(receive(*case, "terminal", AT, {"b" * 64}))

    def test_14_clarification_prefers_high_cost_and_keeps_confirmed_values(self):
        rows = [{"id": key, "question": question, "required": True, "cost_if_wrong": priority, "candidates": candidates}
                for key, question, priority, candidates in (
                    ("format", "Which format?", 2, []),
                    ("zone", "Which zone?", 12, [{"value": "east", "source": "turn1"}, {"value": "west", "source": "turn2"}]),
                    ("size", "Which size?", 9, [{"value": "small", "source": "turn3"}]),
                )]
        plan = {"schema": "ace.presence.clarify-plan.v1", "slots": rows}
        result = ask(plan, identity(plan))
        self.assertEqual(result["resolved"]["size"]["value"], "small")
        self.assertEqual(result["clarify"], {"slot": "zone", "question": "Which zone?", "choices": ["east", "west"]})
        self.assertEqual(result["remaining"], ["zone", "format"])

    def test_15_verified_pointer_does_not_override_closed_write_set(self):
        evidence = save(self.root, "source.txt", b"Kalibrasi panel tersedia.")
        plan = {"schema": "ace.presence.writeback-plan.v1", "dialogue": self.ref,
                "facts": [{"id": "panel", "turn_id": "opening", "quote": "Kalibrasi panel", "evidence": evidence}]}
        before = sorted(self.root.iterdir())
        result = prepare(plan, identity(plan), self.root)
        self.assertEqual(result["reason"], "session_fact_event_class_not_registered")
        self.assertEqual(result["candidates"][0]["external"], evidence)
        self.assertEqual(sorted(self.root.iterdir()), before)
        bad = deepcopy(plan)
        bad["facts"][0]["evidence"] = self.ref
        with self.assertRaises(PresenceError):
            prepare(bad, identity(bad), self.root)
