"""Input-disjoint, *public* stress bank for frozen ACE candidate ASTs.

A replay of known arithmetic generators at new x,y coordinates. This is not
unseen task-family transfer, online learning or a sealed evaluator result.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from .candidate_case_replay import TASKS, BUDGETS, MODES, replay, interpret_ast, task_truth

ORIGINAL_PAIRS = ((-3,2),(-2,-1),(0,1),(2,0),(-5,3),(4,-2),(1,5),(-7,4),(6,-3),(3,7))
STRESS_PAIRS = ((-100,100),(100,-100),(-50,-50),(50,50),(0,0),(0,-1),
                (1,0),(-1,0),(1,-1),(-1,1),(7,11),(-9,-13),(13,-7),
                (-11,9),(35,2),(-40,3))


def run_stress(asts: dict, score_snapshot: dict, pairs: tuple = STRESS_PAIRS) -> dict:
    if type(pairs) is not tuple or not 4 <= len(pairs) <= 64:
        raise ValueError('invalid bounded stress bank')
    if len(set(pairs)) != len(pairs) or set(pairs) & set(ORIGINAL_PAIRS):
        raise ValueError('duplicate or leaked original coordinate')
    for p in pairs:
        if type(p) is not tuple or len(p) != 2 or any(type(v) is not int or abs(v) > 100 for v in p):
            raise ValueError('invalid stress coordinate')
    # Independent frozen-AST check before making new public predictions.
    base = replay(asts, score_snapshot)
    by_budget, rows = {}, []
    for budget in BUDGETS:
        by_budget[budget] = {}
        for mode in MODES:
            correct_by_task = []
            error_by_task = []
            for idx, task in enumerate(TASKS):
                ast_index = asts['by_budget'][budget][mode][idx]
                candidate = asts['asts'][ast_index]
                correct, total_abs_error = 0, 0
                for case_no, (x,y) in enumerate(pairs):
                    expected, observed = task_truth(task,x,y),interpret_ast(candidate,x,y)
                    diff = abs(expected-observed)
                    correct += (diff == 0)
                    total_abs_error += diff
                    rows.append({'budget':budget,'mode':mode,'task':task,'case':case_no,
                                 'x':x,'y':y,'expected':expected,'observed':observed,
                                 'correct':diff == 0,'absolute_error':diff})
                correct_by_task.append(correct)
                error_by_task.append(total_abs_error)
            by_budget[budget][mode] = {'fully_solved_tasks':sum(x == len(pairs) for x in correct_by_task),
                                       'correct_per_task':correct_by_task,
                                       'total_correct':sum(correct_by_task),
                                       'total_instances':len(TASKS)*len(pairs),
                                       'total_absolute_error':sum(error_by_task)}
    return {'schema':'ace.r8.public-input-stress.v1',
            'original_holdout_replay_matched':base['all_claimed_aggregates_match'],
            'original_holdout_unique_input_pairs':base['distinct_holdout_input_pairs'],
            'public_new_input_pairs':[list(x) for x in pairs],
            'new_pairs_disjoint_from_original':True,
            'prediction_rows':len(rows), 'by_budget':by_budget, 'cases':rows,
            'claim_scope':'KNOWN_MECHANISMS_NEW_PUBLIC_INPUTS',
            'scientific_claim':'NOT_CONFIRMED',
            'limitations':['Frozen candidates; no autonomous learning or adaptation during this study.',
                           'Human-defined public stress inputs, not sealed OOD mechanisms.',
                           'Tasks share x,y coordinates; rows are not independent replications.',
                           'Performance may not transfer to unseen task families.']}


def main():
    p=argparse.ArgumentParser()
    root=Path(__file__).parent
    p.add_argument('--asts',type=Path,default=root/'candidate_selected_asts.json')
    p.add_argument('--scores',type=Path,default=root/'candidate_search_snapshot.json')
    p.add_argument('--output',type=Path)
    args=p.parse_args()
    r=run_stress(json.loads(args.asts.read_text()),json.loads(args.scores.read_text()))
    txt=json.dumps(r,indent=2,sort_keys=True)+'\n'
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(txt,encoding='utf-8')
    else: print(txt,end='')

if __name__=='__main__':main()
