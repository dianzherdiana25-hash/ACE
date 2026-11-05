"""R8 independent, pure arithmetic re-evaluation of public Codex candidates.

The compact AST table and task-level snapshot are DERIVED from source PR #36;
independent byte custody only comes from --full-source with the pinned Git blob.
The 192 evaluations reuse three public x,y pairs, hence not 192 independent tasks.
Never import or execute candidate Python, and never confirm general intelligence.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path

SOURCE_COMMIT = '08da5702828285e0bd4d0f4dd8876f331ac89fe2'
SOURCE_BLOB = '069b4ffdf2f0a5a363d81bcec6ddfc4f2a5e098a'
TASKS = ('original_linear', 'negative_linear', 'difference', 'product_offset',
         'quadratic', 'constant', 'outside_grammar_floor_division',
         'outside_budget_polynomial')
BUDGETS = ('standard', 'tight')
MODES = ('fixed', 'fixed-list', 'enumerate', 'beam')
HOLDOUT_PAIRS = ((-7, 4), (6, -3), (3, 7))


def task_truth(task: str, x: int, y: int) -> int:
    if task == 'original_linear': return 3*x + 2*y
    if task == 'negative_linear': return 3*y - 2*x
    if task == 'difference': return x-y
    if task == 'product_offset': return x*y+2
    if task == 'quadratic': return x*x+y
    if task == 'constant': return 3
    if task == 'outside_grammar_floor_division': return x//(abs(y)+1)
    if task == 'outside_budget_polynomial': return x**4+y**4
    raise ValueError('unknown task')


def ast_id(node: list) -> str:
    encoded = json.dumps(node, sort_keys=True, separators=(',', ':'),
                         ensure_ascii=False, allow_nan=False).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()


def interpret_ast(root: object, x: int, y: int) -> int:
    """Strict non-executable typed AST, independently implemented for audit."""
    if type(x) is not int or type(y) is not int or max(abs(x), abs(y)) > 100:
        raise ValueError('out-of-bounds evaluation input')
    def walk(node: object, depth: int):
        if type(node) is not list or len(node) != 3 or depth > 3:
            raise ValueError('malformed or deep AST')
        op, value, children = node
        if type(op) is not str or type(children) is not list:
            raise ValueError('AST node type')
        if op == 'var':
            if type(value) is not str or value not in ('x', 'y') or children:
                raise ValueError('invalid variable')
            return (x if value == 'x' else y), 1, 0
        if op == 'const':
            if type(value) is not int or not -20 <= value <= 20 or children:
                raise ValueError('invalid constant')
            return value, 1, 0
        if op not in ('add', 'sub', 'mul') or value is not None or len(children) != 2:
            raise ValueError('forbidden AST operation')
        left, n1, o1 = walk(children[0], depth+1)
        right, n2, o2 = walk(children[1], depth+1)
        result = (left + right if op == 'add' else left - right if op == 'sub' else left * right)
        if abs(result) > 10**9:
            raise ValueError('AST arithmetic overflow')
        return result, 1+n1+n2, 1+o1+o2
    value, nodes, operations = walk(root, 0)
    if nodes > 31 or operations > 3:
        raise ValueError('AST exceeds benchmark limits')
    return value


def replay(ast_table: dict, score_snapshot: dict) -> dict:
    """Reproduce every predicted case, fail before returning on ANY disagreement."""
    if type(ast_table) is not dict or ast_table.get('schema') != 'ace.r8.codex-selected-asts.v1':
        raise ValueError('unexpected AST snapshot schema')
    if ast_table.get('source_commit') != SOURCE_COMMIT or ast_table.get('source_git_blob') != SOURCE_BLOB:
        raise ValueError('AST snapshot source mismatch')
    if ast_table.get('task_order') != list(TASKS):
        raise ValueError('unexpected task order')
    nodes, ids = ast_table.get('asts'), ast_table.get('ids')
    if (type(nodes) is not list or type(ids) is not list or
        len(nodes) != len(ids) or not 1 <= len(nodes) <= 64):
        raise ValueError('invalid AST dictionary')
    if len(set(ids)) != len(ids):
        raise ValueError('duplicate AST identities')
    for ast, ident in zip(nodes, ids):
        if type(ident) is not str or ident != ast_id(ast):
            raise ValueError('AST identity mismatch')
        interpret_ast(ast, *HOLDOUT_PAIRS[0])
    arms = ast_table.get('by_budget')
    if type(arms) is not dict or set(arms) != set(BUDGETS):
        raise ValueError('missing AST budget')
    # Do not let a case-only replay silently accept forged resource ceilings.
    # The old local prototype and the committed R8 module use compatible
    # validators with different names; the live GitHub branch uses validate.
    from . import candidate_search_audit as score_audit
    validator = getattr(score_audit, 'validate', None)
    if validator is None:
        validator = score_audit.validate_snapshot
    validator(score_snapshot)
    if (score_snapshot.get('source', {}).get('commit') != SOURCE_COMMIT or
        score_snapshot.get('source', {}).get('git_blob_sha1') != SOURCE_BLOB or
        score_snapshot.get('tasks') != list(TASKS) or
        score_snapshot.get('holdout_cases_per_task') != 3):
        raise ValueError('score snapshot source mismatch')
    if type(score_snapshot.get('arms')) is not dict or set(score_snapshot['arms']) != set(BUDGETS):
        raise ValueError('score snapshot budgets mismatch')
    cases, by_run = [], []
    for budget in BUDGETS:
        if type(arms[budget]) is not dict or set(arms[budget]) != set(MODES):
            raise ValueError('missing AST mode')
        for mode in MODES:
            indexes = arms[budget][mode]
            if type(indexes) is not list or len(indexes) != len(TASKS):
                raise ValueError('missing AST task')
            published = score_snapshot['arms'][budget][mode]
            for i, task in enumerate(TASKS):
                ix = indexes[i]
                if type(ix) is not int or ix < 0 or ix >= len(nodes):
                    raise ValueError('invalid AST index')
                selected, correct, error = nodes[ix], 0, 0
                for case_index, (x, y) in enumerate(HOLDOUT_PAIRS):
                    expected = task_truth(task, x, y)
                    predicted = interpret_ast(selected, x, y)
                    diff = abs(expected - predicted)
                    correct += (diff == 0)
                    error += diff
                    cases.append({'budget': budget, 'mode': mode, 'task': task,
                                  'case': case_index, 'x': x, 'y': y, 'expected': expected,
                                  'predicted': predicted, 'correct': diff == 0,
                                  'absolute_error': diff, 'ast_id': ids[ix]})
                if correct != published['correct'][i] or error != published['absolute_error'][i]:
                    raise ValueError('semantic replay mismatch: '+budget+'/'+mode+'/'+task)
                by_run.append({'budget': budget, 'mode': mode, 'task': task,
                               'correct': correct, 'absolute_error': error, 'ast_id': ids[ix]})
    return {'schema': 'ace.r8.public-case-replay.v1',
            'source_commit': SOURCE_COMMIT, 'source_blob_sha1': SOURCE_BLOB,
            'runs_replayed': len(by_run), 'case_predictions_replayed': len(cases),
            'distinct_holdout_input_pairs': len(HOLDOUT_PAIRS),
            'unique_selected_asts': len(nodes), 'all_claimed_aggregates_match': True,
            'replayed_correct_cases': sum(r['correct'] for r in cases),
            'cases': cases,
            'source_custody': 'DERIVED_SNAPSHOTS_ONLY_UNLESS_FULL_SOURCE_VERIFIED',
            'statistical_independence': 'NOT_ESTABLISHED_REUSED_PUBLIC_HOLDOUT_INPUTS',
            'scientific_claim': 'NOT_CONFIRMED'}


def verify_original_source(raw: bytes, ast_table: dict, score_snapshot: dict) -> None:
    """Optional, byte-pinned original receipt verification (no execution)."""
    from .candidate_search_audit import from_full_source
    full_score = from_full_source(raw)
    if full_score != score_snapshot:
        raise ValueError('source/score snapshot discrepancy')
    source = json.loads(raw.decode('utf-8'))
    for r in source['results']:
        budget, mode, task = r['budget'], r['mode'], r['task']
        ix = ast_table['by_budget'][budget][mode][TASKS.index(task)]
        if (r['frozen_candidate']['ast'] != ast_table['asts'][ix] or
            r['frozen_candidate']['id'] != ast_table['ids'][ix] or
            r['result']['selected_id'] != ast_table['ids'][ix]):
            raise ValueError('source/AST snapshot discrepancy')


def main():
    parser = argparse.ArgumentParser()
    root = Path(__file__).parent
    parser.add_argument('--asts', type=Path, default=root/'candidate_selected_asts.json')
    parser.add_argument('--scores', type=Path, default=root/'candidate_search_snapshot.json')
    parser.add_argument('--full-source', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    ast_table = json.loads(args.asts.read_text(encoding='utf-8'))
    scores = json.loads(args.scores.read_text(encoding='utf-8'))
    result = replay(ast_table, scores)
    if args.full_source:
        verify_original_source(args.full_source.read_bytes(), ast_table, scores)
        result['source_custody'] = 'FULL_SOURCE_GIT_BLOB_PIN_VERIFIED'
    encoded = json.dumps(result, indent=2, sort_keys=True)+'\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding='utf-8')
    else: print(encoded, end='')

if __name__ == '__main__': main()
