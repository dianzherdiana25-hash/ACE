"""Verifier diff konten, graph parent, dan hash dataset berkustodi."""
from contextlib import redirect_stdout
from copy import deepcopy
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_forge import dataset_versioning as model
from ace_forge._forge_io import canonical, identity
from ace_forge.test_poison_detector import dataset
from ace_forge.test_dataset_forge import source


def pack(name, rows, *, parents=(), ratio=0):
    data, manifest, anchor = dataset(rows, ratio, f"fixture/source/{name}")
    card = {"version": name, "source_ref": f"fixture/version/{name}", "parents": list(parents)}
    return data, manifest, anchor, card, identity(card)


def fixture():
    old = model.snapshot(*pack("v1", [source("keep"), source("edit", target="Source Content A"), source("gone")]))
    new = model.snapshot(*pack("v2", [source("keep"), source("edit", target="Source Content B"), source("added")],
                               parents=(old["version_sha256"],)))
    return old, new


def compare(left, right):
    return model.compare(left, left["version_sha256"], right, right["version_sha256"])


class VersionTests(unittest.TestCase):
    def test_distinguishes_different_payloads_without_exposing_source_text(self):
        old, new = fixture()
        result = compare(old, new)
        self.assertEqual(result["counts"], {"added": 1, "changed": 1, "removed": 1})
        self.assertEqual(result["changed_fields"], {"payload_sha256": 1, "target_sha256": 1})
        self.assertEqual(result["unchanged_rows"], 1)
        self.assertTrue(result["direct_parent"])
        changed = result["changes"][1]
        self.assertEqual(changed["event_id"], "edit")
        self.assertNotEqual(changed["old_payload_sha256"], changed["new_payload_sha256"])
        self.assertEqual(changed["old_evidence_ref"], "fixture/evidence/edit")
        self.assertNotIn(b"Source Content", canonical(new))
        self.assertEqual(new["version_sha256"], identity(new["version"]))

    def test_split_only_diff_preserves_payload_identity(self):
        rows = [source("single")]
        left = model.snapshot(*pack("before", rows))
        right = model.snapshot(*pack("after", rows, ratio=10_000))
        result = compare(left, right)
        self.assertFalse(result["direct_parent"])
        item, = result["changes"]
        self.assertEqual(item["fields"], ["split"])
        self.assertEqual(item["old_payload_sha256"], item["new_payload_sha256"])

    def test_lineage_nodes_and_heads_of_branch_and_merge(self):
        old, new = fixture()
        alternate = model.snapshot(*pack("alt", [source("a")], parents=(old["version_sha256"],)))
        merged = model.snapshot(*pack("merge", [source("join")],
                                      parents=(alternate["version_sha256"], new["version_sha256"])))
        data = [merged, alternate, old, new]
        lineage = model.lineage(data, identity(data))
        self.assertEqual(lineage["heads"], [merged["version_sha256"]])
        self.assertEqual(lineage["roots"], [old["version_sha256"]])
        self.assertEqual(lineage["status"], "complete")
        missing = [merged, old, new]
        incomplete = model.lineage(missing, identity(missing))
        self.assertEqual(incomplete["status"], "incomplete")
        self.assertEqual(incomplete["gaps"], [{"version_sha256": merged["version_sha256"],
                                               "missing_parents": [alternate["version_sha256"]]}])

    def test_tamper_version_or_dataset_is_refused_by_its_own_anchor(self):
        old, new = fixture()
        expected = new["version_sha256"]
        new["version"]["examples"][0]["target_sha256"] = "0" * 64
        with self.assertRaisesRegex(model.InputError, "anchor"):
            model.compare(old, old["version_sha256"], new, expected)
        data, manifest, head, metadata, policy = pack("v1", [source("row")])
        with self.assertRaisesRegex(model.InputError, "kustodi"):
            model.snapshot(data[:-1], manifest, head, metadata, policy)
        with self.assertRaisesRegex(model.InputError, "Metadata"):
            model.snapshot(data, manifest, head, {**metadata, "version": "other"}, policy)

    def test_duplicate_version_names_or_parent_hashes_are_rejected(self):
        old, new = fixture()
        another = deepcopy(new)
        another["version"]["version"] = old["version"]["version"]
        another["version_sha256"] = identity(another["version"])
        items = [old, another]
        with self.assertRaisesRegex(model.InputError, "ID versi"):
            model.lineage(items, identity(items))
        data, manifest, head, metadata, _ = pack("new", [source("row")], parents=("0"*64, "0"*64))
        with self.assertRaisesRegex(model.InputError, "Parent versi"):
            model.snapshot(data, manifest, head, metadata, identity(metadata))

    def test_cli_seal_and_diff_are_read_only_with_external_anchors(self):
        data, manifest, head, meta, checksum = pack("fixed", [source("one")])
        root = Path(self.enterContext(TemporaryDirectory()))
        d, m, p, v = [root / name for name in ("data.jsonl", "manifest.json", "meta.json", "version.json")]
        for path, value in ((d, data), (m, canonical(manifest)), (p, canonical(meta))):
            path.write_bytes(value)
        with redirect_stdout(StringIO()) as out:
            self.assertEqual(model.main(["snapshot", str(d), str(m), str(p), "--expect-head", head,
                                         "--expect-metadata-sha256", checksum]), 0)
        result = json.loads(out.getvalue())
        v.write_bytes(canonical(result))
        bound = result["version_sha256"]
        with redirect_stdout(StringIO()) as out:
            self.assertEqual(model.main(["diff", str(v), str(v), "--expect-before", bound, "--expect-after", bound]), 0)
        self.assertEqual(json.loads(out.getvalue())["unchanged_rows"], 1)
        self.assertEqual(d.read_bytes(), data)

    def test_empty_snapshot_and_empty_catalogues_are_distinct(self):
        empty = model.snapshot(*pack("empty", []))
        self.assertEqual(compare(empty, empty)["unchanged_rows"], 0)
        lineage = model.lineage([], identity([]))
        self.assertEqual(lineage["versions"], [])
        self.assertEqual(lineage["heads"], [])

    def test_cli_lineage_restores_incomplete_given_known_parent(self):
        old, next_ = fixture()
        root = Path(self.enterContext(TemporaryDirectory()))
        p = root / "catalog.json"
        for catalog, code in (([next_], 1), ([old, next_], 0)):
            p.write_bytes(canonical(catalog))
            with redirect_stdout(StringIO()) as out:
                self.assertEqual(model.main(["lineage", str(p), "--expect-catalog-sha256", identity(catalog)]), code)
            self.assertEqual(json.loads(out.getvalue()), model.lineage(catalog, identity(catalog)))
            self.assertEqual(p.read_bytes(), canonical(catalog))

    def test_changing_provenance_never_becomes_an_unchanged_row(self):
        old, new = fixture()
        new["version"]["examples"][1]["license"] = "fixture/other-license"
        new["version"]["examples"][1]["index_ref"] = "fixture/index/fresh"
        new["version_sha256"] = identity(new["version"])
        result = compare(old, new)
        self.assertEqual(result["changed_fields"]["license"], 1)
        self.assertEqual(result["changed_fields"]["index_ref"], 1)
