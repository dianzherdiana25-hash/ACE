"""Unit tests for the lineage-guard harness (PR #188
Part B.4). Twelve tests, all synthetic — no band, no
registry, no witnesses. They exercise solve_task_guarded
through stub seams: a dict-driven baseline_variants
adapter, dict-driven apply_operator / apply_chain, and a
dict-driven score function patched over the harness's
score base. Runnable standalone:

    python3 evidence/test_lineage_guard_harness.py

Exits non-zero if any test fails.
"""
import copy
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import lineage_guard_harness as lg

SCORES: dict = {}
BASELINE: dict = {}
OPS: dict = {}
CHAINS: dict = {}

K1 = ("op", 1)
K2 = ("op", 2)
C1 = (("op", 1), ("op", 2))


def _fake_score(budget, code, seconds=0.5):
    return SCORES.get(code, 0)


class StubAdapter:
    def baseline_variants(self, code):
        return list(BASELINE.get(code, []))

    def make_budget(self, task):
        return None


ADAPTER = StubAdapter()


def setup():
    SCORES.clear()
    BASELINE.clear()
    OPS.clear()
    CHAINS.clear()
    lg.apply_operator = lambda code, key: OPS.get((code, key))
    lg.apply_chain = lambda code, chain: CHAINS.get(
        (code, chain))
    lg._orig_safe_score = _fake_score


def mktask(start):
    return {"task_id": "synthetic", "buggy_code": start,
            "shown_cases": [None] * 1000,
            "holdout_cases": [], "holdout_truth": None}


def solve(start, *, guard=False, keys=(), chains=(),
          rounds=6, width=4, log=None):
    return lg.solve_task_guarded(
        mktask(start), ADAPTER, tuple(keys), tuple(chains),
        rounds=rounds, frontier_width=width,
        round_log=log, guard=guard)


def label(info, text):
    return info["lineage_labels"][lg._sha(text)]


# --- Labels (B.4 tests 1-6) -------------------------------
def test_01_start_is_base():
    setup()
    _code, info = solve("S0")
    assert label(info, "S0") == "BASE"


def test_02_baseline_child_of_base_is_base():
    setup()
    BASELINE["S0"] = ["c1"]
    SCORES["c1"] = 1
    _code, info = solve("S0")
    assert label(info, "c1") == "BASE"


def test_03_key_child_of_base_is_enriched():
    setup()
    OPS[("S0", K1)] = "k1"
    SCORES["k1"] = 1
    _code, info = solve("S0", keys=(K1,))
    assert label(info, "k1") == "ENRICHED"


def test_04_baseline_child_of_enriched_is_enriched():
    setup()
    OPS[("S0", K1)] = "k1"
    SCORES["k1"] = 5
    BASELINE["k1"] = ["k1b"]
    SCORES["k1b"] = 1
    _code, info = solve("S0", keys=(K1,))
    assert label(info, "k1") == "ENRICHED"
    assert label(info, "k1b") == "ENRICHED"


def test_05_first_generation_wins_enriched_kept():
    setup()
    BASELINE["S0"] = ["A", "B"]
    SCORES["A"] = 10
    SCORES["B"] = 10
    OPS[("A", K1)] = "X"        # X first generated ENRICHED
    BASELINE["B"] = ["X"]       # later via a baseline step
    SCORES["X"] = 0
    _code, info = solve("S0", keys=(K1,))
    assert label(info, "A") == "BASE"
    assert label(info, "B") == "BASE"
    assert label(info, "X") == "ENRICHED"


def test_06_chain_child_is_enriched():
    setup()
    CHAINS[("S0", C1)] = "ch1"
    SCORES["ch1"] = 1
    _code, info = solve("S0", chains=(C1,))
    assert label(info, "ch1") == "ENRICHED"


# --- Guard (B.4 tests 7-10) -------------------------------
def _world_two_enriched_one_base():
    BASELINE["S0"] = ["b1"]
    SCORES["b1"] = 1
    OPS[("S0", K1)] = "k1"
    OPS[("S0", K2)] = "k2"
    SCORES["k1"] = 9
    SCORES["k2"] = 9


def test_07_no_trigger_when_base_in_frontier():
    setup()
    BASELINE["S0"] = ["b1"]
    SCORES["b1"] = 10
    OPS[("S0", K1)] = "k1"
    SCORES["k1"] = 9
    log_on, log_off = [], []
    solve("S0", keys=(K1,), guard=True, log=log_on)
    solve("S0", keys=(K1,), guard=False, log=log_off)
    ev = log_on[0]["guard_event"]
    assert ev is not None and ev["triggered"] is False
    assert log_on[0]["frontier_out"] == \
        log_off[0]["frontier_out"] == \
        [[lg._sha("b1"), "BASE"]]


def test_08_no_trigger_when_no_base_scored():
    setup()
    OPS[("S0", K1)] = "k1"
    SCORES["k1"] = 9
    log = []
    solve("S0", keys=(K1,), guard=True, log=log)
    assert log[0]["scored_base_best"] is None
    assert log[0]["guard_event"]["triggered"] is False
    assert log[0]["frontier_out"] == \
        [[lg._sha("k1"), "ENRICHED"]]


def test_09_trigger_replaces_last_with_argmax_base():
    setup()
    _world_two_enriched_one_base()
    log = []
    solve("S0", keys=(K1, K2), guard=True, log=log)
    entry = log[0]
    assert entry["frontier_out"] == [
        [lg._sha("k1"), "ENRICHED"], [lg._sha("b1"), "BASE"]]
    ev = entry["guard_event"]
    assert ev["triggered"] is True
    assert ev["occupant"] == lg._sha("b1")
    assert ev["displaced"] == lg._sha("k2")
    assert entry["scored_base_best"] == \
        [lg._sha("b1"), 1, 3]


def test_10_guard_off_reproduces_param_bit_for_bit():
    setup()
    BASELINE["S0"] = ["b1"]
    BASELINE["b1"] = ["b2"]
    OPS[("S0", K1)] = "x1"
    OPS[("b1", K1)] = "x2"
    SCORES.update({"b1": 3, "x1": 2, "b2": 4, "x2": 1})
    task = mktask("S0")
    trace_p, trace_g = [], []
    log_p, log_g = [], []
    code_p, info_p = lg.solve_task_param(
        task, ADAPTER, (K1,), (), trace=trace_p,
        round_log=log_p)
    code_g, info_g = lg.solve_task_guarded(
        task, ADAPTER, (K1,), (), trace=trace_g,
        round_log=log_g, guard=False)
    assert code_p == code_g
    assert info_p["termination"] == info_g["termination"]
    assert info_p["score_calls_internal"] == \
        info_g["score_calls_internal"]
    assert trace_p == trace_g
    shared = ("round", "n_candidates_generated", "n_scored",
              "cap_break", "best_score_after", "frontier_size",
              "frontier_cutoff_score")
    assert len(log_p) == len(log_g) >= 2
    for ep, eg in zip(log_p, log_g):
        assert all(ep[k] == eg[k] for k in shared), \
            (ep, eg)
        assert eg["guard_event"] is None


# --- Anchor (B.4 tests 11-12) -----------------------------
def test_11_anchor_fields_present_and_label_consistent():
    setup()
    _world_two_enriched_one_base()
    log = []
    _code, info = solve("S0", keys=(K1, K2), guard=True,
                        log=log)
    labels = info["lineage_labels"]
    assert log, "no rounds recorded"
    for e in log:
        for field in ("frontier_in", "frontier_out",
                      "scored_base_best", "guard_event",
                      "lineage_alive_in"):
            assert field in e, field
        for sha, lab in e["frontier_in"] + e["frontier_out"]:
            assert labels[sha] == lab
        assert e["lineage_alive_in"] == any(
            lab == "BASE" for _s, lab in e["frontier_in"])
        if e["scored_base_best"] is not None:
            sha, score, _rank = e["scored_base_best"]
            assert labels[sha] == "BASE"


def test_12_l5_checker_flags_corrupted_actuation():
    setup()
    _world_two_enriched_one_base()
    log = []
    solve("S0", keys=(K1, K2), guard=True, log=log)
    assert lg.check_l5(log) == []
    corrupt = copy.deepcopy(log)
    for e in corrupt:
        if e["guard_event"] and e["guard_event"]["triggered"]:
            e["guard_event"]["occupant"] = "0" * 64
    violations = lg.check_l5(corrupt)
    assert violations, "corruption not flagged"
    assert any(v["violation"] == "occupant_not_argmax_base"
               for v in violations)


TESTS = [
    test_01_start_is_base,
    test_02_baseline_child_of_base_is_base,
    test_03_key_child_of_base_is_enriched,
    test_04_baseline_child_of_enriched_is_enriched,
    test_05_first_generation_wins_enriched_kept,
    test_06_chain_child_is_enriched,
    test_07_no_trigger_when_base_in_frontier,
    test_08_no_trigger_when_no_base_scored,
    test_09_trigger_replaces_last_with_argmax_base,
    test_10_guard_off_reproduces_param_bit_for_bit,
    test_11_anchor_fields_present_and_label_consistent,
    test_12_l5_checker_flags_corrupted_actuation,
]


def main():
    failed = 0
    for t in TESTS:
        try:
            t()
            print(f"PASS {t.__name__}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"FAIL {t.__name__}: "
                  f"{type(exc).__name__}: {exc}")
    print(f"{len(TESTS) - failed}/{len(TESTS)} tests passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
