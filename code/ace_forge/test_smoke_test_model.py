"""Verifier jendela 60 detik, kelengkapan roster, dan status smoke."""
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_forge import smoke_test_model as model
from ace_forge._forge_io import canonical, identity


ARTIFACT = "a"*64
BEGIN = "2026-11-20T23:59:30Z"
STRUCTURE = {"count": 2, "total": 5}


def probe(key, kind, value):
    return {"id": key, "test_ref": f"fixture/test/{key}", "expected": {"kind": kind, "value": value}}


def answer(key, value, finished):
    return {"id": key, "artifact_sha256": ARTIFACT, "receipt_ref": f"fixture/receipt/{key}",
            "finished_at": finished, "outcome": "answered", "answer": value}


def fixture():
    plan = {"protocol_ref": "fixture/smoke", "artifact_sha256": ARTIFACT, "max_seconds": 60,
            "probes": [probe("numeric", "integer", 1), probe("structure", "json_sha256", identity(STRUCTURE)),
                       probe("text", "exact_text", "a fixture\n")]}
    observed = {"batch_ref": "fixture/probe_batch", "started_at": BEGIN, "observations": [
        answer("numeric", 1, "2026-11-20T23:59:59Z"), answer("structure", STRUCTURE.copy(), "2026-11-21T07:00:00+07:00"),
        answer("text", "a fixture\n", "2026-11-21T00:00:30Z"),
    ]}
    return plan, observed


def assess(plan, evidence):
    return model.assess(plan, evidence, identity(plan))


class SmokeTests(unittest.TestCase):
    def test_all_three_rule_types_pass_at_inclusive_boundary(self):
        plan, evidence = fixture()
        result = assess(plan, evidence)
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["elapsed_microseconds"], 60_000_000)
        self.assertEqual(result["counts"], {"passed": 3, "failed": 0, "incorrect": 0, "timeout": 0, "missing": 0})
        self.assertEqual(result["artifact_sha256"], ARTIFACT)
        self.assertEqual(result["observations_sha256"], identity(evidence))
        self.assertEqual(result["probes"][1]["test_ref"], "fixture/test/structure")
        self.assertEqual(result["probes"][2]["receipt_ref"], "fixture/receipt/text")
        self.assertNotIn("a fixture", canonical(result).decode())

    def test_microsecond_over_window_takes_timeout_despite_correct_answers(self):
        plan, receipts = fixture()
        receipts["observations"][-1]["finished_at"] = "2026-11-21T00:00:30.000001Z"
        result = assess(plan, receipts)
        self.assertEqual(result["elapsed_microseconds"], 60_000_001)
        self.assertEqual(result["status"], "timeout")
        self.assertEqual(result["counts"]["timeout"], 1)

    def test_failed_incorrect_and_missing_remain_distinct(self):
        plan, receipts = fixture()
        rows = receipts["observations"]
        rows[0].update(outcome="failed", answer=None)
        rows[1]["answer"]["count"] = 8
        rows.pop()
        result = assess(plan, receipts)
        self.assertEqual(result["status"], "failed")
        self.assertEqual([row["status"] for row in result["probes"]], ["failed", "incorrect", "missing"])
        self.assertIsNone(result["probes"][2]["receipt_ref"])

    def test_boolean_integer_and_trimmed_text_are_incorrect(self):
        plan, receipts = fixture()
        receipts["observations"][0]["answer"] = True
        receipts["observations"][2]["answer"] = "a fixture"
        result = assess(plan, receipts)
        self.assertEqual(result["counts"]["incorrect"], 2)

    def test_incomplete_is_never_reported_as_pass_or_measured_zero_elapsed(self):
        plan, receipts = fixture()
        receipts["observations"].clear()
        result = assess(plan, receipts)
        self.assertEqual(result["status"], "incomplete")
        self.assertEqual(result["counts"]["missing"], 3)
        self.assertIsNone(result["elapsed_microseconds"])

    def test_validate_receipt_identity_outcome_and_temporal_binding(self):
        for change in ({"id": "unregistered"}, {"artifact_sha256": "0"*64}, {"outcome": "unknown"},
                       {"outcome": "failed"}, {"finished_at": "2026-11-20T23:59:29.999999Z"},
                       {"receipt_ref": "fixture/receipt/structure"}, {"id": "structure"}):
            plan, receipts = fixture()
            receipts["observations"][0].update(change)
            with self.subTest(change=change), self.assertRaisesRegex(model.InputError, "Receipt smoke"):
                assess(plan, receipts)

    def test_protocol_window_cap_is_sixty_and_cannot_be_rewritten_after_anchor(self):
        plan, receipts = fixture()
        anchor = identity(plan)
        for seconds in (61, 0, True):
            plan["max_seconds"] = seconds
            with self.subTest(seconds=seconds), self.assertRaises(model.InputError):
                assess(plan, receipts)
        plan["max_seconds"] = 15
        with self.assertRaisesRegex(model.InputError, "anchor"):
            model.assess(plan, receipts, anchor)
        self.assertEqual(assess(plan, receipts)["counts"]["timeout"], 3)

    def test_probe_roster_is_unambiguous_and_requires_supported_rule(self):
        for field, value in (("id", "text"), ("test_ref", "fixture/test/text"),
                             ("expected", {"kind": "unsupported", "value": 2})):
            plan, receipts = fixture()
            plan["probes"][0][field] = value
            with self.subTest(field=field), self.assertRaises(model.InputError):
                assess(plan, receipts)
        plan, receipts = fixture()
        plan["probes"].clear()
        with self.assertRaisesRegex(model.InputError, "kosong"):
            assess(plan, receipts)

    def test_source_json_equivalent_order_has_same_hash_match(self):
        plan, receipts = fixture()
        receipts["observations"][1]["answer"] = {"total": 5, "count": 2}
        one = assess(plan, receipts)
        receipts["observations"].reverse()
        two = assess(plan, receipts)
        self.assertNotEqual(one.pop("observations_sha256"), two.pop("observations_sha256"))
        self.assertEqual(one, two)

    def test_cli_source_files_and_exit_statuses(self):
        plan, receipts = fixture()
        root = Path(self.enterContext(TemporaryDirectory()))
        path, source = root / "plan.json", root / "receipts.json"
        path.write_bytes(canonical(plan))
        args = [str(path), str(source), "--expect-protocol-sha256", identity(plan)]
        for expected in (0, 1):
            if expected:
                receipts["observations"].pop()
            source.write_bytes(canonical(receipts))
            with redirect_stdout(StringIO()) as out:
                self.assertEqual(model.main(args), expected)
            self.assertEqual(json.loads(out.getvalue()), assess(plan, receipts))
            self.assertEqual(source.read_bytes(), canonical(receipts))
        source.write_text('{"batch_ref":1,"batch_ref":2}')
        with redirect_stderr(StringIO()), self.assertRaises(SystemExit) as failure:
            model.main(args)
        self.assertEqual(failure.exception.code, 2)

    def test_failed_probe_at_the_exact_deadline_remains_failed(self):
        plan, receipts = fixture()
        receipts["observations"][-1].update(outcome="failed", answer=None)
        result = assess(plan, receipts)
        self.assertEqual(result["counts"]["failed"], 1)
        self.assertEqual(result["counts"]["timeout"], 0)
        self.assertEqual(result["status"], "failed")

    def test_finishing_all_probes_at_start_preserves_observed_zero_elapsed(self):
        plan, receipts = fixture()
        for row in receipts["observations"]:
            row["finished_at"] = receipts["started_at"]
        observed = assess(plan, receipts)
        self.assertEqual(observed["elapsed_microseconds"], 0)
        self.assertEqual(observed["status"], "passed")
        self.assertTrue(all(row["finished_at"] is not None for row in observed["probes"]))
        self.assertEqual(observed["counts"]["missing"], 0)
