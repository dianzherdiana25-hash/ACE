// ACE Research R4 v3: task-conditioned update mixtures, PUBLIC SYNTHETIC DEVELOPMENT.
// Node 20+, no external dependencies, no dynamic source execution, no paid oracle.
import {createHash} from 'node:crypto';
import {existsSync, readFileSync, writeFileSync} from 'node:fs';
import {pathToFileURL} from 'node:url';
import {features, trainInit} from './v2_study.mjs';

const VERSION='ACE-R4-v3-conditional-public';
const N=32, D=20, SEEDS=[503,607,701,809], STEPS=[0,1,2,4,8];
const SPLITS={train:{threshold:18,interval:24,alternating:24},validation:{reverse_threshold:10,outside_interval:10,block_xor:12},ood:{modxor:12,triple_band:12,bitparity:12,quadratic_mod:12}};
const LRS=[0.08,0.25,0.6], BANDWIDTHS=[2.5,5], GATE_LRS=[0.03,0.15], MIXES=[0.25,0.5,0.75];
const GATE_EPOCHS=10, GATE_DIM=6, QUERY_CAP=8, METRIC_HIT=0.75;
const ARMS=['scratch','kernel','nearest','fixed_mix','heuristic','reptile','conditional'];
function SHA(v){return createHash('sha256').update(JSON.stringify(v)).digest('hex');}
function seedHash(...parts){let v=2166136261>>>0;for(const c of parts.join('::')){v^=c.charCodeAt(0);v=Math.imul(v,16777619)>>>0;}return v||1;}
function rng(seed){let x=seed>>>0;return ()=>{x^=x<<13;x^=x>>>17;x^=x<<5;return (x>>>0)/4294967296;};}
function ri(r,lo,hi){return lo+Math.floor(r()*(hi-lo+1));}
function popcount(x){let n=0;while(x){n+=x&1;x>>>=1;}return n;}
function generateMask(f,r){let fn;
 if(f==='threshold'||f==='reverse_threshold'){const cut=ri(r,4,28);fn=x=>f==='threshold'?x>=cut:x<cut;}
 else if(f==='interval'||f==='outside_interval'){const a=ri(r,1,19),b=a+ri(r,5,11);fn=x=>f==='interval'?x>=a&&x<b:!(x>=a&&x<b);}
 else if(f==='alternating'){const block=ri(r,2,7),phase=ri(r,0,block*2-1),bit=ri(r,0,1);fn=x=>Math.floor((x+phase)/block)%2===bit;}
 else if(f==='block_xor'){const b=ri(r,2,6),a=ri(r,4,16),c=ri(r,17,29);fn=x=>(Math.floor(x/b)%2===1)!==(x>=a&&x<c);}
 else if(f==='modxor'){const a=ri(r,3,8),b=ri(r,4,11),shift=ri(r,0,20),pa=ri(r,1,a-1),pb=ri(r,1,b-1);fn=x=>(((x+shift)%a)<pa)!==(((x+3*shift)%b)<pb);}
 else if(f==='triple_band'){const bands=Array.from({length:3},()=>[ri(r,0,28),ri(r,2,6)]);fn=x=>bands.some(([a,w])=>x>=a&&x<a+w);}
 else if(f==='bitparity'){let m=ri(r,3,31),shift=ri(r,0,31),par=ri(r,0,1);if(popcount(m)<2)m|=7;fn=x=>popcount((x^shift)&m)%2===par;}
 else if(f==='quadratic_mod'){const p=ri(r,5,13),a=ri(r,1,p-1),b=ri(r,0,p-1),cut=ri(r,2,p-2);fn=x=>((x*x+a*x+b)%p)<cut;}
 else throw Error('unknown family '+f);
 let mask=0;for(let x=0;x<N;x++)if(fn(x))mask=(mask|(1<<x))>>>0;
 if(popcount(mask)<5||popcount(mask)>27)return null;
 return mask>>>0;
}
function makeBank(seed){const seen=new Set(),bank={train:[],validation:[],ood:[]};
 for(const [split,fs] of Object.entries(SPLITS))for(const [family,n] of Object.entries(fs)){
  let attempt=0;while(bank[split].filter(t=>t.family===family).length<n){
   if(++attempt>80000)throw Error('bank exhausted '+split+':'+family);
   const mask=generateMask(family,rng(seedHash(VERSION,seed,split,family,attempt)));
   if(mask===null||seen.has(mask))continue;
   seen.add(mask);bank[split].push({family,id:bank[split].filter(t=>t.family===family).length,mask});
  }
 }return bank;
}
function label(t,x){if(!Number.isInteger(x)||x<0||x>=N)throw Error('invalid point');return (t.mask>>>x)&1;}
function queryOrder(t,seed){const arr=Array.from({length:N},(_,i)=>i),r=rng(seedHash('r4v3query',seed,t.family,t.id));for(let i=N-1;i>0;i--){const j=ri(r,0,i);[arr[i],arr[j]]=[arr[j],arr[i]];}return arr.slice(0,QUERY_CAP);}
const PHI=Array.from({length:N},(_,x)=>features(x));
function sig(z){return z>=0?1/(1+Math.exp(-z)):Math.exp(z)/(1+Math.exp(z));}
function workZero(){return {source_feature_multiplies:0,target_feature_multiplies:0,target_kernel_pairs:0,target_gate_multiplies:0,target_gradient_steps:0,prediction_calls:0,meta_updates:0,meta_supervised_labels:0};}
function logistic(theta,x,work){let z=0;for(let i=0;i<D;i++)z+=theta[i]*PHI[x][i];if(work){work.target_feature_multiplies+=D;work.prediction_calls++;}return sig(z);}
function sgdUpdate(theta,x,y,lr,work){const p=logistic(theta,x,work),error=y-p;for(let i=0;i<D;i++)theta[i]+=lr*error*PHI[x][i];if(work){work.target_feature_multiplies+=D;work.target_gradient_steps++;}}
function nearest(obs,x,work){if(!obs.length)return 0.5;let d=N,n=0,total=0;for(const [pos,y] of obs){const dist=Math.abs(pos-x);if(work)work.target_kernel_pairs++;if(dist<d){d=dist;n=1;total=y;}else if(dist===d){n++;total+=y;}}return total/n;}
function kernel(obs,x,bandwidth,work){if(!obs.length)return 0.5;let mass=0.5,numerator=0.25;for(const [pos,y] of obs){const sim=Math.exp(-Math.abs(pos-x)/bandwidth);mass+=sim;numerator+=sim*y;if(work)work.target_kernel_pairs++;}return numerator/mass;}
function gateFeatures(obs,x,ps,pk){const count=obs.length,positive=obs.reduce((v,[,y])=>v+y,0),rate=count?positive/count:0.5;
 let transitions=0;const sorted=obs.slice().sort((a,b)=>a[0]-b[0]);for(let i=1;i<sorted.length;i++)transitions+=Number(sorted[i][1]!==sorted[i-1][1]);
 const distance=count?Math.min(...obs.map(([pos])=>Math.abs(pos-x))):N;
 return [1,count/8,Math.abs(rate-0.5)*2,count>1?transitions/(count-1):0,distance/N,Math.abs(pk-ps)];
}
function gateProbability(w,z,work){let logit=0;for(let j=0;j<GATE_DIM;j++)logit+=w[j]*z[j];if(work)work.target_gate_multiplies+=GATE_DIM;return sig(logit);}
function chooseProbability(arm,obs,x,theta,conf,work){
 if(arm==='nearest')return nearest(obs,x,work);
 const ps=logistic(theta,x,work);
 if(arm==='scratch'||arm==='reptile')return ps;
 const pk=kernel(obs,x,conf.bandwidth,work);
 if(arm==='kernel')return pk;
 if(arm==='fixed_mix')return conf.mix*pk+(1-conf.mix)*ps;
 const z=gateFeatures(obs,x,ps,pk),g=arm==='conditional'?gateProbability(conf.gate,z,work):sig(-1+2.0*z[2]+2*z[3]+z[4]);
 return g*pk+(1-g)*ps;
}
function episode(t,arm,seed,conf){const obs=[],theta=(conf.initial||Array(D).fill(0)).slice(),positions=queryOrder(t,seed),work=workZero(),by_k={};
 for(let k=0;k<=QUERY_CAP;k++){
  if(STEPS.includes(k)){
   let pcount=0,ncount=0,tp=0,tn=0,unqueried=0,correct=0,brier=0;
   const seen=new Map(obs);
   for(let x=0;x<N;x++){
    const truth=label(t,x),p=seen.has(x)?seen.get(x):chooseProbability(arm,obs,x,theta,conf,work);
    if(truth){pcount++;tp+=Number(p>=0.5);}else{ncount++;tn+=Number(p<0.5);}
    if(!seen.has(x)){unqueried++;correct+=Number((p>=0.5)===Boolean(truth));brier+=(p-truth)**2;}
   }
   by_k[k]={balanced_accuracy:(tp/pcount+tn/ncount)/2,unqueried_accuracy:correct/unqueried,unqueried_brier:brier/unqueried};
  }
  if(k===QUERY_CAP)break;
  const x=positions[k],y=label(t,x);obs.push([x,y]);if(arm!=='nearest'&&arm!=='kernel')sgdUpdate(theta,x,y,conf.lr,work);
 }
 return {by_k,purchases:positions,work};
}
function scoreTasks(tasks,arm,seed,conf){const out=tasks.map(t=>episode(t,arm,seed,conf)),by_k={};
 for(const k of STEPS){by_k[k]={};for(const m of ['balanced_accuracy','unqueried_accuracy','unqueried_brier'])by_k[k][m]=out.reduce((s,e)=>s+e.by_k[k][m],0)/out.length;}
 const work=workZero();let firstHit=0;for(const e of out){firstHit+=STEPS.find(k=>e.by_k[k].balanced_accuracy>=METRIC_HIT)??9;for(const key of Object.keys(work))work[key]+=e.work[key];}
 return {tasks:tasks.length,by_k,mean_hit_censored_9:firstHit/out.length,label_purchases:arm==='nearest'||arm==='kernel'||arm==='scratch'||arm==='reptile'||arm==='fixed_mix'||arm==='heuristic'||arm==='conditional'?tasks.length*QUERY_CAP:0,work};
}
function candidateTrace(seed,train,validation){const traces=[],fitted=[];
 // Every gate candidate gets exactly the same meta-task sequence. No OOD access.
 const support=train.map(t=>{const ps=queryOrder(t,seed),observations=ps.map(x=>[x,label(t,x)]);return {task:t,observations};});
 let cost=0,metaLabels=0;
 for(const lr of LRS)for(const bandwidth of BANDWIDTHS)for(const gate_lr of GATE_LRS){
  const theta=Array(GATE_DIM).fill(0);
  // Prebuild source support prefixes and corresponding SGD model for all four k values.
  const dataset=[];
  for(let i=0;i<support.length;i++){
   const t=train[i],obs=support[i].observations;
   for(const k of [1,2,4,8]){
    const ctx=obs.slice(0,k),model=Array(D).fill(0);
    for(const [x,y] of ctx)sgdUpdate(model,x,y,lr,null);
    const seen=new Set(ctx.map(e=>e[0]));
    for(let x=0;x<N;x++)if(!seen.has(x)){
     const ps=logistic(model,x,null),pk=kernel(ctx,x,bandwidth,null),z=gateFeatures(ctx,x,ps,pk);
     dataset.push({z,delta:pk-ps,ps,y:label(t,x)});
    }
   }
  }
  const meta_supervised_labels=new Set(train.map(t=>t.family+':'+t.id)).size*N;
  for(let epoch=0;epoch<GATE_EPOCHS;epoch++){
   const grad=Array(GATE_DIM).fill(0);
   for(const e of dataset){const g=gateProbability(theta,e.z,null),p=e.ps+g*e.delta,scale=2*(p-e.y)*e.delta*g*(1-g);
    for(let j=0;j<GATE_DIM;j++)grad[j]+=scale*e.z[j];
   }
   for(let j=0;j<GATE_DIM;j++)theta[j]-=gate_lr*(grad[j]/dataset.length+0.005*theta[j]);
   cost+=dataset.length*(GATE_DIM+4);
  }
  metaLabels+=meta_supervised_labels;
  const conf={lr,bandwidth,gate:theta};
  const val=scoreTasks(validation,'conditional',seed,conf);
  const metric=val.by_k[4].balanced_accuracy;
  fitted.push({lr,bandwidth,gate_lr,gate:theta,validation_k4:metric,validation_brier_k4:val.by_k[4].unqueried_brier});
  traces.push({lr,bandwidth,gate_lr,validation_k4:metric,validation_brier_k4:val.by_k[4].unqueried_brier});
 }
 fitted.sort((a,b)=>b.validation_k4-a.validation_k4||a.validation_brier_k4-b.validation_brier_k4||a.lr-b.lr||a.bandwidth-b.bandwidth||a.gate_lr-b.gate_lr);
 return {chosen:fitted[0],trace:traces,meta_training_logical_ops:cost,meta_supervised_source_label_exposures:metaLabels,unique_source_labels:train.length*N};
}
function fit(bank,seed){
 const meta=candidateTrace(seed,bank.train,bank.validation);
 const scratch=LRS.map(lr=>({lr,score:scoreTasks(bank.validation,'scratch',seed,{lr,bandwidth:2.5}).by_k[4].balanced_accuracy})).sort((a,b)=>b.score-a.score||a.lr-b.lr)[0];
 const kern=BANDWIDTHS.map(bandwidth=>({bandwidth,score:scoreTasks(bank.validation,'kernel',seed,{lr:0.25,bandwidth}).by_k[4].balanced_accuracy})).sort((a,b)=>b.score-a.score||a.bandwidth-b.bandwidth)[0];
 const fixed=[];for(const lr of LRS)for(const bandwidth of BANDWIDTHS)for(const mix of MIXES){const conf={lr,bandwidth,mix};fixed.push({...conf,score:scoreTasks(bank.validation,'fixed_mix',seed,conf).by_k[4].balanced_accuracy});}
 fixed.sort((a,b)=>b.score-a.score||a.lr-b.lr||a.bandwidth-b.bandwidth||a.mix-b.mix);
 // Reptile is independently fit on the new source bank, then selected on validation.
 const reps=[];for(const lr of LRS)for(const outer of [0.12,0.40]){const t=trainInit(bank.train,seed,'reptile',lr,outer);const val=scoreTasks(bank.validation,'reptile',seed,{lr,initial:t.theta});reps.push({lr,outer,theta:t.theta,validation_k4:val.by_k[4].balanced_accuracy,source_gradient_steps:t.work.gradient_steps});}
 reps.sort((a,b)=>b.validation_k4-a.validation_k4||a.lr-b.lr||a.outer-b.outer);
 return {conditional:meta.chosen,conditional_trace:meta.trace,meta_training_logical_ops:meta.meta_training_logical_ops,meta_label_exposures:meta.meta_supervised_source_label_exposures,source_unique_labels:meta.unique_source_labels,scratch_lr:scratch.lr,kernel_bandwidth:kern.bandwidth,fixed_mix:fixed[0],reptile:reps[0],reptile_candidates:reps.map(({lr,outer,validation_k4,source_gradient_steps})=>({lr,outer,validation_k4,source_gradient_steps}))};
}
function freezeAll(){return {version:VERSION,seeds:[...SEEDS],N,D,steps:[...STEPS],splits:structuredClone(SPLITS),lrs:[...LRS],bandwidths:[...BANDWIDTHS],gate_lrs:[...GATE_LRS],mixes:[...MIXES],gate_epochs:GATE_EPOCHS,query_cap:QUERY_CAP,per_seed:SEEDS.map(seed=>{const bank=makeBank(seed);return {seed,train_sha256:SHA(bank.train),validation_sha256:SHA(bank.validation),ood_sha256:SHA(bank.ood),fit:fit(bank,seed)};})};}
function scoreFrozen(frozen){
 if(frozen.version!==VERSION||frozen.N!==N||frozen.D!==D||SHA(frozen.seeds)!==SHA(SEEDS)||SHA(frozen.steps)!==SHA(STEPS)||SHA(frozen.splits)!==SHA(SPLITS)||SHA(frozen.lrs)!==SHA(LRS)||SHA(frozen.bandwidths)!==SHA(BANDWIDTHS)||SHA(frozen.gate_lrs)!==SHA(GATE_LRS)||SHA(frozen.mixes)!==SHA(MIXES)||frozen.gate_epochs!==GATE_EPOCHS||frozen.query_cap!==QUERY_CAP)throw Error('protocol mismatch');
 if(!Array.isArray(frozen.per_seed)||frozen.per_seed.length!==SEEDS.length)throw Error('seed count');
 const per_seed=[];
 for(let i=0;i<SEEDS.length;i++){
  const f=frozen.per_seed[i],seed=SEEDS[i],bank=makeBank(seed);
  if(f.seed!==seed||f.train_sha256!==SHA(bank.train)||f.validation_sha256!==SHA(bank.validation)||f.ood_sha256!==SHA(bank.ood))throw Error('bank integrity');
  if(SHA(f.fit)!==SHA(fit(bank,seed)))throw Error('fit integrity');
  const m=f.fit,configs={scratch:{lr:m.scratch_lr},kernel:{lr:0.25,bandwidth:m.kernel_bandwidth},nearest:{lr:0,bandwidth:m.kernel_bandwidth},fixed_mix:m.fixed_mix,heuristic:{lr:m.scratch_lr,bandwidth:m.kernel_bandwidth},reptile:{lr:m.reptile.lr,initial:m.reptile.theta},conditional:m.conditional};
  const arms={};for(const arm of ARMS){arms[arm]={all_ood:scoreTasks(bank.ood,arm,seed,configs[arm]),families:{}};for(const family of Object.keys(SPLITS.ood))arms[arm].families[family]=scoreTasks(bank.ood.filter(t=>t.family===family),arm,seed,configs[arm]);}
  per_seed.push({seed,arms});
 }
 const aggregate={};for(const arm of ARMS){aggregate[arm]={};for(const k of STEPS){aggregate[arm][k]={};for(const metric of ['balanced_accuracy','unqueried_accuracy','unqueried_brier'])aggregate[arm][k][metric]=per_seed.reduce((s,e)=>s+e.arms[arm].all_ood.by_k[k][metric],0)/SEEDS.length;}}
 const best_control=Math.max(...ARMS.filter(a=>a!=='conditional').map(a=>aggregate[a][4].balanced_accuracy));const gain=aggregate.conditional[4].balanced_accuracy-best_control;
 return {version:VERSION+'-scored',freeze_sha256:SHA(frozen),ood_task_count:SEEDS.length*Object.values(SPLITS.ood).reduce((a,b)=>a+b,0),per_seed,aggregate,primary:{metric:'full_domain_balanced_accuracy_k4',conditional:aggregate.conditional[4].balanced_accuracy,best_control,gain,threshold:0.05,pass:gain>=.05},scientific_status:'PUBLIC_SYNTHETIC_DEVELOPMENT_ONLY'};
}
function selfCheck(){const seed=SEEDS[0],bank=makeBank(seed);if(SHA(bank)!==SHA(makeBank(seed)))throw Error('nondeterministic bank');
 const seen=new Set();for(const [split,families] of Object.entries(SPLITS))for(const [family,num] of Object.entries(families)){
  const tasks=bank[split].filter(t=>t.family===family);if(tasks.length!==num)throw Error('family mismatch');for(const task of tasks){if(seen.has(task.mask))throw Error('split leakage');seen.add(task.mask);}}
 const ob={train:bank.train,validation:bank.validation,ood:new Proxy([],{get(){throw Error('OOD read during fit');}})};
 if(SHA(fit(ob,seed))!==SHA(fit(bank,seed)))throw Error('OOD fitting leak');
 const t=bank.validation[0];for(const arm of ARMS){const conf={lr:0.25,bandwidth:2.5,mix:0.5,gate:Array(GATE_DIM).fill(0)};const a=episode(t,arm,seed,conf);if(a.purchases.length!==8||new Set(a.purchases).size!==8)throw Error('invalid query cap');if(SHA(a)!==SHA(episode(t,arm,seed,conf)))throw Error('nondeterministic episode');}
 const frozen=freezeAll();if(SHA(frozen)!==SHA(freezeAll()))throw Error('nondeterministic freeze');
 const f=structuredClone(frozen);f.per_seed[0].fit.conditional.gate[0]+=0.5;try{scoreFrozen(f);throw Error('fit forgery accepted');}catch(e){if(e.message!=='fit integrity')throw e;}
 return {pass:true,checks:7,train:bank.train.length,validation:bank.validation.length,ood:bank.ood.length,unique_masks:seen.size};
}
export {VERSION,N,D,SEEDS,STEPS,SPLITS,SHA,makeBank,label,queryOrder,features,gateFeatures,gateProbability,episode,scoreTasks,fit,freezeAll,scoreFrozen,selfCheck};
if(process.argv[1]&&import.meta.url===pathToFileURL(process.argv[1]).href){const [action,src,dst]=process.argv.slice(2);
 if(action==='test')console.log(JSON.stringify(selfCheck()));
 else if(action==='freeze'){if(!src||existsSync(src))throw Error('freeze requires unused output path');writeFileSync(src,JSON.stringify(freezeAll(),null,2)+'\n');console.log('freeze',SHA(JSON.parse(readFileSync(src,'utf8'))));}
 else if(action==='score'||action==='verify'){if(!src||!dst)throw Error('requires prescore and result paths');const result=scoreFrozen(JSON.parse(readFileSync(src,'utf8')));if(action==='score'){if(existsSync(dst))throw Error('refuse overwrite result');writeFileSync(dst,JSON.stringify(result,null,2)+'\n');console.log('result',JSON.stringify(result.primary));}else{if(SHA(result)!==SHA(JSON.parse(readFileSync(dst,'utf8'))))throw Error('semantic replay mismatch');console.log('PASS semantic replay');}}
 else throw Error('command: test|freeze FILE|score FREEZE RESULT|verify FREEZE RESULT');
}
