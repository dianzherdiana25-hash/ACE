"""Active Epistemic Prober & Boundary Discriminator for ACE Intelligence Evolution.

Implements Active Epistemic Querying (AEQ):
- Resolves the unobservable semantic drift barrier identified in Fase 1 (R9) and Fase 7 (G0->G2).
- Synthesizes targeted boundary-differentiating queries between candidate models and reference specifications.
- Falsifies drifted or Trojaned candidates before admission.
- Interacts with native ACE Runtime to record verifiable task receipts.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import random
import time
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from . import ACE_RUNTIME_ROLE, GEMINI_ROLE, OAIE_ESTABLISHED, RELEASE_GATE, SCHEMA_VERSION, SCIENTIFIC_STATUS


class DivergentQuerySynthesizer:
    """Synthesizes boundary-probing inputs designed to expose latent semantic divergence."""

    def __init__(self, alphabet: Tuple[str, ...] = ("a", "b")):
        self.alphabet = alphabet

    def minimal_string_mutations(self, seeds: List[str], max_mutations_per_seed: int = 4) -> List[str]:
        """Generate 1-edit distance string variations (substitutions, insertions, deletions)."""
        probes: Set[str] = set()
        for s in seeds:
            # 1. Substitutions
            for i in range(len(s)):
                for ch in self.alphabet:
                    if s[i] != ch:
                        probes.add(s[:i] + ch + s[i + 1:])
            # 2. Insertions
            for i in range(len(s) + 1):
                for ch in self.alphabet:
                    probes.add(s[:i] + ch + s[i:])
            # 3. Deletions
            if len(s) > 1:
                for i in range(len(s)):
                    probes.add(s[:i] + s[i + 1:])

        result = sorted(list(probes))
        # Keep deterministic subset
        return result

    def synthesize_discriminating_probes(
        self,
        candidate_fn: Callable[[str], bool],
        reference_fn: Callable[[str], bool],
        seeds: List[str],
        max_probes: int = 8,
    ) -> List[str]:
        """Find inputs q in candidate neighborhood where candidate_fn(q) != reference_fn(q)."""
        neighborhood = self.minimal_string_mutations(seeds)
        differentiating: List[str] = []
        for q in neighborhood:
            try:
                c_pred = bool(candidate_fn(q))
                r_pred = bool(reference_fn(q))
                if c_pred != r_pred:
                    differentiating.append(q)
                    if len(differentiating) >= max_probes:
                        break
            except Exception:
                continue

        # If neighborhood exhausted, perform systematic short-string search
        if len(differentiating) < max_probes:
            for length in range(1, 7):
                for candidate in self._generate_all(length):
                    if candidate not in differentiating:
                        try:
                            if bool(candidate_fn(candidate)) != bool(reference_fn(candidate)):
                                differentiating.append(candidate)
                                if len(differentiating) >= max_probes:
                                    break
                        except Exception:
                            continue
                if len(differentiating) >= max_probes:
                    break

        return differentiating[:max_probes]

    def _generate_all(self, length: int) -> List[str]:
        if length == 0:
            return [""]
        smaller = self._generate_all(length - 1)
        return [s + ch for s in smaller for ch in self.alphabet]


class ActiveEpistemicProber:
    """Interrogates an environment/oracle with targeted probes to falsify candidate drift."""

    def __init__(self, alphabet: Tuple[str, ...] = ("a", "b"), seed: int = 42):
        self.synthesizer = DivergentQuerySynthesizer(alphabet=alphabet)
        self.rng = random.Random(seed)

    def evaluate_candidate(
        self,
        candidate_fn: Callable[[str], bool],
        reference_fn: Callable[[str], bool],
        oracle_fn: Callable[[str], bool],
        train_examples: List[Tuple[str, bool]],
        val_examples: List[Tuple[str, bool]],
        mode: str = "active",
        query_budget: int = 8,
        runtime: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Evaluate a candidate model under passive, random fuzzing, or active epistemic probing.

        Modes:
        - 'passive': Evaluates only on train_examples and val_examples (0 interactive queries).
        - 'random': Queries oracle with uniformly random inputs outside train/val set.
        - 'active': Synthesizes boundary queries differentiating candidate vs reference.
        """
        t0 = time.perf_counter()
        train_acc = sum(candidate_fn(x) == y for x, y in train_examples) / max(1, len(train_examples))
        val_acc = sum(candidate_fn(x) == y for x, y in val_examples) / max(1, len(val_examples))

        if val_acc < 1.0:
            # Did not even satisfy validation data
            elapsed = time.perf_counter() - t0
            return {
                "mode": mode,
                "train_acc": train_acc,
                "val_acc": val_acc,
                "queries_used": 0,
                "admitted": False,
                "falsified": True,
                "falsifying_counterexample": None,
                "reason": "validation_accuracy_suboptimal",
                "elapsed_seconds": round(elapsed, 4),
                "runtime_receipts": [],
            }

        queries_used = 0
        falsified = False
        counterexample: Optional[str] = None
        receipts: List[Dict[str, Any]] = []
        tested_queries: List[str] = []

        if mode == "passive":
            # Passive acceptance based purely on validation accuracy
            admitted = True

        elif mode == "random":
            # Generate random strings of length 1 to 6
            admitted = True
            known_inputs = {x for x, _ in train_examples} | {x for x, _ in val_examples}
            sampled_queries = []
            while len(sampled_queries) < query_budget:
                length = self.rng.randint(1, 6)
                q = "".join(self.rng.choice(self.synthesizer.alphabet) for _ in range(length))
                if q not in known_inputs and q not in sampled_queries:
                    sampled_queries.append(q)

            for q in sampled_queries:
                queries_used += 1
                c_out = bool(candidate_fn(q))
                truth = bool(oracle_fn(q))
                tested_queries.append(q)
                receipt = self._record_receipt(q, c_out, truth, runtime)
                receipts.append(receipt)
                if c_out != truth:
                    falsified = True
                    admitted = False
                    counterexample = q
                    break

        elif mode in ("active", "resource_bounded"):
            # Synthesize targeted boundary queries
            seed_strings = [x for x, _ in train_examples[:8]]
            probes = self.synthesizer.synthesize_discriminating_probes(
                candidate_fn, reference_fn, seed_strings, max_probes=query_budget
            )
            admitted = True
            for q in probes:
                queries_used += 1
                c_out = bool(candidate_fn(q))
                truth = bool(oracle_fn(q))
                tested_queries.append(q)
                receipt = self._record_receipt(q, c_out, truth, runtime)
                receipts.append(receipt)
                if c_out != truth:
                    falsified = True
                    admitted = False
                    counterexample = q
                    break
        else:
            raise ValueError(f"Unknown mode: {mode}")

        elapsed = time.perf_counter() - t0
        return {
            "mode": mode,
            "train_acc": train_acc,
            "val_acc": val_acc,
            "queries_used": queries_used,
            "tested_queries": tested_queries,
            "admitted": admitted,
            "falsified": falsified,
            "falsifying_counterexample": counterexample,
            "reason": "drift_falsified" if falsified else "passed_admission",
            "elapsed_seconds": round(elapsed, 4),
            "runtime_receipts": receipts,
        }

    def _record_receipt(
        self, query: str, candidate_output: bool, ground_truth: bool, runtime: Optional[Any]
    ) -> Dict[str, Any]:
        """Record deterministic cryptographic receipt of query evaluation."""
        raw_payload = f"q:{query}|c:{int(candidate_output)}|t:{int(ground_truth)}|ts:{time.time():.4f}"
        receipt_sha256 = hashlib.sha256(raw_payload.encode("utf-8")).hexdigest()
        receipt = {
            "query": query,
            "candidate_output": candidate_output,
            "ground_truth": ground_truth,
            "match": candidate_output == ground_truth,
            "receipt_sha256": receipt_sha256,
        }
        if runtime is not None and hasattr(runtime, "enqueue"):
            try:
                # Wrap as lightweight runtime task
                task_payload = {
                    "kind": "epistemic_probe",
                    "query": query,
                    "receipt_sha256": receipt_sha256,
                }
                task_id = runtime.enqueue(task_payload)
                receipt["runtime_task_id"] = task_id
            except Exception:
                pass
        return receipt
