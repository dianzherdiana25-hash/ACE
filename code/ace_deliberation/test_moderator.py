"""Uji intervensi waktu, agenda, dan giliran dari transcript fixture."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_deliberation import moderator
from ace_deliberation.test_debate_protocol import fixture as debate_fixture


def fixture():
    debate = debate_fixture()
    return {"plan": debate["plan"], "rules": {
        "agendas": ["reliability", "methods"], "turn_ms": 10, "total_ms": 35, "open_at_ms": 5,
    }, "events": [
        {"kind": "utterance", "event_id": f"e{index}", "at_ms": 5 + 8 * index,
         "agenda_refs": ["reliability" if index < 3 else "methods"], "message": move}
        for index, move in enumerate(debate["turns"], 1)
    ] + [{"kind": "close", "event_id": "end", "at_ms": 32, "decision": debate["decision"]}]}


class ModeratorTests(unittest.TestCase):
    def test_all_turns_then_decision_cover_both_topics(self):
        raw = fixture()
        result = moderator.moderate(raw)
        self.assertEqual(result["phase"], "closed")
        self.assertEqual(result["agenda_covered"], ["methods", "reliability"])
        self.assertEqual(result["agenda_uncovered"], [])
        self.assertEqual([row["reason"] for row in result["interventions"]],
                         ["turn_recorded"] * 3 + ["decision_recorded"])
        self.assertEqual(result["debrief"]["decision"], raw["events"][-1]["decision"])
        self.assertEqual(result, moderator.moderate(raw))

    def test_wrong_turn_and_off_agenda_do_not_advance_the_session(self):
        raw = fixture()
        session = moderator.Moderator(raw["plan"], raw["rules"])
        first = raw["events"][0]
        wrong = {**raw["events"][1], "event_id": "wrong", "at_ms": 7}
        self.assertEqual(session.offer(wrong)["reason"], "turn_refused")
        off_topic = {**first, "event_id": "off", "at_ms": 8, "agenda_refs": ["reliability", "random"]}
        self.assertEqual(session.offer(off_topic)["reason"], "outside_agenda")
        self.assertEqual(session.report()["effective_deadline_ms"], 15)
        self.assertEqual(session.report()["agenda_covered"], [])
        self.assertEqual(session.offer(first)["reason"], "turn_recorded")

    def test_deadline_is_inclusive_then_expires_without_any_late_decision(self):
        raw = fixture()
        session = moderator.Moderator(raw["plan"], raw["rules"])
        self.assertEqual(session.offer({"kind": "tick", "event_id": "t0", "at_ms": 15})["reason"],
                         "within_deadline")
        event = {**raw["events"][0], "at_ms": 16}
        self.assertEqual(session.offer(event)["reason"], "deadline_exceeded")
        report = session.report()
        self.assertEqual(report["phase"], "expired")
        self.assertEqual(report["debrief"]["turns"], [])
        self.assertEqual(session.offer(raw["events"][-1])["reason"], "session_terminal")

    def test_global_deadline_blocks_close_even_after_final_turn(self):
        raw = fixture()
        raw["rules"]["total_ms"] = 25
        report = moderator.moderate(raw)
        self.assertEqual(len(report["debrief"]["turns"]), 3)
        self.assertIsNone(report["debrief"]["decision"])
        self.assertEqual(report["interventions"][-1]["reason"], "deadline_exceeded")

    def test_early_close_is_retained_as_intervention_then_recovery_is_possible(self):
        raw = fixture()
        close = {**raw["events"][-1], "event_id": "early", "at_ms": 6}
        result = moderator.moderate({**raw, "events": [close, *raw["events"]]})
        self.assertEqual(result["interventions"][0]["reason"], "decision_refused")
        self.assertEqual(result["phase"], "closed")

    def test_time_rewind_and_duplicate_event_are_refused(self):
        raw = fixture()
        session = moderator.Moderator(raw["plan"], raw["rules"])
        session.offer(raw["events"][0])
        for event in (raw["events"][0], {**raw["events"][1], "at_ms": 6}):
            with self.subTest(event=event), self.assertRaises(moderator.ModerationError):
                session.offer(event)
        self.assertEqual(len(session.report()["interventions"]), 1)

    def test_report_and_receipt_exports_do_not_alias_expected_turn(self):
        raw = fixture()
        session = moderator.Moderator(raw["plan"], raw["rules"])
        result = session.offer(raw["events"][0])
        result["expected_turn"].clear()
        result["agenda_refs"].clear()
        saved = session.report()
        self.assertEqual(saved["interventions"][0]["expected_turn"]["participant"], "a")
        self.assertEqual(saved["interventions"][0]["agenda_refs"], ["reliability"])

    def test_cli_expires_with_nonzero_and_produces_complete_audit(self):
        raw = fixture()
        raw["events"] = [{"kind": "tick", "event_id": "late", "at_ms": 40}]
        path = Path(self.enterContext(TemporaryDirectory())) / "moderation.json"
        path.write_text(json.dumps(raw), encoding="utf-8")
        with redirect_stdout(StringIO()) as output:
            self.assertEqual(moderator.main([str(path)]), 1)
        self.assertEqual(json.loads(output.getvalue())["phase"], "expired")

    def test_required_agenda_uncovered_prevents_decision_after_last_turn(self):
        raw = fixture()
        raw["rules"]["required_agendas"] = ["methods"]
        raw["events"][2]["agenda_refs"] = ["reliability"]
        report = moderator.moderate(raw)
        self.assertEqual(report["interventions"][-1]["reason"], "required_agenda_uncovered")
        self.assertEqual(report["required_agenda_uncovered"], ["methods"])
        self.assertIsNone(report["debrief"]["decision"])

    def test_unknown_required_agenda_is_not_accepted_as_a_gate(self):
        raw = fixture()
        raw["rules"]["required_agendas"] = ["unknown"]
        with self.assertRaisesRegex(moderator.ModerationError, "Agenda wajib"):
            moderator.moderate(raw)

    def test_terminal_close_cannot_be_replayed_under_new_event_id(self):
        raw = fixture()
        close_again = {**raw["events"][-1], "event_id": "repeat"}
        result = moderator.moderate({**raw, "events": [*raw["events"], close_again]})
        self.assertEqual(result["interventions"][-1]["reason"], "session_terminal")
        self.assertEqual(result["debrief"]["decision"], close_again["decision"])
