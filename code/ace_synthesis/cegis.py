"""Counterexample-Guided Inductive Synthesis (CEGIS).

Operates an efficient verifier-synthesizer loop:
- Synthesizer proposes candidates satisfying a compact counterexample set C.
- Verifier searches for a counterexample on the specification / full training split.
- Guaranteed termination with minimal observation checks.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

from ace_evolution.island_search import EvolutionaryIslandSearch, ProgramCandidate, TypedASTNode


@dataclass
class SynthesisResult:
    status: str  # SUCCESS, TIMEOUT, UNSAT
    candidate: Optional[ProgramCandidate]
    iterations: int
    counterexamples_used: int
    total_evaluations: int
    runtime_sec: float
    function_code: str


class CEGISSynthesizer:
    """Counterexample-Guided Inductive Synthesizer."""

    def __init__(self, max_iterations: int = 15, timeout_sec: float = 30.0):
        self.max_iterations = max_iterations
        self.timeout_sec = timeout_sec

    def synthesize(
        self,
        full_spec_data: List[Tuple[str, bool]],
        func_name: str = "cegis_solution",
    ) -> SynthesisResult:
        import time
        start_time = time.time()

        if not full_spec_data:
            return SynthesisResult(
                status="UNSAT",
                candidate=None,
                iterations=0,
                counterexamples_used=0,
                total_evaluations=0,
                runtime_sec=0.0,
                function_code=""
            )

        # 1. Initialize counterexample set with 1 positive and 1 negative example if available
        positives = [d for d in full_spec_data if d[1]]
        negatives = [d for d in full_spec_data if not d[1]]
        C: List[Tuple[str, bool]] = []
        if positives:
            C.append(positives[0])
        if negatives:
            C.append(negatives[0])
        if not C:
            C.append(full_spec_data[0])

        total_evals = 0
        iterations = 0

        while iterations < self.max_iterations:
            iterations += 1
            if time.time() - start_time > self.timeout_sec:
                break

            # 2. Synthesizer step: find candidate consistent with C
            searcher = EvolutionaryIslandSearch(num_islands=2, island_population=12, max_depth=3, seed=iterations * 17)
            candidate = searcher.search(train_data=C, max_generations=10, target_accuracy=1.0)
            total_evals += len(C) * 12 * 2

            # 3. Verifier step: find a counterexample in full_spec_data
            counterexample = None
            for word, label in full_spec_data:
                total_evals += 1
                try:
                    pred = bool(candidate.root.evaluate(word))
                except Exception:
                    pred = False
                if pred != label:
                    counterexample = (word, label)
                    break

            # 4. If no counterexample found, candidate satisfies the full spec!
            if counterexample is None:
                duration = time.time() - start_time
                code = candidate.to_python_function(func_name)
                return SynthesisResult(
                    status="SUCCESS",
                    candidate=candidate,
                    iterations=iterations,
                    counterexamples_used=len(C),
                    total_evaluations=total_evals,
                    runtime_sec=duration,
                    function_code=code
                )

            # 5. Add counterexample constraint to C
            C.append(counterexample)

        # Fallback if iterations exhausted
        duration = time.time() - start_time
        return SynthesisResult(
            status="TIMEOUT",
            candidate=None,
            iterations=iterations,
            counterexamples_used=len(C),
            total_evaluations=total_evals,
            runtime_sec=duration,
            function_code=""
        )
