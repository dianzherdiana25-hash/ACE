"""R1 H7: evidence-constructed substring residual; bounded public development."""
from __future__ import annotations
import argparse
import itertools
import json
import random
from pathlib import Path
from .h6_distinguish import binary_words, truth_base, digest

SEED = 20261106
BASES = ('equal_counts', 'a_mod3', 'contains_ab', 'dyck')
PATTERNS = tuple(''.join(p) for p in itertools.product('ab', repeat=4))
FROZEN = ('aaaaa', 'aaabb', 'ababa', 'bbbaa', 'bbbbb')
POOL = binary_words(6, 10)
TERMINAL = binary_words(11, 13)


def split_queries(index):
    train = random.Random(SEED + 30000 + index).sample(POOL, 128)
    unused = sorted(set(POOL) - set(train), key=lambda s: (len(s), s))
    val = random.Random(SEED + 40000 + index).sample(unused, 128)
    hold = random.Random(SEED + 50000 + index).sample(TERMINAL, 256)
    assert len(set(train + val)) == 256 and not set(hold).intersection(train + val)
    return train, val, hold


def modified_label(base, word, target, kind='pattern'):
    ordinary = truth_base(base, word)
    if kind == 'pattern':
        flipped = len(word) >= 6 and target in word
    elif kind == 'late':
        flipped = len(word) >= 14 and 'abba' in word
    elif kind == 'non_substring':
        flipped = len(word) >= 6 and word.count('a') % 2 == 0
    else:
        raise ValueError(kind)
    return ordinary ^ flipped


def residual_rows(base, words, target, kind):
    return [(s, bool(modified_label(base, s, target, kind) ^ truth_base(base, s))) for s in words]


def candidate_substrings(rows):
    proposed = set()
    for word, positive in rows:
        if positive:
            for size in (2, 3, 4, 5):
                proposed.update(word[i:i + size] for i in range(len(word) - size + 1))
    if len(proposed) > 100:
        raise RuntimeError('candidate budget exceeded')
    return sorted(proposed, key=lambda s: (len(s), s))


def errors(pattern, rows):
    return sum((len(w) >= 6 and pattern in w) != expected for w, expected in rows)


def discover(train, validation):
    """Construct candidates only from positive training residuals; no target access."""
    if len(train) > 128 or len(validation) > 128:
        raise RuntimeError('query-label budget exceeded')
    proposals = candidate_substrings(train)
    if len(proposals) * (len(train) + len(validation)) > 30000:
        raise RuntimeError('string comparison budget exceeded')
    for candidate in proposals:
        if errors(candidate, train) != 0 or sum(y for _, y in train) < 2:
            continue
        if errors(candidate, validation) == 0 and sum(y for _, y in validation) >= 2:
            return {'accepted': True, 'pattern': candidate,
                    'candidates': len(proposals), 'reason': 'validated_exact_fit'}
    return {'accepted': False, 'pattern': None,
            'candidates': len(proposals), 'reason': 'no_validated_residual_feature'}


def frozen_selection(train, validation):
    # Fit on train only, validation serves as an acceptance gate, not refitting.
    best = min(FROZEN, key=lambda p: (errors(p, train), FROZEN.index(p)))
    ok = (errors(best, train) == 0 and errors(best, validation) == 0 and
          sum(y for _, y in train) >= 2 and sum(y for _, y in validation) >= 2)
    return best if ok else None


def score(base, words, target, kind, pattern):
    true = [modified_label(base, word, target, kind) for word in words]
    guess = [truth_base(base, word) ^ bool(pattern and len(word) >= 6 and pattern in word)
             for word in words]
    bad = next(([w, int(y), int(x)] for w, y, x in zip(words, true, guess) if y != x), None)
    return {'correct': sum(a == b for a, b in zip(true, guess)), 'total': len(words),
            'first_error': bad}


def run_world(index, base, target, kind='pattern'):
    train_words, val_words, hold_words = split_queries(index)
    if kind == 'late':
        hold_words = random.Random(SEED + 70000 + (index-64)).sample(binary_words(14, 17), 256)
    tr = residual_rows(base, train_words, target, kind)
    va = residual_rows(base, val_words, target, kind)
    representation = discover(tr, va)
    fixed_pattern = frozen_selection(tr, va)
    chosen = representation['pattern'] if representation['accepted'] else None
    main_score = score(base, hold_words, target, kind, chosen)
    fixed_score = score(base, hold_words, target, kind, fixed_pattern)
    base_score = score(base, hold_words, target, kind, None)
    oracle_controls = [score(base, hold_words, target, kind, p)['correct'] for p in (None,)+FROZEN]
    return {'index': index, 'base': base, 'target': target if kind == 'pattern' else kind,
            'kind': kind, 'queries_sha256': digest(train_words), 'validation_sha256': digest(val_words),
            'holdout_sha256': digest(hold_words), 'train_residual_positive': sum(y for _, y in tr),
            'validation_residual_positive': sum(y for _, y in va), 'representation': representation,
            'baseline_fixed_pattern': fixed_pattern, 'score': main_score,
            'fixed_score': fixed_score, 'base_score': base_score,
            'control_oracle_correct': max(oracle_controls), 'query_label_count': len(tr)+len(va)}


def run():
    main = [run_world(16*b+p, base, pattern) for b, base in enumerate(BASES)
            for p, pattern in enumerate(PATTERNS)]
    negative = [run_world(64+j, base, 'abba', 'late') for j, base in enumerate(BASES)]
    negative += [run_world(68+j, base, None, 'non_substring') for j, base in enumerate(BASES)]
    accepted = sum(row['representation']['accepted'] for row in main)
    got = sum(row['score']['correct'] for row in main)
    oracle = sum(row['control_oracle_correct'] for row in main)
    abstentions = sum(not row['representation']['accepted'] for row in negative)
    gates = {'h7a': accepted >= 56 and got / (64*256) >= .95 and
             (got-oracle)/(64*256) >= .10,
             'h7b': abstentions >= 7}
    gates['overall_go'] = gates['h7a'] and gates['h7b']
    return {'schema': 'r1-h7-1', 'protocol_commit': '9e7e810952a39a1003e28fb0005037ffe62db0fd',
            'scientific_status': 'NOT_ASSESSED', 'main': main, 'controls': negative,
            'summary': {'accepted': accepted, 'out_of': 64, 'holdout_correct': got,
                        'holdout_total': 64*256, 'oracle_fixed_correct': oracle,
                        'oracle_gain': round((got-oracle)/(64*256), 6),
                        'negative_abstentions': abstentions, 'negative_total': 8,
                        'train_validation_oracle_labels': 72*256, 'gates': gates}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = run()
    if args.output:
        args.output.write_text(json.dumps(result, sort_keys=True, indent=2)+'
')
    print(json.dumps(result['summary'], sort_keys=True))


if __name__ == '__main__':
    main()
