"""Edge-case unit tests for ace_code_agent/problem_selector.py."""
from __future__ import annotations

import typing
import unittest

from ace_code_agent.models import ImprovementHypothesis, ResearchProblem
from ace_code_agent.problem_selector import ProblemSelector


class TestProblemSelectorEdgeCases(unittest.TestCase):
    def setUp(self) -> None:
        self.selector = ProblemSelector()

    def test_01_empty_diagnostics_returns_default_latency_problem(self) -> None:
        prob, hyp = self.selector.select_next_problem({})
        self.assertIsInstance(prob, ResearchProblem)
        self.assertIsInstance(hyp, ImprovementHypothesis)
        self.assertEqual(prob.category, "LATENCY_INEFFICIENCY")
        self.assertEqual(prob.problem_id, "prob_general_optimization_0")
        self.assertEqual(hyp.proposed_strategy, "CONSTRAINT_PRUNING")

    def test_02_stagnation_events_positive_selects_representation_bottleneck(self) -> None:
        prob, hyp = self.selector.select_next_problem({"cycle_count": 4, "stagnation_events": 2})
        self.assertEqual(prob.category, "REPRESENTATION_BOTTLENECK")
        self.assertEqual(prob.problem_id, "prob_rep_saturation_4")
        self.assertEqual(prob.priority_score, 0.95)
        self.assertEqual(hyp.proposed_strategy, "MULTI_TASK_COMPOSITE_DISPATCH")

    def test_03_no_validation_improvement_reason_triggers_representation_bottleneck(self) -> None:
        prob, hyp = self.selector.select_next_problem(
            {
                "cycle_count": 9,
                "stagnation_events": 0,
                "common_rejection_reasons": {"NO_VALIDATION_IMPROVEMENT": 3},
            }
        )
        self.assertEqual(prob.category, "REPRESENTATION_BOTTLENECK")
        self.assertEqual(hyp.hypothesis_id, "hyp_expand_dispatch_9")

    def test_04_stagnation_takes_priority_over_unaddressed_tasks(self) -> None:
        prob, _ = self.selector.select_next_problem(
            {
                "cycle_count": 3,
                "stagnation_events": 1,
                "unaddressed_tasks": ["task_k1", "task_k2"],
                "task_failure_counts": {"task_k1": 5},
            }
        )
        self.assertEqual(prob.category, "REPRESENTATION_BOTTLENECK")

    def test_05_unaddressed_tasks_triggers_algorithmic_gap_for_first_entry(self) -> None:
        prob, hyp = self.selector.select_next_problem(
            {
                "cycle_count": 5,
                "stagnation_events": 0,
                "unaddressed_tasks": ["task_j2", "task_k1"],
                "task_failure_counts": {"task_j2": 14},
            }
        )
        self.assertEqual(prob.category, "ALGORITHMIC_GAP")
        self.assertEqual(prob.problem_id, "prob_task_gap_task_j2_5")
        self.assertEqual(prob.priority_score, 0.85)
        self.assertEqual(prob.failure_evidence["failures"], 14)
        self.assertEqual(hyp.proposed_strategy, "LIBRARY_PRIMITIVE_SYNTHESIS")
        self.assertEqual(hyp.problem_id, prob.problem_id)

    def test_06_unaddressed_task_without_failure_count_defaults_to_zero(self) -> None:
        prob, _ = self.selector.select_next_problem(
            {
                "cycle_count": 2,
                "unaddressed_tasks": ["task_k1"],
            }
        )
        self.assertEqual(prob.category, "ALGORITHMIC_GAP")
        self.assertEqual(prob.failure_evidence["failures"], 0)

    def test_07_empty_unaddressed_list_falls_through_to_default(self) -> None:
        prob, _ = self.selector.select_next_problem(
            {
                "cycle_count": 12,
                "stagnation_events": 0,
                "unaddressed_tasks": [],
                "common_rejection_reasons": {"TIMEOUT": 1},
            }
        )
        self.assertEqual(prob.category, "LATENCY_INEFFICIENCY")
        self.assertEqual(prob.problem_id, "prob_general_optimization_12")

    def test_08_negative_stagnation_events_does_not_trigger_bottleneck(self) -> None:
        prob, _ = self.selector.select_next_problem({"stagnation_events": -1})
        self.assertEqual(prob.category, "LATENCY_INEFFICIENCY")

    def test_09_hypothesis_problem_id_always_matches_selected_problem(self) -> None:
        for diag in (
            {"cycle_count": 1, "stagnation_events": 1},
            {"cycle_count": 2, "unaddressed_tasks": ["task_k2"]},
            {"cycle_count": 3},
        ):
            prob, hyp = self.selector.select_next_problem(diag)
            self.assertEqual(hyp.problem_id, prob.problem_id)

    def test_10_target_files_non_empty_for_all_branches(self) -> None:
        for diag in (
            {"stagnation_events": 1},
            {"unaddressed_tasks": ["task_k1"]},
            {},
        ):
            prob, hyp = self.selector.select_next_problem(diag)
            self.assertTrue(prob.target_files)
            self.assertTrue(hyp.target_module)
            self.assertGreater(hyp.expected_metric_gain, 0.0)

    def test_11_priority_order_across_three_problem_types(self) -> None:
        p1, _ = self.selector.select_next_problem({"stagnation_events": 1})
        p2, _ = self.selector.select_next_problem({"unaddressed_tasks": ["t1"]})
        p3, _ = self.selector.select_next_problem({})
        self.assertGreater(p1.priority_score, p2.priority_score)
        self.assertGreater(p2.priority_score, p3.priority_score)

    def test_12_deterministic_outputs_for_identical_inputs(self) -> None:
        diag = {
            "cycle_count": 8,
            "stagnation_events": 0,
            "unaddressed_tasks": ["task_j1"],
            "task_failure_counts": {"task_j1": 12},
        }
        p1, h1 = self.selector.select_next_problem(diag)
        p2, h2 = self.selector.select_next_problem(diag)
        self.assertEqual(p1, p2)
        self.assertEqual(h1, h2)

    def test_13_selection_does_not_mutate_input_diagnostics_dict(self) -> None:
        diag = {
            "cycle_count": 5,
            "stagnation_events": 1,
            "common_rejection_reasons": {"NO_VALIDATION_IMPROVEMENT": 2},
            "unaddressed_tasks": ["task_k1"],
        }
        snapshot = {k: (list(v) if isinstance(v, list) else dict(v) if isinstance(v, dict) else v) for k, v in diag.items()}
        self.selector.select_next_problem(diag)
        self.assertEqual(diag, snapshot)

    def test_14_none_unaddressed_tasks_handled_as_falsy(self) -> None:
        prob, _ = self.selector.select_next_problem({"unaddressed_tasks": None})
        self.assertEqual(prob.category, "LATENCY_INEFFICIENCY")

    def test_15_none_rejection_reasons_or_failures_raises_when_absent_or_used(self) -> None:
        # With stagnation_events=0 and missing common_rejection_reasons -> empty dict default works.
        prob, _ = self.selector.select_next_problem({"stagnation_events": 0})
        self.assertEqual(prob.category, "LATENCY_INEFFICIENCY")

    def test_16_explicit_none_rejection_reasons_triggers_type_error(self) -> None:
        with self.assertRaises(TypeError):
            self.selector.select_next_problem({"common_rejection_reasons": None})

    def test_17_explicit_none_stagnation_events_triggers_type_error(self) -> None:
        with self.assertRaises(TypeError):
            self.selector.select_next_problem({"stagnation_events": None})

    def test_18_large_cycle_count_formatting_preserved(self) -> None:
        prob, hyp = self.selector.select_next_problem({"cycle_count": 999999})
        self.assertTrue(prob.problem_id.endswith("_999999"))
        self.assertTrue(hyp.hypothesis_id.endswith("_999999"))

    def test_19_special_chars_in_task_id_propagated_cleanly(self) -> None:
        prob, hyp = self.selector.select_next_problem({"unaddressed_tasks": ["task-alpha/v2"], "cycle_count": 1})
        self.assertIn("task-alpha/v2", prob.problem_id)
        self.assertIn("task-alpha/v2", hyp.statement)

    def test_20_failure_evidence_contains_diagnostic_counts(self) -> None:
        reasons = {"NO_VALIDATION_IMPROVEMENT": 4, "SYNTAX_ERROR": 1}
        prob, _ = self.selector.select_next_problem({"stagnation_events": 3, "common_rejection_reasons": reasons})
        self.assertEqual(prob.failure_evidence["stagnation_events"], 3)
        self.assertEqual(prob.failure_evidence["rejection_reasons"], reasons)

    def test_21_non_dict_diagnostics_raises_attribute_error(self) -> None:
        with self.assertRaises(AttributeError):
            self.selector.select_next_problem(None)  # type: ignore[arg-type]

    def test_22_suspected_bug_missing_Tuple_import_in_type_hints(self) -> None:
        # Suspected bug in code/ace_code_agent/problem_selector.py:
        # `select_next_problem` return annotation uses `Tuple[...]` without importing `Tuple` from `typing`,
        # causing `typing.get_type_hints` to raise NameError.
        typing.get_type_hints(ProblemSelector.select_next_problem)


if __name__ == "__main__":
    unittest.main()
