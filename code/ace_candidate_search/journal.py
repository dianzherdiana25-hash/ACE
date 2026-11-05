"""Atomic durable checkpoints with canonical hash-chain and semantic prefix replay.

Single trusted local writer, serialized by flock. Every 64 events (also pause,
freeze and completion), a checkpoint replaces the entire
bounded prefix atomically and fsyncs the directory. A crash leaves the old or new
complete prefix. No damaged/truncated evidence is silently repaired. Hashes are
integrity checks, not signatures or protection against whole-history rollback.
"""
from __future__ import annotations
from dataclasses import asdict, replace
from pathlib import Path
import fcntl
import json
import os
import tempfile
from .model import (Grammar, Limits, Observation, Meter, IntegrityError, canonical,
                    digest, integer, observations)
from .search import Search, evaluate, rank

MAX_JOURNAL = 32 * 1024 * 1024


def events(grammar: Grammar, limits: Limits, training: tuple[Observation, ...],
           validation: tuple[Observation, ...], holdout: tuple[Observation, ...], mode: str):
    if type(grammar) is not Grammar or type(limits) is not Limits:
        raise IntegrityError('run contracts')
    for rows in (training, validation, holdout):
        observations(rows)
    keys = [{(r.x, r.y) for r in rows} for rows in (training, validation, holdout)]
    if any(keys[i] & keys[j] for i, j in ((0, 1), (0, 2), (1, 2))):
        raise IntegrityError('overlapping splits')
    # Reserve worst-case validation + one terminal holdout evaluation. One shared
    # total ceiling; unused evaluation reserve is deliberately not spent on search.
    reserve = (limits.shortlist * len(validation) + len(holdout)) * (2 * limits.max_operations + 1)
    if reserve >= limits.max_work:
        raise IntegrityError('compute budget cannot cover evaluator reserve')
    search = Search(grammar, replace(limits, max_work=limits.max_work - reserve), training, mode)
    yield 'config', {'schema': 1, 'algorithm': 'typed-search-v1', 'mode': mode,
                     'grammar': asdict(grammar), 'limits': asdict(limits),
                     'split_sha256': [digest([asdict(r) for r in rows]) for rows in (training, validation, holdout)],
                     'selection': 'training shortlist; validation error, operations, depth, AST ties',
                     'work_definition': 'composition attempt + interpreted node', 'evaluation_reserve': reserve}
    yield from search.events()
    shortlist = search.shortlist()
    yield 'shortlist', {'ids': [e.identity for e, _ in shortlist],
                        'excluded': len(search.results) - len(shortlist),
                        'exclusion_reason': 'training_rank_or_overflow'}
    meter = Meter(reserve)
    ranked = []
    for expr, _ in shortlist:
        before = meter.work
        result = evaluate(expr, validation, meter)
        ranked.append((expr, result))
        yield 'validation', {'id': expr.identity, 'result': result, 'work': meter.work - before}
    eligible = [(e, r) for e, r in ranked if r['status'] == 'ok']
    if not eligible:
        yield 'complete', {'status': 'no_candidate', 'holdout': None,
                           'total_work': search.meter.work + meter.work,
                           'scientific_decision': 'NOT_ASSESSED', 'candidate_promoted': False}
        return
    selected, score = min(eligible, key=lambda pair: rank(*pair))
    yield 'freeze', {'id': selected.identity, 'ast': selected.data(), 'validation': score,
                     'decisions': [{'id': e.identity, 'selected': e == selected,
                                    'reason': 'validation_rank' if r['status'] == 'ok' else 'overflow'}
                                   for e, r in ranked]}
    # No proposal or selection can follow this point. Pure scoring may repeat
    # during recovery; no remote effects and no exactly-once computation claim.
    final = evaluate(selected, holdout, meter)
    yield 'complete', {'status': 'complete', 'selected_id': selected.identity,
                       'holdout': final, 'search_work': search.meter.work,
                       'evaluation_work': meter.work, 'total_work': search.meter.work + meter.work,
                       'scientific_decision': 'NOT_ASSESSED', 'candidate_promoted': False}


def _safe(path: Path) -> None:
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise IntegrityError('symlink checkpoint path')


def _read(path: Path) -> list[dict]:
    if not path.exists():
        return []
    if path.stat().st_size > MAX_JOURNAL:
        raise IntegrityError('oversized journal')
    data = path.read_bytes()
    if not data or not data.endswith(b'\n'):
        raise IntegrityError('empty or truncated journal')
    try:
        rows = [json.loads(line) for line in data.splitlines()]
        if b''.join(canonical(r) + b'\n' for r in rows) != data:
            raise IntegrityError('noncanonical journal or duplicate JSON keys')
        previous = '0' * 64
        for i, row in enumerate(rows):
            if type(row) is not dict or set(row) != {'seq', 'prev', 'kind', 'payload', 'sha256'}:
                raise IntegrityError('event schema')
            if type(row['seq']) is not int or row['seq'] != i or row['prev'] != previous:
                raise IntegrityError('event sequence')
            expected = digest({k: row[k] for k in ('seq', 'prev', 'kind', 'payload')})
            if row['sha256'] != expected:
                raise IntegrityError('event checksum')
            previous = expected
        return rows
    except (ValueError, TypeError, KeyError, RecursionError) as exc:
        raise IntegrityError('corrupt journal') from exc


def _save(path: Path, rows: list[dict]) -> None:
    content = b''.join(canonical(r) + b'\n' for r in rows)
    if len(content) > MAX_JOURNAL:
        raise IntegrityError('journal size ceiling')
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix='.checkpoint-')
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def run(path: Path, grammar: Grammar, limits: Limits, training: tuple[Observation, ...],
        validation: tuple[Observation, ...], holdout: tuple[Observation, ...],
        mode: str = 'beam', pause_after: int | None = None) -> dict:
    """Resume a canonical semantic prefix. pause_after counts newly committed events.

    Recompute pure work to verify all old events before extending the prefix.
    Checkpoint every 64 events, on pause, before holdout, and at completion;
    interrupted uncommitted work is recomputed without duplicate receipts.
    Logical work is deterministic; replay CPU/elapsed overhead is measured outside
    the journal by the benchmark. Removing a valid suffix cannot be detected
    without an external trusted chain head; this module makes no such claim.
    """
    if pause_after is not None:
        integer(pause_after, 0, 20000, 'pause_after')
    path = Path(path)
    _safe(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = path.with_name(path.name + '.lock')
    _safe(lock)
    with lock.open('a+b') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        _safe(path)
        old = _read(path)
        rows = list(old)
        added = 0
        iterator = events(grammar, limits, training, validation, holdout, mode)
        i = 0
        while True:
            if i >= len(old) and pause_after is not None and added >= pause_after:
                if added:
                    _save(path, rows)
                return {'status': 'paused', 'events': len(rows),
                        'chain_head': rows[-1]['sha256'] if rows else None}
            try:
                kind, payload = next(iterator)
            except StopIteration:
                break
            row = {'seq': i, 'prev': '0' * 64 if i == 0 else rows[i-1]['sha256'],
                   'kind': kind, 'payload': payload}
            row['sha256'] = digest(row)
            if i < len(old):
                # Byte comparison avoids bool == int aliases during semantic replay.
                if canonical(row) != canonical(old[i]):
                    raise IntegrityError('semantic replay mismatch at event ' + str(i))
            else:
                rows.append(row)
                added += 1
                if added % 64 == 0 or kind in ('freeze', 'complete'):
                    _save(path, rows)
            i += 1
            if kind == 'complete':
                if len(rows) != i:
                    raise IntegrityError('unexpected events after terminal receipt')
                return payload
        raise IntegrityError('missing terminal event')
