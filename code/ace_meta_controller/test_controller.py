"""Unit and adversarial tests for deterministic, bounded meta-controller."""
import fcntl
import json
from pathlib import Path
import tempfile
import unittest

from .controller import (Controller, IntegrityError, SimulatedInterruption,
                         canonical, choose, decide, digest, evaluate, initial_state,
                         PROBLEMS)


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)/'run'

    def rows(self):
        return [json.loads(v) for v in (self.root/'events.jsonl').read_text().splitlines()]

    def test_end_to_end_budget_and_gains(self):
        result = Controller(self.root).run()
        self.assertEqual(result['status'], 'COMPLETE_PUBLIC_SYNTHETIC')
        self.assertEqual(result['scientific_decision'], 'NOT_ASSESSED')
        self.assertFalse(result['candidate_promoted'])
        self.assertLessEqual(result['spent_units'], result['budget_units'])
        self.assertGreater(result['problems']['affine_shift']['holdout_error_reduction'], 0)
        self.assertTrue(result['problems']['unproductive_track']['stopped_unproductive'])
        self.assertEqual(result['problems']['unproductive_track']['selected_coefficients'], [1, 1])
        self.assertEqual(sum(r['kind'] == 'trial' for r in self.rows()),
                         sum(x['trials'] for x in result['problems'].values()))

    def test_idempotent_terminal(self):
        expected = Controller(self.root).run()
        before = (self.root/'events.jsonl').read_bytes()
        self.assertEqual(Controller(self.root).run(), expected)
        self.assertEqual((self.root/'events.jsonl').read_bytes(), before)

    def test_pause_resume_byte_identical(self):
        pause = Controller(self.root).run(stop_after_trials=3)
        self.assertEqual(pause['status'], 'PAUSED_CHECKPOINT')
        Controller(self.root).run()
        journal = (self.root/'events.jsonl').read_bytes()
        with tempfile.TemporaryDirectory() as other:
            Controller(Path(other)/'clean').run()
            self.assertEqual(journal, (Path(other)/'clean'/'events.jsonl').read_bytes())

    def test_crash_between_trial_and_decision(self):
        with self.assertRaises(SimulatedInterruption):
            Controller(self.root).run(simulate_crash_after_trial=True)
        self.assertEqual(self.rows()[-1]['kind'], 'trial')
        Controller(self.root).run()
        with tempfile.TemporaryDirectory() as other:
            Controller(Path(other)/'clean').run()
            self.assertEqual((self.root/'events.jsonl').read_bytes(),
                             (Path(other)/'clean'/'events.jsonl').read_bytes())

    def test_terminal_holdout_only(self):
        Controller(self.root).run(stop_after_trials=1)
        rows = self.rows()
        self.assertEqual([r['kind'] for r in rows], ['config', 'trial', 'decision'])
        self.assertNotIn('holdout_baseline', str(rows[1:]))
        Controller(self.root).run()
        self.assertEqual(self.rows()[-1]['kind'], 'complete')
        self.assertIn('holdout_selected', str(self.rows()[-1]['payload']))

    def test_budget_two(self):
        result = Controller(self.root, budget=2).run()
        self.assertEqual(result['spent_units'], 2)
        self.assertEqual(sum(p['trials'] for p in result['problems'].values()), 1)

    def test_reject_budget_bool_odd_or_unbounded(self):
        for value in (True, 3, -2, 0, 102, 2.0):
            with self.subTest(value=value), self.assertRaises(IntegrityError):
                Controller(self.root, budget=value)

    def test_truncated_journal_fails(self):
        Controller(self.root).run(stop_after_trials=1)
        with (self.root/'events.jsonl').open('ab') as f:
            f.write(b'{"partial":')
        with self.assertRaises(IntegrityError): Controller(self.root).run()

    def test_rehashed_forged_decision_fails(self):
        Controller(self.root).run(stop_after_trials=1)
        rows = self.rows()
        rows[2]['payload']['adopted'] = not rows[2]['payload']['adopted']
        for i, row in enumerate(rows):
            row['prev'] = rows[i-1]['sha256'] if i else '0'*64
            row['sha256'] = digest({k: row[k] for k in ('seq', 'prev', 'kind', 'payload')})
        (self.root/'events.jsonl').write_bytes(b''.join(canonical(row) for row in rows))
        with self.assertRaises(IntegrityError): Controller(self.root).run()

    def test_forged_selection_schedule_fails(self):
        Controller(self.root).run(stop_after_trials=1)
        rows = self.rows()
        rows[1]['payload']['problem'] = 'unproductive_track'
        for i, row in enumerate(rows):
            row['prev'] = rows[i-1]['sha256'] if i else '0'*64
            row['sha256'] = digest({k: row[k] for k in ('seq','prev','kind','payload')})
        (self.root/'events.jsonl').write_bytes(b''.join(canonical(row) for row in rows))
        with self.assertRaises(IntegrityError): Controller(self.root).run()

    def test_changed_manifest_budget_fails(self):
        Controller(self.root, budget=16).run(stop_after_trials=1)
        with self.assertRaises(IntegrityError): Controller(self.root, budget=14).run()

    def test_checkpoint_corrupted_fails(self):
        Controller(self.root).run(stop_after_trials=1)
        path = self.root/'checkpoint.json'
        obj = json.loads(path.read_text())
        obj['state_sha256'] = 'a'*64
        path.write_bytes(canonical(obj))
        with self.assertRaises(IntegrityError): Controller(self.root).run()

    def test_missing_checkpoint_rebuilds(self):
        Controller(self.root).run(stop_after_trials=1)
        (self.root/'checkpoint.json').unlink()
        result = Controller(self.root).run()
        self.assertEqual(result['status'], 'COMPLETE_PUBLIC_SYNTHETIC')
        self.assertTrue((self.root/'checkpoint.json').exists())

    def test_symlink_journal_fails(self):
        self.root.mkdir(parents=True)
        external = self.root.parent/'outside'
        external.write_text('sentinel')
        (self.root/'events.jsonl').symlink_to(external)
        with self.assertRaises(IntegrityError): Controller(self.root).run()
        self.assertEqual(external.read_text(), 'sentinel')

    def test_locked_controller_fails_visible(self):
        self.root.mkdir(parents=True)
        with (self.root/'.lock').open('wb') as f:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaises(IntegrityError): Controller(self.root).run()

    def test_invalid_evaluator_input(self):
        with self.assertRaises(IntegrityError): evaluate(PROBLEMS[0], (True, 1), 'validation')
        with self.assertRaises(IntegrityError): evaluate(PROBLEMS[0], (1, 1), 'secret')

    def test_priority_pilot_and_no_holdout_selection(self):
        state = initial_state()
        self.assertEqual(choose(state, 16).key, 'affine_shift')
        t = Controller(self.root)._trial(PROBLEMS[0], state)
        d = decide(state, t)
        self.assertNotIn('holdout', t)
        self.assertNotIn('holdout', d)

    def test_no_extra_events_after_completion(self):
        Controller(self.root).run()
        path = self.root/'events.jsonl'
        rows = self.rows()
        entry = {'seq':len(rows),'prev':rows[-1]['sha256'],'kind':'complete','payload':rows[-1]['payload']}
        entry['sha256'] = digest(entry)
        with path.open('ab') as f: f.write(canonical(entry))
        with self.assertRaises(IntegrityError): Controller(self.root).run()


if __name__ == '__main__':
    unittest.main()
