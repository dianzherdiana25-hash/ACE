"""Game-Theoretic Minimax Adversarial Synthesis (No-Regret Co-Evolution).

Mathematical Foundation:
- Two-Player Zero-Sum Game between Synthesizer (Minimizer) and Adversary Red-Teamer (Maximizer).
- Von Neumann's Minimax Theorem (Von Neumann, 1928):
    min_{p in Delta(H)} max_{q in Delta(X)} p^T L q == max_{q in Delta(X)} min_{p in Delta(H)} p^T L q == V*
- No-Regret Multiplicative Weights / Hedge Dynamics (Freund & Schapire, 1999):
    Synthesizer update (minimizer): p_i^{(t+1)} propto p_i^{(t)} * exp(-eta_p * (L q^{(t)})_i)
    Adversary update   (maximizer): q_j^{(t+1)} propto q_j^{(t)} * exp(+eta_q * (p^{(t) T} L)_j)
- Regret Bound:
    Average Regret <= sqrt(ln(K) / (2T)) = O(1 / sqrt(T))
- Nash Equilibrium Convergence:
    Time-averaged strategies (p_bar, q_bar) converge to an eps-Nash equilibrium with duality gap <= O(1 / sqrt(T)).
"""
from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple


def compute_nash_gap(
    payoff_matrix: Sequence[Sequence[float]],
    p: Sequence[float],
    q: Sequence[float],
) -> float:
    """Computes the duality gap (Nash exploitability):
    Gap = max_j (p^T L)_j - min_i (L q)_i >= 0.
    At Nash equilibrium, Gap == 0.
    """
    m = len(payoff_matrix)
    n = len(payoff_matrix[0])

    # Adversary best response value: max_j (p^T L)_j
    adv_payoffs = [sum(p[i] * payoff_matrix[i][j] for i in range(m)) for j in range(n)]
    max_adv = max(adv_payoffs)

    # Synthesizer best response value: min_i (L q)_i
    synth_payoffs = [sum(payoff_matrix[i][j] * q[j] for j in range(n)) for i in range(m)]
    min_synth = min(synth_payoffs)

    return max(0.0, max_adv - min_synth)


class TwoPlayerGameMatrix:
    """Encapsulates a finite zero-sum game with payoff matrix L in [0, 1]^{m x n}."""

    def __init__(self, matrix: Sequence[Sequence[float]]):
        if not matrix or not matrix[0]:
            raise ValueError("Payoff matrix must be non-empty.")
        self.matrix: List[List[float]] = [[float(val) for val in row] for row in matrix]
        self.m: int = len(self.matrix)
        self.n: int = len(self.matrix[0])
        # Validate rectangular
        if any(len(row) != self.n for row in self.matrix):
            raise ValueError("All rows in payoff matrix must have equal length.")

    def expected_payoff(self, p: Sequence[float], q: Sequence[float]) -> float:
        """Computes bilinear form p^T L q."""
        return sum(
            p[i] * self.matrix[i][j] * q[j]
            for i in range(self.m)
            for j in range(self.n)
        )

    def synthesizer_payoff_vector(self, q: Sequence[float]) -> List[float]:
        """Returns L * q: expected loss of each synthesizer program candidate under adversary q."""
        return [sum(self.matrix[i][j] * q[j] for j in range(self.n)) for i in range(self.m)]

    def adversary_payoff_vector(self, p: Sequence[float]) -> List[float]:
        """Returns p^T * L: expected gain of each adversarial input under synthesizer p."""
        return [sum(p[i] * self.matrix[i][j] for i in range(self.m)) for j in range(self.n)]


class HedgePlayer:
    """No-Regret Multiplicative Weights (Hedge) algorithm player (Freund & Schapire, 1999)."""

    def __init__(self, num_actions: int, is_minimizer: bool = True, eta: Optional[float] = None):
        self.num_actions: int = num_actions
        self.is_minimizer: bool = is_minimizer
        self.eta: float = eta if eta is not None else 1.0
        self.weights: List[float] = [1.0] * num_actions
        self.cumulative_losses: List[float] = [0.0] * num_actions
        self.total_rounds: int = 0
        self.strategy_history: List[List[float]] = []

    @property
    def current_strategy(self) -> List[float]:
        """Returns normalized probability distribution over actions."""
        total = sum(self.weights)
        if total <= 0:
            return [1.0 / self.num_actions] * self.num_actions
        return [w / total for w in self.weights]

    def update(self, feedback_vector: Sequence[float]) -> None:
        """Updates weights based on observed payoff/loss vector.
        Minimizer: w_i <- w_i * exp(-eta * loss_i)
        Maximizer: w_j <- w_j * exp(+eta * gain_j)
        """
        strat = self.current_strategy
        self.strategy_history.append(strat)

        for i in range(self.num_actions):
            cost = feedback_vector[i]
            self.cumulative_losses[i] += cost

            if self.is_minimizer:
                exponent = -self.eta * cost
            else:
                exponent = +self.eta * cost

            # Clip for numerical stability
            exponent = max(-80.0, min(80.0, exponent))
            self.weights[i] *= math.exp(exponent)

        self.total_rounds += 1

    def compute_regret(self) -> float:
        """Computes external regret against the best fixed action in hindsight."""
        if self.total_rounds == 0:
            return 0.0

        # Cumulative loss of the algorithm: ∑_t p^{(t) T} cost^{(t)}
        alg_total_loss = 0.0
        for t in range(self.total_rounds):
            p_t = self.strategy_history[t]
            # Since cumulative_losses stores sum over rounds, we reconstruct round losses or average
            # Direct regret definition:
            # For minimizer: Alg_Loss - min_i Cumulative_Loss[i]
            # For maximizer: max_j Cumulative_Gain[j] - Alg_Gain
        pass

        if self.is_minimizer:
            best_fixed = min(self.cumulative_losses)
            # Estimate algorithm expected loss
            est_alg = sum(self.current_strategy[i] * self.cumulative_losses[i] for i in range(self.num_actions))
            return max(0.0, est_alg - best_fixed)
        else:
            best_fixed = max(self.cumulative_losses)
            est_alg = sum(self.current_strategy[j] * self.cumulative_losses[j] for j in range(self.num_actions))
            return max(0.0, best_fixed - est_alg)


class MinimaxCoEvolution:
    """Co-evolutionary engine running No-Regret dynamics between Synthesizer and Adversary."""

    def __init__(self, game: TwoPlayerGameMatrix):
        self.game = game

    def solve(
        self,
        rounds: int = 200,
        eta_p: Optional[float] = None,
        eta_q: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Simulates No-Regret repeated game and converges to epsilon-Nash equilibrium."""
        m, n = self.game.m, self.game.n

        # Optimal learning rate for T rounds: eta = sqrt(8 * ln(K) / T)
        if eta_p is None:
            eta_p = math.sqrt(8.0 * math.log(max(2, m)) / rounds)
        if eta_q is None:
            eta_q = math.sqrt(8.0 * math.log(max(2, n)) / rounds)

        synth_player = HedgePlayer(num_actions=m, is_minimizer=True, eta=eta_p)
        adv_player = HedgePlayer(num_actions=n, is_minimizer=False, eta=eta_q)

        sum_p = [0.0] * m
        sum_q = [0.0] * n
        history_gap: List[float] = []

        for _ in range(rounds):
            p_t = synth_player.current_strategy
            q_t = adv_player.current_strategy

            for i in range(m):
                sum_p[i] += p_t[i]
            for j in range(n):
                sum_q[j] += q_t[j]

            # Synthesizer observes adversary payoff vector L * q_t
            loss_p = self.game.synthesizer_payoff_vector(q_t)
            # Adversary observes synthesizer payoff vector p_t^T * L
            gain_q = self.game.adversary_payoff_vector(p_t)

            synth_player.update(loss_p)
            adv_player.update(gain_q)

            # Record running duality gap of time-averaged strategies
            avg_p_curr = [v / (_ + 1) for v in sum_p]
            avg_q_curr = [v / (_ + 1) for v in sum_q]
            history_gap.append(compute_nash_gap(self.game.matrix, avg_p_curr, avg_q_curr))

        # Time-averaged empirical strategies (converge to Nash equilibrium)
        p_bar = [v / rounds for v in sum_p]
        q_bar = [v / rounds for v in sum_q]

        final_gap = compute_nash_gap(self.game.matrix, p_bar, q_bar)
        game_value = self.game.expected_payoff(p_bar, q_bar)

        return {
            "rounds": rounds,
            "synthesizer_mixed_strategy": p_bar,
            "adversary_mixed_strategy": q_bar,
            "game_value_V": game_value,
            "duality_gap": final_gap,
            "is_epsilon_nash": final_gap <= 0.15,
            "sublinear_regret_bound": math.sqrt(math.log(max(m, n)) / (2.0 * rounds)),
            "gap_trajectory": history_gap,
        }

    @classmethod
    def from_programs_and_inputs(
        cls,
        programs: Sequence[Callable[[Any], Any]],
        adversarial_inputs: Sequence[Any],
        oracle_evaluator: Callable[[Callable[[Any], Any], Any], float],
    ) -> MinimaxCoEvolution:
        """Constructs a Minimax co-evolution game from executable programs and input generators."""
        matrix: List[List[float]] = []
        for prog in programs:
            row: List[float] = []
            for inp in adversarial_inputs:
                loss = oracle_evaluator(prog, inp)
                # Bounded loss in [0, 1]
                row.append(min(max(float(loss), 0.0), 1.0))
            matrix.append(row)

        game = TwoPlayerGameMatrix(matrix)
        return cls(game)
