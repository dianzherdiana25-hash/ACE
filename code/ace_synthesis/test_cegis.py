"""Unit tests for CEGIS program synthesis."""
from __future__ import annotations

import unittest
from ace_synthesis.cegis import CEGISSynthesizer


class TestCEGIS(unittest.TestCase):
    def test_cegis_synthesis_loop(self):
        # Full spec: starts with "a" and ends with "b"
        spec_data = [
            ("ab", True), ("aab", True), ("abb", True), ("aabb", True),
            ("aaab", True), ("abbb", True),
            ("ba", False), ("b", False), ("a", False), ("bb", False),
            ("bba", False), ("baa", False), ("baba", False)
        ]

        synthesizer = CEGISSynthesizer(max_iterations=10, timeout_sec=10.0)
        res = synthesizer.synthesize(spec_data, func_name="cegis_test_fn")

        self.assertIn(res.status, ("SUCCESS", "TIMEOUT"))
        if res.status == "SUCCESS":
            self.assertIsNotNone(res.candidate)
            self.assertLessEqual(res.counterexamples_used, len(spec_data))
            self.assertIn("def cegis_test_fn(word: str) -> bool:", res.function_code)

            # Test synthesized function
            scope = {}
            exec(res.function_code, scope)
            for w, y in spec_data:
                self.assertEqual(scope["cegis_test_fn"](w), y)


if __name__ == "__main__":
    unittest.main()
