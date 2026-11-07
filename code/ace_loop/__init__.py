"""ACE Loop Module: Source evolution and bounded mutation primitives."""
from .source_evolution import (
    SourceEvolutionError,
    TypedGene,
    SEED_GENE,
    MUTATION_RULES,
    mutate_gene,
    generate_source,
    validate_ast,
    compile_function,
    compute_sha,
)

__all__ = [
    "SourceEvolutionError",
    "TypedGene",
    "SEED_GENE",
    "MUTATION_RULES",
    "mutate_gene",
    "generate_source",
    "validate_ast",
    "compile_function",
    "compute_sha",
]
