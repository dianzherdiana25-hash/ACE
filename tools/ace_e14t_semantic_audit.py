"""Postscore E1.4t independent-from-worker semantic evidence audit.

Separate from frozen E1.4t scorer; this auditor is written *after* observing
results, so it cannot retroactively turn public development into scientific GO.
"""
from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path

from e14.e14_integrated_graph import DurableGraphBudget, graph_oracle
from e14.e14t_bank import sha
from e14.e14t_run import MODES


def distinguishing_witness(truth,hypothesis):
    """Hindsight diagnostic only. Never feed this into the frozen score bank."""
    for word in (hypothesis,truth):
        if not 1<=len(word)<=14:
            continue
        color=0
        edges=[[0,1,color,1]]
        for i,event in enumerate(word,1):
            color ^= int(event==2)
            edges.append([i,i+1,color,1])
        graph={'nodes':len(word)+2,'start':0,'goal':len(word)+1,'edges':edges}
        observed=graph_oracle(graph,truth)
        predicted=graph_oracle(graph,hypothesis)
        if observed!=predicted:
            return {'query_sha256':sha(graph),'graph':graph,
                    'truth_label':observed,'hypothesis_label':predicted,
                    'postscore_counterfactual_oracle_calls':2}
    return None


def inspect(bank,report,ledger_path):
    worlds={w['id']:w for w in bank['worlds']}
    rows=report['rows']
    required={w+':'+m for w in worlds for m in MODES}
    if {row['arm'] for row in rows}!=required or len(rows)!=len(required):
        raise ValueError('semantic audit: incomplete/duplicate arms')
    counts={s:{m:{'accepted':0,'correct_exact':0,'wrong_exact':0,'ambiguous_probe_alias':0,
                  'errors_on_probes':0,'labels':0} for m in MODES}
            for s in ('reachable','natural','rare','out-of-grammar')}
    wrong=[]; checks=0
    for row in rows:
        world_id,mode=row['arm'].rsplit(':',1)
        w=worlds[world_id]
        truth=tuple(w['target'])
        r=DurableGraphBudget(ledger_path,row['arm']).snapshot()
        if row['receipt_sha256']!=sha(r):
            raise ValueError('semantic audit: journal hash differs')
        query_actions=[x for x in row['trace'] if x['action']=='query']
        if len(query_actions)!=r['purchased'] or row['purchased']!=r['purchased']:
            raise ValueError('semantic audit: missing charged action')
        receipts={x['id']:x for x in r['receipts']}
        for line in row['trace']:
            if line['action'] in ('query','reuse'):
                rid=line['receipt_id']
                if rid not in receipts:
                    raise ValueError('semantic audit: nonexisting receipt')
                receipt=receipts[rid]
                if line['action']=='query':
                    if receipt['label']!=line['label'] or receipt['stage']!=line['metadata']['stage']:
                        raise ValueError('semantic audit: trace receipt disagreement')
                else:
                    if line['metadata']['stage'] not in receipt['reused_in'] and line['metadata']['stage']!=receipt['stage']:
                        raise ValueError('semantic audit: forged reuse')
        final=row['trace'][-1]
        if final['action']!=row['final_action'] or row['final_action'] not in ('accept','abstain'):
            raise ValueError('semantic audit: inconsistent terminal')
        cell=counts[w['stratum']][mode]
        cell['labels']+=r['purchased']
        if row['final_action']=='abstain':
            if any(row[k]!=0 for k in ('word_correct','covered','correct','errors','false_accept')):
                raise ValueError('semantic audit: abstention credited')
        else:
            word=final['metadata'].get('word')
            if type(word) is not list or not 5<=len(word)<=9 or any(type(x) is not int or x not in (1,2) for x in word):
                raise ValueError('semantic audit: malformed accepted motif')
            hypothesis=tuple(word)
            for example in w['demos']:
                if graph_oracle(example['input'],hypothesis)!=example['output']:
                    raise ValueError('semantic audit: accepted hypothesis contradicts demo')
            for receipt in r['receipts']:
                if graph_oracle(receipt['query'],hypothesis)!=receipt['label']:
                    raise ValueError('semantic audit: accepted hypothesis contradicts receipt')
            if not any(x['stage']=='qualification' and x['status']=='settled' and x['label'] is not None for x in r['receipts']):
                raise ValueError('semantic audit: unguarded acceptance')
            truth_gold=[graph_oracle(g,truth) for g in w['probes']]
            predicted=[graph_oracle(g,hypothesis) for g in w['probes']]
            correct=sum(y==z for y,z in zip(truth_gold,predicted))
            errors=len(predicted)-correct
            exact=hypothesis==truth
            if (row['word_correct'],row['covered'],row['correct'],row['errors'],row['false_accept']) != (
                    int(exact),len(predicted),correct,errors,int(bool(errors))):
                raise ValueError('semantic audit: scored outcome differs from trusted oracle')
            cell['accepted']+=1
            cell['correct_exact']+=int(exact)
            cell['wrong_exact']+=int(not exact)
            cell['errors_on_probes']+=errors
            alias=not exact and not errors
            cell['ambiguous_probe_alias']+=int(alias)
            if not exact:
                wrong.append({'arm':row['arm'],'stratum':w['stratum'],
                              'probe_errors':errors,'undetected_by_probes':alias,
                              'postscore_distinguishing_witness':distinguishing_witness(truth,hypothesis)})
        checks+=1
    return {'status':'SEMANTIC_AUDIT_PASS','arms':checks,'cells':counts,
            'accepted_wrong_exact_cases':wrong,
            'wrong_exact_total':len(wrong),
            'probe_indistinguishable_wrong_exact':sum(x['undetected_by_probes'] for x in wrong),
            'postscore_counterfactual_oracle_calls':sum(2 for x in wrong if x['postscore_distinguishing_witness']),
            'scope':'postscore development audit; not independent scientific confirmation'}


def load(bankfile,reportfile):
    bank=json.loads(gzip.decompress(Path(bankfile).read_bytes()))
    report=json.loads(gzip.decompress(Path(reportfile).read_bytes()))
    if bank['version']!=1 or report['version']!=1:
        raise ValueError('version mismatch')
    return bank,report


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--bank',required=True)
    p.add_argument('--report',required=True)
    p.add_argument('--ledger',required=True)
    p.add_argument('--output')
    a=p.parse_args()
    bank,report=load(a.bank,a.report)
    result=inspect(bank,report,a.ledger)
    raw=json.dumps(result,indent=2,sort_keys=True)+'\n'
    if a.output:
        Path(a.output).write_text(raw)
    print(json.dumps({k:v for k,v in result.items() if k not in ('cells','accepted_wrong_exact_cases')},sort_keys=True))


if __name__=='__main__':main()
