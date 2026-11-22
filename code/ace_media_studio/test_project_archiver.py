from hashlib import sha256
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZipFile

from ._contracts import ContractError, identity
from .project_archiver import _member, package, verify_archive


class ArchiveTests(unittest.TestCase):
    def test_archive_preserves_reproducibility_and_detects_tamper_and_path_escape(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            files = {"recipe": b'{"frames":12}\n', "artifact": b"local-artifact"}
            members = []
            for name, data in files.items():
                (root / name).write_bytes(data)
                members.append({"source_path": name, "archive_path": f"staged/{name}",
                                "sha256": sha256(data).hexdigest(),
                                "role": "recipe" if name == "recipe" else "output", "source_ref": "fixture:bundle"})
            plan = {"schema": "ace.media.archive-plan.v1", "project": "fixture", "members": members}
            data, report = package(plan, identity(plan), root)
            self.assertEqual(data, package(plan, identity(plan), root)[0])
            self.assertEqual(verify_archive(data, report["archive_sha256"])["members"], 2)
            changed = BytesIO()
            with ZipFile(BytesIO(data)) as source, ZipFile(changed, "w") as output:
                for item in source.namelist():
                    payload = source.read(item)
                    _member(output, item, b"x" + payload[1:] if item == "staged/artifact" else payload)
            bad = changed.getvalue()
            with self.assertRaisesRegex(ContractError, "Hash berbeda untuk staged/artifact"):
                verify_archive(bad, sha256(bad).hexdigest())
            plan["members"][0]["archive_path"] = "../outside"
            with self.assertRaisesRegex(ContractError, "tidak sah"):
                package(plan, identity(plan), root)
