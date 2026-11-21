"""Verifier lifecycle, sumber checkpoint dan akuntansi receipt internal."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_forge import experiment_tracker as model
from ace_forge._forge_io import canonical, identity, utc_stamp


CHECKPOINT = "c" * 64


def event(key, kind, sequence, values, at=None):
    return {"id": key, "type": kind, "at": at or f"2026-11-21T00:{sequence:02}:00Z",
            "event_ref": f"fixture/event/{key}/{sequence}", "values": values}


def plan(key, budget, sequence=0):
    return event(key, "plan", sequence, {"plan_ref": f"fixture/plan/{key}", "recipe_sha256": "a" * 64,
                                        "dataset_sha256": "b" * 64, "budget_units": budget})


def fixture():
    return {"ledger_ref": "fixture/ledger", "events": [
        plan("one", 7),
        event("one", "start", 1, {"runner_ref": "fixture/runner/one"}),
        plan("two", 2),
        event("one", "checkpoint", 2, {"checkpoint_sha256": CHECKPOINT, "checkpoint_ref": "fixture/c1",
                                       "spent_delta_units": 5}),
        event("one", "pause", 3, {"reason_ref": "fixture/pause"}),
        event("two", "start", 1, {"runner_ref": "fixture/runner/two"}),
        event("one", "resume", 4, {"runner_ref": "fixture/runner/resume", "checkpoint_sha256": CHECKPOINT}),
        event("two", "fail", 5, {"diagnosis_ref": "fixture/failed", "spent_delta_units": 4}),
        event("one", "finish", 6, {"result_ref": "fixture/result", "spent_delta_units": 2}),
    ]}


def audit(raw):
    return model.audit(raw, identity(raw))


class TrackingTests(unittest.TestCase):
    def test_interleaved_experiments_keep_independent_transitions_and_usage(self):
        report = audit(fixture())
        self.assertEqual(report["events"], 9)
        self.assertEqual(report["by_state"], {"completed": 1, "failed": 1})
        self.assertEqual(report["total_budget_units"], 9)
        self.assertEqual(report["total_spent_units"], 11)
        self.assertEqual(report["over_budget_experiments"], ["two"])
        one, two = report["experiments"]
        self.assertEqual((one["attempts"], one["margin_units"]), (2, 0))
        self.assertEqual((two["attempts"], two["margin_units"]), (1, -2))
        self.assertEqual(one["checkpoints"], [{"checkpoint_ref": "fixture/c1",
                                              "checkpoint_sha256": CHECKPOINT, "spent_delta_units": 5}])
        self.assertEqual(one["events"][3]["event_ref"], "fixture/event/one/3")
        self.assertEqual(two["terminal_ref"], "fixture/failed")
        self.assertEqual(one["terminal_ref"], "fixture/result")
        self.assertEqual(one["recipe_sha256"], "a" * 64)

    def test_pause_before_first_checkpoint_can_resume_only_from_null(self):
        raw = {"ledger_ref": "fixture/ledger", "events": [
            plan("one", 0), event("one", "start", 1, {"runner_ref": "fixture/start"}),
            event("one", "pause", 2, {"reason_ref": "fixture/pause"}),
            event("one", "resume", 3, {"runner_ref": "fixture/resume", "checkpoint_sha256": None}),
        ]}
        result = audit(raw)["experiments"][0]
        self.assertEqual(result["status"], "running")
        self.assertEqual(result["attempts"], 2)
        raw["events"][-1]["values"]["checkpoint_sha256"] = CHECKPOINT
        with self.assertRaisesRegex(model.InputError, "Resume"):
            audit(raw)

    def test_source_order_is_checked_per_experiment_even_if_offsets_differ(self):
        raw = fixture()
        raw["events"][4]["at"] = "2026-11-21T07:02:00+07:00"
        self.assertEqual(audit(raw)["experiments"][0]["events"][3]["at"], "2026-11-21T00:02:00+00:00")
        raw["events"][4]["at"] = "2026-11-21T07:01:00+07:00"
        with self.assertRaisesRegex(model.InputError, "Event 5.*mundur"):
            audit(raw)

    def test_receipts_before_plan_after_finish_or_with_duplicate_refs_are_invalid(self):
        raw = fixture()
        invalid = (
            [raw["events"][1]], [*raw["events"], event("one", "start", 9, {"runner_ref": "fixture/again"})],
            [*raw["events"], plan("one", 10, 9)], [raw["events"][0], {**raw["events"][1], "event_ref": raw["events"][0]["event_ref"]}],
            [{**raw["events"][0], "at": "2026-11-21T00:00:00"}],
        )
        for events in invalid:
            with self.subTest(events=events), self.assertRaisesRegex(model.InputError, r"Event \d+"):
                audit({**raw, "events": events})

    def test_duplicate_checkpoint_hash_is_not_counted_twice(self):
        raw = fixture()
        duplicate = event("one", "checkpoint", 10, {"checkpoint_sha256": CHECKPOINT, "checkpoint_ref": "fixture/c2",
                                                     "spent_delta_units": 5}, at="2026-11-21T00:02:01Z")
        raw["events"].insert(4, duplicate)
        with self.assertRaisesRegex(model.InputError, "Checkpoint ganda"):
            audit(raw)

    def test_invalid_usage_ref_can_be_retried_without_partial_experiment_state(self):
        refs = set()
        start = utc_stamp("2026-11-21T00:00:00Z")
        item = model.Experiment.read("one", plan("one", 5)["values"], start, refs)
        item.apply("start", {"runner_ref": "fixture/start"}, start, refs)
        invalid = {"checkpoint_sha256": CHECKPOINT, "checkpoint_ref": "fixture/test", "spent_delta_units": -2}
        with self.assertRaises(model.InputError):
            item.apply("checkpoint", invalid, start, refs)
        self.assertEqual(item.charged, 0)
        self.assertNotIn("fixture/test", refs)
        item.apply("checkpoint", {**invalid, "spent_delta_units": 3}, start, refs)
        self.assertEqual(item.charged, 3)

    def test_anchor_must_match_complete_snapshot(self):
        raw = fixture()
        checksum = identity(raw)
        raw["events"].pop()
        with self.assertRaisesRegex(model.InputError, "anchor"):
            model.audit(raw, checksum)

    def test_empty_and_only_planned_runs_are_both_valid(self):
        raw = {"ledger_ref": "fixture/ledger", "events": []}
        self.assertEqual(audit(raw)["by_state"], {})
        raw["events"].append(plan("prepared", 0))
        result = audit(raw)
        self.assertEqual(result["by_state"], {"planned": 1})
        self.assertEqual(result["total_spent_units"], 0)

    def test_cli_matches_api_and_leaves_receipt_bytes_unchanged(self):
        raw = fixture()
        path = Path(self.enterContext(TemporaryDirectory())) / "ledger.json"
        path.write_bytes(canonical(raw))
        with redirect_stdout(StringIO()) as output:
            self.assertEqual(model.main([str(path), "--expect-sha256", identity(raw)]), 0)
        self.assertEqual(json.loads(output.getvalue()), audit(raw))
        self.assertEqual(path.read_bytes(), canonical(raw))
