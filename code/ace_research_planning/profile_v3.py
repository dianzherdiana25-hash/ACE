"""Optional local latency profiling (NONDETERMINISTIC, NEVER acceptance evidence)."""
from __future__ import annotations
from statistics import median
import argparse
import json
import platform
import time
from .planning import simulate
from .study_v3 import make_world, SEEDS

MODES = ('hier_replan', 'astar', 'dijkstra', 'astar_metric', 'robust')

def run(n: int = 24, repeats: int = 5) -> dict:
    if not 1 <= n <= 24 or not 1 <= repeats <= 20:
        raise ValueError('bounds')
    results=[]
    for seed in SEEDS[:n]:
        for condition in ('static','neutral_closure'):
            w=make_world(seed, 'nonlocal_portals', condition)
            for mode in MODES:
                simulate(w, mode, 1800)  # warmup; omit from measurement
                timings=[]
                for _ in range(repeats):
                    start=time.perf_counter_ns()
                    simulate(w, mode, 1800)
                    timings.append((time.perf_counter_ns()-start)/1e6)
                results.append({'seed':seed,'condition':condition,'method':mode,
                                'median_ms':round(median(timings),4)})
    summary={m:round(median(r['median_ms'] for r in results if r['method']==m),4)
             for m in MODES}
    return {'label':'local CPU latency diagnostic, NOT compute-matched or reproducible timing',
            'python':platform.python_version(),'n':n,'repeats':repeats,
            'median_of_per_world_medians_ms':summary,'rows':results}

if __name__ == '__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--n',type=int,default=24)
    p.add_argument('--repeats',type=int,default=5)
    a=p.parse_args()
    out=run(a.n,a.repeats)
    print(json.dumps({'n':out['n'],'repeats':out['repeats'],
                      'median_of_per_world_medians_ms':out['median_of_per_world_medians_ms']},indent=2))
