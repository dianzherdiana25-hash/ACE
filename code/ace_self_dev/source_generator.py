"""Source Generator: Generates typed, AST-validated candidate code from verified mechanisms."""
from __future__ import annotations

import difflib
import hashlib
import time
from typing import Any, Dict, Optional, Tuple

from ace_loop.source_evolution import (
    SEED_GENE,
    TypedGene,
    compile_function,
    compute_sha,
    generate_source,
    mutate_gene,
    validate_ast,
)
from .models import AuthorType, CodeCandidate, ResearchHypothesis


class SourceGenerator:
    """Generates typed Python source candidates targeting specific hypotheses."""

    def generate_candidate(
        self,
        hypothesis: ResearchHypothesis,
        parent_candidate: Optional[CodeCandidate] = None,
        parent_id: Optional[str] = None,
        ordinal: int = 1,
        author_type: AuthorType = AuthorType.ACE_AUTONOMOUS_V01,
    ) -> CodeCandidate:
        """Generate a strongly-typed, AST-validated candidate function and diff patch."""
        parent_gene = TypedGene(**parent_candidate.gene_dict) if parent_candidate else SEED_GENE
        parent_source = parent_candidate.source_code if parent_candidate else generate_source(parent_gene).decode("utf-8")
        effective_parent_id = parent_id or (parent_candidate.candidate_id if parent_candidate else "G0_root_seed")

        # Apply deterministic mutation
        mutated_gene = mutate_gene(parent_gene, ordinal=ordinal)
        source_bytes = generate_source(mutated_gene)

        # Validate AST strictly against security boundaries
        validate_ast(source_bytes, expected_name="evaluate_mechanism")

        source_str = source_bytes.decode("utf-8")
        source_sha = compute_sha(source_bytes)

        # Compute unified diff patch
        diff_lines = list(
            difflib.unified_diff(
                parent_source.splitlines(keepends=True),
                source_str.splitlines(keepends=True),
                fromfile=f"a/{effective_parent_id}.py",
                tofile=f"b/{hypothesis.hypothesis_id}_ord{ordinal}.py",
            )
        )
        diff_patch = "".join(diff_lines)

        cand_id = f"CAND_{hypothesis.hypothesis_id}_ord{ordinal}"

        return CodeCandidate(
            candidate_id=cand_id,
            parent_id=effective_parent_id,
            author_type=author_type,
            source_code=source_str,
            source_sha=source_sha,
            gene_dict=mutated_gene.to_dict(),
            diff_patch=diff_patch,
            creation_timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        )
