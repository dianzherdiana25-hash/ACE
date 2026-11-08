"""Unit tests for Disjunctive Abstract Interpretation via Semantic Trace Partitioning."""
from __future__ import annotations

import unittest
from ace_abstract_interp.disjunctive_domain import (
    DisjunctiveInterpreter,
    DisjunctiveInterval,
    TracePartitionState,
)
from ace_abstract_interp.invariants import Interval


class TestDisjunctiveDomain(unittest.TestCase):
    def test_disjunctive_interval_representation_and_normalization(self):
        # Non-convex interval: [-10, -2] v [2, 10]
        i1 = Interval(low=-10.0, high=-2.0)
        i2 = Interval(low=2.0, high=10.0)
        disj = DisjunctiveInterval((i1, i2))

        self.assertFalse(disj.is_convex)
        self.assertTrue(disj.contains(-5.0))
        self.assertTrue(disj.contains(5.0))
        # Zero is strictly excluded!
        self.assertFalse(disj.contains(0.0))
        self.assertFalse(disj.contains_zero())

        # Overlapping normalization: [1, 4] v [3, 8] -> [1, 8]
        overlap = DisjunctiveInterval((Interval(1.0, 4.0), Interval(3.0, 8.0))).normalize()
        self.assertEqual(len(overlap.intervals), 1)
        self.assertEqual(overlap.intervals[0].low, 1.0)
        self.assertEqual(overlap.intervals[0].high, 8.0)

    def test_zero_false_alarm_in_division(self):
        """Convex interval domain fails on Y in {-2, 2} by computing [-2, 2] (containing 0),
        raising a false division-by-zero alarm. Disjunctive domain proves exact safety.
        """
        # Divisor Y in {-2, 2}
        divisor_disj = DisjunctiveInterval.from_points(-2.0, 2.0)
        numerator = DisjunctiveInterval.from_interval(Interval.point(100.0))

        # 1. Verify zero is NOT contained
        self.assertFalse(divisor_disj.contains_zero())

        # 2. Sound division succeeds with zero false alarm
        result = numerator.safe_div(divisor_disj)
        self.assertIsNotNone(result)
        # Expected outputs: 100 / -2 = -50, 100 / 2 = 50
        self.assertTrue(result.contains(-50.0))
        self.assertTrue(result.contains(50.0))
        self.assertFalse(result.contains(0.0))

        # Contrast with interval that actually contains zero: [-1, 1]
        unsafe_divisor = DisjunctiveInterval.from_interval(Interval(low=-1.0, high=1.0))
        self.assertIsNone(numerator.safe_div(unsafe_divisor))

    def test_disjunctive_join_and_meet(self):
        d1 = DisjunctiveInterval.from_interval(Interval(low=0.0, high=2.0))
        d2 = DisjunctiveInterval.from_interval(Interval(low=8.0, high=10.0))

        # Join preserves non-convex disjunction
        j = d1.join(d2)
        self.assertEqual(len(j.intervals), 2)
        self.assertTrue(j.contains(1.0))
        self.assertTrue(j.contains(9.0))
        self.assertFalse(j.contains(5.0))

        # Meet with [1, 9] yields [1, 2] v [8, 9]
        d3 = DisjunctiveInterval.from_interval(Interval(low=1.0, high=9.0))
        m = j.meet(d3)
        self.assertEqual(len(m.intervals), 2)
        self.assertEqual(m.intervals[0].low, 1.0)
        self.assertEqual(m.intervals[0].high, 2.0)
        self.assertEqual(m.intervals[1].low, 8.0)
        self.assertEqual(m.intervals[1].high, 9.0)

    def test_trace_partition_state_splitting(self):
        state = TracePartitionState()

        # Branch 1 (path_true): x > 0 -> y = 5
        state.add_partition("path_true", {
            "x": DisjunctiveInterval.from_interval(Interval(low=1.0, high=10.0)),
            "y": DisjunctiveInterval.from_interval(Interval.point(5.0)),
        })

        # Branch 2 (path_false): x <= 0 -> y = -5
        state.add_partition("path_false", {
            "x": DisjunctiveInterval.from_interval(Interval(low=-10.0, high=0.0)),
            "y": DisjunctiveInterval.from_interval(Interval.point(-5.0)),
        })

        # Marginal y is {-5, 5}
        marginal_y = state.get_disjunctive_variable("y")
        self.assertTrue(marginal_y.contains(5.0))
        self.assertTrue(marginal_y.contains(-5.0))
        self.assertFalse(marginal_y.contains(0.0))

        # Sound safety verification: zero false alarms
        self.assertTrue(state.is_safe_nonzero("y"))

    def test_automatic_partition_merge_bound(self):
        state = TracePartitionState()
        for i in range(10):
            state.add_partition(f"branch_{i}", {
                "v": DisjunctiveInterval.from_interval(Interval(low=float(i), high=float(i + 1))),
            })

        self.assertEqual(len(state.partitions), 10)
        # Enforce partition budget <= 4
        state.merge_to_limit(max_partitions=4)
        self.assertLessEqual(len(state.partitions), 4)

        # Value coverage is preserved across the merge
        marginal = state.get_disjunctive_variable("v")
        self.assertTrue(marginal.contains(0.5))
        self.assertTrue(marginal.contains(9.5))


if __name__ == "__main__":
    unittest.main()
