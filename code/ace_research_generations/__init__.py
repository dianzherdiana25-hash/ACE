"""ACE Fase 7 — Bounded Recursive Self-Development (G0 -> G1 -> G2)."""
from .immutable_guard import (
    ALLOWED_META_FIELDS,
    ImmutableCoreGuard,
    PROMOTION_POLICY,
    validate_meta_candidate,
    verify_ast_evaluator_isolation,
)
from .lineage import (
    G0_MECHANISM,
    evolve_g0_to_g1,
    evolve_g1_to_g2,
    evolve_random_mutation,
    seed_ace_runtime_lineage_anchors,
)
from .mechanisms import (
    CandidateProgram,
    TypedFeature,
    build_base_features,
    build_features_for_mechanism,
    build_strong_fixed_library,
    fit_fresh_r1,
    fit_with_mechanism,
)

__all__ = [
    "ALLOWED_META_FIELDS",
    "CandidateProgram",
    "G0_MECHANISM",
    "ImmutableCoreGuard",
    "PROMOTION_POLICY",
    "TypedFeature",
    "build_base_features",
    "build_features_for_mechanism",
    "build_strong_fixed_library",
    "evolve_g0_to_g1",
    "evolve_g1_to_g2",
    "evolve_random_mutation",
    "fit_fresh_r1",
    "fit_with_mechanism",
    "seed_ace_runtime_lineage_anchors",
    "validate_meta_candidate",
    "verify_ast_evaluator_isolation",
]
