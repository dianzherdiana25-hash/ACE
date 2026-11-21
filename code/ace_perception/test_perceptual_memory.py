"""Verifier indeks persepsi terlepas runtime dan recall tertambat."""
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from ace_perception import document_extractor, perceptual_memory as model
from ace_perception.test_document_extractor import FULL, field, image, layout
from ace_perception.test_ocr_engine import font


IMAGE = "a"*64
AUDIO = "b"*64


def record(key, excerpt, date="2026-11-21T01:00:00Z", **overrides):
    values = {"id": key, "modality": "image", "media_sha256": IMAGE, "observed_at": date,
              "receipt_ref": f"fixture/receipt/{key}", "location": [5, 10, 30, 30], "excerpt": excerpt}
    return {**values, **overrides}


def fixture():
    return [
        record("a", "Café biru", "2026-11-21T08:00:00+07:00"),
        record("b", "Café merah"),
        record("c", "cafe biru", "2026-11-22T00:00:00Z", modality="audio",
               media_sha256=AUDIO, location=[12_000, 24_000]),
        record("d", "CAFÉ BIRU", "2026-11-20T00:00:00Z", location=[4, 0, 12, 12]),
    ]


def search(records, query, **filters):
    index = model.catalog(records)
    return model.recall(index, index["head_sha256"], query, **filters)


class PerceptualMemoryTests(unittest.TestCase):
    def test_casefold_and_nfc_with_stable_ranking_and_source_pointers(self):
        result = search(fixture(), "BIRU CAFE\u0301 biru")
        matches = result["results"]
        self.assertEqual([row["id"] for row in matches], ["a", "d", "c", "b"])
        self.assertEqual([row["overlap"] for row in matches], [2, 2, 1, 1])
        self.assertEqual(matches[0]["matched_terms"], ["biru", "café"])
        self.assertEqual(matches[0]["other_receipt_refs"], ["fixture/receipt/b"])
        self.assertEqual(matches[0]["other_receipt_count"], 1)
        self.assertEqual(matches[0]["status"], "conflicting_receipts")
        self.assertEqual(matches[1]["status"], "matched")
        self.assertEqual(matches[2]["location"], [12_000, 24_000])
        self.assertEqual(matches[0]["observed_at"], "2026-11-21T01:00:00+00:00")
        self.assertEqual(len(matches[0]["record_sha256"]), 64)

    def test_replay_rejects_record_edit_reorder_and_full_tamper_rehashed_under_old_head(self):
        index = model.catalog(fixture())
        head = index["head_sha256"]
        with self.assertRaisesRegex(ValueError, "anchor"):
            model.inspect({**index, "entries": index["entries"][::-1]}, head)
        index["entries"][0]["record"]["excerpt"] += " REPLACED"
        with self.assertRaisesRegex(ValueError, "anchor"):
            model.inspect(index, head)
        changed = model.catalog([row["record"] for row in index["entries"]])
        with self.assertRaisesRegex(ValueError, "anchor"):
            model.inspect(changed, head)

    def test_same_time_overlap_prefers_id_and_respects_bounds_filters_and_limit(self):
        report = search(fixture(), "café", modality="image", limit=1,
                        since="2026-11-21T01:00:00Z", until="2026-11-21T01:00:00Z")
        self.assertEqual(report["matched"], 2)
        self.assertEqual([row["id"] for row in report["results"]], ["a"])
        self.assertEqual(search(fixture(), "biru", modality="audio")["results"][0]["id"], "c")
        self.assertEqual(search(fixture(), "unset")["results"], [])

    def test_conflict_keeps_nonmatching_and_older_receipt_pointer(self):
        report = search(fixture(), "merah", since="2026-11-21T01:00:00Z")
        winner, = report["results"]
        self.assertEqual(winner["status"], "conflicting_receipts")
        self.assertEqual(winner["other_receipt_refs"], ["fixture/receipt/a"])

    def test_large_equivalent_group_limits_related_receipts_without_hiding_count(self):
        records = [record(f"r{index:03d}", "Café  BIRU" if index % 2 else "cafe\u0301 biru")
                   for index in range(45)]
        first = search(records, "biru", limit=1)["results"][0]
        self.assertEqual(first["other_receipt_count"], 44)
        self.assertEqual(first["status"], "matched")
        self.assertEqual(len(first["other_receipt_refs"]), model.MAX_RELATED_REFS)
        self.assertNotIn(first["receipt_ref"], first["other_receipt_refs"])

    def test_invalid_record_locator_duplicate_id_source_and_stamps_close(self):
        first = fixture()[0]
        for changes in ({"location": [0, 1, 0, 2]}, {"location": [2, True, 3, 6]}, {"location": [0, 1]},
                        {"observed_at": "2026-11-21T00:00:00"}, {"media_sha256": "z"*64}, {"excerpt": " \n"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                model.catalog([{**first, **changes}])
        with self.assertRaisesRegex(ValueError, "ganda"):
            model.catalog([first, record("b", "new", receipt_ref=first["receipt_ref"])])

    def test_real_document_claim_roundtrips_into_readonly_recall(self):
        scan = image("HA HOT")
        output = document_extractor.extract(scan, font(FULL), layout(field("subject", "HA ")))
        claim, = output["claims"]
        item = record("subject", claim["value"], media_sha256=output["image_sha256"], location=claim["evidence"][0]["box"])
        result, = search([item], "hot")["results"]
        self.assertEqual(result["media_sha256"], output["image_sha256"])
        self.assertEqual(result["location"], [3, 1, 35, 8])
        self.assertEqual(result["receipt_ref"], item["receipt_ref"])

    def test_cli_creates_canonical_index_then_uses_anchor_to_search(self):
        temp = Path(self.enterContext(TemporaryDirectory()))
        records, index = temp/"records.json", temp/"index.json"
        records.write_bytes(model._canonical(fixture()))
        cmd = [sys.executable, "-m", "ace_perception.perceptual_memory"]
        result = subprocess.run([*cmd, "index", str(records)], capture_output=True, check=True)
        index.write_bytes(result.stdout)
        obj = json.loads(result.stdout)
        search_result = subprocess.run([*cmd, "search", str(index), "biru", "--expect-head", obj["head_sha256"],
                                        "--modality", "audio"], capture_output=True, check=True)
        self.assertEqual(json.loads(search_result.stdout), search(fixture(), "biru", modality="audio"))
        self.assertEqual(records.read_bytes(), model._canonical(fixture()))
