"""Verifier distilasi dari fixture kustodi dan penahanan lesson ambigu."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_forge import curriculum_distiller as model
from ace_forge.dataset_custody import seal
from ace_forge.dataset_forge import forge, _partition
from ace_forge._forge_io import canonical
from ace_forge.test_dataset_custody import wire
from ace_forge.test_dataset_forge import inputs, source


def observation(key, steps, group="search"):
    return {"event_id": key, "lesson_id": group, "teacher_ref": f"fixture/teacher/{key}", "steps": steps}


def fixture():
    candidates = [f"family-{i}" for i in range(64)]
    train = next(item for item in candidates if _partition(52, item, 2500) == "train")
    test = next(item for item in candidates if _partition(52, item, 2500) == "held_out")
    raw, verified = inputs(
        source("a", family=train), source("b", family=train), source("c", family=train),
        source("h", family=test, target="GOLD_TARGET_42"), source("unmapped", family=train),
    )
    rows, _ = forge(raw, verified)
    data = wire(rows)
    manifest = seal(data, "fixture/in")
    metadata = {
        "metadata_ref": "fixture/metadata", "minimum_training": 2, "minimum_held_out": 1,
        "minimum_step_support": 2, "observations": [
            observation("a", ["Langkah Z", "Langkah A", "Opsional"]),
            observation("b", ["Langkah Z", "Langkah A"]),
            observation("c", ["Langkah A"]),
            observation("h", []),
        ],
    }
    return data, manifest, manifest["head_sha256"], metadata


class DistillerTests(unittest.TestCase):
    def test_frequent_steps_respect_documented_order_and_keep_provenance(self):
        report = model.distill(*fixture())
        lesson, = report["lessons"]
        self.assertEqual(lesson["lesson_id"], "search")
        self.assertEqual(lesson["task_kind"], "fixture-logic")
        self.assertEqual(lesson["steps"], [
            {"instruction": "Langkah Z", "event_ids": ["a", "b"]},
            {"instruction": "Langkah A", "event_ids": ["a", "b", "c"]},
        ])
        self.assertEqual(lesson["demonstrations"][0]["teacher_ref"], "fixture/teacher/a")
        self.assertEqual(lesson["demonstrations"][0]["evidence_ref"], "fixture/evidence/a")
        self.assertEqual(report["unmapped_events"], ["unmapped"])
        self.assertEqual(report["audit"][0]["discarded_steps"], {"Opsional": ["a"]})
        self.assertEqual(report["audit"][0]["reasons"], [])

    def test_held_out_items_have_prompts_and_refs_without_answer_or_payload_hash(self):
        report = model.distill(*fixture())
        held, = report["lessons"][0]["held_out"]
        self.assertEqual(held, {"event_id": "h", "teacher_ref": "fixture/teacher/h",
                                "prompt": "Uji kasus h.", "evidence_ref": "fixture/evidence/h"})
        self.assertNotIn(b"GOLD_TARGET_42", canonical(report))
        self.assertNotIn("h", [item["event_id"] for item in report["lessons"][0]["demonstrations"]])

    def test_insufficient_counts_and_step_support_each_hold_the_lesson(self):
        data, manifest, head, protocol = fixture()
        for changes, reason in (
            ({"minimum_training": 4}, "insufficient_training"),
            ({"minimum_held_out": 2}, "insufficient_held_out"),
            ({"minimum_step_support": 4}, "no_supported_steps"),
        ):
            with self.subTest(changes=changes):
                result = model.distill(data, manifest, head, {**protocol, **changes})
                self.assertEqual(result["lessons"], [])
                self.assertIn(reason, result["audit"][0]["reasons"])

    def test_reversed_precedence_is_explained_from_actual_example_ids(self):
        data, manifest, head, protocol = fixture()
        protocol["observations"][1]["steps"].reverse()
        report = model.distill(data, manifest, head, protocol)
        self.assertEqual(report["lessons"], [])
        self.assertEqual(report["audit"][0]["ordering_conflicts"], {"contradictions": [
            {"pair": ["Langkah A", "Langkah Z"], "forward_events": ["b"], "reverse_events": ["a"]},
        ]})

    def test_longer_cycle_is_detected_even_if_no_pair_directly_disagrees(self):
        data, manifest, head, protocol = fixture()
        for record, steps in zip(protocol["observations"], (["A", "B"], ["B", "C"], ["C", "A"], []), strict=True):
            record["steps"] = steps
        result = model.distill(data, manifest, head, protocol)
        self.assertEqual(result["lessons"], [])
        self.assertEqual(result["audit"][0]["ordering_conflicts"], {"cycle_remaining_steps": ["A", "B", "C"]})

    def test_held_out_receipt_cannot_contribute_procedural_steps(self):
        data, manifest, head, protocol = fixture()
        protocol["observations"][-1]["steps"] = ["Uji berasal dari held-out"]
        with self.assertRaisesRegex(model.InputError, "train"):
            model.distill(data, manifest, head, protocol)

    def test_metadata_must_reference_an_attested_row_with_independent_teacher_pointer(self):
        for change in ({"event_id": "unknown"}, {"event_id": "b"},
                       {"teacher_ref": "fixture/teacher/b"}, {"teacher_ref": "fixture/evidence/a"},
                       {"steps": ["A", "A"]}):
            data, manifest, head, metadata = fixture()
            metadata["observations"][0].update(change)
            with self.subTest(change=change), self.assertRaises(model.InputError):
                model.distill(data, manifest, head, metadata)

    def test_unauthenticated_dataset_or_anchor_never_emits_lessons(self):
        data, manifest, head, metadata = fixture()
        for changed, anchor in ((data + b"\n", head), (data, "a" * 64)):
            with self.subTest(anchor=anchor), self.assertRaisesRegex(model.InputError, "kustodi"):
                model.distill(changed, manifest, anchor, metadata)

    def test_cli_is_byte_identical_on_metadata_permutations(self):
        data, manifest, head, metadata = fixture()
        root = Path(self.enterContext(TemporaryDirectory()))
        source_path = root / "dataset.jsonl"
        meta_path = root / "meta.json"
        manifest_path = root / "manifest.json"
        source_path.write_bytes(data)
        manifest_path.write_bytes(canonical(manifest))
        args = [str(source_path), str(meta_path), "--manifest", str(manifest_path), "--expect-head", head]
        seen = []
        for _ in range(2):
            meta_path.write_bytes(canonical(metadata))
            with redirect_stdout(StringIO()) as stream:
                self.assertEqual(model.main(args), 0)
            seen.append(stream.getvalue())
            metadata["observations"].reverse()
        self.assertEqual(seen[0], seen[1])
        self.assertEqual(json.loads(seen[0])["dataset_head_sha256"], head)
