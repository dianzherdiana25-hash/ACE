from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._contracts import canonical, identity
from .document_proofreader import proofread
from .test_tabular_engine import save


class ProofTests(unittest.TestCase):
    def test_suggestions_keep_position_and_preserve_fenced_words(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            language = {"schema": "ace.production.word-rules.v1", "languages": {
                "id": [{"wrong": "aktifitas", "replacement": "aktivitas", "source_ref": "fixture:spell"}], "en": []}}
            raw = b"Aktifitas dan dan contoh .\n```\nAktifitas\n```\n"
            plan = {"schema": "ace.production.proof-plan.v1", "draft": save(root, "draft.md", raw),
                    "rules": save(root, "dictionary", canonical(language)), "ignore": [], "language": "id"}
            result = proofread(plan, identity(plan), root)
            self.assertEqual(result["counts"], {"repeated_word": 1, "space_before_punctuation": 1, "word_rule": 1})
            self.assertEqual(result["findings"][0], {"rule": "word_rule", "line": 1, "column": 1,
                                                   "suggested": "Aktivitas", "source_ref": "fixture:spell"})
            self.assertEqual((root / "draft.md").read_bytes(), raw)
