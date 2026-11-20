"""Verifier rantai provenance, penyegelan ulang, dan pembacaan CLI."""
from contextlib import redirect_stdout
from copy import deepcopy
import hashlib
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_forge import dataset_custody as model
from ace_forge.dataset_forge import forge
from ace_forge._forge_io import canonical, identity
from ace_forge.test_dataset_forge import inputs, source


def wire(records):
    return b"".join(canonical(record) + b"\n" for record in records)


def fixture():
    return forge(*inputs(source("b"), source("a"), source("c", family="other")))[0]


class CustodyTests(unittest.TestCase):
    def test_commits_header_payload_refs_and_every_ordered_line(self):
        artifacts = fixture()
        data = wire(artifacts)
        manifest = model.seal(data, "fixture/dataset")
        self.assertEqual(manifest["dataset_sha256"], hashlib.sha256(data).hexdigest())
        self.assertEqual(manifest["record_count"], 3)
        self.assertEqual(manifest["byte_count"], len(data))
        previous = manifest["genesis_sha256"]
        for index, (record, report) in enumerate(zip(artifacts, manifest["records"], strict=True), 1):
            self.assertEqual(report["previous_sha256"], previous)
            self.assertEqual(report["line"], index)
            self.assertEqual(report["entry_sha256"], hashlib.sha256(canonical(record)).hexdigest())
            self.assertEqual(report["evidence_ref"], record["provenance"]["evidence_ref"])
            self.assertEqual(report["index_ref"], record["provenance"]["index_ref"])
            previous = identity({key: value for key, value in report.items() if key != "chain_sha256"})
            self.assertEqual(report["chain_sha256"], previous)
        self.assertEqual(manifest["head_sha256"], previous)
        self.assertTrue(model.verify(data, manifest, previous)["valid"])

    def test_reordering_and_truncation_report_first_divergent_line(self):
        values = fixture()
        original = model.seal(wire(values), "fixture/dataset")
        for data, first in ((wire(values[::-1]), 1), (wire(values[:-1]), 3)):
            with self.subTest(first=first):
                result = model.verify(data, original, original["head_sha256"])
                self.assertFalse(result["valid"])
                self.assertIn("dataset_sha256_mismatch", result["blockers"])
                self.assertIn("records_mismatch", result["blockers"])
                self.assertEqual(result["first_record_mismatch"], first)

    def test_clean_reseal_of_changed_source_snapshot_cannot_reuse_old_anchor(self):
        data = wire(fixture())
        original = model.seal(data, "fixture/dataset")
        changed = fixture()
        changed[1]["provenance"]["evidence_ref"] = "fixture/other/evidence"
        rewritten = wire(changed)
        new_manifest = model.seal(rewritten, "fixture/dataset")
        report = model.verify(rewritten, new_manifest, original["head_sha256"])
        self.assertFalse(report["valid"])
        self.assertEqual(report["blockers"], ["expected_head_mismatch"])

    def test_change_in_manifest_chain_alone_is_rejected(self):
        data = wire(fixture())
        manifest = model.seal(data, "fixture/dataset")
        edited = deepcopy(manifest)
        edited["records"][1]["previous_sha256"] = "0" * 64
        result = model.verify(data, edited, manifest["head_sha256"])
        self.assertEqual(result["first_record_mismatch"], 2)
        self.assertEqual(result["blockers"], ["records_mismatch"])

    def test_changed_target_without_updated_payload_hash_is_refused(self):
        values = fixture()
        manifest = model.seal(wire(values), "fixture/dataset")
        values[-1]["payload"]["target"] += " salah"
        report = model.verify(wire(values), manifest, manifest["head_sha256"])
        self.assertFalse(report["valid"])
        self.assertIn("Baris dataset 3 tidak sah.", report["blockers"])

    def test_rejects_single_family_across_train_and_held_out(self):
        records = fixture()
        records[1]["split"] = "train" if records[0]["split"] == "held_out" else "held_out"
        with self.assertRaisesRegex(model.InputError, "Baris dataset 2"):
            model.seal(wire(records), "fixture/dataset")

    def test_rejects_duplicate_row_or_evidence_even_if_bytes_are_valid(self):
        records = fixture()
        with self.assertRaisesRegex(model.InputError, "Baris dataset 2"):
            model.seal(wire([records[0], records[0]]), "fixture/dataset")
        records[1]["provenance"]["evidence_ref"] = records[0]["provenance"]["evidence_ref"]
        with self.assertRaisesRegex(model.InputError, "Baris dataset 2"):
            model.seal(wire(records), "fixture/dataset")

    def test_noncanonical_crlf_blank_lines_or_unfinished_record_are_invalid(self):
        one = canonical(fixture()[0])
        for data in (one, one + b"\r\n", b"\n", b" " + one + b"\n", one + b"\n\n", b"\xff\n"):
            with self.subTest(data=data), self.assertRaises(model.InputError):
                model.seal(data, "fixture/dataset")

    def test_empty_dataset_is_valid_and_anchor_includes_dataset_ref(self):
        empty = model.seal(b"", "fixture/empty")
        self.assertEqual(empty["records"], [])
        self.assertEqual(empty["head_sha256"], empty["genesis_sha256"])
        self.assertNotEqual(model.seal(b"", "fixture/other")["head_sha256"], empty["head_sha256"])
        self.assertTrue(model.verify(b"", empty, empty["head_sha256"])["valid"])

    def test_header_counts_require_strict_integer_types_and_record_array(self):
        data = wire(fixture()[:1])
        manifest = model.seal(data, "fixture/dataset")
        malformed = {**manifest, "record_count": True, "records": {}}
        report = model.verify(data, malformed, manifest["head_sha256"])
        self.assertEqual(report["blockers"], ["record_count_mismatch", "records_invalid"])

    def test_verify_cli_reports_success_then_failure_without_mutating_inputs(self):
        root = Path(self.enterContext(TemporaryDirectory()))
        data_path = root / "dataset.jsonl"
        manifest_path = root / "manifest.json"
        data = wire(fixture())
        data_path.write_bytes(data)
        with redirect_stdout(StringIO()) as output:
            self.assertEqual(model.main(["seal", str(data_path), "--dataset-ref", "fixture/file"]), 0)
        manifest = json.loads(output.getvalue())
        manifest_path.write_text(output.getvalue(), encoding="utf-8")
        before_manifest = manifest_path.read_bytes()
        for head, verdict in ((manifest["head_sha256"], True), ("a" * 64, False)):
            with self.subTest(head=head), redirect_stdout(StringIO()) as output:
                result = model.main(["verify", str(data_path), str(manifest_path), "--expect-head", head])
                self.assertEqual(result, int(not verdict))
                self.assertIs(json.loads(output.getvalue())["valid"], verdict)
        self.assertEqual(data_path.read_bytes(), data)
        self.assertEqual(manifest_path.read_bytes(), before_manifest)
