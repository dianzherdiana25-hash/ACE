"""Public synthetic S3 v4: see docs/research/generalization/s3_v4_preregistration.md."""
import json,random,time
TRIALS=range(6000,6024)
EDGES={'chain':[(0,1),(1,2),(2,3),(3,4)],'star':[(0,1),(0,2),(0,3),(0,4)],'branch':[(0,1),(0,2),(1,3),(2,4)]}
CANDIDATES=[('xor',mask,bias) for mask in range(32) for bias in (0,1)]+[('marker',0,0),('edge',0,0),('constant',0,0)]
def rows(trial,split,n,topology,fidelity,random_labels=False):
 r=random.Random(100000*trial+split);out=[]
 for _ in range(n):
  bits=tuple(r.randrange(2) for _ in range(5));true=sum(bits)%2
  marker=true if r.random()<fidelity else 1-true
  edge=sum(bits[a]*bits[b] for a,b in EDGES[topology])%2
  label=r.randrange(2) if random_labels else true
  out.append((bits,marker,edge,label))
 return out
def pred(c,row):
 kind,mask,bias=c;bits,marker,edge,_=row
 if kind=='xor':return (sum(bits[i] for i in range(5) if mask>>i&1)+bias)%2
 return {'marker':marker,'edge':edge,'constant':0}[kind]
def cost(c):return c[1].bit_count()+c[2] if c[0]=='xor' else 1
def choose(train,reverse=False):
 order=list(reversed(CANDIDATES)) if reverse else CANDIDATES
 rank=sorted((sum(pred(c,x)!=x[3] for x in train),cost(c),i,c) for i,c in enumerate(order))
 return (None if rank[0][0]>3 or rank[0][0]==rank[1][0] else rank[0][3]),rank[0][0]
def run():
 start=time.process_time();all_rows=[]
 for seed in TRIALS:
  common=rows(seed,11,32,'chain',.95)
  arms={'single':common+rows(seed,13,32,'chain',.95),'dual':common+rows(seed,17,32,'star',.95)}
  test=rows(seed,29,128,'branch',.10);neg=rows(seed,41,128,'branch',.10,True)
  counter=next((i for i,x in enumerate(test) if x[1]!=x[3]),None)
  assert counter is not None
  oracle=min(sum(pred(c,x)!=x[3] for x in test) for c in CANDIDATES)
  record={'seed':seed,'reachable_marker_counterexample_index':counter,'arms':{}}
  for arm,train in arms.items():
   selected,train_error=choose(train)
   inverted,_=choose([(b,m,e,1-y) for b,m,e,y in train])
   reverse,_=choose(train,True)
   permuted=[(b,m,e,1-y) for b,m,e,y in test]
   # Selection API takes source rows only; test label permutation cannot enter it.
   leak_changed=choose(train)[0]!=selected
   assert len(permuted)==len(test)
   errors=sum(pred(selected,x)!=x[3] for x in test) if selected else None
   neg_errors=sum(pred(selected,x)!=x[3] for x in neg) if selected else None
   record['arms'][arm]={'selection':str(selected) if selected else None,'train_errors':train_error,'branch_errors':errors,'random_label_errors':neg_errors,'false_accept':int(errors is not None and errors>12),'abstain':int(selected is None),'regret':errors-oracle if errors is not None else None,'penalized_regret':(errors if errors is not None else 128)-oracle,'inverted_source_selection':str(inverted) if inverted else None,'reversed_tie_order_selection':str(reverse) if reverse else None,'leakage_sentinel_changed':leak_changed}
  all_rows.append(record)
 summary={}
 for arm in ('single','dual'):
  arr=[r['arms'][arm] for r in all_rows];obs=[x['regret'] for x in arr if x['regret'] is not None]
  summary[arm]={'false_accept':sum(x['false_accept'] for x in arr),'abstain':sum(x['abstain'] for x in arr),'mean_regret_nonabstain':sum(obs)/len(obs) if obs else None,'mean_penalized_regret':sum(x['penalized_regret'] for x in arr)/24,'random_label_mean_errors_nonabstain':sum(x['random_label_errors'] for x in arr if x['random_label_errors'] is not None)/len(obs) if obs else None,'inversion_changed':sum(x['selection']!=x['inverted_source_selection'] for x in arr),'order_changed':sum(x['selection']!=x['reversed_tie_order_selection'] for x in arr),'leakage_sentinel_failures':sum(x['leakage_sentinel_changed'] for x in arr)}
 s,d=summary['single'],summary['dual']
 accepted=s['false_accept']-d['false_accept']>=4 and d['abstain']<=12 and d['mean_penalized_regret']<=s['mean_penalized_regret']
 return {'protocol_commit':'ace6dcea813f880a73dced8695e4d9b3dc6ef529','seed_range':[6000,6023],'trials':24,'selection_labels_per_arm_per_trial':64,'selection_label_presentations_total':3072,'unique_source_rows_total':2304,'evaluation_labels_reporting_only':3072,'random_label_negative_control_labels':3072,'candidate_count':67,'candidate_row_evaluations_selection':617472,'candidate_row_evaluations_oracle_reporting':205824,'cpu_seconds':round(time.process_time()-start,6),'summary':summary,'decision':'ACCEPT' if accepted else 'REJECT','rows':all_rows}
if __name__=='__main__':print(json.dumps(run(),sort_keys=True,indent=2))
