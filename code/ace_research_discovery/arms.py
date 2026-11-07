"""Benchmark capability arms M0..M5 and separately reported native upper bound.

Strictly isolated from `evaluator.py` and `tasks.py`: never inspects task names,
strata, or ground-truth functions. Integrates real `ace_runtime.engine.Runtime`
for `M1_exact_reuse` and `r1.fixed_predicates()` for `M2_strong_fixed`.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tempfile
from typing import Any, Callable

from ace_research_primitives import primitive_discovery as r1
from ace_runtime.engine import Runtime, program_from_data

from . import digest
from .discovery import (
    AdapterFeature,
    DiscoveredAbstraction,
    PROBE_AGREEMENT_THRESHOLD,
    PROBE_COMPLEXITY_MARGIN,
    PROBE_COUNT,
    SourceDiscoveryReport,
    fit_boolean_adapter,
    lift_pair_functor_atoms,
    surface_dsl_atoms,
)
from .dsl import (
    BoolExpr,
    IntExpr,
    NodePred,
    WorkMeter,
    parse_dyck_input,
    synthesize_bottom_up,
)
from .sampling import unlabeled_paired_tree_probes

C_FRESH_1X = 600
C_FRESH_4X = 2400

ARM_NAMES: tuple[str, ...] = (
    "M0_memorize",
    "M1_exact_reuse",
    "M2_strong_fixed",
    "M3_fresh_dsl",
    "M3_fresh_4x",
    "M4_random_abs",
    "M5_ace_discovery",
    "M5_ace_ungated",
)


@dataclass(frozen=True)
class ArmFitOutcome:
    """Standardized fit + admission output for any capability arm before terminal scoring."""

    arm: str
    capability_class: str
    predict_fn: Callable[[str, WorkMeter | None], bool]
    train_correct: int
    validation_correct: int
    admitted: bool
    probe_agreement: float | None
    selected_description: str
    selected_identity: str
    work: dict[str, int]
    metadata: dict[str, Any]


def partition_for_runtime_prefix_budget(
    train: list[tuple[str, bool]],
    validation: list[tuple[str, bool]],
    max_prefix_nodes: int = 63,
) -> tuple[list[list[Any]], list[list[Any]]]:
    """Partition `train + validation` so `train_rt` satisfies `ace_runtime`'s 63-prefix budget.

    Zero labels are added or discarded: any `train` examples exceeding the 63-node
    prefix-tree hardware limit of `r1.infer` move into `val_rt`, where `Runtime`
    still enforces exact admission consistency across all `B` labeled observations.
    """
    remaining = sorted(train, key=lambda row: (len(row[0]), row[0]))
    train_rt: list[list[Any]] = []
    overflow_rt: list[list[Any]] = []
    prefixes: set[str] = {""}

    while remaining and len(train_rt) < 63:
        best_idx = -1
        best_key: tuple[int, int, str] | None = None
        best_merged: set[str] | None = None
        for idx, (word, _) in enumerate(remaining):
            word_prefixes = {word[:i] for i in range(len(word) + 1)}
            merged = prefixes | word_prefixes
            if len(merged) <= max_prefix_nodes:
                added = len(merged) - len(prefixes)
                key = (added, len(word), word)
                if best_key is None or key < best_key:
                    best_key = key
                    best_idx = idx
                    best_merged = merged
        if best_idx < 0 or best_merged is None:
            break
        word, label = remaining.pop(best_idx)
        prefixes = best_merged
        train_rt.append([word, bool(label)])

    overflow_rt = [[w, bool(y)] for w, y in remaining]

    if not train_rt:
        ordered_train = sorted(train, key=lambda row: (len(row[0]), row[0]))
        first_w, first_y = ordered_train[0]
        train_rt.append([first_w, bool(first_y)])
        overflow_rt = [[w, bool(y)] for w, y in ordered_train[1:]]

    val_rt = overflow_rt + [[w, bool(y)] for w, y in validation]
    if len(val_rt) > 128:
        val_rt = val_rt[:128]
    return train_rt, val_rt


class RuntimeReuseSession:
    """Real `ace_runtime.engine.Runtime` session seeded with `S_mixed` for `M1_exact_reuse`."""

    def __init__(self, source_tasks: list[dict[str, Any]]) -> None:
        self._tmpdir = tempfile.TemporaryDirectory(prefix="ace-f6-m1-")
        self.workspace = Path(self._tmpdir.name) / "runtime_ws"
        self.runtime = Runtime(self.workspace)
        self.source_staged_count = 0
        self.source_outcomes: list[dict[str, Any]] = []

        for idx, item in enumerate(source_tasks):
            tr_rt, va_rt = partition_for_runtime_prefix_budget(item["train"], item["validation"])
            self.runtime.enqueue(
                {
                    "name": f"source_{idx:02d}",
                    "train": tr_rt,
                    "validation": va_rt,
                }
            )
        if source_tasks:
            outcomes = self.runtime.run(max_tasks=len(source_tasks))
            for out in outcomes:
                if out.get("staged"):
                    self.source_staged_count += 1
                self.source_outcomes.append(
                    {
                        "name": out["name"],
                        "phase": out.get("phase"),
                        "staged": bool(out.get("staged")),
                        "model_id": out.get("model_id"),
                    }
                )
        self.capabilities_after_source = self.runtime.status()["capabilities"]

    def close(self) -> None:
        self.runtime.close()
        self._tmpdir.cleanup()

    def __enter__(self) -> RuntimeReuseSession:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def fit_and_evaluate_target(
        self,
        slot_label: str,
        train: list[tuple[str, bool]],
        validation: list[tuple[str, bool]],
        terminal: list[tuple[str, bool]],
    ) -> tuple[ArmFitOutcome, dict[str, Any]]:
        """Enqueue target task into real `Runtime`, run, and score terminal bank."""
        tr_rt, va_rt = partition_for_runtime_prefix_budget(train, validation)
        task_id = self.runtime.enqueue(
            {
                "name": slot_label,
                "train": tr_rt,
                "validation": va_rt,
            }
        )
        outcome = self.runtime.run(max_tasks=1)[0]
        staged = bool(outcome.get("staged"))
        phase = outcome.get("phase", "FAILED")

        sel_work = (outcome.get("selection") or {}).get("work") or {}
        inh_work = ((outcome.get("inherited_selection") or {}).get("work")) or {}
        fit_rep = outcome.get("fit_report") or {}
        prop_work = fit_rep.get("proposal_work") or {}

        ast_nodes = int(sel_work.get("ast_nodes", 0)) + int(prop_work.get("ast_nodes", 0))
        if outcome.get("learning_called") and inh_work:
            ast_nodes += int(inh_work.get("ast_nodes", 0))
        symbol_steps = int(sel_work.get("dfa_character_upper_bound", 0)) + int(
            inh_work.get("dfa_character_upper_bound", 0)
        )
        cand_eval = int((outcome.get("selection") or {}).get("candidate_count", 0)) + int(
            (outcome.get("inherited_selection") or {}).get("candidate_count", 0)
        )

        # Evaluate on original (train, validation) & terminal
        if staged:
            term_rows = [[w, bool(y)] for w, y in terminal]
            rt_eval = self.runtime.evaluate(task_id, term_rows)
            tr_corr = sum(1 for w, y in train if self.runtime.predict(task_id, w) == y)
            va_corr = sum(1 for w, y in validation if self.runtime.predict(task_id, w) == y)
            preds = [self.runtime.predict(task_id, w) for w, _ in terminal]
            term_work = {
                "ast_nodes_evaluated": 0,
                "symbol_steps": sum(len(w) for w, _ in terminal),
                "candidates_evaluated": 1,
            }
            assert rt_eval["correct"] == sum(p == y for p, (_, y) in zip(preds, terminal))
            model_id = str(outcome["model_id"])

            def pred_fn(word: str, meter: WorkMeter | None = None) -> bool:
                if meter is not None:
                    meter.symbol_steps += len(word)
                return bool(self.runtime.predict(task_id, word))

            fit_out = ArmFitOutcome(
                arm="M1_exact_reuse",
                capability_class="exact_model_reuse",
                predict_fn=pred_fn,
                train_correct=tr_corr,
                validation_correct=va_corr,
                admitted=True,
                probe_agreement=None,
                selected_description=f"runtime:{phase}:{model_id[:12]}",
                selected_identity=model_id,
                work={
                    "ast_nodes_evaluated": ast_nodes,
                    "symbol_steps": symbol_steps,
                    "candidates_evaluated": cand_eval,
                },
                metadata={
                    "runtime_phase": phase,
                    "learning_called": bool(outcome.get("learning_called")),
                    "inherited_candidates": int(outcome.get("inherited_candidates", 0)),
                    "source_capabilities_in_db": self.capabilities_after_source,
                    "runtime_evaluated_in_sqlite": True,
                },
            )
            term_summary = {
                "terminal_correct": int(rt_eval["correct"]),
                "terminal_total": len(terminal),
                "terminal_accuracy": round(int(rt_eval["correct"]) / len(terminal), 6),
                "predictions_sha256": str(rt_eval["predictions_sha256"]),
                "terminal_work": term_work,
            }
            return fit_out, term_summary

        # Unstaged (`NO_VALIDATED_MODEL`): evaluate selected composition candidate diagnostically
        comp_prog_data = fit_rep["arms"]["composition"]["program"]
        prog = program_from_data(comp_prog_data)
        tr_corr = sum(1 for w, y in train if prog.predict(w) == y)
        va_corr = sum(1 for w, y in validation if prog.predict(w) == y)
        preds = [bool(prog.predict(w)) for w, _ in terminal]
        term_corr = sum(1 for p, (_, y) in zip(preds, terminal) if p == y)

        def unstaged_pred(word: str, meter: WorkMeter | None = None) -> bool:
            if meter is not None:
                meter.symbol_steps += len(word)
            return bool(prog.predict(word))

        fit_out = ArmFitOutcome(
            arm="M1_exact_reuse",
            capability_class="exact_model_reuse",
            predict_fn=unstaged_pred,
            train_correct=tr_corr,
            validation_correct=va_corr,
            admitted=False,
            probe_agreement=None,
            selected_description=f"runtime:{phase}:{prog.identity[:12]}",
            selected_identity=prog.identity,
            work={
                "ast_nodes_evaluated": ast_nodes,
                "symbol_steps": symbol_steps,
                "candidates_evaluated": cand_eval,
            },
            metadata={
                "runtime_phase": phase,
                "learning_called": bool(outcome.get("learning_called", True)),
                "inherited_candidates": int(outcome.get("inherited_candidates", 0)),
                "source_capabilities_in_db": self.capabilities_after_source,
                "runtime_evaluated_in_sqlite": False,
            },
        )
        term_summary = {
            "terminal_correct": term_corr,
            "terminal_total": len(terminal),
            "terminal_accuracy": round(term_corr / len(terminal), 6),
            "predictions_sha256": digest(preds),
            "terminal_work": {
                "ast_nodes_evaluated": 0,
                "symbol_steps": sum(len(w) for w, _ in terminal),
                "candidates_evaluated": 1,
            },
        }
        return fit_out, term_summary


def fit_memorize(
    train: list[tuple[str, bool]],
    validation: list[tuple[str, bool]],
) -> ArmFitOutcome:
    """`M0_memorize`: exact lookup on `train + validation` with deterministic Hamming NN."""
    memory_rows = sorted(train + validation, key=lambda r: (len(r[0]), r[0]))
    exact_map = {w: y for w, y in memory_rows}
    mem_chars = sum(len(w) for w, _ in memory_rows)

    def predict_nn(word: str, meter: WorkMeter | None = None) -> bool:
        if word in exact_map:
            if meter is not None:
                meter.symbol_steps += len(word)
            return exact_map[word]
        if meter is not None:
            meter.symbol_steps += len(word) * len(memory_rows) + mem_chars
        best_key: tuple[int, int, str] | None = None
        best_label = False
        for cand_w, cand_y in memory_rows:
            dist = sum(1 for a, b in zip(word, cand_w) if a != b) + abs(len(word) - len(cand_w))
            key = (dist, len(cand_w), cand_w)
            if best_key is None or key < best_key:
                best_key = key
                best_label = cand_y
        return best_label

    mem_id = digest([[w, y] for w, y in memory_rows])
    return ArmFitOutcome(
        arm="M0_memorize",
        capability_class="memorization",
        predict_fn=predict_nn,
        train_correct=len(train),
        validation_correct=len(validation),
        admitted=False,
        probe_agreement=None,
        selected_description=f"hamming_nn(n={len(memory_rows)})",
        selected_identity=mem_id,
        work={
            "ast_nodes_evaluated": 0,
            "symbol_steps": mem_chars,
            "candidates_evaluated": 1,
        },
        metadata={"memory_size": len(memory_rows)},
    )


def strong_fixed_feature_library() -> list[AdapterFeature]:
    """Build 174-predicate flat feature bank (`130` R1 fixed + `44` extended hand features)."""
    features: list[AdapterFeature] = []

    # 1. All 130 unchanged R1 predicates (65 base + 65 complements)
    for name, fn in r1.fixed_predicates():
        features.append(
            AdapterFeature(
                name=f"r1:{name}",
                complexity=2,
                fn=fn,
                ast_nodes_per_eval=3,
                scans_per_eval=1,
                dsl_expr=None,
            )
        )

    # 2. 18 length-modulo predicates (m in 3, 4, 5, 6)
    for m in (3, 4, 5, 6):
        for rem in range(m):
            features.append(
                AdapterFeature(
                    name=f"hand:len%{m}=={rem}",
                    complexity=2,
                    fn=lambda s, m=m, rem=rem: len(s) % m == rem,
                    ast_nodes_per_eval=3,
                    scans_per_eval=1,
                )
            )

    # 3. 8 count modulo-4 predicates for 'a' and 'b'
    for ch in ("a", "b"):
        for rem in range(4):
            features.append(
                AdapterFeature(
                    name=f"hand:count_{ch}%4=={rem}",
                    complexity=2,
                    fn=lambda s, ch=ch, rem=rem: s.count(ch) % 4 == rem,
                    ast_nodes_per_eval=3,
                    scans_per_eval=1,
                )
            )

    # 4. 4 global balance / ratio / Dyck checks
    features.extend(
        [
            AdapterFeature("hand:eq_ab", 2, lambda s: s.count("a") == s.count("b"), 3, 1),
            AdapterFeature("hand:a_eq_2b", 2, lambda s: s.count("a") == 2 * s.count("b"), 3, 1),
            AdapterFeature("hand:b_eq_2a", 2, lambda s: s.count("b") == 2 * s.count("a"), 3, 1),
            AdapterFeature("hand:dyck", 2, r1.dyck, 3, 1),
        ]
    )

    # 5. 8 fixed-offset index predicates (front 0..3 and back -1..-4)
    for idx in (0, 1, 2, 3):
        features.append(
            AdapterFeature(
                name=f"hand:char_{idx}==a",
                complexity=2,
                fn=lambda s, idx=idx: len(s) > idx and s[idx] == "a",
                ast_nodes_per_eval=3,
                scans_per_eval=1,
            )
        )
    for back in (1, 2, 3, 4):
        features.append(
            AdapterFeature(
                name=f"hand:char_neg{back}==a",
                complexity=2,
                fn=lambda s, back=back: len(s) >= back and s[-back] == "a",
                ast_nodes_per_eval=3,
                scans_per_eval=1,
            )
        )

    # 6. 6 length-4 prefix/suffix window predicates
    for p4 in ("aaaa", "aaab", "aaba"):
        features.append(
            AdapterFeature(f"hand:starts_{p4}", 2, lambda s, p4=p4: s.startswith(p4), 3, 1)
        )
    for s4 in ("bbbb", "abbb", "babb"):
        features.append(
            AdapterFeature(f"hand:ends_{s4}", 2, lambda s, s4=s4: s.endswith(s4), 3, 1)
        )

    assert len(features) == 174, f"expected 174 fixed features, got {len(features)}"
    return features


STRONG_FIXED_FEATURES: list[AdapterFeature] = strong_fixed_feature_library()


def fit_strong_fixed(
    train: list[tuple[str, bool]],
    validation: list[tuple[str, bool]],
    seed: int,
) -> ArmFitOutcome:
    """`M2_strong_fixed`: 174 fixed flat string features with shared adapter & gate."""
    fitted = fit_boolean_adapter(STRONG_FIXED_FEATURES, train, validation, seed=seed, gated=True)

    def pred(word: str, meter: WorkMeter | None = None) -> bool:
        if meter is not None:
            meter.ast_nodes_evaluated += fitted.ast_nodes_per_eval
            meter.symbol_steps += fitted.scans_per_eval * len(word)
        return bool(fitted.predict_fn(word))

    return ArmFitOutcome(
        arm="M2_strong_fixed",
        capability_class="strong_fixed_feature_library",
        predict_fn=pred,
        train_correct=fitted.train_correct,
        validation_correct=fitted.validation_correct,
        admitted=fitted.admitted,
        probe_agreement=fitted.probe_agreement,
        selected_description=fitted.formula_name,
        selected_identity=digest({"arm": "M2", "formula": fitted.formula_name}),
        work=fitted.work,
        metadata={
            "library_size": len(STRONG_FIXED_FEATURES),
            "exact_candidate_count": fitted.exact_candidate_count,
        },
    )


def _finalize_fresh_dsl_outcome(
    arm_name: str,
    max_candidates: int,
    candidates: list[tuple[BoolExpr, tuple[bool, ...]]],
    work_dict: dict[str, int],
    train_labels: list[bool],
    val_labels: list[bool],
    n_probes: int,
) -> ArmFitOutcome:
    n_train = len(train_labels)
    n_val = len(val_labels)
    n_dev = n_train + n_val

    best_expr: BoolExpr | None = None
    best_tr = -1
    best_va = -1
    best_rank: tuple[int, int, int, int] | None = None
    exact_pool: list[tuple[BoolExpr, tuple[bool, ...]]] = []

    for expr, full_vec in candidates:
        tr_c = sum(1 for p, y in zip(full_vec[:n_train], train_labels) if p == y)
        va_c = sum(1 for p, y in zip(full_vec[n_train:n_dev], val_labels) if p == y)
        if tr_c == n_train and va_c == n_val:
            exact_pool.append((expr, full_vec[n_dev:]))
        rank = (tr_c + va_c, va_c, tr_c, -expr.ast_size)
        if best_rank is None or rank > best_rank or (
            rank == best_rank and expr.identity < best_expr.identity  # type: ignore[union-attr]
        ):
            best_rank = rank
            best_expr = expr
            best_tr = tr_c
            best_va = va_c

    assert best_expr is not None
    admitted = False
    probe_agreement: float | None = None
    if best_tr == n_train and best_va == n_val and exact_pool:
        min_sz = min(e.ast_size for e, _ in exact_pool)
        near = [(e, pvec) for e, pvec in exact_pool if e.ast_size <= min_sz + PROBE_COMPLEXITY_MARGIN]
        near.sort(key=lambda item: (item[0].ast_size, item[0].identity))
        near = near[:16]
        min_ag = 1.0
        for i in range(len(near)):
            for j in range(i + 1, len(near)):
                ag = sum(1 for a, b in zip(near[i][1], near[j][1]) if a == b) / n_probes
                if ag < min_ag:
                    min_ag = ag
        probe_agreement = round(min_ag, 6)
        admitted = probe_agreement >= PROBE_AGREEMENT_THRESHOLD

    chosen = best_expr
    return ArmFitOutcome(
        arm=arm_name,
        capability_class="supplied_operator_composition",
        predict_fn=chosen.predict,
        train_correct=best_tr,
        validation_correct=best_va,
        admitted=admitted,
        probe_agreement=probe_agreement,
        selected_description=f"dsl(size={chosen.ast_size},id={chosen.identity[:10]})",
        selected_identity=chosen.identity,
        work=dict(work_dict),
        metadata={
            "max_bool_candidates": max_candidates,
            "unique_bool_synthesized": len(candidates),
            "selected_ast_size": chosen.ast_size,
            "selected_ast": chosen.to_data(),
            "exact_candidate_count": len(exact_pool),
        },
    )


def fit_fresh_dsl(
    train: list[tuple[str, bool]],
    validation: list[tuple[str, bool]],
    seed: int,
    max_candidates: int,
    arm_name: str,
) -> ArmFitOutcome:
    """`M3_fresh_dsl` / `M3_fresh_4x`: direct bottom-up synthesis over base combinators."""
    meter = WorkMeter()
    dev_words = [w for w, _ in train] + [w for w, _ in validation]
    probes = list(unlabeled_paired_tree_probes(seed, PROBE_COUNT))
    parsed_all = tuple(parse_dyck_input(w) for w in (dev_words + probes))

    candidates = synthesize_bottom_up(
        parsed_inputs=parsed_all,
        frames_allowed=("Whole", "LeftF", "RightF"),
        max_bool_candidates=max_candidates,
        meter=meter,
        max_ast_size=9,
    )
    return _finalize_fresh_dsl_outcome(
        arm_name=arm_name,
        max_candidates=max_candidates,
        candidates=candidates,
        work_dict=meter.to_dict(),
        train_labels=[y for _, y in train],
        val_labels=[y for _, y in validation],
        n_probes=len(probes),
    )


def fit_fresh_dsl_pair(
    train: list[tuple[str, bool]],
    validation: list[tuple[str, bool]],
    seed: int,
) -> tuple[ArmFitOutcome, ArmFitOutcome]:
    """Synthesize once up to `C_FRESH_4X` with exact checkpoint at `C_FRESH_1X`."""
    meter = WorkMeter()
    dev_words = [w for w, _ in train] + [w for w, _ in validation]
    probes = list(unlabeled_paired_tree_probes(seed, PROBE_COUNT))
    parsed_all = tuple(parse_dyck_input(w) for w in (dev_words + probes))

    cp_store: dict[int, tuple[list[tuple[BoolExpr, tuple[bool, ...]]], dict[str, int]]] = {}
    cands_4x = synthesize_bottom_up(
        parsed_inputs=parsed_all,
        frames_allowed=("Whole", "LeftF", "RightF"),
        max_bool_candidates=C_FRESH_4X,
        meter=meter,
        max_ast_size=9,
        checkpoints=(C_FRESH_1X,),
        checkpoint_store=cp_store,
    )
    cands_1x, work_1x = cp_store[C_FRESH_1X]
    train_labels = [y for _, y in train]
    val_labels = [y for _, y in validation]
    out_1x = _finalize_fresh_dsl_outcome(
        arm_name="M3_fresh_dsl",
        max_candidates=C_FRESH_1X,
        candidates=cands_1x,
        work_dict=work_1x,
        train_labels=train_labels,
        val_labels=val_labels,
        n_probes=len(probes),
    )
    out_4x = _finalize_fresh_dsl_outcome(
        arm_name="M3_fresh_4x",
        max_candidates=C_FRESH_4X,
        candidates=cands_4x,
        work_dict=meter.to_dict(),
        train_labels=train_labels,
        val_labels=val_labels,
        n_probes=len(probes),
    )
    return out_1x, out_4x


SURFACE_ATOMS_CACHE: tuple[AdapterFeature, ...] = tuple(surface_dsl_atoms())


def build_transfer_atom_bank(abstractions: tuple[DiscoveredAbstraction, ...]) -> list[AdapterFeature]:
    """Materialize functor-lifted relational pair atoms + shared surface atoms."""
    return lift_pair_functor_atoms(abstractions) + list(SURFACE_ATOMS_CACHE)


def fit_transfer_abstractions(
    arm_name: str,
    capability_class: str,
    abstractions: tuple[DiscoveredAbstraction, ...],
    train: list[tuple[str, bool]],
    validation: list[tuple[str, bool]],
    seed: int,
    gated: bool,
    raw_source_work: dict[str, int],
    n_target_tasks_for_amortization: int,
    prebuilt_atoms: list[AdapterFeature] | None = None,
) -> ArmFitOutcome:
    """Fit target adapter over functor-lifted unary abstractions + common surface atoms."""
    atoms = prebuilt_atoms if prebuilt_atoms is not None else build_transfer_atom_bank(abstractions)
    fitted = fit_boolean_adapter(atoms, train, validation, seed=seed, gated=gated)

    amortized_ast = round(raw_source_work["ast_nodes_evaluated"] / max(1, n_target_tasks_for_amortization))
    amortized_steps = round(raw_source_work["symbol_steps"] / max(1, n_target_tasks_for_amortization))
    amortized_cands = round(raw_source_work["candidates_evaluated"] / max(1, n_target_tasks_for_amortization))

    def pred(word: str, meter: WorkMeter | None = None) -> bool:
        if fitted.dsl_expr is not None:
            return fitted.dsl_expr.predict(word, meter)
        if meter is not None:
            meter.ast_nodes_evaluated += fitted.ast_nodes_per_eval
            meter.symbol_steps += fitted.scans_per_eval * len(word)
        return bool(fitted.predict_fn(word))

    ident = fitted.dsl_expr.identity if fitted.dsl_expr is not None else digest(fitted.formula_name)
    return ArmFitOutcome(
        arm=arm_name,
        capability_class=capability_class,
        predict_fn=pred,
        train_correct=fitted.train_correct,
        validation_correct=fitted.validation_correct,
        admitted=fitted.admitted,
        probe_agreement=fitted.probe_agreement,
        selected_description=fitted.formula_name,
        selected_identity=ident,
        work={
            "ast_nodes_evaluated": fitted.work["ast_nodes_evaluated"],
            "symbol_steps": fitted.work["symbol_steps"],
            "candidates_evaluated": fitted.work["candidates_evaluated"],
            "amortized_source_ast_nodes": amortized_ast,
            "amortized_source_symbol_steps": amortized_steps,
            "amortized_source_candidates": amortized_cands,
            "total_amortized_ast_nodes": fitted.work["ast_nodes_evaluated"] + amortized_ast,
            "total_amortized_symbol_steps": fitted.work["symbol_steps"] + amortized_steps,
        },
        metadata={
            "transferred_abstraction_count": len(abstractions),
            "adapter_atom_count": len(atoms),
            "gated": gated,
            "selected_ast": fitted.dsl_expr.to_data() if fitted.dsl_expr is not None else None,
            "exact_candidate_count": fitted.exact_candidate_count,
        },
    )


def native_oracle_abstractions() -> tuple[DiscoveredAbstraction, ...]:
    """Hand-authored exact structural projections for the SEPARATE upper-bound report.

    NEVER used by `M0..M5` and NEVER placed inside `report['arms']`.
    """
    specs: list[IntExpr] = [
        IntExpr(kind="max_nodes", frame="SlotF", attr="depth"),
        IntExpr(kind="count_nodes", frame="SlotF", npred=NodePred("eq", "deg", 0)),
        IntExpr(kind="count_nodes", frame="SlotF", npred=NodePred("eq", "depth", 2)),
        IntExpr(kind="signed_balance", frame="SlotF", npred=NodePred("mod_eq", "depth", 2, 1)),
        IntExpr(kind="max_nodes", frame="SlotF", attr="deg"),
        IntExpr(kind="count_nodes", frame="SlotF", npred=NodePred("ge", "deg", 2)),
    ]
    out: list[DiscoveredAbstraction] = []
    for ie in specs:
        out.append(
            DiscoveredAbstraction(
                kind="int",
                int_expr=ie,
                bool_expr=None,
                ast_size=ie.ast_size,
                entropy_bits=0.0,
                non_mode_rate=1.0,
                source_reuse_count=0,
                utility_score=0.0,
                identity=ie.identity,
            )
        )
    return tuple(out)


ORACLE_ABSTRACTIONS: tuple[DiscoveredAbstraction, ...] = native_oracle_abstractions()
ORACLE_ATOMS_CACHE: list[AdapterFeature] = build_transfer_atom_bank(ORACLE_ABSTRACTIONS)


def fit_native_oracle_upper_bound(
    train: list[tuple[str, bool]],
    validation: list[tuple[str, bool]],
    seed: int,
) -> ArmFitOutcome:
    """Fit separate researcher-authored native structural oracle upper bound."""
    return fit_transfer_abstractions(
        arm_name="U_native_oracle",
        capability_class="native_solver_upper_bound",
        abstractions=ORACLE_ABSTRACTIONS,
        train=train,
        validation=validation,
        seed=seed,
        gated=True,
        raw_source_work={"ast_nodes_evaluated": 0, "symbol_steps": 0, "candidates_evaluated": 0},
        n_target_tasks_for_amortization=1,
        prebuilt_atoms=ORACLE_ATOMS_CACHE,
    )
