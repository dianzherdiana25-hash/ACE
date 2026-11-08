"""ACE Autonomous Source-Code Development Agent Package (V0.3)."""
from .codebase_reader import CodebaseReader
from .controller import AutonomousSoftwareResearcher
from .independent_evaluator import IndependentEvaluator
from .models import (
    AutonomousPRMetadata,
    CodePatch,
    ImprovementHypothesis,
    ResearchProblem,
    WorktreeExecutionResult,
)
from .patch_synthesizer import ModularPatchGenerator
from .pr_manager import AutonomousPRManager
from .problem_selector import ProblemSelector
from .worktree_harness import WorktreeHarness

__all__ = [
    "CodebaseReader",
    "ProblemSelector",
    "ModularPatchGenerator",
    "WorktreeHarness",
    "IndependentEvaluator",
    "AutonomousPRManager",
    "AutonomousSoftwareResearcher",
    "ResearchProblem",
    "ImprovementHypothesis",
    "CodePatch",
    "WorktreeExecutionResult",
    "AutonomousPRMetadata",
]
