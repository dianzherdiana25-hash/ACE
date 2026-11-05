// ACE R4 v6: diagnostic attribution only, public synthetic, NOT a meta-learning promotion.
// No fitting is done using the new OOD outcomes; v5 learned parameters are frozen inputs.
import {createHash} from 'node:crypto';
import {readFileSync,writeFileSync,existsSync} from 'node:fs';
import {pathToFileURL,fileURLToPath} from 'node:url';
import {features} from './v2_study.mjs';
import {bankForSeed,queryOrder,directionalStep} from './v5_study.mjs';
const VERSION='ACE-R4-v6-attribution-public-v1';
const N=32,D=20,SEEDS=[2009,2063,2137,2221],PRIOR_SEEDS=[1301,1423,1559,1697];
const POOL_SEEDS=[2333,2401,2503,2609,2707,2803,2909,3011];
const CHECKPOINTS=[0,2,4,8],CAP=8,LR_FULL=0.12,FULL_EPOCHS=96;
const STRESS_BETA=[0.4,-0.4,0.4,-0.4,-0.4,0.4];
const arms=['scratch_blind','learned_blind','stress_blind','scratch_family_query'];
const sha=x=>createHash('sha256').update(JSON.stringify(x)).digest('hex');
const rfile=(name)=>new URL(name,import.meta.url);
const PHI=Array.from({length:N},(_,x)=>features(x));
function seedHash(...parts){let h=2166136261>>>0;for(const c of parts.join('|')){h^=c.charCodeAt(0);h=Math.imul(h,16777619)>>>0;}return h||1;}
function randomGenerator(seed){let state=seed>>>0;return ()=>{state^=state<<13;state^=state>>>17;state^=state<<5;return (state>>>0)/4294967296;};}
function label(task,x){return (task.mask>>>x)&1;}
function blindOrder(seed,id){if(!Number.isInteger(seed)||!Number.isInteger(id)||id<0)throw Error('invalid key');const a=Array.from({length:N},(_,i)=>i),rng=randomGenerator(seedHash('v6-family-blind',seed,id));for(let i=N-1;i>0;i--){const j=Math.floor(rng()*(i+1));[a[i],a[j]]=[a[j],a[i]];}return a.slice(0,CAP);}
function sigmoid(z){return z>=0?1/(1+Math.exp(-z)):Math.exp(z)/(1+Math.exp(z));}
function prediction(theta,x){let z=0;for(let j=0;j<D;j++)z+=theta[j]*PHI[x][j];return sigmoid(z);}
function workBlank(){return {feature_multiply:0,gradient_steps:0,route_ops:0,predictions:0,nearest_pairs:0};}
function metrics(task,theta,known){const seen=new Map(known),numPos=Array.from({length:N},(_,x)=>label(task,x)).reduce((a,b)=>a+b,0),numNeg=N-numPos;
 let tp=0,tn=0,brier=0,unqCount=0,unqCorrect=0;
 const predictions=[];
 for(let x=0;x<N;x++){
  const p=seen.has(x)?seen.get(x):prediction(theta,x),y=label(task,x);
  predictions.push(p);
  if(y===1&&p>=.5)tp++;if(y===0&&p<.5)tn++;
  if(!seen.has(x)){brier+=(p-y)**2;unqCount++;unqCorrect+=Number((p>=.5)===Boolean(y));}
 }
 return {balanced_accuracy:(tp/numPos+tn/numNeg)/2,unqueried_brier:unqCount?brier/unqCount:null,unqueried_accuracy:unqCount?unqCorrect/unqCount:null,predictions};
}
function episode(task,seed,kind,lr,beta){const theta=Array(D).fill(0),history={mean:[0,0,0],count:0},work=workBlank(),seen=[],positions=kind==='family_query'?queryOrder(task,seed):blindOrder(seed,task.id),out={};
 for(let k=0;k<=CAP;k++){
  if(CHECKPOINTS.includes(k))out[k]=metrics(task,theta,seen);
  if(k===CAP)break;
  const x=positions[k],y=label(task,x);seen.push([x,y]);
  directionalStep(theta,history,x,y,lr,beta,kind==='learned'?'conditional':kind==='stress'?'static':'none',work);
 }
 return {by_k:out,purchases:positions,work};
}
function fitAllLabels(task){const theta=Array(D).fill(0);for(let epoch=0;epoch<FULL_EPOCHS;epoch++)for(let x=0;x<N;x++){
 const err=label(task,x)-prediction(theta,x);for(let j=0;j<D;j++)theta[j]+=LR_FULL*err*PHI[x][j];
 }return metrics(task,theta,[]).balanced_accuracy;
}
function referencePool(seed){const masks=new Set(bankForSeed(seed).ood.map(x=>x.mask));for(const s of POOL_SEEDS)for(const t of bankForSeed(s).ood)masks.add(t.mask);return [...masks];}
function versionSpace(task,positions,k,pool){const match=pool.filter(mask=>positions.slice(0,k).every(x=>((mask>>>x)&1)===label(task,x)));
 if(!match.length)throw Error('target missing from evaluator-only pool');
 let ambiguous=0,entropy=0,unseen=0,correct=0;
 const observed=new Set(positions.slice(0,k));
 for(let x=0;x<N;x++){if(observed.has(x))continue;const p=match.reduce((a,mask)=>a+((mask>>>x)&1),0)/match.length;
  if(p>0&&p<1)ambiguous++;
  entropy+=p===0||p===1?0:-p*Math.log2(p)-(1-p)*Math.log2(1-p);
  correct+=Number((p>=.5)===Boolean(label(task,x)));unseen++;
 }
 return {count:match.length,ambiguous_unqueried:ambiguous,entropy_per_unqueried:entropy/unseen,oracle_candidate_unqueried_accuracy:correct/unseen};
}
function oldConfig(index){const frozen=JSON.parse(readFileSync(rfile('v5_prescore.json'),'utf8'));
 if(!frozen.per_seed||frozen.per_seed[index].seed!==PRIOR_SEEDS[index])throw Error('v5 source seed integrity');
 const fit=frozen.per_seed[index].fit;
 return {lr:fit.scratch_lr,beta:fit.directional.conditional.selected.beta.slice(),source_seed:PRIOR_SEEDS[index]};
}
function freeze(){const parent=JSON.parse(readFileSync(rfile('v5_prescore.json'),'utf8'));
 return {version:VERSION,seeds:SEEDS,prior_seeds:PRIOR_SEEDS,pool_seeds:POOL_SEEDS,checkpoints:CHECKPOINTS,cap:CAP,n:N,d:D,lr_full:LR_FULL,full_epochs:FULL_EPOCHS,stress_beta:STRESS_BETA,source_v5_sha256:sha(parent),per_seed:SEEDS.map((seed,i)=>{
 const bank=bankForSeed(seed),config=oldConfig(i);
 return {seed,train_sha256:sha(bank.train),validation_sha256:sha(bank.validation),ood_sha256:sha(bank.ood),config};
 })};
}
function validateFrozen(f){const expected=freeze();if(sha(f)!==sha(expected))throw Error('prescore changed or dependency drift');return expected;}
function score(f){validateFrozen(f);const per_seed=[];let pairwise=[],ambig={};
 for(let i=0;i<SEEDS.length;i++){
 const seed=SEEDS[i],tasks=bankForSeed(seed).ood,pool=referencePool(seed),cfg=f.per_seed[i].config;
 const per_family={};for(const task of tasks){
  const outcomes={scratch_blind:episode(task,seed,'scratch',cfg.lr,[]),learned_blind:episode(task,seed,'learned',cfg.lr,cfg.beta),stress_blind:episode(task,seed,'stress',cfg.lr,STRESS_BETA),scratch_family_query:episode(task,seed,'family_query',cfg.lr,[])};
  const full=fitAllLabels(task),vs4=versionSpace(task,outcomes.scratch_blind.purchases,4,pool),vs8=versionSpace(task,outcomes.scratch_blind.purchases,8,pool);
  let different=0;for(let x=0;x<N;x++)if((outcomes.learned_blind.by_k[4].predictions[x]>=.5)!==(outcomes.scratch_blind.by_k[4].predictions[x]>=.5))different++;
  const record={family:task.family,id:task.id,k4:{},k8:{},full_label_fit_balanced_accuracy:full,oracle_pool_k4:vs4,oracle_pool_k8:vs8,learned_vs_scratch_k4_label_flips:different};
  for(const arm of arms){for(const [k,tgt] of [[4,'k4'],[8,'k8']])record[tgt][arm]={balanced_accuracy:outcomes[arm].by_k[k].balanced_accuracy,unqueried_brier:outcomes[arm].by_k[k].unqueried_brier};}
  (per_family[task.family]??=[]).push(record);
 }
 per_seed.push({seed,config:cfg,pool_size:pool.length,families:per_family});
 }
 const summaries={};for(const arm of arms){summaries[arm]={};for(const k of ['k4','k8']){
  let vals=[];for(const s of per_seed)for(const entries of Object.values(s.families))for(const t of entries)vals.push(t[k][arm]);
  summaries[arm][k]={balanced_accuracy:vals.reduce((a,b)=>a+b.balanced_accuracy,0)/vals.length,unqueried_brier:vals.reduce((a,b)=>a+b.unqueried_brier,0)/vals.length};
 }}
 let all=[];for(const s of per_seed)for(const arr of Object.values(s.families))all.push(...arr);
 const avg=fn=>all.reduce((a,t)=>a+fn(t),0)/all.length;
 const attribution={tasks:all.length,full_fit_balanced_accuracy:avg(t=>t.full_label_fit_balanced_accuracy),oracle_pool_k4_candidate_accuracy:avg(t=>t.oracle_pool_k4.oracle_candidate_unqueried_accuracy),oracle_pool_k4_match_count:avg(t=>t.oracle_pool_k4.count),oracle_pool_k4_ambiguity_fraction:avg(t=>t.oracle_pool_k4.ambiguous_unqueried/(N-4)),oracle_pool_k8_match_count:avg(t=>t.oracle_pool_k8.count),learned_prediction_flip_fraction_k4:avg(t=>t.learned_vs_scratch_k4_label_flips/N),v5_beta_max_abs:Math.max(...per_seed.flatMap(s=>s.config.beta.map(Math.abs))),v5_beta_rms:Math.sqrt(per_seed.flatMap(s=>s.config.beta).reduce((a,b)=>a+b*b,0)/(SEEDS.length*6))};
 return {version:VERSION+'-results',prescore_sha256:sha(f),status:'PUBLIC_EXPLORATORY_DIAGNOSTIC_NOT_CONFIRMATORY',summaries,attribution,per_seed};
}
function selfTest(){const a=bankForSeed(SEEDS[0]);if(a.ood.length!==48)throw Error('wrong OOD task count');
 const b=a.ood[0],c=a.ood[12];if(b.id!==c.id||b.family===c.family)throw Error('expected same local ID distinct family');
 if(sha(blindOrder(SEEDS[0],b.id))!==sha(blindOrder(SEEDS[0],c.id)))throw Error('family leaked into blind schedule');
 const schedule=blindOrder(SEEDS[0],b.id);if(schedule.length!==CAP||new Set(schedule).size!==CAP)throw Error('invalid schedule');
 const c0=oldConfig(0);for(const kind of ['scratch','learned','stress','family_query']){const x=episode(b,SEEDS[0],kind,c0.lr,c0.beta);if(x.purchases.length!==8||!Number.isFinite(x.by_k[4].balanced_accuracy))throw Error('episode invalid');if(sha(x)!==sha(episode(b,SEEDS[0],kind,c0.lr,c0.beta)))throw Error('episode nondeterministic');}
 const truth={mask:0b10101},pool=[0b10101,0b110101,0b11000];const vs=versionSpace(truth,[0,1,2,3,4,5,6,7],4,pool);if(vs.count!==2)throw Error('version-space mismatch');
 const f=freeze();f.per_seed[0].config.beta[0]+=0.1;try{validateFrozen(f);throw Error('failed tamper guard');}catch(e){if(!/prescore changed/.test(e.message))throw e;}
 const f2=freeze();if(sha(f2)!==sha(freeze()))throw Error('prescore unstable');
 return {passed:7,seed_count:SEEDS.length,ood_tasks_per_seed:a.ood.length,version:VERSION};
}
export {VERSION,SEEDS,PRIOR_SEEDS,POOL_SEEDS,N,D,blindOrder,episode,versionSpace,fitAllLabels,freeze,validateFrozen,score,selfTest,sha};
if(process.argv[1]&&import.meta.url===pathToFileURL(process.argv[1]).href){const [mode,input,output]=process.argv.slice(2);
 if(mode==='test')console.log(JSON.stringify(selfTest()));
 else if(mode==='freeze'){if(!input||existsSync(input))throw Error('output exists or missing');writeFileSync(input,JSON.stringify(freeze(),null,2)+'\n');console.log('PRESCORE_SHA',sha(JSON.parse(readFileSync(input,'utf8'))));}
 else if(mode==='score'||mode==='verify'){if(!input||!output)throw Error('requires input and output');const x=score(JSON.parse(readFileSync(input,'utf8')));if(mode==='score'){if(existsSync(output))throw Error('refuse overwrite result');writeFileSync(output,JSON.stringify(x,null,2)+'\n');console.log(JSON.stringify(x.attribution));}else{if(sha(x)!==sha(JSON.parse(readFileSync(output,'utf8'))))throw Error('semantic replay mismatch');console.log('PASS semantic replay');}}
 else throw Error('unknown command');
}
