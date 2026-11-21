"""Verifier paritas per keluarga, split, dan integritas byte keluaran."""
from contextlib import redirect_stdout
from collections import Counter
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_forge import bilingual_balance as model
from ace_forge._forge_io import canonical, identity
from ace_forge.dataset_custody import seal, verify
from ace_forge.dataset_forge import _partition, forge
from ace_forge.test_dataset_forge import inputs, source
from ace_forge.test_dataset_custody import wire


def fixture():
    families = [f"fixture-{i}" for i in range(40)]
    train = [family for family in families if _partition(52, family, 2500) == "train"]
    held = next(family for family in families if _partition(52, family, 2500) == "held_out")
    rows = []
    for family, prefix, tags in (
        (train[0], "large", "id id en en"),
        (train[1], "small", "id en"),
        (train[2], "mono", "id"),
        (held, "held", "id en es"),
    ):
        rows.extend({**source(f"{prefix}-{i}", family=family), "language": tag}
                    for i, tag in enumerate(tags.split()))
    rows.append({**source("other-kind", family=train[0]), "task_kind": "other"})
    dataset, _ = forge(*inputs(*rows))
    raw = wire(dataset)
    manifest = seal(raw, "fixture/source")
    plan = {"policy_ref": "fixture/parity", "seed": 52, "quotas": [
        {"task_kind": "fixture-logic", "split": "train", "pairs": 2},
        {"task_kind": "fixture-logic", "split": "held_out", "pairs": 1},
    ]}
    return raw, manifest, manifest["head_sha256"], plan, identity(plan)


class BilingualTests(unittest.TestCase):
    def test_exact_id_en_parity_at_each_stratum_and_distinct_families(self):
        selected, report = model.balance(*fixture())
        self.assertEqual(report["status"], "balanced")
        self.assertEqual(report["selected_examples"], 6)
        self.assertEqual(report["excluded"], {"language_outside_id_en": 1, "outside_quota": 1})
        held, train = report["strata"]
        self.assertEqual(held["available_pairs"], 1)
        self.assertEqual(train["available_pairs"], 3)
        self.assertEqual(train["unpaired_languages"], {"id": 1, "en": 0})
        self.assertEqual(len({row["family_id"] for row in train["pairs"]}), 2)
        observed = Counter((row["split"], row["payload"]["language"]) for row in selected)
        self.assertEqual(observed, {("held_out", "en"): 1, ("held_out", "id"): 1,
                                    ("train", "en"): 2, ("train", "id"): 2})

    def test_every_selected_record_is_exact_source_with_independent_verifier_metadata(self):
        raw, *others = fixture()
        originals = {row["example_id"]: row for row in map(json.loads, raw.splitlines())}
        selected, report = model.balance(raw, *others)
        for row in selected:
            self.assertEqual(row, originals[row["example_id"]])
        chosen = wire(selected)
        sealed = seal(chosen, "fixture/subset")
        self.assertTrue(verify(chosen, sealed, sealed["head_sha256"])["valid"])
        for strata in report["strata"]:
            for pair in strata["pairs"]:
                for tag in ("id", "en"):
                    row = originals[pair[tag]["id"]]
                    self.assertEqual(row["payload"]["family_id"], pair["family_id"])
                    self.assertEqual(row["provenance"]["evidence_ref"], pair[tag]["evidence_ref"])

    def test_quota_shortfall_holds_whole_export_even_if_other_partition_is_full(self):
        raw, manifest, head, plan, _ = fixture()
        plan["quotas"][0]["pairs"] = 4
        chosen, report = model.balance(raw, manifest, head, plan, identity(plan))
        self.assertEqual(chosen, [])
        self.assertEqual(report["status"], "hold")
        self.assertEqual(report["strata"][0]["shortfall_pairs"], 0)
        self.assertEqual(report["strata"][1]["shortfall_pairs"], 1)

    def test_changed_weights_policy_and_dataset_fail_before_selection(self):
        raw, manifest, head, plan, checksum = fixture()
        with self.assertRaisesRegex(model.InputError, "kustodi"):
            model.balance(raw[:-1], manifest, head, plan, checksum)
        plan["seed"] += 1
        with self.assertRaisesRegex(model.InputError, "anchor"):
            model.balance(raw, manifest, head, plan, checksum)

    def test_unknown_duplicate_and_empty_quota_are_invalid(self):
        raw, manifest, head, plan, _ = fixture()
        for quotas in ([], plan["quotas"] * 2, [{**plan["quotas"][0], "pairs": 0}],
                       [{**plan["quotas"][0], "split": "development"}]):
            changed = {**plan, "quotas": quotas}
            with self.subTest(quotas=quotas), self.assertRaises(model.InputError):
                model.balance(raw, manifest, head, changed, identity(changed))

    def test_seeded_pairing_reproducible_under_resealed_input_order(self):
        data, manifest, head, plan, anchor = fixture()
        original, report = model.balance(data, manifest, head, plan, anchor)
        reversed_ = b"\n".join(data.splitlines()[::-1]) + b"\n"
        resealed = seal(reversed_, "fixture/reordered")
        chosen, after = model.balance(reversed_, resealed, resealed["head_sha256"], plan, anchor)
        self.assertEqual(chosen, original)
        self.assertEqual(report["strata"], after["strata"])
        self.assertNotEqual(report["dataset_head_sha256"], after["dataset_head_sha256"])

    def test_cli_report_and_export_match_the_pure_api(self):
        raw, manifest, head, plan, anchor = fixture()
        folder = Path(self.enterContext(TemporaryDirectory()))
        p, m, r = folder / "rows.jsonl", folder / "manifest.json", folder / "policy.json"
        p.write_bytes(raw)
        m.write_bytes(canonical(manifest))
        r.write_bytes(canonical(plan))
        args = [str(p), str(m), str(r), "--expect-head", head, "--expect-policy-sha256", anchor]
        chosen, report = model.balance(raw, manifest, head, plan, anchor)
        with redirect_stdout(StringIO()) as written:
            self.assertEqual(model.main(args), 0)
        self.assertEqual(json.loads(written.getvalue()), report)
        with redirect_stdout(StringIO()) as written:
            self.assertEqual(model.main([*args, "--export"]), 0)
        self.assertEqual(written.getvalue().encode(), wire(chosen))
        self.assertEqual(p.read_bytes(), raw)

    def test_availability_in_different_families_cannot_fill_false_pairs(self):
        raw, manifest, head, plan, _ = fixture()
        plan["quotas"] = [{"task_kind": "other", "split": "train", "pairs": 1}]
        chosen, report = model.balance(raw, manifest, head, plan, identity(plan))
        self.assertEqual(chosen, [])
        self.assertEqual(report["strata"][0]["available_pairs"], 0)
        self.assertEqual(report["strata"][0]["unpaired_languages"], {"id": 1, "en": 0})

    def test_export_cli_emits_no_partial_rows_under_shortfall(self):
        raw, manifest, head, plan, _ = fixture()
        plan["quotas"][0]["pairs"] = 6
        current = identity(plan)
        folder = Path(self.enterContext(TemporaryDirectory()))
        p, m, r = folder / "rows.jsonl", folder / "manifest.json", folder / "policy.json"
        p.write_bytes(raw)
        m.write_bytes(canonical(manifest))
        r.write_bytes(canonical(plan))
        args = [str(p), str(m), str(r), "--expect-head", head, "--expect-policy-sha256", current, "--export"]
        with redirect_stdout(StringIO()) as written:
            self.assertEqual(model.main(args), 1)
        self.assertEqual(written.getvalue(), "")

    def test_quota_equal_to_available_capacity_takes_all_and_reports_exact_pair_counts(self):
        raw, manifest, head, plan, _ = fixture()
        plan["quotas"][0]["pairs"] = 3
        rows, report = model.balance(raw, manifest, head, plan, identity(plan))
        self.assertEqual(len(rows), 8)
        training = report["strata"][1]
        self.assertEqual(training["shortfall_pairs"], 0)
        self.assertEqual(sorted(Counter(item["family_id"] for item in training["pairs"]).values()), [1, 2])
        stats = Counter(row["payload"]["language"] for row in rows)
        self.assertEqual(stats, {"id": 4, "en": 4})

    def test_zero_eligible_rows_is_a_reported_quota_failure(self):
        _, _, _, plan, checksum = fixture()
        manifest = seal(b"", "fixture/empty")
        rows, report = model.balance(b"", manifest, manifest["head_sha256"], plan, checksum)
        self.assertEqual(rows, [])
        self.assertEqual([record["shortfall_pairs"] for record in report["strata"]], [1, 2])
