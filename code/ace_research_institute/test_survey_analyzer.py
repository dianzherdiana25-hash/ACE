from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._contracts import canonical, identity
from .survey_analyzer import analyze_answers


class SurveyAnalysisTests(unittest.TestCase):
    def test_conflicting_private_and_nonconsented_responses_do_not_inflate_counts(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            rows = [{"id": label, "answer": answer, "consented": consent} for label, answer, consent in (
                ("one", "Jelas sekali.", True), ("two", "Jelas.", True), ("three", "Jelas tetapi lambat.", True),
                ("four", "Lambat.", True), ("five", "Rahasia terlindungi.", False), ("six", "Jelaskan.", True))]
            raw = b"\n".join(map(canonical, rows)) + b"\n"
            (root / "responses.jsonl").write_bytes(raw)
            codes = [{"id": label, "exclusive_group": "reading", "required": [phrase],
                      "excluded": [], "min_hits": 1, "definition_ref": f"fixture:{label}"}
                     for label, phrase in (("clear", "jelas"), ("slow", "lambat"))]
            plan = {"schema": "ace.institute.survey-analysis.v1",
                    "responses": {"path": "responses.jsonl", "sha256": sha256(raw).hexdigest()},
                    "codebook": codes, "redact_below": 2}
            result = analyze_answers(plan, identity(plan), root)
            clear, slow = result["codes"]
            self.assertEqual(clear["count"], 2)
            self.assertIsNone(slow["count"])
            self.assertEqual(result["outcomes"][2]["status"], "ambiguous")
            self.assertEqual(result["outcomes"][4]["status"], "excluded_no_consent")
            self.assertEqual(result["outcomes"][5]["status"], "uncoded")
            self.assertNotIn("Rahasia", str(result))
            self.assertNotIn("slow", str(result["trace"]))
