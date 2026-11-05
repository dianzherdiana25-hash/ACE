"""ACE red-team tests against the exact stacked PR #25/#27 engine/source code.

Known defects are labelled expectedFailure. An expected failure is evidence of a
*missing* safety property, not a protected behavior. Remove the decorator when
fixing the defect; an unexpected success deliberately makes unittest non-green.
No frozen data, live services, repository HEAD, network, or paid calls are used.
"""
from __future__ import annotations

import ast
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from ace_loop.engine import HashLedger, ResearchIntegrityError, canonical, digest
from ace_loop import source_evolution as evolution
from ace_loop.source_evolution import PROPOSALS, SourceEvolution, score


class RedTeamCase(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)

    def session(self):
        return self.root / 'session'

    def append_valid_trial(self, controller, index):
        controller.ledger.append('trial', {
            'index': index,
            'name': PROPOSALS[index].name,
            'source_sha256': controller.manifest['sources_sha256'][index],
            'train': score(controller.sources[index], controller.bank['train']),
            'validation': score(controller.sources[index], controller.bank['validation']),
        })

    def rewrite_with_valid_hashes(self, path, mutate):
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        mutate(rows)
        previous = '0' * 64
        for row in rows:
            row['prev'] = previous
            row['sha256'] = digest({key: row[key] for key in
                                    ('seq', 'prev', 'kind', 'payload')})
            previous = row['sha256']
        path.write_bytes(b''.join(canonical(row) + b'\n' for row in rows))


class VerifiedSafetyProperties(RedTeamCase):
    def test_checkpoint_resume_matches_clean_and_is_idempotent(self):
        first = SourceEvolution(self.session())
        self.assertEqual(first.run(stop_after=2)['status'], 'PAUSED_CHECKPOINT')
        resumed = SourceEvolution(self.session()).run()
        journal = (self.session() / 'events.jsonl').read_bytes()
        self.assertEqual(SourceEvolution(self.session()).run(), resumed)
        self.assertEqual(journal, (self.session() / 'events.jsonl').read_bytes())
        clean_path = self.root / 'clean'
        self.assertEqual(SourceEvolution(clean_path).run(), resumed)
        self.assertEqual(journal, (clean_path / 'events.jsonl').read_bytes())
        self.assertFalse(resumed['candidate_promoted'])

    def test_crash_after_trial_recovery_records_one_decision(self):
        first = SourceEvolution(self.session())
        self.append_valid_trial(first, 0)
        result = SourceEvolution(self.session()).run()
        events = HashLedger(self.session() / 'events.jsonl').events
        self.assertEqual(result['status'], 'COMPLETE_PUBLIC_SOURCE_DEVELOPMENT')
        self.assertEqual([r['payload']['index'] for r in events if r['kind'] == 'trial'],
                         list(range(len(PROPOSALS))))
        self.assertEqual(len([r for r in events if r['kind'] == 'decision']), len(PROPOSALS))

    def test_rehashed_forged_decision_is_rejected(self):
        SourceEvolution(self.session()).run(stop_after=2)
        path = self.session() / 'events.jsonl'
        def mutate(rows):
            next(row for row in rows if row['kind'] == 'decision')['payload']['champion'] = 4
        self.rewrite_with_valid_hashes(path, mutate)
        with self.assertRaises(ResearchIntegrityError):
            SourceEvolution(self.session())

    def test_rehashed_forged_completion_is_rejected(self):
        SourceEvolution(self.session()).run()
        path = self.session() / 'events.jsonl'
        self.rewrite_with_valid_hashes(path,
            lambda rows: rows[-1]['payload'].__setitem__('scientific_decision', 'GO'))
        with self.assertRaises(ResearchIntegrityError):
            SourceEvolution(self.session())

    def test_staged_tamper_blocks_reopen(self):
        SourceEvolution(self.session()).run()
        (self.session() / 'staged_candidate.py').write_text('def predict(x,y): return 0\n')
        with self.assertRaises(ResearchIntegrityError):
            SourceEvolution(self.session())

    def test_staged_symlink_blocks_reopen(self):
        SourceEvolution(self.session()).run()
        stage = self.session() / 'staged_candidate.py'
        stage.unlink()
        stage.symlink_to(self.root / 'untrusted.py')
        with self.assertRaises(ResearchIntegrityError):
            SourceEvolution(self.session())

    def test_missing_stage_is_recovered_without_extra_event(self):
        out = SourceEvolution(self.session()).run()
        journal = (self.session() / 'events.jsonl').read_bytes()
        (self.session() / 'staged_candidate.py').unlink()
        self.assertEqual(SourceEvolution(self.session()).run(), out)
        self.assertTrue((self.session() / 'staged_candidate.py').is_file())
        self.assertEqual((self.session() / 'events.jsonl').read_bytes(), journal)

    def test_holdout_score_not_requested_before_terminal(self):
        controller = SourceEvolution(self.session())
        holdout_cases = controller.bank['holdout']
        actual_score = evolution.score
        used_splits = []
        def trace(src, cases):
            used_splits.append(cases)
            return actual_score(src, cases)
        with patch.object(evolution, 'score', side_effect=trace):
            self.assertEqual(controller.run(stop_after=2)['status'], 'PAUSED_CHECKPOINT')
        self.assertFalse(any(cases is holdout_cases for cases in used_splits))

    def test_two_stale_journal_snapshots_cannot_append(self):
        path = self.root / 'journal.jsonl'
        left, right = HashLedger(path), HashLedger(path)
        left.append('receipt', {'trial': 1})
        with self.assertRaises(ResearchIntegrityError):
            right.append('receipt', {'trial': 2})
        self.assertEqual(len(HashLedger(path).events), 1)

    def test_truncated_event_halts_without_silent_repair(self):
        controller = SourceEvolution(self.session())
        controller.run(stop_after=1)
        with (self.session() / 'events.jsonl').open('ab') as f:
            f.write(b'{"seq":')
        with self.assertRaises(ResearchIntegrityError):
            SourceEvolution(self.session())

    def test_reject_source_with_effects(self):
        for payload in ('__import__("os")', 'open("/tmp/x")', 'x.__class__', 'x**y'):
            with self.subTest(payload=payload), self.assertRaises(ResearchIntegrityError):
                evolution.source_for(payload)


class KnownSafetyGaps(RedTeamCase):
    @unittest.expectedFailure
    def test_rt01_ledger_path_swap_after_lock_must_not_ack_lost_receipt(self):
        """RT-01: inode lock does not protect a replaced journal pathname."""
        path = self.root / 'events.jsonl'
        archive = self.root / 'old_inode.jsonl'
        journal = HashLedger(path)
        journal.append('seed', {'n': 0})
        native_read = journal._read
        def rotate_after_check():
            live = native_read()
            os.replace(path, archive)
            path.write_bytes(archive.read_bytes())
            return live
        with patch.object(journal, '_read', side_effect=rotate_after_check):
            journal.append('acknowledged', {'n': 1})
        # Currently FALSE: append returned success but the active pathname lost it.
        self.assertEqual(len(HashLedger(path).events), 2)

    @unittest.expectedFailure
    def test_rt02_replay_must_reject_two_unpaired_trials(self):
        """RT-02: valid SHA chain with two trials and zero decisions passes replay."""
        controller = SourceEvolution(self.session())
        self.append_valid_trial(controller, 0)
        self.append_valid_trial(controller, 1)
        with self.assertRaises(ResearchIntegrityError):
            SourceEvolution(self.session())

    @unittest.expectedFailure
    def test_rt03_ancestor_symlink_must_not_redirect_run_root(self):
        """RT-03: only immediate parent/root symlinks are screened."""
        actual = self.root / 'actual'
        actual.mkdir()
        alias = self.root / 'alias'
        alias.symlink_to(actual, target_is_directory=True)
        hidden_root = alias / 'nested' / 'session'
        with self.assertRaises(ResearchIntegrityError):
            SourceEvolution(hidden_root)

    @unittest.expectedFailure
    def test_rt04_mutated_holdout_bank_must_halt_before_terminal_receipt(self):
        """RT-04: a mutable in-process evaluator bank bypasses its init digest."""
        controller = SourceEvolution(self.session())
        x, y, truth = controller.bank['holdout'][0]
        controller.bank['holdout'][0] = (x, y, truth + 1000)
        with self.assertRaises(ResearchIntegrityError):
            controller.run()

    @unittest.expectedFailure
    def test_rt05_interpreter_must_reject_unvalidated_operation(self):
        """RT-05: direct interpret() treats any unknown binary op as multiply."""
        invalid = ast.BinOp(left=ast.Constant(value=2), op=ast.Pow(),
                            right=ast.Constant(value=3))
        with self.assertRaises(ResearchIntegrityError):
            evolution.interpret(invalid, 1, 1)


if __name__ == '__main__':
    unittest.main()
