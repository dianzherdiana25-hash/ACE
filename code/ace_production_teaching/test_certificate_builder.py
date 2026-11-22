from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._contracts import canonical, identity
from .certificate_builder import certify
from .test_tabular_engine import save


class CertificateTests(unittest.TestCase):
    def test_verified_score_and_permission_stand_before_certificate(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            people = []
            for who, score, authorized in (("one", 7500, True), ("two", 7499, True), ("three", 10000, False)):
                proof = {"schema": "ace.production.course-proof.v1", "id": who, "course": "Data kelas",
                         "score_bp": score, "completed": "2025-04-15", "source_ref": "fixture:grade"}
                people.append({"id": who, "display_label": "Label " + who, "authorized": authorized,
                               "achievement": save(root, who + ".json", canonical(proof))})
            plan = {"schema": "ace.production.certificate-plan.v1", "course": "Data kelas", "issuer": "Fixture",
                    "date": "2025-04-18", "passing_bp": 7500, "participants": people, "formats": ["docx"]}
            files, report = certify(plan, identity(plan), root)
            self.assertEqual(set(files), {"one.docx"})
            self.assertEqual([row["id"] for row in report["certified"]], ["one"])
            self.assertEqual({row["reason"] for row in report["held"]}, {"label_not_authorized", "below_passing_score"})
