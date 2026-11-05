"""Deterministic, bounded ACE meta-controller for PUBLIC SYNTHETIC research.

No live source mutation, subprocess, model training, paid oracle or promotion.
All outcomes are re-evaluable pure functions; never attach side-effectful adapters.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
import fcntl
import hashlib
import json
import os
import tempfile


class IntegrityError(RuntimeError):
    """Fail-closed state, input, or evidence error."""


class SimulatedInterruption(RuntimeError):
    """Test-only crash immediately after a durable trial receipt."""


def canonical(obj):
    return (json.dumps(obj, sort_keys=True, separators=(',', ':'),
                       ensure_ascii=False, allow_nan=False) + '\n').encode('utf-8')


def digest(obj):
    return hashlib.sha256(canonical(obj)).hexdigest()


@dataclass(frozen=True)
class Problem:
    key: str
    priority: int
    target: tuple[int, int]
    hypotheses: tuple[tuple[int, int], ...]
    cost: int = 2


# Public synthetic examples. These are NOT independently sealed research tasks.
PROBLEMS = (
    Problem('affine_shift', 3, (3, 2), ((2, 1), (3, 2), (4, 2))),
    Problem('operator_transfer', 2, (1, 2), ((1, 2), (1, 3))),
    Problem('unproductive_track', 1, (1, 1), ((2, 2), (3, 2), (4, 4))),
)
SPLITS = {
    'train': ((-3, 2), (0, 1), (2, -2), (3, 1)),
    'validation': ((-5, 3), (4, -2), (1, 5)),
    'holdout': ((-7, 4), (6, -3), (3, 7)),
}
BASELINE = (1, 1)
PATIENCE = 2
BASELINE_COMMIT = '965640786cbf2f8adcd89eb1d980945f78c2da77'


def evaluate(problem: Problem, coefficients: tuple[int, int], split: str) -> dict:
    """Bounded pure synthetic evaluator. Does not call external services."""
    if split not in SPLITS or any(type(v) is not int or abs(v) > 10 for v in coefficients):
        raise IntegrityError('invalid evaluator arguments')
    errors = [abs(coefficients[0]*x + coefficients[1]*y -
                  (problem.target[0]*x + problem.target[1]*y))
              for x, y in SPLITS[split]]
    return {'cases': len(errors), 'exact': sum(e == 0 for e in errors),
            'absolute_error': sum(errors)}


def initial_state():
    return {p.key: {'index': 0, 'champion': list(BASELINE), 'spent': 0,
                    'gain': 0, 'failures': 0, 'stopped': False} for p in PROBLEMS}


def choose(state: dict, remaining: int):
    eligible = [p for p in PROBLEMS if not state[p.key]['stopped']
                and state[p.key]['index'] < len(p.hypotheses) and remaining >= p.cost]
    if not eligible:
        return None
    pilots = [p for p in eligible if state[p.key]['index'] == 0]
    if pilots:
        return max(pilots, key=lambda p: (p.priority, p.key))
    # Validation gain per paid unit, with bounded priority tie break. No holdout.
    return max(eligible, key=lambda p: (state[p.key]['gain']*100 //
                                       max(1, state[p.key]['spent']), p.priority, p.key))


def decide(state: dict, trial: dict):
    """Candidate adoption and per-track stop. Never adopt on worse training error."""
    name = trial['problem']
    p = next(p for p in PROBLEMS if p.key == name)
    before = state[name]
    incumbent = evaluate(p, tuple(before['champion']), 'validation')
    incumbent_train = evaluate(p, tuple(before['champion']), 'train')
    adopted = (trial['validation']['absolute_error'] < incumbent['absolute_error']
               and trial['train']['absolute_error'] <= incumbent_train['absolute_error'])
    champion = list(trial['coefficients']) if adopted else before['champion'][:]
    failures = 0 if adopted else before['failures'] + 1
    stopped = failures >= PATIENCE
    spent = before['spent'] + p.cost
    gain = (evaluate(p, BASELINE, 'validation')['absolute_error'] -
            evaluate(p, tuple(champion), 'validation')['absolute_error'])
    return {'problem': name, 'adopted': adopted, 'champion': champion,
            'reason': 'validation_and_train_improved' if adopted else 'no_safe_gain',
            'failures': failures, 'stopped': stopped, 'spent': spent, 'gain': gain}


def apply(state: dict, trial: dict, decision: dict):
    state[trial['problem']].update(index=state[trial['problem']]['index'] + 1,
                                  champion=decision['champion'][:],
                                  failures=decision['failures'],
                                  stopped=decision['stopped'],
                                  spent=decision['spent'], gain=decision['gain'])


def terminal(state: dict, budget: int):
    used = sum(v['spent'] for v in state.values())
    reports = {}
    for p in PROBLEMS:
        s = state[p.key]
        base = evaluate(p, BASELINE, 'holdout')
        selected = evaluate(p, tuple(s['champion']), 'holdout')
        reports[p.key] = {'trials': s['index'], 'spent_units': s['spent'],
                          'stopped_unproductive': s['stopped'],
                          'selected_coefficients': s['champion'][:],
                          'validation_gain_absolute_error': s['gain'],
                          'holdout_baseline': base, 'holdout_selected': selected,
                          'holdout_error_reduction': base['absolute_error'] - selected['absolute_error']}
    return {'status': 'COMPLETE_PUBLIC_SYNTHETIC', 'scientific_decision': 'NOT_ASSESSED',
            'candidate_promoted': False, 'budget_units': budget, 'spent_units': used,
            'unspent_units': budget-used, 'problems': reports,
            'holdout_policy': 'TERMINAL_ONLY_NO_SELECTION',
            'external_actions': 'FORBIDDEN'}


class Controller:
    """Audit-first scheduler with append-only journal and recoverable checkpoint.

    Only a pure built-in synthetic evaluator is allowed. A journal trial is
    durable before adoption; on resume a pending trial is *decided* once.
    """
    def __init__(self, root, *, budget=16):
        if type(budget) is not int or not 2 <= budget <= 100 or budget % 2:
            raise IntegrityError('budget must be even integer in [2,100]')
        self.root = Path(root)
        if self.root.is_symlink() or self.root.parent.is_symlink():
            raise IntegrityError('symlink root forbidden')
        self.root.mkdir(parents=True, exist_ok=True)
        self.budget = budget
        self.journal = self.root/'events.jsonl'
        self.checkpoint = self.root/'checkpoint.json'
        self.lock_path = self.root/'.lock'
        self.manifest = {'schema': 1, 'baseline_commit': BASELINE_COMMIT,
                         'purpose': 'PUBLIC_SYNTHETIC_META_CONTROLLER',
                         'budget_units': budget, 'patience': PATIENCE,
                         'problems': [{'key': p.key, 'priority': p.priority,
                                       'target': list(p.target),
                                       'hypotheses': [list(h) for h in p.hypotheses],
                                       'cost': p.cost} for p in PROBLEMS],
                         'splits': {k: [list(v) for v in values]
                                    for k, values in SPLITS.items()},
                         'selection': 'pilot_by_priority_then_validation_gain_per_spent',
                         'holdout': 'terminal_only', 'remote_actions': 'FORBIDDEN'}

    def _guard(self):
        for path in (self.root, self.journal, self.checkpoint, self.lock_path):
            if path.is_symlink():
                raise IntegrityError('symlink state path forbidden')

    @contextmanager
    def _locked(self):
        self._guard()
        flags = os.O_RDWR | os.O_CREAT
        if hasattr(os, 'O_NOFOLLOW'): flags |= os.O_NOFOLLOW
        fd = os.open(self.lock_path, flags, 0o600)
        try:
            try: fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc: raise IntegrityError('concurrent controller run') from exc
            self._guard()
            yield
        finally:
            os.close(fd)

    def _read(self):
        if not self.journal.exists(): return []
        if self.journal.stat().st_size > 2_000_000:
            raise IntegrityError('journal size limit')
        rows = []
        prev = '0'*64
        for raw in self.journal.read_bytes().splitlines(keepends=True):
            if not raw.endswith(b'\n'): raise IntegrityError('truncated journal')
            try: row = json.loads(raw)
            except (ValueError, UnicodeError) as exc: raise IntegrityError('malformed journal') from exc
            if type(row) is not dict or set(row) != {'seq', 'prev', 'kind', 'payload', 'sha256'}:
                raise IntegrityError('invalid event keys')
            if type(row['seq']) is not int or row['seq'] != len(rows) or row['prev'] != prev:
                raise IntegrityError('event chain order/fork')
            expect = digest({k: row[k] for k in ('seq', 'prev', 'kind', 'payload')})
            if row['sha256'] != expect or canonical(row) != raw:
                raise IntegrityError('event hash/canonical mismatch')
            rows.append(row)
            prev = expect
        return rows

    def _append(self, rows: list, kind: str, payload: dict):
        record = {'seq': len(rows), 'prev': rows[-1]['sha256'] if rows else '0'*64,
                  'kind': kind, 'payload': payload}
        record['sha256'] = digest(record)
        flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND
        if hasattr(os, 'O_NOFOLLOW'): flags |= os.O_NOFOLLOW
        fd = os.open(self.journal, flags, 0o600)
        try:
            content = canonical(record)
            if os.write(fd, content) != len(content):
                raise IntegrityError('partial journal write')
            os.fsync(fd)
        finally:
            os.close(fd)
        rows.append(record)

    def _trial(self, p, state):
        index = state[p.key]['index']
        coeff = p.hypotheses[index]
        return {'ordinal': sum(x['index'] for x in state.values()),
                'problem': p.key, 'hypothesis_id': f'{p.key}:h{index}',
                'coefficients': list(coeff), 'cost_units': p.cost,
                'prior_champion': state[p.key]['champion'][:],
                'train': evaluate(p, coeff, 'train'),
                'validation': evaluate(p, coeff, 'validation')}

    def _replay(self, rows):
        state = initial_state()
        if not rows: return state, None, False, {}
        if rows[0]['kind'] != 'config' or rows[0]['payload'] != {'manifest': self.manifest,
                                                                  'manifest_sha256': digest(self.manifest)}:
            raise IntegrityError('config changed or forged')
        snapshots = {0: digest(state)}
        pending = None
        complete = False
        for r in rows[1:]:
            kind, payload = r['kind'], r['payload']
            remaining = self.budget - sum(s['spent'] for s in state.values())
            if kind == 'trial':
                p = choose(state, remaining)
                if complete or pending is not None or p is None or payload != self._trial(p, state):
                    raise IntegrityError('trial diverges from scheduler/evaluator')
                pending = payload
            elif kind == 'decision':
                if complete or pending is None or payload != decide(state, pending):
                    raise IntegrityError('forged or out-of-order decision')
                apply(state, pending, payload)
                pending = None
                snapshots[r['seq']] = digest(state)
            elif kind == 'complete':
                if complete or pending is not None or choose(state, remaining) is not None:
                    raise IntegrityError('premature/duplicate completion')
                if payload != terminal(state, self.budget):
                    raise IntegrityError('forged terminal metrics')
                complete = True
                snapshots[r['seq']] = digest(state)
            else:
                raise IntegrityError('unsupported event kind')
        if complete and rows[-1]['kind'] != 'complete':
            raise IntegrityError('post-terminal event')
        return state, pending, complete, snapshots

    def _verify_checkpoint(self, rows, snapshots):
        if not self.checkpoint.exists(): return
        raw = self.checkpoint.read_bytes()
        try: checkpoint = json.loads(raw)
        except (ValueError, UnicodeError) as exc: raise IntegrityError('invalid checkpoint') from exc
        if type(checkpoint) is not dict or set(checkpoint) != {'seq', 'head', 'state_sha256'} or canonical(checkpoint) != raw:
            raise IntegrityError('checkpoint schema/canonical mismatch')
        seq = checkpoint['seq']
        if type(seq) is not int or seq not in snapshots or seq >= len(rows):
            raise IntegrityError('checkpoint points to invalid event')
        if checkpoint != {'seq': seq, 'head': rows[seq]['sha256'],
                          'state_sha256': snapshots[seq]}:
            raise IntegrityError('checkpoint contradicts replay')

    def _save_checkpoint(self, rows, state):
        checkpoint = {'seq': rows[-1]['seq'], 'head': rows[-1]['sha256'],
                      'state_sha256': digest(state)}
        data = canonical(checkpoint)
        self._guard()
        fd, name = tempfile.mkstemp(prefix='.checkpoint-', dir=self.root)
        try:
            with os.fdopen(fd, 'wb') as output:
                output.write(data)
                output.flush()
                os.fsync(output.fileno())
            os.replace(name, self.checkpoint)
            dir_fd = os.open(self.root, os.O_RDONLY)
            try: os.fsync(dir_fd)
            finally: os.close(dir_fd)
        finally:
            if os.path.exists(name): os.unlink(name)

    def run(self, *, stop_after_trials=None, simulate_crash_after_trial=False):
        if stop_after_trials is not None and (type(stop_after_trials) is not int or
                                              stop_after_trials < 0):
            raise IntegrityError('invalid stop point')
        with self._locked():
            rows = self._read()
            if not rows:
                self._append(rows, 'config', {'manifest': self.manifest,
                                              'manifest_sha256': digest(self.manifest)})
            state, pending, complete, snapshots = self._replay(rows)
            self._verify_checkpoint(rows, snapshots)
            if complete:
                return rows[-1]['payload']
            if pending is not None:
                result = decide(state, pending)
                self._append(rows, 'decision', result)
                apply(state, pending, result)
                self._save_checkpoint(rows, state)
            while True:
                spent = sum(s['spent'] for s in state.values())
                p = choose(state, self.budget-spent)
                if p is None:
                    result = terminal(state, self.budget)
                    self._append(rows, 'complete', result)
                    self._save_checkpoint(rows, state)
                    return result
                trials = sum(s['index'] for s in state.values())
                if stop_after_trials is not None and trials >= stop_after_trials:
                    return {'status': 'PAUSED_CHECKPOINT', 'trials': trials,
                            'spent_units': spent, 'remaining_units': self.budget-spent,
                            'chain_head': rows[-1]['sha256']}
                trial = self._trial(p, state)
                self._append(rows, 'trial', trial)
                if simulate_crash_after_trial:
                    raise SimulatedInterruption('durable trial written; decision pending')
                result = decide(state, trial)
                self._append(rows, 'decision', result)
                apply(state, trial, result)
                self._save_checkpoint(rows, state)
