"""Verifier catatan terminal, provenance yang berulang, dan ekspor kanonis."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_forge import failure_archive as model
from ace_forge._forge_io import canonical, identity
from ace_forge.test_experiment_tracker import CHECKPOINT, event, fixture as ledger_fixture, plan


def tag(key, category, ref, diagnosis=None):
    return {"experiment_id": key, "category": category, "classification_ref": ref,
            "diagnosis_ref": diagnosis or f"test/diagnosis/{key}"}


def failed(key, sequence, checkpoint=False):
    planned = plan(key, 10)
    planned["values"]["recipe_sha256"] = "f"*64
    rows = [planned, event(key, "start", 1, {"runner_ref": f"test/runner/{key}"})]
    if checkpoint:
        rows.append(event(key, "checkpoint", 3, {"checkpoint_sha256": CHECKPOINT,
                                                  "checkpoint_ref": f"test/checkpoint/{key}", "spent_delta_units": 5}))
    rows.append(event(key, "fail", sequence, {"diagnosis_ref": f"test/diagnosis/{key}", "spent_delta_units": 4}))
    return rows


def refresh(snapshot):
    snapshot["ledger_sha256"] = identity(snapshot["ledger"])


def fixture():
    first = {"ledger": ledger_fixture(), "tags": [tag("two", "bounded_memory", "fixture/classify/two", "fixture/failed")]}
    second = {"ledger": ledger_fixture(), "tags": [tag("three", "bounded_memory", "fixture/classify/three")]}
    second["ledger"]["events"] += failed("three", 20, checkpoint=True) + failed("four", 15)
    second["ledger"]["ledger_ref"] = "fixture/ledger/successor"
    for snapshot in (first, second):
        refresh(snapshot)
    return {"archive_ref": "fixture/archive", "snapshots": [first, second]}


def archive(raw):
    return model.archive(raw, identity(raw))


class ArchiveTests(unittest.TestCase):
    def test_terminal_failure_in_multiple_snapshots_counts_once(self):
        raw = fixture()
        result = archive(raw)
        self.assertEqual(result["failed"], 3)
        self.assertEqual(result["unclassified"], ["four"])
        self.assertEqual(result["classification_conflicts"], [])
        group, = result["categories"]
        self.assertEqual(group["experiment_ids"], ["two", "three"])
        self.assertEqual(group["distinct_recipe_count"], 2)
        self.assertEqual(group["count"], 2)
        two, four, three = result["failures"]
        self.assertEqual([row["ledger_ref"] for row in two["sources"]], ["fixture/ledger", "fixture/ledger/successor"])
        self.assertEqual([row["line"] for row in two["sources"]], [8, 8])
        self.assertEqual(two["failure"]["spent_units"], 4)
        self.assertTrue(two["failure"]["over_budget"])
        self.assertIsNone(four["failure"]["last_checkpoint"])
        self.assertEqual(three["failure"]["last_checkpoint"]["checkpoint_sha256"], CHECKPOINT)

    def test_conflicting_categories_reported_without_counting_in_either_group(self):
        raw = fixture()
        second = raw["snapshots"][1]
        second["tags"].append(tag("two", "resource_budget", "fixture/alternative", "fixture/failed"))
        report = archive(raw)
        self.assertEqual(report["classification_conflicts"], ["two"])
        self.assertEqual(report["categories"][0]["experiment_ids"], ["three"])
        self.assertEqual(len(report["failures"][0]["tags"]), 2)

    def test_hash_anchors_payload_and_an_independent_archive_envelope(self):
        raw = fixture()
        report = archive(raw)
        for entry in report["failures"]:
            self.assertEqual(entry["failure_sha256"], identity(entry["failure"]))
            self.assertEqual(entry["archive_sha256"], identity({k: v for k, v in entry.items() if k != "archive_sha256"}))
        swapped = {**raw, "snapshots": raw["snapshots"][::-1]}
        self.assertEqual(report["failures"], archive(swapped)["failures"])
        self.assertNotEqual(report["input_sha256"], archive(swapped)["input_sha256"])

    def test_modified_terminal_receipt_with_same_run_is_rejected(self):
        raw = fixture()
        second = raw["snapshots"][1]
        second["ledger"]["events"][7]["values"]["spent_delta_units"] += 1
        refresh(second)
        with self.assertRaisesRegex(model.InputError, "bertentangan"):
            archive(raw)

    def test_a_terminal_diagnosis_must_match_annotation(self):
        raw = fixture()
        raw["snapshots"][0]["tags"][0]["diagnosis_ref"] = "fixture/wrong"
        with self.assertRaisesRegex(model.InputError, "terminal"):
            archive(raw)

    def test_failed_classification_cannot_be_used_for_completed_run(self):
        raw = fixture()
        raw["snapshots"][0]["tags"] = [tag("one", "other", "fixture/classify/one", "fixture/result")]
        with self.assertRaisesRegex(model.InputError, "eksperimen gagal"):
            archive(raw)

    def test_duplicate_classification_pointer_can_only_restate_the_same_category(self):
        raw = fixture()
        second = raw["snapshots"][1]
        conflicting = {**raw["snapshots"][0]["tags"][0], "category": "source_fault"}
        second["tags"].append(conflicting)
        with self.assertRaisesRegex(model.InputError, "isi berbeda"):
            archive(raw)
        conflicting["category"] = "bounded_memory"
        self.assertEqual(len(archive(raw)["failures"][0]["tags"]), 1)

    def test_snapshot_and_archive_anchors_checked_independently(self):
        raw = fixture()
        previous = identity(raw)
        raw["snapshots"][1]["ledger"]["ledger_ref"] = "test/renamed"
        with self.assertRaisesRegex(model.InputError, "arsip"):
            model.archive(raw, previous)
        with self.assertRaisesRegex(model.InputError, "Snapshot"):
            archive(raw)

    def test_unfinished_runs_and_empty_ledger_add_no_failures(self):
        raw = fixture()
        raw["snapshots"].pop()
        snapshot = raw["snapshots"][0]
        snapshot["tags"] = []
        snapshot["ledger"]["events"] = snapshot["ledger"]["events"][:7]
        refresh(snapshot)
        self.assertEqual(archive(raw)["failed"], 0)
        raw["snapshots"].clear()
        self.assertEqual(archive(raw)["failures"], [])

    def test_jsonl_matches_json_archive_without_mutating_input(self):
        raw = fixture()
        path = Path(self.enterContext(TemporaryDirectory())) / "archive.json"
        path.write_bytes(canonical(raw))
        call = [str(path), "--expect-sha256", identity(raw)]
        with redirect_stdout(StringIO()) as out:
            self.assertEqual(model.main(call), 0)
        expected = json.loads(out.getvalue())
        self.assertEqual(expected, archive(raw))
        with redirect_stdout(StringIO()) as out:
            self.assertEqual(model.main([*call, "--format", "jsonl"]), 0)
        self.assertEqual([json.loads(row) for row in out.getvalue().splitlines()], expected["failures"])
        self.assertEqual(path.read_bytes(), canonical(raw))

    def test_jsonl_empty_plan_emits_no_records(self):
        raw = {**fixture(), "snapshots": []}
        path = Path(self.enterContext(TemporaryDirectory())) / "empty.json"
        path.write_bytes(canonical(raw))
        with redirect_stdout(StringIO()) as out:
            model.main([str(path), "--expect-sha256", identity(raw), "--format", "jsonl"])
        self.assertEqual(out.getvalue(), "")
        self.assertEqual(archive(raw)["categories"], [])

    def test_same_file_receipt_moved_to_another_line_traces_both_locations(self):
        raw = fixture()
        before, after = raw["snapshots"]
        after["ledger"]["events"].insert(0, plan("unrelated", 10))
        refresh(after)
        row = archive(raw)["failures"][0]
        self.assertEqual({source["line"] for source in row["sources"]}, {8, 9})
        self.assertEqual({source["ledger_sha256"] for source in row["sources"]},
                         {before["ledger_sha256"], after["ledger_sha256"]})
        self.assertEqual(row["failure_sha256"], identity(row["failure"]))
