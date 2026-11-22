from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._contracts import PresenceError, canonical
from ._journal import Journal
from .answer_length_adapter import adapt
from .appointment_maker import propose
from .confusion_detector import detect
from .decision_linker_presence import link
from .decision_marker import decisions
from .dialogue_note_taker import notes
from .promise_reminder import reminders
from .speech_preference_memory import preferences
from .summary_offerer import offer
from .test_dialogue_server import turn
from .test_rolling_summary import save
from .test_temporal_core import at, call
from .thread_resumer import resume

class ExtendedPresenceTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        journal = Journal(self.root / "talk.sqlite")
        for payload in [
            turn(message="Saya belum paham batasnya."),
            turn("first_answer", "assistant", "opening", "Keputusan: Batas ditetapkan setelah audit."),
            turn("decision", "user", "first_answer", "Putusan [approved] audit: Lanjutkan pemeriksaan."),
            turn("second_answer", "assistant", "decision", "Action: Kumpulkan bukti."),
        ]:
            journal.append(payload)
        self.doc = journal.export("fixture")
        self.ref = save(self.root, "talk.json", canonical(self.doc))

    def test_31_remember_only_self_authorized_and_expiry_does_not_revive_older_option(self):
        base = {"speaker": "subject", "author": "subject", "key": "tone", "value": "formal",
                "set_on": "2025-05-01", "expires_on": "2025-05-30", "source": "self"}
        plan = {"schema": "ace.presence.preferences.v1", "speaker": "subject", "as_of": "2025-05-11",
                "updates": [base, {**base, "key": "register", "author": "guest", "source": "injected"},
                            {**base, "set_on": "2025-05-05", "expires_on": "2025-05-10", "value": "casual"}]}
        self.assertEqual(call(preferences, plan)["preferences"], {})
        plan["as_of"] = "2025-05-07"
        self.assertEqual(call(preferences, plan)["preferences"]["tone"]["value"], "casual")

    def test_32_maximum_channel_safeguards_mandatory_text(self):
        plan = {"schema": "ace.presence.answer-length.v1", "max_chars": 12, "blocks": [
            {"id": key, "text": raw, "required": mandatory, "priority": rank, "source": key}
            for key, raw, mandatory, rank in [("lead", "Lapor", True, 1), ("large", "Over budget", False, 30),
                                             ("end", "Bukti.", False, 10)]]}
        self.assertEqual(call(adapt, plan)["answer"], "Lapor\nBukti.")
        plan["max_chars"] = 4
        self.assertEqual(call(adapt, plan)["status"], "requires_larger_channel")

    def test_33_confusion_preserves_phrase_and_source(self):
        plan = {"schema": "ace.presence.confusion.v1", "dialogue": self.ref}
        result = call(detect, plan, self.root)["detected"]
        self.assertEqual(result, [{"turn_id": "opening", "rule": "comprehension",
                                   "phrase": "Saya belum paham", "turn_sha256": self.doc["events"][0]["sha256"]}])

    def test_34_offer_cooldown_uses_hash_of_last_turn(self):
        plan = {"schema": "ace.presence.summary-offer.v1", "dialogue": self.ref, "last_offer_sha256": None,
                "turn_threshold": 3, "char_threshold": 20, "cooldown": 3}
        self.assertTrue(call(offer, plan, self.root)["offer"])
        plan["last_offer_sha256"] = self.doc["events"][1]["sha256"]
        self.assertFalse(call(offer, plan, self.root)["offer"])

    def test_35_only_proposes_common_appointment(self):
        plan = {"schema": "ace.presence.appointments.v1", "request_ref": "turn:a", "title": "Lab",
                "duration": 25, "earliest": at("09:00"), "people": [
                    {"id": key, "windows": [{"start": at(start), "end": at(end)}]}
                    for key, start, end in [("anna", "09:10", "10:30"), ("bo", "09:30", "10:00")]]}
        result = call(propose, plan)
        self.assertEqual((result["start"], result["end"]), (at("09:30"), at("09:55")))
        plan["duration"] = 31
        self.assertEqual(call(propose, plan)["status"], "no_common_slot")

    def test_36_reminder_is_idempotent_using_returned_receipt(self):
        plan = {"schema": "ace.presence.promise-reminders.v1", "as_of": "2025-05-01", "before_days": [0, 7],
                "promises": [{"id": "archive", "action": "Archive sample", "due_on": "2025-05-08",
                              "status": "open", "source": "turn:4"}], "emitted": []}
        result = call(reminders, plan)["reminders"]
        self.assertEqual(result[0]["days_before"], 7)
        plan["emitted"] = [result[0]["sha256"]]
        self.assertEqual(call(reminders, plan)["reminders"], [])

    def test_37_notes_include_only_permitted_marked_turns(self):
        plan = {"schema": "ace.presence.notes.v1", "dialogue": self.ref, "allowed_speakers": ["ace"]}
        result = call(notes, plan, self.root)
        self.assertEqual(result["decisions"][0]["text"], "Batas ditetapkan setelah audit.")
        self.assertEqual(result["actions"][0]["source_turn_sha256"], self.doc["events"][3]["sha256"])
        self.assertEqual(result["agenda"], [])

    def test_38_resume_checkpoints_page_and_rejects_different_history(self):
        plan = {"schema": "ace.presence.thread-resume.v1", "dialogue": self.ref,
                "after_sha256": self.doc["events"][1]["sha256"], "max_turns": 1}
        report = call(resume, plan, self.root)
        self.assertEqual(report["events"], self.doc["events"][2:3])
        self.assertEqual(report["remaining"], 1)
        plan["after_sha256"] = "f" * 64
        with self.assertRaises(PresenceError):
            call(resume, plan, self.root)

    def test_39_decision_attribution_filters_unauthorized_speaker(self):
        plan = {"schema": "ace.presence.decision-plan.v1", "dialogue": self.ref, "authorized_speakers": ["quoted"]}
        report = call(decisions, plan, self.root)
        self.assertEqual(report["decisions"][0]["status"], "approved")
        self.assertEqual(report["latest"]["audit"], self.doc["events"][2]["sha256"])
        plan["authorized_speakers"] = ["ace"]
        self.assertEqual(call(decisions, plan, self.root)["decisions"], [])

    def test_40_only_approved_decisions_link_to_open_commitments(self):
        plan = {"schema": "ace.presence.decision-links.v1",
                "decisions": [{"id": "audit", "status": "approved", "sha256": "a" * 64},
                              {"id": "hold", "status": "deferred", "sha256": "b" * 64}],
                "promises": [{"id": "check", "source": "journal:17"}], "links": [
                    {"decision": key, "promise": "check"} for key in ("audit", "hold")]}
        report = call(link, plan)
        self.assertEqual(report["links"], [{"decision": "audit", "promise": "check",
                                           "decision_sha256": "a" * 64, "promise_source": "journal:17"}])
        self.assertEqual(report["dangling"], [{"decision": "hold", "promise": "check"}])
