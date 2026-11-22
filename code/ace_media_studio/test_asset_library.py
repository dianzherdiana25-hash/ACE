from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._contracts import ContractError, identity
from .asset_library import collect, verify_library


class LibraryTests(unittest.TestCase):
    def test_dedup_provenance_inverse_verification_and_tamper_detection(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            content = b"Audio script\nLine two\n"
            path = source / "text.txt"
            path.write_bytes(content)
            anchor = sha256(content).hexdigest()
            entry = {"kind": "text", "path": "text.txt", "sha256": anchor,
                     "source_ref": "fixture:draft", "license_ref": "fixture:terms", "tags": ["scene", "scene"]}
            plan = {"schema": "ace.media.library-plan.v1", "id": "local", "max_total_bytes": 30,
                    "items": [entry | {"id": "before"}, entry | {"id": "after", "source_ref": "fixture:review"}]}
            index, objects = collect(plan, identity(plan), source)
            self.assertEqual(objects, {anchor: content})
            self.assertEqual(index["unique_bytes"], len(content))
            self.assertEqual(index["assets"][0]["source_ref"], "fixture:review")
            self.assertEqual(index["assets"][0]["measurement"], {"lines": 2})
            store = root / "store"
            (store / "objects").mkdir(parents=True)
            (store / "objects" / anchor).write_bytes(content)
            self.assertTrue(verify_library(index, identity(index), store)["ok"])
            (store / "objects" / anchor).write_bytes(content + b"!")
            problems = verify_library(index, identity(index), store)
            self.assertFalse(problems["ok"])
            self.assertEqual({row["id"] for row in problems["findings"]}, {"before", "after", None})
            plan["max_total_bytes"] = 8
            with self.assertRaisesRegex(ContractError, "anggaran"):
                collect(plan, identity(plan), source)
