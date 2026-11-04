import argparse,json,hashlib
from pathlib import Path
from oracle import make_episode
from independent_eval import independent_program
from agents import SOURCE_BUDGET,TARGET_BUDGET
from run_e12 import POLICIES

def sha(obj):return hashlib.sha256(json.dumps(obj,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def audit(folder):
 folder=Path(folder)
 rows=[json.loads(ln) for ln in (folder/'runs.jsonl').read_text().splitlines() if ln.strip()]
 summary=json.loads((folder/'summary.json').read_text())
 assert len(rows)==summary['runs']==summary['episodes']*4*len(POLICIES)
 prev='0'*64
 groups={};counts={p:{c:{m:0 for m in ('hidden9_score','hidden13_score')} for c in ('all','related','unrelated')} for p in POLICIES}
 for row in rows:
  saved=row['sha256'];temp={k:v for k,v in row.items() if k!='sha256'}
  assert row['prev_sha256']==prev
  assert sha(temp)==saved
  prev=saved
  assert row['source_cost']==SOURCE_BUDGET
  assert row['target_cost']==TARGET_BUDGET
  policy=row['policy'];cat=row['category'];assert policy in POLICIES
  episode=make_episode(row['seed'])
  task=next(x for x in episode.targets if x['task_id']==row['task_id'])
  assert task['category']==cat
  p=row['selected_primitive'];w=row['selected_wrapper']
  for field,tk in (('hidden9_score','h9'),('hidden13_score','h13')):
   bits=[int(independent_program(p,w,x)==y) for x,y in task[tk]]
   assert bits==row[field.replace('_score','_bits')]
   assert sum(bits)==row[field]
   counts[policy]['all'][field]+=sum(bits)
   counts[policy][cat][field]+=sum(bits)
  groups.setdefault(row['task_id'],[]).append(row)
 assert prev==summary['last_sha256']
 for task_id,rs in groups.items():
  assert len(rs)==len(POLICIES)
  assert set(r['policy'] for r in rs)==set(POLICIES)
  assert len(set(r['common_initial_sha256'] for r in rs))==1
 for p in POLICIES:
  for c in counts[p]:
   for m,v in counts[p][c].items():assert summary['results'][p][c][m]['correct']==v
 out={'status':'PASS','runs':len(rows),'episodes':summary['episodes'],
      'tasks':len(groups),'hidden_predictions_checked':len(rows)*16,
      'hashes_checked':len(rows),'common_initial_groups':len(groups),
      'last_sha256':prev,'policy_totals':{p:counts[p]['all']['hidden9_score'] for p in POLICIES}}
 (folder/'audit_result.json').write_text(json.dumps(out,indent=2))
 print(json.dumps(out,indent=2))
 return out

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--folder',required=True);args=parser.parse_args();audit(args.folder)
