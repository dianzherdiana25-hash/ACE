"""Verifier presedensi waktu and cap keputusan foto."""
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_perception import photo_sequencer as model


def time(n):
    return f"2026-11-21T00:00:{n:02d}Z"


class PhotoTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(TemporaryDirectory()))
        self.plan = {"schema": "ace.perception-photo-sequence.v1", "series_ref": "fixture/series",
                     "photos": [], "constraints": []}

    def add(self, key, interval):
        payload = f"fixture bytes for photo {key}".encode()
        path = self.root/(key+".pgm")
        path.write_bytes(payload)
        timestamp = {"earliest": time(interval[0]), "latest": time(interval[1]),
                     "source_ref": f"fixture/time/{key}"} if interval is not None else None
        self.plan["photos"].append({"id": key, "path": path.name, "sha256": sha256(payload).hexdigest(),
                                    "timestamp": timestamp, "bytes": len(payload)})

    def read(self):
        return model.sequence(self.root, model._canonical(self.plan), model._sha(self.plan))

    def test_distinct_intervals_constrain_order_and_conflicts_block_it(self):
        self.add("c", (8, 9))
        self.add("b", (5, 6))
        self.add("a", (0, 4))
        report = self.read()
        self.assertEqual(report["status"], "ordered")
        self.assertEqual(report["order"], ["a", "b", "c"])
        self.assertEqual(report["precedence"][0]["evidence"], [{"kind": "disjoint_time",
                                                               "refs": ["fixture/time/a", "fixture/time/b"]}])
        self.plan["constraints"] = [{"before": "c", "after": "a", "source_ref": "fixture/contradiction"}]
        held = self.read()
        self.assertEqual(held["status"], "contradictory")
        self.assertIsNone(held["order"])
        self.assertEqual(held["unresolved"], ["a", "b", "c"])

    def test_adjacent_boundary_unknown_time_and_explicit_constraint(self):
        self.add("a", (0, 4))
        self.add("b", (4, 6))
        self.add("c", None)
        report = self.read()
        self.assertEqual(report["status"], "ambiguous")
        self.assertEqual(report["decisions"][0]["possible_here"], ["a", "b", "c"])
        self.assertIsNone(report["photos"][2]["timestamp"])
        self.plan["constraints"] = [{"before": "a", "after": "b", "source_ref": "fixture/next"},
                                    {"before": "b", "after": "c", "source_ref": "fixture/final"}]
        self.assertEqual(self.read()["status"], "ordered")

    def test_source_bytes_and_plan_anchor_are_checked(self):
        self.add("a", (3, 4))
        (self.root/"a.pgm").write_bytes(b"altered")
        with self.assertRaisesRegex(ValueError, "Hash byte"):
            self.read()
        with self.assertRaisesRegex(ValueError, "anchor"):
            model.sequence(self.root, model._canonical(self.plan), "0"*64)
