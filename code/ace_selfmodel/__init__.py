"""ACE Functional Self-Model & Metacognition package (Fase 4)."""
from .core import (
    CapabilityAwareness,
    FUNCTIONAL_SELF_MODEL_STATUS,
    METACOGNITIVE_AWARENESS_STATUS,
    PHENOMENAL_CONSCIOUSNESS_STATUS,
    SelfIdentity,
    SelfState,
    introspect_self_state,
)
from .memory import ExperienceMemory, MANDATORY_INVARIANTS
from .metacognition import (
    AttentionController,
    MetacognitiveEvaluator,
    MetacognitiveForecast,
    SelfReflection,
    compute_calibration_metrics,
)

__all__ = [
    "AttentionController",
    "CapabilityAwareness",
    "ExperienceMemory",
    "FUNCTIONAL_SELF_MODEL_STATUS",
    "MANDATORY_INVARIANTS",
    "METACOGNITIVE_AWARENESS_STATUS",
    "MetacognitiveEvaluator",
    "MetacognitiveForecast",
    "PHENOMENAL_CONSCIOUSNESS_STATUS",
    "SelfIdentity",
    "SelfReflection",
    "SelfState",
    "compute_calibration_metrics",
    "introspect_self_state",
]
