"""Read-only provenance-bound audit of ACE E1.5 public-development aggregates.

No per-instance records, transfer results, or independent holdout are inferred.
Full-repository checkout is needed for default CLI; unit tests use fixtures.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

SOURCE_REPO = 'dianzherdiana25-hash/ACE'
SOURCE_REF = '965640786cbf2f8adcd89eb1d980945f78c2da77'
SOURCE_PATH = 'evidence/e15/E15_DEVELOPMENT_SUMMARY_v0.json'
SOURCE_GIT_BLOB_SHA1 = '2561d8ee47f84a85388cbd4c7de7737f1266342b'
TRACKS = {
    'in_family': 'WORK/e15_demo/final-infamily-v2.json',
    'mixed_grammar': 'WORK/e15_demo/final-mixed-v2.json',
}


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON key: ' + key)
        result[key] = value
    return result


def _constant(value):
    raise ValueError('non-finite JSON constant: ' + value)


def load_pinned_source(path: Path) -> dict:
    """Verify Git raw blob byte identity before parsing untrusted evidence."""
    if path.is_symlink() or not path.is_file():
        raise ValueError('source missing or symlink')
    raw = path.read_bytes()
    if len(raw) > 2_000_000:
        raise ValueError('source too large')
    prefix = b'blob ' + str(len(raw)).encode('ascii') + b'\0'
    sha = hashlib.sha1(prefix + raw).hexdigest()
    if sha != SOURCE_GIT_BLOB_SHA1:
        raise ValueError('source Git blob mismatch')
    return json.loads(raw.decode('utf-8'), object_pairs_hook=_unique_pairs, parse_constant=_constant)


def _metric(obj: dict) -> dict:
    if type(obj) is not dict:
        raise ValueError('metric object expected')
    required = ('worlds', 'accepted_correct', 'accepted_wrong', 'abstained',
                'logical_labels', 'probe_errors', 'utility_units')
    if not all(k in obj and type(obj[k]) is int for k in required):
        raise ValueError('missing/non-integer metric')
    w, ok, wrong, abstain, labels, errors, utility = (obj[k] for k in required)
    if w < 1 or min(ok, wrong, abstain, labels, errors) < 0:
        raise ValueError('invalid negative metric')
    if ok + wrong + abstain != w:
        raise ValueError('outcome totals do not partition worlds')
    if utility != 20 * ok - 40 * wrong - 2 * abstain - labels:
        raise ValueError('E1.5 reported utility inconsistent with scoring rule')
    return {k: obj[k] for k in required}


def audit(summary: dict) -> dict:
    """Paired totals only. Never invent family-cluster or per-instance scores."""
    if type(summary) is not dict or summary.get('project') != 'ACE E1.5':
        raise ValueError('unexpected study')
    if summary.get('scientific_decision') != 'NOT_ASSESSED':
        raise ValueError('scientific status changed unexpectedly')
    results = summary.get('results')
    if type(results) is not dict:
        raise ValueError('missing results')
    audits = {}
    for family, source_name in TRACKS.items():
        row = results.get(source_name)
        if type(row) is not dict or row.get('status') != 'COMPLETE_PUBLIC_DEVELOPMENT':
            raise ValueError('missing or incomplete expected track: ' + family)
        if row.get('scientific_decision') != 'NOT_ASSESSED':
            raise ValueError('invalid scientific decision')
        baseline_val = _metric(row.get('baseline_validation'))
        candidate_val = _metric(row.get('champion_validation'))
        baseline_h = _metric(row.get('holdout_baseline'))
        candidate_h = _metric(row.get('holdout'))
        if baseline_val['worlds'] != candidate_val['worlds'] or baseline_h['worlds'] != candidate_h['worlds']:
            raise ValueError('unmatched aggregate world count')
        val_delta = candidate_val['utility_units'] - baseline_val['utility_units']
        holdout_delta = candidate_h['utility_units'] - baseline_h['utility_units']
        if row.get('holdout_delta_utility') != holdout_delta:
            raise ValueError('reported holdout delta mismatch')
        if row.get('candidate_policy_promoted') is not False or row.get('deployment_decision') != 'REVERT_TYPED_POLICY_TO_BASELINE':
            raise ValueError('unsupported deployment conclusion')
        signals = []
        if val_delta > 0 and holdout_delta <= 0:
            signals.append('VALIDATION_HOLDOUT_UTILITY_REVERSAL')
        if candidate_h['accepted_correct'] > baseline_h['accepted_correct'] and holdout_delta < 0:
            signals.append('MORE_CORRECT_BUT_LOWER_NET_UTILITY')
        if candidate_h['logical_labels'] > baseline_h['logical_labels']:
            signals.append('GREATER_HOLDOUT_LABEL_COST')
        audits[family] = {
            'validation_worlds': baseline_val['worlds'],
            'holdout_worlds': baseline_h['worlds'],
            'validation_delta_utility': val_delta,
            'holdout_delta_utility': holdout_delta,
            'holdout_delta_accepted_correct': candidate_h['accepted_correct'] - baseline_h['accepted_correct'],
            'holdout_delta_logical_labels': candidate_h['logical_labels'] - baseline_h['logical_labels'],
            'signals': signals,
        }
    return {
        'schema': 'ace.r8.e15-aggregate-audit.v1',
        'source': {'repo': SOURCE_REPO, 'ref': SOURCE_REF, 'path': SOURCE_PATH,
                   'git_blob_sha1': SOURCE_GIT_BLOB_SHA1},
        'scope': 'PINNED_PUBLIC_DEVELOPMENT_AGGREGATES_ONLY',
        'tracks': audits,
        'claim_gate': 'NOT_ASSESSED',
        'cannot_infer': ['task-level paired deltas', 'new primitive discovery',
                         'cross-family transfer', 'compositional novelty',
                         'statistical significance', 'independent holdout', 'OAIE'],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, default=Path(__file__).resolve().parents[2] / SOURCE_PATH)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = audit(load_pinned_source(args.source))
    rendered = json.dumps(result, indent=2, sort_keys=True) + '\n'
    if args.output:
        args.output.write_text(rendered, encoding='utf-8')
    else:
        print(rendered, end='')


if __name__ == '__main__':
    main()
