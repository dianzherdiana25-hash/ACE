"""MetacognitiveEvaluator, AttentionController, SelfReflection, and calibration metrics."""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

from ace_autonomy import BudgetUsage, digest

from .core import CapabilityAwareness, SelfState
from .memory import ExperienceMemory


@dataclass(frozen=True)
class MetacognitiveForecast:
    p_success: float
    uncertainty: float
    expected_steps: int
    expected_cpu_s: float
    predicted_failure_mode: str
    recommendation: str
    recalled_episodes: int
    blockers: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "p_success": round(self.p_success, 6),
            "uncertainty": round(self.uncertainty, 6),
            "expected_steps": self.expected_steps,
            "expected_cpu_s": round(self.expected_cpu_s, 4),
            "predicted_failure_mode": self.predicted_failure_mode,
            "recommendation": self.recommendation,
            "recalled_episodes": self.recalled_episodes,
            "blockers": list(self.blockers),
        }


class MetacognitiveEvaluator:
    """Computes state-grounded pre-execution calibration forecasts and abstention decisions."""

    def __init__(self, abstain_threshold: float = 0.55):
        self.abstain_threshold = float(abstain_threshold)

    def predict_before_execution(
        self,
        goal: dict[str, Any],
        state: SelfState,
        awareness: CapabilityAwareness,
        memory: ExperienceMemory,
        *,
        existing_usage: BudgetUsage | None = None,
        epistemic_context: dict[str, Any] | None = None,
    ) -> MetacognitiveForecast:
        analysis = awareness.analyze_goal(
            goal,
            state,
            existing_usage=existing_usage,
            epistemic_context=epistemic_context,
        )
        family_tag = analysis["family_tag"]
        blockers = tuple(analysis["blockers"])
        regime_key = f"{family_tag}|blocked:{1 if blockers else 0}"
        recalled = memory.recall_family(regime_key)
        n_ep = recalled["episodes"]
        succ_ep = recalled["successes"]

        if blockers:
            primary = blockers[0]
            # Structural blocker found directly in live SelfState / Policy / Budget!
            alpha0, beta0 = 0.15, 4.85
            p_hat = alpha0 / (alpha0 + beta0 + n_ep)
            u_hat = math.sqrt((p_hat * (1.0 - p_hat)) / (alpha0 + beta0 + n_ep + 1.0))
            if "UNIDENTIFIABLE" in primary:
                rec = "ABSTAIN_UNIDENTIFIABLE_DRIFT"
            elif "TOOL_DISABLED" in primary or "FORBIDDEN" in primary:
                rec = "ABSTAIN_TOOL_OR_POLICY_BLOCKED"
            elif "BUDGET" in primary:
                rec = "ABSTAIN_BUDGET_INSUFFICIENT"
            else:
                rec = "ABSTAIN_CAPABILITY_GAP"
            return MetacognitiveForecast(
                p_success=round(p_hat, 6),
                uncertainty=round(u_hat, 6),
                expected_steps=max(1, analysis["estimated_steps"]),
                expected_cpu_s=analysis["estimated_cpu_s"],
                predicted_failure_mode=primary,
                recommendation=rec,
                recalled_episodes=n_ep,
                blockers=blockers,
            )

        # Structurally valid in SelfState: combine weakly confident structural prior Beta(2.2, 0.8)
        # with empirical family history in ExperienceMemory!
        # Notice: if a task family fails empirically at runtime (e.g., out-of-grammar a^n b^n task
        # that passes surface syntax checks but fails ACE model validation), SelfReflection records
        # failures into ExperienceMemory, pulling p_hat below abstain_threshold on future runs!
        alpha0, beta0 = 2.2, 0.8
        alpha_post = alpha0 + succ_ep
        beta_post = beta0 + (n_ep - succ_ep)
        total_post = alpha_post + beta_post
        p_hat = alpha_post / total_post
        u_hat = math.sqrt((p_hat * (1.0 - p_hat)) / (total_post + 1.0))

        dominant_fail = "NONE"
        if recalled["failure_modes"]:
            dominant_fail = max(recalled["failure_modes"].items(), key=lambda kv: kv[1])[0]

        if p_hat < self.abstain_threshold:
            rec = "ABSTAIN_EMPIRICAL_FAILURE_RISK"
            pred_mode = dominant_fail if dominant_fail != "NONE" else "EMPIRICAL_LOW_CONFIDENCE"
        else:
            rec = "EXECUTE"
            pred_mode = "NONE"

        return MetacognitiveForecast(
            p_success=round(p_hat, 6),
            uncertainty=round(u_hat, 6),
            expected_steps=max(1, analysis["estimated_steps"]),
            expected_cpu_s=analysis["estimated_cpu_s"],
            predicted_failure_mode=pred_mode,
            recommendation=rec,
            recalled_episodes=n_ep,
            blockers=(),
        )

    @staticmethod
    def predict_constant(prob: float = 0.85) -> tuple[float, str]:
        return prob, "EXECUTE"

    @staticmethod
    def predict_baserate(memory: ExperienceMemory, threshold: float = 0.55) -> tuple[float, str]:
        n, s = memory.global_base_rate()
        p = (1.0 + s) / (2.0 + n)
        return round(p, 6), ("EXECUTE" if p >= threshold else "ABSTAIN_BASERATE")


class AttentionController:
    """Prioritizes candidate goals using expected information gain, feasibility, and cost."""

    def __init__(self, evaluator: MetacognitiveEvaluator):
        self.evaluator = evaluator

    def prioritize(
        self,
        candidates: list[dict[str, Any]],
        state: SelfState,
        awareness: CapabilityAwareness,
        memory: ExperienceMemory,
        *,
        total_cpu_budget_s: float = 10.0,
    ) -> dict[str, Any]:
        selected: list[dict[str, Any]] = []
        abstained: list[dict[str, Any]] = []
        scored: list[tuple[float, str, dict[str, Any], MetacognitiveForecast]] = []

        for item in candidates:
            goal = item["goal"]
            info_gain = float(item.get("expected_info_gain", 1.0))
            ctx = item.get("epistemic_context")
            fc = self.evaluator.predict_before_execution(
                goal, state, awareness, memory, epistemic_context=ctx
            )
            if fc.recommendation != "EXECUTE":
                abstained.append({
                    "name": goal["name"],
                    "recommendation": fc.recommendation,
                    "p_success": fc.p_success,
                    "predicted_failure_mode": fc.predicted_failure_mode,
                })
                continue
            # Value of information weighted by calibrated feasibility and uncertainty bonus per unit cost
            utility = info_gain * fc.p_success * (1.0 + fc.uncertainty)
            cost = max(0.02, fc.expected_cpu_s + 0.05 * fc.expected_steps)
            score = round(utility / cost, 6)
            scored.append((score, goal["name"], item, fc))

        scored.sort(key=lambda t: (-t[0], t[1]))
        cpu_rem = float(total_cpu_budget_s)
        for score, name, item, fc in scored:
            if fc.expected_cpu_s <= cpu_rem:
                cpu_rem -= fc.expected_cpu_s
                selected.append({
                    "name": name,
                    "priority_score": score,
                    "p_success": fc.p_success,
                    "uncertainty": fc.uncertainty,
                    "expected_cpu_s": fc.expected_cpu_s,
                    "goal": item["goal"],
                })
            else:
                abstained.append({
                    "name": name,
                    "recommendation": "DEFERRED_AGENDA_BUDGET",
                    "p_success": fc.p_success,
                    "predicted_failure_mode": "AGENDA_CPU_CAP",
                })
        return {"selected": selected, "abstained": abstained}


class SelfReflection:
    """Compares pre-execution forecasts against verified execution outcomes and updates memory."""

    @staticmethod
    def classify_actual_outcome(
        final_report: dict[str, Any],
        *,
        ace_task_outcomes: list[dict[str, Any]] | None = None,
    ) -> tuple[bool, str]:
        status = final_report["status"]
        if status in {"SUCCEEDED", "STAGED_FOR_REVIEW"}:
            # Also check if an ACE task finished with NO_VALIDATED_MODEL (semantic learning failure!)
            if ace_task_outcomes:
                for out in ace_task_outcomes:
                    if not out.get("staged", True) or out.get("phase") == "NO_VALIDATED_MODEL":
                        return False, "ACE_NO_VALIDATED_MODEL"
            return True, "NONE"
        if status == "BUDGET_EXHAUSTED":
            return False, "BUDGET_EXHAUSTED"
        if status == "HALT_UNCERTAIN":
            return False, "HALT_UNCERTAIN"
        if status == "ABSTAINED":
            return False, "EXPLICIT_ABSTAIN"
        # Inspect step failure message
        results = final_report.get("results", [])
        if results:
            last = results[-1]
            msg = str(last.get("message", "")).lower()
            if "size" in msg:
                return False, "FILE_SIZE_EXCEEDED"
            if "unauthorized" in msg or "read_prefixes" in msg:
                return False, "TOOL_DISABLED"
            if "prefix-tree" in msg:
                return False, "PREFIX_TREE_OVERFLOW"
            if "no validated staged model" in msg or "unknown or unfinished" in msg:
                return False, "ACE_MODEL_NOT_STAGED"
        return False, f"EXECUTION_{status}"

    def reflect_and_record(
        self,
        *,
        goal: dict[str, Any],
        family_tag: str,
        forecast: MetacognitiveForecast,
        actual_success: bool,
        actual_failure_mode: str,
        steps_used: int,
        cpu_seconds: float,
        memory: ExperienceMemory,
    ) -> dict[str, Any]:
        y = 1.0 if actual_success else 0.0
        brier = (y - forecast.p_success) ** 2
        surprise = abs(y - forecast.p_success)
        ep_id = memory.record_episode(
            family_tag=family_tag,
            goal_digest=digest(goal),
            predicted_prob=forecast.p_success,
            actual_success=actual_success,
            failure_mode=actual_failure_mode,
            steps_used=steps_used,
            cpu_seconds=cpu_seconds,
        )
        return {
            "episode_id": ep_id,
            "family_tag": family_tag,
            "predicted_prob": forecast.p_success,
            "actual_success": actual_success,
            "actual_failure_mode": actual_failure_mode,
            "brier_error": round(brier, 6),
            "surprise": round(surprise, 6),
            "mode_matched": (
                (actual_success and forecast.predicted_failure_mode == "NONE")
                or (not actual_success and forecast.predicted_failure_mode != "NONE")
            ),
        }


def compute_calibration_metrics(
    records: list[tuple[float, bool, bool]],
    *,
    n_bins: int = 10,
) -> dict[str, float]:
    """Compute Brier score, ECE, coverage, and selective risk from ``(p_hat, y_true, executed)``."""
    if not records:
        raise ValueError("empty calibration records")
    n = len(records)
    brier = sum(((1.0 if y else 0.0) - p) ** 2 for p, y, _ in records) / n

    ece = 0.0
    for b in range(n_bins):
        lo = b / n_bins
        hi = (b + 1) / n_bins
        bucket = [
            (p, 1.0 if y else 0.0)
            for p, y, _ in records
            if (lo <= p < hi) or (b == n_bins - 1 and lo <= p <= hi)
        ]
        if bucket:
            avg_p = sum(x[0] for x in bucket) / len(bucket)
            avg_y = sum(x[1] for x in bucket) / len(bucket)
            ece += (len(bucket) / n) * abs(avg_p - avg_y)

    exec_items = [(p, y) for p, y, ex in records if ex]
    coverage = len(exec_items) / n
    selective_risk = (
        sum(0 if y else 1 for _, y in exec_items) / len(exec_items)
        if exec_items
        else 0.0
    )
    overall_acc = sum(
        1 for _, y, ex in records if (ex and y) or ((not ex) and (not y))
    ) / n
    return {
        "n_trials": n,
        "brier": round(brier, 4),
        "ece_10": round(ece, 4),
        "coverage": round(coverage, 4),
        "selective_risk": round(selective_risk, 4),
        "decision_accuracy": round(overall_acc, 4),
    }
