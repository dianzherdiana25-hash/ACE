// ACE R4 meta-learning: isolated, bounded, public synthetic benchmark.
// Node.js 20+; no dependencies and no arbitrary candidate code execution.
const N=24;
const STEPS=[0,1,2,4,8];
const SPLITS={"train":{"threshold":14,"interval":24},"validation":{"reverse_threshold":10,"outside_interval":10},"ood_test":{"periodic":16,"double_interval":16,"sparse":16}};
function seedHash(...parts){let h=2166136261>>>0;for(const ch of parts.join("::")){h^=ch.charCodeAt(0);h=Math.imul(h,16777619)>>>0;}return h || 123456789;}

function randomGenerator(s){let state=s>>>0;return ()=>{state^=state<<13;state^=state>>>17;state^=state<<5;return (state>>>0)/4294967296;};}

function randint(rng,lo,hi){return lo+Math.floor(rng()*(hi-lo+1));}

function generateTruth(family,rng){
let test;
if(family==="threshold"||family==="reverse_threshold"){const cut=randint(rng,3,21);test=x=>family==="threshold"?x>=cut:x<cut;}
else if(family==="interval"||family==="outside_interval"){const a=randint(rng,2,13),len=randint(rng,3,10);test=x=>family==="interval"?(x>=a&&x<a+len):!(x>=a&&x<a+len);}
else if(family==="periodic"){const p=randint(rng,3,8),phase=randint(rng,0,p-1),width=randint(rng,1,p-1);test=x=>((x-phase+p*24)%p)<width;}
else if(family==="double_interval"){const a=randint(rng,1,8),aw=randint(rng,2,5),b=randint(rng,15,20),bw=randint(rng,2,4);test=x=>(x>=a&&x<a+aw)||(x>=b&&x<b+bw);}
else if(family==="sparse"){const vals=new Set();while(vals.size<3)vals.add(randint(rng,1,22));const pts=[...vals].sort((a,b)=>a-b);if(pts[1]-pts[0]<3||pts[2]-pts[1]<3)return null;test=x=>vals.has(x);}
else throw Error("unknown family");
let mask=0;for(let x=0;x<N;x++)if(test(x))mask|=(1<<x);return mask;
}

function makeBank(seed){
const seen=new Set(), bank={train:[],validation:[],ood_test:[]};
for(const split of Object.keys(SPLITS))for(const [family,n] of Object.entries(SPLITS[split])){
let attempt=0;for(let id=0;id<n;){if(++attempt>50000)throw Error("unique-bank exhaustion "+family);
const mask=generateTruth(family,randomGenerator(seedHash("r4",seed,split,family,attempt)));
if(mask===null||mask===0||mask===((1<<N)-1)||seen.has(mask))continue;
seen.add(mask);bank[split].push({family,id,mask});id++;
}}
return bank;
}

function label(task,x){if(x<0||x>=N)throw Error("invalid x");return (task.mask>>>x)&1;}

function digest(tasks){return seedHash("task-bank",tasks.map(t=>`${t.family}:${t.id}:${t.mask.toString(16)}`).join("|")).toString(16).padStart(8,"0");}

function sourcePrior(tasks){const p=[];for(let x=0;x<N;x++)p.push((1+tasks.reduce((a,t)=>a+label(t,x),0))/(2+tasks.length));return p;}

function evidencePrediction(x,observations,w,prior,priorStrength,work,nearest){
work.predictions++;
if(!observations.length)return prior;
if(nearest){let mind=Infinity,sum=0,n=0;for(const [pos,y] of observations){const d=Math.abs(x-pos);work.pair_ops++;if(d<mind){mind=d;sum=y;n=1;}else if(d===mind){sum+=y;n++;}}return sum/n;}
let numerator=prior*priorStrength,denominator=priorStrength;
for(const [pos,y] of observations){const d=Math.abs(x-pos);
const similarity=w.local*Math.pow(2,-d/3)+w.parity*(d%2===0?1:0)+w.block*(Math.floor(pos/4)===Math.floor(x/4)?1:0)+w.global;
numerator+=similarity*y;denominator+=similarity;work.pair_ops++;
}return numerator/denominator;
}

function chooseQuery(observations,w,rng,active,prior,priorStrength,nearest,work){
const observed=new Set(observations.map(a=>a[0])),rest=[];
for(let x=0;x<N;x++)if(!observed.has(x))rest.push(x);
if(!active)return rest[Math.floor(rng()*rest.length)];
let winner=-1,max=-Infinity;
for(const x of rest){
const p=evidencePrediction(x,observations,w,prior[x],priorStrength,work,nearest);
let nearestDistance=N;for(const [pos] of observations)nearestDistance=Math.min(nearestDistance,Math.abs(x-pos));
const score=(1-Math.abs(2*p-1))+w.explore*nearestDistance/N;
if(score>max+1e-12){max=score;winner=x;}
}return winner;
}

function episode(task,arm,seed,w,prior){
const allowed=["scratch","static_transfer","static_finetune","simple_meta","learned_meta","learned_random"];
if(!allowed.includes(arm))throw Error("unknown arm");
const work={pair_ops:0,predictions:0,observations:0},obs=[],rng=randomGenerator(seedHash("target",seed,task.family,task.id));
const evidence=(arm==="static_transfer")?[]:obs;
const nearest=arm==="scratch";
const active=arm==="simple_meta"||arm==="learned_meta";
const source=arm==="static_transfer"||arm==="static_finetune";
const p0=source?prior:Array(N).fill(.5),strength=source?2.0:.25;
const results={};
for(let k=0;k<=8;k++){
if(STEPS.includes(k)){
let total=0,brier=0,count=0;
const observed=new Set(obs.map(a=>a[0]));
for(let x=0;x<N;x++){if(observed.has(x))continue;
const p=evidencePrediction(x,evidence,w,p0[x],strength,work,nearest),y=label(task,x);
total+=((p>=.5)===Boolean(y))?1:0;brier+=(p-y)**2;count++;
}
results[k]={accuracy:total/count,brier:brier/count};
}
if(k===8)break;
if(arm==="static_transfer")continue;
const q=chooseQuery(obs,w,rng,active,p0,strength,nearest,work);
obs.push([q,label(task,q)]);work.observations++;
}
return {results,work,purchased:obs.map(o=>o[0])};
}

function objective(tasks,seed,w){
let brier=0,ops=0;
for(const t of tasks){const e=episode(t,"learned_meta",seed,w,null);brier+=(e.results[4].brier+e.results[8].brier)/2;ops+=e.work.pair_ops;}
return {brier:brier/tasks.length,pair_ops:ops};
}

function weightCandidates(seed){
const candidates=[{local:1,parity:0,block:0,global:0,explore:.4},{local:1,parity:.4,block:0,global:0,explore:.4},{local:.7,parity:0,block:.4,global:.1,explore:.8},{local:.25,parity:1,block:0,global:0,explore:.4}];
const rng=randomGenerator(seedHash("search",seed)),v=[0,.1,.3,.6,1,1.5];
for(let i=0;i<14;i++){const a=Array.from({length:4},()=>v[Math.floor(rng()*v.length)]);if(a.every(x=>x===0))a[0]=1;candidates.push({local:a[0],parity:a[1],block:a[2],global:a[3],explore:v[Math.floor(rng()*v.length)]});}
return candidates;
}

function metaFit(bank,seed){
const candidates=weightCandidates(seed),trace=[],train=bank.train,valid=bank.validation;
let pair_ops=0;
for(let i=0;i<candidates.length;i++){const s=objective(train,seed,candidates[i]);pair_ops+=s.pair_ops;trace.push({index:i,train_brier:s.brier});}
const finalists=[...trace].sort((a,b)=>a.train_brier-b.train_brier||a.index-b.index).slice(0,4);
for(const t of finalists){const s=objective(valid,seed,candidates[t.index]);pair_ops+=s.pair_ops;t.validation_brier=s.brier;}
finalists.sort((a,b)=>a.validation_brier-b.validation_brier||a.train_brier-b.train_brier||a.index-b.index);
const chosen=finalists[0];return {weights:candidates[chosen.index],selected_index:chosen.index,train_brier:chosen.train_brier,validation_brier:chosen.validation_brier,candidates:trace,meta_fit_pair_ops:pair_ops,train_label_exposures:train.length*N,validation_label_exposures:valid.length*N};
}

function freeze(seed){
const bank=makeBank(seed);const fitted=metaFit(bank,seed);
return {protocol:"ACE-R4-v1",seed,N,STEPS,SPLITS,train_digest:digest(bank.train),validation_digest:digest(bank.validation),ood_digest:digest(bank.ood_test),fitted,prescore:true};
}

function summarize(tasks,arm,seed,w,prior){
const episodes=tasks.map(t=>episode(t,arm,seed,w,prior));
const by_k={},work={pair_ops:0,predictions:0,observations:0};
for(const k of STEPS){
by_k[k]={accuracy:episodes.reduce((s,e)=>s+e.results[k].accuracy,0)/episodes.length,
brier:episodes.reduce((s,e)=>s+e.results[k].brier,0)/episodes.length,
fraction_reaches_80pct:episodes.filter(e=>e.results[k].accuracy>=.8).length/episodes.length};
}
let sumK=0;
for(const e of episodes){let hit=9;for(const k of STEPS)if(e.results[k].accuracy>=.8){hit=k;break;}sumK+=hit;for(const key of Object.keys(work))work[key]+=e.work[key];}
return {tasks:tasks.length,by_k,mean_first_hit_censored_at_9:sumK/episodes.length,work};
}

function scoreFrozen(frozen){
if(!frozen.prescore||frozen.protocol!=="ACE-R4-v1")throw Error("invalid freeze");
if(frozen.N!==N||JSON.stringify(frozen.STEPS)!==JSON.stringify(STEPS)||JSON.stringify(frozen.SPLITS)!==JSON.stringify(SPLITS))throw Error("protocol mismatch");
const bank=makeBank(frozen.seed);
if(frozen.train_digest!==digest(bank.train)||frozen.validation_digest!==digest(bank.validation)||frozen.ood_digest!==digest(bank.ood_test))throw Error("bank-mismatch");
const learned=frozen.fitted.weights,base={local:1,parity:0,block:0,global:0,explore:.4},prior=sourcePrior(bank.train);
const arms={};
for(const arm of ["scratch","static_transfer","static_finetune","simple_meta","learned_meta","learned_random"]){
const w=(arm==="learned_meta"||arm==="learned_random")?learned:base;
const families={};
for(const family of Object.keys(SPLITS.ood_test))families[family]=summarize(bank.ood_test.filter(t=>t.family===family),arm,frozen.seed,w,prior);
arms[arm]={all_ood:summarize(bank.ood_test,arm,frozen.seed,w,prior),families};
}
return {protocol:"ACE-R4-v1-results",seed:frozen.seed,frozen_digest:seedHash(JSON.stringify(frozen)).toString(16),arms,ood_task_count:bank.ood_test.length,ood_labels_scored:bank.ood_test.length*N,scientific_status:"PUBLIC_DEVELOPMENT_NOT_CONFIRMATORY"};
}

function selfTest(){
const b=makeBank(0),c=makeBank(0);
if(JSON.stringify(b)!==JSON.stringify(c))throw Error("non-deterministic task generation");
if(JSON.stringify(makeBank(1))===JSON.stringify(b))throw Error("seed variation absent");
const seen=new Set();for(const split of Object.keys(SPLITS)){const expected=Object.keys(SPLITS[split]);if([...new Set(b[split].map(t=>t.family))].sort().join()!==expected.sort().join())throw Error("wrong family partition");for(const t of b[split]){if(seen.has(t.mask))throw Error("truth leakage across splits");seen.add(t.mask);}}
const w={local:1,parity:0,block:0,global:0,explore:.4},p=sourcePrior(b.train);
for(const arm of ["scratch","static_transfer","static_finetune","simple_meta","learned_meta","learned_random"]){
const a=episode(b.train[0],arm,0,w,p),same=episode(b.train[0],arm,0,w,p);
if(JSON.stringify(a)!==JSON.stringify(same))throw Error("episode non deterministic");
if(arm!=="static_transfer"&&(a.work.observations!==8||new Set(a.purchased).size!==8))throw Error("invalid purchase count");
if(arm==="static_transfer"&&a.work.observations!==0)throw Error("static baseline queried target");
}
const fake={...b,ood_test:new Proxy([], {get(){throw Error("OOD exposed while training");}})};
if(JSON.stringify(metaFit(fake,0))!==JSON.stringify(metaFit(b,0)))throw Error("OOD leakage in meta fit");
const oldW={local:-1,parity:0,block:0,global:0,explore:0};
if(!Number.isFinite(objective(b.train.slice(0,1),0,w).brier))throw Error("nonfinite objective");
const t=b.train[0],ob=[[0,label(t,0)]],wr={pair_ops:0,predictions:0,observations:0};
const q=chooseQuery(ob,w,randomGenerator(1),true,Array(N).fill(.5),.25,false,wr);
if(q===0||q<0||q>=N)throw Error("query leak");
const frozen=freeze(0);
const altered={...frozen,ood_digest:"deadbeef"};
try{scoreFrozen(altered);throw Error("missing digest integrity check");}catch(e){if(e.message==="missing digest integrity check")throw e;}
return {checks:10,train_tasks:b.train.length,valid_tasks:b.validation.length,ood_tasks:b.ood_test.length,meta_selected_index:frozen.fitted.selected_index};
}

export {N,STEPS,SPLITS,seedHash,generateTruth,makeBank,label,digest,sourcePrior,evidencePrediction,chooseQuery,episode,objective,metaFit,freeze,summarize,scoreFrozen,selfTest};
import {existsSync,readFileSync,writeFileSync} from 'node:fs';
import {pathToFileURL} from 'node:url';
if(process.argv[1] && import.meta.url===pathToFileURL(process.argv[1]).href){
 const [action,src,dest]=process.argv.slice(2);
 if(action==='test'){console.log(JSON.stringify(selfTest()));}
 else if(action==='freeze'){
   if(!src||!dest)throw Error('usage: node study.mjs freeze SEED FILE');
   if(existsSync(dest))throw Error('refusing to overwrite frozen artifact');
   writeFileSync(dest,JSON.stringify(freeze(Number(src)),null,2)+'\\n');
 }else if(action==='score'||action==='verify'){
   if(!src||!dest)throw Error('usage: node study.mjs score|verify FROZEN_FILE RESULTS_FILE');
   const result=scoreFrozen(JSON.parse(readFileSync(src,'utf8')));
   if(action==='verify'){if(JSON.stringify(result)!==JSON.stringify(JSON.parse(readFileSync(dest,'utf8'))))throw Error('replay mismatch');console.log('PASS semantic replay');}
   else{if(existsSync(dest))throw Error('refusing to overwrite results');writeFileSync(dest,JSON.stringify(result,null,2)+'\\n');}
 }else throw Error('unknown action');
}
