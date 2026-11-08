"""ACE Uncheatable Sealed Evaluator module (W2)."""
from .task_families import TASK_FAMILIES, generate_family_instances
from .sealed_generator import get_evaluation_seed_and_status
from .cheat_detection import evaluate_candidate_integrity

__all__ = [
    "TASK_FAMILIES",
    "generate_family_instances",
    "get_evaluation_seed_and_status",
    "evaluate_candidate_integrity",
]
