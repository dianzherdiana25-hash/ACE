"""E1.4d preregistered public-development pilot. No heldout tuning."""
from __future__ import annotations
import argparse,json,re
from pathlib import Path
from e13.contract import canonical_json
from .e14d_bank import bank,digest,FAMILIES,REGIMES
from .e14d_policy import fit5,choose_context,learn,minimax_index,ABSTAIN
from .cross_episode_candidate import choose,predict,POLICIES
from .query_bank import oracle

SEED=141804

def score(task,chosen):
    pred=[predict(task.family,chosen,p['input']) for p in task.probes]
    truth=[p['output'] for p in task.probes]
    vals=[int(x==y) for x,y in zip(pred,truth)]
    return {'total':sum(vals),'natural':sum(vals[:4]),'diagnostic':sum(vals[4:])}


def source(task):
    candidates=fit5(task.family,task.demos)
    arms=[]
    for i,v in enumerate(task.pool):
        labeled={'input':v,'output':oracle(task.family,task.word,v)}
        after=fit5(task.family,(*task.demos,labeled))
        arms.append({'index':i,'score':score(task,after[0]),'labels':1})
    policy_scores={p:arms[choose(p,task.family,candidates,task.pool,seed=SEED+task.slot)[0]]['score']['total'] for p in POLICIES}
    from .e14d_policy import context
    return {'family':task.family,'regime':task.regime,'task_id':task.task_id,
            'bucket':context(task.family,candidates,task.pool),'candidate_count':len(candidates),
            'policy_scores':policy_scores,'no_label':score(task,candidates[0])['total'],
            'source_labels':8,'arms':arms}

def target(task,model):
    candidates=fit5(task.family,task.demos)
    arms=[]
    labeled_pool=[]
    for i,v in enumerate(task.pool):
        lab={'input':v,'output':oracle(task.family,task.word,v)}
        labeled_pool.append(lab)
        after=fit5(task.family,(*task.demos,lab))
        arms.append({'index':i,'score':score(task,after[0]),'labels':1})
    no=score(task,candidates[0]);action=choose_context(task.family,candidates,task.pool,model['mapping'],SEED+task.slot)
    # Sham rotates mapping across buckets, and is fixed without target outcomes.
    mapping=model['mapping'];sham_model={**mapping}
    a=mapping.get('high_ambiguity',ABSTAIN);b=mapping.get('low_ambiguity',ABSTAIN)
    sham_model['high_ambiguity']=b;sham_model['low_ambiguity']=a
    def alias(a):return no if a['index'] is None else arms[a['index']]['score']
    sham=choose_context(task.family,candidates,task.pool,sham_model,SEED+task.slot)
    local_index,_=choose('max_partition',task.family,candidates,task.pool,seed=SEED+task.slot)
    minimax_slot=minimax_index(task.family,candidates,task.pool)
    # Additional strong upper baseline: learn using ALL eight labelled target pool examples.
    full_demos=tuple(task.demos)+tuple(labeled_pool)
    full_fit=fit5(task.family,full_demos)
    scores={'inherited':alias(action),'sham':alias(sham),'task_local':arms[local_index]['score'],
            'grammar_informed_reference':arms[minimax_slot]['score'],
            'no_label':no,'full_target_eight_labels':score(task,full_fit[0])}
    return {'family':task.family,'regime':task.regime,'task_id':task.task_id,'slot':task.slot,
            'bucket':action['bucket'],'candidate_count':len(candidates),'inherited':action,
            'sham':sham,'local_index':local_index,'reference_index':minimax_slot,
            'scores':scores,'arms':arms,'uniform_expected':sum(a['score']['total'] for a in arms)/8,
            'hindsight_ceiling':max(a['score']['total'] for a in arms)}


def report(source_commit):
    if not re.fullmatch('[0-9a-f]{40}',source_commit):raise ValueError('bad frozen source sha')
    pairs=bank();s=[source(a) for a,_ in pairs];models={fam:learn(s,fam) for fam in FAMILIES}
    t=[target(b,models[b.family]) for _,b in pairs]
    groups=[]
    for fam in FAMILIES:
      for regime in REGIMES:
        rows=[x for x in t if x['family']==fam and x['regime']==regime]
        assert len(rows)==3
        names=rows[0]['scores'].keys();sc={k:sum(r['scores'][k]['total'] for r in rows) for k in names}
        groups.append({'family':fam,'regime':regime,'episodes':3,'probes':24,'scores':sc,
                       'random_expected':sum(r['uniform_expected'] for r in rows),
                       'inherited_query_labels':sum(r['inherited']['labels'] for r in rows)})
    inherited_labels=sum(x['inherited']['labels'] for x in t)
    costs={'source_training_labels':96,'target_counterfactual_labels':96,
           'inherited_target_labels':inherited_labels,'inherited_total_acquisition_labels':96+inherited_labels,
           'task_local_deployment_labels':12,'full_target_eight_label_comparator':96,
           'source_labels_per_target_at_current_horizon':8.0,
           'compute_parity_established':False}
    # Strict advancement requires family/regime wins against both class-aware controls,
    # random expectation, no label and same budget FULL TARGET comparator.
    performance=all(g['scores']['inherited']>max(g['scores']['sham'],g['scores']['task_local'],
       g['scores']['grammar_informed_reference'],g['scores']['no_label'],
       g['random_expected']) for g in groups)
    # Predictive GO is separately labeled: it makes no claim of full-cost efficiency.
    cost_dominated=costs['inherited_total_acquisition_labels']>costs['full_target_eight_label_comparator']
    return {'mode':'E1.4d_public_development','source_commit':source_commit,
            'bank_sha256':digest(pairs),'source_episodes':len(s),'target_episodes':len(t),
            'models':models,'source_rows':s,'target_rows':t,'summary':groups,'costs':costs,
            'decision':('GO_PREDICTIVE_ONLY_COST_UNPROVEN' if performance else 'HOLD_CONTEXT_TRANSFER'),
            'cost_dominated_by_full_target_eight_labels':cost_dominated,
            'limitations':['Human-defined five-event grammar and policy family, not open-ended evolution.',
            'Public development, not independent confirmation. Same-process candidate and evaluator.',
            'Source training label acquisition is not amortized at this 12-target horizon.',
            'Four natural random probes plus four constructed diagnostic probes per episode.',
            'Full-target eight-label comparator is a separate budget tier, not a one-label control.']}

def main():
    p=argparse.ArgumentParser();p.add_argument('--source-commit',required=True);p.add_argument('--verify',type=Path)
    args=p.parse_args();r=report(args.source_commit)
    if args.verify and canonical_json(r)!=canonical_json(json.loads(args.verify.read_text())):
        raise ValueError('replay mismatch')
    print(canonical_json(r).decode("utf-8"))
if __name__=='__main__':main()
