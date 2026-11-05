// ACE R4 v4: gradient-coherence-conditioned learned inner-loop update.
// PUBLIC SYNTHETIC DEVELOPMENT, not independently sealed or deployed.
import {createHash} from 'node:crypto';
import {existsSync,readFileSync,writeFileSync} from 'node:fs';
import {pathToFileURL} from 'node:url';
import {features,trainInit} from './v2_study.mjs';
import {makeBank as makeV3Bank} from './v3_study.mjs';
const VERSION='ACE-R4-v4-gradient-conditioned-public';
const N=32,D=20,SEEDS=[907,1009,1103,1217],STEPS=[0,1,2,4,8];
const SOURCE_SPLITS={train:{threshold:18,interval:24,alternating:24},validation:{reverse_threshold:10,outside_interval:10,block_xor:12}};
const OOD_SPLITS={prime_affine:12,palindromic_bands:12,bitcount_gate:12,modular_intersection:12};
const LRS=[0.08,0.25,0.6], META_RATES=[0.2,0.6], OUTER_STEPS=6, FINITE_DIFF=0.125;
const MAX_META_BETA=1.75, HIT=0.75, QUERY_CAP=8;
const PRIMARY_GATE={metric:'full_domain_balanced_accuracy_k4',required_absolute_gain:0.05,relative_target_compute_cap:1.40,required_seed_wins:3,requires_unqueried_brier_noninferior:true};
const ARMS=['scratch','reptile','nearest','fixed_diag','joint_finetune','untrained_conditioned','learned_conditioned'];
const sha=x=>createHash('sha256').update(JSON.stringify(x)).digest('hex');
function seedHash(...parts){let z=2166136261>>>0;for(const c of parts.join('::')){z^=c.charCodeAt(0);z=Math.imul(z,16777619)>>>0;}return z||1;}
function random(seed){let x=seed>>>0;return ()=>{x^=x<<13;x^=x>>>17;x^=x<<5;return (x>>>0)/4294967296;};}
function ri(r,a,b){return a+Math.floor(r()*(b-a+1));}
function bits(x){let n=0;while(x){n+=x&1;x>>>=1;}return n;}
function isPrime(x){if(x<2)return false;for(let p=2;p*p<=x;p++)if(x%p===0)return false;return true;}
function oodMask(f,r){let fn;
 if(f==='prime_affine'){const a=ri(r,2,30),b=ri(r,0,30);fn=x=>isPrime((a*x+b)%31);}
 else if(f==='palindromic_bands'){const b=ri(r,2,7),phase=ri(r,0,b-1),center=ri(r,12,19);fn=x=>Math.floor((Math.abs(x-center)+phase)/b)%2===0;}
 else if(f==='bitcount_gate'){const a=ri(r,3,31)|1,b=ri(r,0,31),cut=ri(r,2,4);fn=x=>bits((a*x+b)&31)>=cut;}
 else if(f==='modular_intersection'){const p=ri(r,4,9),q=ri(r,5,11),u=ri(r,1,p-1),v=ri(r,1,q-1),shift=ri(r,0,8);fn=x=>((x+shift)%p)<u && ((x+2*shift)%q)>=v;}
 else throw Error('unknown family');
 let mask=0;for(let x=0;x<N;x++)if(fn(x))mask=(mask|(1<<x))>>>0;
 return bits(mask)>=5&&bits(mask)<=27?mask>>>0:null;
}
function makeBank(seed){const base=makeV3Bank(seed),out={train:base.train,validation:base.validation,ood:[]};
 const used=new Set([...out.train,...out.validation].map(t=>t.mask));
 for(const [family,n] of Object.entries(OOD_SPLITS)){
  let attempt=0,id=0;while(id<n){if(++attempt>120000)throw Error('OOD task generator exhausted '+family);
   const mask=oodMask(family,random(seedHash('v4-ood',seed,family,attempt)));
   if(mask===null||used.has(mask))continue;used.add(mask);out.ood.push({family,id,mask});id++;
  }
 }return out;
}
function label(t,x){if(!Number.isInteger(x)||x<0||x>=N)throw Error('invalid label input');return (t.mask>>>x)&1;}
const PHI=Array.from({length:N},(_,x)=>features(x));
function sigmoid(z){return z>=0?1/(1+Math.exp(-z)):Math.exp(z)/(1+Math.exp(z));}
function queryOrder(seed){const a=Array.from({length:N},(_,x)=>x),r=random(seedHash('v4-blind-fixed-target-order',seed));
 for(let i=N-1;i>0;i--){const j=ri(r,0,i);[a[i],a[j]]=[a[j],a[i]];}return a.slice(0,QUERY_CAP);
}
function initWork(){return {grad_steps:0,feature_multiplies:0,conditioner_ops:0,predictions:0,nearest_pairs:0};}
function prediction(theta,x,work){let z=0;for(let j=0;j<D;j++)z+=theta[j]*PHI[x][j];
 if(work){work.feature_multiplies+=D;work.predictions++;}return sigmoid(z);
}
function group(j){return j<4?0:j<12?1:2;}
function step(theta,history,x,y,lr,beta,conditioned,work,diag){const p=prediction(theta,x,work),e=y-p,grad=Array(D);
 for(let j=0;j<D;j++)grad[j]=e*PHI[x][j];
 for(let j=0;j<D;j++){
  // Support gradient coherence at this coordinate, computed only from acquired labels.
  let scale=diag?diag[group(j)]:1;if(conditioned){const st=history[j],s=st.sum+grad[j],a=st.abs+Math.abs(grad[j]);
   const coherence=a>1e-10?Math.abs(s)/a:0.5;
   scale=Math.max(0.25,Math.min(4,Math.exp(beta[group(j)]*(2*coherence-1))));
   work.conditioner_ops+=6;
  }
  theta[j]+=lr*scale*grad[j];history[j].sum+=grad[j];history[j].abs+=Math.abs(grad[j]);
 }
 work.feature_multiplies+=D;work.grad_steps++;
}
function nearest(obs,x,work){if(!obs.length)return 0.5;let mind=N+1,sum=0,num=0;
 for(const [pos,y] of obs){work.nearest_pairs++;const d=Math.abs(pos-x);if(d<mind){mind=d;sum=y;num=1;}else if(d===mind){sum+=y;num++;}}return sum/num;}
function episode(task,arm,seed,cfg){if(!ARMS.includes(arm))throw Error('unknown arm');const work=initWork(),theta=(cfg.initial||Array(D).fill(0)).slice(),history=Array.from({length:D},()=>({sum:0,abs:0})),obs=[],order=queryOrder(seed),by_k={};
 for(let k=0;k<=QUERY_CAP;k++){
  if(STEPS.includes(k)){
   const observed=new Map(obs);let tp=0,tn=0,np=0,nn=0,u=0,accurate=0,brier=0;
   for(let x=0;x<N;x++){
    const y=label(task,x),p=observed.has(x)?observed.get(x):(arm==='nearest'?nearest(obs,x,work):prediction(theta,x,work));
    if(y){np++;tp+=Number(p>=0.5);}else{nn++;tn+=Number(p<0.5);}
    if(!observed.has(x)){u++;accurate+=Number((p>=0.5)===Boolean(y));brier+=(p-y)*(p-y);}
   }
   by_k[k]={balanced_accuracy:0.5*(tp/np+tn/nn),unqueried_accuracy:accurate/u,unqueried_brier:brier/u};
  }
  if(k===QUERY_CAP)break;
  const x=order[k],y=label(task,x);obs.push([x,y]);
  if(arm!=='nearest')step(theta,history,x,y,cfg.lr,cfg.beta||[0,0,0],arm==='learned_conditioned'||arm==='untrained_conditioned',work,cfg.diag);
 }
 return {by_k,work,purchases:obs.map(x=>x[0])};
}
function summarize(tasks,arm,seed,cfg){const items=tasks.map(t=>episode(t,arm,seed,cfg));const by_k={},work=initWork();let first=0;
 for(const k of STEPS){by_k[k]={};for(const metric of ['balanced_accuracy','unqueried_accuracy','unqueried_brier'])by_k[k][metric]=items.reduce((s,e)=>s+e.by_k[k][metric],0)/items.length;}
 for(const item of items){first+=STEPS.find(k=>item.by_k[k].balanced_accuracy>=HIT)??9;for(const x of Object.keys(work))work[x]+=item.work[x];}
 return {tasks:tasks.length,by_k,mean_hit_censored_at_9:first/items.length,target_labels:tasks.length*QUERY_CAP,work};
}
function trainingLoss(tasks,seed,lr,beta,work){let sum=0;
 for(const task of tasks){const out=episode(task,'learned_conditioned',seed,{lr,beta});sum+=0.5*(out.by_k[4].unqueried_brier+out.by_k[8].unqueried_brier);for(const k of Object.keys(work))work[k]+=out.work[k];}
 return sum/tasks.length;
}
function fit(bank,seed){const work=initWork();let fullEval=0;
 const learned=[];
 for(const lr of LRS)for(const metaRate of META_RATES){const beta=[0,0,0],curve=[];
  for(let round=0;round<OUTER_STEPS;round++){
   const delta=[];
   for(let j=0;j<3;j++){const up=beta.slice(),down=beta.slice();up[j]+=FINITE_DIFF;down[j]-=FINITE_DIFF;
    const a=trainingLoss(bank.train,seed,lr,up,work),b=trainingLoss(bank.train,seed,lr,down,work);fullEval+=2;
    delta[j]=(a-b)/(2*FINITE_DIFF);
   }
   for(let j=0;j<3;j++)beta[j]=Math.max(-MAX_META_BETA,Math.min(MAX_META_BETA,beta[j]-metaRate*delta[j]));
   curve.push({round,beta:beta.slice(),gradient:delta});
  }
  const val=summarize(bank.validation,'learned_conditioned',seed,{lr,beta});
  learned.push({lr,metaRate,beta:beta.slice(),validation_k4:val.by_k[4].balanced_accuracy,validation_brier:val.by_k[4].unqueried_brier,curve});
 }
 learned.sort((a,b)=>b.validation_k4-a.validation_k4||a.validation_brier-b.validation_brier||a.lr-b.lr||a.metaRate-b.metaRate);
 const scratch=LRS.map(lr=>({lr,v:summarize(bank.validation,'scratch',seed,{lr}).by_k[4].balanced_accuracy})).sort((a,b)=>b.v-a.v||a.lr-b.lr)[0];
 const diagonals=[];for(const lr of LRS)for(const diag of [[1,1,1],[0.7,1,1.4],[1.4,1,0.7]]){const res=summarize(bank.validation,'fixed_diag',seed,{lr,diag});diagonals.push({lr,diag,score:res.by_k[4].balanced_accuracy,brier:res.by_k[4].unqueried_brier});}diagonals.sort((a,b)=>b.score-a.score||a.brier-b.brier||a.lr-b.lr);
 const fixed=[];for(const lr of LRS)for(const beta of [[0,0,0],[0.75,0.75,0.75],[-0.75,-0.75,-0.75]]){
  const s=summarize(bank.validation,'untrained_conditioned',seed,{lr,beta});fixed.push({lr,beta,score:s.by_k[4].balanced_accuracy,brier:s.by_k[4].unqueried_brier});
 }
 fixed.sort((a,b)=>b.score-a.score||a.brier-b.brier||a.lr-b.lr);
 const reptile=[];for(const lr of LRS)for(const outer of [0.12,0.4]){
  const t=trainInit(bank.train,seed,'reptile',lr,outer),s=summarize(bank.validation,'reptile',seed,{lr,initial:t.theta});
  reptile.push({lr,outer,initial:t.theta,val:s.by_k[4].balanced_accuracy,source_gradient_steps:t.work.gradient_steps});
 }
 reptile.sort((a,b)=>b.val-a.val||a.lr-b.lr||a.outer-b.outer);
 const joint=[];for(const lr of LRS){const t=trainInit(bank.train,seed,'joint',lr,0),v=summarize(bank.validation,'joint_finetune',seed,{lr,initial:t.theta});joint.push({lr,initial:t.theta,val:v.by_k[4].balanced_accuracy,source_gradient_steps:t.work.gradient_steps});}joint.sort((a,b)=>b.val-a.val||a.lr-b.lr);
 return {learned:learned[0],learned_trace:learned.map(({lr,metaRate,beta,validation_k4,validation_brier})=>({lr,metaRate,beta,validation_k4,validation_brier})),scratch_lr:scratch.lr,static_diag:diagonals[0],fixed:fixed[0],reptile:reptile[0],joint:joint[0],train_work:work,train_loss_evaluations:fullEval,source_label_scoring_exposures:fullEval*bank.train.length*N,train_source_unique_labels:bank.train.length*N,validation_labels:bank.validation.length*N};
}
function freezeAll(){return {version:VERSION,seeds:SEEDS,steps:STEPS,source_splits:SOURCE_SPLITS,ood_splits:OOD_SPLITS,n:N,d:D,lrs:LRS,meta_rates:META_RATES,outer_steps:OUTER_STEPS,finite_diff:FINITE_DIFF,max_beta:MAX_META_BETA,query_cap:QUERY_CAP,primary_gate:structuredClone(PRIMARY_GATE),per_seed:SEEDS.map(seed=>{const bank=makeBank(seed);return {seed,train_sha256:sha(bank.train),validation_sha256:sha(bank.validation),ood_sha256:sha(bank.ood),fit:fit(bank,seed)};})};}
function scoreFrozen(f){if(f.version!==VERSION||sha(f.seeds)!==sha(SEEDS)||sha(f.steps)!==sha(STEPS)||sha(f.source_splits)!==sha(SOURCE_SPLITS)||sha(f.ood_splits)!==sha(OOD_SPLITS)||f.n!==N||f.d!==D||sha(f.lrs)!==sha(LRS)||sha(f.meta_rates)!==sha(META_RATES)||f.outer_steps!==OUTER_STEPS||f.finite_diff!==FINITE_DIFF||f.max_beta!==MAX_META_BETA||f.query_cap!==QUERY_CAP||sha(f.primary_gate)!==sha(PRIMARY_GATE))throw Error('protocol mismatch');
 if(!Array.isArray(f.per_seed)||f.per_seed.length!==SEEDS.length)throw Error('seed mismatch');
 const per_seed=[];
 for(let i=0;i<SEEDS.length;i++){
  const seed=SEEDS[i],r=f.per_seed[i],bank=makeBank(seed);
  if(r.seed!==seed||r.train_sha256!==sha(bank.train)||r.validation_sha256!==sha(bank.validation)||r.ood_sha256!==sha(bank.ood))throw Error('bank integrity');
  if(sha(r.fit)!==sha(fit(bank,seed)))throw Error('fit integrity');
  const cfg={scratch:{lr:r.fit.scratch_lr},nearest:{lr:0},reptile:{lr:r.fit.reptile.lr,initial:r.fit.reptile.initial},fixed_diag:r.fit.static_diag,joint_finetune:{lr:r.fit.joint.lr,initial:r.fit.joint.initial},untrained_conditioned:r.fit.fixed,learned_conditioned:{lr:r.fit.learned.lr,beta:r.fit.learned.beta}};
  const arms={};for(const arm of ARMS){const xarm=arm;arms[arm]={all_ood:summarize(bank.ood,xarm,seed,cfg[arm]),families:{}};for(const family of Object.keys(OOD_SPLITS))arms[arm].families[family]=summarize(bank.ood.filter(t=>t.family===family),xarm,seed,cfg[arm]);}
  per_seed.push({seed,arms});
 }
 const aggregate={};for(const arm of ARMS){aggregate[arm]={};for(const k of STEPS){aggregate[arm][k]={};for(const m of ['balanced_accuracy','unqueried_accuracy','unqueried_brier'])aggregate[arm][k][m]=per_seed.reduce((v,s)=>v+s.arms[arm].all_ood.by_k[k][m],0)/SEEDS.length;}}
 const bestArm=ARMS.filter(a=>a!=='learned_conditioned').sort((a,b)=>aggregate[b][4].balanced_accuracy-aggregate[a][4].balanced_accuracy)[0];
 const gain=aggregate.learned_conditioned[4].balanced_accuracy-aggregate[bestArm][4].balanced_accuracy;
 const seedWins=per_seed.filter(s=>s.arms.learned_conditioned.all_ood.by_k[4].balanced_accuracy>s.arms[bestArm].all_ood.by_k[4].balanced_accuracy).length;
 const condOps=per_seed.reduce((a,s)=>a+s.arms.learned_conditioned.all_ood.work.conditioner_ops,0),ctrlOps=per_seed.reduce((a,s)=>a+s.arms.scratch.all_ood.work.feature_multiplies,0);
 const condiF=per_seed.reduce((a,s)=>a+s.arms.learned_conditioned.all_ood.work.feature_multiplies,0);
 const computeRatio=(condiF+condOps)/ctrlOps;
 const brierNoninferior=aggregate.learned_conditioned[4].unqueried_brier<=aggregate[bestArm][4].unqueried_brier;
 return {version:VERSION+'-scored',prescore_sha256:sha(f),per_seed,aggregate,primary:{best_control:bestArm,meta:aggregate.learned_conditioned[4].balanced_accuracy,control:aggregate[bestArm][4].balanced_accuracy,gain,seed_wins:seedWins,compute_ratio:computeRatio,brier_noninferior:brierNoninferior,passed:gain>=0.05&&seedWins>=3&&computeRatio<=PRIMARY_GATE.relative_target_compute_cap&&brierNoninferior},status:'PUBLIC_SYNTHETIC_DEVELOPMENT_NOT_INDEPENDENT'};
}
function checks(){const b=makeBank(SEEDS[0]),same=makeBank(SEEDS[0]);if(sha(b)!==sha(same))throw Error('nondeterministic bank');
 const seen=new Set();for(const [name,fs] of Object.entries({...SOURCE_SPLITS,ood:OOD_SPLITS})){
  if(name==='train'||name==='validation'||name==='ood'){const arr=b[name];for(const task of arr){if(seen.has(task.mask))throw Error('split collision');seen.add(task.mask);}}
 }
 if(seen.size!==b.train.length+b.validation.length+b.ood.length)throw Error('bank count');
 const task=b.validation[0],base={lr:0.25,beta:[0.3,0.5,-0.2]};const all=[];
 for(const arm of ARMS){const a=episode(task,arm,SEEDS[0],base);if(a.purchases.length!==8||new Set(a.purchases).size!==8)throw Error('query cap');if(sha(a)!==sha(episode(task,arm,SEEDS[0],base)))throw Error('nondeterminism '+arm);all.push(a);}
 if(!all.every(v=>sha(v.purchases)===sha(all[0].purchases)))throw Error('purchase mismatch');
 const fake={train:b.train,validation:b.validation,ood:new Proxy([],{get(){throw Error('fit accessed OOD');}})};
 if(sha(fit(fake,SEEDS[0]))!==sha(fit(b,SEEDS[0])))throw Error('fit leakage');
 const bad=freezeAll();bad.per_seed[0].fit.learned.beta[0]+=0.1;try{scoreFrozen(bad);throw Error('fit forgery accepted');}catch(e){if(e.message!=='fit integrity')throw e;}
 return {pass:true,tests:6,source:b.train.length,validation:b.validation.length,ood:b.ood.length,masks:seen.size};
}
export {VERSION,N,D,SEEDS,STEPS,SOURCE_SPLITS,OOD_SPLITS,ARMS,sha,makeBank,label,queryOrder,prediction,step,episode,summarize,trainingLoss,fit,freezeAll,scoreFrozen,checks};
if(process.argv[1]&&import.meta.url===pathToFileURL(process.argv[1]).href){const [cmd,input,output]=process.argv.slice(2);
 if(cmd==='test')console.log(JSON.stringify(checks()));
 else if(cmd==='freeze'){if(!input||existsSync(input))throw Error('freeze requires unused target');writeFileSync(input,JSON.stringify(freezeAll(),null,2)+'\n');console.log('prescore',sha(JSON.parse(readFileSync(input,'utf8'))));}
 else if(cmd==='score'||cmd==='verify'){if(!input||!output)throw Error('requires freeze and results');const out=scoreFrozen(JSON.parse(readFileSync(input,'utf8')));if(cmd==='score'){if(existsSync(output))throw Error('refuse overwrite');writeFileSync(output,JSON.stringify(out,null,2)+'\n');console.log(JSON.stringify(out.primary));}else{if(sha(out)!==sha(JSON.parse(readFileSync(output,'utf8'))))throw Error('replay mismatch');console.log('PASS semantic replay');}}
 else throw Error('usage: test|freeze PATH|score PRESCORE RESULT|verify PRESCORE RESULT');
}
