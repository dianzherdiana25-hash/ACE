"""Receipt-backed online quarantine for inherited operator semantics.

Trusted evaluator support, not a sandbox. Every decision reconstructs all paid
evidence; no score, truth function or held-out probe is available to this module.
An agreement is explicitly conditional, never proof of absence of drift.
"""
from __future__ import annotations

import hashlib
import json
import random

from .e14_shared_budget import BudgetContractError, SharedLabelBudget
from .e14_integrated_graph import audit_journal
from .e14u_primitive import PAIR_SPACE
from .e14w_synthesis import GRID
from .e14x_identifiability import measured_costs
from .e14y_induction import grammar, GRID_INDEX
from .e14aa_learning import signature as checked_signature


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


class OnlineSemanticGuard:
    """Inspect a durable four-label epoch before *each* inherited use.

    A changed epoch must use a distinct evaluator-owned arm identity. A detected
    contradiction irreversibly quarantines this inherited artifact within the
    epoch, even if later observations happen to agree. No uncharged canary calls.
    """

    def __init__(self, pair, inherited_ast, *, scope='open-world-unrestricted',
                 min_checks=2, seed=0):
        if (type(pair) is not tuple or len(pair) != 2 or
                any(type(word) is not tuple or len(word) != 3 or
                    any(type(event) is not int for event in word) for word in pair) or
                pair not in PAIR_SPACE):
            raise BudgetContractError('invalid inherited motif pair')
        if scope not in ('open-world-unrestricted', 'bounded-dsl-assumed'):
            raise BudgetContractError('unknown epistemic scope')
        if type(min_checks) is not int or not 1 <= min_checks <= 4:
            raise BudgetContractError('invalid minimum check count')
        if type(seed) is not int:
            raise BudgetContractError('invalid random seed')
        # Full finite-domain type/value validation before using an artifact.
        try:
            signature = checked_signature(inherited_ast)
        except (TypeError, ValueError, RecursionError, IndexError) as exc:
            raise BudgetContractError('invalid inherited AST') from exc
        if any(type(y) is not int or not 0 <= y <= 960 for y in signature):
            raise BudgetContractError('inherited operator exceeds label domain')
        self.pair, self.ast, self.signature = pair, inherited_ast, signature
        self.scope, self.min_checks, self.seed = scope, min_checks, seed
        self.artifact_sha256 = hashlib.sha256(canonical(inherited_ast)).hexdigest()

    def inspect(self, snapshot):
        book = SharedLabelBudget.from_snapshot(snapshot)
        paid = book.snapshot()['receipts']
        if any(row['status'] != 'settled' for row in paid):
            return self._report('blocked_pending', paid, [], [], None)
        audit_journal(snapshot)
        observations, contradictions = [], []
        for row in paid:
            points = measured_costs(row['query'], self.pair)
            if len(points) != 1:
                raise BudgetContractError('online check requires one measured cost pair')
            xy = next(iter(points))
            if xy not in GRID:
                raise BudgetContractError('online check outside declared finite domain')
            expected = self.signature[GRID_INDEX[xy]]
            observations.append((xy, row['label']))
            if row['label'] != expected:
                contradictions.append({'receipt': row['id'], 'costs': list(xy),
                                       'predicted': expected, 'observed': row['label']})
        if contradictions:
            decision = 'quarantine'
        elif len({xy for xy, _ in observations}) < self.min_checks:
            decision = 'abstain_insufficient'
        elif self.scope == 'open-world-unrestricted':
            decision = 'abstain_open_world'
        else:
            decision = 'accept_conditional'
        return self._report(decision, paid, observations, contradictions,
                            contradictions[0]['receipt'] if contradictions else None)

    def _report(self, decision, paid, observations, contradictions, first):
        return {'version': 1, 'decision': decision,
                'artifact_sha256': self.artifact_sha256, 'scope': self.scope,
                'purchased': len(paid), 'remaining': 4-len(paid),
                'observations': observations, 'contradictions': contradictions,
                'first_contradicting_receipt': first,
                'grammar_completeness_assumed': self.scope == 'bounded-dsl-assumed',
                'absence_of_drift_proven': False}

    def next_query(self, snapshot, *, allowed, strategy='random'):
        report = self.inspect(snapshot)
        if report['decision'] in ('blocked_pending', 'quarantine') or report['remaining'] == 0:
            return None
        if strategy not in ('random', 'active', 'fixed'):
            raise BudgetContractError('unknown online query strategy')
        if type(allowed) not in (tuple, list) or not allowed:
            raise BudgetContractError('invalid online query domain')
        if any(type(xy) is not tuple or len(xy) != 2 or
               any(type(x) is not int for x in xy) or xy not in GRID for xy in allowed):
            raise BudgetContractError('invalid online query point')
        if len(set(allowed)) != len(allowed):
            raise BudgetContractError('duplicate online query point')
        used = {tuple(xy) for xy, _ in report['observations']}
        offers = [xy for xy in allowed if xy not in used]
        if not offers:
            return None
        if strategy == 'fixed':
            return min(offers)
        if strategy == 'random':
            # A fixed permutation independent of truth, with no replacement.
            order = list(allowed)
            random.Random(self.seed).shuffle(order)
            return next(xy for xy in order if xy not in used)
        # Disagreement with supplied challengers; no completeness/OOD guarantee.
        challengers = [item[2] for item in grammar()
                       if all(item[2][GRID_INDEX[xy]] == y
                              for xy, y in report['observations'])]
        return max(offers, key=lambda xy: (
            sum(sig[GRID_INDEX[xy]] != self.signature[GRID_INDEX[xy]] for sig in challengers),
            -GRID_INDEX[xy]))

    def predict(self, snapshot, costs):
        if (type(costs) is not tuple or len(costs) != 2 or
                any(type(x) is not int for x in costs) or costs not in GRID):
            raise BudgetContractError('out-of-domain inherited prediction')
        report = self.inspect(snapshot)
        return (self.signature[GRID_INDEX[costs]]
                if report['decision'] == 'accept_conditional' else None)
