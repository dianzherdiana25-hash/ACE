"""Crash-safe, audit-first bounded research orchestration (stdlib only).

Research actions are deterministic PURE local simulations. This ledger does not
claim exactly-once remote oracle calls: plug-in external actions must implement
receipt escrow and verified reconciliation before using this engine. No eval,
exec, network, arbitrary subprocess, or source rewriting is performed here.

The runner proposes a finite policy, tests it on development tasks, validates a
candidate on a second disjoint task set, adopts/rejects with a predeclared
utility and saves an append-only hash chain. The untouched test set is opened
only after the final decision. Every stopped hypothesis, failure and cost is
persisted, including on resumed runs.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
import hashlib
import json
import os
import fcntl


class ResearchIntegrityError(RuntimeError):
    pass


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False, allow_nan=False).encode('utf-8')


def digest(obj):
    return hashlib.sha256(canonical(obj)).hexdigest()


def _int(n, start, end, name):
    if type(n) is not int or not start <= n <= end:
        raise ResearchIntegrityError('invalid ' + name)


@dataclass(frozen=True)
class Policy:
    selector: str
    label_cap: int
    min_evidence: int

    def __post_init__(self):
        if type(self.selector) is not str or self.selector not in ('fixed','active','random'):
            raise ResearchIntegrityError('invalid selector')
        _int(self.label_cap,1,4,'label cap')
        _int(self.min_evidence,1,4,'minimum evidence')
        if self.min_evidence > self.label_cap:
            raise ResearchIntegrityError('unreachable evidence threshold')

    def json(self):
        return {'selector':self.selector,'label_cap':self.label_cap,
                'min_evidence':self.min_evidence}


def _metrics(results):
    if not results:
        raise ResearchIntegrityError('empty experiment')
    m={'worlds':len(results),'accepted_correct':0,'accepted_wrong':0,
       'abstained':0,'logical_labels':0,'probe_errors':0}
    for r in results:
        for k in ('accepted_correct','accepted_wrong','abstained','logical_labels','probe_errors'):
            _int(r[k],0,100000,k)
            m[k]+=r[k]
        if r['accepted_correct']+r['accepted_wrong']+r['abstained']!=1:
            raise ResearchIntegrityError('invalid disjoint outcome')
    # Integer utility, with explicitly declared penalty for wrong acceptance.
    m['utility_units']=(20*m['accepted_correct']-40*m['accepted_wrong']
                        -2*m['abstained']-m['logical_labels'])
    return m


class HashLedger:
    """Append-only fsync JSONL; an interrupted/forged line is never discarded."""
    def __init__(self,path:Path):
        self.path=Path(path)
        if self.path.is_symlink() or self.path.parent.is_symlink():
            raise ResearchIntegrityError('symlink journal path forbidden')
        self.path.parent.mkdir(parents=True,exist_ok=True)
        self.events=self._read()

    def _read(self):
        if not self.path.exists(): return []
        rows=[];prev='0'*64
        with self.path.open('rb') as source:
            for raw in source:
                if not raw.endswith(b'\n'):
                    raise ResearchIntegrityError('truncated event: stop without repair')
                try: row=json.loads(raw)
                except (ValueError,UnicodeError) as exc:
                    raise ResearchIntegrityError('invalid event encoding') from exc
                if type(row) is not dict or set(row)!={'seq','prev','kind','payload','sha256'}:
                    raise ResearchIntegrityError('invalid event schema')
                if type(row['seq']) is not int or row['seq']!=len(rows):
                    raise ResearchIntegrityError('event order conflict')
                if type(row['prev']) is not str or row['prev']!=prev:
                    raise ResearchIntegrityError('event chain fork')
                expect=digest({k:row[k] for k in ('seq','prev','kind','payload')})
                if type(row['sha256']) is not str or expect!=row['sha256']:
                    raise ResearchIntegrityError('event digest mismatch')
                if canonical(row)+b'\n'!=raw:
                    raise ResearchIntegrityError('noncanonical event row')
                rows.append(row);prev=expect
        return rows

    def append(self,kind,payload):
        if type(kind) is not str or type(payload) is not dict:
            raise ResearchIntegrityError('invalid event kind/payload')
        row={'seq':len(self.events),'prev':self.events[-1]['sha256'] if self.events else '0'*64,
             'kind':kind,'payload':payload}
        row['sha256']=digest(row)
        data=canonical(row)+b'\n'
        flags=os.O_WRONLY|os.O_CREAT|os.O_APPEND
        if hasattr(os,'O_NOFOLLOW'):flags |= os.O_NOFOLLOW
        fd=os.open(self.path,flags,0o600)
        try:
            fcntl.flock(fd,fcntl.LOCK_EX)
            # Another process may have appended since our local snapshot.
            # Never append a fork or duplicate paid/evaluation event.
            live=self._read()
            if live!=self.events:
                raise ResearchIntegrityError('concurrent journal modification')
            if os.write(fd,data)!=len(data):
                raise ResearchIntegrityError('partial journal write; stop')
            os.fsync(fd)
        finally:
            fcntl.flock(fd,fcntl.LOCK_UN)
            os.close(fd)
        self.events.append(row)
        return row


class ResearchEngine:
    """Deterministic multi-cycle bounded search with resume and one-shot holdout.

    adapter: object with `bank_manifest()`, `task_ids(split)`, `evaluate(policy,split)`.
    Evaluations MUST be read-only, deterministic, local; no external tools.
    """
    def __init__(self,root,adapter,*,max_cycles=12,patience=5):
        _int(max_cycles,1,100,'cycle cap');_int(patience,1,100,'patience')
        self.root=Path(root)
        if self.root.is_symlink():raise ResearchIntegrityError('symlink run root forbidden')
        self.root.mkdir(parents=True,exist_ok=True)
        self.adapter=adapter;self.max_cycles=max_cycles;self.patience=patience
        self.ledger=HashLedger(self.root/'events.jsonl')
        self.manifest={'schema':1,'purpose':'PUBLIC_DEVELOPMENT_FINITE_POLICY_SEARCH',
            'bank':adapter.bank_manifest(),'max_cycles':max_cycles,'patience':patience,
            'seed_policy':Policy('fixed',1,1).json(),
            'utility':'20 correct - 40 wrong - 2 abstain - 1 per label',
            'holdout':'one final evaluation only; never used to choose candidate',
            'external_oracle':'FORBIDDEN_IN_THIS_RUNNER'}
        if not self.ledger.events:
            self.ledger.append('run_config',{'manifest':self.manifest,'sha256':digest(self.manifest)})
        self._verify_history()

    @staticmethod
    def proposals():
        # Fixed public finite policy set. These are not invented architectures.
        return tuple(Policy(selector,cap,checks) for selector,cap,checks in (
            ('active',1,1),('fixed',2,1),('active',2,1),
            ('active',3,1),('fixed',3,1),('random',3,1),
            ('active',4,1),('fixed',4,1),('random',4,1),
            ('active',4,2),('fixed',4,2),('random',4,2)))

    def _verify_history(self):
        events=self.ledger.events
        if events[0]['kind']!='run_config' or events[0]['payload']!={'manifest':self.manifest,'sha256':digest(self.manifest)}:
            raise ResearchIntegrityError('run config or frozen bank changed')
        kinds=[e['kind'] for e in events]
        if any(k not in ('run_config','trial','decision','completed') for k in kinds):
            raise ResearchIntegrityError('unsupported run event')
        trials=0;decisions=0;completed=0;champion=Policy('fixed',1,1).json()
        for row in events[1:]:
            p=row['payload'];kind=row['kind']
            if kind=='trial':
                if trials!=decisions or completed or trials>=min(self.max_cycles,len(self.proposals())):
                    raise ResearchIntegrityError('trial out of state')
                if p.get('ordinal')!=trials or p.get('candidate')!=self.proposals()[trials].json():
                    raise ResearchIntegrityError('candidate order changed')
                if p.get('previous')!=champion:
                    raise ResearchIntegrityError('candidate predecessor changed')
                for key in ('train','validation'):
                    if p.get(key)!=self.adapter.evaluate(self.proposals()[trials],key):
                        raise ResearchIntegrityError('stored trial outcome disagrees with evaluator')
                trials+=1
            elif kind=='decision':
                if decisions>=trials or trials!=decisions+1 or completed:
                    raise ResearchIntegrityError('decision out of state')
                source=events[row['seq']-1]
                if source['kind']!='trial' or p.get('ordinal')!=decisions:
                    raise ResearchIntegrityError('decision without paired trial')
                expected=self._decide(source['payload'],champion)
                if p!=expected:
                    raise ResearchIntegrityError('decision gate mismatch')
                champion=p['champion'];decisions+=1
            elif kind=='completed':
                if completed or decisions!=trials:
                    raise ResearchIntegrityError('invalid completion state')
                adopted=[e['payload']['adopted'] for e in events[:row['seq']]
                         if e['kind']=='decision']
                limit=min(self.max_cycles,len(self.proposals()))
                naturally_stopped=(trials>=min(8,limit) and
                                   len(adopted)>=self.patience and
                                   not any(adopted[-self.patience:]))
                if trials!=limit and not naturally_stopped:
                    raise ResearchIntegrityError('premature terminal completion')
                expected=self._completion(champion,trials)
                if p!=expected:
                    raise ResearchIntegrityError('completed evidence mismatch')
                completed+=1
        if completed and events[-1]['kind']!='completed':
            raise ResearchIntegrityError('events after completion')

    def _decide(self,trial,champion):
        # Validation candidate versus current champion, same disjoint worlds.
        challenger=trial['candidate']
        incumbent=self.adapter.evaluate(Policy(**champion),'validation')
        score=trial['validation']['utility_units']
        better=score>incumbent['utility_units']
        # Evidence-oriented gate: require greater utility AND no new wrong accepts.
        safe=trial['validation']['accepted_wrong']<=incumbent['accepted_wrong']
        adopted=better and safe
        return {'ordinal':trial['ordinal'],'adopted':adopted,
                'champion':challenger if adopted else champion,
                'reason':'validated_improvement' if adopted else 'no_safe_validation_gain',
                'candidate_validation_utility':score,
                'incumbent_validation_utility':incumbent['utility_units']}

    def _completion(self,champion,trials):
        baseline_validation=self.adapter.evaluate(Policy('fixed',1,1),'validation')
        selected_validation=self.adapter.evaluate(Policy(**champion),'validation')
        baseline_test=self.adapter.evaluate(Policy('fixed',1,1),'test')
        selected_test=self.adapter.evaluate(Policy(**champion),'test')
        delta=selected_test['utility_units']-baseline_test['utility_units']
        # Scientific acceptance is never implied by an author-visible public bank.
        return {'status':'COMPLETE_PUBLIC_DEVELOPMENT',
                'scientific_decision':'NOT_ASSESSED',
                'generalization_gate':'NO_VALIDATED_GAIN' if delta<=0 else 'INDEPENDENT_CONFIRMATION_REQUIRED',
                'champion':champion,'trials':trials,
                'baseline_validation':baseline_validation,
                'champion_validation':selected_validation,
                'holdout_baseline':baseline_test,
                'holdout':selected_test,
                'holdout_delta_utility':delta,
                'holdout_recorded_once_per_policy_and_reaudited_on_replay':True,
                'note':'finite policy optimization; no autonomous code/architecture invention'}

    def run(self,*,stop_after_trials=None):
        if stop_after_trials is not None:_int(stop_after_trials,0,self.max_cycles,'stop point')
        self._verify_history()
        events=self.ledger.events
        if events[-1]['kind']=='completed':return events[-1]['payload']
        trials=sum(e['kind']=='trial' for e in events)
        decisions=sum(e['kind']=='decision' for e in events)
        champion=next((e['payload']['champion'] for e in reversed(events)
                       if e['kind']=='decision'),Policy('fixed',1,1).json())
        # Recover a fully recorded pure simulation trial without executing again.
        if trials>decisions:
            trial=events[-1]['payload']
            decision=self._decide(trial,champion)
            self.ledger.append('decision',decision)
            champion=decision['champion'];decisions+=1
        proposals=self.proposals();limit=min(self.max_cycles,len(proposals))
        while trials<limit:
            if stop_after_trials is not None and trials>=stop_after_trials:break
            candidate=proposals[trials]
            record={'ordinal':trials,'candidate':candidate.json(),'previous':champion,
                    'train':self.adapter.evaluate(candidate,'train'),
                    'validation':self.adapter.evaluate(candidate,'validation')}
            self.ledger.append('trial',record)
            decision=self._decide(record,champion)
            self.ledger.append('decision',decision)
            champion=decision['champion'];trials+=1;decisions+=1
            # Explicit early stopping; never resume by silently skipping tests.
            tail=[e['payload']['adopted'] for e in self.ledger.events
                  if e['kind']=='decision']
            if trials>=min(8,limit) and len(tail)>=self.patience and not any(tail[-self.patience:]):break
        if stop_after_trials is not None and trials>=stop_after_trials and trials<limit:
            return {'status':'PAUSED_CHECKPOINT','trials':trials,'champion':champion,
                    'journal_sha256':self.ledger.events[-1]['sha256']}
        # A paused instance may have previously reached patience: do not continue.
        decisions_history=[e['payload']['adopted'] for e in self.ledger.events if e['kind']=='decision']
        if trials>=limit or (trials>=min(8,limit) and len(decisions_history)>=self.patience and
                            not any(decisions_history[-self.patience:])):
            result=self._completion(champion,trials)
            self.ledger.append('completed',result)
            return result
        return {'status':'PAUSED_CHECKPOINT','trials':trials,'champion':champion,
                'journal_sha256':self.ledger.events[-1]['sha256']}
