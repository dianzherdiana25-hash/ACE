"""Uji perubahan gap dengan store fixture."""
import unittest

from ace_operational.director_actions import CloseGap


class FixtureStore:
    def __init__(self):
        self.status = {"gap": "OPEN"}
        self.writes = []
        self.refs = {"r1", "r2"}

    def verify_ref(self, ref):
        return ref in self.refs

    def set_gap_status(self, gap_id, status):
        self.writes.append((gap_id, status))
        self.status[gap_id] = status


class CloseGapTests(unittest.TestCase):
    def test_valid_refs_close_and_undo_reopens(self):
        store = FixtureStore()
        action = CloseGap(store)
        payload = action.execute({"checkpoint": {"gap_id": "gap", "evidence_refs": ["r1", "r2"]}})
        self.assertEqual(store.status, {"gap": "RESOLVED"})
        action.undo(payload)
        self.assertEqual(store.writes, [("gap", "RESOLVED"), ("gap", "OPEN")])

    def test_dangling_or_missing_ref_refuses_without_write(self):
        for refs in (["r1", "dangling"], []):
            with self.subTest(refs=refs):
                store = FixtureStore()
                with self.assertRaises(ValueError):
                    CloseGap(store).execute({"checkpoint": {"gap_id": "gap", "evidence_refs": refs}})
                self.assertEqual(store.writes, [])
                self.assertEqual(store.status, {"gap": "OPEN"})


if __name__ == "__main__":
    unittest.main()
