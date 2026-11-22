"""Verifier anomali versi, irisan, dan konsentrasi bukti per kelompok."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_forge import poison_detector as model
from ace_forge._forge_io import canonical, identity
from ace_forge.dataset_custody import seal
from ace_forge.dataset_forge import _partition, forge
from ace_forge.test_dataset_custody import wire
from ace_forge.test_dataset_forge import inputs, source
from ace_forge.test_forgetting_guard import q


def dataset(rows, ratio, ref):
    data, proof = inputs(*rows)
    data["held_out_basis_points"] = ratio
    rows, _ = forge(data, proof)
    packed = wire(rows)
    manifest = seal(packed, ref)
    return packed, manifest, manifest["head_sha256"]


def fixture():
    held = next(f"family/{i}" for i in range(60) if _partition(52, f"family/{i}", 2500) == "held_out")
    train = [f"family/{i}" for i in range(60) if _partition(52, f"family/{i}", 2500) == "train"]
    keep = source("same", family=train[0])
    changed = source("changed", family=train[1], target="Gold prior fixture")
    escape = source("held", family=held)
    other = [source(f"surge-{ix}", family=train[2], target="Repeated fixture answer") for ix in range(3)]
    one = dataset([keep, changed, escape], 2500, "fixture/old")
    two = dataset([keep, {**changed, "target": "New fixture result"}, escape, *other], 0, "fixture/new")
    policy = {"policy_ref": "fixture/policy", "minimum_group": 3, "minimum_share_bp": 5000,
              "minimum_increase_bp": 2000}
    return *one, *two, policy, identity(policy)


class PoisonTests(unittest.TestCase):
    def test_signal_kinds_and_counts_follow_custodied_reference(self):
        report = model.audit(*fixture())
        self.assertEqual(report["status"], "review_required")
        self.assertEqual((report["baseline_examples"], report["candidate_examples"]), (3, 6))
        types = [row["type"] for row in report["findings"]]
        self.assertCountEqual(types, ["label_changed", "held_out_entered_train", "evidence_changed_payload",
                                      "concentration_increase", "concentration_increase", "family_partition_conflict"])
        for row in report["findings"]:
            if row["type"] == "concentration_increase":
                self.assertEqual(row["share"], q(1, 2))
                self.assertEqual(row["old_share"], q(0))
                self.assertEqual(row["evidence_refs"], [f"fixture/evidence/surge-{i}" for i in range(3)])
        data = canonical(report)
        for phrase in (b"Gold prior fixture", b"New fixture result", b"Repeated fixture answer"):
            self.assertNotIn(phrase, data)

    def test_identical_snapshot_produces_no_configured_signal(self):
        packed, manifest, head, *_, policy, checksum = fixture()
        result = model.audit(packed, manifest, head, packed, manifest, head, policy, checksum)
        self.assertEqual(result["status"], "no_configured_signal")
        self.assertEqual(result["findings"], [])

    def test_hold_out_contamination_matches_normalized_prompt_across_event_ids(self):
        row = source("hold", prompt="Naïve  example")
        one = dataset([row], 10_000, "fixture/held")
        two = dataset([source("new-id", prompt="Nai\u0308ve example", target=row["target"])], 0, "fixture/train")
        policy = fixture()[-2]
        signal = model.audit(*one, *two, policy, identity(policy))["findings"][0]
        self.assertEqual(signal["type"], "held_out_entered_train")
        self.assertEqual(signal["old_evidence_ref"], "fixture/evidence/hold")
        self.assertEqual(signal["new_evidence_ref"], "fixture/evidence/new-id")

    def test_normalized_label_whitespace_diff_is_not_content_flip(self):
        old = source("old", prompt="Satu", target="gold one")
        new = source("new", prompt="Satu", target="gold  one\n")
        one, two = dataset([old], 0, "fixture/old"), dataset([new], 0, "fixture/new")
        policy = fixture()[-2]
        self.assertEqual(model.audit(*one, *two, policy, identity(policy))["findings"], [])

    def test_concentration_threshold_and_min_group_are_exact(self):
        *files, policy, _ = fixture()
        for changed in ({"minimum_group": 4}, {"minimum_share_bp": 5001}, {"minimum_increase_bp": 5001}):
            source_ = {**policy, **changed}
            result = model.audit(*files, source_, identity(source_))
            self.assertEqual({row["type"] for row in result["findings"]},
                             {"label_changed", "held_out_entered_train", "evidence_changed_payload", "family_partition_conflict"})

    def test_new_cell_without_baseline_preserves_unknown_old_share(self):
        train = [source(f"id-{i}", target="Gold", family="train/new") for i in range(4)]
        one, two = dataset([], 0, "fixture/nil"), dataset(train, 0, "fixture/train")
        policy = fixture()[-2]
        report = model.audit(*one, *two, policy, identity(policy))
        self.assertEqual(len(report["findings"]), 2)
        self.assertTrue(all(row["old_total"] == 0 and row["old_share"] is None for row in report["findings"]))

    def test_integrity_policy_and_each_snapshot_are_independent(self):
        old, om, oh, new, nm, nh, policy, anchor = fixture()
        with self.assertRaisesRegex(model.InputError, "anchor"):
            model.audit(old, om, oh, new, nm, nh, {**policy, "minimum_group": 8}, anchor)
        for a, b in ((old[:-1], new), (old, new[:-1])):
            with self.subTest(old_size=len(a), new_size=len(b)), self.assertRaisesRegex(model.InputError, "kustodi"):
                model.audit(a, om, oh, b, nm, nh, policy, anchor)

    def test_cli_flags_review_and_writes_single_deterministic_json_report(self):
        old, om, oh, new, nm, nh, policy, anchor = fixture()
        root = Path(self.enterContext(TemporaryDirectory()))
        files = [root / path for path in ("old.jsonl", "old.manifest", "new.jsonl", "new.manifest", "policy.json")]
        for path, payload in zip(files, (old, canonical(om), new, canonical(nm), canonical(policy)), strict=True):
            path.write_bytes(payload)
        args = [*map(str, files), "--expect-baseline-head", oh, "--expect-candidate-head", nh,
                "--expect-policy-sha256", anchor]
        with redirect_stdout(StringIO()) as output:
            self.assertEqual(model.main(args), 1)
        self.assertEqual(json.loads(output.getvalue()), model.audit(old, om, oh, new, nm, nh, policy, anchor))
        self.assertEqual(files[0].read_bytes(), old)
        self.assertEqual(files[2].read_bytes(), new)

    def test_train_to_held_out_is_detected_even_when_target_label_did_not_change(self):
        row = source("prior", family="fixture/replayed")
        baseline, candidate = dataset([row], 0, "fixture/base"), dataset([row], 10_000, "fixture/next")
        policy = fixture()[-2]
        signals = model.audit(*baseline, *candidate, policy, identity(policy))["findings"]
        self.assertEqual([obj["type"] for obj in signals], ["train_entered_held_out", "family_partition_conflict"])

    def test_family_conflict_matches_new_prompt_with_distinct_evidence_and_no_point_overlap(self):
        baseline = dataset([source("past", family="fixture/shared")], 0, "fixture/base")
        candidate = dataset([source("future", family="fixture/shared")], 10_000, "fixture/next")
        policy = fixture()[-2]
        report = model.audit(*baseline, *candidate, policy, identity(policy))
        pair, = report["findings"]
        self.assertEqual(pair["type"], "family_partition_conflict")
        self.assertEqual(pair["old_evidence_refs"], ["fixture/evidence/past"])
        self.assertEqual(pair["new_evidence_refs"], ["fixture/evidence/future"])

    def test_concentration_is_compared_with_the_original_share_in_the_same_task(self):
        series = [source(f"case-{i}", family="fixture/stable", target="same answer") for i in range(5)]
        baseline, candidate = dataset(series[:3], 0, "fixture/base"), dataset(series, 0, "fixture/next")
        policy = fixture()[-2]
        self.assertEqual(model.audit(*baseline, *candidate, policy, identity(policy))["findings"], [])

    def test_concentration_denominator_is_scoped_to_task_kind(self):
        prior = [{**source("stable", target="unique"), "task_kind": "other"}]
        focal = [source(f"training{i}", family="target", target="shared") for i in range(3)]
        no_pool = [*prior, *focal, *({**source(f"other{i}"), "task_kind": "other"} for i in range(10))]
        baseline, candidate = dataset(prior, 0, "fixture/one"), dataset(no_pool, 0, "fixture/two")
        policy = fixture()[-2]
        result = model.audit(*baseline, *candidate, policy, identity(policy))
        focus = [signal for signal in result["findings"] if signal.get("task_kind") == "fixture-logic"]
        self.assertEqual(len(focus), 2)
        self.assertTrue(all(signal["share"] == q(1) and signal["total"] == 3 for signal in focus))
