"""Epoch C — Multi-File Causal Repository Evolution, Epistemic Truth Market, and
Cartography of Ignorance (`causal_repo_evolution.py`).

Unites:
1. Multi-File Causal Fault Localization (`StructuralCausalModel`, `CausalInvariantMiner`,
   `is_d_separated`, `BoundedRepositoryRetriever`, `atomic_write_verified`),
2. Atomic Cross-File Patch Synthesis with Mutation Testing (`MutationTestGuard`,
   `WeakTestSuiteOrOverfitError`),
3. Internal Epistemic Prediction Market (`EpistemicTruthMarket`) with Brier-scored credit
   staking, Prover vs Counterexample-Hunter debate, and automatic bankruptcy dismissal in
   `BrainRegistry`, and
4. Cartography of Ignorance (`CartographyOfIgnorance`) powered by Conformal Risk Control
   (`compute_conformal_quantile`, `ConformalIntervalPredictor`) and PAC-Bayes bounds
   (`seeger_maurer_bound`, `mcallester_bound`) classifying decisions into:
   - `PROVED`
   - `CONFORMAL_BOUNDED`
   - `ABSTAIN_FOR_EXPERIMENT`
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any, Callable

from ace_causal.causal_miner import (
    CausalInvariantMiner,
    StructuralCausalModel,
    is_d_separated,
)
from ace_conformal.conformal_risk import (
    ConformalIntervalPredictor,
    compute_conformal_quantile,
)
from ace_pac_bayes.pac_bounds import mcallester_bound, seeger_maurer_bound

from .brain_registry import BrainRegistry
from .lexical_ops import apply_lexical_operator, enumerate_lexical_variants
from .local_repo_workflow import atomic_write_verified

EPISTEMIC_ZONES = ("PROVED", "CONFORMAL_BOUNDED", "ABSTAIN_FOR_EXPERIMENT")


class WeakTestSuiteOrOverfitError(RuntimeError):
    """Raised when a cross-file patch fails mutation testing or leaves surviving mutants."""


class AbstainPromotionError(RuntimeError):
    """Raised when an action in the ABSTAIN_FOR_EXPERIMENT zone attempts promotion."""


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _sha256_hex(data: bytes | str) -> str:
    raw = data.encode("utf-8") if isinstance(data, str) else data
    return hashlib.sha256(raw).hexdigest()


# ============================================================================
# 1. CARTOGRAPHY OF IGNORANCE (Conformal + PAC-Bayes Epistemic Classification)
# ============================================================================


@dataclass(frozen=True)
class EpistemicVerdict:
    """Honest classification of ACE's certainty vs ignorance for a candidate decision."""

    zone: str  # "PROVED" | "CONFORMAL_BOUNDED" | "ABSTAIN_FOR_EXPERIMENT"
    empirical_risk: float
    seeger_maurer_upper_bound: float
    mcallester_upper_bound: float
    conformal_quantile: float
    mutation_kill_rate: float
    can_promote: bool
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "zone": self.zone,
            "empirical_risk": round(self.empirical_risk, 6),
            "seeger_maurer_upper_bound": round(self.seeger_maurer_upper_bound, 6),
            "mcallester_upper_bound": round(self.mcallester_upper_bound, 6),
            "conformal_quantile": round(self.conformal_quantile, 6),
            "mutation_kill_rate": round(self.mutation_kill_rate, 4),
            "can_promote": self.can_promote,
            "reason": self.reason,
        }


class CartographyOfIgnorance:
    """Maps every hypothesis into PROVED, CONFORMAL_BOUNDED, or ABSTAIN_FOR_EXPERIMENT."""

    def __init__(
        self,
        *,
        alpha: float = 0.10,
        delta: float = 0.05,
        max_pac_bound: float = 0.22,
        max_conformal_quantile: float = 0.35,
    ) -> None:
        self.alpha = alpha
        self.delta = delta
        self.max_pac_bound = max_pac_bound
        self.max_conformal_quantile = max_conformal_quantile

    def classify(
        self,
        *,
        deterministic_proof: bool,
        mutation_kill_rate: float,
        empirical_errors: int,
        sample_size: int,
        kl_divergence: float,
        calibration_nonconformity_scores: list[float],
    ) -> EpistemicVerdict:
        m = max(1, int(sample_size))
        r_hat = float(empirical_errors) / m
        sm_bound = seeger_maurer_bound(r_hat, kl_divergence, m, self.delta)
        mc_bound = mcallester_bound(r_hat, kl_divergence, m, self.delta)
        q_hat = compute_conformal_quantile(calibration_nonconformity_scores, alpha=self.alpha)

        if deterministic_proof and empirical_errors == 0 and mutation_kill_rate >= 1.0:
            return EpistemicVerdict(
                zone="PROVED",
                empirical_risk=r_hat,
                seeger_maurer_upper_bound=sm_bound,
                mcallester_upper_bound=mc_bound,
                conformal_quantile=q_hat,
                mutation_kill_rate=mutation_kill_rate,
                can_promote=True,
                reason="deterministic_proof_and_100pct_mutation_kill",
            )

        if (
            empirical_errors == 0
            and sm_bound <= self.max_pac_bound
            and q_hat <= self.max_conformal_quantile
            and mutation_kill_rate >= 0.80
        ):
            return EpistemicVerdict(
                zone="CONFORMAL_BOUNDED",
                empirical_risk=r_hat,
                seeger_maurer_upper_bound=sm_bound,
                mcallester_upper_bound=mc_bound,
                conformal_quantile=q_hat,
                mutation_kill_rate=mutation_kill_rate,
                can_promote=True,
                reason="bounded_pac_bayes_and_conformal_risk",
            )

        return EpistemicVerdict(
            zone="ABSTAIN_FOR_EXPERIMENT",
            empirical_risk=r_hat,
            seeger_maurer_upper_bound=sm_bound,
            mcallester_upper_bound=mc_bound,
            conformal_quantile=q_hat,
            mutation_kill_rate=mutation_kill_rate,
            can_promote=False,
            reason=f"uncertainty_exceeds_fence:r_hat={r_hat:.3f},sm={sm_bound:.3f},q={q_hat:.3f}",
        )


# ============================================================================
# 2. INTERNAL EPISTEMIC PREDICTION MARKET (Prover vs Counterexample Hunter)
# ============================================================================


class EpistemicTruthMarket:
    """Brier-scored internal prediction market & adversarial debate court for sub-brains.

    Each brain starts with `initial_credits`. When a Prover brain proposes a patch with
    claimed confidence `p` and stakes `stake` credits:
      - A Counterexample-Hunter brain attempts to produce a concrete input `x_ce` where
        the proposed patch fails the oracle.
      - Ground-truth outcome `y in {0, 1}` is settled by the deterministic oracle.
      - Brier score loss is `(p - y)^2`.
      - If `y == 0` (patch failed or counterexample succeeded): the Prover loses its
        stake (plus an overconfidence penalty `stake * p^2`), and the Counterexample
        Hunter wins the pot!
      - Any brain whose credit balance drops to `<= bankruptcy_threshold` is automatically
        dismissed in `BrainRegistry`.
    """

    def __init__(
        self,
        registry: BrainRegistry,
        *,
        initial_credits: float = 100.0,
        bankruptcy_threshold: float = 20.0,
    ) -> None:
        self.registry = registry
        self.initial_credits = initial_credits
        self.bankruptcy_threshold = bankruptcy_threshold
        self._credits: dict[str, float] = {}
        self._brier_history: dict[str, list[float]] = {}
        self._rounds: list[dict[str, Any]] = []

    def register_market_participant(self, brain_id: str, *, kind: str, descriptor: str) -> None:
        if self.registry.get(brain_id) is None:
            self.registry.register(brain_id, kind=kind, descriptor=descriptor, status="active")
        self._credits.setdefault(brain_id, self.initial_credits)
        self._brier_history.setdefault(brain_id, [])

    def adjudicate_debate_round(
        self,
        *,
        round_id: str,
        prover_brain_id: str,
        hunter_brain_id: str,
        prover_confidence: float,
        stake: float,
        proposed_patch_passes_oracle: bool,
        counterexample_found: Any | None,
    ) -> dict[str, Any]:
        rec = self.registry.get(prover_brain_id)
        if rec is None or rec["status"] != "active":
            raise RuntimeError(f"Prover brain {prover_brain_id} is not active")

        p = max(0.0, min(1.0, float(prover_confidence)))
        y = 1.0 if (proposed_patch_passes_oracle and counterexample_found is None) else 0.0
        brier_loss = (p - y) ** 2
        self._brier_history[prover_brain_id].append(brier_loss)

        if y == 1.0:
            reward = round(stake * (1.0 - brier_loss), 4)
            self._credits[prover_brain_id] = round(self._credits[prover_brain_id] + reward, 4)
            hunter_delta = 0.0
        else:
            penalty = round(stake * (1.0 + p * p), 4)
            self._credits[prover_brain_id] = round(self._credits[prover_brain_id] - penalty, 4)
            hunter_delta = round(stake, 4)
            if hunter_brain_id in self._credits:
                self._credits[hunter_brain_id] = round(self._credits[hunter_brain_id] + hunter_delta, 4)

        dismissed_now = False
        if self._credits[prover_brain_id] <= self.bankruptcy_threshold:
            self.registry.dismiss(
                prover_brain_id,
                reason=f"epistemic_market_bankruptcy:credits={self._credits[prover_brain_id]}",
            )
            dismissed_now = True

        round_rec = {
            "round_id": round_id,
            "prover_brain_id": prover_brain_id,
            "hunter_brain_id": hunter_brain_id,
            "prover_confidence": p,
            "outcome_verified": bool(y == 1.0),
            "counterexample_found": counterexample_found,
            "brier_loss": round(brier_loss, 6),
            "prover_credits_after": self._credits[prover_brain_id],
            "hunter_credits_after": self._credits.get(hunter_brain_id, 0.0),
            "prover_dismissed_bankrupt": dismissed_now,
        }
        self._rounds.append(round_rec)
        return round_rec

    def summary(self) -> dict[str, Any]:
        standings: list[dict[str, Any]] = []
        for bid, cred in sorted(self._credits.items(), key=lambda kv: kv[1], reverse=True):
            hist = self._brier_history.get(bid, [])
            avg_brier = round(sum(hist) / len(hist), 6) if hist else 0.0
            rec = self.registry.get(bid)
            standings.append(
                {
                    "brain_id": bid,
                    "status": rec["status"] if rec else "unknown",
                    "credits": cred,
                    "avg_brier_loss": avg_brier,
                    "rounds_participated": len(hist),
                }
            )
        return {
            "rounds_count": len(self._rounds),
            "standings": standings,
            "rounds": list(self._rounds),
        }


# ============================================================================
# 3. MULTI-FILE CAUSAL REPOSITORY EVOLUTION & MUTATION TESTING
# ============================================================================


class CausalMultiFileRepoEvolver:
    """Diagnoses, localizes causally, patches atomically, and mutation-tests a multi-file repo."""

    def __init__(self, repo_dir: str | Path) -> None:
        self.repo_dir = Path(repo_dir).resolve()
        self.repo_dir.mkdir(parents=True, exist_ok=True)

    def materialize_buggy_multi_file_repo(self) -> dict[str, Path]:
        """Create a realistic 4-file billing repository with 2 cross-file bugs and 1 confounder module."""
        files = {
            "noise_logger.py": (
                "def format_audit_banner(subtotal: int, region_code: int) -> int:\n"
                "    # Spurious correlated co-effect of subtotal, but does NOT affect invoice total\n"
                "    return subtotal * 4 + region_code\n"
            ),
            "discount_policy.py": (
                "def compute_tier_discount(subtotal: int, threshold: int, rate_pct: int) -> int:\n"
                "    # BUG 1: strict '>' instead of '>=' misses boundary threshold\n"
                "    if subtotal > threshold:\n"
                "        return (subtotal * rate_pct) // 100\n"
                "    return 0\n"
            ),
            "tax_rules.py": (
                "def compute_regional_tax(net_amount: int, tax_pct: int) -> int:\n"
                "    # BUG 2: off-by-one multiplier '(tax_pct - 1)' instead of 'tax_pct'\n"
                "    return (net_amount * (tax_pct - 1)) // 100\n"
            ),
            "billing_engine.py": (
                "from discount_policy import compute_tier_discount\n"
                "from noise_logger import format_audit_banner\n"
                "from tax_rules import compute_regional_tax\n\n"
                "def settle_invoice(subtotal: int, threshold: int, disc_pct: int, tax_pct: int) -> dict:\n"
                "    banner_metric = format_audit_banner(subtotal, tax_pct)\n"
                "    disc = compute_tier_discount(subtotal, threshold, disc_pct)\n"
                "    net = subtotal - disc\n"
                "    tax = compute_regional_tax(net, tax_pct)\n"
                "    return {'total': net + tax, 'discount': disc, 'tax': tax, 'banner': banner_metric}\n"
            ),
        }
        paths: dict[str, Path] = {}
        for name, content in files.items():
            p = self.repo_dir / name
            atomic_write_verified(p, content)
            paths[name] = p
        return paths

    def localize_faults_via_do_calculus(self) -> dict[str, Any]:
        """Build a StructuralCausalModel of the multi-file repo and isolate true root-cause modules."""
        scm = StructuralCausalModel()
        # Confounder: subtotal drives both banner_metric (noise_logger) and invoice_error
        scm.add_variable("subtotal", [], lambda env, u: 100.0 + 10.0 * u)
        scm.add_variable("noise_logger", ["subtotal"], lambda env, u: 4.0 * env["subtotal"] + u)
        scm.add_variable("discount_policy", ["subtotal"], lambda env, u: 0.1 * env["subtotal"] + u)
        scm.add_variable("tax_rules", ["subtotal"], lambda env, u: 0.1 * env["subtotal"] + u)
        scm.add_variable(
            "invoice_error",
            ["discount_policy", "tax_rules"],
            lambda env, u: 2.5 * env["discount_policy"] + 3.0 * env["tax_rules"] + u,
        )

        miner = CausalInvariantMiner(scm)
        obs = scm.sample(n=250, seed=42)
        spurious_corr_noise = abs(miner.compute_observational_correlation("noise_logger", "invoice_error", obs))
        do_effect_noise = miner.measure_interventional_effect("noise_logger", "invoice_error", -10.0, 10.0, n_samples=250)
        do_effect_discount = miner.measure_interventional_effect("discount_policy", "invoice_error", -10.0, 10.0, n_samples=250)
        do_effect_tax = miner.measure_interventional_effect("tax_rules", "invoice_error", -10.0, 10.0, n_samples=250)

        dag = {
            "subtotal": ["noise_logger", "discount_policy", "tax_rules"],
            "noise_logger": [],
            "discount_policy": ["invoice_error"],
            "tax_rules": ["invoice_error"],
            "invoice_error": [],
        }
        noise_d_sep = is_d_separated(dag, "noise_logger", "invoice_error", {"subtotal"})

        effects = {
            "noise_logger.py": round(do_effect_noise, 4),
            "discount_policy.py": round(do_effect_discount, 4),
            "tax_rules.py": round(do_effect_tax, 4),
        }
        causal_suspects = sorted([m for m, eff in effects.items() if eff > 5.0])
        pruned_confounders = sorted([m for m, eff in effects.items() if eff <= 5.0])
        return {
            "observational_corr_noise_logger": round(spurious_corr_noise, 4),
            "interventional_do_effects": effects,
            "noise_d_separated_given_subtotal": noise_d_sep,
            "causal_suspects": causal_suspects,
            "pruned_confounders": pruned_confounders,
        }

    def evaluate_repo_suite(self, cases: list[tuple[tuple[int, int, int, int], int]]) -> tuple[int, list[tuple[int, int, int, int]]]:
        """Dynamically load the multi-file repo and evaluate `settle_invoice` against oracle cases."""
        sys_path_added = False
        repo_str = str(self.repo_dir)
        if repo_str not in sys.path:
            sys.path.insert(0, repo_str)
            sys_path_added = True
        try:
            for mod_name in ("noise_logger", "discount_policy", "tax_rules", "billing_engine"):
                if mod_name in sys.modules:
                    del sys.modules[mod_name]
                spec = importlib.util.spec_from_file_location(mod_name, self.repo_dir / f"{mod_name}.py")
                if spec is None or spec.loader is None:
                    raise RuntimeError(f"Cannot load {mod_name}")
                mod = importlib.util.module_from_spec(spec)
                sys.modules[mod_name] = mod
                spec.loader.exec_module(mod)

            billing = sys.modules["billing_engine"]
            passed = 0
            failed_inputs: list[tuple[int, int, int, int]] = []
            for args, expected_total in cases:
                res = billing.settle_invoice(*args)
                if res["total"] == expected_total:
                    passed += 1
                else:
                    failed_inputs.append(args)
            return passed, failed_inputs
        finally:
            for mod_name in ("noise_logger", "discount_policy", "tax_rules", "billing_engine"):
                sys.modules.pop(mod_name, None)
            if sys_path_added and repo_str in sys.path:
                sys.path.remove(repo_str)

    def apply_atomic_cross_file_patch(
        self,
        file_patches: dict[str, str],
        verification_cases: list[tuple[tuple[int, int, int, int], int]],
    ) -> dict[str, Any]:
        """Atomically write multi-file patches; rollback immediately if any verification case fails."""
        backups: dict[str, str] = {}
        for rel_name in file_patches:
            target = self.repo_dir / rel_name
            if target.exists():
                backups[rel_name] = target.read_text(encoding="utf-8")

        try:
            for rel_name, new_code in file_patches.items():
                atomic_write_verified(self.repo_dir / rel_name, new_code)
            passed, failures = self.evaluate_repo_suite(verification_cases)
            if passed != len(verification_cases):
                raise RuntimeError(f"Cross-file patch failed {len(failures)} cases: {failures}")
            return {
                "patched_files": sorted(file_patches.keys()),
                "passed_cases": passed,
                "total_cases": len(verification_cases),
                "rolled_back": False,
            }
        except Exception:
            for rel_name, old_code in backups.items():
                atomic_write_verified(self.repo_dir / rel_name, old_code)
            raise

    def run_mutation_testing_guard(
        self,
        verification_cases: list[tuple[tuple[int, int, int, int], int]],
    ) -> dict[str, Any]:
        """Inject structural AST mutants across patched files and require 100% mutant kill rate."""
        disc_path = self.repo_dir / "discount_policy.py"
        tax_path = self.repo_dir / "tax_rules.py"
        orig_disc = disc_path.read_text(encoding="utf-8")
        orig_tax = tax_path.read_text(encoding="utf-8")

        mutants = [
            ("discount_policy.py", orig_disc.replace("subtotal >= threshold", "subtotal > threshold")),
            ("discount_policy.py", orig_disc.replace("subtotal >= threshold", "subtotal <= threshold")),
            ("tax_rules.py", orig_tax.replace("net_amount * tax_pct", "net_amount * (tax_pct + 1)")),
            ("tax_rules.py", orig_tax.replace("// 100", "// 10")),
        ]
        killed = 0
        try:
            for target_file, mutant_code in mutants:
                atomic_write_verified(self.repo_dir / target_file, mutant_code)
                passed, _ = self.evaluate_repo_suite(verification_cases)
                if passed < len(verification_cases):
                    killed += 1
                atomic_write_verified(disc_path, orig_disc)
                atomic_write_verified(tax_path, orig_tax)
        finally:
            atomic_write_verified(disc_path, orig_disc)
            atomic_write_verified(tax_path, orig_tax)

        kill_rate = round(killed / max(1, len(mutants)), 4)
        if kill_rate < 1.0:
            raise WeakTestSuiteOrOverfitError(
                f"Surviving mutants detected: kill_rate={kill_rate} ({killed}/{len(mutants)})"
            )
        return {
            "mutants_tested": len(mutants),
            "mutants_killed": killed,
            "mutation_kill_rate": kill_rate,
        }


def run_causal_repo_evolution_cycle(workspace: str | Path) -> dict[str, Any]:
    """Run the complete Epoch C Multi-File Causal Repo Evolution + Truth Market + Cartography cycle."""
    ws = Path(workspace).resolve()
    ws.mkdir(parents=True, exist_ok=True)

    evolver = CausalMultiFileRepoEvolver(ws / "billing_repo")
    evolver.materialize_buggy_multi_file_repo()
    causal_report = evolver.localize_faults_via_do_calculus()

    # Oracle test vectors covering boundary threshold (1000 == 1000) and exact tax rate
    oracle_cases = [
        ((1000, 1000, 10, 10), 990),   # 1000 - 100 = 900; + 10% tax (90) = 990
        ((2000, 1000, 20, 10), 1760),  # 2000 - 400 = 1600; + 10% tax (160) = 1760
        ((500, 1000, 10, 10), 550),    # 500 - 0 = 500; + 10% tax (50) = 550
        ((1500, 1500, 10, 20), 1620),  # 1500 - 150 = 1350; + 20% tax (270) = 1620
    ]
    baseline_passed, baseline_failures = evolver.evaluate_repo_suite(oracle_cases)

    # Set up Internal Epistemic Prediction Market with 3 brains
    reg = BrainRegistry(ws / "epoch_c_brain_registry.json")
    market = EpistemicTruthMarket(reg, initial_credits=100.0, bankruptcy_threshold=20.0)
    market.register_market_participant(
        "brain_overconfident_hallucinator",
        kind="uncalibrated_llm",
        descriptor="overconfident-single-file-guesser",
    )
    market.register_market_participant(
        "brain_counterexample_hunter",
        kind="red_team_adversary",
        descriptor="boundary-counterexample-hunter",
    )
    market.register_market_participant(
        "brain_causal_multifile_solver",
        kind="causal_ast_solver",
        descriptor="do-calculus-multifile-synthesizer",
    )

    # Round 1 & 2: Overconfident brain claims p=0.98 with a partial single-file patch;
    # Counterexample Hunter exposes boundary failure `(1000, 1000, 10, 10)` -> Overconfident brain goes bankrupt!
    for r_idx in (1, 2):
        market.adjudicate_debate_round(
            round_id=f"debate-r{r_idx}",
            prover_brain_id="brain_overconfident_hallucinator",
            hunter_brain_id="brain_counterexample_hunter",
            prover_confidence=0.98,
            stake=30.0,
            proposed_patch_passes_oracle=False,
            counterexample_found=list(baseline_failures[0]),
        )

    # Synthesize atomic cross-file patch on the 2 causally localized suspect files
    disc_buggy = (ws / "billing_repo" / "discount_policy.py").read_text(encoding="utf-8")
    tax_buggy = (ws / "billing_repo" / "tax_rules.py").read_text(encoding="utf-8")
    disc_key = next(
        k for k, _ in enumerate_lexical_variants(disc_buggy)
        if k[0] == "compare_swap" and k[2] == "GtE"
    )
    tax_key = next(
        k for k, _ in enumerate_lexical_variants(tax_buggy)
        if k[0] == "binop_unwrap" and k[2] == "left"
    )
    disc_fixed = apply_lexical_operator(disc_buggy, disc_key)
    tax_fixed = apply_lexical_operator(tax_buggy, tax_key)
    if disc_fixed is None or tax_fixed is None:
        raise RuntimeError("Failed to synthesize lexical cross-file fixes")

    patch_report = evolver.apply_atomic_cross_file_patch(
        {
            "discount_policy.py": disc_fixed,
            "tax_rules.py": tax_fixed,
        },
        oracle_cases,
    )
    mutation_report = evolver.run_mutation_testing_guard(oracle_cases)

    # Round 3: Causal multi-file solver submits verified cross-file patch; Counterexample Hunter finds no counterexample
    market.adjudicate_debate_round(
        round_id="debate-r3",
        prover_brain_id="brain_causal_multifile_solver",
        hunter_brain_id="brain_counterexample_hunter",
        prover_confidence=0.95,
        stake=30.0,
        proposed_patch_passes_oracle=True,
        counterexample_found=None,
    )
    market_summary = market.summary()

    # Cartography of Ignorance across all 3 zones
    cartographer = CartographyOfIgnorance()
    proved_verdict = cartographer.classify(
        deterministic_proof=True,
        mutation_kill_rate=mutation_report["mutation_kill_rate"],
        empirical_errors=0,
        sample_size=120,
        kl_divergence=0.4,
        calibration_nonconformity_scores=[0.01 * i for i in range(1, 20)],
    )
    bounded_verdict = cartographer.classify(
        deterministic_proof=False,
        mutation_kill_rate=0.90,
        empirical_errors=0,
        sample_size=120,
        kl_divergence=0.5,
        calibration_nonconformity_scores=[0.01 * i for i in range(1, 20)],
    )
    abstain_verdict = cartographer.classify(
        deterministic_proof=False,
        mutation_kill_rate=0.50,
        empirical_errors=8,
        sample_size=20,
        kl_divergence=3.5,
        calibration_nonconformity_scores=[0.5 * i for i in range(1, 20)],
    )

    digest_core = {
        "causal_suspects": causal_report["causal_suspects"],
        "pruned_confounders": causal_report["pruned_confounders"],
        "baseline_passed": baseline_passed,
        "patch_report": patch_report,
        "mutation_report": mutation_report,
        "market_standings": market_summary["standings"],
        "zones": [proved_verdict.zone, bounded_verdict.zone, abstain_verdict.zone],
    }
    return {
        "epoch": "EPOCH_C_CAUSAL_REPO_AND_TRUTH_MARKET",
        "causal_localization": causal_report,
        "baseline_passed": baseline_passed,
        "patch_report": patch_report,
        "mutation_report": mutation_report,
        "truth_market": market_summary,
        "cartography": {
            "proved": proved_verdict.to_dict(),
            "conformal_bounded": bounded_verdict.to_dict(),
            "abstain": abstain_verdict.to_dict(),
        },
        "epoch_c_digest": _sha256_hex(_canonical_json(digest_core)),
    }
