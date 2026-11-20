"""Uji status tambatan tanpa menulis ke store."""
import unittest
from unittest.mock import Mock

from ace_operational.memory_anchor import check_anchors


class MemoryAnchorTests(unittest.TestCase):
    def setUp(self):
        self.store = Mock()
        self.store.verify_ref.side_effect = {"a": True, "b": True, "c": False}.__getitem__

    def test_all_retrievable(self):
        result = check_anchors(["a", "b"], self.store)
        self.assertEqual(result["score"], 1)
        self.assertEqual(result["status"], "anchored")
        self.assertEqual([row["status"] for row in result["refs"]], ["retrievable"] * 2)

    def test_dangling_and_duplicate(self):
        result = check_anchors(["a", "c", "missing", "a"], self.store)
        self.assertEqual(result["score"], 1 / 3)
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["refs"][-1], {"ref": "missing", "status": "dangling"})
        self.assertEqual(self.store.verify_ref.call_count, 3)

    def test_no_refs(self):
        self.assertEqual(check_anchors([], self.store),
                         {"refs": [], "score": 0, "status": "untethered"})
        self.store.verify_ref.assert_not_called()


if __name__ == "__main__":
    unittest.main()
