"""Post-confirmation statistical analysis only; does not influence candidate selection."""
import json,random,statistics
from pathlib import Path
from collections import defaultdict

def main():
 root=Path(__file__).resolve().parent
 rows=[json.loads(z) for z in (root/'confirmation/runs.jsonl').read_text().splitlines()]
 keyed=defaultdict(lambda:defaultdict(int))
 for r in rows:
  keyed[r['seed']][(r['policy'],r['category'])]+=r['hidden9_score']
 seeds=sorted(keyed)
 r=random.Random(120112)
 results={}
 contrasts=[('REUSE','TARGET_ONLY','related'),('REUSE','SHAM','related'),('REUSE','WRONG','related'),('REUSE','STRUCTURED','related'),('REUSE','TARGET_ONLY','unrelated')]
 for a,b,cat in contrasts:
  differences=[(keyed[s][a,cat]-keyed[s][b,cat])/16 for s in seeds]
  point=sum(differences)/len(differences)
  boots=[]
  for _ in range(10000):
   boots.append(sum(differences[r.randrange(len(differences))] for _ in differences)/len(differences))
  boots.sort();ci=[boots[250],boots[9750]]
  results[f'{a}_vs_{b}_{cat}']={'difference_percentage_points':round(point*100,4),
      'bootstrap_cluster_95pct_ci_pp':[round(t*100,4) for t in ci],
      'episodes_a_higher':sum(x>0 for x in differences),
      'episodes_tied':sum(x==0 for x in differences),
      'episodes_a_lower':sum(x<0 for x in differences)}
 result={'scope':'posthoc paired cluster-bootstrap, episode as unit, 10000 replicates, seed 120112',
         'n_episodes':len(seeds),'contrasts':results}
 (root/'E12_Posthoc_Statistics.json').write_text(json.dumps(result,indent=2))
 print(json.dumps(result,indent=2))

if __name__=='__main__':main()
