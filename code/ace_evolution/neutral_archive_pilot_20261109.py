"""S2 public synthetic neutral archive pilot; prescore 568439bac8fb4bd30b0476a9e3cf67b3b8837ee3."""
import random,time,json
C=[(a,b) for a in range(-2,3) for b in range(-2,3)]
T=[c for c in C if c!=(0,0)]
TRAIN=[(1,1),(2,2)]
QUERY=(1,-1)
TEST=[(-3,2),(4,-1),(-2,-4),(3,5)]
def f(c,p):return c[0]*p[0]+c[1]*p[1]
def run():
 rows=[]; cpu=time.process_time(); nops=0
 for i,target in enumerate(T):
  labels=[f(target,p) for p in TRAIN]; q=f(target,QUERY)
  consistent=[c for c in C if [f(c,p) for p in TRAIN]==labels]
  start=consistent[0]
  for arm in ['archive','fixed_dsl','no_mutation','random','exhaustive']:
   if arm=='archive':
    neighbors=[(start[0]+d,start[1]-d) for d in (1,-1)]
    neighbors=[c for c in neighbors if c in C and c in consistent]
    proposals=[start]+neighbors
    pool=list(dict.fromkeys(proposals))[:2]
    evaluated=(proposals*25)[:25]
   elif arm=='fixed_dsl':
    evaluated=C[:];pool=[c for c in evaluated if c in consistent]
   elif arm=='no_mutation':
    evaluated=[start]*25;pool=[start]
   elif arm=='random':
    evaluated=C[:];random.Random(10000+i).shuffle(evaluated)
    pool=[c for c in evaluated if c in consistent]
   else:
    evaluated=C[:];pool=[c for c in evaluated if c in consistent]
   selected=min(pool,key=lambda c:(abs(f(c,QUERY)-q),C.index(c))) if pool else None
   correct=selected is not None and all(f(selected,p)==f(target,p) for p in TEST)
   nops+=len(evaluated)*6
   rows.append(dict(task=i,partition='development' if i<8 else 'evaluation',target=target,arm=arm,selected=selected,success=correct,train_fit=bool(pool),overfit=selected is not None and not correct,proposals=len(evaluated),unique_proposals=len(set(evaluated))))
 elapsed=time.process_time()-cpu
 summary={p:{a:{'solved':sum(x['success'] for x in rows if x['partition']==p and x['arm']==a),'overfit':sum(x['overfit'] for x in rows if x['partition']==p and x['arm']==a)} for a in ['archive','fixed_dsl','no_mutation','random','exhaustive']} for p in ['development','evaluation']}
 outside=[(1,1),(2,2)]+TEST
 return dict(protocol_commit='568439bac8fb4bd30b0476a9e3cf67b3b8837ee3',base_main='b81c076ef0f326331f81cb9c0678d6baa3b3250f',cpu_seconds=elapsed,proposal_evaluations=sum(x['proposals'] for x in rows),interpreted_arithmetic_ops=nops,train_labels=48,counterexample_labels=24,terminal_labels=96,outside_grammar_diagnostic_labels=6,outside_grammar_representable=any(all(f(c,p)==p[0]*p[1] for p in outside) for c in C),summary=summary,rows=rows)
if __name__=='__main__':print(json.dumps(run(),sort_keys=True,indent=2))
