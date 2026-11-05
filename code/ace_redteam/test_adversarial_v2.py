"""Second independent adversarial pass on PR #25/#27.

Expected failures expose missing safety properties and must not be read as PASS.
All mutations happen in temporary directories; candidate code is not executed.
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

from ace_loop import engine as engine_module
from ace_loop.engine import HashLedger, ResearchEngine, ResearchIntegrityError
from ace_loop.source_evolution import SourceEvolution, parse_source


class TinyDeterministicAdapter:
    """Standalone evaluator contract with no dependency on frozen E1.4."""
    def __init__(self):
        self.holdout_calls = 0

    def bank_manifest(self):
        return {'synthetic': 'redteam-public-no-secrets', 'version': 1}

    def evaluate(self, policy, split):
        if split == 'test':
            self.holdout_calls += 1
        return {'worlds': 1, 'accepted_correct': 0, 'accepted_wrong': 0,
                'abstained': 1, 'logical_labels': 1, 'probe_errors': 0,
                'utility_units': -3}


class SecondPass(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    @unittest.expectedFailure
    def test_rt06_same_object_thread_race_must_not_corrupt_journal(self):
        """P1: shared snapshot is updated after unlock; stale event may be written."""
        journal_path = self.root / 'events.jsonl'
        journal = HashLedger(journal_path)
        journal.append('seed', {'n': 0})
        second_ready, allow_second_open = threading.Event(), threading.Event()
        returned, raised = [], []
        original_open = os.open

        def synchronized_open(*args, **kwargs):
            # B computed its seq/prev/digest before entering os.open.
            if threading.current_thread().name == 'REDTEAM_B' and Path(args[0]) == journal_path:
                second_ready.set()
                if not allow_second_open.wait(5):
                    raise RuntimeError('redteam synchronization timeout')
            return original_open(*args, **kwargs)

        def second_append():
            try:
                returned.append(journal.append('thread-b', {'n': 2}))
            except Exception as exc:
                raised.append(exc)

        with patch.object(engine_module.os, 'open', side_effect=synchronized_open):
            worker = threading.Thread(target=second_append, name='REDTEAM_B', daemon=True)
            worker.start()
            try:
                self.assertTrue(second_ready.wait(5), 'thread did not reach instrumented write')
                journal.append('thread-a', {'n': 1})
            finally:
                allow_second_open.set()
                worker.join(timeout=5)

        self.assertFalse(worker.is_alive(), 'worker stalled')
        # Desired: stale B is rejected and the original journal remains valid.
        self.assertEqual(len(returned), 0)
        self.assertEqual(len(raised), 1)
        self.assertIsInstance(raised[0], ResearchIntegrityError)
        self.assertEqual(len(HashLedger(journal_path).events), 2)

    @unittest.expectedFailure
    def test_rt07_valid_prefix_rollback_must_not_repeat_holdout(self):
        """P1: dropping terminal event permits silent re-evaluation."""
        adapter = TinyDeterministicAdapter()
        journal_root = self.root / 'run'
        original = ResearchEngine(journal_root, adapter, max_cycles=1, patience=1).run()
        path = journal_root / 'events.jsonl'
        completed_journal = path.read_bytes()
        self.assertEqual(adapter.holdout_calls, 2)
        self.assertEqual(original['status'], 'COMPLETE_PUBLIC_DEVELOPMENT')
        # The remaining journal is a byte-for-byte valid digest chain prefix.
        path.write_bytes(b''.join(completed_journal.splitlines(keepends=True)[:-1]))
        resumed = ResearchEngine(journal_root, adapter, max_cycles=1, patience=1).run()
        self.assertEqual(resumed, original)
        self.assertEqual(path.read_bytes(), completed_journal)
        # Desired: terminal rollback must be detected before repeat holdout reads.
        self.assertEqual(adapter.holdout_calls, 2)

    @unittest.expectedFailure
    @unittest.skipUnless(hasattr(os, 'mkfifo') and os.name == 'posix', 'FIFO needs POSIX')
    def test_rt08_staged_fifo_must_reject_without_hanging(self):
        """P2: attacker-provided FIFO stalls Path.read_bytes on source reopen."""
        root = self.root / 'source'
        SourceEvolution(root).run()
        staged = root / 'staged_candidate.py'
        staged.unlink()
        os.mkfifo(staged)
        code = ('from pathlib import Path\n'
                'from ace_loop.source_evolution import SourceEvolution\n'
                'SourceEvolution(Path(__import__("sys").argv[1]))\n')
        package_root = str(Path(engine_module.__file__).resolve().parents[1])
        env = dict(os.environ)
        env['PYTHONPATH'] = os.pathsep.join([package_root, env.get('PYTHONPATH', '')])
        timed_out = False
        try:
            process = subprocess.run([sys.executable, '-c', code, str(root)],
                                     capture_output=True, text=True, env=env, timeout=2)
        except subprocess.TimeoutExpired:
            timed_out = True
            process = None
        self.assertFalse(timed_out, 'reader hung on attacker-supplied FIFO')
        self.assertIsNotNone(process)
        self.assertNotEqual(process.returncode, 0, 'nonregular staging file accepted')

    @unittest.expectedFailure
    def test_rt09_generic_type_params_must_be_rejected_by_parser(self):
        """P3: Python 3.13 FunctionDef.type_params is not checked."""
        source = 'def predict[T](x, y):\n    return x + y\n'
        with self.assertRaises(ResearchIntegrityError):
            parse_source(source)

    def test_partial_journal_write_is_detected_and_never_auto_repaired(self):
        """Positive control: incomplete writes halt and preserve evidence."""
        target = self.root / 'journal.jsonl'
        journal = HashLedger(target)
        journal.append('begin', {'ok': True})
        original_write = os.write

        def short_write(fd, data):
            original_write(fd, data[:3])
            return 3

        with patch.object(engine_module.os, 'write', side_effect=short_write):
            with self.assertRaisesRegex(ResearchIntegrityError, 'partial journal write'):
                journal.append('incomplete', {'n': 1})
        with self.assertRaisesRegex(ResearchIntegrityError, 'truncated event'):
            HashLedger(target)

    def test_zero_trial_pause_preserves_journal_and_does_not_stage(self):
        """Positive control: no-op pause remains recoverable."""
        root = self.root / 'source'
        controller = SourceEvolution(root)
        state = controller.run(stop_after=0)
        self.assertEqual(state['status'], 'PAUSED_CHECKPOINT')
        self.assertEqual(state['trials'], 0)
        self.assertEqual(len(controller.ledger.events), 1)
        self.assertFalse((root / 'staged_candidate.py').exists())
        self.assertEqual(SourceEvolution(root).run()['scientific_decision'], 'NOT_ASSESSED')


if __name__ == '__main__':
    unittest.main()
