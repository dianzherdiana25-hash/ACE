"""AST-isolated independent terminal verification suite for all 18 unseen target units.

STRICT CUSTODY INVARIANT:
- This module MUST NEVER be imported by `corpus.py`, `sandbox.py`, `operators.py`,
  `represent.py`, `memory.py`, `engine.py`, or `__init__.py`.
- Only `runner.py`, `verify.py`, and `test_repair.py` may import `evaluator.py`,
  strictly after candidate selection and staging decisions are frozen.
- Executes candidate patches exclusively inside `sandbox.run_dev_suite` (never `exec` in parent).
"""
from __future__ import annotations

from typing import Any

from .corpus import DevTestCase, sha256_digest
from .sandbox import run_dev_suite

TERMINAL_SUITES: dict[str, tuple[DevTestCase, ...]] = {
    "T01_binary_search_index": (
        DevTestCase("t_singleton_found", "call", ([42], 42), 0),
        DevTestCase("t_singleton_missing", "call", ([42], 99), -1),
        DevTestCase("t_leftmost_neg", "call", ([-20, -10, 0, 10, 20, 30], -20), 0),
        DevTestCase("t_rightmost_pos", "call", ([-20, -10, 0, 10, 20, 30], 30), 5),
        DevTestCase("t_interior_even", "call", ([-20, -10, 0, 10, 20, 30], 10), 3),
        DevTestCase("t_gap_miss", "call", ([-20, -10, 0, 10, 20, 30], 15), -1),
        DevTestCase("t_unsorted_guard", "call", ([3, 1, 2], 1), -1),
        DevTestCase("t_two_elem_second", "call", ([11, 22], 22), 1),
    ),
    "T02_interior_local_maxima": (
        DevTestCase("t_too_short", "call", ([1, 9],), []),
        DevTestCase("t_three_elem_peak", "call", ([2, 8, 3],), [1]),
        DevTestCase("t_last_interior_peak", "call", ([1, 3, 2, 9, 4],), [1, 3]),
        DevTestCase("t_descending", "call", ([9, 5, 1],), []),
        DevTestCase("t_ascending", "call", ([1, 5, 9],), []),
        DevTestCase("t_signed_triple_peaks", "call", ([-5, -1, -4, 0, -2, 3, 1],), [1, 3, 5]),
        DevTestCase("t_flat_plateau", "call", ([2, 5, 5, 2],), []),
        DevTestCase("t_alternating_saw", "call", ([0, 2, 1, 2, 0, 2, 1],), [1, 3, 5]),
    ),
    "T03_trimmed_floor_mean": (
        DevTestCase("t_empty_trim_one", "call", ([], 1), 0),
        DevTestCase("t_empty_trim_five", "call", ([], 5), 0),
        DevTestCase("t_single_no_trim", "call", ([9], 0), 9),
        DevTestCase("t_single_overtrim", "call", ([9], 1), 9),
        DevTestCase("t_extreme_tails", "call", ([-100, 10, 20, 30, 500], 1), 20),
        DevTestCase("t_trim_two_each_side", "call", ([-100, -50, 10, 20, 30, 40, 200, 900], 2), 25),
        DevTestCase("t_constant_samples", "call", ([7, 7, 7, 7], 1), 7),
        DevTestCase("t_negative_trim_fallback", "call", ([4, 8, 12], -1), 8),
    ),
    "T04_parse_env_entries": (
        DevTestCase("t_query_params_url", "call", (["URL=https://h.io/p?a=1&b=2"],), {"URL": "https://h.io/p?a=1&b=2"}),
        DevTestCase("t_semicolon_and_multi_eq", "call", (["  ; comment", "  ", "KEY = x=y=z "],), {"KEY": "x=y=z"}),
        DevTestCase("t_empty_rhs", "call", (["EMPTY_VAL="],), {"EMPTY_VAL": ""}),
        DevTestCase("t_override_key", "call", (["A=1", "A=2=3"],), {"A": "2=3"}),
        DevTestCase("t_missing_eq_raises", "call", (["NO_DELIM"],), expected_exc="ValueError"),
        DevTestCase("t_blank_key_raises", "call", ([" =bad"],), expected_exc="ValueError"),
        DevTestCase("t_double_eq_padding", "call", (["K1=v1", "# skip", "K2=a==b=="],), {"K1": "v1", "K2": "a==b=="}),
        DevTestCase("t_comments_only", "call", (["   # only comment   "],), {}),
    ),
    "T05_parse_version_triple": (
        DevTestCase("t_crlf_padded", "call", (" 3.0.12\r\n",), (3, 0, 12)),
        DevTestCase("t_all_zeros_padded", "call", ("\n\t0.0.0  ",), (0, 0, 0)),
        DevTestCase("t_large_numbers", "call", ("  10.25.99 ",), (10, 25, 99)),
        DevTestCase("t_two_parts_raises", "call", ("1.2",), expected_exc="ValueError"),
        DevTestCase("t_leading_zero_raises", "call", ("01.2.3",), expected_exc="ValueError"),
        DevTestCase("t_four_parts_raises", "call", ("1.2.3.4",), expected_exc="ValueError"),
        DevTestCase("t_blank_raises", "call", ("   ",), expected_exc="ValueError"),
        DevTestCase("t_exact_clean", "call", ("42.7.1",), (42, 7, 1)),
    ),
    "T06_replay_stock_deltas": (
        DevTestCase("t_signed_in_out_adj", "call", (["IN +50", "OUT +12", "ADJ -8"],), 30),
        DevTestCase("t_signed_zeros", "call", (["ADJ +0", "ADJ -0"],), 0),
        DevTestCase("t_net_negative", "call", (["ADJ -25", "ADJ -15", "IN 10"],), -30),
        DevTestCase("t_out_negative_reverses", "call", (["OUT -5"],), 5),
        DevTestCase("t_bare_plus_raises", "call", (["ADJ +"],), expected_exc="ValueError"),
        DevTestCase("t_alnum_qty_raises", "call", (["ADJ 12a"],), expected_exc="ValueError"),
        DevTestCase("t_bad_verb_raises", "call", (["BAD 5"],), expected_exc="ValueError"),
        DevTestCase("t_four_step_ledger", "call", (["IN 100", "ADJ -40", "OUT 10", "ADJ +7"],), 57),
    ),
    "T07_run_length_counts": (
        DevTestCase("t_singleton", "call", ([5],), [1]),
        DevTestCase("t_returning_symbol", "call", ([1, 1, 2, 1, 1, 1],), [2, 1, 3]),
        DevTestCase("t_negative_runs", "call", ([0, -1, -1, 0, 0, 0, 8],), [1, 2, 3, 1]),
        DevTestCase("t_long_head_short_tail", "call", ([3, 3, 3, 3, 4],), [4, 1]),
        DevTestCase("t_short_head_long_tail", "call", ([3, 4, 4, 4, 4],), [1, 4]),
        DevTestCase("t_five_alternating", "call", ([7, 8, 7, 8, 7],), [1, 1, 1, 1, 1]),
        DevTestCase("t_domain_guard", "call", ([200000, 1],), []),
        DevTestCase("t_three_pairs", "call", ([2, 2, 5, 5, 9, 9],), [2, 2, 2]),
    ),
    "T08_step_differences": (
        DevTestCase("t_singleton_empty", "call", ([9],), []),
        DevTestCase("t_mixed_five_diffs", "call", ([0, 10, 3, 15, 15, -5],), [10, -7, 12, 0, -20]),
        DevTestCase("t_negative_series", "call", ([-10, -4, -12],), [6, -8]),
        DevTestCase("t_single_drop", "call", ([100, 50],), [-50]),
        DevTestCase("t_doubling_series", "call", ([1, 2, 4, 8, 16],), [1, 2, 4, 8]),
        DevTestCase("t_out_of_limits", "call", ([2000000, 1],), []),
        DevTestCase("t_oscillating_sign", "call", ([7, -7, 7, -7],), [-14, 14, -14]),
        DevTestCase("t_three_steps", "call", ([12, 15, 19, 18],), [3, 4, -1]),
    ),
    "T09_session_durations": (
        DevTestCase("t_single_event_zero_dur", "call", ([42], 5), [0]),
        DevTestCase("t_one_continuous_session", "call", ([1, 2, 3, 4], 5), [3]),
        DevTestCase("t_four_isolated_events", "call", ([1, 10, 20, 30], 5), [0, 0, 0, 0]),
        DevTestCase("t_three_varied_sessions", "call", ([0, 4, 8, 20, 22, 40], 5), [8, 2, 0]),
        DevTestCase("t_simultaneous_zero_gap", "call", ([5, 5, 5], 0), [0]),
        DevTestCase("t_strict_zero_gap_splits", "call", ([5, 6, 8], 0), [0, 0, 0]),
        DevTestCase("t_negative_gap_guard", "call", ([0, 10], -1), []),
        DevTestCase("t_three_active_spans", "call", ([10, 13, 16, 30, 35, 39, 100, 108], 10), [6, 9, 8]),
    ),
    "T10_apply_row_mask": (
        DevTestCase("t_two_ends_immutable", "call", ([4, 5, 6], [(0, 9), (2, 1)]), [9, 5, 1], forbid_arg_mutation=True),
        DevTestCase("t_overwrite_same_slot", "call", ([1, 2], [(1, 7), (1, 8)]), [1, 8], forbid_arg_mutation=True),
        DevTestCase("t_empty_row", "call", ([], []), [], forbid_arg_mutation=True),
        DevTestCase("t_singleton_neg", "call", ([9], [(0, -3)]), [-3], forbid_arg_mutation=True),
        DevTestCase("t_upper_oob_raises", "call", ([1, 2, 3], [(3, 5)]), expected_exc="ValueError"),
        DevTestCase("t_neg_oob_raises", "call", ([1, 2, 3], [(-1, 5)]), expected_exc="ValueError"),
        DevTestCase("t_sequential_calls", "sequence", (([10, 20], [(0, 1)]), ([30, 40], [(1, 2)])), [[1, 20], [30, 2]]),
        DevTestCase("t_middle_slot_immutable", "call", ([0, 0, 0, 0, 0], [(2, 42)]), [0, 0, 42, 0, 0], forbid_arg_mutation=True),
    ),
    "T11_register_route": (
        DevTestCase("t_three_isolated_defaults", "sequence", (("/a", "get"), ("/b", "post"), ("/c", "delete")), [{"/a": ["GET"]}, {"/b": ["POST"]}, {"/c": ["DELETE"]}]),
        DevTestCase("t_append_second_verb", "call", ("/a", "post", {"/a": ["GET"]}), {"/a": ["GET", "POST"]}, forbid_arg_mutation=False),
        DevTestCase("t_idempotent_duplicate_verb", "call", ("/a", "get", {"/a": ["GET"]}), {"/a": ["GET"]}, forbid_arg_mutation=False),
        DevTestCase("t_missing_slash_raises", "call", ("no_slash", "GET"), expected_exc="ValueError"),
        DevTestCase("t_bad_method_raises", "call", ("/x", "PATCH"), expected_exc="ValueError"),
        DevTestCase("t_trimmed_path_and_verb", "call", (" /trim ", " put "), {"/trim": ["PUT"]}),
        DevTestCase("t_same_path_fresh_defaults", "sequence", (("/one", "GET"), ("/one", "POST")), [{"/one": ["GET"]}, {"/one": ["POST"]}]),
        DevTestCase("t_single_delete", "call", ("/z", "DELETE"), {"/z": ["DELETE"]}),
    ),
    "T12_compute_net_total": (
        DevTestCase("t_quarter_off_ten_tax", "call", ([2000], 2500, 1000), 1650),
        DevTestCase("t_full_discount_zero_tax", "call", ([400, 600], 10000, 2000), 0),
        DevTestCase("t_three_items_net", "call", ([100, 200, 300], 1000, 500), 567),
        DevTestCase("t_zero_rates", "call", ([999], 0, 0), 999),
        DevTestCase("t_fifteen_disc_eight_tax", "call", ([5000], 1500, 800), 4590),
        DevTestCase("t_neg_disc_raises", "call", ([100], -1, 500), expected_exc="ValueError"),
        DevTestCase("t_excess_tax_raises", "call", ([100], 500, 20000), expected_exc="ValueError"),
        DevTestCase("t_thirty_disc_fifteen_tax", "call", ([250, 250, 500], 3000, 1500), 805),
    ),
    "T13_ood_greedy_coin_change": (
        DevTestCase("t_dp_134_6", "call", ([1, 3, 4], 6), 2),
        DevTestCase("t_dp_25_6", "call", ([2, 5], 6), 3),
        DevTestCase("t_dp_1610_12", "call", ([1, 6, 10], 12), 2),
        DevTestCase("t_dp_impossible", "call", ([3, 7], 5), -1),
        DevTestCase("t_dp_145_8", "call", ([1, 4, 5], 8), 2),
        DevTestCase("t_dp_237_11", "call", ([2, 3, 7], 11), 3),
        DevTestCase("t_dp_57_19", "call", ([5, 7], 19), 3),
        DevTestCase("t_dp_469_12", "call", ([4, 6, 9], 12), 2),
    ),
    "T14_ood_nested_expr_eval": (
        DevTestCase("t_double_nested_sub", "call", ("50 - (20 - (5 + 3))",), 38),
        DevTestCase("t_zero_minus_diff", "call", ("0 - (4 - 9)",), 5),
        DevTestCase("t_two_groups", "call", ("(10 - 3) - (8 - (2 + 1))",), 2),
        DevTestCase("t_outer_sub_inner_add", "call", ("100 - (30 + (20 - 5))",), 55),
        DevTestCase("t_triple_flip", "call", ("7 - (3 - (2 - 1))",), 5),
        DevTestCase("t_zero_sub", "call", ("0 - 5",), -5),
        DevTestCase("t_add_nested_sub", "call", ("12 + (4 - (9 - 2))",), 9),
        DevTestCase("t_chained_groups", "call", ("30 - (10 + 5) - (8 - 3)",), 10),
    ),
    "T15_ood_weighted_shortest_hops": (
        DevTestCase("t_three_hop_beats_direct", "call", (4, [(0, 3, 50), (0, 1, 5), (1, 2, 5), (2, 3, 5)], 0, 3), 15),
        DevTestCase("t_zero_weight_detour", "call", (4, [(0, 3, 4), (0, 1, 0), (1, 2, 0), (2, 3, 1)], 0, 3), 1),
        DevTestCase("t_five_node_chain", "call", (5, [(0, 4, 30), (0, 1, 2), (1, 2, 2), (2, 3, 2), (3, 4, 2)], 0, 4), 8),
        DevTestCase("t_same_node", "call", (3, [(0, 1, 5)], 1, 1), 0),
        DevTestCase("t_disconnected", "call", (4, [(0, 1, 2), (2, 3, 2)], 0, 3), -1),
        DevTestCase("t_diamond_multi_relax", "call", (4, [(0, 1, 10), (0, 2, 2), (2, 1, 3), (1, 3, 1), (2, 3, 20)], 0, 3), 6),
        DevTestCase("t_parallel_edges", "call", (3, [(0, 2, 12), (0, 1, 4), (1, 2, 4)], 0, 2), 8),
        DevTestCase("t_cycle_graph", "call", (4, [(0, 1, 2), (1, 0, 1), (0, 3, 15), (1, 2, 2), (2, 3, 2)], 0, 3), 6),
    ),
    "T16_ood_triple_fault_ledger": (
        DevTestCase("t_two_memo_transfers", "call", ({"x": 200, "y": 50}, ["x:y:40:inv:1", "y:z:30:inv:2"]), {"x": 160, "y": 60, "z": 30}, forbid_arg_mutation=True),
        DevTestCase("t_overdraft_allowed", "call", ({"a": 10}, ["a:b:25:loan"]), {"a": -15, "b": 25}, forbid_arg_mutation=True),
        DevTestCase("t_round_trip", "call", ({"u": 50, "v": 50}, ["u:v:20:m1", "v:u:20:m2"]), {"u": 50, "v": 50}, forbid_arg_mutation=True),
        DevTestCase("t_colon_rich_memo", "call", ({"p": 100}, ["p:q:10:a:b:c"]), {"p": 90, "q": 10}, forbid_arg_mutation=True),
        DevTestCase("t_three_hops", "call", ({"n1": 90}, ["n1:n2:30:t", "n2:n3:15:t"]), {"n1": 60, "n2": 15, "n3": 15}, forbid_arg_mutation=True),
        DevTestCase("t_zero_transfer", "call", ({"k": 12}, ["k:m:0:noop"]), {"k": 12, "m": 0}, forbid_arg_mutation=True),
        DevTestCase("t_invalid_ledger_raises", "call", ({"": 10}, []), expected_exc="ValueError"),
        DevTestCase("t_multi_credit", "call", ({"s1": 40, "s2": 60}, ["s1:sink:15:x", "s2:sink:25:y"]), {"s1": 25, "s2": 35, "sink": 40}, forbid_arg_mutation=True),
    ),
    "T17_trap_constant_collapse": (
        DevTestCase("t_already_grouped_three", "call", ([1, 1, 1],), 0),
        DevTestCase("t_all_zeros", "call", ([0, 0, 0, 0],), 0),
        DevTestCase("t_single_one", "call", ([1],), 0),
        DevTestCase("t_sparse_three_ones", "call", ([1, 0, 0, 1, 0, 0, 1],), 2),
        DevTestCase("t_alternating_seven", "call", ([1, 0, 1, 0, 1, 0, 1],), 2),
        DevTestCase("t_split_ends_four_ones", "call", ([1, 1, 0, 0, 0, 1, 1],), 2),
        DevTestCase("t_sparse_four_ones_twelve", "call", ([1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1],), 3),
        DevTestCase("t_contiguous_middle", "call", ([0, 0, 1, 1, 1, 0],), 0),
    ),
    "T18_trap_special_case_guard": (
        DevTestCase("t_interior_pair", "call", ([5, 2, -2, 8],), 2),
        DevTestCase("t_interior_quad_alt", "call", ([9, 1, -1, 3, -3, 7],), 4),
        DevTestCase("t_interior_triple", "call", ([4, 2, 2, -4, 1],), 3),
        DevTestCase("t_neg_neg_pos_triple", "call", ([10, -3, -2, 5, 11],), 3),
        DevTestCase("t_strictly_positive", "call", ([1, 2, 3, 4],), 0),
        DevTestCase("t_interior_zero_elem", "call", ([6, 0, 9],), 1),
        DevTestCase("t_interior_five_span", "call", ([8, 5, -2, -3, 4, -4, 9],), 5),
        DevTestCase("t_shifted_triple", "call", ([-7, 3, 4, -7, 9],), 3),
    ),
}


def evaluate_target_trial(
    unit_id: str,
    entrypoint: str,
    staged: bool,
    patched_source: str | None,
) -> dict[str, Any]:
    """Score a frozen trial outcome against the sealed terminal test suite for `unit_id`."""
    if unit_id not in TERMINAL_SUITES:
        raise ValueError(f"unknown target unit in terminal evaluator: {unit_id}")
    suite = TERMINAL_SUITES[unit_id]
    suite_sha256 = sha256_digest([tc.to_dict() for tc in suite])

    if not staged or patched_source is None:
        return {
            "unit_id": unit_id,
            "evaluated_staged_patch": False,
            "terminal_all_passed": False,
            "terminal_passed_count": 0,
            "terminal_total_count": len(suite),
            "overfit_false_admission": False,
            "terminal_suite_sha256": suite_sha256,
        }

    res = run_dev_suite(patched_source, entrypoint, suite, collect_trace=False)
    all_ok = bool(res["all_passed"])
    return {
        "unit_id": unit_id,
        "evaluated_staged_patch": True,
        "terminal_all_passed": all_ok,
        "terminal_passed_count": int(res["passed_count"]),
        "terminal_total_count": int(res["total_count"]),
        "overfit_false_admission": not all_ok,
        "terminal_suite_sha256": suite_sha256,
    }
