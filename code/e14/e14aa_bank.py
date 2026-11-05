"""Fresh public development stream bank, constructed without scored outcomes."""
import hashlib
import json
import random

SEED = 202611051101


def build():
    rng = random.Random(SEED)
    rows = []
    for i in range(6):
        p = rng.choice((3, 4, 5, 6))
        terms = [{'kind': 'periodic', 'p': p, 'r': rng.randrange(p),
                  'a': rng.choice((-2, -1, 1, 2))}]
        if i >= 3:
            terms.append({'kind': 'threshold', 't': rng.choice((3, 5, 7, 9)),
                          'a': rng.choice((-2, -1, 1, 2))})
        domain = [(lo, hi) for lo in range(4, 19) for hi in range(lo, 19)
                  if (lo+hi) % 3 != 0]
        needle = rng.choice(domain)
        rows.append({'id': f'aa:{i:03d}', 'source': {'terms': terms},
                     'needle': {'kind': 'needle', 'lo': needle[0], 'hi': needle[1], 'a': 1}})
    return {'version': 1, 'status': 'PUBLIC_DEVELOPMENT_PRESCORE', 'seed': SEED,
            'source_pairs': [0, 5, 10], 'target_pairs': [18, 22],
            'regimes': ['stable', 'needle', 'broad', 'delayed'],
            'modes': ['frozen2', 'online-random', 'online-active', 'sham-online'],
            'target_label_cap': 4, 'source_label_cap_per_task': 4,
            'source_tasks_per_lineage': 3, 'rows': rows, 'expected_arms': 192}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()
