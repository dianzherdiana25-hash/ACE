"""Prospectively locked trusted-DSL online drift development experiment."""
from __future__ import annotations

import argparse
from dataclasses import asdict
from copy import deepcopy
import gzip
import hashlib
import json
from pathlib import Path
import random
import resource
import time

from .e14aa_bank import build, canonical, digest, SEED
from .e14aa_learning import fit, select_query, signature, SearchLimits, GRID
from .e14aa_online import OnlineSemanticGuard
from .e14aa_oracle import graph_label, value
from .e14_integrated_graph import DurableGraphBudget, purchase, audit_journal, graph_routes
from .e14_shared_budget import BudgetContractError, SharedLabelBudget
from .e14u_primitive import PAIR_SPACE
from .e14v_operator import pairs_of
from .e14y_induction import base_ast, residue_ast, threshold_ast, ast_eval, grammar, candidates
from .e14y_study import question

QUERY_GRID = tuple(xy for xy in GRID if sum(xy) % 3 != 0)
PROBE_GRID = tuple(xy for xy in GRID if xy not in QUERY_GRID)


def truth_at(row, regime, turn):
    spec = deepcopy(row['source'])
    if regime == 'needle':
        spec['outsider'] = deepcopy(row['needle'])
    elif regime == 'broad' or (regime == 'delayed' and turn >= 3):
        spec['outsider'] = {'kind': 'lo_parity', 'a': 2}
    elif regime not in ('stable', 'delayed'):
        raise BudgetContractError('unknown stream regime')
    return spec


def production_value(spec, xy):
    # Deliberately distinct from the direct-arithmetic auditor implementation.
    tree = base_ast()
    for term in spec['terms']:
        addition = (residue_ast(term['p'], term['r'], term['a'])[2]
                    if term['kind'] == 'periodic' else
                    threshold_ast(term['t'], term['a'])[2])
        tree = ('add', tree, addition)
    answer = ast_eval(tree, *xy)
    perturbation = spec.get('outsider')
    if perturbation:
        if perturbation['kind'] == 'needle':
            answer += perturbation['a'] * int(xy == (perturbation['lo'], perturbation['hi']))
        elif perturbation['kind'] == 'lo_parity':
            answer += perturbation['a'] * (xy[0] % 2)
        else:
            raise BudgetContractError('unknown production perturbation')
    return answer


def production_label(graph, pair, spec):
    points = pairs_of(graph_routes(graph)[0], pair)
    return min((production_value(spec, xy) for xy in points), default=None)


def _write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name+'.tmp')
    temporary.write_bytes(canonical(obj)+b'\n')
    temporary.replace(path)


def acquire(journal, pair, xy, spec):
    rid, label = purchase(journal, 'qualification', question(pair, xy),
                          lambda graph: production_label(graph, pair, spec))
    receipt = journal.snapshot()['receipts'][-1]
    if graph_label(receipt['query'], pair, spec) != label:
        raise BudgetContractError('independent arithmetic/DFS receipt disagreement')
    return rid, label


def learn_source(row, root):
    observed, snapshots, fits, selections = [], [], [], []
    latest = None
    limits = SearchLimits(max_seconds=5)
    for pair_idx in (0, 5, 10):
        pair = PAIR_SPACE[pair_idx]
        key = f'{row["id"]}:source:{pair_idx}'
        journal = DurableGraphBudget(root/'journals'/f'source-{row["id"]}-{pair_idx}.sqlite', key)
        for _ in range(4):
            remaining = [xy for xy in GRID if xy not in {p for p, _ in observed}]
            xy = None
            if latest is not None:
                selection = select_query(latest, observed)
                selections.append(asdict(selection))
                xy = selection.costs
            if xy is None:
                xy = remaining[0]
            _, label = acquire(journal, pair, xy, row['source'])
            observed.append((xy, label))
            latest = fit(observed, limits=limits)
            fits.append({'status': latest.status, 'complete': latest.complete,
                         'survivors': len(latest.signatures), 'stats': asdict(latest.stats)})
        snapshots.append({'pair_index': pair_idx, 'journal': journal.snapshot()})
    chosen = latest.programs[0] if latest.unique else None
    gold = tuple(value(row['source'], xy) for xy in GRID)
    old = candidates(observed)
    return {'id': row['id'], 'observations': observed, 'journals': snapshots,
            'source_labels': len(observed), 'fits': fits,
            'query_selections': selections,
            'selector_signature_lookups': sum(s['signature_lookups'] for s in selections),
            'selected_ast': chosen, 'unique_complete': latest.unique,
            'exact': chosen is not None and signature(chosen) == gold,
            'outside_old_grammar': gold not in {g[2] for g in grammar()},
            'old_grammar_survivors': len(old),
            'source_auditor_calls': len(observed)}


def _prefix(snapshot, count):
    book = SharedLabelBudget()
    for row in snapshot['receipts'][:count]:
        rid = book.reserve(row['stage'], row['query'], cost=row['cost'])
        book.settle(rid, row['label'])
    return book.snapshot()


def run_arm(row, source, pair_idx, regime, mode, root):
    key = f'{row["id"]}:{pair_idx}:{regime}:{mode}'
    journal = DurableGraphBudget(root/'journals'/f'target-{key}.sqlite', key)
    pair = PAIR_SPACE[pair_idx]
    inherited = source['selected_ast']
    if mode == 'sham-online':
        inherited = base_ast()
    serial = int(row['id'].split(':')[1])
    seed = SEED+serial*101+pair_idx*23
    guard = (OnlineSemanticGuard(pair, inherited, scope='bounded-dsl-assumed', seed=seed)
             if inherited is not None else None)
    random_order = list(QUERY_GRID)
    random.Random(seed).shuffle(random_order)
    events, used, final = [], set(), None
    for turn in range(1, 5):
        xy = None
        if guard is not None and mode == 'online-active':
            xy = guard.next_query(journal.snapshot(), allowed=QUERY_GRID, strategy='active')
        if xy is None:
            xy = next(p for p in random_order if p not in used)
        used.add(xy)
        spec = truth_at(row, regime, turn)
        rid, label = acquire(journal, pair, xy, spec)
        snap = journal.snapshot()
        if guard is None:
            state = {'decision': 'abstain_source_ambiguous', 'contradictions': []}
        else:
            # Online evidence is processed before the next inherited use.
            state = guard.inspect(_prefix(snap, min(turn, 2)) if mode == 'frozen2' else snap)
        accepted = state['decision'] == 'accept_conditional'
        predicted = signature(inherited) if accepted else None
        gold = tuple(value(spec, p) for p in GRID)
        errors = sum(a != b for a, b in zip(predicted, gold)) if accepted else 0
        probe_errors = (sum(predicted[GRID.index(p)] != value(spec, p) for p in PROBE_GRID)
                        if accepted else 0)
        events.append({'turn': turn, 'receipt': rid, 'query': xy, 'label': label,
                       'decision': state['decision'], 'accepted': int(accepted),
                       'exact': int(accepted and errors == 0),
                       'wrong_accepted': int(accepted and errors != 0),
                       'finite_domain_errors': errors, 'probe_errors': probe_errors,
                       'accepted_probes': len(PROBE_GRID)*int(accepted),
                       'drift_detected': int(state['decision'] == 'quarantine'),
                       'monitor': state})
        final = state
    snapshot = journal.snapshot()
    audit_journal(snapshot)
    _write_json(root/'snapshots'/f'{key}.json', snapshot)
    return {'id': key, 'source_id': row['id'], 'pair_index': pair_idx,
            'regime': regime, 'mode': mode, 'inherited_ast': inherited,
            'source_label_cost': source['source_labels'],
            'target_labels': snapshot['purchased'],
            'target_auditor_calls': snapshot['purchased'],
            'query_cost': snapshot['query_cost_totals'],
            'target_journal': snapshot, 'events': events,
            'first_detection_turn': next((e['turn'] for e in events if e['drift_detected']), None),
            'final_decision': final['decision'],
            'wrong_use_events': sum(e['wrong_accepted'] for e in events),
            'accepted_use_events': sum(e['accepted'] for e in events)}


def study(root, bank):
    if canonical(bank) != canonical(build()):
        raise BudgetContractError('prospective development bank changed')
    if root.exists() and any(root.iterdir()):
        raise BudgetContractError('fresh study requires empty output; never silently repurchase on resume')
    root.mkdir(parents=True, exist_ok=True)
    started, cpu = time.monotonic(), time.process_time()
    sources, arms = [], []
    for row in bank['rows']:
        source = learn_source(row, root)
        sources.append(source)
        _write_json(root/'sources'/f'{row["id"]}.json', source)
        for pair in bank['target_pairs']:
            for regime in bank['regimes']:
                for mode in bank['modes']:
                    arms.append(run_arm(row, source, pair, regime, mode, root))
        _write_json(root/'progress.json', {'status': 'RUNNING', 'sources': len(sources),
                                         'arms': len(arms), 'expected': bank['expected_arms']})
        print(json.dumps({'checkpoint': row['id'], 'source_unique': source['unique_complete'],
                          'source_exact': source['exact'], 'arms': len(arms)}), flush=True)
    summary = {}
    for regime in bank['regimes']:
        summary[regime] = {}
        for mode in bank['modes']:
            selected = [a for a in arms if a['regime'] == regime and a['mode'] == mode]
            summary[regime][mode] = {
                'arms': len(selected), 'target_labels': sum(a['target_labels'] for a in selected),
                'wrong_use_events': sum(a['wrong_use_events'] for a in selected),
                'accepted_use_events': sum(a['accepted_use_events'] for a in selected),
                'detected_arms': sum(a['first_detection_turn'] is not None for a in selected),
                'final_wrong_accepted': sum(a['events'][-1]['wrong_accepted'] for a in selected),
                'probe_errors': sum(e['probe_errors'] for a in selected for e in a['events'])}
    report = {'version': 1, 'status': 'COMPLETE_PUBLIC_DEVELOPMENT',
              'scientific_decision': 'NOT_ASSESSED', 'bank_sha256': digest(bank),
              'source_labels': sum(s['source_labels'] for s in sources),
              'source_exact': sum(s['exact'] for s in sources),
              'target_labels': sum(a['target_labels'] for a in arms),
              'target_auditor_calls': sum(a['target_auditor_calls'] for a in arms),
              'source_auditor_calls': sum(s['source_auditor_calls'] for s in sources),
              'evaluator_calls': {
                  'receipt_graph_rechecks': sum(a['target_labels'] for a in arms)+sum(s['source_labels'] for s in sources),
                  'source_finite_domain_values': len(GRID)*len(sources),
                  'target_finite_domain_values': len(GRID)*4*len(arms),
                  'target_heldout_value_rechecks': len(PROBE_GRID)*sum(e['accepted'] for a in arms for e in a['events']),
                  'learner_fit_full_grid_signatures': 'counted in each source fits.stats.signature_evaluations',
                  'production_graph_calls': sum(a['target_labels'] for a in arms)+sum(s['source_labels'] for s in sources)},
              'arm_count': len(arms), 'query_points': len(QUERY_GRID),
              'heldout_points': len(PROBE_GRID), 'summary': summary,
              'resources': {'cpu_seconds': time.process_time()-cpu,
                            'wall_seconds': time.monotonic()-started,
                            'peak_rss_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss},
              'sources': sources, 'rows': arms,
              'limitations': ['same-project public development, not independent confirmation',
                              'trusted in-process DSL; native sandbox gate remains open',
                              'provided primitives and finite two-term residual search',
                              'query blindness does not imply universal semantic safety',
                              'target-heldout cost coordinates may be observed in separate source tasks',
                              'source cost shared across target controls; no cold total-budget dominance']}
    report['sha256'] = digest(report)
    with (root/'report.json.gz').open('wb') as output:
        with gzip.GzipFile(filename='', mode='wb', fileobj=output, mtime=0) as stream:
            stream.write(canonical(report))
    _write_json(root/'summary.json', {k:v for k,v in report.items() if k not in ('sources', 'rows')})
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bank', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--lock', type=Path, required=True)
    args = parser.parse_args()
    verify_lock(args.lock)
    report = study(args.output, json.loads(args.bank.read_bytes()))
    print(json.dumps({k:v for k,v in report.items() if k not in ('sources','rows')}, sort_keys=True))


def verify_lock(path):
    """Refuse scoring on bytes different from the prospectively committed lock."""
    root = Path(__file__).resolve().parents[2]
    lock = json.loads(path.read_bytes())
    if lock.get('status') != 'PRESCORE_LOCK' or not lock.get('files'):
        raise BudgetContractError('invalid prescore source lock')
    for name, expected in lock['files'].items():
        source = (root/name).resolve()
        if not source.is_relative_to(root) or not source.is_file():
            raise BudgetContractError('invalid locked source path')
        if hashlib.sha256(source.read_bytes()).hexdigest() != expected:
            raise BudgetContractError('prescore source mismatch: '+name)


if __name__ == '__main__':
    main()
