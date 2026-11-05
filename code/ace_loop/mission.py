"""One-command, crash-safe E1.5 + E1.6 research mission orchestration.

The mission performs both public synthetic development tracks in one invocation,
keeps their distinct ledgers, and persists its own verified stage boundaries.
No live backend, untrusted arbitrary execution, merge, deployment or background
agent is permitted. A pending remote escrow remains an explicit external gate.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from .engine import HashLedger, ResearchIntegrityError, digest
from .operators import OperatorAdapter
from .portfolio import run_portfolio
from .source_evolution import SourceAdapter, SourceEvolution


def _sha(path):
    p=Path(path)
    if p.is_symlink() or not p.is_file():
        raise ResearchIntegrityError('missing or symlinked mission evidence')
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _int(v,lo,hi,name):
    if type(v) is not int or not lo<=v<=hi:
        raise ResearchIntegrityError('invalid mission '+name)


class AceMission:
    def __init__(self,root,*,policy_pilot=8,policy_trials=12,
                 source_trials=8,source_patience=5,outsiders_per_split=2):
        _int(policy_pilot,1,11,'pilot count')
        _int(policy_trials,2,12,'policy trials')
        if policy_pilot>=policy_trials:raise ResearchIntegrityError('pilot must be smaller than total')
        _int(source_trials,1,16,'source trials')
        _int(source_patience,1,16,'source patience')
        _int(outsiders_per_split,0,2,'unknown operators')
        self.root=Path(root)
        if self.root.is_symlink():raise ResearchIntegrityError('mission root symlink')
        self.root.mkdir(parents=True,exist_ok=True)
        self.params={'policy_pilot':policy_pilot,'policy_trials':policy_trials,
                     'source_trials':source_trials,'source_patience':source_patience,
                     'outsiders_per_split':outsiders_per_split}
        self.policy_path=self.root/'policy'
        self.source_path=self.root/'source'
        if self.policy_path.is_symlink() or self.source_path.is_symlink():
            raise ResearchIntegrityError('mission stage root symlink')
        self.manifest={'schema':1,'purpose':'BOUNDED_MULTI_TRACK_RESEARCH_MISSION',
                       'params':self.params,
                       'security':'no external actions; native isolation not certified',
                       'promotion':'forbidden pending separate evidence and approval',
                       'backend':'PUBLIC_SYNTHETIC_ONLY'}
        self.ledger=HashLedger(self.root/'mission.jsonl')
        if not self.ledger.events:
            self.ledger.append('config',{'manifest':self.manifest,'digest':digest(self.manifest)})
        self._verify()

    def _policy(self):
        p=self.params
        result=run_portfolio(self.policy_path,pilot_trials=p['policy_pilot'],
                             total_trials=p['policy_trials'])
        allocation_sha=_sha(self.policy_path/'allocation.json')
        return {'result':result,'allocation_sha256':allocation_sha,
                'public_label_type':'simulated_logical_not_external_purchase'}

    def _source(self):
        p=self.params
        adapter=SourceAdapter(OperatorAdapter(outsiders_per_split=p['outsiders_per_split']))
        engine=SourceEvolution(self.source_path,adapter,max_cycles=p['source_trials'],
                               patience=p['source_patience'])
        result=engine.run()
        if result['status']!='COMPLETE_PUBLIC_DEVELOPMENT':
            raise ResearchIntegrityError('source research not complete')
        return {'result':result,'journal_sha256':_sha(self.source_path/'events.jsonl'),
                'public_label_type':'simulated_logical_not_external_purchase'}

    def _finish(self,policy,source):
        selected=policy['result']['selected_result']
        candidate=source['result']
        return {'status':'COMPLETE_BOUNDED_RESEARCH_MISSION',
                'scientific_decision':'NOT_ASSESSED',
                'policy_selected_track':policy['result']['allocation']['selected'],
                'policy_suspended_tracks':policy['result']['suspended_tracks'],
                'policy_heldout_delta':selected['holdout_delta_utility'] if selected else None,
                'source_trials':candidate['trials'],
                'source_heldout_delta':candidate['heldout_delta_utility'],
                'source_deployment_decision':candidate['deployment_decision'],
                'candidate_code_deployed':False,
                'external_purchase_count':0,
                'evidence_sha256':digest({'policy':policy,'source':source}),
                'next_gate':'clean full checkout, native isolation, authentic external receipt custody',
                'oaie_achieved':False}

    def _verify(self):
        events=self.ledger.events
        if not events or events[0]['kind']!='config' or events[0]['payload']!={'manifest':self.manifest,'digest':digest(self.manifest)}:
            raise ResearchIntegrityError('mission configuration changed')
        if len(events)>4:raise ResearchIntegrityError('mission event overflow')
        expected=('config','policy','source','completed')
        if any(e['kind']!=expected[i] for i,e in enumerate(events)):
            raise ResearchIntegrityError('mission event order invalid')
        policy=source=None
        if len(events)>=2:
            if not (self.policy_path/'allocation.json').is_file() or (self.policy_path/'allocation.json').is_symlink():
                raise ResearchIntegrityError('persisted policy checkpoint missing; do not recreate')
            policy=self._policy()
            if events[1]['payload']!=policy:
                raise ResearchIntegrityError('mission policy evidence mismatch')
        if len(events)>=3:
            if not (self.source_path/'events.jsonl').is_file() or (self.source_path/'events.jsonl').is_symlink():
                raise ResearchIntegrityError('persisted source checkpoint missing; do not recreate')
            source=self._source()
            if events[2]['payload']!=source:
                raise ResearchIntegrityError('mission source evidence mismatch')
        if len(events)==4 and events[3]['payload']!=self._finish(policy,source):
            raise ResearchIntegrityError('mission conclusion forged')

    def run(self,*,stop_after_policy=False):
        if type(stop_after_policy) is not bool:
            raise ResearchIntegrityError('invalid policy stop switch')
        self._verify()
        events=self.ledger.events
        if len(events)==4:return events[-1]['payload']
        if len(events)==1:
            self.ledger.append('policy',self._policy())
        if stop_after_policy:
            return {'status':'PAUSED_POLICY_CHECKPOINT',
                    'mission_head':self.ledger.events[-1]['sha256'],
                    'policy_saved':True,'external_purchase_count':0}
        if len(self.ledger.events)==2:
            self.ledger.append('source',self._source())
        policy=self.ledger.events[1]['payload'];source=self.ledger.events[2]['payload']
        result=self._finish(policy,source)
        self.ledger.append('completed',result)
        return result
