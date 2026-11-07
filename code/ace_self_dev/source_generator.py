"""Source Generator: Generates typed, AST-validated candidate code from verified mechanisms."""
from __future__ import annotations

import difflib
import hashlib
import time
from typing import Any, Dict, Optional, Tuple

from ace_loop.source_evolution import (
    CompositeGene,
    DispatchGene,
    GatedGene,
    RelationalGene,
    RelationalGatedGene,
    SEED_GENE,
    TypedGene,
    compile_function,
    compute_sha,
    generate_source,
    gene_from_dict,
    mutate_composite_gene,
    mutate_dispatch_gene,
    mutate_gated_gene,
    mutate_gene,
    mutate_relational_gated_gene,
    mutate_relational_gene,
    validate_ast,
)
from .models import AuthorType, CodeCandidate, ResearchHypothesis
from .provenance_engine import ProvenanceEngine


class SourceGenerator:
    """Generates typed Python source candidates targeting specific hypotheses."""

    def __init__(self, provenance_engine: Optional[ProvenanceEngine] = None):
        self.provenance_engine = provenance_engine or ProvenanceEngine()

    def generate_candidate(
        self,
        hypothesis: ResearchHypothesis,
        parent_candidate: Optional[CodeCandidate] = None,
        parent_id: Optional[str] = None,
        ordinal: int = 1,
        author_type: AuthorType = AuthorType.ACE_AUTONOMOUS_V02,
    ) -> CodeCandidate:
        """Generate a strongly-typed, AST-validated candidate function and diff patch."""
        effective_parent_id = parent_id or (parent_candidate.candidate_id if parent_candidate else "G0_root_seed")
        parent_source = parent_candidate.source_code if parent_candidate else generate_source(SEED_GENE).decode("utf-8")

        # Determine mutation strategy (atomic vs composite vs gated vs relational vs dispatch)
        strat = getattr(hypothesis, "strategy", "")
        is_dispatch = (
            strat == "MULTI_TASK_DISPATCH"
            or "dispatch" in hypothesis.statement.lower()
        )
        is_relational_gated = (
            strat in ("SYNTHESIZE_RELATIONAL_MULTI_CLAUSE", "RELATIONAL_GATED", "RELATIONAL_MULTI_CLAUSE")
            or "relational gated" in hypothesis.statement.lower()
            or "relational" in hypothesis.statement.lower()
            or "multi-clause" in hypothesis.statement.lower()
            or "conjunction" in hypothesis.statement.lower()
            or "disjunction" in hypothesis.statement.lower()
        )
        is_gated = (
            strat == "SYNTHESIZE_GATED_EXPRESSION_TREE"
            or "gated" in hypothesis.statement.lower()
            or "expression tree" in hypothesis.statement.lower()
        ) and not is_relational_gated
        is_composite = (
            strat == "SYNTHESIZE_COMPOSITE_MECHANISM"
            or "composite" in hypothesis.statement.lower()
        ) and not is_relational_gated

        if is_dispatch:
            mutated_gene = mutate_dispatch_gene(ordinal=ordinal)
        elif is_relational_gated:
            mutated_gene = mutate_relational_gated_gene(ordinal=ordinal)
        elif is_gated:
            mutated_gene = mutate_gated_gene(ordinal=ordinal)
        elif is_composite:
            base_gene = gene_from_dict(parent_candidate.gene_dict) if parent_candidate else SEED_GENE
            if isinstance(base_gene, CompositeGene):
                gene_a = base_gene.gene_a
                gene_b = base_gene.gene_b
            elif isinstance(base_gene, (GatedGene, RelationalGene, RelationalGatedGene, DispatchGene)):
                gene_a = SEED_GENE
                gene_b = mutate_gene(SEED_GENE, ordinal + 2)
            else:
                gene_a = base_gene
                gene_b = mutate_gene(base_gene, ordinal + 2)
            mutated_gene = mutate_composite_gene(gene_a, gene_b, ordinal=ordinal)
        else:
            parent_gene = gene_from_dict(parent_candidate.gene_dict) if parent_candidate else SEED_GENE
            if isinstance(parent_gene, (CompositeGene, GatedGene, RelationalGene, RelationalGatedGene, DispatchGene)):
                parent_gene = SEED_GENE
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

        cand_id = f"CAND_{hypothesis.hypothesis_id}"

        # Generate verifiable cryptographic provenance proof
        proof = self.provenance_engine.create_provenance_proof(
            source_sha=source_sha,
            author_type=author_type,
        )

        return CodeCandidate(
            candidate_id=cand_id,
            parent_id=effective_parent_id,
            author_type=author_type,
            source_code=source_str,
            source_sha=source_sha,
            gene_dict=mutated_gene.to_dict(),
            diff_patch=diff_patch,
            creation_timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            provenance_proof=proof,
        )
