// ACE R4 v5. Research-only, deterministic, bounded directional meta-adaptation.
// Public synthetic development; no code execution from candidate parameters.
import {createHash} from 'node:crypto';
import {readFileSync,writeFileSync,existsSync} from 'node:fs';
import {pathToFileURL} from 'node:url';
import {features,trainInit} from './v2_study.mjs';
import {makeBank as makeSourceBank} from './v3_study.mjs';

const VERSION='ACE-R4-v5-direction-routing-public';
const N=32,D=20,SEEDS=[1301,1423,1559,1697],STEPS=[0,1,2,4,8],CAP=8;
const TRAIN_FAMILIES=['threshold','interval','alternating'];
const VALID_FAMILIES=['reverse_threshold','outside_interval','block_xor'];
const OOD_FAMILIES={rotating_stencil:12,change_point_parity:12,cyclic_xor_intervals:12,piecewise_modulo:12};
const LRS=[0.10,0.30],META_RATES=[0.15,0.5],META_ROUNDS=3,FD=0.15,BETA_LIMIT=1.25;
const ARMS=['scratch','nearest','joint','reptile','random_route','learned_static_route','learned_conditional_route'];
const PRIMARY={metric:'full_domain_balanced_accuracy_at_k4',min_absolute_gain:0.05,min_seed_wins:3,max_target_compute_ratio:1.5,max_extra_unqueried_brier:0.01};
const SHA=x=>createHash('sha256').update(JSON.stringify(x)).digest('hex');
function hashSeed(...parts){let x=2166136261>>>0;for(const c of parts.join('|')){x^=c.charCodeAt(0);x=Math.imul(x,16777619)>>>0;}return x||1;}
function rand(seed){let x=seed>>>0;return ()=>{x^=x<<13;x^=x>>>17;x^=x<<5;return (x>>>0)/4294967296;};}
function ri(r,lo,hi){return lo+Math.floor(r()*(hi-lo+1));}
function countBits(m){let n=0;for(let i=0;i<N;i++)n+=(m>>>i)&1;return n;}
function novelMask(f,r){let predicate;
 if(f==='rotating_stencil'){const p=ri(r,3,8),width=ri(r,1,p-1),phase=ri(r,0,p-1),twist=ri(r,1,p-1);predicate=x=>((x+phase+Math.floor(x/8)*twist)%p)<width;}
 else if(f==='change_point_parity'){const cut=ri(r,7,26),p=ri(r,2,4),q=ri(r,3,6),phase=ri(r,0,11);predicate=x=>x<cut?((x+phase)%p<Math.ceil(p/2)):((x+2*phase)%q<Math.ceil(q/2));}
 else if(f==='cyclic_xor_intervals'){const a=ri(r,0,31),b=ri(r,0,31),w1=ri(r,4,13),w2=ri(r,4,12);predicate=x=>(((x-a+64)%32)<w1)!==(((x-b+64)%32)<w2);}
 else if(f==='piecewise_modulo'){const cut=ri(r,8,24),p=ri(r,3,8),q=ri(r,4,9),a=ri(r,0,10),b=ri(r,0,10);predicate=x=>x<cut?((x+a)%p===0||((x+a)%p===1)):((x+b)%q>=Math.floor(q/2));}
 else throw Error('unknown OOD family');
 let m=0;for(let x=0;x<N;x++)if(predicate(x))m=(m|(1<<x))>>>0;
 return countBits(m)>=5&&countBits(m)<=27?m:null;
}
function bankForSeed(seed){const parent=makeSourceBank(seed),train=parent.train,validation=parent.validation,ood=[];
 const seen=new Set([...train,...validation].map(t=>t.mask));
 for(const [family,num] of Object.entries(OOD_FAMILIES)){let id=0,tries=0;while(id<num){if(++tries>100000)throw Error('bank exhaustion '+family);const m=novelMask(family,rand(hashSeed('v5',seed,family,tries)));if(m===null||seen.has(m))continue;seen.add(m);ood.push({family,id,mask:m});id++;}}
 return {train,validation,ood};
}
function label(t,x){if(!Number.isInteger(x)||x<0||x>=N)throw Error('invalid input');return (t.mask>>>x)&1;}
const PHI=Array.from({length:N},(_,x)=>features(x));
function sigmoid(z){return z>=0?1/(1+Math.exp(-z)):Math.exp(z)/(1+Math.exp(z));}
function group(j){return j<4?0:j<12?1:2;}
const MAP=[[0,1],[0,2],[1,0],[1,2],[2,0],[2,1]];
function queryOrder(task,seed){const a=Array.from({length:N},(_,x)=>x),r=rand(hashSeed('v5-blind-query',seed,task.family,task.id));for(let i=N-1;i>0;i--){const j=ri(r,0,i);[a[i],a[j]]=[a[j],a[i]];}return a.slice(0,CAP);}
function zeros(){return {feature_multiply:0,gradient_steps:0,route_ops:0,predictions:0,nearest_pairs:0};}
function predict(theta,x,work){let z=0;for(let j=0;j<D;j++)z+=theta[j]*PHI[x][j];if(work){work.feature_multiply+=D;work.predictions++;}return sigmoid(z);}
function directionalStep(theta,history,x,y,lr,beta,kind,work){const err=y-predict(theta,x,work),grad=PHI[x].map(v=>v*err);
 const averages=[0,0,0],cnt=[0,0,0];for(let j=0;j<D;j++){averages[group(j)]+=grad[j];cnt[group(j)]++;}for(let g=0;g<3;g++)averages[g]/=cnt[g];
 let adjusted=grad.slice();if(kind!=='none'){
  for(let j=0;j<D;j++){let add=0;for(let i=0;i<MAP.length;i++)if(MAP[i][0]===group(j)){
   const src=MAP[i][1],coherence=history.count?Math.tanh(5*averages[src]*history.mean[src]):0;
   const c=kind==='conditional'?coherence:1;
   add+=beta[i]*averages[src]*c;work.route_ops+=6;
  }adjusted[j]=Math.max(-3,Math.min(3,grad[j]+add));}
 }
 for(let j=0;j<D;j++)theta[j]+=lr*adjusted[j];
 for(let g=0;g<3;g++)history.mean[g]=(history.mean[g]*history.count+averages[g])/(history.count+1);
 history.count++;work.gradient_steps++;work.feature_multiply+=D;
}
function nearest(obs,x,work){if(!obs.length)return 0.5;let dist=N+1,yes=0,n=0;for(const [pos,y] of obs){const d=Math.abs(pos-x);work.nearest_pairs++;if(d<dist){dist=d;yes=y;n=1;}else if(d===dist){yes+=y;n++;}}return yes/n;}
function episode(task,arm,seed,cfg){if(!ARMS.includes(arm))throw Error('unknown arm');const work=zeros(),theta=(cfg.initial||Array(D).fill(0)).slice(),obs=[],history={mean:[0,0,0],count:0},positions=queryOrder(task,seed),by_k={};
 for(let k=0;k<=CAP;k++){
  if(STEPS.includes(k)){
   const known=new Map(obs);let positives=0,negatives=0,tp=0,tn=0,u=0,correct=0,brier=0;
   for(let x=0;x<N;x++){const y=label(task,x),p=known.has(x)?known.get(x):arm==='nearest'?nearest(obs,x,work):predict(theta,x,work);
    if(y){positives++;tp+=Number(p>=0.5);}else{negatives++;tn+=Number(p<0.5);}
    if(!known.has(x)){u++;correct+=Number((p>=0.5)===Boolean(y));brier+=(p-y)**2;}
   }
   by_k[k]={balanced_accuracy:(tp/positives+tn/negatives)/2,unqueried_accuracy:correct/u,unqueried_brier:brier/u};
  }
  if(k===CAP)break;
  const x=positions[k],y=label(task,x);obs.push([x,y]);
  if(arm!=='nearest'){
   const kind=arm==='learned_conditional_route'?'conditional':(arm==='learned_static_route'||arm==='random_route'?'static':'none');
   directionalStep(theta,history,x,y,cfg.lr,cfg.beta||Array(6).fill(0),kind,work);
  }
 }
 return {by_k,purchases:positions,work};
}
function summary(tasks,arm,seed,cfg){const eps=tasks.map(t=>episode(t,arm,seed,cfg)),by_k={},work=zeros();let first=0;
 for(const k of STEPS){by_k[k]={};for(const metric of ['balanced_accuracy','unqueried_accuracy','unqueried_brier'])by_k[k][metric]=eps.reduce((a,e)=>a+e.by_k[k][metric],0)/eps.length;}
 for(const e of eps){first+=STEPS.find(k=>e.by_k[k].balanced_accuracy>=.75)??9;for(const key of Object.keys(work))work[key]+=e.work[key];}
 return {tasks:tasks.length,target_purchases:tasks.length*CAP,mean_first_hit_right_censored_9:first/eps.length,work,by_k};
}
function objective(tasks,seed,lr,beta,kind){let loss=0,work=zeros();for(const task of tasks){const a=episode(task,kind==='conditional'?'learned_conditional_route':'learned_static_route',seed,{lr,beta});loss+=.5*(a.by_k[4].unqueried_brier+a.by_k[8].unqueried_brier);for(const k of Object.keys(work))work[k]+=a.work[k];}return {loss:loss/tasks.length,work};}
function optimize(tasks,seed,lr,outer,kind){let beta=Array(6).fill(0),calls=0,logical=0,trace=[];
 for(let round=0;round<META_ROUNDS;round++){const derivatives=[];
  for(let j=0;j<6;j++){const plus=beta.slice(),minus=beta.slice();plus[j]+=FD;minus[j]-=FD;
   const up=objective(tasks,seed,lr,plus,kind),down=objective(tasks,seed,lr,minus,kind);calls+=2;
   logical+=up.work.feature_multiply+up.work.route_ops+down.work.feature_multiply+down.work.route_ops;
   derivatives.push((up.loss-down.loss)/(2*FD));
  }
  beta=beta.map((b,i)=>Math.max(-BETA_LIMIT,Math.min(BETA_LIMIT,b-outer*derivatives[i])));
  trace.push({round,gradient:derivatives,beta:beta.slice()});
 }
 return {beta,objective_calls:calls,logical_meta_work:logical,trace};
}
function fit(bank,seed){let meta_work=0,objective_calls=0;const results={};
 for(const kind of ['static','conditional']){
  const trials=[];for(const lr of LRS)for(const outer of META_RATES){const res=optimize(bank.train,seed,lr,outer,kind);meta_work+=res.logical_meta_work;objective_calls+=res.objective_calls;
   const arm=kind==='static'?'learned_static_route':'learned_conditional_route',v=summary(bank.validation,arm,seed,{lr,beta:res.beta});
   trials.push({lr,outer,beta:res.beta,validation_balanced_k4:v.by_k[4].balanced_accuracy,validation_brier_k4:v.by_k[4].unqueried_brier,train_loss_trace:res.trace});
  }
  trials.sort((a,b)=>b.validation_balanced_k4-a.validation_balanced_k4||a.validation_brier_k4-b.validation_brier_k4||a.lr-b.lr||a.outer-b.outer);
  results[kind]={selected:trials[0],trials};
 }
 const baselineLr=LRS.map(lr=>({lr,s:summary(bank.validation,'scratch',seed,{lr}).by_k[4].balanced_accuracy})).sort((a,b)=>b.s-a.s||a.lr-b.lr)[0].lr;
 const pretrained={};for(const kind of ['joint','reptile']){
  const picks=[];for(const lr of LRS)for(const outer of (kind==='reptile'?[.15,.45]:[0])){const p=trainInit(bank.train,seed,kind,lr,outer);const val=summary(bank.validation,kind,seed,{lr,initial:p.theta});picks.push({lr,outer,initial:p.theta,validation_balanced_k4:val.by_k[4].balanced_accuracy,source_gradient_steps:p.work.gradient_steps});}
  picks.sort((a,b)=>b.validation_balanced_k4-a.validation_balanced_k4||a.lr-b.lr);pretrained[kind]=picks[0];
 }
 return {directional:results,scratch_lr:baselineLr,pretrained,meta_logical_work:meta_work,meta_objective_calls:objective_calls,source_unique_labels:bank.train.length*N,validation_unique_labels:bank.validation.length*N,source_fit_label_exposures:objective_calls*bank.train.length*N};
}
function freezeAll(){return {version:VERSION,n:N,d:D,seeds:SEEDS.slice(),steps:STEPS.slice(),cap:CAP,train_families:TRAIN_FAMILIES.slice(),validation_families:VALID_FAMILIES.slice(),ood_families:structuredClone(OOD_FAMILIES),lrs:LRS.slice(),meta_rates:META_RATES.slice(),meta_rounds:META_ROUNDS,finite_difference:FD,beta_limit:BETA_LIMIT,primary:structuredClone(PRIMARY),per_seed:SEEDS.map(seed=>{const b=bankForSeed(seed);return {seed,train_sha256:SHA(b.train),validation_sha256:SHA(b.validation),ood_sha256:SHA(b.ood),fit:fit(b,seed)};})};}
function scoreFrozen(f){const spec={version:VERSION,n:N,d:D,seeds:SEEDS,steps:STEPS,cap:CAP,train_families:TRAIN_FAMILIES,validation_families:VALID_FAMILIES,ood_families:OOD_FAMILIES,lrs:LRS,meta_rates:META_RATES,meta_rounds:META_ROUNDS,finite_difference:FD,beta_limit:BETA_LIMIT,primary:PRIMARY};for(const [key,value] of Object.entries(spec))if(SHA(f[key])!==SHA(value))throw Error('protocol mismatch '+key);
 if(f.per_seed?.length!==SEEDS.length)throw Error('seed count integrity');const per_seed=[];
 for(let i=0;i<SEEDS.length;i++){const seed=SEEDS[i],b=bankForSeed(seed),record=f.per_seed[i];if(record.seed!==seed||record.train_sha256!==SHA(b.train)||record.validation_sha256!==SHA(b.validation)||record.ood_sha256!==SHA(b.ood))throw Error('bank integrity');if(SHA(record.fit)!==SHA(fit(b,seed)))throw Error('fit integrity');
  const configs={scratch:{lr:record.fit.scratch_lr},nearest:{lr:0},joint:{lr:record.fit.pretrained.joint.lr,initial:record.fit.pretrained.joint.initial},reptile:{lr:record.fit.pretrained.reptile.lr,initial:record.fit.pretrained.reptile.initial},random_route:{lr:record.fit.directional.conditional.selected.lr,beta:[.4,-.4,.4,-.4,-.4,.4]},learned_static_route:{lr:record.fit.directional.static.selected.lr,beta:record.fit.directional.static.selected.beta},learned_conditional_route:{lr:record.fit.directional.conditional.selected.lr,beta:record.fit.directional.conditional.selected.beta}};
  const arms={};for(const arm of ARMS){arms[arm]={all_ood:summary(b.ood,arm,seed,configs[arm]),families:{}};for(const fam of Object.keys(OOD_FAMILIES))arms[arm].families[fam]=summary(b.ood.filter(t=>t.family===fam),arm,seed,configs[arm]);}
  per_seed.push({seed,arms});
 }
 const aggregate={};for(const arm of ARMS){aggregate[arm]={};for(const k of STEPS){aggregate[arm][k]={};for(const metric of ['balanced_accuracy','unqueried_accuracy','unqueried_brier'])aggregate[arm][k][metric]=per_seed.reduce((a,x)=>a+x.arms[arm].all_ood.by_k[k][metric],0)/SEEDS.length;}}
 const active='learned_conditional_route',best=ARMS.filter(x=>x!==active).sort((a,b)=>aggregate[b][4].balanced_accuracy-aggregate[a][4].balanced_accuracy)[0];
 const advantage=aggregate[active][4].balanced_accuracy-aggregate[best][4].balanced_accuracy,seed_wins=per_seed.filter(x=>x.arms[active].all_ood.by_k[4].balanced_accuracy>x.arms[best].all_ood.by_k[4].balanced_accuracy).length;
 const logical=x=>x.feature_multiply+x.route_ops+x.nearest_pairs;
 const budget=per_seed.reduce((s,x)=>s+logical(x.arms[active].all_ood.work),0)/per_seed.reduce((s,x)=>s+logical(x.arms.scratch.all_ood.work),0);
 const excessBrier=aggregate[active][4].unqueried_brier-aggregate[best][4].unqueried_brier;
 const passed=advantage>=PRIMARY.min_absolute_gain&&seed_wins>=PRIMARY.min_seed_wins&&budget<=PRIMARY.max_target_compute_ratio&&excessBrier<=PRIMARY.max_extra_unqueried_brier;
 return {version:VERSION+'-results',prescore_sha256:SHA(f),per_seed,aggregate,primary:{best_control:best,learned_balanced_k4:aggregate[active][4].balanced_accuracy,control_balanced_k4:aggregate[best][4].balanced_accuracy,advantage,seed_wins,target_work_ratio_vs_scratch:budget,extra_brier_vs_best:excessBrier,passed},status:'PUBLIC_DEVELOPMENT_UNSEALED_NOT_CONFIRMED'};
}
function checks(){const a=bankForSeed(SEEDS[0]);if(SHA(a)!==SHA(bankForSeed(SEEDS[0])))throw Error('nondeterministic bank');
 const seen=new Set();for(const arr of [a.train,a.validation,a.ood])for(const task of arr){if(seen.has(task.mask))throw Error('split overlap');seen.add(task.mask);}if(a.ood.length!==48)throw Error('OOD count');
 const sample=a.train[0],cfg={lr:.3,beta:[.5,-.2,.4,-.4,.3,.1]};for(const arm of ARMS){const ep=episode(sample,arm,SEEDS[0],cfg);if(SHA(ep)!==SHA(episode(sample,arm,SEEDS[0],cfg)))throw Error('episode nondeterminism');if(ep.purchases.length!==8||new Set(ep.purchases).size!==8)throw Error('purchase violation');}
 const all=ARMS.map(arm=>episode(sample,arm,SEEDS[0],cfg).purchases);if(!all.every(x=>SHA(x)===SHA(all[0])))throw Error('different target queries');
 const theta=Array(D).fill(0),h={mean:[0,0,0],count:0},w=zeros();directionalStep(theta,h,3,1,.3,cfg.beta,'conditional',w);directionalStep(theta,h,8,0,.3,cfg.beta,'conditional',w);if(!theta.every(Number.isFinite)||w.route_ops===0)throw Error('no safe directional update');
 const src=a.train,valid=a.validation,locked={train:src,validation:valid,ood:new Proxy([], {get(){throw Error('OOD accessed in training');}})};
 if(SHA(fit(locked,SEEDS[0]))!==SHA(fit(a,SEEDS[0])))throw Error('OOD leakage in fit');
 const f=freezeAll();f.per_seed[0].fit.directional.conditional.selected.beta[0]+=.001;try{scoreFrozen(f);throw Error('fit mutation accepted');}catch(e){if(e.message!=='fit integrity')throw e;}
 return {checks:7,source:a.train.length,validation:a.validation.length,ood:a.ood.length};
}
export {VERSION,N,D,SEEDS,STEPS,ARMS,PRIMARY,SHA,bankForSeed,label,queryOrder,directionalStep,episode,summary,objective,optimize,fit,freezeAll,scoreFrozen,checks};
if(process.argv[1]&&import.meta.url===pathToFileURL(process.argv[1]).href){const [cmd,input,output]=process.argv.slice(2);if(cmd==='test')console.log(JSON.stringify(checks()));else if(cmd==='freeze'){if(!input||existsSync(input))throw Error('freeze requires unused output');writeFileSync(input,JSON.stringify(freezeAll(),null,2)+'\n');console.log(SHA(JSON.parse(readFileSync(input,'utf8'))));}else if(cmd==='score'||cmd==='verify'){if(!input||!output)throw Error('input+output required');const o=scoreFrozen(JSON.parse(readFileSync(input,'utf8')));if(cmd==='score'){if(existsSync(output))throw Error('refuse result overwrite');writeFileSync(output,JSON.stringify(o,null,2)+'\n');console.log(JSON.stringify(o.primary));}else{if(SHA(o)!==SHA(JSON.parse(readFileSync(output,'utf8'))))throw Error('semantic replay mismatch');console.log('PASS semantic replay');}}else throw Error('usage: test|freeze FILE|score PRESCORE RESULT|verify PRESCORE RESULT');}
