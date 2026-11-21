"""Verifier pita kesulitan, replay dan ekspor dari dataset tertambat."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_forge import staged_curriculum as model
from ace_forge._forge_io import canonical, identity
from ace_forge.dataset_custody import seal, verify
from ace_forge.dataset_forge import _partition, forge
from ace_forge.test_dataset_custody import wire
from ace_forge.test_dataset_forge import inputs, source


def fixture():
    families = [f"group-{i}" for i in range(40)]
    training = next(value for value in families if _partition(52, value, 2500) == "train")
    held = next(value for value in families if _partition(52, value, 2500) == "held_out")
    difficulty = {"zero": 0, "easy": 2000, "medium": 2001, "midpoint": 5000,
                  "hard": 5001, "outlier": 10000, "held": 2000}
    records, _ = forge(*inputs(*(source(name, family=held if name == "held" else training)
                                 for name in (*difficulty, "unrated"))))
    data = wire(records)
    manifest = seal(data, "fixture/data")
    plan = {"plan_ref": "fixture/plan", "seed": 52, "stages": [
        {"id": "easy", "max_difficulty_bp": 2000, "new_examples": 2, "replay_limit": 0},
        {"id": "medium", "max_difficulty_bp": 5000, "new_examples": 2, "replay_limit": 1},
        {"id": "hard", "max_difficulty_bp": 9000, "new_examples": 1, "replay_limit": 4},
    ], "annotations": [
        {"example_id": row["example_id"], "difficulty_bp": difficulty[row["payload"]["event_id"]],
         "evidence_ref": f"fixture/difficulty/{row['payload']['event_id']}"}
        for row in records if row["payload"]["event_id"] in difficulty
    ]}
    return data, manifest, manifest["head_sha256"], plan, identity(plan)


class CurriculumTests(unittest.TestCase):
    def test_disjoint_bands_have_exact_boundaries_and_replay_only_earlier_exposures(self):
        outputs, report = model.prepare(*fixture())
        self.assertEqual(report["status"], "ready")
        self.assertEqual(report["excluded"], {"above_final_stage": 1, "held_out": 1, "unannotated": 1})
        stages = report["stages"]
        self.assertEqual([row["difficulty_range_bp"] for row in stages], [[0, 2000], [2001, 5000], [5001, 9000]])
        self.assertEqual([{item["difficulty_bp"] for item in row["new"]} for row in stages],
                         [{0, 2000}, {2001, 5000}, {5001}])
        self.assertEqual([len(row["replay"]) for row in stages], [0, 1, 4])
        earlier = set()
        for row in stages:
            self.assertTrue({item["example_id"] for item in row["replay"]} <= earlier)
            new = {item["example_id"] for item in row["new"]}
            self.assertFalse(earlier & new)
            earlier.update(new)
            selected = outputs[row["id"]]
            self.assertTrue(all(item["split"] == "train" for item in selected))
            self.assertEqual(len({item["example_id"] for item in selected}), len(selected))
        proof, = stages[-1]["new"]
        self.assertEqual(proof["difficulty_ref"], "fixture/difficulty/hard")
        self.assertEqual(proof["dataset_evidence_ref"], "fixture/evidence/hard")

    def test_exported_rows_match_original_and_can_be_sealed_per_stage(self):
        data, *remaining = fixture()
        rows = {row["example_id"]: row for row in map(json.loads, data.splitlines())}
        outputs, _ = model.prepare(data, *remaining)
        for key, selection in outputs.items():
            found = wire(selection)
            manifest = seal(found, f"fixture/artifacts/{key}")
            self.assertTrue(verify(found, manifest, manifest["head_sha256"])["valid"])
            self.assertEqual(selection, [rows[row["example_id"]] for row in selection])

    def test_insufficient_band_holds_every_export_and_records_shortfall(self):
        data, manifest, head, plan, _ = fixture()
        plan["stages"][-1]["new_examples"] = 2
        exported, report = model.prepare(data, manifest, head, plan, identity(plan))
        self.assertEqual(report["status"], "hold")
        self.assertEqual(report["stages"][-1]["shortfall"], 1)
        self.assertEqual(report["stages"][0]["shortfall"], 0)
        self.assertEqual(exported, {})

    def test_anchor_and_old_dataset_bytes_reject_tampering(self):
        data, manifest, head, plan, bound = fixture()
        plan["annotations"][0]["difficulty_bp"] += 1
        with self.assertRaisesRegex(model.InputError, "anchor"):
            model.prepare(data, manifest, head, plan, bound)
        with self.assertRaisesRegex(model.InputError, "kustodi"):
            model.prepare(data[:-1], manifest, head, plan, identity(plan))

    def test_unmapped_or_duplicate_annotations_fail_closed(self):
        data, manifest, head, plan, _ = fixture()
        last = plan["annotations"][-1]
        for altered in ({"example_id": "unknown"}, {"evidence_ref": "fixture/difficulty/hard"},
                        {"difficulty_bp": True}, {}):
            duplicate = {**last, **altered}
            if altered and "example_id" not in altered:
                duplicate["example_id"] = "unknown-but-scope"
            raw = {**plan, "annotations": [*plan["annotations"], duplicate]}
            with self.subTest(altered=altered), self.assertRaises(model.InputError):
                model.prepare(data, manifest, head, raw, identity(raw))

    def test_nonincreasing_pita_and_duplicate_stage_are_rejected(self):
        data, manifest, head, plan, _ = fixture()
        stages = plan["stages"]
        for rows in ([*stages[:1], {**stages[1], "max_difficulty_bp": 2000}],
                     [*stages[:1], {**stages[1], "id": "easy"}], []):
            modified = {**plan, "stages": rows}
            with self.subTest(rows=rows), self.assertRaises(model.InputError):
                model.prepare(data, manifest, head, modified, identity(modified))

    def test_reordered_source_rows_do_not_change_selected_examples_or_evidence(self):
        data, manifest, head, plan, bound = fixture()
        before, first = model.prepare(data, manifest, head, plan, bound)
        reordered = b"\n".join(data.splitlines()[::-1]) + b"\n"
        fresh = seal(reordered, "fixture/data2")
        after, last = model.prepare(reordered, fresh, fresh["head_sha256"], plan, bound)
        self.assertNotEqual(first["dataset_head_sha256"], last["dataset_head_sha256"])
        self.assertEqual(first["stages"], last["stages"])
        self.assertEqual(before, after)

    def test_maximum_replay_is_a_limit_without_duplicating_or_requiring_extra_examples(self):
        data, manifest, head, plan, _ = fixture()
        plan["stages"][0]["replay_limit"] = 100
        plan["stages"][1]["replay_limit"] = 100
        outputs, report = model.prepare(data, manifest, head, plan, identity(plan))
        self.assertEqual(report["status"], "ready")
        self.assertEqual(len(outputs["easy"]), 2)
        self.assertEqual(len(outputs["medium"]), 4)

    def test_cli_report_and_export_are_independently_replayable(self):
        data, manifest, head, plan, bound = fixture()
        paths = Path(self.enterContext(TemporaryDirectory()))
        s, m, p = (paths / name for name in ("book.jsonl", "manifest.json", "plan.json"))
        s.write_bytes(data)
        m.write_bytes(canonical(manifest))
        p.write_bytes(canonical(plan))
        args = [str(s), str(m), str(p), "--expect-head", head, "--expect-plan-sha256", bound]
        outputs, report = model.prepare(data, manifest, head, plan, bound)
        with redirect_stdout(StringIO()) as out:
            self.assertEqual(model.main(args), 0)
        self.assertEqual(json.loads(out.getvalue()), report)
        with redirect_stdout(StringIO()) as out:
            self.assertEqual(model.main([*args, "--export-stage", "medium"]), 0)
        self.assertEqual(out.getvalue().encode(), wire(outputs["medium"]))
        self.assertEqual(s.read_bytes(), data)

    def test_scarce_pita_selection_matches_seeded_ranking_using_anchor(self):
        data, manifest, head, plan, _ = fixture()
        plan["stages"][0]["new_examples"] = 1
        outputs, report = model.prepare(data, manifest, head, plan, identity(plan))
        rows = {item["example_id"]: item for item in plan["annotations"]}
        default = min((item for item, card in rows.items() if card["difficulty_bp"] <= 2000
                       and not card["evidence_ref"].endswith("/held")),
                      key=lambda key: identity([plan["seed"], "easy", "new", key]))
        self.assertEqual([selected["example_id"] for selected in outputs["easy"]], [default])
        self.assertEqual(len(report["stages"][2]["replay"]), 3)

    def test_empty_roster_is_measured_shortfall_when_annotations_are_also_empty(self):
        _, _, _, plan, _ = fixture()
        plan["annotations"] = []
        manifest = seal(b"", "fixture/empty")
        chosen, report = model.prepare(b"", manifest, manifest["head_sha256"], plan, identity(plan))
        self.assertEqual(chosen, {})
        self.assertEqual([row["shortfall"] for row in report["stages"]], [2, 2, 1])

    def test_annotation_ref_cannot_replace_dataset_proof_reference(self):
        data, manifest, head, plan, bound = fixture()
        rows, report = model.prepare(data, manifest, head, plan, bound)
        record = report["stages"][0]["new"][0]
        selected = next(item for item in rows["easy"] if item["example_id"] == record["example_id"])
        self.assertEqual(selected["provenance"]["evidence_ref"], record["dataset_evidence_ref"])
        self.assertNotEqual(selected["provenance"]["evidence_ref"], record["difficulty_ref"])
