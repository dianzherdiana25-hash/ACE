"""R8: predeclared, family-cluster diagnostic gate for *claimed* capability growth.

Designed to try to falsify a positive claim. It can return a diagnostic success,
NEVER confirm intelligence, learning, or OAIE; that requires independently
custodied sealed evaluation and pre-registered statistical analysis.

No external network, model code execution, nor arbitrary supplied plugins.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from collections import defaultdict
import hashlib
import json

from .measurement import Record, validate
from .lineage import Lineage, audit_lineage


@dataclass(frozen=True)
class GrowthPlan:
    """Developer-visible synthetic screening thresholds (NOT a preregistration)."""
    min_families: int = 8
    min_novel_families: int = 6
    min_compositional_families: int = 6
    min_per_family: int = 8
    min_novel_macro_delta: float = 0.10
    max_family_regression: float = 0.10
    alpha: float = 0.05

    def __post_init__(self):
        for name in ('min_families', 'min_novel_families', 'min_compositional_families', 'min_per_family'):
            v = getattr(self, name)
            if type(v) is not int or not 1 <= v <= 16:
                raise ValueError('invalid bounded plan count: ' + name)
        for name in ('min_novel_macro_delta', 'max_family_regression', 'alpha'):
            v = getattr(self, name)
            if type(v) not in (float, int) or not (0 < v < 1):
                raise ValueError('invalid bounded plan probability: ' + name)
        if self.min_novel_families > self.min_families:
            raise ValueError('novel family minimum exceeds total family minimum')
        if self.min_compositional_families > self.min_families:
            raise ValueError('compositional family minimum exceeds total family minimum')


def _cluster_signflip_p(deltas: list[float]) -> float | None:
    """Exact, one-sided family sign flip. Assumes exchangeable *independent* clusters.

    This test DOES NOT adjust for repeated/selected analyses or verify that
    distributions are sign-symmetric. It is a diagnostic only.
    """
    if not 2 <= len(deltas) <= 16:
        return None
    observed = sum(deltas)
    extreme = 0
    for signs in product((-1, 1), repeat=len(deltas)):
        if sum(sign * x for sign, x in zip(signs, deltas)) >= observed - 1e-12:
            extreme += 1
    return extreme / (1 << len(deltas))


def screen_growth(records: list[Record], lineage: list[Lineage], plan: GrowthPlan | None = None) -> dict:
    """Fail closed on provenance inconsistencies. Never call it confirmation."""
    if type(records) is not list or type(lineage) is not list:
        raise ValueError('expected explicit evaluator list records')
    plan = plan if plan is not None else GrowthPlan()
    if type(plan) is not GrowthPlan:
        raise ValueError('invalid plan')
    rows = validate(records)
    provenance = audit_lineage(lineage, claim='mechanism_disjoint')
    linked = {r.case_id: r for r in lineage}
    if set(linked) != {r.case_id for r in rows}:
        raise ValueError('lineage/measurement case set mismatch')
    for row in rows:
        l = linked[row.case_id]
        if (row.split != l.split or row.fingerprint != l.semantic_sha256):
            raise ValueError('lineage/measurement split or semantic mismatch')

    evaluation = [r for r in rows if r.split == 'evaluation']
    grouped = defaultdict(list)
    for r in evaluation:
        grouped[r.family].append(r)

    family_mechanisms = {}
    for family, members in grouped.items():
        mechanisms = {linked[x.case_id].mechanism_sha256 for x in members}
        if len(mechanisms) != 1:
            raise ValueError('family spans multiple claimed mechanisms')
        family_mechanisms[family] = next(iter(mechanisms))
    if len(set(family_mechanisms.values())) != len(family_mechanisms):
        raise ValueError('two families share an underlying mechanism')

    family_deltas = {
        family: sum(int(x.candidate_correct) - int(x.baseline_correct) for x in members) / len(members)
        for family, members in sorted(grouped.items())
    }
    novel = {family for family, members in grouped.items() if all(x.novel for x in members)}
    partial_novel = {family for family, members in grouped.items() if any(x.novel for x in members) and family not in novel}
    compositional = {family for family, members in grouped.items() if all(x.compositional for x in members)}
    partial_compositional = {family for family, members in grouped.items()
                             if any(x.compositional for x in members) and family not in compositional}

    reasons = []
    if len(grouped) < plan.min_families:
        reasons.append('INSUFFICIENT_FAMILY_COVERAGE')
    if len(novel) < plan.min_novel_families:
        reasons.append('INSUFFICIENT_NOVEL_FAMILIES')
    if len(compositional) < plan.min_compositional_families:
        reasons.append('INSUFFICIENT_COMPOSITIONAL_FAMILIES')
    if any(len(members) < plan.min_per_family for members in grouped.values()):
        reasons.append('INSUFFICIENT_PER_FAMILY_INSTANCES')
    if partial_novel or partial_compositional:
        reasons.append('MIXED_FAMILY_NOVELTY_OR_COMPOSITIONALITY')
    if any(x.candidate_ops > x.baseline_ops or x.candidate_labels > x.baseline_labels for x in evaluation):
        reasons.append('CANDIDATE_USES_MORE_RESOURCES')
    if any(delta < -plan.max_family_regression for delta in family_deltas.values()):
        reasons.append('MATERIAL_FAMILY_REGRESSION')
    if len(grouped) > 16:
        reasons.append('TOO_MANY_CLUSTERS_FOR_EXACT_TEST')

    novel_deltas = [family_deltas[family] for family in sorted(novel)]
    novelty_effect = sum(novel_deltas) / len(novel_deltas) if novel_deltas else None
    p_value = _cluster_signflip_p(novel_deltas)
    if novelty_effect is None or novelty_effect < plan.min_novel_macro_delta:
        reasons.append('INSUFFICIENT_NOVEL_TRANSFER_EFFECT')
    if p_value is None or p_value > plan.alpha:
        reasons.append('NO_NOMINAL_NOVEL_FAMILY_SIGNFLIP_SUPPORT')

    descriptor = json.dumps(plan.__dict__, sort_keys=True, separators=(',', ':'))
    return {
        'schema': 'ace.r8.growth-screen.v1',
        'public_plan_sha256': hashlib.sha256(descriptor.encode()).hexdigest(),
        'plan_is_registered': False,
        'evaluation_instances': len(evaluation),
        'evaluation_families': len(grouped),
        'novel_families': len(novel),
        'compositional_families': len(compositional),
        'family_deltas': family_deltas,
        'novel_family_macro_delta': novelty_effect,
        'novel_family_signflip_one_sided_nominal_p': p_value,
        'resource_costs': {
            'baseline_ops': sum(x.baseline_ops for x in evaluation),
            'candidate_ops': sum(x.candidate_ops for x in evaluation),
            'baseline_labels': sum(x.baseline_labels for x in evaluation),
            'candidate_labels': sum(x.candidate_labels for x in evaluation),
        },
        'lineage_custody': provenance['custody'],
        'diagnostic_status': 'PASS_PUBLIC_SCREEN_ONLY' if not reasons else 'HOLD_PUBLIC_SCREEN',
        'reasons': reasons,
        'scientific_claim': 'NOT_CONFIRMED',
        'warning': ('Nominal sign-flip p assumes independent symmetric family effects, '
                    'is not multiple-selection adjusted, and uses public self-supplied digests. '
                    'A matching lineage record is not proof of independent provenance.'),
    }
