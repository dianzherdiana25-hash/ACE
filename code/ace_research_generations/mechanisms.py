"""Typed Feature Synthesis & Meta-Mechanism Executor for Fase 7 (G0, G1, G2, and baselines).

Never imports ``evaluator.py``. Executes bounded candidate search under an explicit
hypothesis-evaluation ceiling ``eval_budget_k`` with full deterministic compute accounting.
"""
from __future__ import annotations

from dataclasses import dataclass
import itertools
from typing import Any, Callable, Sequence

from ace_research_primitives import primitive_discovery as r1

from .immutable_guard import validate_meta_candidate
from .tasks import block2_aa, even_a, odd_b, split_halves, words_of_len


@dataclass(frozen=True)
class TypedFeature:
    name: str
    mdl_cost: int
    fn: Callable[[str], bool]


@dataclass(frozen=True)
class CandidateProgram:
    name: str
    mdl_cost: int
    predict: Callable[[str], bool]


def _dedupe_features(feats: Sequence[TypedFeature]) -> list[TypedFeature]:
    probe_words = [w for n in range(0, 8) for w in words_of_len(n)]
    seen: set[int] = set()
    kept: list[TypedFeature] = []
    # Keep lower MDL cost first when deduplicating equivalent predicates
    for f in sorted(feats, key=lambda x: (x.mdl_cost, x.name)):
        sig = 0
        for idx, w in enumerate(probe_words):
            if f.fn(w):
                sig |= 1 << idx
        if sig not in seen:
            seen.add(sig)
            kept.append(f)
    return kept


def build_base_features() -> list[TypedFeature]:
    """Base G0 features: compact surface predicates + flat mod 2/3 counters."""
    raw: list[TypedFeature] = []
    for sub in ("a", "b", "aa", "ab", "ba", "bb", "aba", "bab", "aab", "bba"):
        raw.append(TypedFeature(f"starts:{sub}", 2 + len(sub), lambda w, s=sub: w.startswith(s)))
        raw.append(TypedFeature(f"ends:{sub}", 2 + len(sub), lambda w, s=sub: w.endswith(s)))
        if len(sub) >= 2:
            raw.append(TypedFeature(f"contains:{sub}", 3 + len(sub), lambda w, s=sub: s in w))
    for m in (2, 3):
        for r in range(m):
            raw.append(TypedFeature(f"ca%{m}=={r}", 3, lambda w, m=m, r=r: w.count("a") % m == r))
            raw.append(TypedFeature(f"cb%{m}=={r}", 3, lambda w, m=m, r=r: w.count("b") % m == r))
            raw.append(TypedFeature(f"len%{m}=={r}", 3, lambda w, m=m, r=r: len(w) % m == r))
    return _dedupe_features(raw)


def build_strong_fixed_library() -> list[TypedFeature]:
    """B_fixed: repo's full 100-predicate ``r1.fixed_predicates()`` + flat mod 2..5 counters."""
    raw: list[TypedFeature] = list(build_base_features())
    for name, fn in r1.fixed_predicates():
        raw.append(TypedFeature(f"r1:{name}", 5, fn))
    for m in (4, 5):
        for r in range(m):
            raw.append(TypedFeature(f"ca%{m}=={r}", 4, lambda w, m=m, r=r: w.count("a") % m == r))
            raw.append(TypedFeature(f"cb%{m}=={r}", 4, lambda w, m=m, r=r: w.count("b") % m == r))
            raw.append(TypedFeature(f"len%{m}=={r}", 4, lambda w, m=m, r=r: len(w) % m == r))
    return _dedupe_features(raw)


def build_features_for_mechanism(meta: dict) -> list[TypedFeature]:
    """Construct the typed feature vocabulary induced by a validated meta-mechanism."""
    validate_meta_candidate(meta)
    feats: list[TypedFeature] = list(build_base_features())
    moduli = tuple(meta["stride_moduli"])

    if meta["enable_strided_features"]:
        for m in moduli:
            for r in range(m):
                feats.append(TypedFeature(
                    f"even_a%{m}=={r}", 4, lambda w, m=m, r=r: even_a(w) % m == r
                ))
                feats.append(TypedFeature(
                    f"odd_b%{m}=={r}", 4, lambda w, m=m, r=r: odd_b(w) % m == r
                ))
                feats.append(TypedFeature(
                    f"block2_aa%{m}=={r}", 5, lambda w, m=m, r=r: block2_aa(w) % m == r
                ))

    if meta["enable_split_frame_lifting"]:
        # Lift unary count projections across split_halves(w), and if strided features are
        # ALREADY present in the parent lineage (G1 -> G2!), lift strided projections too!
        for m in (2, 3):
            for r in range(m):
                feats.append(TypedFeature(
                    f"L_ca%{m}=={r}", 4, lambda w, m=m, r=r: split_halves(w)[0].count("a") % m == r
                ))
                feats.append(TypedFeature(
                    f"R_cb%{m}=={r}", 4, lambda w, m=m, r=r: split_halves(w)[1].count("b") % m == r
                ))
            feats.append(TypedFeature(
                f"eq_half_ca%{m}",
                4,
                lambda w, m=m: (split_halves(w)[0].count("a") % m) == (split_halves(w)[1].count("a") % m),
            ))
        if meta["enable_strided_features"]:
            for m in moduli:
                feats.append(TypedFeature(
                    f"eq_half_even_a%{m}",
                    4,
                    lambda w, m=m: (even_a(split_halves(w)[0]) % m) == (even_a(split_halves(w)[1]) % m),
                ))
                feats.append(TypedFeature(
                    f"neq_half_odd_b%{m}",
                    4,
                    lambda w, m=m: (odd_b(split_halves(w)[0]) % m) != (odd_b(split_halves(w)[1]) % m),
                ))
                feats.append(TypedFeature(
                    f"eq_half_block2_aa%{m}",
                    5,
                    lambda w, m=m: (block2_aa(split_halves(w)[0]) % m) == (block2_aa(split_halves(w)[1]) % m),
                ))

    return _dedupe_features(feats)


def _bitvec(fn: Callable[[str], bool], words: Sequence[str]) -> int:
    v = 0
    for i, w in enumerate(words):
        if fn(w):
            v |= 1 << i
    return v


def fit_with_mechanism(
    features: Sequence[TypedFeature],
    train: list[tuple[str, bool]],
    val: list[tuple[str, bool]],
    *,
    eval_budget_k: int,
    enable_mdl_ranking: bool,
    enable_probe_agreement_gate: bool,
    probes: list[str],
) -> tuple[CandidateProgram | None, dict]:
    """Bounded pair/literal synthesis under explicit ``eval_budget_k`` ceiling."""
    tr_words = [w for w, _ in train]
    va_words = [w for w, _ in val]
    tr_mask = (1 << len(tr_words)) - 1
    va_mask = (1 << len(va_words)) - 1
    pr_mask = (1 << len(probes)) - 1

    tr_target = sum((1 << i) for i, (_, y) in enumerate(train) if y)
    va_target = sum((1 << i) for i, (_, y) in enumerate(val) if y)

    # Order features either by MDL cost (learned G2 heuristic) or lexicographic name (uninformed G0/G1)
    ordered_feats = (
        sorted(features, key=lambda f: (f.mdl_cost, f.name))
        if enable_mdl_ranking
        else sorted(features, key=lambda f: f.name)
    )

    f_tr = [_bitvec(f.fn, tr_words) for f in ordered_feats]
    f_va = [_bitvec(f.fn, va_words) for f in ordered_feats]
    n_f = len(ordered_feats)

    evals_used = 0
    symbol_reads = sum(len(w) for w in tr_words + va_words) * n_f
    exact_survivors: list[tuple[int, str, Callable[[str], bool], Callable[[], int]]] = []

    # 1. Single literals (each feature tests direct + negated polarity against train/val)
    neg_tr_mask = tr_mask ^ tr_target
    and_eligible: list[tuple[int, bool, int, int, int, str, Callable[[str], bool]]] = []
    or_eligible: list[tuple[int, bool, int, int, int, str, Callable[[str], bool]]] = []
    all_lits: list[tuple[int, bool, int, int, int, str, Callable[[str], bool]]] = []

    for k in range(n_f):
        if evals_used >= eval_budget_k:
            break
        evals_used += 1
        feat = ordered_feats[k]
        for neg in (False, True):
            v_tr = (tr_mask ^ f_tr[k]) if neg else f_tr[k]
            v_va = (va_mask ^ f_va[k]) if neg else f_va[k]
            nm = f"(not {feat.name})" if neg else feat.name
            cost = feat.mdl_cost + (1 if neg else 0)
            pred = (lambda w, f=feat.fn: not f(w)) if neg else feat.fn
            if v_tr == tr_target and v_va == va_target:
                probe_fn = (
                    lambda f=feat.fn, _neg=neg: (pr_mask ^ _bitvec(f, probes))
                    if _neg
                    else _bitvec(f, probes)
                )
                exact_survivors.append((cost, nm, pred, probe_fn))
            # Deductive necessary conditions on train:
            # - (A and B) == target requires A >= tr_target and B >= tr_target
            # - (A or B) == target requires (A & neg_tr_mask) == 0 and (B & neg_tr_mask) == 0
            lit_entry = (k, neg, v_tr, v_va, cost, nm, pred)
            all_lits.append(lit_entry)
            if (v_tr & tr_target) == tr_target and v_tr != tr_mask:
                and_eligible.append(lit_entry)
            if (v_tr & neg_tr_mask) == 0 and v_tr != 0:
                or_eligible.append(lit_entry)

    def _pair_order_key(pair):
        a, b = pair
        if enable_mdl_ranking:
            return (a[4] + b[4], a[5], b[5])
        return (a[5], b[5])

    # 2. Pair combinators (bounded strictly by eval_budget_k)
    if not exact_survivors and evals_used < eval_budget_k:
        and_pairs = [
            (a, b) for idx, a in enumerate(and_eligible) for b in and_eligible[idx + 1 :]
            if a[0] != b[0]
        ]
        and_pairs.sort(key=_pair_order_key)
        for a, b in and_pairs:
            if evals_used >= eval_budget_k:
                break
            evals_used += 1
            if (a[2] & b[2]) == tr_target and (a[3] & b[3]) == va_target:
                nm = f"({a[5]} and {b[5]})"
                cost = a[4] + b[4] + 2
                pred = lambda w, fa=a[6], fb=b[6]: fa(w) and fb(w)
                pfn = lambda fa=a[6], fb=b[6]: _bitvec(fa, probes) & _bitvec(fb, probes)
                exact_survivors.append((cost, nm, pred, pfn))

        or_pairs = [
            (a, b) for idx, a in enumerate(or_eligible) for b in or_eligible[idx + 1 :]
            if a[0] != b[0]
        ]
        or_pairs.sort(key=_pair_order_key)
        for a, b in or_pairs:
            if evals_used >= eval_budget_k:
                break
            evals_used += 1
            if (a[2] | b[2]) == tr_target and (a[3] | b[3]) == va_target:
                nm = f"({a[5]} or {b[5]})"
                cost = a[4] + b[4] + 2
                pred = lambda w, fa=a[6], fb=b[6]: fa(w) or fb(w)
                pfn = lambda fa=a[6], fb=b[6]: _bitvec(fa, probes) | _bitvec(fb, probes)
                exact_survivors.append((cost, nm, pred, pfn))

        # XOR: index positive-polarity literals by exact train bitvector (since (~A ^ B) == (A ^ ~B))
        pos_lits = [lit for lit in all_lits if not lit[1]]
        by_tr: dict[int, list[tuple[int, bool, int, int, int, str, Callable[[str], bool]]]] = {}
        for lit in pos_lits:
            by_tr.setdefault(lit[2], []).append(lit)
        xor_candidates: list[tuple[Any, Any, bool]] = []
        for a in pos_lits:
            need_same = a[2] ^ tr_target
            for b in by_tr.get(need_same, ()):
                if a[0] < b[0]:
                    xor_candidates.append((a, b, False))
            need_inv = tr_mask ^ (a[2] ^ tr_target)
            for b in by_tr.get(need_inv, ()):
                if a[0] < b[0]:
                    xor_candidates.append((a, b, True))
        xor_candidates.sort(
            key=lambda item: (
                (item[0][4] + item[1][4] + (1 if item[2] else 0), item[0][5], item[1][5])
                if enable_mdl_ranking
                else (item[0][5], item[1][5], item[2])
            )
        )
        for a, b, inv_xor in xor_candidates:
            if evals_used >= eval_budget_k:
                break
            evals_used += 1
            v_va = (va_mask ^ (a[3] ^ b[3])) if inv_xor else (a[3] ^ b[3])
            if v_va == va_target:
                op_name = "xnor" if inv_xor else "xor"
                nm = f"({a[5]} {op_name} {b[5]})"
                cost = a[4] + b[4] + (3 if inv_xor else 2)
                if inv_xor:
                    pred = lambda w, fa=a[6], fb=b[6]: fa(w) == fb(w)
                    pfn = lambda fa=a[6], fb=b[6]: pr_mask ^ (_bitvec(fa, probes) ^ _bitvec(fb, probes))
                else:
                    pred = lambda w, fa=a[6], fb=b[6]: fa(w) != fb(w)
                    pfn = lambda fa=a[6], fb=b[6]: _bitvec(fa, probes) ^ _bitvec(fb, probes)
                exact_survivors.append((cost, nm, pred, pfn))

    if not exact_survivors:
        return None, {
            "admitted": False,
            "abstain_reason": "no_consistent_candidate_within_budget",
            "evals_used": evals_used,
            "symbol_reads": symbol_reads,
            "feature_count": n_f,
        }

    exact_survivors.sort(key=lambda x: (x[0], x[1]))
    if enable_probe_agreement_gate and len(exact_survivors) > 1:
        min_cost = exact_survivors[0][0]
        minimal_set = [s for s in exact_survivors if s[0] == min_cost]
        if len(minimal_set) > 1:
            ref_p = minimal_set[0][3]()
            for s in minimal_set[1:]:
                if s[3]() != ref_p:
                    return None, {
                        "admitted": False,
                        "abstain_reason": "probe_disagreement_abstain",
                        "evals_used": evals_used,
                        "symbol_reads": symbol_reads,
                        "feature_count": n_f,
                    }

    best_cost, best_name, best_pred, _ = exact_survivors[0]
    return CandidateProgram(best_name, best_cost, best_pred), {
        "admitted": True,
        "program_name": best_name,
        "mdl_cost": best_cost,
        "evals_used": evals_used,
        "symbol_reads": symbol_reads,
        "feature_count": n_f,
    }


def fit_fresh_r1(train: list[tuple[str, bool]], val: list[tuple[str, bool]]) -> tuple[CandidateProgram | None, dict]:
    """B_fresh: Direct R1 DFA inference admitted iff node/merge budget holds and val errors == 0."""
    try:
        dfa, merges = r1.infer(train)
    except (ValueError, RuntimeError) as exc:
        return None, {
            "admitted": False,
            "abstain_reason": str(exc),
            "r1_merges": 0,
            "evals_used": 1,
            "symbol_reads": sum(len(w) + 1 for w, _ in train),
        }
    va_err = sum(1 for w, y in val if dfa.run(w) != y)
    syms = merges * sum(len(w) + 1 for w, _ in train) + sum(len(w) for w, _ in val)
    if va_err == 0:
        return CandidateProgram("fresh_r1_dfa", len(dfa.labels), dfa.run), {
            "admitted": True,
            "r1_merges": merges,
            "evals_used": merges,
            "symbol_reads": syms,
        }
    return None, {
        "admitted": False,
        "validation_errors": va_err,
        "r1_merges": merges,
        "evals_used": merges,
        "symbol_reads": syms,
    }
