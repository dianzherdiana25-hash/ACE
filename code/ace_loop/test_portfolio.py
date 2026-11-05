import json
from pathlib import Path
import tempfile
import unittest
from .portfolio import run_portfolio
from .engine import ResearchIntegrityError

class PortfolioTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'portfolio'

    def test_pilot_reallocates_to_productive_track(self):
        r=run_portfolio(self.root,pilot_trials=8,total_trials=12)
        self.assertEqual(r['allocation']['selected'],'in_family')
        self.assertGreater(r['allocation']['gains']['in_family'],r['allocation']['gains']['mixed_grammar'])
        self.assertFalse(r['allocation']['holdout_used_for_allocation'])
        self.assertEqual(r['selected_result']['status'],'COMPLETE_PUBLIC_DEVELOPMENT')
        self.assertEqual(r['suspended_tracks'],['mixed_grammar'])

    def test_replay_keeps_suspended_track_unmodified(self):
        a=run_portfolio(self.root,pilot_trials=8,total_trials=12)
        protected=(self.root/'mixed_grammar'/'events.jsonl').read_bytes()
        allocated=(self.root/'allocation.json').read_bytes()
        b=run_portfolio(self.root,pilot_trials=8,total_trials=12)
        self.assertEqual(a,b)
        self.assertEqual((self.root/'mixed_grammar'/'events.jsonl').read_bytes(),protected)
        self.assertEqual((self.root/'allocation.json').read_bytes(),allocated)

    def test_tampered_allocation_rejected(self):
        run_portfolio(self.root,pilot_trials=8,total_trials=12)
        file=self.root/'allocation.json';row=json.loads(file.read_text());row['allocation']['selected']='mixed_grammar'
        file.write_text(json.dumps(row))
        with self.assertRaises(ResearchIntegrityError):run_portfolio(self.root,pilot_trials=8,total_trials=12)

if __name__=='__main__':unittest.main()

class CliIntegration(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)

    def test_run_pause_status_resume(self):
        from io import StringIO
        from contextlib import redirect_stdout
        from .cli import main
        path=str(self.root/'single')
        def call(*args):
            buffer=StringIO()
            with redirect_stdout(buffer):code=main(list(args))
            return code,json.loads(buffer.getvalue())
        self.assertEqual(call('run','--root',path,'--cycles','3','--patience','3',
                              '--stop-after-trials','1')[1]['status'],'PAUSED_CHECKPOINT')
        self.assertEqual(call('status','--root',path,'--cycles','3','--patience','3')[1]['trials'],1)
        self.assertEqual(call('run','--root',path,'--cycles','3','--patience','3')[1]['status'],'COMPLETE_PUBLIC_DEVELOPMENT')

    def test_config_change_visible_halt(self):
        from io import StringIO
        from contextlib import redirect_stdout
        from .cli import main
        path=str(self.root/'single');capture=StringIO()
        with redirect_stdout(capture):main(['run','--root',path,'--cycles','3'])
        capture=StringIO()
        with redirect_stdout(capture):code=main(['status','--root',path,'--cycles','4'])
        self.assertEqual(code,2)
        self.assertIn('HALT_INTEGRITY_ERROR',capture.getvalue())
