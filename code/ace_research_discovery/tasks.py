"""Task specifications and deterministic SHA-256 dataset builders for Fase 6.

Defines the 12-task uncurated mixed source pool (`S_mixed`) and 15 family-disjoint
paired-tree target tasks across `U_cross`, `L_surface`, `N_abstain`, and `D_drift`.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from . import digest
from .evaluator import (
    DRIFT_BASE_MAP,
     encode_tree,
    eval_nominal_target_task,
    eval_source_task,
    eval_target_split_truth,
    parse_single_tree,
    tree_mirror,
)
from .sampling import (
    paired_tree_general_pool,
    prime_dyck_by_vertices,
    rank_select,
    sha256_rank,
    single_tree_pool,
)

SEEDS: tuple[int, ...] = (1, 2, 3, 4, 5)
BUDGETS: tuple[int, ...] = (16, 32, 64)
PRIMARY_BUDGET: int = 32
SOURCE_TRAIN_PER_CLASS: int = 16  # 32 train (16 pos + 16 neg)
SOURCE_VAL_PER_CLASS: int = 16  # 32 val (16 pos + 16 neg)
TERMINAL_PER_CLASS: int = 64  # 128 terminal (64 pos + 64 neg)


@dataclass(frozen=True)
class SourceTaskSpec:
    name: str
    true_kind: str  # "structural" | "surface_distractor" (NEVER passed to learner)
    description: str


@dataclass(frozen=True)
class TargetTaskSpec:
    name: str
    stratum: str  # "U_cross" | "L_surface" | "N_abstain" | "D_drift"
    description: str


SOURCE_TASKS_SPEC: tuple[SourceTaskSpec, ...] = (
    SourceTaskSpec("s_struct_depth_odd", "structural", "max_depth(T) % 2 == 1"),
    SourceTaskSpec("s_struct_leaves_mod3", "structural", "leaves(T) % 3 == 0"),
    SourceTaskSpec("s_struct_root_deg_eq2", "structural", "root_deg(T) == 2"),
    SourceTaskSpec("s_struct_bipartite_zero", "structural", "bipartite_diff(T) == 0"),
    SourceTaskSpec("s_struct_max_outdeg_le2", "structural", "max_outdeg(T) <= 2"),
    SourceTaskSpec("s_struct_branching_ge2", "structural", "branching_nodes(T) >= 2"),
    SourceTaskSpec("s_surf_starts_aaa", "surface_distractor", "x.startswith('aaa')"),
    SourceTaskSpec("s_surf_ends_abb", "surface_distractor", "x.endswith('abb')"),
    SourceTaskSpec("s_surf_contains_bba", "surface_distractor", "'bba' in x"),
    SourceTaskSpec("s_surf_count_a_mod3", "surface_distractor", "x.count('a') % 3 == 0"),
    SourceTaskSpec("s_surf_char3_is_a", "surface_distractor", "len(x) >= 4 and x[3] == 'a'"),
    SourceTaskSpec("s_surf_aab_and_bbb", "surface_distractor", "x.startswith('aab') and x.endswith('bbb')"),
)

TARGET_TASKS_SPEC: tuple[TargetTaskSpec, ...] = (
    # U_cross (6 cross-family paired-tree relational tasks)
    TargetTaskSpec("u1_leaves_mod4_rel", "U_cross", "leaves(T1) % 4 == leaves(T2) % 4"),
    TargetTaskSpec(
        "u2_rootdeg_eq_and_deep", "U_cross", "root_deg(T1) == root_deg(T2) and max_depth(T1) >= 3"
    ),
    TargetTaskSpec("u3_bipartite_diff_rel", "U_cross", "bipartite_diff(T1) == bipartite_diff(T2)"),
    TargetTaskSpec("u4_branching_mod3_rel", "U_cross", "branching_nodes(T1) % 3 == branching_nodes(T2) % 3"),
    TargetTaskSpec(
        "u5_depth_parity_and_motzkin",
        "U_cross",
        "(max_depth(T1) % 2 == max_depth(T2) % 2) and max_outdeg(T1) <= 2 and max_outdeg(T2) <= 2",
    ),
    TargetTaskSpec("u6_max_depth_eq", "U_cross", "max_depth(T1) == max_depth(T2)"),
    # L_surface (3 flat/surface compositional tasks)
    TargetTaskSpec("l1_starts_aaa_ends_abb", "L_surface", "x.startswith('aaa') and x.endswith('abb')"),
    TargetTaskSpec("l2_total_a_mod4_eq0", "L_surface", "x.count('a') % 4 == 0"),
    TargetTaskSpec("l3_starts_aab_even_a", "L_surface", "x.startswith('aab') and x.count('a') % 2 == 0"),
    # N_abstain (3 non-expressible relational tasks)
    TargetTaskSpec("n1_ordered_tree_identity", "N_abstain", "T1 == T2 (vs asymmetric mirror pairs)"),
    TargetTaskSpec("n2_mirror_tree_duality", "N_abstain", "T2 == mirror(T1) (vs asymmetric identity pairs)"),
    TargetTaskSpec(
        "n3_ordered_leaf_hash_eq",
        "N_abstain",
        "sum((i+1)*leaf_depth_i(T1)) % 5 == sum((i+1)*leaf_depth_i(T2)) % 5",
    ),
    # D_drift (3 unobservable terminal inversion controls)
    TargetTaskSpec(
        "d1_leaves_mod4_late_invert",
        "D_drift",
        "u1_leaves_mod4_rel on dev, inverted on terminal",
    ),
    TargetTaskSpec(
        "d2_bipartite_late_invert",
        "D_drift",
        "u3_bipartite_diff_rel on dev, inverted on terminal",
    ),
    TargetTaskSpec(
        "d3_surface_late_invert",
        "D_drift",
        "l1_starts_aaa_ends_abb on dev, inverted on terminal",
    ),
)

STRATA_ORDER: tuple[str, ...] = ("U_cross", "L_surface", "N_abstain", "D_drift")


@lru_cache(maxsize=16)
def _classified_source_pool(task_name: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    pool = single_tree_pool(2, 9)
    pos = tuple(w for w in pool if eval_source_task(task_name, w))
    neg = tuple(w for w in pool if not eval_source_task(task_name, w))
    return pos, neg


@lru_cache(maxsize=8)
def _invariant_matched_pair_pools(min_v: int, max_v: int, cap_per_v: int) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Return `(identity_pairs, asymmetric_mirror_pairs)` with `min_v <= v <= max_v`.

    Every `(T, T)` and `(T, mirror(T))` has identical `(depth, out_degree)` vertex
    multisets, ensuring commutative structural summaries cannot separate `n1` or `n2`.
    """
    dp = prime_dyck_by_vertices(max_v)
    identity_asym: list[str] = []
    mirror_asym: list[str] = []
    for v in range(min_v, max_v + 1):
        asym_words_v: list[tuple[str, str]] = []
        for w in dp[v]:
            node = parse_single_tree(w)
            assert node is not None
            mir = tree_mirror(node)
            if mir != node:
                asym_words_v.append((w, encode_tree(mir)))
        if len(asym_words_v) > cap_per_v:
            ranked_keys = rank_select([p[0] for p in asym_words_v], f"asym_v:{v}", 0, cap_per_v)
            keep = set(ranked_keys)
            asym_words_v = [p for p in asym_words_v if p[0] in keep]
        for w, mw in asym_words_v:
            identity_asym.append(w + w)
            mirror_asym.append(w + mw)
    return tuple(sorted(set(identity_asym), key=lambda s: (len(s), s))), tuple(
        sorted(set(mirror_asym), key=lambda s: (len(s), s))
    )


@lru_cache(maxsize=32)
def _classified_nominal_target_pools(
    base_task_name: str,
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    """Return `(dev_pos, dev_neg, term_pos, term_neg)` for a nominal target task."""
    if base_task_name == "n1_ordered_tree_identity":
        dev_id, dev_mir = _invariant_matched_pair_pools(4, 7, cap_per_v=200)
        term_id, term_mir = _invariant_matched_pair_pools(8, 10, cap_per_v=160)
        return dev_id, dev_mir, term_id, term_mir
    if base_task_name == "n2_mirror_tree_duality":
        dev_id, dev_mir = _invariant_matched_pair_pools(4, 7, cap_per_v=200)
        term_id, term_mir = _invariant_matched_pair_pools(8, 10, cap_per_v=160)
        return dev_mir, dev_id, term_mir, term_id

    dev_pool = paired_tree_general_pool(5, 14, per_pair_cap=160)
    term_pool = paired_tree_general_pool(15, 20, per_pair_cap=240)
    dev_pos = tuple(w for w in dev_pool if eval_nominal_target_task(base_task_name, w))
    dev_neg = tuple(w for w in dev_pool if not eval_nominal_target_task(base_task_name, w))
    term_pos = tuple(w for w in term_pool if eval_nominal_target_task(base_task_name, w))
    term_neg = tuple(w for w in term_pool if not eval_nominal_target_task(base_task_name, w))
    return dev_pos, dev_neg, term_pos, term_neg


def build_uncurated_source_pool(seed: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Build `(learner_source_tasks, audit_manifest)` for a given seed.

    `learner_source_tasks` contains ONLY `{"train": ..., "validation": ...}` in
    deterministic hash-interleaved order without task names or relevance labels.
    """
    ordered_specs = sorted(
        SOURCE_TASKS_SPEC,
        key=lambda sp: (sha256_rank("s_mixed_order", seed, sp.name), sp.name),
    )
    learner_tasks: list[dict[str, Any]] = []
    manifest: list[dict[str, Any]] = []

    need_total = SOURCE_TRAIN_PER_CLASS + SOURCE_VAL_PER_CLASS
    for ordinal, spec in enumerate(ordered_specs):
        pos_pool, neg_pool = _classified_source_pool(spec.name)
        pos_sel = rank_select(pos_pool, f"src:{spec.name}:pos", seed, need_total)
        neg_sel = rank_select(neg_pool, f"src:{spec.name}:neg", seed, need_total)

        tr_words = pos_sel[:SOURCE_TRAIN_PER_CLASS] + neg_sel[:SOURCE_TRAIN_PER_CLASS]
        va_words = pos_sel[SOURCE_TRAIN_PER_CLASS:] + neg_sel[SOURCE_TRAIN_PER_CLASS:]
        train = sorted([(w, eval_source_task(spec.name, w)) for w in tr_words], key=lambda r: (len(r[0]), r[0]))
        val = sorted([(w, eval_source_task(spec.name, w)) for w in va_words], key=lambda r: (len(r[0]), r[0]))

        assert not ({w for w, _ in train} & {w for w, _ in val})
        learner_tasks.append({"train": train, "validation": val})
        manifest.append(
            {
                "ordinal": ordinal,
                "name": spec.name,
                "true_kind": spec.true_kind,
                "description": spec.description,
                "train_sha256": digest(train),
                "validation_sha256": digest(val),
            }
        )
    return learner_tasks, manifest


def build_target_splits(
    task_name: str,
    seed: int,
    budget: int,
) -> tuple[list[tuple[str, bool]], list[tuple[str, bool]], list[tuple[str, bool]]]:
    """Build `(train, validation, terminal)` for `(task_name, seed, budget)`.

    Guarantees:
    - `len(train) == budget // 2`, `len(validation) == budget // 2` (50/50 class-balanced)
    - `len(terminal) == 128` (64 pos + 64 neg, strictly longer lengths 30..40)
    - `train(16) ⊂ train(32) ⊂ train(64)` and `val(16) ⊂ val(32) ⊂ val(64)`
    - `D_drift` tasks have 100% identical `(train, validation)` and terminal words as
      their nominal counterpart, with complemented terminal truth.
    """
    if budget not in BUDGETS or budget % 4 != 0:
        raise ValueError(f"unsupported target budget: {budget}")
    base_name = DRIFT_BASE_MAP.get(task_name, task_name)
    dev_pos, dev_neg, term_pos, term_neg = _classified_nominal_target_pools(base_name)

    max_k = max(BUDGETS) // 4  # 16 per class for train, 16 per class for val -> 32 total
    k = budget // 4

    ranked_dev_pos = rank_select(dev_pos, f"tgt:{base_name}:dev:pos", seed, 2 * max_k)
    ranked_dev_neg = rank_select(dev_neg, f"tgt:{base_name}:dev:neg", seed, 2 * max_k)
    ranked_term_pos = rank_select(term_pos, f"tgt:{base_name}:term:pos", seed, TERMINAL_PER_CLASS)
    ranked_term_neg = rank_select(term_neg, f"tgt:{base_name}:term:neg", seed, TERMINAL_PER_CLASS)

    tr_words = ranked_dev_pos[:k] + ranked_dev_neg[:k]
    va_words = ranked_dev_pos[max_k : max_k + k] + ranked_dev_neg[max_k : max_k + k]
    te_words = ranked_term_pos + ranked_term_neg

    train = sorted(
        [(w, eval_target_split_truth(task_name, w, is_terminal=False)) for w in tr_words],
        key=lambda r: (len(r[0]), r[0]),
    )
    validation = sorted(
        [(w, eval_target_split_truth(task_name, w, is_terminal=False)) for w in va_words],
        key=lambda r: (len(r[0]), r[0]),
    )
    terminal = sorted(
        [(w, eval_target_split_truth(task_name, w, is_terminal=True)) for w in te_words],
        key=lambda r: (len(r[0]), r[0]),
    )

    tr_set = {w for w, _ in train}
    va_set = {w for w, _ in validation}
    te_set = {w for w, _ in terminal}
    if (tr_set & va_set) or (tr_set & te_set) or (va_set & te_set):
        raise AssertionError(f"split overlap detected in {task_name}")
    return train, validation, terminal
