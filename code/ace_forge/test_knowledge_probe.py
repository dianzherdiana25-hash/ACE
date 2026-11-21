"""Verifier skor domain, kunci yang tidak terekspos, dan observasi absen."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_forge import knowledge_probe as model
from ace_forge._forge_io import canonical, identity
from ace_forge.test_forgetting_guard import q


ARTIFACT = "f" * 64


def question(key, domain, mode, answers):
    return {"id": key, "domain": domain, "mode": mode, "answers": answers, "prompt_ref": f"fixture/question/{key}"}


def answer(key, response):
    return {"id": key, "artifact_sha256": ARTIFACT, "response": response, "receipt_ref": f"fixture/receipt/{key}"}


def fixture():
    return ({"protocol_ref": "fixture/probe", "artifact_sha256": ARTIFACT, "minimum_observed": 1, "questions": [
                question("a", "number", "integer", [239]),
                question("b", "number", "integer", [71]),
                question("c", "number", "integer", [52]),
                question("d", "word", "folded_text", ["café noir", "kopi hitam"]),
                question("e", "unknown", "exact", ["TEST-HELD-SECRET-WORD"]),
            ]}, [answer("a", "239"), answer("b", "72"), answer("c", "052"),
                 answer("d", "  CAFE\u0301   NOIR\n")])


def read(question, observations):
    return model.probe(question, observations, identity(question))


class KnowledgeTests(unittest.TestCase):
    def test_probe_grades_each_domain_with_separate_coverage_and_macro(self):
        result = read(*fixture())
        total = result["summary"]
        self.assertEqual(total["correct"], 2)
        self.assertEqual(total["incorrect"], 1)
        self.assertEqual(total["invalid_format"], 1)
        self.assertEqual(total["missing"], 1)
        self.assertEqual(total["coverage"], q(4, 5))
        self.assertEqual(total["accuracy"], q(1, 2))
        self.assertEqual(result["macro"], {
            "scored_domains": 2, "unknown_domains": 1, "mean_accuracy": q(2, 3),
            "minimum_accuracy": q(1, 3), "maximum_accuracy": q(1),
        })
        self.assertEqual([row["id"] for row in result["records"]], list("abcde"))
        self.assertEqual(result["records"][-1]["outcome"], "missing")
        self.assertIsNone(result["records"][-1]["receipt_ref"])

    def test_output_omits_raw_answers_and_keys_and_keeps_receipt_provenance(self):
        report = read(*fixture())
        payload = canonical(report)
        for phrase in (b"TEST-HELD-SECRET-WORD", b"kopi hitam", b"NOIR", b'"response"', b'"answers"'):
            self.assertNotIn(phrase, payload)
        self.assertEqual(report["records"][3]["prompt_ref"], "fixture/question/d")
        self.assertEqual(report["records"][3]["receipt_ref"], "fixture/receipt/d")

    def test_exact_probe_preserves_case_and_whitespace_unless_folded(self):
        raw, answers = fixture()
        raw["questions"] = [question("a", "literal", "exact", ["hello ", "Hai"])]
        for actual, expected in (("hello ", "correct"), ("hello", "incorrect"),
                                 ("hai", "incorrect"), ("Hai", "correct")):
            with self.subTest(actual=actual):
                row, = read(raw, [answer("a", actual)])["records"]
                self.assertEqual(row["outcome"], expected)

    def test_integral_format_does_not_convert_decimal_boolean_or_unicode(self):
        raw, _ = fixture()
        raw["questions"] = [question("a", "numeric", "integer", [0, -4, 10**12])]
        types = [("0", "correct"), ("-0", "invalid_format"), ("\t-4\n", "correct"),
                 ("0.0", "invalid_format"), ("+0", "invalid_format"), ("０", "invalid_format"),
                 ("1000000000000", "correct"), ("1000000000001", "invalid_format"),
                 (False, "invalid_format"), ("4", "incorrect"), ("", "invalid_format"), (None, "invalid_format")]
        for value, expected in types:
            with self.subTest(value=value):
                actual = read(raw, [answer("a", value)])["records"][0]["outcome"]
                self.assertEqual(actual, expected)

    def test_minimum_sample_is_applied_per_domain_separately(self):
        raw, observations = fixture()
        raw["minimum_observed"] = 2
        report = read(raw, observations)
        self.assertEqual(report["summary"]["status"], "scored")
        domains = {row["domain"]: row for row in report["domains"]}
        self.assertIsNone(domains["word"]["accuracy"])
        self.assertEqual(domains["word"]["correct"], 1)
        self.assertEqual(report["macro"]["mean_accuracy"], q(1, 3))

    def test_no_results_does_not_generate_numeric_accuracy(self):
        raw, _ = fixture()
        result = read(raw, [])
        self.assertEqual(result["summary"]["coverage"], q(0))
        self.assertIsNone(result["summary"]["accuracy"])
        self.assertIsNone(result["macro"]["mean_accuracy"])

    def test_malformed_roster_key_and_wrong_artefact_receipts_are_refused(self):
        raw, observations = fixture()
        invalid = (question("a", "repeat", "exact", ["a"]),
                   question("f", "empty", "exact", []),
                   question("f", "fold", "folded_text", ["case", "CASE"]),
                   question("f", "illegal", "integer", [True]))
        for row in invalid:
            with self.subTest(row=row), self.assertRaises(model.InputError):
                read({**raw, "questions": [*raw["questions"], row]}, observations)
        for receipt in (answer("unknown-id", "0"), observations[0], {**answer("e", "kunci"), "artifact_sha256": "a" * 64}):
            with self.subTest(receipt=receipt), self.assertRaises(model.InputError):
                read(raw, [*observations, receipt])

    def test_key_change_breaks_protocol_anchor_even_with_valid_format(self):
        raw, answers = fixture()
        expected = identity(raw)
        raw["questions"][0]["answers"] = [7]
        with self.assertRaisesRegex(model.InputError, "anchor"):
            model.probe(raw, answers, expected)

    def test_cli_reports_deterministic_observation_snapshot(self):
        raw, answers = fixture()
        root = Path(self.enterContext(TemporaryDirectory()))
        p, obs = root / "protocol.json", root / "recorded.json"
        p.write_bytes(canonical(raw))
        obs.write_bytes(canonical(answers))
        with redirect_stdout(StringIO()) as result:
            self.assertEqual(model.main([str(p), str(obs), "--expect-protocol-sha256", identity(raw)]), 0)
        self.assertEqual(json.loads(result.getvalue()), read(raw, answers))
        self.assertEqual(obs.read_bytes(), canonical(answers))

    def test_sufficient_failed_answers_report_real_zero_accuracy(self):
        raw, _ = fixture()
        raw["questions"] = [question("a", "number", "integer", [-100])]
        self.assertEqual(read(raw, [answer("a", "42")])["summary"]["accuracy"], q(0))

    def test_observation_permutation_retains_scores_but_snapshot_digest_tracks_order(self):
        raw, observations = fixture()
        first = read(raw, observations)
        reversed_ = read(raw, observations[::-1])
        self.assertNotEqual(first.pop("observation_sha256"), reversed_.pop("observation_sha256"))
        self.assertEqual(first, reversed_)

    def test_explicit_alias_can_match_after_unicode_folding_without_a_substring_guess(self):
        raw, _ = fixture()
        raw["questions"] = [question("term", "language", "folded_text", ["Straße", "jalan"])]
        for answer_text, verdict in (("STRASSE", "correct"), ("JALAN", "correct"), ("jalan terus", "incorrect")):
            with self.subTest(answer_text=answer_text):
                report = read(raw, [answer("term", answer_text)])
                self.assertEqual(report["records"][0]["outcome"], verdict)

    def test_overlong_or_null_marked_reply_cannot_inflate_valid_coverage_score(self):
        raw, _ = fixture()
        for response in ("x" * 2001, "239\x00"):
            parsed = read(raw, [answer("a", response)])
            self.assertEqual(parsed["summary"]["invalid_format"], 1)
            self.assertEqual(parsed["summary"]["accuracy"], q(0))
