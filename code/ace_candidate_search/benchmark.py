"""Public, synthetic development bank. Never an independent confirmatory bank."""
from __future__ import annotations
import argparse
from dataclasses import asdict
from pathlib import Path
import hashlib
import json
import platform
import time
from .model import Grammar, Limits, Observation, digest
from .journal import run

BASE_SHA = '965640786cbf2f8adcd89eb1d980945f78c2da77'
PAIRS = ((-3, 2), (-2, -1), (0, 1), (2, 0), (-5, 3), (4, -2), (1, 5), (-7, 4), (6, -3), (3, 7))
TASKS = {
    'original_linear': lambda x, y: 3*x + 2*y,
    'negative_linear': lambda x, y: 3*y - 2*x,
    'difference': lambda x, y: x-y,
    'product_offset': lambda x, y: x*y + 2,
    'quadratic': lambda x, y: x*x + y,
    'constant': lambda x, y: 3,
    'outside_grammar_floor_division': lambda x, y: x // (abs(y)+1),
    'outside_budget_polynomial': lambda x, y: x*x*x*x + y*y*y*y,
}


def bank(name: str) -> tuple:
    rows = tuple(Observation(x, y, TASKS[name](x, y)) for x, y in PAIRS)
    return rows[:4], rows[4:7], rows[7:]


def benchmark(root: Path) -> dict:
    grammar = Grammar()
    budgets = {'standard': Limits(), 'tight': Limits(max_candidates=5, max_work=300)}
    results = []
    for budget_name, limits in budgets.items():
        for task in TASKS:
            for mode in ('fixed', 'fixed-list', 'enumerate', 'beam'):
                path = root / budget_name / task / (mode + '.jsonl')
                cpu, wall = time.process_time(), time.perf_counter()
                result = run(path, grammar, limits, *bank(task), mode=mode)
                elapsed = {'cpu_seconds': time.process_time()-cpu, 'wall_seconds': time.perf_counter()-wall}
                rows = [json.loads(line) for line in path.read_text().splitlines()]
                stop = next(r['payload'] for r in rows if r['kind'] == 'search_stop')
                results.append({'budget': budget_name, 'task': task, 'mode': mode,
                                'result': result, 'search': stop, 'timing': elapsed,
                                'chain_head': rows[-1]['sha256'],
                                'frozen_candidate': next((r['payload'] for r in rows if r['kind']=='freeze'), None),
                                'journal_sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    return {'schema': 1, 'base_sha': BASE_SHA, 'python': platform.python_version(),
            'status': 'PUBLIC_SYNTHETIC_DEVELOPMENT_ONLY', 'scientific_decision': 'NOT_ASSESSED',
            'grammar': asdict(grammar), 'budgets': {k: asdict(v) for k, v in budgets.items()},
            'bank_sha256': digest({n: [[asdict(r) for r in split] for split in bank(n)] for n in TASKS}),
            'results': results}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='new directory for receipts and summary')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    result = benchmark(args.output)
    (args.output / 'summary.json').write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    for budget in result['budgets']:
        for mode in ('fixed', 'fixed-list', 'enumerate', 'beam'):
            rows = [r for r in result['results'] if r['budget'] == budget and r['mode'] == mode]
            solved = sum(r['result']['holdout']['correct'] == 3 for r in rows)
            work = sum(r['result']['total_work'] for r in rows)
            print(budget, mode, 'solved', solved, '/', len(rows), 'work', work)


if __name__ == '__main__':
    main()
