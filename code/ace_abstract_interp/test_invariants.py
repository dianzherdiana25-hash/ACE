"""Unit tests for Abstract Interpretation Invariant Analyzer & Synthesizer."""
from __future__ import annotations

import unittest
from ace_abstract_interp.invariants import (
    Interval,
    AbstractState,
    AbstractInterpreter,
    InvariantSynthesizer,
    INF,
    NEG_INF,
)


class TestInvariants(unittest.TestCase):
    def test_interval_lattice_and_galois_properties(self):
        i1 = Interval(low=2, high=5)
        i2 = Interval(low=4, high=8)

        # Join (sqcup)
        j = i1.join(i2)
        self.assertEqual(j.low, 2)
        self.assertEqual(j.high, 8)

        # Meet (sqcap)
        m = i1.meet(i2)
        self.assertEqual(m.low, 4)
        self.assertEqual(m.high, 5)

        # Disjoint meet -> bot
        disjoint = Interval(low=10, high=12)
        bot = i1.meet(disjoint)
        self.assertTrue(bot.is_bot)

        # Containment & subset
        self.assertTrue(i1.contains(3))
        self.assertFalse(i1.contains(1))
        self.assertTrue(m.is_subset(i1))
        self.assertTrue(m.is_subset(i2))

    def test_interval_abstract_arithmetic(self):
        a = Interval(low=1, high=3)
        b = Interval(low=2, high=4)

        # Addition
        add_res = a + b
        self.assertEqual(add_res.low, 3)
        self.assertEqual(add_res.high, 7)

        # Subtraction
        sub_res = a - b
        self.assertEqual(sub_res.low, 1 - 4)  # -3
        self.assertEqual(sub_res.high, 3 - 2)  # 1

        # Multiplication
        mul_res = a * b
        self.assertEqual(mul_res.low, 2)
        self.assertEqual(mul_res.high, 12)

    def test_widening_and_narrowing_operators(self):
        # Widening when upper bound grows
        base = Interval(low=0, high=5)
        grown = Interval(low=0, high=10)
        widened = base.widen(grown)
        self.assertEqual(widened.low, 0)
        self.assertEqual(widened.high, INF)

        # Narrowing when infinite bound meets finite upper bound
        narrowed = widened.narrow(Interval(low=0, high=15))
        self.assertEqual(narrowed.low, 0)
        self.assertEqual(narrowed.high, 15)

    def test_loop_invariant_synthesis_and_bounds_certification(self):
        # Program:
        # x = 0
        # while x < 10:
        #     x = x + 1
        init_state = AbstractState({"x": Interval.point(0)})
        interp = AbstractInterpreter()

        def loop_step(s: AbstractState) -> AbstractState:
            # 1. Guard check: x < 10
            filtered = interp.filter_guard("x", "<", 10, s)
            if filtered.is_bot:
                return AbstractState.bot()
            # 2. Body: x = x + 1
            curr_x = filtered.get("x")
            return filtered.set("x", curr_x + Interval.point(1))

        synthesizer = InvariantSynthesizer(max_widening_steps=5)
        invariant, steps = synthesizer.synthesize_loop_invariant(init_state, loop_step)

        # Invariant should bound x >= 0
        self.assertGreaterEqual(invariant.get("x").low, 0)
        self.assertLessEqual(steps, 5)

        # Certification of safe bounds
        is_safe, interval = synthesizer.certify_bounds(init_state, "x", safe_low=0, safe_high=100)
        self.assertTrue(is_safe)

        # Unsafe bounds detection
        is_safe_bad, _ = synthesizer.certify_bounds(AbstractState({"x": Interval(0, 150)}), "x", safe_low=0, safe_high=100)
        self.assertFalse(is_safe_bad)


if __name__ == "__main__":
    unittest.main()
