"""E1.6 source-mutation tests; all evaluator costs are local synthetic calls."""
from __future__ import annotations

import ast
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from .engine import ResearchIntegrityError, HashLedger, canonical, digest
from .operators import OperatorAdapter
from .source_evolution import (Gene, SEED, RULES, source_for, compile_rank,
                               mutate, SourceAdapter, SourceEvolution)


class SourceGrammarTests(unittest.TestCase):
    def test_mutation_changes_actual_python_source(self):
        before=source_for(SEED);g=mutate(SEED,0);after=source_for(g)
        self.assertNotEqual(before,after)
        self.assertEqual(len(ast.parse(after).body),1)
        a=compile_rank(before,SEED);b=compile_rank(after,g)
        self.assertNotEqual(a(4,7,1,4,10),b(4,7,1,4,10))

    def test_mutations_are_typed_deterministic_and_bounded(self):
        self.assertEqual(len(RULES),16)
        self.assertEqual(mutate(SEED,8),mutate(SEED,8))
        for i in range(len(RULES)):
            gene=mutate(SEED,i)
            self.assertNotEqual(source_for(gene),source_for(SEED))
            rank=compile_rank(source_for(gene),gene)
            self.assertIsInstance(rank(4,18,3,19,200),int)

    def test_bad_gene_and_python_source_fail_closed(self):
        for bad in [dict(SEED.json(),diversity=True),dict(SEED.json(),modulus=0),
                    dict(SEED.json(),sign=2),dict(SEED.json(),gap=9),
                    dict(SEED.json(),balance=1.0)]:
            with self.subTest(bad=bad),self.assertRaises(ResearchIntegrityError):Gene(**bad)
        for evil in (b'import os\n', b'def rank(*args): return open("/etc/passwd").read()\n',
                     b'def rank(lo, hi, turn, diversity, balance):\n return 0\n',
                     source_for(SEED)+b'print("hello")\n'):
            with self.subTest(evil=evil),self.assertRaises(ResearchIntegrityError):compile_rank(evil,SEED)

    def test_mutated_byte_string_cannot_be_executed_under_other_gene(self):
        with self.assertRaises(ResearchIntegrityError):
            compile_rank(source_for(mutate(SEED,0)),SEED)


class SourceStudyTests(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.adapter=SourceAdapter(OperatorAdapter(sizes=(6,4,5),outsiders_per_split=0))

    def engine(self,path='run',cycles=3,adapter=None):
        return SourceEvolution(self.root/path,adapter or self.adapter,max_cycles=cycles,patience=cycles)

    def test_split_independence_and_budget_conservation(self):
        sets=self.adapter.original._sets
        groups=[set(w.key for w in sets[s]) for s in ('train','validation','test')]
        self.assertFalse(groups[0]&groups[1]);self.assertFalse(groups[0]&groups[2]);self.assertFalse(groups[1]&groups[2])
        v=self.adapter.evaluate(SEED,'validation')
        self.assertEqual(v['worlds'],4)
        self.assertLessEqual(v['logical_labels'],4*self.adapter.label_cap)
        self.assertEqual(sum(v[k] for k in ('accepted_correct','accepted_wrong','abstained')),4)

    def test_resume_identical_to_uninterrupted_journal(self):
        e=self.engine()
        self.assertEqual(e.run(stop_after=1)['status'],'PAUSED_CHECKPOINT')
        state_before=(self.root/'run'/'events.jsonl').read_bytes()
        self.assertEqual(sum(x['kind']=='trial' for x in e.ledger.events),1)
        self.assertNotIn(b'"completed"',state_before)
        done=self.engine().run()
        clean=self.engine('fresh').run()
        self.assertEqual(done,clean)
        self.assertEqual((self.root/'run'/'events.jsonl').read_bytes(),
                         (self.root/'fresh'/'events.jsonl').read_bytes())
        self.assertEqual(len(list((self.root/'run'/'proposals').glob('*.py'))),3)
        self.assertFalse(done['candidate_code_deployed'])

    def test_repeated_completion_is_idempotent(self):
        e=self.engine();a=e.run()
        before=(self.root/'run'/'events.jsonl').read_bytes()
        b=self.engine().run()
        self.assertEqual(a,b)
        self.assertEqual(before,(self.root/'run'/'events.jsonl').read_bytes())

    def test_crash_after_durable_trial_replays_without_extra_trial(self):
        e=self.engine(cycles=2)
        gene=mutate(SEED,0)
        sha=e._source(0,gene,create=True)
        p={'ordinal':0,'parent':SEED.json(),'gene':gene.json(),
           'source_sha256':sha,'train':self.adapter.evaluate(gene,'train'),
           'validation':self.adapter.evaluate(gene,'validation')}
        e.ledger.append('trial',p)
        result=self.engine(cycles=2).run()
        self.assertEqual(result['trials'],2)
        events=self.engine(cycles=2).ledger.events
        self.assertEqual(sum(x['kind']=='trial' for x in events),2)
        self.assertEqual(sum(x['kind']=='decision' for x in events),2)

    def test_no_holdout_consulted_before_terminal_decision(self):
        e=self.engine(cycles=3)
        original=self.adapter.evaluate
        def guard(gene,split):
            if split=='test':raise AssertionError('holdout leaked before completion')
            return original(gene,split)
        with patch.object(self.adapter,'evaluate',side_effect=guard):
            paused=e.run(stop_after=2)
        self.assertEqual(paused['status'],'PAUSED_CHECKPOINT')

    def test_config_change_blocks_resume(self):
        self.engine(cycles=2).run(stop_after=1)
        with self.assertRaisesRegex(ResearchIntegrityError,'config'):
            self.engine(cycles=3)

    def test_source_tamper_blocks_any_resume(self):
        self.engine().run(stop_after=1)
        source=self.root/'run'/'proposals'/'mutation_000.py'
        source.write_bytes(source.read_bytes()+b'\n')
        with self.assertRaisesRegex(ResearchIntegrityError,'bytes tampered'):
            self.engine()

    def test_symlink_source_blocks_replay_without_changing_target(self):
        self.engine().run(stop_after=1)
        source=self.root/'run'/'proposals'/'mutation_000.py'
        original=source.read_bytes()
        source.unlink()
        outside=self.root/'outside.py';outside.write_bytes(original)
        source.symlink_to(outside)
        with self.assertRaisesRegex(ResearchIntegrityError,'symlink'):
            self.engine()
        self.assertEqual(outside.read_bytes(),original)

    def test_rehashed_forged_decision_is_rejected_by_semantics(self):
        self.engine(cycles=2).run()
        f=self.root/'run'/'events.jsonl'
        rows=[json.loads(x) for x in f.read_text().splitlines()]
        for row in rows:
            if row['kind']=='decision':
                row['payload']['adopted']=not row['payload']['adopted']
                break
        prev='0'*64
        for row in rows:
            row['prev']=prev
            row['sha256']=digest({k:row[k] for k in ('seq','prev','kind','payload')})
            prev=row['sha256']
        f.write_bytes(b''.join(canonical(x)+b'\n' for x in rows))
        with self.assertRaisesRegex(ResearchIntegrityError,'promotion decision'):
            self.engine(cycles=2)

    def test_rehashed_forged_trial_is_rejected_by_recompute(self):
        self.engine(cycles=2).run()
        f=self.root/'run'/'events.jsonl'
        rows=[json.loads(x) for x in f.read_text().splitlines()]
        for row in rows:
            if row['kind']=='trial':
                row['payload']['validation']['utility_units']+=100
                break
        prev='0'*64
        for row in rows:
            row['prev']=prev;row['sha256']=digest({k:row[k] for k in ('seq','prev','kind','payload')});prev=row['sha256']
        f.write_bytes(b''.join(canonical(x)+b'\n' for x in rows))
        with self.assertRaisesRegex(ResearchIntegrityError,'scored evidence'):
            self.engine(cycles=2)

    def test_terminal_writes_holdout_once_and_does_not_deploy(self):
        result=self.engine(cycles=2).run()
        events=self.engine(cycles=2).ledger.events
        self.assertEqual(sum(e['kind']=='completed' for e in events),1)
        self.assertIn(result['deployment_decision'],
                      ('HOLD_FOR_EXTERNAL_REVIEW','REVERT_UNPROMOTED_SOURCE'))
        self.assertFalse(result['candidate_code_deployed'])

    def test_early_stop_when_no_safe_gain(self):
        adapter=SourceAdapter(OperatorAdapter(sizes=(6,4,5),outsiders_per_split=0))
        e=self.engine('stalled',cycles=8,adapter=adapter)
        # A smaller patience is an explicit cost-saving, stop-unproductive gate.
        e=SourceEvolution(self.root/'early',adapter,max_cycles=8,patience=2)
        outcome=e.run()
        self.assertGreaterEqual(outcome['trials'],3)
        self.assertLess(outcome['trials'],8)
        self.assertEqual(outcome['deployment_decision'],'REVERT_UNPROMOTED_SOURCE')
        self.assertEqual(SourceEvolution(self.root/'early',adapter,max_cycles=8,patience=2).run(),outcome)

    def test_positive_heldout_is_still_not_a_deployment(self):
        adapter=SourceAdapter(OperatorAdapter(sizes=(6,4,5),outsiders_per_split=2))
        e=SourceEvolution(self.root/'hold',adapter,max_cycles=8,patience=2)
        outcome=e.run()
        self.assertGreater(outcome['heldout_delta_utility'],0)
        self.assertEqual(outcome['deployment_decision'],'HOLD_FOR_EXTERNAL_REVIEW')
        self.assertFalse(outcome['candidate_code_deployed'])

    def test_cli_is_real_and_resumes_replay(self):
        from contextlib import redirect_stdout
        from io import StringIO
        from .cli import main
        base=str(self.root/'cli')
        def command(*argv):
            buf=StringIO()
            with redirect_stdout(buf):status=main(list(argv))
            return status,json.loads(buf.getvalue())
        opts=('--root',base,'--cycles','2','--patience','2','--outsiders-per-split','0')
        code,paused=command('evolve',*opts,'--stop-after-trials','1')
        self.assertEqual(code,0);self.assertEqual(paused['status'],'PAUSED_CHECKPOINT')
        code,status=command('evolve-status',*opts)
        self.assertEqual(code,0);self.assertEqual(status['trials'],1)
        code,completed=command('evolve',*opts)
        self.assertEqual(code,0)
        self.assertEqual(completed['status'],'COMPLETE_PUBLIC_DEVELOPMENT')
        code,replayed=command('evolve',*opts)
        self.assertEqual(code,0);self.assertEqual(completed,replayed)

    def test_invalid_source_header_fails_in_memory_before_persist(self):
        with self.assertRaises(ResearchIntegrityError):
            SourceEvolution(self.root/'x',self.adapter,max_cycles=True)


if __name__=='__main__':unittest.main()
