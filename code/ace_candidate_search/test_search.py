"""Reproducible safety, resource, separation, replay and interruption tests."""
from dataclasses import replace
from pathlib import Path
import json
import os
import select
import signal
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from .model import (Expr, Grammar, Limits, Observation, Meter, Exhausted, IntegrityError,
                    canonical, digest, interpret)
from .search import Search, evaluate, fixed_candidates
from .journal import events, run, _read
from .benchmark import bank


class ModelTests(unittest.TestCase):
    def test_typed_ast_rejects_executable_constructs(self):
        for op in ('call', 'import', 'attribute', 'pow', 'div', '__import__', 'x+y'):
            with self.subTest(op=op), self.assertRaises(IntegrityError):
                Expr(op)
        for value in (True, 1.5, '2', None, 21, -21):
            with self.subTest(value=value), self.assertRaises(IntegrityError):
                Expr('const', value)
        for expr in (lambda: Expr('var', '__class__'), lambda: Expr('add'),
                     lambda: Expr('mul', args=(Expr('const', 1),)),
                     lambda: Expr('sub', args=['x', 'y'])):
            with self.assertRaises(IntegrityError):
                expr()
        with self.assertRaises(IntegrityError):
            interpret('__import__("os")', 0, 0, Meter(100))

    def test_interpret_matches_arithmetic(self):
        for expr, (a, b) in zip(fixed_candidates(), ((1,1), (2,1), (3,1), (3,2), (2,2))):
            for x, y in ((-100,100), (0,0), (3,-4)):
                meter = Meter(100)
                self.assertEqual(interpret(expr, x, y, meter), a*x+b*y)
                self.assertEqual(meter.work, expr.nodes)

    def test_input_types_and_limits(self):
        for args in ((True,0,0), (0,1.2,0), (101,0,0), (0,0,10**9+1)):
            with self.assertRaises(IntegrityError):
                Observation(*args)
        for kw in ({'max_work': True}, {'max_depth': 7}, {'max_operations': 16},
                   {'max_candidates': 10001}, {'shortlist': 0}, {'beam_width': -1}):
            with self.assertRaises(IntegrityError):
                Limits(**kw)
        for kw in ({'constants': (True,)}, {'constants': (1,1)}, {'operations': ('div',)},
                   {'operations': ()}, {'constants': [0]}):
            with self.assertRaises(IntegrityError):
                Grammar(**kw)

    def test_overflow_and_meter_stop(self):
        x = Expr('var', 'x')
        square = Expr('mul', args=(x,x))
        fourth = Expr('mul', args=(square,square))
        sixth = Expr('mul', args=(fourth,square))
        with self.assertRaises(OverflowError):
            interpret(sixth, 100, 0, Meter(100))
        score = evaluate(sixth, (Observation(100,0,0),), Meter(100))
        self.assertEqual(score['status'], 'overflow')
        meter = Meter(1)
        with self.assertRaises(Exhausted):
            interpret(square, 1, 0, meter)
        self.assertEqual(meter.work, 1)
        with self.assertRaises(IntegrityError):
            interpret(x, True, 0, Meter(10))


class SearchTests(unittest.TestCase):
    def collect(self, **kw):
        kw.setdefault('mode','beam')
        return list(events(Grammar(), kw.pop('limits', Limits()), *bank('negative_linear'), **kw))

    def test_synthesizes_outside_fixed_list(self):
        ev = self.collect()
        self.assertEqual(ev[-1][1]['holdout']['absolute_error'], 0)
        selected = next(p for k,p in ev if k == 'freeze')
        self.assertNotIn(selected['id'], {e.identity for e in fixed_candidates()})
        trials = [p for k,p in ev if k == 'trial']
        self.assertGreater(len(trials), 5)
        self.assertTrue(all(p['type'] == 'Int' and 'parents' in p['provenance'] for p in trials))
        shortlist = next(p for k,p in ev if k == 'shortlist')
        self.assertEqual(shortlist['excluded']+len(shortlist['ids']), len(trials))

    def test_determinism(self):
        self.assertEqual(self.collect(), self.collect())

    def test_candidate_and_compute_caps(self):
        for limits, reason in ((Limits(max_candidates=2), 'candidate_limit'),
                               (Limits(max_work=160), 'compute_limit')):
            ev = self.collect(limits=limits)
            stop = next(p for k,p in ev if k == 'search_stop')
            self.assertEqual(stop['reason'], reason)
            self.assertLessEqual(stop['candidates'], limits.max_candidates)
            self.assertLessEqual(ev[-1][1]['total_work'], limits.max_work)

    def test_depth_operations_and_grammar(self):
        for limits in (Limits(max_depth=0), Limits(max_operations=0),
                       Limits(max_depth=1,max_operations=1)):
            search = Search(Grammar(constants=(),operations=('sub',)), limits, bank('difference')[0])
            ev = list(search.events())
            for kind, trial in ev:
                if kind == 'trial':
                    self.assertLessEqual(trial['depth'], limits.max_depth)
                    self.assertLessEqual(trial['operations'], limits.max_operations)
                    self.assertIn(trial['provenance']['rule'], ('var','sub'))

    def test_generator_observation_boundary(self):
        training, validation, holdout = bank('negative_linear')
        changed = tuple(replace(r,target=0) for r in validation)
        first = list(events(Grammar(),Limits(),training,validation,holdout,'beam'))
        second = list(events(Grammar(),Limits(),training,changed,holdout,'beam'))
        self.assertEqual([e for e in first if e[0] in ('trial','search_stop','shortlist')],
                         [e for e in second if e[0] in ('trial','search_stop','shortlist')])
        changed_holdout = tuple(replace(r,target=0) for r in holdout)
        third = list(events(Grammar(),Limits(),training,validation,changed_holdout,'beam'))
        self.assertEqual([e for e in first if e[0] != 'config'][:-1],
                         [e for e in third if e[0] != 'config'][:-1])
        self.assertNotEqual(first[-1], third[-1])
        self.assertEqual([k for k,_ in first][-2:], ['freeze','complete'])

    def test_training_changes_search(self):
        training = bank('negative_linear')[0]
        a = Search(Grammar(),Limits(),training)
        b = Search(Grammar(),Limits(),tuple(replace(r,target=0) for r in training))
        self.assertNotEqual([p['id'] for k,p in a.events() if k=='trial'],
                            [p['id'] for k,p in b.events() if k=='trial'])

    def test_reject_overlap_duplicates_empty_and_reserve(self):
        t,v,h = bank('difference')
        for splits in ((t,t,h), ((),v,h), (t+(t[0],),v,h), (list(t),v,h)):
            with self.assertRaises(IntegrityError):
                list(events(Grammar(),Limits(),*splits,'beam'))
        with self.assertRaises(IntegrityError):
            self.collect(limits=Limits(max_work=1))

    def test_baselines_share_caps_and_keep_failures(self):
        for mode in ('fixed','fixed-list','enumerate','beam'):
            ev = self.collect(mode=mode,limits=Limits(max_candidates=5,max_work=300))
            self.assertLessEqual(sum(k=='trial' for k,_ in ev),5)
            self.assertLessEqual(ev[-1][1]['total_work'],300)
            self.assertEqual(ev[-1][1]['scientific_decision'],'NOT_ASSESSED')
            self.assertFalse(ev[-1][1]['candidate_promoted'])
        fixed = self.collect(mode='fixed-list')
        self.assertGreater(fixed[-1][1]['holdout']['absolute_error'],0)

    def test_no_candidate_is_visible(self):
        ev = self.collect(mode='fixed',limits=Limits(max_depth=0))
        self.assertEqual(ev[-1][1]['status'],'no_candidate')
        self.assertIsNone(ev[-1][1]['holdout'])


class JournalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.path = self.root/'run.jsonl'
        self.limits = Limits(max_candidates=30)

    def execute(self, path=None, **kw):
        return run(path or self.path,Grammar(),self.limits,*bank('negative_linear'),**kw)

    def rehash(self, rows):
        previous = '0'*64
        for i,row in enumerate(rows):
            row.update(seq=i,prev=previous)
            row['sha256'] = digest({k:row[k] for k in ('seq','prev','kind','payload')})
            previous = row['sha256']
        self.path.write_bytes(b''.join(canonical(r)+b'\n' for r in rows))

    def test_resume_at_phase_boundaries_matches_clean(self):
        expected = self.execute(self.root/'clean')
        clean = (self.root/'clean').read_bytes()
        rows = _read(self.root/'clean')
        cuts = [1,2, len(rows)-3, len(rows)-2, len(rows)-1, len(rows)]
        for cut in cuts:
            with self.subTest(cut=cut):
                self.path.write_bytes(b''.join(canonical(r)+b'\n' for r in rows[:cut]))
                self.assertEqual(self.execute(),expected)
                self.assertEqual(self.path.read_bytes(),clean)

    def test_pause_idempotence_and_zero(self):
        self.assertEqual(self.execute(pause_after=0)['events'],0)
        self.assertFalse(self.path.exists())
        self.assertEqual(self.execute(pause_after=8)['status'],'paused')
        result = self.execute()
        before = self.path.read_bytes()
        self.assertEqual(self.execute(),result)
        self.assertEqual(self.path.read_bytes(),before)
        for value in (True,-1,1.5):
            with self.assertRaises(IntegrityError):
                self.execute(pause_after=value)

    def test_truncated_malformed_and_tampered_fail_closed(self):
        self.execute()
        clean = self.path.read_bytes()
        for raw in (b'',clean[:-1],b'{}\n',b'null\n',b'{bad}\n',clean.replace(b'eligible',b'forged',1),
                    clean.replace(b'"seq":0',b'"seq":true',1),clean+b'{}\n'):
            with self.subTest(raw=raw[:40]):
                self.path.write_bytes(raw)
                with self.assertRaises(IntegrityError):
                    self.execute()
                self.assertEqual(self.path.read_bytes(),raw)

    def test_rehashed_forged_score_and_bool_alias_rejected(self):
        self.execute()
        clean = self.path.read_bytes()
        for target in (999, True):
            rows = [json.loads(line) for line in clean.splitlines()]
            rows[1]['payload']['train']['absolute_error'] = target
            self.rehash(rows)
            with self.assertRaisesRegex(IntegrityError,'semantic replay'):
                self.execute()
        rows = [json.loads(line) for line in clean.splitlines()]
        rows[-2]['payload']['id'] = 'a'*64
        self.rehash(rows)
        with self.assertRaises(IntegrityError):
            self.execute()

    def test_changed_configuration_and_bank_rejected(self):
        self.execute(pause_after=8)
        for kw in ({'mode':'enumerate'},):
            with self.assertRaises(IntegrityError):
                self.execute(**kw)
        self.limits = replace(self.limits,max_candidates=31)
        with self.assertRaises(IntegrityError):
            self.execute()

    def test_symlink_checkpoint_and_ancestor_and_lock_rejected(self):
        target = self.root/'target'
        target.write_text('untouched')
        for path in (self.path,self.path.with_name('run.jsonl.lock')):
            path.symlink_to(target)
            with self.assertRaises(IntegrityError):
                self.execute()
            path.unlink()
        folder = self.root/'link'
        folder.symlink_to(self.root,target_is_directory=True)
        with self.assertRaises(IntegrityError):
            self.execute(folder/'receipt')
        self.assertEqual(target.read_text(),'untouched')

    def test_pause_at_freeze_does_not_open_holdout(self):
        from . import journal
        reference = list(events(Grammar(),self.limits,*bank('negative_linear'),'beam'))
        freeze_count = next(i+1 for i,(k,_) in enumerate(reference) if k=='freeze')
        calls = []
        original = journal.evaluate
        def watched(expr, rows, meter):
            calls.append(rows)
            return original(expr, rows, meter)
        with patch('ace_candidate_search.journal.evaluate',side_effect=watched):
            result = self.execute(pause_after=freeze_count)
        self.assertEqual(result['status'],'paused')
        self.assertEqual(_read(self.path)[-1]['kind'],'freeze')
        self.assertNotIn(bank('negative_linear')[2],calls)
        self.execute()
        self.assertEqual(_read(self.path)[-1]['kind'],'complete')

    def test_atomic_write_failure_preserves_checkpoint(self):
        self.execute(pause_after=8)
        before = self.path.read_bytes()
        with patch('ace_candidate_search.journal.os.replace',side_effect=OSError('injected interruption')):
            with self.assertRaises(OSError):
                self.execute()
        self.assertEqual(self.path.read_bytes(),before)
        self.execute()
        self.assertFalse(list(self.root.glob('.checkpoint-*')))

    @unittest.skipUnless(os.name=='posix','SIGKILL/flock test requires POSIX')
    def test_real_sigkill_after_durable_checkpoint(self):
        script = '''
import signal,sys
from pathlib import Path
from ace_candidate_search import journal
from ace_candidate_search.model import Grammar,Limits
from ace_candidate_search.benchmark import bank
save = journal._save
def interrupt(path, rows):
    save(path, rows)
    print('durable',flush=True)
    signal.pause()
journal._save = interrupt
journal.run(Path(sys.argv[1]),Grammar(),Limits(max_candidates=100),*bank('negative_linear'))
'''
        worker = subprocess.Popen([sys.executable,'-c',script,str(self.path)],stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE,text=True)
        try:
            ready,_,_ = select.select([worker.stdout],[],[],15)
            self.assertTrue(ready,'worker failed to reach checkpoint')
            self.assertEqual(worker.stdout.readline().strip(),'durable')
            worker.kill()
            worker.wait(timeout=5)
            self.assertEqual(worker.returncode,-signal.SIGKILL)
            self.assertEqual(len(_read(self.path)),64)
        finally:
            if worker.poll() is None:
                worker.kill()
            worker.communicate(timeout=5)
        self.limits = Limits(max_candidates=100)
        self.execute()
        self.execute(self.root/'clean')
        self.assertEqual(self.path.read_bytes(),(self.root/'clean').read_bytes())


if __name__ == '__main__':
    unittest.main()
