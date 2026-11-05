"""R8 exposure/lineage checks for claims about generalization to unseen tasks.

Only evaluator-custodied digests are meaningful. Hash labels supplied by an
untrusted candidate do not establish semantic novelty or independent testing.
"""
from __future__ import annotations

from dataclasses import dataclass
from collections import defaultdict


@dataclass(frozen=True)
class Lineage:
    case_id: str
    split: str  # development, validation, evaluation
    semantic_sha256: str
    generator_sha256: str
    mechanism_sha256: str
    source_world_sha256: str  # origin of sibling/derived instances
    exposed_to_candidate: bool


def _sha(value: object) -> bool:
    return type(value) is str and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


def audit_lineage(records: list[Lineage], *, claim: str = 'public_diagnostic') -> dict:
    """No semantic-oracle guarantee: checks only evaluator-attested provenance.

    public_diagnostic: permits known exposed public evaluation, cannot confirm.
    generator_disjoint: eval generator & source-world disjoint from all fitting.
    mechanism_disjoint: additionally requires mechanism SHA disjoint.
    """
    if claim not in {'public_diagnostic', 'generator_disjoint', 'mechanism_disjoint'}:
        raise ValueError('unsupported claim scope')
    if type(records) is not list or not records:
        raise ValueError('empty or invalid lineage records')
    case_ids, instance_sha = set(), set()
    by_split = defaultdict(list)
    for r in records:
        if type(r) is not Lineage or type(r.case_id) is not str or not r.case_id:
            raise ValueError('malformed lineage row')
        if r.case_id in case_ids:
            raise ValueError('reused task identity')
        case_ids.add(r.case_id)
        if r.split not in {'development', 'validation', 'evaluation'}:
            raise ValueError('unsupported split')
        if type(r.exposed_to_candidate) is not bool:
            raise ValueError('invalid exposure flag')
        for field in ('semantic_sha256', 'generator_sha256', 'mechanism_sha256', 'source_world_sha256'):
            if not _sha(getattr(r, field)):
                raise ValueError('invalid evaluator digest: ' + field)
        if r.semantic_sha256 in instance_sha:
            raise ValueError('repeated semantic instance across splits or rows')
        instance_sha.add(r.semantic_sha256)
        by_split[r.split].append(r)
    if not by_split['development'] or not by_split['evaluation']:
        raise ValueError('development/evaluation required')
    fitting = by_split['development'] + by_split['validation']
    evaluation = by_split['evaluation']
    eval_world_count = len({r.source_world_sha256 for r in evaluation})
    known_generators = {r.generator_sha256 for r in fitting}
    known_mechanisms = {r.mechanism_sha256 for r in fitting}
    known_worlds = {r.source_world_sha256 for r in fitting}
    reused_generators = sorted({r.generator_sha256 for r in evaluation} & known_generators)
    reused_mechanisms = sorted({r.mechanism_sha256 for r in evaluation} & known_mechanisms)
    reused_worlds = sorted({r.source_world_sha256 for r in evaluation} & known_worlds)
    exposed = sorted(r.case_id for r in evaluation if r.exposed_to_candidate)
    signals = []
    if reused_generators:
        signals.append('GENERATOR_REUSED')
    if reused_mechanisms:
        signals.append('MECHANISM_REUSED')
    if reused_worlds:
        signals.append('SOURCE_WORLD_REUSED')
    if exposed:
        signals.append('EVALUATION_EXPOSED')
    if eval_world_count != len(evaluation):
        signals.append('EVALUATION_WORLD_CLUSTERING')
    distinct_eval_mechanisms = len({r.mechanism_sha256 for r in evaluation})
    if distinct_eval_mechanisms < 4:
        signals.append('LOW_MECHANISM_COVERAGE')
    if claim != 'public_diagnostic':
        if reused_generators or reused_worlds or exposed or eval_world_count != len(evaluation):
            raise ValueError('unseen-generator claim contradicted by exposure/lineage')
        if claim == 'mechanism_disjoint' and reused_mechanisms:
            raise ValueError('unseen-mechanism claim contradicted by exposure/lineage')
    return {
        'schema': 'ace.r8.lineage.v1',
        'claim_scope_requested': claim,
        'evaluation_instances': len(evaluation),
        'distinct_source_worlds': eval_world_count,
        'evaluation_mechanisms': distinct_eval_mechanisms,
        'signals': signals,
        'custody': 'NOT_AUTHENTICATED_BY_THIS_MODULE',
        'claim_gate': 'NOT_CONFIRMED',
        'limitations': ('SHA labels require independent evaluator custody. '
                        'Different digests do not prove semantic independence. '
                        'Counts and provenance checks are not a behavioral assessment.'),
    }
