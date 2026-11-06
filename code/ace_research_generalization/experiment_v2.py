"""S3 v2 preregistered public synthetic development; Python stdlib only."""
import json,random,time
NAMES=('marker','edge','bit0','constant')
EDGES={'chain':((0,1),(1,2),(2,3),(3,4)),'star':((0,1),(0,2),(0,3),(0,4)),'branch':((0,1),(0,2),(1,3),(2,4))}
def cases(n,topology,fidelity,seed):
 r=random.Random(seed);out=[]
 for _ in range(n):
  b=tuple(r.randrange(2) for _ in range(5));y=sum(b)%2
  m=y if r.random()<fidelity else 1-y
  e=sum(b[a]*b[c] for a,c in EDGES[topology])%2
  out.append((b,y,m,e))
 return out
def prediction(name,row):
 b,y,m,e=row
 return {'marker':m,'edge':e,'bit0':b[0],'constant':0}[name]
def errors(name,rows):return sum(prediction(name,row)!=row[1] for row in rows)
def baseline(rows):return min(NAMES,key=lambda n:(errors(n,rows),NAMES.index(n)))
def intervention(a,b):
 eligible=[n for n in NAMES if errors(n,a)<=12 and errors(n,b)<=12]
 return min(eligible,key=lambda n:(errors(n,a)+errors(n,b),NAMES.index(n))) if eligible else None
def run():
 start=time.process_time();trials=[]
 for i in range(24):
  s=51000+11*i
  train=cases(64,'chain',.95,s);a=cases(32,'chain',.95,s+1);b=cases(32,'star',.05,s+2)
  test=cases(128,'branch',.10,s+3);noise=cases(32,'star',.5,s+4)
  p=baseline(train);q=intervention(a,b);negative=intervention(a,noise)
  inverted=[(bits,1-y,m,e) for bits,y,m,e in test]
  assert baseline(train)==p and intervention(a,b)==q
  assert len({s,s+1,s+2,s+3,s+4})==5
  assert any(prediction('marker',r)!=r[1] for r in test)
  oracle=min(errors(n,test) for n in NAMES)
  trials.append({'trial':i,'seed':s,'baseline':p,'intervention':q,'negative_no_signal':negative,
   'baseline_errors':errors(p,test),'intervention_errors':errors(q,test) if q else None,
   'baseline_false_accept':int(errors(p,test)>32),'intervention_false_accept':int(q is not None and errors(q,test)>32),
   'abstain':int(q is None),'oracle_errors':oracle,'baseline_regret':errors(p,test)-oracle,
   'intervention_regret':errors(q,test)-oracle if q else None,
   'counterexample_index':next(j for j,r in enumerate(test) if prediction('marker',r)!=r[1]),
   'inverted_test_diagnostic_marker_errors':errors('marker',inverted)})
 sums={k:sum(t[k] for t in trials) for k in ('baseline_false_accept','intervention_false_accept','abstain')}
 return {'protocol':'s3_intervention_v2','status':'PUBLIC_DEVELOPMENT_NOT_CONFIRMATORY','trials':trials,'summary':sums,
 'hypothesis_accepted':sums['intervention_false_accept']<=sums['baseline_false_accept']-6 and sums['abstain']<=12,
 'selection_labels_per_method_per_trial':64,'evaluation_labels_per_trial':128,
 'selection_candidate_example_comparisons_per_method_per_trial':256,
 'total_selection_labels_per_method':1536,'total_reporting_evaluation_labels':3072,
 'total_selection_candidate_example_comparisons_per_method':6144,
 'additional_negative_control_labels':768,'cpu_seconds':round(time.process_time()-start,6)}
if __name__=='__main__':print(json.dumps(run(),sort_keys=True,indent=2))
