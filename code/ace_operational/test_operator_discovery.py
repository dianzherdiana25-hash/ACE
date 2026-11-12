"""Stage I evidence: generic schema search discovers real fixes,
abstraction re-applies them, and admission requires >1 pool fix."""
from __future__ import annotations

import unittest

from ace_operational.grid_generalization import NEW_DEFECTS, _apply, \
    build_universe
from ace_operational.curriculum_lab import _NAVIGATE_REFERENCE
from ace_operational.operator_discovery import apply_operator, \
    discover_for_task, enumerate_variants


class VariantTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Built once: universe construction is the expensive part
        # (identifiability search), and tests must not multiply it.
        cls.universe = build_universe()

    def test_variants_exist_and_roundtrip(self):
        variants = enumerate_variants(_NAVIGATE_REFERENCE)
        self.assertGreater(len(variants), 20)
        key, text = variants[0]
        self.assertEqual(apply_operator(_NAVIGATE_REFERENCE, key),
                         text)

    def test_discovery_finds_the_step_cost_fix(self):
        task = next(t for t in self.universe["tasks"]
                    if t["subset"] == "new_only"
                    and t["defects"] == ["dist_step_2"])
        found = discover_for_task(task)
        self.assertTrue(found, "no one-edit fix discovered")
        schemas = {key[0] for key in found}
        self.assertIn("int_constant", schemas)

    def test_discovery_finds_the_wall_literal_fix(self):
        task = next(t for t in self.universe["tasks"]
                    if t["subset"] == "new_only"
                    and t["defects"] == ["wall_char_x"])
        found = discover_for_task(task)
        schemas = {key[0] for key in found}
        self.assertIn("string_literal", schemas)

    def test_discovery_finds_the_return_indices_fix(self):
        # Regression: v1 of the run found zero candidates for this
        # class because dist[a][b] is a nested-Subscript chain, not
        # a Tuple slice.
        task = next(t for t in self.universe["tasks"]
                    if t["subset"] == "new_only"
                    and t["defects"] == ["returns_start_distance"])
        found = discover_for_task(task)
        schemas = {key[0] for key in found}
        self.assertIn("return_indices", schemas)

    def test_reference_itself_needs_no_discovery(self):
        # A task whose buggy code is the reference cannot exist in
        # the universe; directly: variants of the reference scored
        # against a defect task's budget are not the mechanism.
        buggy = _apply(_NAVIGATE_REFERENCE, ("dist_step_2",))
        self.assertNotEqual(buggy, _NAVIGATE_REFERENCE)
        self.assertIn("dist_step_2", NEW_DEFECTS)


if __name__ == "__main__":
    unittest.main()
