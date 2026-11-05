"""Public synthetic hypothesis-proposal benchmark. No ACE frozen data."""
import json, random, time
from itertools import combinations, product

X = list(product((0, 1), repeat=4))

def grammar():
    # Construct compositions, then deduplicate semantically equivalent hypotheses.
    unique = {}
    for n in (1, 2, 3):
        for ids in combinations(range(4), n):
            for neg in product((0, 1), repeat=n):
                atoms = [tuple(int(x[i] != z) for x in X) for i, z in zip(ids, neg)]
                for op in (('atom',) if n == 1 else ('and', 'or', 'xor')):
                    values = tuple(
                        all(a[j] for a in atoms) if op == 'and'
                        else any(a[j] for a in atoms) if op == 'or'
                        else sum(a[j] for a in atoms) % 2
                        for j in range(16)
                    ) if n > 1 else atoms[0]
                    unique[values] = (op, ids, neg)
    return list(unique)

H = grammar()

def trial(truth, policy, seed, budget=4):
    rng = random.Random(seed)
    pool = list(range(16))
    rng.shuffle(pool)
    train, test = pool[:12], pool[12:]
    live = list(range(len(H)))
    used = []
    for _ in range(budget):
        available = [x for x in train if x not in used]
        if policy == 'random':
            x = rng.choice(available)
        elif policy == 'static':
            x = available[0]
        else:
            x = max(available, key=lambda x: (
                sum(H[i][x] for i in live) * (len(live) - sum(H[i][x] for i in live)), -x
            ))
        used.append(x)
        live = [i for i in live if H[i][x] == truth[x]]
        if not live:
            break
    accuracy = sum(
        (2 * sum(H[i][x] for i in live) > len(live)) == bool(truth[x])
        for x in test
    ) / len(test) if live else 0.0
    return accuracy, len(used), len(live)

def study():
    start = time.process_time()
    out = {}
    for policy in ('adaptive', 'random', 'static'):
        rows = [trial(H[(i * 37 + 11) % len(H)], policy, 90000 + i) for i in range(60)]
        out[policy] = {'mean_accuracy': round(sum(r[0] for r in rows)/60, 5),
                       'labels': sum(r[1] for r in rows),
                       'mean_remaining': round(sum(r[2] for r in rows)/60, 3)}
    parity4 = tuple(sum(x) % 2 for x in X)
    out['negative_four_way_parity'] = {}
    for policy in ('adaptive', 'random', 'static'):
        rows = [trial(parity4, policy, 70000 + i) for i in range(30)]
        out['negative_four_way_parity'][policy] = {
            'mean_accuracy': round(sum(r[0] for r in rows)/30, 5),
            'labels': sum(r[1] for r in rows)}
    out['meta'] = {'unique_hypotheses': len(H), 'worlds': 60,
                   'adversarial_worlds': 30, 'labels_per_world': 4,
                   'test_points_per_world': 4,
                   'cpu_seconds': round(time.process_time()-start, 5)}
    return out

if __name__ == '__main__':
    print(json.dumps(study(), indent=2, sort_keys=True))
