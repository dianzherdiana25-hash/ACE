"""Uji transisi agresif, hysteresis, ambang waktu dan kegagalan masukan."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_deliberation import signal_watcher as watcher


def observation(number, stamp, value, identifier="test"):
    return {"id": identifier, "at": f"2026-11-20T00:{stamp}Z", "value": value, "source_ref": f"fixture/data/{number}"}


def fixture():
    return {"as_of": "2026-11-20T00:00:46Z", "rules": [
        {"id": "test", "direction": "above", "enter": "2.5", "exit": "2",
         "consecutive": 2, "max_age_seconds": 10, "rule_ref": "fixture/rule"}
    ], "observations": [
        observation(1, "00:00", "2.5"), observation(2, "00:05", "2.5"),
        observation(3, "00:09", "2.3"), observation(4, "00:19", "2"),
        observation(5, "00:24", "2.5"), observation(6, "00:36", "2.5"), observation(7, "00:46", "2.5"),
    ]}


class SignalTests(unittest.TestCase):
    def test_hysteresis_clear_and_broken_streak(self):
        row, = watcher.watch(fixture())["signals"]
        self.assertEqual(row["status"], "active")
        self.assertEqual([event["kind"] for event in row["transitions"]], ["activated", "cleared", "activated"])
        self.assertEqual(row["transitions"][0]["observation_refs"], ["fixture/data/1", "fixture/data/2"])
        self.assertEqual(row["transitions"][-1]["observation_refs"], ["fixture/data/6", "fixture/data/7"])

    def test_active_gap_emits_stale_then_requires_new_sustained_observations(self):
        raw = fixture()
        raw["observations"].pop(3)
        raw["observations"].pop()
        raw["as_of"] = "2026-11-20T00:00:36Z"
        row, = watcher.watch(raw)["signals"]
        self.assertEqual([event["kind"] for event in row["transitions"]], ["activated", "stale"])
        self.assertEqual(row["status"], "clear")
        self.assertEqual(row["consecutive_pending"], 1)
        self.assertEqual(row["transitions"][1]["observation_refs"], ["fixture/data/3"])
        self.assertEqual(row["transitions"][1]["at"], "2026-11-20T00:00:19+00:00")

    def test_stale_boundary_is_inclusive_and_unobserved_signal_does_not_fabricate_measurements(self):
        raw = fixture()
        raw["as_of"] = "2026-11-20T00:00:56Z"
        self.assertEqual(watcher.watch(raw)["signals"][0]["status"], "active")
        raw["as_of"] = "2026-11-20T00:00:57Z"
        self.assertEqual(watcher.watch(raw)["signals"][0]["status"], "stale")
        raw["observations"] = []
        report = watcher.watch(raw)["signals"][0]
        self.assertEqual(report["status"], "unobserved")
        self.assertIsNone(report["last_observation"])

    def test_below_direction_reverses_both_boundaries(self):
        raw = fixture()
        raw["rules"][0].update(direction="below", enter="-2", exit="-1")
        raw["observations"] = [observation(1, "00:01", -2), observation(2, "00:02", -3),
                               observation(3, "00:03", "-1")]
        raw["as_of"] = "2026-11-20T00:00:03Z"
        self.assertEqual([item["kind"] for item in watcher.watch(raw)["signals"][0]["transitions"]],
                         ["activated", "cleared"])

    def test_rejects_duplicate_instants_future_and_nonpositive_hysteresis(self):
        raw = fixture()
        cases = [fixture()["observations"] + [observation(8, "00:46", 0)],
                 fixture()["observations"] + [observation(8, "00:47", 0)]]
        for observations in cases:
            with self.subTest(observations=observations), self.assertRaises(watcher.SignalError):
                watcher.watch({**raw, "observations": observations})
        raw["rules"][0]["exit"] = raw["rules"][0]["enter"]
        with self.assertRaisesRegex(watcher.SignalError, "hysteresis"):
            watcher.watch(raw)

    def test_normalized_time_and_source_ordering_are_deterministic(self):
        raw = fixture()
        expected = watcher.watch(raw)
        raw["observations"].reverse()
        path = Path(self.enterContext(TemporaryDirectory())) / "signal.json"
        path.write_text(json.dumps(raw), encoding="utf-8")
        with redirect_stdout(StringIO()) as output:
            self.assertEqual(watcher.main([str(path)]), 0)
        self.assertEqual(json.loads(output.getvalue()), expected)

    def test_current_activation_provenance_stops_when_freshness_is_lost(self):
        raw = fixture()
        raw["as_of"] = "2026-11-20T00:00:46.000123Z"
        report = watcher.watch(raw)
        self.assertEqual(report["active_ids"], ["test"])
        current, = report["signals"]
        self.assertEqual(current["observation_age_microseconds"], 123)
        self.assertEqual(current["current_activation"]["observation_refs"], ["fixture/data/6", "fixture/data/7"])
        raw["as_of"] = "2026-11-20T00:00:57Z"
        stale = watcher.watch(raw)
        self.assertEqual(stale["active_ids"], [])
        self.assertEqual(stale["stale_ids"], ["test"])
        self.assertIsNone(stale["signals"][0]["current_activation"])

    def test_second_signal_does_not_inherit_streak_from_first(self):
        raw = fixture()
        second = {**raw["rules"][0], "id": "other", "rule_ref": "fixture/other"}
        raw["rules"].append(second)
        raw["observations"].append(observation(10, "00:46", "2.7", identifier="other"))
        other, first = watcher.watch(raw)["signals"]
        self.assertEqual(other["consecutive_pending"], 1)
        self.assertEqual(other["transitions"], [])
        self.assertEqual(first["status"], "active")

    def test_expired_partial_sequence_has_no_pending_samples(self):
        raw = fixture()
        raw["observations"] = raw["observations"][:1]
        result = watcher.watch(raw)["signals"][0]
        self.assertEqual(result["status"], "stale")
        self.assertEqual(result["consecutive_pending"], 0)
        self.assertEqual(result["transitions"], [])
