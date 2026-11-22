from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._contracts import ResearchError, identity
from .actor_mapper import map_actors
from .test_comparison_analyst import save


class MappingTests(unittest.TestCase):
    def test_source_spans_and_directed_reachability(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            data = save(root, "partners.md", b"BRAVO mitra Alpha.\nBRAVO mendanai Coffee Lab.\n")
            plan = {"schema": "ace.institute.actor-plan.v1", "reach_from": "alpha",
                    "actors": [{"id": key, "name": name, "aliases": [], "role": "facility",
                                "source_ref": f"fixture:{key}"} for key, name in (
                                    ("alpha", "Alpha"), ("bravo", "Bravo"), ("coffee", "Coffee Lab"), ("out", "Outside"))],
                    "documents": [{"id": "source", **data}],
                    "relations": [{"from": "alpha", "to": "bravo", "kind": "partner", "document": "source", "line": 1},
                                  {"from": "bravo", "to": "coffee", "kind": "funds", "document": "source", "line": 2}]}
            report = map_actors(plan, identity(plan), root)
            self.assertEqual({row["id"]: row["distance_from_focus"] for row in report["actors"]},
                             {"alpha": 0, "bravo": 1, "coffee": 2, "out": None})
            self.assertEqual(report["edges"][1]["evidence"][0]["line"], 2)
            plan["relations"][1]["line"] = 1
            with self.assertRaisesRegex(ResearchError, "kedua aktor"):
                map_actors(plan, identity(plan), root)
