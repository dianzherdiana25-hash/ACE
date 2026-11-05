"""E1.6: bounded, reproducible *source-code* mutation experiment.

This intentionally narrow vertical slice writes and executes new Python function
sources constructed from a hard-coded, typed arithmetic grammar. It is not
permission to execute arbitrary generated code or a native security sandbox.
It uses synthetic E1.4y labels only, never a remote oracle or sealed holdout.

Research integrity: public train/validation/test worlds are disjoint; a test
score cannot select the candidate. A candidate that looks good in validation
is NOT promoted without positive heldout gain; all rejected proposals remain
in a durable, deterministic evidence chain. Source bytes are verified on replay.
"""
from __future__ import annotations

import ast
from collections import Counter
from dataclasses import dataclass
import hashlib
from pathlib import Path
import os

from .engine import HashLedger, Policy, ResearchIntegrityError, _int, _metrics, digest
from .operators import OperatorAdapter
from e14.e14y_induction import GRID, GRID_INDEX, candidates, grammar


def _sha(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


# Genes change real Python expression trees and are not blindly executable text.
# Components: candidate diversity, balance penalty, cost gap, rotation weight,
# modulo, and orientation of final rank. These are all pre-declared primitives.
@dataclass(frozen=True)
class Gene:
    diversity: int
    balance: int
    gap: int
    rotation: int
    modulus: int
    sign: int

    def __post_init__(self):
        for name in ('diversity', 'balance', 'gap', 'rotation'):
            _int(getattr(self,name), -8, 8, name)
        _int(self.modulus, 2, 11, 'modulus')
        if type(self.sign) is not int or self.sign not in (-1, 1):
            raise ResearchIntegrityError('invalid rank orientation')

    def json(self):
        return {'diversity':self.diversity, 'balance':self.balance,
                'gap':self.gap, 'rotation':self.rotation,
                'modulus':self.modulus, 'sign':self.sign}


SEED=Gene(0,0,-1,0,3,1)
RULES=(
    ('diversity',2),('balance',-1),('gap',2),('rotation',3),
    ('diversity',-3),('balance',1),('gap',-2),('rotation',-4),
    ('modulus',2),('modulus',5),('sign',-1),('diversity',5),
    ('balance',-3),('gap',5),('rotation',7),('modulus',7),
)


def mutate(parent:Gene,ordinal:int)->Gene:
    _int(ordinal,0,1000,'mutation ordinal')
    field,value=RULES[ordinal%len(RULES)]
    data=parent.json()
    data[field]=value
    # At boundaries, keep a reproducible novel source expression.
    if data==parent.json():
        data['gap']=parent.gap+1 if parent.gap<8 else -8
    return Gene(**data)


def source_for(gene:Gene)->bytes:
    if type(gene) is not Gene:raise ResearchIntegrityError('typed source gene required')
    # All code is produced from validated integers, never interpolated commands.
    text=("def rank(lo, hi, turn, diversity, balance):\n"
          f"    return {gene.sign} * (diversity * {gene.diversity} "
          f"+ balance * {gene.balance} + (hi - lo) * {gene.gap} "
          f"+ ((lo + hi + turn) % {gene.modulus}) * {gene.rotation})\n")
    return text.encode('ascii')


def compile_rank(source: bytes, gene: Gene):
    """Reject arbitrary code even if a disk file is rehashed by an attacker.

    This is defense in depth for our own trusted template, NOT a security
    boundary for adversarial code; no external/LLM-generated source accepted.
    """
    if type(gene) is not Gene or source != source_for(gene):
        raise ResearchIntegrityError('source not in approved generated grammar')
    if type(source) is not bytes or len(source)>1024:
        raise ResearchIntegrityError('invalid source byte length')
    try: tree=ast.parse(source, mode='exec')
    except (SyntaxError,ValueError,TypeError) as exc:
        raise ResearchIntegrityError('invalid source syntax') from exc
    if len(tree.body)!=1 or not isinstance(tree.body[0],ast.FunctionDef):
        raise ResearchIntegrityError('source must define exactly one function')
    fn=tree.body[0]
    if (fn.name!='rank' or fn.decorator_list or fn.returns is not None or
        len(fn.body)!=1 or not isinstance(fn.body[0],ast.Return) or
        fn.args.posonlyargs or fn.args.vararg or fn.args.kwarg or fn.args.kwonlyargs or
        fn.args.defaults or fn.args.kw_defaults or
        [x.arg for x in fn.args.args]!=['lo','hi','turn','diversity','balance'] or
        any(x.annotation is not None for x in fn.args.args)):
        raise ResearchIntegrityError('source function shape rejected')
    allowed=(ast.Module,ast.FunctionDef,ast.arguments,ast.arg,ast.Return,
             ast.BinOp,ast.Add,ast.Sub,ast.Mult,ast.Mod,ast.Name,ast.Load,
             ast.Constant,ast.UnaryOp,ast.USub)
    nodes=list(ast.walk(tree))
    if len(nodes)>96:raise ResearchIntegrityError('oversized candidate AST')
    for node in nodes:
        if type(node) not in allowed:
            raise ResearchIntegrityError('untrusted candidate AST operation')
        if isinstance(node,ast.Name) and node.id not in ('lo','hi','turn','diversity','balance'):
            raise ResearchIntegrityError('untrusted candidate identifier')
        if isinstance(node,ast.Constant) and (type(node.value) is not int or abs(node.value)>11):
            raise ResearchIntegrityError('untrusted candidate literal')
    namespace={'__builtins__':{}}
    # Only the trusted generated arithmetic source is compiled; the caller
    # MUST check the byte equality against source_for(gene) before reaching here.
    exec(compile(tree,'<ACE-generated-arithmetic>', 'exec'), namespace, namespace)
    return namespace['rank']


class SourceAdapter:
    """Use generated ranker to choose paid *synthetic* E1.4y cost queries."""
    def __init__(self,original:OperatorAdapter,label_cap=3):
        if type(original) is not OperatorAdapter:raise ResearchIntegrityError('unexpected evaluator')
        _int(label_cap,1,4,'label cap')
        self.original=original
        self.label_cap=label_cap
        self.signatures=tuple(x[2] for x in grammar())
        self._cache={}

    def manifest(self):
        return {'bank':self.original.bank_manifest(),'cap':self.label_cap,
                'scoring':'20 correct - 40 wrong -2 abstain -1 logical label',
                'source_grammar':'trusted_arithmetic_v1'}

    def evaluate(self,gene:Gene,split):
        if type(gene) is not Gene:raise ResearchIntegrityError('invalid gene type')
        if split not in ('train','validation','test'):
            raise ResearchIntegrityError('invalid experiment split')
        key=(gene,split)
        if key in self._cache:return dict(self._cache[key])
        fn=compile_rank(source_for(gene),gene)
        rows=[]
        for world in self.original._sets[split]:
            rows.append(self._one(world,fn))
        self._cache[key]=_metrics(rows)
        return dict(self._cache[key])

    def _one(self,world,rank):
        seen=[]
        for turn in range(self.label_cap):
            ids=candidates(seen)
            if len(ids)<=1:break
            used={xy for xy,_ in seen}
            # Candidate ranking observes current version-space predictions only.
            # It cannot query world truth except the single selected coordinate.
            proposed=None
            for xy in GRID:
                if xy in used:continue
                counts=Counter(self.signatures[i][GRID_INDEX[xy]] for i in ids)
                if len(counts)<=1:continue
                diversity=len(counts);balance=sum(n*n for n in counts.values())
                score=rank(xy[0],xy[1],turn,diversity,balance)
                if type(score) is not int or abs(score)>2000000:
                    raise ResearchIntegrityError('invalid generated rank result')
                candidate=(score,-GRID_INDEX[xy])
                if proposed is None or candidate>proposed[0]:
                    proposed=(candidate,xy)
            if proposed is None:break
            xy=proposed[1]
            seen.append((xy,self.original._truth(world,xy)))
        ids=candidates(seen)
        if len(ids)!=1:
            return {'accepted_correct':0,'accepted_wrong':0,'abstained':1,
                    'logical_labels':len(seen),'probe_errors':0}
        predicted=self.signatures[ids[0]]
        gold=tuple(self.original._truth(world,xy) for xy in GRID)
        errors=sum(a!=b for a,b in zip(predicted,gold))
        return {'accepted_correct':int(errors==0),'accepted_wrong':int(errors!=0),
                'abstained':0,'logical_labels':len(seen),'probe_errors':errors}


class SourceEvolution:
    """Mutation -> source file -> train/validation -> decision -> holdout.

    No code is promoted to the repository/live service. A 'promoted' outcome
    below only means a local *simulation decision*, not a deployment.
    """
    def __init__(self,root,adapter:SourceAdapter,*,max_cycles=8,patience=8):
        _int(max_cycles,1,len(RULES),'max_cycles')
        _int(patience,1,len(RULES),'patience')
        if type(adapter) is not SourceAdapter:raise ResearchIntegrityError('invalid adapter')
        self.root=Path(root)
        if self.root.is_symlink():raise ResearchIntegrityError('symlink root')
        self.root.mkdir(parents=True,exist_ok=True)
        self.paths=self.root/'proposals'
        if self.paths.is_symlink():raise ResearchIntegrityError('symlink proposal path')
        self.paths.mkdir(parents=True,exist_ok=True)
        self.adapter=adapter;self.max_cycles=max_cycles;self.patience=patience
        self.manifest={'schema':1,'research':'PUBLIC_FINITE_SOURCE_MUTATION',
                       'max_cycles':max_cycles,'patience':patience,
                       'adapter':adapter.manifest(),'seed':SEED.json(),
                       'rules':[[x,y] for x,y in RULES],
                       'holdout':'terminal-only, not for candidate selection',
                       'external_oracle':'NONE',
                       'security':'trusted generated arithmetic, not a sandbox'}
        self.ledger=HashLedger(self.root/'events.jsonl')
        if not self.ledger.events:
            self.ledger.append('config',{'manifest':self.manifest,'digest':digest(self.manifest)})
        self._verify()

    def _file(self,i):return self.paths/f'mutation_{i:03d}.py'

    def _source(self,i,gene,*,create):
        path=self._file(i)
        content=source_for(gene)
        if path.is_symlink():raise ResearchIntegrityError('candidate source symlink')
        if path.exists():
            if path.read_bytes()!=content:
                raise ResearchIntegrityError('candidate source bytes tampered')
        elif create:
            fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
            try:
                with os.fdopen(fd,'wb') as f:
                    f.write(content);f.flush();os.fsync(f.fileno())
            except BaseException:
                raise
        else:
            raise ResearchIntegrityError('missing candidate source')
        if content!=source_for(gene):raise ResearchIntegrityError('source mismatch')
        compile_rank(content,gene)
        return _sha(content)

    def _verify(self):
        ev=self.ledger.events
        if not ev or ev[0]['kind']!='config' or ev[0]['payload']!={'manifest':self.manifest,'digest':digest(self.manifest)}:
            raise ResearchIntegrityError('source evolution config mismatch')
        champion=SEED
        ordinal=0
        idx=1
        completed=False
        adoption_history=[]
        while idx<len(ev):
            row=ev[idx]
            if row['kind']=='completed':
                if idx!=len(ev)-1 or not (ordinal==self.max_cycles or self._should_stop(adoption_history,ordinal)):
                    raise ResearchIntegrityError('invalid source completion position')
                if row['payload']!=self._finish(champion,ordinal):
                    raise ResearchIntegrityError('forged completion evidence')
                completed=True;idx+=1;break
            if row['kind']!='trial' or ordinal>=self.max_cycles or self._should_stop(adoption_history,ordinal):
                raise ResearchIntegrityError('source trial out of sequence')
            p=row['payload'];candidate=mutate(champion,ordinal)
            if p.get('ordinal')!=ordinal or p.get('parent')!=champion.json() or p.get('gene')!=candidate.json():
                raise ResearchIntegrityError('mutation lineage conflict')
            if p.get('source_sha256')!=self._source(ordinal,candidate,create=False):
                raise ResearchIntegrityError('mutation source signature conflict')
            if p.get('train')!=self.adapter.evaluate(candidate,'train') or p.get('validation')!=self.adapter.evaluate(candidate,'validation'):
                raise ResearchIntegrityError('mutation scored evidence conflict')
            idx+=1
            if idx==len(ev):break  # crash after durable trial; decision can replay
            if ev[idx]['kind']!='decision':raise ResearchIntegrityError('missing source decision')
            decision=self._decide(p,champion)
            if ev[idx]['payload']!=decision:
                raise ResearchIntegrityError('forged source promotion decision')
            champion=Gene(**decision['champion'])
            adoption_history.append(decision['adopted'])
            idx+=1;ordinal+=1
        if completed and idx!=len(ev):raise ResearchIntegrityError('events after completion')
        self._state=(ordinal,champion,completed)

    def _should_stop(self,adoptions,ordinal):
        # Stop only after evidence of repeated failed source modifications.
        return (ordinal>=min(3,self.max_cycles) and
                len(adoptions)>=self.patience and
                not any(adoptions[-self.patience:]))

    def _decide(self,trial,champion):
        baseline=self.adapter.evaluate(champion,'validation')
        other=trial['validation']
        accepted=(other['utility_units']>baseline['utility_units'] and
                  other['accepted_wrong']<=baseline['accepted_wrong'])
        return {'ordinal':trial['ordinal'],'adopted':accepted,
                'reason':'VALIDATION_GAIN' if accepted else 'NO_SAFE_GAIN',
                'candidate_utility':other['utility_units'],
                'incumbent_utility':baseline['utility_units'],
                'champion':trial['gene'] if accepted else champion.json()}

    def _finish(self,champion,ordinal):
        baseline=self.adapter.evaluate(SEED,'test')
        selected=self.adapter.evaluate(champion,'test')
        delta=selected['utility_units']-baseline['utility_units']
        return {'status':'COMPLETE_PUBLIC_DEVELOPMENT',
                'scientific_decision':'NOT_ASSESSED','trials':ordinal,
                'winner_source_sha256':_sha(source_for(champion)),
                'winner_gene':champion.json(),
                'baseline_validation':self.adapter.evaluate(SEED,'validation'),
                'winner_validation':self.adapter.evaluate(champion,'validation'),
                'heldout_baseline':baseline,'heldout_candidate':selected,
                'heldout_delta_utility':delta,
                'deployment_decision':('HOLD_FOR_EXTERNAL_REVIEW' if delta>0
                                       else 'REVERT_UNPROMOTED_SOURCE'),
                'candidate_code_deployed':False,
                'limits':'trusted grammar; local synthetic oracle; no new primitive; no independent custody'}

    def run(self,*,stop_after=None):
        if stop_after is not None:_int(stop_after,0,self.max_cycles,'stop_after')
        self._verify()
        ordinal,champion,completed=self._state
        if completed:return self.ledger.events[-1]['payload']
        if self.ledger.events[-1]['kind']=='trial':
            decision=self._decide(self.ledger.events[-1]['payload'],champion)
            self.ledger.append('decision',decision)
            champion=Gene(**decision['champion']);ordinal+=1
        adoptions=[x['payload']['adopted'] for x in self.ledger.events if x['kind']=='decision']
        while (ordinal<self.max_cycles and not self._should_stop(adoptions,ordinal)
               and (stop_after is None or ordinal<stop_after)):
            candidate=mutate(champion,ordinal)
            sha=self._source(ordinal,candidate,create=True)
            trial={'ordinal':ordinal,'parent':champion.json(), 'gene':candidate.json(),
                   'source_sha256':sha,
                   'train':self.adapter.evaluate(candidate,'train'),
                   'validation':self.adapter.evaluate(candidate,'validation')}
            self.ledger.append('trial',trial)
            decision=self._decide(trial,champion)
            self.ledger.append('decision',decision)
            champion=Gene(**decision['champion']);ordinal+=1
            adoptions.append(decision['adopted'])
        if ordinal==self.max_cycles or self._should_stop(adoptions,ordinal):
            final=self._finish(champion,ordinal)
            self.ledger.append('completed',final)
            return final
        return {'status':'PAUSED_CHECKPOINT','trials':ordinal,
                'champion_source_sha256':_sha(source_for(champion)),
                'head':self.ledger.events[-1]['sha256']}
