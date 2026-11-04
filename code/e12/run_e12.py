import argparse,hashlib,json,sys
from pathlib import Path
from oracle import make_episode,apply_primitive,apply_program
from agents import discover,find_target,SOURCE_BUDGET,TARGET_BUDGET
POLICIES=('REUSE','TARGET_ONLY','SHAM','WRONG','STRUCTURED')

def digest(obj):return hashlib.sha256(json.dumps(obj,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def run(out,seed_start,episodes):
    out=Path(out);out.mkdir(parents=True,exist_ok=True);prev='0'*64
    rows=[]
    for seed in range(seed_start,seed_start+episodes):
        episode=make_episode(seed)
        source=discover(episode.source_examples,apply_primitive)[0]
        wrong=discover(episode.wrong_source_examples,apply_primitive)[0]
        sham=discover(episode.sham_examples,apply_primitive)[0]
        # TARGET_ONLY pays same source exploration budget and discards it.
        for task in episode.targets:
            for policy in POLICIES:
                base={'REUSE':source,'TARGET_ONLY':None,'SHAM':sham,'WRONG':wrong,'STRUCTURED':None}[policy]
                outcome=find_target(policy,base,task['demos'],apply_program,task['task_id'])
                p,w=outcome['selected']
                h9=[int(apply_program(p,w,x)==y) for x,y in task['h9']]
                h13=[int(apply_program(p,w,x)==y) for x,y in task['h13']]
                row={'seed':seed,'task_id':task['task_id'],'category':task['category'],
                     'policy':policy,'selected_primitive':p,'selected_wrapper':w,
                     'source_synthesized_primitive':base,
                     'source_cost':SOURCE_BUDGET,'target_cost':TARGET_BUDGET,
                     'demo_score':outcome['score'],
                     'hidden9_score':sum(h9),'hidden13_score':sum(h13),
                     'hidden9_bits':h9,'hidden13_bits':h13,
                     'proposal_sha256':outcome['proposal_sha256'],
                     'common_initial_sha256':outcome['common_initial_sha256']}
                row['prev_sha256']=prev;row['sha256']=digest(row);prev=row['sha256'];rows.append(row)
    with (out/'runs.jsonl').open('w') as f:
        for row in rows:f.write(json.dumps(row,sort_keys=True)+'\n')
    def part(policy,cat,metric):
        subset=[r for r in rows if r['policy']==policy and (cat=='all' or r['category']==cat)]
        return {'correct':sum(r[metric] for r in subset),'total':len(subset)*8,
                'tasks':len(subset)}
    summary={'episodes':episodes,'runs':len(rows),'task_count':episodes*4,
             'source_budget_per_policy_episode':SOURCE_BUDGET,
             'target_budget_per_policy_task':TARGET_BUDGET,
             'total_candidate_evaluations_per_policy':episodes*(SOURCE_BUDGET+4*TARGET_BUDGET),
             'results':{p:{cat:{m:part(p,cat,m) for m in ('hidden9_score','hidden13_score')}
                              for cat in ('all','related','unrelated')} for p in POLICIES},
             'last_sha256':prev}
    (out/'summary.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps(summary,indent=2))
    return summary

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--out',required=True);a.add_argument('--seed-start',type=int,required=True);a.add_argument('--episodes',type=int,required=True);x=a.parse_args();run(x.out,x.seed_start,x.episodes)
