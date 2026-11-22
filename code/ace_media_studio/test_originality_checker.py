from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._contracts import identity
from ._raster import blank, png
from .originality_checker import check_originality


class OriginalityTests(unittest.TestCase):
    def test_exact_and_similar_files_distinguished_from_same_hash_structure_different_color(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            seen = {}
            for name, size, color in (("source", 24, (200, 120, 54)), ("near", 32, (203, 125, 56)),
                                      ("different", 24, (42, 172, 219))):
                data = png(blank(size, size, color))
                (root / f"{name}.png").write_bytes(data)
                seen[name] = {"path": f"{name}.png", "sha256": sha256(data).hexdigest()}
            plan = {"schema": "ace.media.originality-plan.v1", "candidate": seen["source"],
                    "library": [info | {"id": name, "source_ref": f"fixture:{name}"} for name, info in seen.items()],
                    "max_hamming": 4, "max_color_delta": 7}
            report = check_originality(plan, identity(plan), root)
            self.assertEqual([row["relation"] for row in report["rows"]], ["exact_bytes", "possible_near_duplicate", "distant"])
            self.assertEqual(report["rows"][-1]["dhash_distance"], 0)
            self.assertEqual(report["status"], "review")
