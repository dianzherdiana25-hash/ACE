"""E1.5 follow-on: bounded *source* candidate evolution, without executing candidate Python.

A candidate is a real Python source file containing a single expression function.
It is parsed and interpreted with a strict arithmetic AST whitelist. No eval/exec,
imports, calls, attributes, loops or arbitrary source files are accepted. The
module stages an immutable candidate and its receipt; it never changes a live
repository file. All examples are synthetic/public development only.
"""
from __future__ import annotations
import ast
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import tempfile
from .engine import HashLedger, ResearchIntegrityError, digest

ALLOWED = (ast.Expression, ast.BinOp, ast.Add, ast.Sub, ast.Mult, ast.Name,
           ast.Load, ast.Constant)
SOURCE_TEMPLATE = 'def predict(x, y):\n    return {expr}\n'
MAX_ABS = 10**9


def parse_source(source: str):
    if type(source) is not str or len(source) > 300:
        raise ResearchIntegrityError('source size/type invalid')
    try: tree = ast.parse(source, mode='exec')
    except (SyntaxError, ValueError) as e: raise ResearchIntegrityError('invalid source') from e
    if len(tree.body) != 1 or type(tree.body[0]) is not ast.FunctionDef:
        raise ResearchIntegrityError('only one function allowed')
    fn = tree.body[0]
    if fn.name != 'predict' or fn.decorator_list or fn.returns or fn.type_comment:
        raise ResearchIntegrityError('unexpected function signature')
    a = fn.args
    if (a.posonlyargs or a.vararg or a.kwonlyargs or a.kwarg or a.defaults or a.kw_defaults
        or len(a.args) != 2 or [v.arg for v in a.args] != ['x','y']
        or any(v.annotation for v in a.args)):
        raise ResearchIntegrityError('unexpected function arguments')
    if len(fn.body) != 1 or type(fn.body[0]) is not ast.Return:
        raise ResearchIntegrityError('function must contain one return')
    expression = fn.body[0].value
    nodes=list(ast.walk(expression))
    if len(nodes)>25: raise ResearchIntegrityError('expression too complex')
    for node in nodes:
        if type(node) not in ALLOWED: raise ResearchIntegrityError('forbidden source construct')
        if type(node) is ast.Name and node.id not in ('x','y'):
            raise ResearchIntegrityError('unknown variable')
        if type(node) is ast.Constant and (type(node.value) is not int or abs(node.value)>20):
            raise ResearchIntegrityError('invalid literal')
    return expression


def interpret(node, x: int, y: int) -> int:
    if type(x) is not int or type(y) is not int or max(abs(x),abs(y))>100:
        raise ResearchIntegrityError('invalid evaluation input')
    def walk(n):
        if type(n) is ast.Name: return x if n.id=='x' else y
        if type(n) is ast.Constant: return n.value
        if type(n) is ast.BinOp:
            left,right=walk(n.left),walk(n.right)
            if type(n.op) is ast.Add: out=left+right
            elif type(n.op) is ast.Sub: out=left-right
            else: out=left*right
            if abs(out)>MAX_ABS: raise ResearchIntegrityError('expression overflow')
            return out
        raise ResearchIntegrityError('invalid node')
    return walk(node)


def source_for(expr: str) -> str:
    src=SOURCE_TEMPLATE.format(expr=expr)
    parse_source(src)
    return src


def synthetic_bank():
    """Disjoint deterministic splits; target hidden from proposal function."""
    return {
        'train': [(x,y,3*x+2*y) for x,y in [(-3,2),(-2,-1),(0,1),(2,0)]],
        'validation': [(x,y,3*x+2*y) for x,y in [(-5,3),(4,-2),(1,5)]],
        'holdout': [(x,y,3*x+2*y) for x,y in [(-7,4),(6,-3),(3,7)]],
    }


def score(src: str, cases) -> dict:
    expr=parse_source(src)
    predicted=[interpret(expr,x,y) for x,y,_ in cases]
    errors=[abs(a-row[2]) for a,row in zip(predicted,cases)]
    return {'count':len(cases),'correct':sum(e==0 for e in errors),
            'absolute_error':sum(errors)}


@dataclass(frozen=True)
class Candidate:
    name: str
    expression: str


# Explicit finite grammar; this demonstrates source-level candidate selection,
# not unrestricted autonomous program synthesis or architecture discovery.
PROPOSALS=(Candidate('baseline','x + y'), Candidate('x2_y','2*x + y'),
           Candidate('x3_y','3*x + y'), Candidate('x3_y2','3*x + 2*y'),
           Candidate('x2_y2','2*x + 2*y'))


class SourceEvolution:
    def __init__(self, root: Path):
        self.root=Path(root)
        if self.root.is_symlink() or self.root.parent.is_symlink():
            raise ResearchIntegrityError('symlink root forbidden')
        self.root.mkdir(parents=True,exist_ok=True)
        self.bank=synthetic_bank()
        self.sources=[source_for(p.expression) for p in PROPOSALS]
        self.manifest={'schema':1,'mode':'BOUNDED_SOURCE_CANDIDATE_PUBLIC_DEVELOPMENT',
                       'sources_sha256':[hashlib.sha256(s.encode()).hexdigest() for s in self.sources],
                       'bank_sha256':digest(self.bank),'selection':'validation error, ties keep incumbent',
                       'holdout':'terminal only; no promotion'}
        self.ledger=HashLedger(self.root/'events.jsonl')
        if not self.ledger.events:self.ledger.append('config',{'manifest':self.manifest})
        self._verify()

    def _expected(self):
        events=self.ledger.events
        if events[0]['kind']!='config' or events[0]['payload']!={'manifest':self.manifest}:
            raise ResearchIntegrityError('source evolution config mismatch')
        current=0;trials=0;complete=False
        for event in events[1:]:
            k,p=event['kind'],event['payload']
            if k=='trial':
                if complete or trials>=len(PROPOSALS) or p!={'index':trials,'name':PROPOSALS[trials].name,
                    'source_sha256':self.manifest['sources_sha256'][trials],
                    'train':score(self.sources[trials],self.bank['train']),
                    'validation':score(self.sources[trials],self.bank['validation'])}:
                    raise ResearchIntegrityError('trial replay mismatch')
                trials+=1
            elif k=='decision':
                if complete or trials==0 or trials!=sum(e['kind']=='decision' for e in events[1:event['seq']])+1:
                    raise ResearchIntegrityError('decision ordering mismatch')
                idx=trials-1
                if events[event['seq']-1]['kind']!='trial':raise ResearchIntegrityError('decision missing trial')
                incumbent=score(self.sources[current],self.bank['validation'])['absolute_error']
                challenger=score(self.sources[idx],self.bank['validation'])['absolute_error']
                adopted=challenger<incumbent
                expected={'index':idx,'adopted':adopted,'champion':idx if adopted else current}
                if p!=expected:raise ResearchIntegrityError('decision replay mismatch')
                current=expected['champion']
            elif k=='complete':
                if complete or trials!=len(PROPOSALS) or events[event['seq']-1]['kind']!='decision':
                    raise ResearchIntegrityError('premature completion')
                expected=self._terminal(current)
                if p!=expected:raise ResearchIntegrityError('terminal replay mismatch')
                complete=True
            else:raise ResearchIntegrityError('unknown evolution event')
        if complete and events[-1]['kind']!='complete':raise ResearchIntegrityError('events after completion')
        return current,trials,complete

    def _verify(self):
        self._expected()
        # Verify staged source if present; it is not an executable deployment.
        candidate=self.root/'staged_candidate.py'
        if candidate.is_symlink():raise ResearchIntegrityError('staged source symlink')
        if candidate.exists():
            if self.ledger.events[-1]['kind']!='complete':
                raise ResearchIntegrityError('staged source before completion')
            idx=self.ledger.events[-1]['payload']['selected_index']
            if candidate.read_bytes()!=self.sources[idx].encode():
                raise ResearchIntegrityError('staged source modified')
        elif self.ledger.events[-1]['kind']=='complete':
            # A crash between terminal receipt and staging can be recovered safely.
            pass

    def _terminal(self,idx):
        base=score(self.sources[0],self.bank['holdout'])
        selected=score(self.sources[idx],self.bank['holdout'])
        return {'status':'COMPLETE_PUBLIC_SOURCE_DEVELOPMENT','scientific_decision':'NOT_ASSESSED',
                'selected_index':idx,'selected_name':PROPOSALS[idx].name,
                'selected_sha256':self.manifest['sources_sha256'][idx],
                'holdout_baseline':base,'holdout_selected':selected,
                'holdout_delta_absolute_error':selected['absolute_error']-base['absolute_error'],
                'candidate_promoted':False,'deployment':'STAGED_ONLY_NO_LIVE_MUTATION'}

    def _stage(self,idx):
        path=self.root/'staged_candidate.py'
        if path.is_symlink():raise ResearchIntegrityError('staged source symlink')
        content=self.sources[idx].encode()
        if path.exists():
            if path.read_bytes()!=content:raise ResearchIntegrityError('staged source mismatch')
            return
        fd,tmp=tempfile.mkstemp(dir=self.root,prefix='.candidate-')
        try:
            with os.fdopen(fd,'wb') as f:
                f.write(content);f.flush();os.fsync(f.fileno())
            # Atomic exclusive create prevents replacing a file created concurrently.
            os.link(tmp,path)
        except FileExistsError:
            if path.is_symlink() or path.read_bytes()!=content:
                raise ResearchIntegrityError('staged source race')
        finally:
            os.unlink(tmp)

    def run(self,stop_after=None):
        if stop_after is not None and (type(stop_after) is not int or not 0<=stop_after<=len(PROPOSALS)):
            raise ResearchIntegrityError('invalid stop_after')
        current,trials,complete=self._expected()
        if complete:
            self._stage(current)
            return self.ledger.events[-1]['payload']
        # Recover trial receipt without reevaluation; pure local deterministic.
        if self.ledger.events[-1]['kind']=='trial':
            idx=trials-1
            adopted=score(self.sources[idx],self.bank['validation'])['absolute_error'] < score(self.sources[current],self.bank['validation'])['absolute_error']
            current=idx if adopted else current
            self.ledger.append('decision',{'index':idx,'adopted':adopted,'champion':current})
        for idx in range(trials,len(PROPOSALS)):
            if stop_after is not None and idx>=stop_after:break
            self.ledger.append('trial',{'index':idx,'name':PROPOSALS[idx].name,
                'source_sha256':self.manifest['sources_sha256'][idx],
                'train':score(self.sources[idx],self.bank['train']),
                'validation':score(self.sources[idx],self.bank['validation'])})
            adopted=score(self.sources[idx],self.bank['validation'])['absolute_error'] < score(self.sources[current],self.bank['validation'])['absolute_error']
            current=idx if adopted else current
            self.ledger.append('decision',{'index':idx,'adopted':adopted,'champion':current})
        if sum(e['kind']=='decision' for e in self.ledger.events)==len(PROPOSALS):
            result=self._terminal(current)
            self.ledger.append('complete',result)
            self._stage(current)
            return result
        return {'status':'PAUSED_CHECKPOINT','trials':sum(e['kind']=='trial' for e in self.ledger.events),
                'chain_head':self.ledger.events[-1]['sha256']}
