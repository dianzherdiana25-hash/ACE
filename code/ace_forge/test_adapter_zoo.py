"""Verifier identitas adaptor, compatibility layout dan jejak versi."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_forge import adapter_zoo as model
from ace_forge._forge_io import canonical, identity


BASE, ALT = "a"*64, "b"*64


def artifact(coefficient, base=BASE, layer="fixture/dense", rank=1, width=2, outputs=1):
    return {"schema": "ace.lora-dense-adapter.v1", "base_sha256": base, "layer": layer,
            "rank": rank, "alpha": rank,
            "a": [[coefficient + column for column in range(width)] for _ in range(rank)],
            "b": [[1]*rank for _ in range(outputs)]}


def row(name, version, payload, *, domain="code", state="qualified", caps=None, parent=None):
    return {"name": name, "version": version, "domain": domain,
            "capabilities": ["rank", "review"] if caps is None else caps,
            "artifact_sha256": identity(payload), "artifact_ref": f"fixture/artifact/{name}/{version}",
            "recipe_ref": f"fixture/recipe/{name}/{version}", "previous_sha256": parent,
            "review": None if state is None else {"status": state, "review_ref": f"fixture/review/{name}/{version}",
                                                 "held_out_sha256": "d"*64}}


def fixture():
    old, latest, language = (artifact(value) for value in (1, 2, 3))
    entries = [row("alpha", 1, old), row("alpha", 2, latest, parent=identity(old), state=None),
               row("language", 1, language, domain="language", state="rejected", caps=["summarize"])]
    return {"catalog_ref": "fixture/catalog", "entries": entries}, [old, latest, language]


def catalog(manifest, payloads):
    return model.catalog(manifest, payloads, identity(manifest))


class ZooTests(unittest.TestCase):
    def test_history_keeps_latest_and_latest_qualified_separate(self):
        manifest, payloads = fixture()
        result = catalog(manifest, payloads)
        self.assertEqual(result["catalog_sha256"], identity(manifest))
        self.assertEqual(result["histories"], [
            {"name": "alpha", "domain": "code", "latest_version": 2, "latest_qualified_version": 1},
            {"name": "language", "domain": "language", "latest_version": 1, "latest_qualified_version": None},
        ])
        first, second, third = result["adapters"]
        self.assertEqual(second["previous_sha256"], first["artifact_sha256"])
        self.assertIsNone(second["review"])
        self.assertEqual(third["status"], "rejected")
        self.assertEqual(first["review"]["held_out_sha256"], "d"*64)
        self.assertEqual((first["features"], first["outputs"], first["rank"]), (2, 1, 1))
        self.assertNotIn("a", first)

    def test_fixture_payloads_and_membership_are_both_hash_bound(self):
        manifest, payloads = fixture()
        anchor = identity(manifest)
        manifest["entries"][0]["capabilities"].append("lookup")
        with self.assertRaisesRegex(model.InputError, "anchor"):
            model.catalog(manifest, payloads, anchor)
        payloads[0]["a"][0][0] += 1
        with self.assertRaisesRegex(model.InputError, "hilang"):
            catalog(manifest, payloads)

    def test_retired_latest_does_not_appear_qualified_when_predecessor_remains(self):
        manifest, payloads = fixture()
        manifest["entries"][1]["review"] = {"status": "retired", "review_ref": "test/retire", "held_out_sha256": "e"*64}
        report = catalog(manifest, payloads)
        self.assertEqual(report["histories"][0]["latest_qualified_version"], 1)
        self.assertEqual(report["adapters"][1]["status"], "retired")

    def test_newer_qualified_version_replaces_previous_qualification_in_summary(self):
        manifest, payloads = fixture()
        manifest["entries"][1]["review"] = {"status": "qualified", "review_ref": "test/eligible", "held_out_sha256": "e"*64}
        report = catalog(manifest, payloads)
        self.assertEqual(report["histories"][0]["latest_qualified_version"], 2)
        self.assertEqual([r["status"] for r in report["adapters"]], ["qualified", "qualified", "rejected"])

    def test_reject_parent_gap_and_wrong_domain(self):
        for mutation in ({"version": 3}, {"previous_sha256": "c"*64}, {"domain": "other"}):
            manifest, payloads = fixture()
            manifest["entries"][1].update(mutation)
            with self.subTest(mutation=mutation), self.assertRaisesRegex(model.InputError, "Riwayat"):
                catalog(manifest, payloads)

    def test_layout_may_change_rank_but_not_base_layer_width_or_output_count(self):
        for pattern in ({"base": ALT}, {"layer": "other"}, {"width": 3}, {"outputs": 3}):
            manifest, payloads = fixture()
            changed = artifact(2, **pattern)
            payloads[1] = changed
            manifest["entries"][1]["artifact_sha256"] = identity(changed)
            with self.subTest(pattern=pattern), self.assertRaisesRegex(model.InputError, "layout"):
                catalog(manifest, payloads)
        manifest, payloads = fixture()
        payloads[1] = artifact(2, rank=2)
        manifest["entries"][1]["artifact_sha256"] = identity(payloads[1])
        self.assertEqual(catalog(manifest, payloads)["adapters"][1]["rank"], 2)

    def test_cannot_register_ambiguous_versions_hashes_or_source_refs(self):
        for field in ("version", "artifact_ref", "artifact_sha256"):
            manifest, payloads = fixture()
            manifest["entries"][1][field] = manifest["entries"][0][field]
            with self.subTest(field=field), self.assertRaisesRegex(model.InputError, "ganda"):
                catalog(manifest, payloads)
        manifest, payloads = fixture()
        manifest["entries"][0]["review"]["review_ref"] = manifest["entries"][0]["artifact_ref"]
        with self.assertRaisesRegex(model.InputError, "review.*ganda"):
            catalog(manifest, payloads)

    def test_requires_review_shape_and_known_verdict(self):
        manifest, payloads = fixture()
        manifest["entries"][0]["review"]["status"] = "unreviewed"
        with self.assertRaisesRegex(model.InputError, "tak dikenal"):
            catalog(manifest, payloads)
        manifest["entries"][0]["review"].update(status="qualified", held_out_sha256="unknown")
        with self.assertRaises(model.InputError):
            catalog(manifest, payloads)

    def test_name_and_capability_set_on_each_version_must_be_explicit(self):
        for labels in ([], ["rank", "rank"], [""]):
            manifest, payloads = fixture()
            manifest["entries"][0]["capabilities"] = labels
            with self.subTest(labels=labels), self.assertRaises(model.InputError):
                catalog(manifest, payloads)

    def test_payload_catalog_is_a_bijection(self):
        manifest, payloads = fixture()
        with self.assertRaisesRegex(model.InputError, "luar katalog"):
            catalog(manifest, [*payloads, artifact(31)])
        with self.assertRaisesRegex(model.InputError, "Payload.*ganda"):
            catalog(manifest, [*payloads, payloads[0]])
        with self.assertRaisesRegex(model.InputError, "hilang"):
            catalog(manifest, payloads[:-1])
        self.assertEqual(catalog({"catalog_ref": "test/empty", "entries": []}, [])["histories"], [])

    def test_wrong_factor_shape_cannot_enter_catalog_even_with_fresh_anchor(self):
        manifest, payloads = fixture()
        payloads[0]["b"][0] = []
        manifest["entries"][0]["artifact_sha256"] = identity(payloads[0])
        with self.assertRaises(model.InputError):
            catalog(manifest, payloads)

    def test_order_api_is_stable_except_for_hash_of_reordered_catalog(self):
        manifest, payloads = fixture()
        first = catalog(manifest, payloads)
        manifest["entries"].reverse()
        second = catalog(manifest, payloads[::-1])
        self.assertNotEqual(first.pop("catalog_sha256"), second.pop("catalog_sha256"))
        self.assertEqual(first, second)

    def test_cli_uses_separate_catalog_and_payload_files(self):
        manifest, payloads = fixture()
        base = Path(self.enterContext(TemporaryDirectory()))
        index, artifacts = base / "zoo.json", base / "adapters.json"
        index.write_bytes(canonical(manifest))
        artifacts.write_bytes(canonical(payloads))
        with redirect_stdout(StringIO()) as out:
            self.assertEqual(model.main([str(index), str(artifacts), "--expect-catalog-sha256", identity(manifest)]), 0)
        self.assertEqual(json.loads(out.getvalue()), catalog(manifest, payloads))
        self.assertEqual(artifacts.read_bytes(), canonical(payloads))

    def test_reject_duplicate_review_pointer_across_distinct_histories(self):
        manifest, payloads = fixture()
        manifest["entries"][2]["review"]["review_ref"] = manifest["entries"][0]["review"]["review_ref"]
        with self.assertRaisesRegex(model.InputError, "review.*ganda"):
            catalog(manifest, payloads)
        manifest["entries"][2]["review"]["review_ref"] = "test/review/distinct"
        product = catalog(manifest, payloads)
        self.assertEqual(product["adapters"][2]["review"]["review_ref"], "test/review/distinct")
