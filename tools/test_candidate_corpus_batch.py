import json
from pathlib import Path
import tempfile
import unittest

from tools.candidate_corpus_batch import build_batch, main, validate_corpus


class CandidateCorpusBatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.batch = build_batch()

    def test_default_batch_is_repeatable_and_mixed(self):
        self.assertEqual(self.batch, build_batch())
        report = validate_corpus(self.batch["episodes.jsonl"])
        self.assertEqual(report["task_kinds"], {"code": 128, "language": 96})
        self.assertEqual(report["distinct_normalized_prefixes"], 224)
        quality = json.loads(self.batch["quality.json"])
        self.assertEqual(quality["corpus_sha256"], report["corpus_sha256"])
        self.assertEqual(quality["language_samples_verified"], 96)
        self.assertGreaterEqual(len(quality["code_template_families"]), 5)
        self.assertGreaterEqual(len(quality["language_domains"]), 3)

    def test_changed_kind_and_duplicate_key_fail(self):
        row = self.batch["episodes.jsonl"].splitlines()[0]
        with self.assertRaisesRegex(ValueError, "disagree"):
            validate_corpus(row.replace(b'"code"', b'"language"', 1))
        with self.assertRaisesRegex(ValueError, "duplicate JSON key"):
            validate_corpus(b'{"id":"a","id":"b"}')

    def test_reworded_prefix_collision_fails(self):
        row = json.loads(self.batch["episodes.jsonl"].splitlines()[0])
        second = dict(row, id="candidate_code_002", instruction=row["instruction"][:1].lower() + row["instruction"][1:] + " Extra.")
        with self.assertRaisesRegex(ValueError, "duplicate instruction"):
            validate_corpus(json.dumps(row).encode() + b"\n" + json.dumps(second).encode())

    def test_exhaustion_leaves_no_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "new"
            with self.assertRaises(SystemExit):
                main(["generate", str(output), "--language-count", "300"])
            self.assertFalse(output.exists())

    def test_existing_destination_stays_intact(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "new"
            args = ["generate", str(output), "--language-count", "2", "--code-count", "2"]
            self.assertEqual(main(args), 0)
            before = (output / "quality.json").read_bytes()
            with self.assertRaises(SystemExit):
                main(args + ["--seed", "22"])
            self.assertEqual((output / "quality.json").read_bytes(), before)
