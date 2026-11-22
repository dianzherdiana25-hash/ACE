"""Verifier tenggat, prioritas, serta penggunaan RAM per slot."""
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from io import StringIO
import json
from pathlib import Path
from random import Random
from tempfile import TemporaryDirectory
import unittest

from ace_forge import forge_scheduler as model
from ace_forge._forge_io import canonical, identity


START = datetime(2026, 11, 21, tzinfo=timezone.utc)


def stamp(index):
    return (START + timedelta(minutes=15 * index)).isoformat()


def window(name, first, last, ram):
    return {"source_ref": f"fixture/window/{name}", "start": stamp(first), "end": stamp(last), "ram_mib": ram}


def job(name, first, last, duration, ram, priority):
    return {"id": name, "source_ref": f"fixture/job/{name}", "earliest": stamp(first), "deadline": stamp(last),
            "duration_slots": duration, "ram_mib": ram, "priority": priority}


def fixture():
    return {"calendar_ref": "fixture/calendar", "start": stamp(0), "end": stamp(8), "slot_minutes": 15,
            "reserve_mib": 2, "windows": [window("first", 0, 4, 10), window("last", 5, 8, 8)],
            "jobs": [job("heavy", 0, 4, 3, 6, 5), job("light", 0, 4, 2, 2, 4),
                     job("last", 4, 8, 2, 6, 3), job("reserve-block", 0, 3, 2, 3, 2),
                     job("gap", 3, 6, 3, 1, 1), job("short", 0, 1, 2, 1, 0)]}


def schedule(plan):
    return model.schedule(plan, identity(plan))


class SchedulerTests(unittest.TestCase):
    def test_earliest_contiguous_fit_enforces_memory_and_gaps(self):
        result = schedule(fixture())
        self.assertEqual(result["status"], "partial")
        self.assertEqual([(row["id"], row["start"], row["end"]) for row in result["planned"]], [
            ("heavy", stamp(0), stamp(3)), ("light", stamp(0), stamp(2)), ("last", stamp(5), stamp(7)),
        ])
        self.assertEqual({row["id"]: row["reason"] for row in result["held"]}, {
            "reserve-block": "capacity_reserved", "gap": "no_ram_window", "short": "duration_exceeds_window",
        })
        self.assertEqual(result["windows"][0]["peak_scheduled_ram_mib"], 8)
        self.assertEqual(result["windows"][0]["minimum_free_mib"], 0)
        self.assertEqual(result["windows"][1]["source_ref"], "fixture/window/last")
        self.assertEqual(result["planned"][0]["source_ref"], "fixture/job/heavy")

    def test_deadline_then_duration_then_id_break_priority_ties(self):
        raw = fixture()
        raw["jobs"] = [job("z", 0, 4, 2, 8, 5), job("b", 0, 3, 1, 8, 5),
                       job("a", 0, 3, 1, 8, 5), job("earlier", 0, 2, 1, 8, 5)]
        self.assertEqual([row["id"] for row in schedule(raw)["planned"]], ["earlier", "a", "b"])
        self.assertEqual(schedule(raw)["held"][0]["id"], "z")

    def test_touching_windows_can_host_contiguous_job_without_overallocating(self):
        raw = {**fixture(), "windows": [window("low", 0, 2, 4), window("high", 2, 5, 10)],
               "jobs": [job("spanning", 0, 5, 4, 2, 1)]}
        report = schedule(raw)
        self.assertEqual(report["planned"][0]["end"], stamp(4))
        self.assertEqual([row["peak_scheduled_ram_mib"] for row in report["windows"]], [2, 2])

    def test_sampled_schedules_respect_independent_slot_accounting_oracle(self):
        rng = Random(29)
        for _ in range(20):
            raw = fixture()
            raw["jobs"] = [job(f"j{i}", 0, 8, rng.randint(1, 4), rng.randint(1, 9), rng.randint(1, 9))
                           for i in range(10)]
            result = schedule(raw)
            observed = [0] * 8
            for row in result["planned"]:
                first = (datetime.fromisoformat(row["start"]) - START) // timedelta(minutes=15)
                last = (datetime.fromisoformat(row["end"]) - START) // timedelta(minutes=15)
                self.assertEqual(last - first, row["duration_slots"])
                for index in range(first, last):
                    observed[index] += row["ram_mib"]
            self.assertTrue(all(spent <= cap for spent, cap in zip(observed, [8] * 4 + [0] + [6] * 3)))

    def test_off_slot_or_overlapping_calendar_and_bad_timestamps_fail(self):
        for change in ({"windows": [window("one", 0, 3, 5), window("two", 2, 4, 5)]},
                       {"end": "2026-11-21T02:00:01+00:00"}, {"start": "2026-11-21T00:00:00"},
                       {"windows": [window("none", 0, 0, 1)]}, {"slot_minutes": True}):
            with self.subTest(change=change), self.assertRaises(model.InputError):
                schedule({**fixture(), **change})

    def test_larger_reserve_blocks_even_though_a_window_is_registered(self):
        report = schedule({**fixture(), "reserve_mib": 12})
        self.assertEqual(report["planned"], [])
        self.assertEqual(report["windows"][0]["usable_ram_mib"], 0)
        self.assertIn("no_ram_window", {row["reason"] for row in report["held"]})

    def test_policy_anchor_and_duplicate_ids_are_checked_before_scheduling(self):
        raw = fixture()
        anchor = identity(raw)
        raw["jobs"].append(raw["jobs"][0])
        with self.assertRaisesRegex(model.InputError, "anchor"):
            model.schedule(raw, anchor)
        with self.assertRaisesRegex(model.InputError, "ganda"):
            schedule(raw)

    def test_empty_schedule_and_outside_horizon_are_reported_honestly(self):
        raw = {**fixture(), "windows": [], "jobs": []}
        self.assertEqual(schedule(raw)["status"], "scheduled")
        raw["jobs"] = [job("cannot-start", 0, 2, 1, 1, 1)]
        self.assertEqual(schedule(raw)["held"][0]["reason"], "no_ram_window")
        raw["jobs"][0]["deadline"] = stamp(12)
        with self.assertRaisesRegex(model.InputError, "horizon"):
            schedule(raw)

    def test_cli_preserves_anchored_input_and_reports_partial_status(self):
        raw = fixture()
        path = Path(self.enterContext(TemporaryDirectory())) / "calendar.json"
        path.write_bytes(canonical(raw))
        with redirect_stdout(StringIO()) as out:
            self.assertEqual(model.main([str(path), "--expect-input-sha256", identity(raw)]), 1)
        self.assertEqual(json.loads(out.getvalue()), schedule(raw))
        self.assertEqual(path.read_bytes(), canonical(raw))

    def test_full_schedule_no_overwrite_and_exact_boundaries_with_zone_offset(self):
        raw = fixture()
        raw["jobs"] = [job("boundary", 0, 4, 4, 8, 2)]
        raw["jobs"][0]["earliest"] = "2026-11-21T07:00:00+07:00"
        result = schedule(raw)
        self.assertEqual(result["status"], "scheduled")
        self.assertEqual(result["planned"][0]["start"], stamp(0))
        self.assertEqual(result["planned"][0]["end"], stamp(4))

    def test_greedy_assignment_matches_contiguous_scan_under_competing_priorities(self):
        raw = fixture()
        jobs = [job("long", 0, 8, 3, 7, 1), job("short", 0, 4, 2, 7, 1), job("priority", 1, 8, 2, 2, 7)]
        raw["jobs"] = jobs
        room = [8] * 4 + [0] + [6] * 3
        expected = {}
        for work in sorted(jobs, key=lambda row: (-row["priority"], row["deadline"], row["duration_slots"], row["id"])):
            begin, stop = ((datetime.fromisoformat(work[field]) - START) // timedelta(minutes=15)
                           for field in ("earliest", "deadline"))
            duration, capacity = work["duration_slots"], work["ram_mib"]
            locations = [first for first in range(begin, stop - duration + 1)
                         if min(room[first:first + duration]) >= capacity]
            if locations:
                first = locations[0]
                expected[work["id"]] = stamp(first)
                for i in range(first, first + duration):
                    room[i] -= capacity
        self.assertEqual({row["id"]: row["start"] for row in schedule(raw)["planned"]}, expected)

    def test_input_window_and_job_array_permutations_preserve_allocation(self):
        raw = fixture()
        first = schedule(raw)
        raw["jobs"].reverse()
        raw["windows"].reverse()
        after = schedule(raw)
        self.assertNotEqual(first.pop("input_sha256"), after.pop("input_sha256"))
        self.assertEqual(first, after)
