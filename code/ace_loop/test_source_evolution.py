"""E1.5 bounded source candidate tests: never execute generated Python."""
import json
from pathlib import Path
import tempfile
import unittest
from .engine import ResearchIntegrityError
from .source_evolution import SourceEvolution, source_for, parse_source, interpret, score, synthetic_bank


class SourceSafetyTests(unittest.TestCase):
    def test_baseline(self):
        self.assertEqual(interpret(parse_source(source_for('x+y')),2,3),5)

    def test_no_calls_imports_or_exec(self):
        for s in ('__import__("os")','open("x")','x.__class__','x / y','x ** y',
                  '[x for x in range(2)]','x if x>y else y'):
            with self.subTest(s=s), self.assertRaises(ResearchIntegrityError):source_for(s)

    def test_reject_function_side_effects(self):
        for s in ('import os\ndef predict(x,y): return x+y\n',
                  'def predict(x,y):\n print(x)\n return x\n',
                  '@property\ndef predict(x,y): return x\n',
                  'def predict(x,y,z): return x+y\n'):
            with self.subTest(s=s),self.assertRaises(ResearchIntegrityError):parse_source(s)

    def test_reject_bool_float_and_overflow(self):
        with self.assertRaises(ResearchIntegrityError):interpret(parse_source(source_for('x+y')),True,1)
        with self.assertRaises(ResearchIntegrityError):source_for('True + x')
        with self.assertRaises(ResearchIntegrityError):source_for('1.5*x')
        with self.assertRaises(ResearchIntegrityError):interpret(parse_source(source_for('20*20*20*20*20*20*x')),100,1)

    def test_disjoint_cases(self):
        b=synthetic_bank()
        keys=[set((x,y) for x,y,_ in b[k]) for k in b]
        self.assertFalse(keys[0]&keys[1]);self.assertFalse(keys[1]&keys[2]);self.assertFalse(keys[0]&keys[2])


class EvolutionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)

    def test_evolution_stages_real_source(self):
        e=SourceEvolution(self.root/'one');result=e.run()
        self.assertEqual(result['status'],'COMPLETE_PUBLIC_SOURCE_DEVELOPMENT')
        self.assertEqual(result['selected_name'],'x3_y2')
        self.assertEqual(result['holdout_selected']['absolute_error'],0)
        self.assertFalse(result['candidate_promoted'])
        staged=(self.root/'one'/'staged_candidate.py').read_text()
        self.assertEqual(score(staged,e.bank['holdout'])['absolute_error'],0)

    def test_checkpoint_resume_matches_clean(self):
        p=SourceEvolution(self.root/'one');self.assertEqual(p.run(stop_after=2)['status'],'PAUSED_CHECKPOINT')
        resumed=SourceEvolution(self.root/'one').run()
        fresh=SourceEvolution(self.root/'two').run()
        self.assertEqual(resumed,fresh)
        self.assertEqual((self.root/'one'/'events.jsonl').read_bytes(),(self.root/'two'/'events.jsonl').read_bytes())

    def test_idempotence(self):
        e=SourceEvolution(self.root/'one');a=e.run();before=(self.root/'one'/'events.jsonl').read_bytes()
        self.assertEqual(SourceEvolution(self.root/'one').run(),a)
        self.assertEqual((self.root/'one'/'events.jsonl').read_bytes(),before)

    def test_tamper_event_blocks(self):
        e=SourceEvolution(self.root/'one');e.run(stop_after=2)
        p=self.root/'one'/'events.jsonl';p.write_bytes(p.read_bytes().replace(b'"index":1',b'"index":9'))
        with self.assertRaises(ResearchIntegrityError):SourceEvolution(self.root/'one')

    def test_staged_tamper_blocks(self):
        e=SourceEvolution(self.root/'one');e.run()
        (self.root/'one'/'staged_candidate.py').write_text('def predict(x,y): return 0\n')
        with self.assertRaises(ResearchIntegrityError):SourceEvolution(self.root/'one')

    def test_stage_recover_from_missing_file(self):
        e=SourceEvolution(self.root/'one');r=e.run();(self.root/'one'/'staged_candidate.py').unlink()
        self.assertEqual(SourceEvolution(self.root/'one').run(),r)

    def test_replay_rejects_rehashed_forged_decision(self):
        e=SourceEvolution(self.root/'one');e.run(stop_after=2)
        p=self.root/'one'/'events.jsonl'
        rows=[json.loads(line) for line in p.read_text().splitlines()]
        rows[2]['payload']['champion']=4
        from .engine import digest,canonical
        for i,row in enumerate(rows):
            row['prev']='0'*64 if i==0 else rows[i-1]['sha256']
            row['sha256']=digest({k:row[k] for k in ('seq','prev','kind','payload')})
        p.write_bytes(b''.join(canonical(row)+b'\n' for row in rows))
        with self.assertRaises(ResearchIntegrityError):SourceEvolution(self.root/'one')

    def test_staged_symlink_blocked(self):
        e=SourceEvolution(self.root/'one');e.run()
        p=self.root/'one'/'staged_candidate.py';p.unlink();p.symlink_to(self.root/'other')
        with self.assertRaises(ResearchIntegrityError):SourceEvolution(self.root/'one')

    def test_stop_type_guard(self):
        with self.assertRaises(ResearchIntegrityError):SourceEvolution(self.root/'one').run(stop_after=True)

if __name__=='__main__':unittest.main()
