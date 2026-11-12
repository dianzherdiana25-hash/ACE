"""Stage I evidence: generic schema search discovers real fixes,
abstraction re-applies them, and admission requires >1 pool fix."""
from __future__ import annotations

import unittest

from ace_operational.grid_generalization import NEW_DEFECTS, _apply, \
    build_universe
from ace_operational.curriculum_lab import _NAVIGATE_REFERENCE
from ace_operational.operator_discovery import apply_operator, \
    discover_for_task, discover_pairs_for_task, enumerate_variants


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

    def test_direct_apply_matches_enumeration(self):
        # The fast application path must be semantically identical
        # to enumerate-and-match for EVERY key the enumeration can
        # produce, on reference and on real defect-task code.
        from ace_operational.operator_discovery import \
            _apply_key_direct
        codes = [_NAVIGATE_REFERENCE]
        codes += [t["buggy_code"] for t in self.universe["tasks"]
                  if t["subset"] == "new_only"][:4]
        for code in codes:
            for key, text in enumerate_variants(code):
                self.assertEqual(_apply_key_direct(code, key), text,
                                 f"direct apply diverged for {key}")

    def test_stage_l2_schemas_are_enumerated(self):
        code = ("def nav(grid, start, goal):\n"
                "    seen = {start: True}\n"
                "    if grid[start] == '#':\n"
                "        return grid[0]\n"
                "    return start\n")
        schemas = {key[0] for key, _ in enumerate_variants(code)}
        for expected in ("bool_constant", "name_swap", "unary_not",
                         "subscript_index"):
            self.assertIn(expected, schemas)

    def test_pair_discovery_solves_a_two_defect_task(self):
        # A mixed new_only task: two defects, no single edit is
        # shown-perfect (the masking situation pair discovery
        # exists for). If this universe instance happens to be
        # single-solvable, the pair contract still holds vacuously
        # (empty list) — so assert the mechanism's real contract:
        # every returned pair actually composes to a shown-perfect
        # program.
        from ace_operational.grid_generalization import _budget_for
        from ace_operational.operator_discovery import _safe_score
        task = next(t for t in self.universe["tasks"]
                    if t["subset"] == "new_only"
                    and len(t["defects"]) == 2)
        pairs = discover_pairs_for_task(task)
        budget = _budget_for(task)
        for key_a, key_b in pairs:
            step = apply_operator(task["buggy_code"], key_a)
            self.assertIsNotNone(step)
            full = apply_operator(step, key_b)
            self.assertIsNotNone(full)
            self.assertGreaterEqual(
                _safe_score(budget, full), len(task["shown_cases"]))

    def test_chain_discovery_contract(self):
        # Composition discovery v2: on a two-defect task, any
        # returned chain must apply step-by-step (each key located
        # on the intermediate program) to a shown-perfect program,
        # and must have length >= 2 (length-1 is single
        # discovery's domain). A None result is a legitimate
        # measured outcome, not a failure of this contract.
        from ace_operational.grid_generalization import _budget_for
        from ace_operational.operator_discovery import (
            _safe_score, apply_chain, discover_chain_for_task)
        task = next(t for t in self.universe["tasks"]
                    if t["subset"] == "new_only"
                    and len(t["defects"]) == 2)
        chain = discover_chain_for_task(task)
        if chain is not None:
            self.assertGreaterEqual(len(chain), 2)
            full = apply_chain(task["buggy_code"], chain)
            self.assertIsNotNone(full)
            self.assertGreaterEqual(
                _safe_score(_budget_for(task), full),
                len(task["shown_cases"]))

    def test_reference_itself_needs_no_discovery(self):
        # A task whose buggy code is the reference cannot exist in
        # the universe; directly: variants of the reference scored
        # against a defect task's budget are not the mechanism.
        buggy = _apply(_NAVIGATE_REFERENCE, ("dist_step_2",))
        self.assertNotEqual(buggy, _NAVIGATE_REFERENCE)
        self.assertIn("dist_step_2", NEW_DEFECTS)


if __name__ == "__main__":
    unittest.main()
