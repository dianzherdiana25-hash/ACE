"""One-entrypoint integration, recovery and fail-closed tests for ACE mission."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from contextlib import redirect_stdout
from io import StringIO
import json
import unittest

from .mission import AceMission
from .engine import ResearchIntegrityError, canonical, digest


class MissionTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'mission'
        self.opts={'policy_pilot':2,'policy_trials':4,'source_trials':3,
                   'source_patience':3,'outsiders_per_split':0}

    def new(self,**changes):return AceMission(self.root,**dict(self.opts,**changes))

    def test_one_command_completes_two_tracks_with_no_external_side_effect(self):
        m=self.new();r=m.run()
        self.assertEqual(r['status'],'COMPLETE_BOUNDED_RESEARCH_MISSION')
        self.assertFalse(r['candidate_code_deployed'])
        self.assertEqual(r['external_purchase_count'],0)
        self.assertFalse(r['oaie_achieved'])
        self.assertEqual([e['kind'] for e in m.ledger.events],
                         ['config','policy','source','completed'])
        self.assertTrue((self.root/'policy'/'allocation.json').is_file())
        self.assertTrue((self.root/'source'/'events.jsonl').is_file())
        self.assertEqual(len(list((self.root/'source'/'proposals').glob('*.py'))),r['source_trials'])

    def test_pause_then_resume_byte_identical(self):
        a=self.new()
        paused=a.run(stop_after_policy=True)
        self.assertEqual(paused['status'],'PAUSED_POLICY_CHECKPOINT')
        self.assertEqual([x['kind'] for x in a.ledger.events],['config','policy'])
        policy_bytes=(self.root/'policy'/'allocation.json').read_bytes()
        result=self.new().run()
        self.assertEqual((self.root/'policy'/'allocation.json').read_bytes(),policy_bytes)
        frozen=(self.root/'mission.jsonl').read_bytes()
        self.assertEqual(self.new().run(),result)
        self.assertEqual((self.root/'mission.jsonl').read_bytes(),frozen)

    def test_missing_policy_checkpoint_halts_without_rebuilding(self):
        self.new().run(stop_after_policy=True)
        target=self.root/'policy'/'allocation.json';target.unlink()
        with self.assertRaisesRegex(ResearchIntegrityError,'persisted policy checkpoint missing'):
            self.new()
        self.assertFalse(target.exists())

    def test_missing_source_checkpoint_halts_without_rebuilding(self):
        self.new().run()
        target=self.root/'source'/'events.jsonl';target.unlink()
        with self.assertRaisesRegex(ResearchIntegrityError,'persisted source checkpoint missing'):
            self.new()
        self.assertFalse(target.exists())

    def test_mission_config_difference_fails_closed(self):
        self.new().run(stop_after_policy=True)
        with self.assertRaisesRegex(ResearchIntegrityError,'mission configuration changed'):
            self.new(source_trials=4)

    def test_tampered_conclusion_even_with_rehashed_chain_rejected(self):
        self.new().run()
        target=self.root/'mission.jsonl'
        rows=[json.loads(x) for x in target.read_text().splitlines()]
        rows[-1]['payload']['candidate_code_deployed']=True
        prev='0'*64
        for row in rows:
            row['prev']=prev
            row['sha256']=digest({k:row[k] for k in ('seq','prev','kind','payload')})
            prev=row['sha256']
        target.write_bytes(b''.join(canonical(x)+b'\n' for x in rows))
        with self.assertRaisesRegex(ResearchIntegrityError,'conclusion forged'):
            self.new()

    def test_symlink_stage_directory_forbidden(self):
        self.root.mkdir(parents=True,exist_ok=True)
        (self.root/'policy').symlink_to(Path(self.temp.name))
        with self.assertRaisesRegex(ResearchIntegrityError,'stage root symlink'):
            self.new()

    def test_cli_mission_and_status(self):
        from .cli import main
        opts=('--root',str(self.root),'--pilot-trials','2','--cycles','4',
              '--source-cycles','3','--source-patience','3','--outsiders-per-split','0')
        def call(*args):
            buf=StringIO()
            with redirect_stdout(buf):rc=main(list(args))
            return rc,json.loads(buf.getvalue())
        rc,paused=call('mission',*opts,'--stop-after-policy')
        self.assertEqual(rc,0);self.assertEqual(paused['status'],'PAUSED_POLICY_CHECKPOINT')
        rc,state=call('mission-status',*opts)
        self.assertEqual(rc,0);self.assertFalse(state['complete'])
        rc,result=call('mission',*opts)
        self.assertEqual(rc,0);self.assertEqual(result['status'],'COMPLETE_BOUNDED_RESEARCH_MISSION')
        rc,state=call('mission-status',*opts)
        self.assertEqual(rc,0);self.assertTrue(state['complete'])


if __name__=='__main__':unittest.main()
