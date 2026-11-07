"""Automated source abstraction discovery, MDL compression, pair functor, and gate.

Strictly isolated from `evaluator.py` and `tasks.py`: operates solely on labeled
`(word, bool)` development rows and unlabeled probes from `sampling.py`.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import math
from typing import Any, Callable

from . import digest
from .dsl import (
    ALPHABET,
    BoolExpr,
    IntExpr,
    MODULI,
    PATTERNS_1_TO_3,
    ParsedInput,
    WorkMeter,
    extract_subexpressions,
    parse_dyck_input,
    synthesize_bottom_up,
)
from .sampling import sha256_rank, unlabeled_paired_tree_probes, unlabeled_single_tree_probes

C_SOURCE = 2000
K_MAX = 7
MDL_REUSE_WEIGHT = 0.25
MDL_SIZE_PENALTY = 0.12
MIN_NON_MODE_RATE = 0.10
PROBE_COUNT = 64
PROBE_AGREEMENT_THRESHOLD = 0.90
PROBE_COMPLEXITY_MARGIN = 2


@dataclass(frozen=True)
class DiscoveredAbstraction:
    """Unary `SlotF`-parameterized abstraction extracted from source solutions."""

    kind: str  # "int" | "bool"
    int_expr: IntExpr | None
    bool_expr: BoolExpr | None
    ast_size: int
    entropy_bits: float
    non_mode_rate: float
    source_reuse_count: int
    utility_score: float
    identity: str

    def to_data(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "expr": self.int_expr.to_data() if self.int_expr is not None else self.bool_expr.to_data(),  # type: ignore[union-attr]
            "ast_size": self.ast_size,
            "entropy_bits": self.entropy_bits,
            "non_mode_rate": self.non_mode_rate,
            "source_reuse_count": self.source_reuse_count,
            "utility_score": self.utility_score,
            "identity": self.identity,
        }


@dataclass(frozen=True)
class SourceDiscoveryReport:
    """Full provenance of Phase 1 discovery over an uncurated source pool."""

    seed: int
    source_task_count: int
    admitted_source_count: int
    abstractions: tuple[DiscoveredAbstraction, ...]
    ungated_abstractions: tuple[DiscoveredAbstraction, ...]
    work: dict[str, int]
    per_source_outcomes: tuple[dict[str, Any], ...]


def shannon_entropy_bits(values: tuple[Any, ...]) -> tuple[float, float]:
    """Compute exact empirical Shannon entropy (bits) and non-mode rate."""
    n = len(values)
    if n == 0:
        return 0.0, 0.0
    counts = Counter(values)
    max_count = max(counts.values())
    entropy = 0.0
    for count in counts.values():
        p = count / n
        if p > 0.0:
            entropy -= p * math.log2(p)
    return round(entropy, 6), round(1.0 - (max_count / n), 6)


def is_functionally_determined(cand_vec: tuple[Any, ...], basis_vec: tuple[Any, ...]) -> bool:
    """Return True iff `H(cand_vec | basis_vec) == 0` on unlabeled probes."""
    mapping: dict[Any, Any] = {}
    for b_val, c_val in zip(basis_vec, cand_vec):
        if b_val in mapping:
            if mapping[b_val] != c_val:
                return False
        else:
            mapping[b_val] = c_val
    return True


def discover_from_source_pool(
    source_tasks: list[dict[str, Any]],
    seed: int,
) -> SourceDiscoveryReport:
    """Solve uncurated source tasks and compress reusable unary abstractions via MDL.

    Receives ONLY `[{"train": [...], "validation": [...]}, ...]` with zero task
    category flags and zero access to target tasks.
    """
    meter = WorkMeter()
    probes_raw = unlabeled_single_tree_probes(seed, PROBE_COUNT)

    # Collect unique unlabeled strings across source pool + single-tree probes
    vocab_set: set[str] = set(probes_raw)
    for item in source_tasks:
        for w, _ in item["train"]:
            vocab_set.add(w)
        for w, _ in item["validation"]:
            vocab_set.add(w)
    vocab_words = sorted(vocab_set, key=lambda w: (len(w), w))
    word_to_idx = {w: i for i, w in enumerate(vocab_words)}
    parsed_vocab = tuple(parse_dyck_input(w) for w in vocab_words)
    parsed_probes = tuple(parsed_vocab[word_to_idx[w]] for w in probes_raw)

    # Synthesize unary expressions (`Whole` frame only) once over shared source vocabulary
    synthesized = synthesize_bottom_up(
        parsed_inputs=parsed_vocab,
        frames_allowed=("Whole",),
        max_bool_candidates=C_SOURCE,
        meter=meter,
        max_ast_size=8,
    )

    admitted_solutions: list[BoolExpr] = []
    all_best_solutions: list[BoolExpr] = []
    per_source_outcomes: list[dict[str, Any]] = []

    for ordinal, item in enumerate(source_tasks):
        train_rows: list[tuple[str, bool]] = item["train"]
        val_rows: list[tuple[str, bool]] = item["validation"]
        tr_idx = [word_to_idx[w] for w, _ in train_rows]
        tr_lbl = [y for _, y in train_rows]
        va_idx = [word_to_idx[w] for w, _ in val_rows]
        va_lbl = [y for _, y in val_rows]

        best_expr: BoolExpr | None = None
        best_key: tuple[int, int, int, int, str] | None = None
        best_tr = 0
        best_va = 0

        for expr, vec in synthesized:
            tr_c = sum(1 for idx, y in zip(tr_idx, tr_lbl) if vec[idx] == y)
            va_c = sum(1 for idx, y in zip(va_idx, va_lbl) if vec[idx] == y)
            key = (tr_c + va_c, va_c, tr_c, -expr.ast_size, expr.identity)
            if best_key is None or key > best_key:
                # Deterministic tie-break on lowest identity if scores+size tie
                if best_key is not None and key[:4] == best_key[:4]:
                    if expr.identity < best_key[4]:
                        best_key = (tr_c + va_c, va_c, tr_c, -expr.ast_size, expr.identity)
                        best_expr = expr
                        best_tr, best_va = tr_c, va_c
                else:
                    best_key = key
                    best_expr = expr
                    best_tr, best_va = tr_c, va_c

        assert best_expr is not None
        admitted = (best_tr == len(train_rows)) and (best_va == len(val_rows))
        all_best_solutions.append(best_expr)
        if admitted:
            admitted_solutions.append(best_expr)
        per_source_outcomes.append(
            {
                "ordinal": ordinal,
                "admitted": admitted,
                "train_correct": best_tr,
                "train_total": len(train_rows),
                "validation_correct": best_va,
                "validation_total": len(val_rows),
                "selected_ast_size": best_expr.ast_size,
                "selected_identity": best_expr.identity,
            }
        )

    # Extract and score unary sub-expressions (`SlotF`) for gated MDL discovery
    probe_chars = sum(len(p.word) for p in parsed_probes)
    sig_to_best_entry: dict[tuple[str, tuple[Any, ...]], tuple[str, IntExpr | None, BoolExpr | None, int]] = {}
    sig_task_sets: dict[tuple[str, tuple[Any, ...]], set[int]] = {}

    for sol_idx, sol in enumerate(admitted_solutions):
        int_subs, bool_subs = extract_subexpressions(sol)
        for ie in int_subs:
            slot_ie = ie.bind_frame("SlotF")
            if slot_ie.ast_size < 3:
                continue
            meter.charge_expr(slot_ie.ast_size, slot_ie.scan_count, probe_chars, len(parsed_probes))
            vec = tuple(slot_ie.eval_parsed(p) for p in parsed_probes)
            sig = ("int", vec)
            sig_task_sets.setdefault(sig, set()).add(sol_idx)
            prev = sig_to_best_entry.get(sig)
            if prev is None or (slot_ie.ast_size, slot_ie.identity) < (prev[3], prev[1].identity if prev[1] else ""):
                sig_to_best_entry[sig] = ("int", slot_ie, None, slot_ie.ast_size)

        for be in bool_subs:
            slot_be = be.bind_frame("SlotF")
            if slot_be.ast_size < 3 or slot_be.kind == "valid_frame":
                continue
            meter.charge_expr(slot_be.ast_size, slot_be.scan_count, probe_chars, len(parsed_probes))
            vec_b = tuple(slot_be.eval_parsed(p) for p in parsed_probes)
            sig_b = ("bool", vec_b)
            sig_task_sets.setdefault(sig_b, set()).add(sol_idx)
            prev_b = sig_to_best_entry.get(sig_b)
            if prev_b is None or (slot_be.ast_size, slot_be.identity) < (
                prev_b[3],
                prev_b[2].identity if prev_b[2] else "",
            ):
                sig_to_best_entry[sig_b] = ("bool", None, slot_be, slot_be.ast_size)

    scored_candidates: list[tuple[DiscoveredAbstraction, tuple[Any, ...]]] = []
    for sig, (kind, ie_opt, be_opt, ast_sz) in sig_to_best_entry.items():
        vec = sig[1]
        entropy, non_mode = shannon_entropy_bits(vec)
        if non_mode < MIN_NON_MODE_RATE:
            continue
        reuse = len(sig_task_sets[sig])
        utility = round(
            entropy + MDL_REUSE_WEIGHT * (reuse - 1) - MDL_SIZE_PENALTY * ast_sz,
            6,
        )
        ident = ie_opt.identity if ie_opt is not None else be_opt.identity  # type: ignore[union-attr]
        scored_candidates.append(
            (
                DiscoveredAbstraction(
                    kind=kind,
                    int_expr=ie_opt,
                    bool_expr=be_opt,
                    ast_size=ast_sz,
                    entropy_bits=entropy,
                    non_mode_rate=non_mode,
                    source_reuse_count=reuse,
                    utility_score=utility,
                    identity=ident,
                ),
                vec,
            )
        )

    # Sort descending by utility, then smaller AST, then canonical identity
    scored_candidates.sort(key=lambda item: (-item[0].utility_score, item[0].ast_size, item[0].identity))

    # Greedy MDL conditional-information selection (`H(cand | selected) > 0`) up to K_MAX
    selected_gated: list[DiscoveredAbstraction] = []
    selected_vecs: list[tuple[Any, ...]] = []
    for cand, vec in scored_candidates:
        if len(selected_gated) >= K_MAX:
            break
        if any(is_functionally_determined(vec, bvec) for bvec in selected_vecs):
            continue
        selected_gated.append(cand)
        selected_vecs.append(vec)

    # Ungated ablation: take raw root/sub-expressions from ALL solutions in source order without MDL entropy filter
    ungated_list: list[DiscoveredAbstraction] = []
    seen_ungated_ids: set[str] = set()
    for sol in all_best_solutions:
        if len(ungated_list) >= K_MAX:
            break
        slot_be = sol.bind_frame("SlotF")
        if slot_be.identity not in seen_ungated_ids and slot_be.ast_size >= 3:
            seen_ungated_ids.add(slot_be.identity)
            vec_u = tuple(slot_be.eval_parsed(p) for p in parsed_probes)
            ent_u, nm_u = shannon_entropy_bits(vec_u)
            ungated_list.append(
                DiscoveredAbstraction(
                    kind="bool",
                    int_expr=None,
                    bool_expr=slot_be,
                    ast_size=slot_be.ast_size,
                    entropy_bits=ent_u,
                    non_mode_rate=nm_u,
                    source_reuse_count=1,
                    utility_score=round(ent_u - MDL_SIZE_PENALTY * slot_be.ast_size, 6),
                    identity=slot_be.identity,
                )
            )

    return SourceDiscoveryReport(
        seed=seed,
        source_task_count=len(source_tasks),
        admitted_source_count=len(admitted_solutions),
        abstractions=tuple(selected_gated),
        ungated_abstractions=tuple(ungated_list),
        work=meter.to_dict(),
        per_source_outcomes=tuple(per_source_outcomes),
    )


def sample_random_abstractions(seed: int, count: int, meter: WorkMeter) -> tuple[DiscoveredAbstraction, ...]:
    """Deterministically sample `count` non-constant unary DSL abstractions (`ast_size` 3..6)."""
    probes_raw = unlabeled_single_tree_probes(seed, PROBE_COUNT)
    parsed_probes = tuple(parse_dyck_input(w) for w in probes_raw)
    probe_chars = sum(len(p.word) for p in parsed_probes)

    pool_bools = synthesize_bottom_up(
        parsed_inputs=parsed_probes,
        frames_allowed=("SlotF",),
        max_bool_candidates=400,
        meter=meter,
        max_ast_size=6,
    )

    candidates: list[tuple[str, DiscoveredAbstraction, tuple[Any, ...]]] = []
    seen_sigs: set[tuple[str, tuple[Any, ...]]] = set()

    # Collect distinct IntExprs and BoolExprs of AST size 3..6
    for be, bvec in pool_bools:
        int_subs, bool_subs = extract_subexpressions(be)
        for ie in int_subs:
            if not (3 <= ie.ast_size <= 6):
                continue
            vec = tuple(ie.eval_parsed(p) for p in parsed_probes)
            sig = ("int", vec)
            if sig in seen_sigs:
                continue
            ent, nm = shannon_entropy_bits(vec)
            if nm < 0.05:
                continue
            seen_sigs.add(sig)
            meter.charge_expr(ie.ast_size, ie.scan_count, probe_chars, len(parsed_probes))
            da = DiscoveredAbstraction(
                kind="int",
                int_expr=ie,
                bool_expr=None,
                ast_size=ie.ast_size,
                entropy_bits=ent,
                non_mode_rate=nm,
                source_reuse_count=0,
                utility_score=0.0,
                identity=ie.identity,
            )
            candidates.append((sha256_rank("random_abs", seed, ie.identity), da, vec))

        if 3 <= be.ast_size <= 6 and be.kind != "valid_frame":
            sig_b = ("bool", bvec)
            if sig_b not in seen_sigs:
                ent_b, nm_b = shannon_entropy_bits(bvec)
                if nm_b >= 0.05:
                    seen_sigs.add(sig_b)
                    da_b = DiscoveredAbstraction(
                        kind="bool",
                        int_expr=None,
                        bool_expr=be,
                        ast_size=be.ast_size,
                        entropy_bits=ent_b,
                        non_mode_rate=nm_b,
                        source_reuse_count=0,
                        utility_score=0.0,
                        identity=be.identity,
                    )
                    candidates.append((sha256_rank("random_abs", seed, be.identity), da_b, bvec))

    candidates.sort(key=lambda item: (item[0], item[1].identity))
    chosen = [item[1] for item in candidates[:count]]
    return tuple(chosen)


@dataclass(frozen=True)
class AdapterFeature:
    """Named boolean predicate atom with complexity cost for the shared target adapter."""

    name: str
    complexity: int
    fn: Callable[[str], bool]
    ast_nodes_per_eval: int
    scans_per_eval: int
    dsl_expr: BoolExpr | None = None


def surface_dsl_atoms() -> list[AdapterFeature]:
    """Common surface `Whole`-frame boolean atoms shared across transfer arms."""
    atoms: list[AdapterFeature] = []
    for pat in PATTERNS_1_TO_3:
        for kind in ("starts_with", "ends_with", "contains"):
            be = BoolExpr(kind=kind, frame="Whole", pat=pat)
            atoms.append(
                AdapterFeature(
                    name=f"surf:{kind}:{pat}",
                    complexity=2,
                    fn=be.predict,
                    ast_nodes_per_eval=be.ast_size,
                    scans_per_eval=be.scan_count,
                    dsl_expr=be,
                )
            )
    for m in MODULI:
        base_cnt = IntExpr(kind="mod", mod=m, sub=IntExpr(kind="char_count", frame="Whole", ch="a"))
        for r in range(m):
            be_mod = BoolExpr(kind="int_eq_const", int_sub=base_cnt, threshold=r)
            atoms.append(
                AdapterFeature(
                    name=f"surf:count_a%{m}=={r}",
                    complexity=2,
                    fn=be_mod.predict,
                    ast_nodes_per_eval=be_mod.ast_size,
                    scans_per_eval=be_mod.scan_count,
                    dsl_expr=be_mod,
                )
            )
    return atoms


def lift_pair_functor_atoms(abstractions: tuple[DiscoveredAbstraction, ...]) -> list[AdapterFeature]:
    """General typed pair-frame functor `F_pair` lifting unary `SlotF` abstractions."""
    atoms: list[AdapterFeature] = []
    for idx, ab in enumerate(abstractions):
        tag = f"abs{idx}_{ab.identity[:8]}"
        if ab.kind == "int":
            assert ab.int_expr is not None
            phi_l = ab.int_expr.bind_frame("LeftF")
            phi_r = ab.int_expr.bind_frame("RightF")

            # 1. Direct relational equality: phi(LeftF) == phi(RightF)
            eq_be = BoolExpr(kind="int_eq", int_left=phi_l, int_right=phi_r)
            atoms.append(
                AdapterFeature(
                    name=f"{tag}:eq_pair",
                    complexity=2,
                    fn=eq_be.predict,
                    ast_nodes_per_eval=eq_be.ast_size,
                    scans_per_eval=eq_be.scan_count,
                    dsl_expr=eq_be,
                )
            )

            # 2. Modular relational equalities: phi(LeftF) % m == phi(RightF) % m
            for m in MODULI:
                mod_be = BoolExpr(
                    kind="int_eq",
                    int_left=IntExpr(kind="mod", mod=m, sub=phi_l),
                    int_right=IntExpr(kind="mod", mod=m, sub=phi_r),
                )
                atoms.append(
                    AdapterFeature(
                        name=f"{tag}:mod{m}_eq_pair",
                        complexity=3,
                        fn=mod_be.predict,
                        ast_nodes_per_eval=mod_be.ast_size,
                        scans_per_eval=mod_be.scan_count,
                        dsl_expr=mod_be,
                    )
                )

            # 3. Symmetric pair bounds: both <= c, both >= c
            for c in (1, 2, 3):
                both_le = BoolExpr(
                    kind="and",
                    bool_left=BoolExpr(kind="int_le_const", int_sub=phi_l, threshold=c),
                    bool_right=BoolExpr(kind="int_le_const", int_sub=phi_r, threshold=c),
                )
                atoms.append(
                    AdapterFeature(
                        name=f"{tag}:both_le_{c}",
                        complexity=3,
                        fn=both_le.predict,
                        ast_nodes_per_eval=both_le.ast_size,
                        scans_per_eval=both_le.scan_count,
                        dsl_expr=both_le,
                    )
                )
                both_ge = BoolExpr(
                    kind="and",
                    bool_left=BoolExpr(kind="int_ge_const", int_sub=phi_l, threshold=c),
                    bool_right=BoolExpr(kind="int_ge_const", int_sub=phi_r, threshold=c),
                )
                atoms.append(
                    AdapterFeature(
                        name=f"{tag}:both_ge_{c}",
                        complexity=3,
                        fn=both_ge.predict,
                        ast_nodes_per_eval=both_ge.ast_size,
                        scans_per_eval=both_ge.scan_count,
                        dsl_expr=both_ge,
                    )
                )

            # 4. Frame-specific thresholds
            for side, phi_s in (("L", phi_l), ("R", phi_r)):
                for c in (0, 1, 2, 3):
                    be_eqc = BoolExpr(kind="int_eq_const", int_sub=phi_s, threshold=c)
                    atoms.append(
                        AdapterFeature(
                            name=f"{tag}:{side}_eq_{c}",
                            complexity=3,
                            fn=be_eqc.predict,
                            ast_nodes_per_eval=be_eqc.ast_size,
                            scans_per_eval=be_eqc.scan_count,
                            dsl_expr=be_eqc,
                        )
                    )
                for c in (2, 3, 4):
                    be_gec = BoolExpr(kind="int_ge_const", int_sub=phi_s, threshold=c)
                    atoms.append(
                        AdapterFeature(
                            name=f"{tag}:{side}_ge_{c}",
                            complexity=3,
                            fn=be_gec.predict,
                            ast_nodes_per_eval=be_gec.ast_size,
                            scans_per_eval=be_gec.scan_count,
                            dsl_expr=be_gec,
                        )
                    )
        else:
            assert ab.bool_expr is not None
            psi_l = ab.bool_expr.bind_frame("LeftF")
            psi_r = ab.bool_expr.bind_frame("RightF")
            for rel_kind, nm in (("bool_eq", "beq_pair"), ("and", "band_pair")):
                be_rel = BoolExpr(kind=rel_kind, bool_left=psi_l, bool_right=psi_r)
                atoms.append(
                    AdapterFeature(
                        name=f"{tag}:{nm}",
                        complexity=2,
                        fn=be_rel.predict,
                        ast_nodes_per_eval=be_rel.ast_size,
                        scans_per_eval=be_rel.scan_count,
                        dsl_expr=be_rel,
                    )
                )
            for side, psi_s in (("L", psi_l), ("R", psi_r)):
                atoms.append(
                    AdapterFeature(
                        name=f"{tag}:{side}",
                        complexity=2,
                        fn=psi_s.predict,
                        ast_nodes_per_eval=psi_s.ast_size,
                        scans_per_eval=psi_s.scan_count,
                        dsl_expr=psi_s,
                    )
                )
    return atoms


@dataclass(frozen=True)
class FittedClassifier:
    """Selected depth-1/depth-2 target classifier with admission gate diagnostics."""

    formula_name: str
    complexity: int
    predict_fn: Callable[[str], bool]
    ast_nodes_per_eval: int
    scans_per_eval: int
    dsl_expr: BoolExpr | None
    train_correct: int
    validation_correct: int
    admitted: bool
    probe_agreement: float | None
    exact_candidate_count: int
    work: dict[str, int]


def fit_boolean_adapter(
    base_atoms: list[AdapterFeature],
    train: list[tuple[str, bool]],
    validation: list[tuple[str, bool]],
    seed: int,
    gated: bool,
    meter: WorkMeter | None = None,
) -> FittedClassifier:
    """Shared depth-2 boolean adapter + unlabeled probe-agreement gate.

    Used identically by `M2_strong_fixed`, `M4_random_abs`, `M5_ace_discovery`,
    `M5_ace_ungated`, and `U_native_oracle` so representation quality is isolated.
    """
    meter = meter if meter is not None else WorkMeter()
    dev_words = [w for w, _ in train] + [w for w, _ in validation]
    n_train = len(train)
    n_val = len(validation)
    n_dev = len(dev_words)
    dev_chars = sum(len(w) for w in dev_words)
    train_labels = [y for _, y in train]
    val_labels = [y for _, y in validation]

    parsed_dev: tuple[ParsedInput, ...] | None = None
    if any(a.dsl_expr is not None for a in base_atoms):
        parsed_dev = tuple(parse_dyck_input(w) for w in dev_words)

    # 1. Evaluate base atoms and negations on dev_words
    literals: list[tuple[AdapterFeature, tuple[bool, ...]]] = []
    seen_names: set[str] = set()

    # Include True/False constants
    for cv, nm in ((False, "const:false"), (True, "const:true")):
        be_c = BoolExpr(kind="const", const_val=cv)
        feat_c = AdapterFeature(nm, 1, be_c.predict, 1, 0, be_c)
        vec_c = (cv,) * n_dev
        meter.charge_expr(1, 0, dev_chars, n_dev)
        seen_names.add(nm)
        literals.append((feat_c, vec_c))

    for atom in base_atoms:
        if atom.name in seen_names:
            continue
        seen_names.add(atom.name)
        meter.charge_expr(atom.ast_nodes_per_eval, atom.scans_per_eval, dev_chars, n_dev)
        if atom.dsl_expr is not None and parsed_dev is not None:
            vec = tuple(atom.dsl_expr.eval_parsed(p) for p in parsed_dev)
        else:
            vec = tuple(bool(atom.fn(w)) for w in dev_words)
        literals.append((atom, vec))

        neg_vec = tuple(not b for b in vec)
        neg_dsl = BoolExpr(kind="not", bool_sub=atom.dsl_expr) if atom.dsl_expr is not None else None
        neg_feat = AdapterFeature(
            name=f"not({atom.name})",
            complexity=atom.complexity + 1,
            fn=(neg_dsl.predict if neg_dsl is not None else (lambda w, f=atom.fn: not bool(f(w)))),
            ast_nodes_per_eval=atom.ast_nodes_per_eval + 1,
            scans_per_eval=atom.scans_per_eval,
            dsl_expr=neg_dsl,
        )
        meter.charge_expr(neg_feat.ast_nodes_per_eval, neg_feat.scans_per_eval, dev_chars, n_dev)
        literals.append((neg_feat, neg_vec))

    # 2. Shortlist literals on training data ONLY (zero validation leakage in proposal!)
    scored_for_and: list[tuple[int, int, int, str, AdapterFeature, tuple[bool, ...]]] = []
    scored_for_or: list[tuple[int, int, int, str, AdapterFeature, tuple[bool, ...]]] = []
    for feat, vec in literals:
        if feat.name in ("const:false", "const:true"):
            continue
        tr_vec = vec[:n_train]
        tr_corr = sum(1 for p, y in zip(tr_vec, train_labels) if p == y)
        fn_count = sum(1 for p, y in zip(tr_vec, train_labels) if y and not p)
        fp_count = sum(1 for p, y in zip(tr_vec, train_labels) if (not y) and p)
        scored_for_and.append((fn_count, -tr_corr, feat.complexity, feat.name, feat, vec))
        scored_for_or.append((fp_count, -tr_corr, feat.complexity, feat.name, feat, vec))

    scored_for_and.sort(key=lambda r: r[:4])
    scored_for_or.sort(key=lambda r: r[:4])
    and_short: list[tuple[AdapterFeature, tuple[bool, ...]]] = []
    seen_and_v: set[tuple[bool, ...]] = set()
    for r in scored_for_and:
        if r[5] not in seen_and_v:
            seen_and_v.add(r[5])
            and_short.append((r[4], r[5]))
            if len(and_short) == 24:
                break
    or_short: list[tuple[AdapterFeature, tuple[bool, ...]]] = []
    seen_or_v: set[tuple[bool, ...]] = set()
    for r in scored_for_or:
        if r[5] not in seen_or_v:
            seen_or_v.add(r[5])
            or_short.append((r[4], r[5]))
            if len(or_short) == 16:
                break

    all_candidates: list[tuple[AdapterFeature, tuple[bool, ...]]] = list(literals)

    for i, (f1, v1) in enumerate(and_short):
        for f2, v2 in and_short[i + 1 :]:
            comb_vec = tuple(a and b for a, b in zip(v1, v2))
            comb_dsl = (
                BoolExpr(kind="and", bool_left=f1.dsl_expr, bool_right=f2.dsl_expr)
                if (f1.dsl_expr is not None and f2.dsl_expr is not None)
                else None
            )
            comb_feat = AdapterFeature(
                name=f"({f1.name} AND {f2.name})",
                complexity=f1.complexity + f2.complexity + 1,
                fn=(
                    comb_dsl.predict
                    if comb_dsl is not None
                    else (lambda w, g1=f1.fn, g2=f2.fn: bool(g1(w)) and bool(g2(w)))
                ),
                ast_nodes_per_eval=f1.ast_nodes_per_eval + f2.ast_nodes_per_eval + 1,
                scans_per_eval=f1.scans_per_eval + f2.scans_per_eval,
                dsl_expr=comb_dsl,
            )
            meter.charge_expr(comb_feat.ast_nodes_per_eval, comb_feat.scans_per_eval, dev_chars, n_dev)
            all_candidates.append((comb_feat, comb_vec))

    for i, (f1, v1) in enumerate(or_short):
        for f2, v2 in or_short[i + 1 :]:
            comb_vec = tuple(a or b for a, b in zip(v1, v2))
            comb_dsl = (
                BoolExpr(kind="or", bool_left=f1.dsl_expr, bool_right=f2.dsl_expr)
                if (f1.dsl_expr is not None and f2.dsl_expr is not None)
                else None
            )
            comb_feat = AdapterFeature(
                name=f"({f1.name} OR {f2.name})",
                complexity=f1.complexity + f2.complexity + 1,
                fn=(
                    comb_dsl.predict
                    if comb_dsl is not None
                    else (lambda w, g1=f1.fn, g2=f2.fn: bool(g1(w)) or bool(g2(w)))
                ),
                ast_nodes_per_eval=f1.ast_nodes_per_eval + f2.ast_nodes_per_eval + 1,
                scans_per_eval=f1.scans_per_eval + f2.scans_per_eval,
                dsl_expr=comb_dsl,
            )
            meter.charge_expr(comb_feat.ast_nodes_per_eval, comb_feat.scans_per_eval, dev_chars, n_dev)
            all_candidates.append((comb_feat, comb_vec))

    # 3. Rank all candidates by total dev fit, validation fit, minimal complexity, canonical name
    best_feat: AdapterFeature | None = None
    best_tr = -1
    best_va = -1
    best_rank: tuple[int, int, int, int] | None = None
    exact_Pool: list[AdapterFeature] = []

    for feat, vec in all_candidates:
        tr_c = sum(1 for p, y in zip(vec[:n_train], train_labels) if p == y)
        va_c = sum(1 for p, y in zip(vec[n_train:], val_labels) if p == y)
        if tr_c == n_train and va_c == n_val:
            exact_Pool.append(feat)
        rank = (tr_c + va_c, va_c, tr_c, -feat.complexity)
        if best_rank is None or rank > best_rank or (rank == best_rank and feat.name < best_feat.name):  # type: ignore[union-attr]
            best_rank = rank
            best_feat = feat
            best_tr = tr_c
            best_va = va_c

    assert best_feat is not None
    if not gated:
        return FittedClassifier(
            formula_name=best_feat.name,
            complexity=best_feat.complexity,
            predict_fn=best_feat.fn,
            ast_nodes_per_eval=best_feat.ast_nodes_per_eval,
            scans_per_eval=best_feat.scans_per_eval,
            dsl_expr=best_feat.dsl_expr,
            train_correct=best_tr,
            validation_correct=best_va,
            admitted=True,
            probe_agreement=None,
            exact_candidate_count=len(exact_Pool),
            work=meter.to_dict(),
        )

    # 4. Exact validation + unlabeled probe-agreement stability gate
    if best_tr < n_train or best_va < n_val or not exact_Pool:
        return FittedClassifier(
            formula_name=best_feat.name,
            complexity=best_feat.complexity,
            predict_fn=best_feat.fn,
            ast_nodes_per_eval=best_feat.ast_nodes_per_eval,
            scans_per_eval=best_feat.scans_per_eval,
            dsl_expr=best_feat.dsl_expr,
            train_correct=best_tr,
            validation_correct=best_va,
            admitted=False,
            probe_agreement=None,
            exact_candidate_count=0,
            work=meter.to_dict(),
        )

    min_exact_comp = min(f.complexity for f in exact_Pool)
    near_minimal = [f for f in exact_Pool if f.complexity <= min_exact_comp + PROBE_COMPLEXITY_MARGIN]
    near_minimal.sort(key=lambda f: (f.complexity, f.name))
    near_minimal = near_minimal[:16]

    probes = unlabeled_paired_tree_probes(seed, PROBE_COUNT)
    parsed_probes = tuple(parse_dyck_input(w) for w in probes)
    probe_chars = sum(len(w) for w in probes)

    probe_vecs: list[tuple[bool, ...]] = []
    for f in near_minimal:
        meter.charge_expr(f.ast_nodes_per_eval, f.scans_per_eval, probe_chars, len(probes))
        if f.dsl_expr is not None:
            pvec = tuple(f.dsl_expr.eval_parsed(p) for p in parsed_probes)
        else:
            pvec = tuple(bool(f.fn(w)) for w in probes)
        probe_vecs.append(pvec)

    min_agreement = 1.0
    for i in range(len(probe_vecs)):
        for j in range(i + 1, len(probe_vecs)):
            agree = sum(1 for a, b in zip(probe_vecs[i], probe_vecs[j]) if a == b) / len(probes)
            if agree < min_agreement:
                min_agreement = agree

    min_agreement = round(min_agreement, 6)
    admitted = min_agreement >= PROBE_AGREEMENT_THRESHOLD

    return FittedClassifier(
        formula_name=best_feat.name,
        complexity=best_feat.complexity,
        predict_fn=best_feat.fn,
        ast_nodes_per_eval=best_feat.ast_nodes_per_eval,
        scans_per_eval=best_feat.scans_per_eval,
        dsl_expr=best_feat.dsl_expr,
        train_correct=best_tr,
        validation_correct=best_va,
        admitted=admitted,
        probe_agreement=min_agreement,
        exact_candidate_count=len(exact_Pool),
        work=meter.to_dict(),
    )
