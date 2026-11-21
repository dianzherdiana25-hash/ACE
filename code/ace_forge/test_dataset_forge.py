"""Verifier promosi bukti, partisi keluarga, dan keluaran JSONL."""
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from ace_forge import dataset_forge as model
from ace_forge._forge_io import canonical, identity


def source(key, *, family="same", prompt=None, target=None):
    return {"event_id": key, "family_id": family, "task_kind": "fixture-logic", "language": "id",
            "prompt": prompt if prompt is not None else f"Uji kasus {key}.",
            "target": target if target is not None else f"Keluaran {key}."}


def proof(row, *, status="verified", license_id="CC0-1.0"):
    return {"event_id": row["event_id"], "status": status, "payload_sha256": identity(row),
            "evidence_ref": f"fixture/evidence/{row['event_id']}", "license": license_id}


def inputs(*rows):
    refs = {"index_ref": "fixture/index", "records": [proof(row) for row in rows]}
    request = {"examples": list(rows), "allowed_licenses": ["CC0-1.0"], "seed": 52, "held_out_basis_points": 2500}
    return request, refs


class DatasetTests(unittest.TestCase):
    def test_only_verified_unmodified_and_allowed_rows_are_admitted(self):
        rows = [source(key) for key in ("ok", "pending", "no", "tampered", "restricted", "missing")]
        setup, proofs = inputs(*rows)
        proofs["records"][1]["status"] = "pending"
        proofs["records"][2]["status"] = "rejected"
        proofs["records"][4]["license"] = "other"
        proofs["records"].pop()
        setup["examples"][3]["target"] += "Changed."
        examples, report = model.forge(setup, proofs)
        self.assertEqual([item["payload"]["event_id"] for item in examples], ["ok"])
        self.assertEqual({row["event_id"]: row["reason"] for row in report["rejected"]}, {
            "pending": "verification_pending", "no": "verification_rejected", "tampered": "payload_changed",
            "restricted": "license_not_allowed", "missing": "verification_missing",
        })
        self.assertEqual(report["task_kind"], {"fixture-logic": 1})
        self.assertEqual(report["sources"], 6)

    def test_record_hash_and_exact_unicode_payload_are_preserved(self):
        row = source("one", prompt="  Bayangkan aß\nβ.  ", target="Satu\n\nbaris")
        records, _ = model.forge(*inputs(row))
        self.assertEqual(records[0]["payload"], row)
        self.assertEqual(records[0]["provenance"], {
            "index_ref": "fixture/index", "evidence_ref": "fixture/evidence/one",
            "payload_sha256": identity(row), "license": "CC0-1.0",
        })
        self.assertEqual(records[0]["example_id"], f"forge-{identity(row)}")

    def test_prompt_aliases_preserve_only_lowest_event_and_conflicts_reject_entire_bucket(self):
        first, second = source("b", prompt="É  token", target="one"), source("a", prompt="E\u0301 token", target="one")
        conflict_a, conflict_b = source("c", prompt="yang sama", target="Y"), source("d", prompt="yang sama", target="Z")
        records, report = model.forge(*inputs(first, second, conflict_a, conflict_b))
        self.assertEqual([row["payload"]["event_id"] for row in records], ["a"])
        self.assertEqual([(row["event_id"], row["reason"]) for row in report["rejected"]], [
            ("b", "duplicate_prompt"), ("c", "conflicting_prompt"), ("d", "conflicting_prompt"),
        ])
        self.assertEqual(report["rejected"][0]["retained_event"], "a")

    def test_partitions_are_grouped_reproducible_and_support_exact_extremes(self):
        setup, proofs = inputs(*(source(f"id-{index}", family=f"grp-{index % 41}") for index in range(100)))
        setup["held_out_basis_points"] = 5000
        records, report = model.forge(setup, proofs)
        group_split = {}
        for row in records:
            family = row["payload"]["family_id"]
            self.assertEqual(row["split"], group_split.setdefault(family, row["split"]))
        self.assertGreater(report["train"], 0)
        self.assertGreater(report["held_out"], 0)
        for basis_points, target in ((0, "train"), (10_000, "held_out")):
            examples, totals = model.forge({**setup, "held_out_basis_points": basis_points}, proofs)
            self.assertEqual({item["split"] for item in examples}, {target})
            self.assertEqual(totals[target], 100)

    def test_index_is_separate_from_request_and_unmatched_proofs_are_visible(self):
        raw, refs = inputs(source("ok"))
        refs["records"].append(proof(source("unused")))
        self.assertEqual(model.forge(raw, refs)[1]["unused_verifications"], ["unused"])
        with self.assertRaises(model.InputError):
            model.forge({**raw, "inline_verification": refs["records"]}, refs)

    def test_duplicate_hash_status_or_bad_policy_fails_closed(self):
        request, refs = inputs(source("ok"))
        scenarios = (
            ({**request, "examples": request["examples"] * 2}, refs),
            (request, {**refs, "records": refs["records"] * 2}),
            (request, {**refs, "records": [{**refs["records"][0], "status": "yes"}]}),
            (request, {**refs, "records": [{**refs["records"][0], "payload_sha256": "badsum"}]}),
            (request, {**refs, "index_ref": refs["records"][0]["evidence_ref"]}),
            ({**request, "allowed_licenses": []}, refs),
            ({**request, "seed": True}, refs),
        )
        for candidate, independent in scenarios:
            with self.subTest(candidate=candidate, independent=independent), self.assertRaises(model.InputError):
                model.forge(candidate, independent)

    def test_cli_outputs_canonical_jsonl_and_report_for_permuted_inputs(self):
        folder = Path(self.enterContext(TemporaryDirectory()))
        examples = folder / "candidate.json"
        indices = folder / "verified.json"
        request, refs = inputs(source("x"), source("a"))
        args = [str(examples), "--verified-index", str(indices)]
        logs = []
        for _ in range(2):
            examples.write_bytes(canonical(request))
            indices.write_bytes(canonical(refs))
            with redirect_stdout(StringIO()) as output:
                self.assertEqual(model.main(args), 0)
            logs.append(output.getvalue())
            request["examples"].reverse()
            refs["records"].reverse()
        self.assertEqual(logs[0], logs[1])
        with redirect_stdout(StringIO()) as output:
            self.assertEqual(model.main([*args, "--report-only"]), 0)
        self.assertEqual(json.loads(output.getvalue())["examples"], 2)
        self.assertEqual([json.loads(line)["payload"]["event_id"] for line in logs[0].splitlines()], ["a", "x"])

    def test_cli_rejects_ambiguous_json_without_partial_dataset(self):
        folder = Path(self.enterContext(TemporaryDirectory()))
        examples = folder / "candidate.json"
        indices = folder / "verified.json"
        examples.write_bytes(b'{"seed":0,"seed":1}')
        indices.write_bytes(b'{}')
        with redirect_stdout(StringIO()) as output, redirect_stderr(StringIO()) as errors:
            with self.assertRaises(SystemExit) as raised:
                model.main([str(examples), "--verified-index", str(indices)])
        self.assertEqual(raised.exception.code, 2)
        self.assertEqual(output.getvalue(), "")
        self.assertIn("ganda", errors.getvalue())

    def test_limits_are_checked_before_emitting_a_dataset(self):
        request, refs = inputs(source("ok", prompt="a" * 1000))
        with patch.object(model, "MAX_BYTES", 500):
            with self.assertRaisesRegex(model.InputError, "batas byte"):
                model.forge(request, refs)
