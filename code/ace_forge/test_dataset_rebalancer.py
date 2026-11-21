"""Verifier bobot per kelompok, cutoff, ESS, dan provenance."""
from collections import defaultdict
from contextlib import redirect_stdout
from fractions import Fraction
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_forge import dataset_rebalancer as model
from ace_forge._forge_io import canonical, identity
from ace_forge.dataset_custody import seal
from ace_forge.dataset_forge import _partition, forge
from ace_forge.test_dataset_custody import wire
from ace_forge.test_dataset_forge import inputs, source
from ace_forge.test_forgetting_guard import q


def packaged(rows, ratio=0):
    raw, verified = inputs(*rows)
    raw["held_out_basis_points"] = ratio
    corpus, _ = forge(raw, verified)
    data = wire(corpus)
    manifest = seal(data, "fixture/sample")
    return data, manifest, manifest["head_sha256"]


def sample(language, count, family="train", kind="fixture-logic"):
    return [{**source(f"{family}-{language}-{i}", family=family), "language": language, "task_kind": kind}
            for i in range(count)]


def fixtures():
    family = [f"fam/{i}" for i in range(24)]
    train, held = [next(name for name in family if _partition(52, name, 2500) == split)
                   for split in ("train", "held_out")]
    left = sample("id", 6, train)
    right = sample("en", 2, train)
    extras = [*sample("ja", 1, train), *sample("en", 1, held)]
    raw = packaged([*left, *right, *extras], 2500)
    policy = {"policy_ref": "fixture/rebalance", "max_weight_bp": 20_000, "minimum_group": 1, "targets": [
        {"task_kind": "fixture-logic", "language": language, "share_bp": 5000} for language in ("id", "en")
    ]}
    return *raw, policy, identity(policy)


def measure(fixtures_, **updates):
    data, manifest, head, old, _ = fixtures_
    new = {**old, **updates}
    return model.rebalance(data, manifest, head, new, identity(new))


class RebalanceTests(unittest.TestCase):
    def test_equal_targets_from_imbalanced_selection_are_checked_exactly(self):
        args = fixtures()
        result = model.rebalance(*args)
        self.assertEqual(result["status"], "balanced")
        self.assertEqual(result["eligible_train"], 8)
        self.assertEqual(result["excluded"], {"held_out": 1, "out_of_policy": 1})
        self.assertEqual(result["effective_sample_size"], q(6))
        english, indonesian = result["groups"]
        self.assertEqual(english["observed"], q(1, 4))
        self.assertEqual(indonesian["observed"], q(3, 4))
        self.assertEqual(english["weight"], q(2))
        self.assertEqual(indonesian["weight"], q(2, 3))
        self.assertEqual([row["weighted_share"] for row in result["groups"]], [q(1, 2)] * 2)
        self.assertEqual(len(result["assignments"]), 8)
        denied = {item["example_id"] for item in result["exclusions"]}
        self.assertFalse(denied & {item["example_id"] for item in result["assignments"]})

    def test_cap_changes_post_balance_fraction_without_concealing_distortion(self):
        report = measure(fixtures(), max_weight_bp=12_500)
        en, id_ = report["groups"]
        self.assertEqual(report["status"], "capped")
        self.assertEqual((en["weight"], en["capped"]), (q(5, 4), True))
        self.assertEqual((id_["weight"], id_["capped"]), (q(2, 3), False))
        self.assertEqual((en["weighted_share"], id_["weighted_share"]), (q(5, 13), q(8, 13)))
        self.assertEqual(en["weighted_minus_target"], q(-3, 26))

    def test_insufficient_counts_do_not_issue_weights_to_part_of_train(self):
        report = measure(fixtures(), minimum_group=3)
        self.assertEqual(report["status"], "held")
        self.assertEqual(report["groups"][0]["shortfall"], 1)
        self.assertEqual(report["groups"][1]["shortfall"], 0)
        self.assertTrue(all(group["weight"] is None and group["weighted_share"] is None for group in report["groups"]))
        self.assertEqual(report["assignments"], [])
        self.assertIsNone(report["effective_sample_size"])

    def test_missing_group_and_empty_corpus_report_distinct_observations(self):
        *_, plan, checksum = fixtures()
        baseline = packaged(sample("id", 4))
        report = model.rebalance(*baseline, plan, checksum)
        self.assertEqual(report["groups"][0]["observed"], q(0))
        empty = model.rebalance(*packaged([]), plan, checksum)
        self.assertIsNone(empty["groups"][0]["observed"])
        self.assertEqual(empty["eligible_train"], 0)

    def test_weights_match_independent_mass_oracle_for_nonuniform_targets(self):
        rows = [*sample("en", 2, "f1"), *sample("id", 7, "f2"), *sample("id", 4, "f3", "math")]
        source_ = packaged(rows)
        plan = fixtures()[-2]
        plan["targets"] = [{"language": tag, "task_kind": task, "share_bp": amount} for tag, task, amount in [
            ("en", "fixture-logic", 3000), ("id", "fixture-logic", 5500), ("id", "math", 1500),
        ]]
        plan["max_weight_bp"] = 25_000
        result = model.rebalance(*source_, plan, identity(plan))
        originals = {row["example_id"]: row for row in map(json.loads, source_[0].splitlines())}
        masses = defaultdict(Fraction)
        all_weights = []
        for row in result["assignments"]:
            source_row = originals[row["example_id"]]
            self.assertEqual(row["evidence_ref"], source_row["provenance"]["evidence_ref"])
            value = Fraction(**row["weight"])
            all_weights.append(value)
            payload = source_row["payload"]
            masses[payload["task_kind"], payload["language"]] += value
        total = sum(all_weights)
        self.assertEqual(Fraction(**result["effective_sample_size"]), total**2 / sum(item**2 for item in all_weights))
        self.assertEqual({key: mass / total for key, mass in masses.items()},
                         {(row["task_kind"], row["language"]): Fraction(**row["weighted_share"]) for row in result["groups"]})

    def test_recorded_weight_ratio_does_not_change_between_identical_runs(self):
        args = fixtures()
        self.assertEqual(model.rebalance(*args), model.rebalance(*args))

    def test_duplicate_targets_wrong_total_and_anchor_mismatch_are_rejected(self):
        args = fixtures()
        with self.assertRaisesRegex(model.InputError, "anchor"):
            model.rebalance(*args[:-2], {**args[-2], "minimum_group": 100}, args[-1])
        for options in ({"targets": args[-2]["targets"] * 2}, {"targets": args[-2]["targets"][:1]},
                        {"max_weight_bp": 9000}, {"minimum_group": True}):
            with self.subTest(options=options), self.assertRaises(model.InputError):
                measure(args, **options)

    def test_dataset_tamper_and_wrong_independent_head_are_separate_failures(self):
        data, manifest, head, raw, checksum = fixtures()
        for value, anchor in ((data[:-1], head), (data, "0" * 64)):
            with self.subTest(anchor=anchor), self.assertRaisesRegex(model.InputError, "kustodi"):
                model.rebalance(value, manifest, anchor, raw, checksum)

    def test_cli_has_nonzero_status_for_capped_plan_and_leaves_sources_untouched(self):
        data, manifest, head, plan, _ = fixtures()
        root = Path(self.enterContext(TemporaryDirectory()))
        d, m, p = (root / name for name in ("dataset.jsonl", "manifest.json", "policy.json"))
        d.write_bytes(data)
        m.write_bytes(canonical(manifest))
        for cap, code in ((20_000, 0), (12_500, 1)):
            plan["max_weight_bp"] = cap
            policy = canonical(plan)
            p.write_bytes(policy)
            args = [str(d), str(m), str(p), "--expect-head", head, "--expect-policy-sha256", identity(plan)]
            with redirect_stdout(StringIO()) as capture:
                self.assertEqual(model.main(args), code)
            self.assertEqual(json.loads(capture.getvalue()), model.rebalance(data, manifest, head, plan, identity(plan)))
            self.assertEqual(p.read_bytes(), policy)
            self.assertEqual(d.read_bytes(), data)

    def test_already_balanced_dataset_reports_unit_weights_and_exact_ess(self):
        _, _, _, plan, checksum = fixtures()
        args = packaged([*sample("id", 2), *sample("en", 2)])
        report = model.rebalance(*args, plan, checksum)
        self.assertEqual(report["effective_sample_size"], q(4))
        self.assertTrue(all(row["weight"] == q(1) for row in report["assignments"]))

    def test_four_times_weight_and_saturation_report_actual_mass(self):
        rows = packaged([*sample("id", 9), *sample("en", 1)])
        raw = fixtures()[-2]
        raw["max_weight_bp"] = 40_000
        result = model.rebalance(*rows, raw, identity(raw))
        row = result["groups"][0]
        self.assertEqual(row["weight"], q(4))
        self.assertEqual(row["weighted_share"], q(4, 9))
        self.assertEqual(row["weighted_minus_target"], q(-1, 18))
        self.assertEqual(result["effective_sample_size"], q(729, 169))

    def test_only_declared_groups_contribute_to_empirical_denominator(self):
        rows = packaged([*sample("id", 2), *sample("en", 2), *sample("other", 40)])
        raw = fixtures()[-2]
        result = model.rebalance(*rows, raw, identity(raw))
        self.assertTrue(all(row["observed"] == q(1, 2) for row in result["groups"]))
        self.assertEqual(result["eligible_train"], 4)
        self.assertEqual(result["excluded"], {"out_of_policy": 40})

    def test_weighted_mass_excludes_heldout_while_exclusions_keep_source(self):
        result = model.rebalance(*fixtures())
        held = next(row for row in result["exclusions"] if row["reason"] == "held_out")
        self.assertTrue(held["evidence_ref"].startswith("fixture/evidence/fam"))
        self.assertNotIn(held["example_id"], {row["example_id"] for row in result["assignments"]})
