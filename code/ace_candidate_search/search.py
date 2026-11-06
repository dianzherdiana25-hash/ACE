"""Deterministic training-only proposal generation and restricted evaluation."""
from __future__ import annotations
from dataclasses import asdict
from collections.abc import Iterator
from .model import (Expr, Grammar, Limits, Observation, Meter, IntegrityError,
                    Exhausted, observations, interpret)


def evaluate(expr: Expr, rows: tuple[Observation, ...], meter: Meter) -> dict:
    observations(rows)
    error = correct = 0
    try:
        for row in rows:
            delta = abs(interpret(expr, row.x, row.y, meter) - row.target)
            error += delta
            correct += delta == 0
    except OverflowError:
        return {'status': 'overflow', 'absolute_error': None, 'correct': 0, 'count': len(rows)}
    return {'status': 'ok', 'absolute_error': error, 'correct': correct, 'count': len(rows)}


def rank(expr: Expr, result: dict) -> tuple:
    return (result['status'] != 'ok', result['absolute_error'] or 0,
            expr.operations, expr.depth, expr.key)


def fixed_candidates() -> tuple[Expr, ...]:
    """PR #27's five programs, represented as data for the comparison arm only."""
    x, y = Expr('var', 'x'), Expr('var', 'y')
    def linear(a: int, b: int) -> Expr:
        left = x if a == 1 else Expr('mul', args=(Expr('const', a), x))
        right = y if b == 1 else Expr('mul', args=(Expr('const', b), y))
        return Expr('add', args=(left, right))
    return tuple(linear(a, b) for a, b in ((1, 1), (2, 1), (3, 1), (3, 2), (2, 2)))


class Search:
    """Only training observations cross this boundary. No validation or holdout API.

    beam: train-ranked beam per completed depth, always retaining terminals.
    enumerate: all preceding expressions; same bounds, no feedback pruning.
    fixed-list/fixed: comparison arms only; never used by the proposal generator.
    Work = one unit per composition attempt + each interpreted AST node.
    """
    def __init__(self, grammar: Grammar, limits: Limits,
                 training: tuple[Observation, ...], mode: str = 'beam'):
        if type(grammar) is not Grammar or type(limits) is not Limits:
            raise IntegrityError('search contracts')
        observations(training)
        if type(mode) is not str or mode not in ('beam', 'enumerate', 'fixed-list', 'fixed'):
            raise IntegrityError('unknown search mode')
        self.grammar, self.limits, self.training, self.mode = grammar, limits, training, mode
        self.results: list[tuple[Expr, dict]] = []
        self.meter = Meter(limits.max_work)
        self.attempts = self.bound_rejections = self.duplicates = 0
        self.seen: set[str] = set()
        self.started = False

    def _proposals(self) -> Iterator[Expr | dict]:
        if self.mode in ('fixed-list', 'fixed'):
            yield from fixed_candidates()[:1 if self.mode == 'fixed' else 5]
            return
        terminals = self.grammar.terminals()
        yield from terminals
        pool = list(terminals)
        for depth in range(1, self.limits.max_depth + 1):
            for op in self.grammar.operations:
                for left in pool:
                    for right in pool:
                        self.meter.charge()
                        self.attempts += 1
                        if (1 + max(left.depth, right.depth) != depth or
                                1 + left.operations + right.operations > self.limits.max_operations):
                            self.bound_rejections += 1
                            continue
                        # Canonicalize commutative operands; retain subtraction direction.
                        if op in ('add', 'mul') and left.key > right.key:
                            self.duplicates += 1
                            continue
                        yield Expr(op, args=(left, right))
            valid = [(e, r) for e, r in self.results if r['status'] == 'ok']
            if self.mode == 'beam':
                valid.sort(key=lambda pair: rank(*pair))
                pool = list(dict.fromkeys((*terminals, *(e for e, _ in valid[:self.limits.beam_width]))))
            else:
                pool = [e for e, _ in valid]
            yield {'completed_depth': depth, 'retained_ids': [e.identity for e in pool],
                   'eligible_pruned': len(valid) - len({e.identity for e in pool} & {e.identity for e, _ in valid}),
                   'reason': 'training_rank' if self.mode == 'beam' else 'no_feedback_pruning'}

    def events(self) -> Iterator[tuple[str, dict]]:
        if self.started:
            raise IntegrityError('Search is single use')
        self.started = True
        reason = 'frontier_exhausted' if self.mode == 'beam' else 'grammar_exhausted'
        proposals = self._proposals()
        try:
            while True:
                if len(self.results) >= self.limits.max_candidates:
                    reason = 'candidate_limit'
                    break
                expr = next(proposals)
                if type(expr) is dict:
                    yield 'frontier', expr
                    continue
                # Baseline arms obey the same grammar and structural contract.
                def permitted(e: Expr) -> bool:
                    return ((e.op != 'const' or e.value in self.grammar.constants) and
                            (not e.args or e.op in self.grammar.operations) and
                            all(permitted(a) for a in e.args))
                if (expr.depth > self.limits.max_depth or expr.operations > self.limits.max_operations
                        or not permitted(expr)):
                    self.meter.charge()
                    self.bound_rejections += 1
                    continue
                if expr.identity in self.seen:
                    self.duplicates += 1
                    continue
                # Reserve a full training evaluation; never store partially scored candidates.
                if self.meter.work + expr.nodes * len(self.training) > self.meter.limit:
                    reason = 'compute_limit'
                    break
                self.seen.add(expr.identity)
                before = self.meter.work
                result = evaluate(expr, self.training, self.meter)
                self.results.append((expr, result))
                yield 'trial', {'index': len(self.results) - 1, 'id': expr.identity,
                                'ast': expr.data(), 'type': 'Int',
                                'provenance': {'rule': expr.op, 'parents': [a.identity for a in expr.args]},
                                'depth': expr.depth, 'operations': expr.operations,
                                'train': result, 'evaluation_work': self.meter.work - before,
                                'search_work': self.meter.work,
                                'decision': 'eligible' if result['status'] == 'ok' else 'rejected_overflow'}
        except StopIteration:
            pass
        except Exhausted:
            reason = 'compute_limit'
        finally:
            proposals.close()
        yield 'search_stop', {'reason': reason, 'candidates': len(self.results),
                              'composition_attempts': self.attempts,
                              'bound_rejections': self.bound_rejections,
                              'commutative_or_duplicate_skips': self.duplicates,
                              'search_work': self.meter.work, 'limits': asdict(self.limits)}

    def shortlist(self) -> list[tuple[Expr, dict]]:
        return sorted(((e, r) for e, r in self.results if r['status'] == 'ok'),
                      key=lambda pair: rank(*pair))[:self.limits.shortlist]
