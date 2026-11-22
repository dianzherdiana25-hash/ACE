from hashlib import sha256
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile
import unittest

from ._contracts import ResearchError, identity
from .research_archiver import _add, archive, verify
from .test_comparison_analyst import save


class ArchiveTests(unittest.TestCase):
    def test_reproducible_archive_and_independent_verifier_reject_tampering(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            plan = {"schema": "ace.institute.archive-plan.v1", "study": "fixture", "members": [
                save(root, "paper.md", b"Source") | {"target": "sources/paper.md", "role": "source", "source_ref": "fixture:data"},
                save(root, "report.md", b"Answer") | {"target": "reports/report.md", "role": "report", "source_ref": "fixture:paper"}]}
            data, report = archive(plan, identity(plan), root)
            self.assertEqual(data, archive(plan, identity(plan), root)[0])
            self.assertEqual(verify(data, report["archive_sha256"])["verified_bytes"], 12)
            stream = BytesIO()
            with ZipFile(BytesIO(data)) as read_back, ZipFile(stream, "w") as changed:
                for filename in read_back.namelist():
                    _add(changed, filename, b"Change" if filename == "sources/paper.md" else read_back.read(filename))
            corrupt = stream.getvalue()
            with self.assertRaisesRegex(ResearchError, "Hash anggota sources/paper"):
                verify(corrupt, sha256(corrupt).hexdigest())
            plan["members"][0]["target"] = "../paper.md"
            with self.assertRaisesRegex(ResearchError, "bebas lompatan"):
                archive(plan, identity(plan), root)
