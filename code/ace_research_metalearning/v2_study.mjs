// ACE Research R4 v2: disjoint-family first-order meta-initialization experiment.
// PUBLIC DEVELOPMENT, stdlib Node 20+, no hidden or paid evaluator.
import {createHash} from 'node:crypto';
import {existsSync, readFileSync, writeFileSync} from 'node:fs';
import {pathToFileURL} from 'node:url';

const VERSION='ACE-R4-v2-public';
const N=32, D=20, STEPS=[0,1,2,4,8], SEEDS=[101,211,307,401];
const SPLITS={train:{threshold:24,interval:24},validation:{reverse_threshold:12,outside_interval:12},ood:{periodic:12,two_interval:12,parity_band:12,sparse:12}};
const LR=[0.05,0.15,0.40], OUTER=[0.12,0.40], EPOCHS=8, SUPPORT=8, HIT=.75;
const ARMS=['scratch','static_transfer','pretrained_finetune','reptile','nearest'];
const SHA=x=>createHash('sha256').update(JSON.stringify(x)).digest('hex');
function seedHash(...xs){let h=2166136261>>>0;for(const c of xs.join('::')){h^=c.charCodeAt(0);h=Math.imul(h,16777619)>>>0;}return h||1;}
function rng(s){let a=s>>>0;return ()=>{a^=a<<13;a^=a>>>17;a^=a<<5;return (a>>>0)/4294967296;};}
function ri(r,lo,hi){return lo+Math.floor(r()*(hi-lo+1));}
function generateMask(f,r){let predicate;
 if(f==='threshold'||f==='reverse_threshold'){const c=ri(r,4,28);predicate=x=>f==='threshold'?x>=c:x<c;}
 else if(f==='interval'||f==='outside_interval'){const a=ri(r,2,18),b=a+ri(r,5,12);predicate=x=>f==='interval'?x>=a&&x<b:!(x>=a&&x<b);}
 else if(f==='periodic'){const p=ri(r,3,8),phase=ri(r,0,p-1),w=ri(r,1,p-1);predicate=x=>((x-phase+N*p)%p)<w;}
 else if(f==='two_interval'){const a=ri(r,1,9),b=ri(r,19,25),wa=ri(r,3,7),wb=ri(r,3,6);predicate=x=>(x>=a&&x<a+wa)||(x>=b&&x<b+wb);}
 else if(f==='parity_band'){const a=ri(r,2,12),b=a+ri(r,10,17),flip=ri(r,0,1),mod=ri(r,2,4);predicate=x=>((x>=a&&x<b)?1:0) !== ((Math.floor(x/mod)+flip)%2===1?1:0);}
 else if(f==='sparse'){const selected=new Set();while(selected.size<4)selected.add(ri(r,1,30));predicate=x=>selected.has(x);}
 else throw Error('unknown family '+f);
 let bits=0;for(let x=0;x<N;x++)if(predicate(x))bits=(bits|(1<<x))>>>0;return bits>>>0;
}
function makeBank(seed){const taken=new Set(), bank={train:[],validation:[],ood:[]};
 for(const [split,fs] of Object.entries(SPLITS))for(const [family,n] of Object.entries(fs)){
  let i=0,attempt=0;while(i<n){if(++attempt>100000)throw Error('bank exhaustion');const mask=generateMask(family,rng(seedHash('v2',seed,split,family,attempt)));const key=mask.toString(16);
   if(mask===0||mask===0xffffffff||taken.has(key))continue;taken.add(key);bank[split].push({family,id:i,mask});i++;}
 }return bank;
}
function label(task,x){if(!Number.isInteger(x)||x<0||x>=N)throw Error('x out of domain');return (task.mask>>>x)&1;}
function shufflePositions(seed){const a=Array.from({length:N},(_,i)=>i),r=rng(seed);for(let i=N-1;i>0;i--){const j=ri(r,0,i);[a[i],a[j]]=[a[j],a[i]];}return a;}
function sourceExamples(task,seed){return shufflePositions(seedHash('source',seed,task.family,task.id)).slice(0,SUPPORT).map(x=>[x,label(task,x)]);}
function targetPositions(task,seed){return shufflePositions(seedHash('target',seed,task.family,task.id)).slice(0,8);}
function features(x){const t=(x-(N-1)/2)/((N-1)/2);const v=[1,t,t*t,t*t*t];for(let k=1;k<=4;k++){v.push(Math.sin(2*Math.PI*k*x/N),Math.cos(2*Math.PI*k*x/N));}for(let i=0;i<8;i++)v.push(Math.max(0,1-Math.abs(x-(i+.5)*N/8)/(N/4)));if(v.length!==D)throw Error('feature dimension');return v;}
const PHI=Array.from({length:N},(_,x)=>features(x));
function sigmoid(z){if(z>=0){const e=Math.exp(-z);return 1/(1+e);}const e=Math.exp(z);return e/(1+e);}
function predict(theta,x,work){if(work)work.predictions++;let z=0;const p=PHI[x];for(let j=0;j<D;j++)z+=theta[j]*p[j];if(work)work.feature_multiplies+=D;return sigmoid(z);}
function update(theta,x,y,lr,work){const p=predict(theta,x,work),e=y-p,phi=PHI[x];for(let j=0;j<D;j++)theta[j]+=lr*e*phi[j];if(work){work.gradient_steps++;work.feature_multiplies+=D;}return theta;}
function adapted(start,examples,lr,work){const theta=start.slice();for(const [x,y] of examples)update(theta,x,y,lr,work);return theta;}
function nearestProb(observations,x,work){if(!observations.length)return .5;let best=N+1,sum=0,n=0;for(const [pos,y] of observations){const d=Math.abs(pos-x);if(work)work.nearest_pairs++;if(d<best){best=d;sum=y;n=1;}else if(d===best){sum+=y;n++;}}return sum/n;}
function workZero(){return {gradient_steps:0,feature_multiplies:0,predictions:0,nearest_pairs:0};}
function trainInit(tasks,seed,method,lr,outer){const t=Array(D).fill(0),work=workZero();let labelExposures=0;
 const sets=tasks.map(task=>sourceExamples(task,seed));labelExposures=sets.reduce((a,v)=>a+v.length,0);
 for(let ep=0;ep<EPOCHS;ep++)for(let i=0;i<tasks.length;i++){
  const idx=(i+ep*17)%tasks.length;const ex=sets[idx];
  if(method==='joint'){for(const [x,y] of ex)update(t,x,y,lr,work);}
  else if(method==='reptile'){const child=adapted(t,ex,lr,work);for(let j=0;j<D;j++)t[j]+=outer*(child[j]-t[j]);work.feature_multiplies+=D;}
  else throw Error('bad training method');
 }return {theta:t,work,labelExposures};
}
function evaluate(task,arm,theta,lr,seed){const work=workZero(),query=targetPositions(task,seed),observations=[],byK={};
 for(let k=0;k<=8;k++){
  if(STEPS.includes(k)){
   let correct=0,unqueried=0,brier=0,tp=0,tn=0,pos=0,neg=0;
   const seen=new Map(observations);
   for(let x=0;x<N;x++){
    const y=label(task,x);let p;
    if(seen.has(x))p=seen.get(x);
    else if(arm==='nearest')p=nearestProb(observations,x,work);
    else p=predict(theta,x,work);
    if(!seen.has(x)){correct+=Number((p>=.5)===Boolean(y));unqueried++;brier+=(p-y)**2;}
    if(y){pos++;tp+=Number(p>=.5);}else{neg++;tn+=Number(p<.5);}
   }
   byK[k]={unqueried_accuracy:correct/unqueried,unqueried_brier:brier/unqueried,balanced_accuracy:(tp/pos+tn/neg)/2};
  }
  if(k===8)break;
  if(arm==='static_transfer')continue;
  const x=query[k],y=label(task,x);observations.push([x,y]);
  if(arm!=='nearest')update(theta,x,y,lr,work);
 }
 return {byK,work,purchased:observations.map(e=>e[0])};
}
function scoreTasks(tasks,arm,trained,lr,seed){const results=tasks.map(task=>evaluate(task,arm,(trained||Array(D).fill(0)).slice(),lr,seed));const byK={},work=workZero();
 for(const k of STEPS){byK[k]={};for(const m of ['unqueried_accuracy','unqueried_brier','balanced_accuracy'])byK[k][m]=results.reduce((v,e)=>v+e.byK[k][m],0)/results.length;}
 let censored=0,purchases=0;
 for(const e of results){censored+=STEPS.find(k=>e.byK[k].balanced_accuracy>=HIT)??9;purchases+=e.purchased.length;for(const key of Object.keys(work))work[key]+=e.work[key];}
 return {tasks:tasks.length,byK,mean_first_hit_censored_at_9:censored/results.length,target_label_purchases:purchases,work};
}
function fit(bank,seed){const candidates=[];for(const method of ['reptile','joint'])for(const lr of LR)for(const outer of method==='reptile'?OUTER:[0]){
 const trained=trainInit(bank.train,seed,method,lr,outer),validation=scoreTasks(bank.validation,method==='reptile'?'reptile':'pretrained_finetune',trained.theta,lr,seed);
 const val=(validation.byK[2].balanced_accuracy+validation.byK[4].balanced_accuracy)/2;
 candidates.push({method,lr,outer,score:val,trained});
 }
 const best={};for(const method of ['reptile','joint']){const sorted=candidates.filter(c=>c.method===method).sort((a,b)=>b.score-a.score||a.lr-b.lr||a.outer-b.outer);best[method]=sorted[0];}
 const baselineLR=LR.map(lr=>({lr,score:(scoreTasks(bank.validation,'scratch',null,lr,seed).byK[2].balanced_accuracy+scoreTasks(bank.validation,'scratch',null,lr,seed).byK[4].balanced_accuracy)/2})).sort((a,b)=>b.score-a.score||a.lr-b.lr)[0];
 const trainingWork=workZero();for(const c of candidates)for(const key of Object.keys(trainingWork))trainingWork[key]+=c.trained.work[key];
 return {scratch_lr:baselineLR.lr,chosen:Object.fromEntries(Object.entries(best).map(([k,c])=>[k,{lr:c.lr,outer:c.outer,validation_balanced:c.score,theta:c.trained.theta}])),candidate_trace:candidates.map(c=>({method:c.method,lr:c.lr,outer:c.outer,validation_balanced:c.score,training_gradients:c.trained.work.gradient_steps})),training_work_all_candidates:trainingWork,source_unique_label_exposures:bank.train.length*SUPPORT,validation_unique_label_exposures:bank.validation.length*8};
}
function freezeAll(){return {protocol:VERSION,N,D,STEPS:[...STEPS],SEEDS:[...SEEDS],SPLITS:structuredClone(SPLITS),LR:[...LR],OUTER:[...OUTER],EPOCHS,SUPPORT,HIT,per_seed:SEEDS.map(seed=>{const bank=makeBank(seed);return {seed,train_sha256:SHA(bank.train),validation_sha256:SHA(bank.validation),ood_sha256:SHA(bank.ood),fit:fit(bank,seed)};})};}
function scoreFrozen(frozen){if(frozen.protocol!==VERSION||frozen.N!==N||frozen.D!==D||SHA(frozen.STEPS)!==SHA(STEPS)||SHA(frozen.SEEDS)!==SHA(SEEDS)||SHA(frozen.SPLITS)!==SHA(SPLITS)||SHA(frozen.LR)!==SHA(LR)||SHA(frozen.OUTER)!==SHA(OUTER)||frozen.EPOCHS!==EPOCHS||frozen.SUPPORT!==SUPPORT||frozen.HIT!==HIT)throw Error('protocol mismatch');
 if(!Array.isArray(frozen.per_seed)||frozen.per_seed.length!==SEEDS.length)throw Error('seed list mismatch');
 const per_seed=[];
 for(let i=0;i<SEEDS.length;i++){
  const f=frozen.per_seed[i],seed=SEEDS[i],bank=makeBank(seed);
  if(f.seed!==seed||f.train_sha256!==SHA(bank.train)||f.validation_sha256!==SHA(bank.validation)||f.ood_sha256!==SHA(bank.ood))throw Error('bank integrity');
  if(SHA(f.fit)!==SHA(fit(bank,seed)))throw Error('fit integrity');
  const arms={};const plans={scratch:{theta:null,lr:f.fit.scratch_lr},static_transfer:{theta:f.fit.chosen.joint.theta,lr:0},pretrained_finetune:{theta:f.fit.chosen.joint.theta,lr:f.fit.chosen.joint.lr},reptile:{theta:f.fit.chosen.reptile.theta,lr:f.fit.chosen.reptile.lr},nearest:{theta:null,lr:0}};
  for(const arm of ARMS){arms[arm]={all_ood:scoreTasks(bank.ood,arm,plans[arm].theta,plans[arm].lr,seed),families:{}};for(const family of Object.keys(SPLITS.ood))arms[arm].families[family]=scoreTasks(bank.ood.filter(t=>t.family===family),arm,plans[arm].theta,plans[arm].lr,seed);}
  per_seed.push({seed,arms});
 }
 const aggregate={};for(const arm of ARMS){aggregate[arm]={};for(const k of STEPS){aggregate[arm][k]={};for(const m of ['balanced_accuracy','unqueried_accuracy','unqueried_brier'])aggregate[arm][k][m]=per_seed.reduce((s,e)=>s+e.arms[arm].all_ood.byK[k][m],0)/SEEDS.length;}}
 const best_control=Math.max(...['scratch','pretrained_finetune','nearest'].map(a=>aggregate[a][4].balanced_accuracy));
 const delta=aggregate.reptile[4].balanced_accuracy-best_control;
 return {protocol:VERSION+'-results',freeze_sha256:SHA(frozen),seeds:SEEDS,ood_tasks:SEEDS.length*Object.values(SPLITS.ood).reduce((s,n)=>s+n,0),per_seed,aggregate,primary:{metric:'balanced_accuracy_k4',best_control,meta:aggregate.reptile[4].balanced_accuracy,delta,criterion:'delta >= 0.05',pass:delta>=.05},status:'PUBLIC_DEVELOPMENT_NOT_CONFIRMATORY'};
}
function checks(){const b=makeBank(SEEDS[0]),copy=makeBank(SEEDS[0]);if(SHA(b)!==SHA(copy))throw Error('nondeterministic bank');
 const seen=new Set();for(const [split,expected] of Object.entries(SPLITS)){
  for(const [f,num] of Object.entries(expected))if(b[split].filter(t=>t.family===f).length!==num)throw Error('family split mismatch');
  for(const t of b[split]){if(seen.has(t.mask))throw Error('overlapping truth');seen.add(t.mask);}}
 const fitOnly={train:b.train,validation:b.validation,ood:new Proxy([],{get(){throw Error('OOD leakage');}})};
 if(SHA(fit(fitOnly,SEEDS[0]))!==SHA(fit(b,SEEDS[0])))throw Error('fit OOD leak');
 const task=b.validation[0],lr=.15,theta=Array(D).fill(0);
 for(const arm of ARMS){const e=evaluate(task,arm,theta.slice(),lr,SEEDS[0]);if(e.purchased.length!==(arm==='static_transfer'?0:8))throw Error('purchase mismatch '+arm);if(new Set(e.purchased).size!==e.purchased.length)throw Error('query dup '+arm);if(SHA(e)!==SHA(evaluate(task,arm,theta.slice(),lr,SEEDS[0])))throw Error('nondeterministic episode');}
 const altered=freezeAll();altered.per_seed[0].fit.chosen.reptile.theta[0]+=1;try{scoreFrozen(altered);throw Error('missing fit integrity rejection');}catch(e){if(e.message==='missing fit integrity rejection')throw e;if(e.message!=='fit integrity')throw e;}
 return {pass:true,assertions:9,seed:SEEDS[0],features:D,training_tasks:b.train.length,validation_tasks:b.validation.length,ood_tasks:b.ood.length};
}
export {VERSION,N,D,STEPS,SEEDS,SPLITS,LR,OUTER,makeBank,label,features,trainInit,fit,freezeAll,scoreFrozen,evaluate,scoreTasks,checks,SHA};
if(process.argv[1]&&import.meta.url===pathToFileURL(process.argv[1]).href){const [action,src,dst]=process.argv.slice(2);
 if(action==='test')console.log(JSON.stringify(checks()));
 else if(action==='freeze'){if(!src||existsSync(src))throw Error('freeze path required and must not exist');writeFileSync(src,JSON.stringify(freezeAll(),null,2)+'\n');console.log('prescore SHA256',SHA(JSON.parse(readFileSync(src,'utf8'))));}
 else if(action==='score'||action==='verify'){if(!src||!dst)throw Error('frozen and results paths required');const out=scoreFrozen(JSON.parse(readFileSync(src,'utf8')));if(action==='score'){if(existsSync(dst))throw Error('refuse overwrite');writeFileSync(dst,JSON.stringify(out,null,2)+'\n');console.log('scored',JSON.stringify(out.primary));}else{if(SHA(out)!==SHA(JSON.parse(readFileSync(dst,'utf8'))))throw Error('replay mismatch');console.log('PASS exact semantic replay');}}
 else throw Error('usage: node v2_study.mjs test|freeze PATH|score PRESCORE RESULTS|verify PRESCORE RESULTS');
}
