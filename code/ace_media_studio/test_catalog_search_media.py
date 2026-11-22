from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._contracts import ContractError, identity
from .catalog_search_media import search


class MediaSearchTests(unittest.TestCase):
    def test_ranked_transcript_search_source_lines_series_and_tamper(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            items = []
            for key, source, series in (("alpha", "Gelap.\n\nCahaya senja dan cahaya pagi.\n", "science"),
                                        ("beta", "Cahaya ruangan.\n", "history"),
                                        ("gamma", "Kapal dan laut.\n", "history")):
                raw = source.encode()
                name = f"{key}.txt"
                (root / name).write_bytes(raw)
                items.append({"id": key, "title": key, "path": name, "sha256": sha256(raw).hexdigest(),
                              "source_ref": f"fixture:{name}", "series": series, "season": 1})
            plan = {"schema": "ace.media.catalog-plan.v1", "works": items}
            result = search(plan, identity(plan), root, "CAHAYA senja")
            self.assertEqual([r["id"] for r in result["results"]], ["alpha", "beta"])
            self.assertEqual(result["results"][0]["source_ref"], "fixture:alpha.txt")
            self.assertEqual(result["results"][0]["excerpts"], [{"line": 3, "text": "Cahaya senja dan cahaya pagi."}])
            self.assertEqual(search(plan, identity(plan), root, "cahaya", series="history")["matched_works"], 1)
            (root / "beta.txt").write_bytes(b"beda")
            with self.assertRaisesRegex(ContractError, "hash"):
                search(plan, identity(plan), root, "baru")
