"""Bounded bottom-up synthesis for public integer-valued synthetic worlds.

No eval/exec, arbitrary Python source execution, or holdout-driven selection.
"""
from dataclasses import dataclass
from hashlib import sha256
import json


@dataclass(frozen=True)
class Expr:
    text: str
    values: tuple[int, ...]
    depth: int
    ops: int


def search(train, validation, *, max_depth=3, max_ops=3, max_candidates=3000,
           max_abs=100000, constants=(-2, -1, 0, 1, 2, 3)):
    """Search bounded +,-,* grammar; choose by validation only after training fit.

    Returns a deterministic ledger with resource counts. Public train/validation
    rows are (x,y,target). No holdout parameter exists by construction.
    """
    if not train or not validation or max_depth < 0 or max_ops < 0 or max_candidates < 1:
        raise ValueError('invalid budget or empty split')
    if max_depth > 5 or max_ops > 6 or max_candidates > 100000:
        raise ValueError('budget exceeds hard safety ceiling')
    rows = tuple(train) + tuple(validation)
    if any(len(r) != 3 or any(type(v) is not int or abs(v) > 100 for v in r) for r in rows):
        raise ValueError('invalid synthetic integer row')
    if any(type(c) is not int or abs(c) > 20 for c in constants):
        raise ValueError('invalid constants')
    ntrain = len(train)
    pool = {}
    layers = [[] for _ in range(max_depth + 1)]
    evaluated = 0
    truncated = False

    def insert(text, values, depth, ops):
        nonlocal evaluated, truncated
        if any(abs(v) > max_abs for v in values):
            return
        if values in pool:
            return
        if evaluated >= max_candidates:
            truncated = True
            return
        node = Expr(text, values, depth, ops)
        pool[values] = node
        layers[depth].append(node)
        evaluated += 1

    insert('x', tuple(r[0] for r in rows), 0, 0)
    insert('y', tuple(r[1] for r in rows), 0, 0)
    for c in constants:
        insert(str(c), (c,) * len(rows), 0, 0)
    for depth in range(1, max_depth + 1):
        if truncated:
            break
        earlier = [e for layer in layers[:depth] for e in layer]
        for a in earlier:
            if truncated:
                break
            for b in earlier:
                if truncated:
                    break
                if max(a.depth, b.depth) != depth - 1 or a.ops + b.ops + 1 > max_ops:
                    continue
                for op in ('+', '-', '*'):
                    if op in ('+', '*') and a.text > b.text:
                        continue
                    if op == '+':
                        values = tuple(x + y for x, y in zip(a.values, b.values))
                    elif op == '-':
                        values = tuple(x - y for x, y in zip(a.values, b.values))
                    else:
                        values = tuple(x * y for x, y in zip(a.values, b.values))
                    insert(f'({a.text}{op}{b.text})', values, depth, a.ops + b.ops + 1)
                    if truncated:
                        break
    targets_train = tuple(r[2] for r in train)
    targets_valid = tuple(r[2] for r in validation)
    def error(e, start, targets):
        return sum(abs(x-y) for x,y in zip(e.values[start:start+len(targets)], targets))
    train_fits = [e for e in pool.values() if error(e, 0, targets_train) == 0]
    champion = min(train_fits, key=lambda e: (error(e,ntrain,targets_valid), e.ops,e.depth,e.text)) if train_fits else None
    result = {'status': 'FOUND' if champion else 'NO_TRAIN_FIT',
              'expression': champion.text if champion else None,
              'train_error': error(champion,0,targets_train) if champion else None,
              'validation_error': error(champion,ntrain,targets_valid) if champion else None,
              'candidates_evaluated': evaluated, 'training_fits': len(train_fits),
              'truncated': truncated, 'budget': {'max_depth':max_depth,'max_ops':max_ops,
              'max_candidates':max_candidates,'max_abs':max_abs},
              'data_digest': sha256(json.dumps({'train':train,'validation':validation},sort_keys=True).encode()).hexdigest()}
    return result
