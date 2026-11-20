"""Uji penerusan yang dapat diputar ulang dan deadline berbasis siklus."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_deliberation import async_deliberation as asynchronous
from ace_deliberation.test_debate_protocol import fixture as debate_fixture


def fixture():
    debate = debate_fixture()
    return {"plan": debate["plan"], "first_cycle": 4, "wait_cycles": 4, "as_of_cycle": 9,
            "events": [{"round": 1, "turn": turn, "arrived_cycle": cycle}
                       for turn, cycle in zip(debate["turns"], (8, 6, 9))]}


class AsyncTests(unittest.TestCase):
    def test_buffered_objection_waits_for_argument_then_remains_traceable(self):
        report = asynchronous.replay(fixture())
        self.assertEqual(report["state"], "ready_for_decision")
        self.assertEqual([row["turn_id"] for row in report["debate"]["turns"]], ["a1", "b1", "c1"])
        first, second, _ = report["receipts"]
        self.assertEqual((first["arrived_cycle"], first["processed_cycle"]), (8, 8))
        self.assertEqual((second["arrived_cycle"], second["processed_cycle"]), (6, 8))
        self.assertTrue(asynchronous.verify(report))

    def test_resume_reproduces_single_run_without_eating_buffer(self):
        raw = fixture()
        prefix = asynchronous.replay({**raw, "as_of_cycle": 7, "events": [raw["events"][1]]})
        self.assertEqual(prefix["queued_turn_ids"], ["b1"])
        self.assertEqual(prefix["next_deadline_cycle"], 8)
        self.assertEqual(asynchronous.resume(prefix, through_cycle=9, incoming=[raw["events"][0], raw["events"][2]]),
                         asynchronous.replay(raw))
        self.assertEqual(prefix["queued_turn_ids"], ["b1"])

    def test_invalid_ready_attempt_does_not_reset_wait_or_block_correction(self):
        raw = fixture()
        first = raw["events"][0]
        bad = {**first, "arrived_cycle": 5, "turn": {**first["turn"], "turn_id": "wrong", "targets": ["missing"]}}
        result = asynchronous.replay({**raw, "events": [bad, *raw["events"]]})
        self.assertEqual(result["receipts"][0]["status"], "protocol_refused")
        self.assertEqual(result["state"], "ready_for_decision")
        self.assertNotIn("wrong", [row["turn_id"] for row in result["debate"]["turns"]])

    def test_late_first_turn_cannot_restore_expired_session(self):
        raw = fixture()
        raw["events"][0]["arrived_cycle"] = 9
        result = asynchronous.replay(raw)
        self.assertEqual(result["state"], "expired")
        self.assertEqual(result["debate"]["turns"], [])
        self.assertIn("deadline_exceeded", [row["status"] for row in result["receipts"]])

    def test_historical_rewrite_and_checkpoint_tamper_are_rejected(self):
        raw = fixture()
        report = asynchronous.replay(raw)
        self.assertTrue(asynchronous.verify(report))
        with self.assertRaises(asynchronous.AsyncError):
            asynchronous.resume(report, through_cycle=11, incoming=[raw["events"][0]])
        report["state"] = "waiting"
        with self.assertRaisesRegex(asynchronous.AsyncError, "replay"):
            asynchronous.resume(report, through_cycle=11, incoming=[])

    def test_same_cycle_receipts_are_canonical_and_duplicate_slots_remain_traceable(self):
        raw = fixture()
        source = raw["events"][1]
        raw["events"].append({**source, "turn": {**source["turn"], "turn_id": "other"}})
        report = asynchronous.replay(raw)
        self.assertEqual(report, asynchronous.replay({**raw, "events": raw["events"][::-1]}))
        duplicate = next(row for row in report["receipts"] if row["turn_id"] == "other")
        self.assertEqual(duplicate["status"], "slot_already_used")

    def test_cli_resumes_from_saved_checkpoint(self):
        raw = fixture()
        root = Path(self.enterContext(TemporaryDirectory()))
        previous = root / "checkpoint.json"
        previous.write_text(json.dumps(asynchronous.replay({**raw, "as_of_cycle": 4, "events": []})), encoding="utf-8")
        incoming = root / "incoming.json"
        incoming.write_text(json.dumps({"through_cycle": 9, "incoming": raw["events"]}), encoding="utf-8")
        with redirect_stdout(StringIO()) as output:
            self.assertEqual(asynchronous.main([str(incoming), "--resume", str(previous)]), 0)
        self.assertEqual(json.loads(output.getvalue()), asynchronous.replay(raw))

    def test_no_events_stops_after_deadline_inclusive(self):
        raw = {**fixture(), "events": []}
        active = asynchronous.replay({**raw, "as_of_cycle": 8})
        self.assertEqual(active["state"], "waiting")
        later = asynchronous.resume(active, through_cycle=9, incoming=[])
        self.assertEqual(later["state"], "expired")
        self.assertIsNone(later["next_deadline_cycle"])

    def test_two_rounds_with_out_of_order_future_round_buffered(self):
        raw = fixture()
        raw["plan"].update(rounds=2, budget=30)
        second = []
        for item in raw["events"]:
            turn = dict(item["turn"])
            turn["turn_id"] += "-r2"
            second.append({"round": 2, "turn": turn, "arrived_cycle": 7})
        raw["events"].extend(second)
        report = asynchronous.replay(raw)
        self.assertEqual([entry["turn_id"] for entry in report["debate"]["turns"]],
                         ["a1", "b1", "c1", "a1-r2", "b1-r2", "c1-r2"])
        self.assertEqual([row["processed_cycle"] for row in report["receipts"] if row["round"] == 2], [9, 9, 9])

    def test_invalid_catalog_turn_and_duplicate_record_are_refused_before_export(self):
        raw = fixture()
        with self.assertRaisesRegex(asynchronous.AsyncError, "Turn ganda"):
            asynchronous.replay({**raw, "events": [*raw["events"], raw["events"][0]]})
        raw["events"][0]["turn"]["participant"] = "unknown"
        with self.assertRaises(asynchronous.AsyncError):
            asynchronous.replay(raw)

    def test_checkpoint_roundtrip_canonically_normalizes_protocol_defaults(self):
        raw = fixture()
        first = asynchronous.replay(raw)
        version = json.loads(json.dumps(first, ensure_ascii=False))
        self.assertTrue(asynchronous.verify(version))
        self.assertEqual(asynchronous.resume(version, through_cycle=9, incoming=[]), first)
