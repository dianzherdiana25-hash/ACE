// Post-score fail-closed audit for ACE R4 v4; no refitting or hypothesis revision.
import {readFileSync} from 'node:fs';
import {gunzipSync} from 'node:zlib';
import {sha,scoreFrozen,ARMS,STEPS,SEEDS,OOD_SPLITS} from './v4_study.mjs';
function assert(x,msg){if(!x)throw Error('R4 v4 audit: '+msg);}
function near(a,b){return Number.isFinite(a)&&Number.isFinite(b)&&Math.abs(a-b)<1e-12;}
function audit(frozen,raw){assert(sha(frozen)===raw.prescore_sha256,'prescore fingerprint');
 assert(sha(scoreFrozen(frozen))===sha(raw),'independent invocation full semantic replay');
 assert(raw.per_seed.length===SEEDS.length,'seed count');
 for(const [i,s] of raw.per_seed.entries()){
  assert(s.seed===SEEDS[i],'seed order');
  for(const arm of ARMS){const t=s.arms[arm],work=t.all_ood.work;
   assert(t.all_ood.tasks===48&&t.all_ood.target_labels===384,'target label count '+arm);
   assert(work.grad_steps===(arm==='nearest'?0:384),'gradient step count '+arm);
   for(const k of STEPS){const metrics=t.all_ood.by_k[k];assert(metrics.balanced_accuracy>=0&&metrics.balanced_accuracy<=1,'balanced range');
    for(const key of ['unqueried_accuracy','unqueried_brier'])assert(metrics[key]>=0&&metrics[key]<=1,'metric bound');
    for(const key of ['balanced_accuracy','unqueried_accuracy','unqueried_brier']){
     const avg=Object.keys(OOD_SPLITS).reduce((v,f)=>v+t.families[f].by_k[k][key],0)/4;
     assert(near(avg,metrics[key]),'family macro aggregate '+arm+' k'+k+' '+key);
    }
   }
  }
 }
 for(const arm of ARMS)for(const k of STEPS)for(const metric of ['balanced_accuracy','unqueried_accuracy','unqueried_brier']){
  const expected=raw.per_seed.reduce((v,s)=>v+s.arms[arm].all_ood.by_k[k][metric],0)/SEEDS.length;
  assert(near(expected,raw.aggregate[arm][k][metric]),'aggregate '+arm+' '+k+' '+metric);
 }
 const winner=ARMS.filter(a=>a!=='learned_conditioned').sort((a,b)=>raw.aggregate[b][4].balanced_accuracy-raw.aggregate[a][4].balanced_accuracy)[0];
 assert(winner===raw.primary.best_control,'strongest control');
 const gain=raw.aggregate.learned_conditioned[4].balanced_accuracy-raw.aggregate[winner][4].balanced_accuracy;
 const seedWins=raw.per_seed.filter(s=>s.arms.learned_conditioned.all_ood.by_k[4].balanced_accuracy>s.arms[winner].all_ood.by_k[4].balanced_accuracy).length;
 const featureCost=raw.per_seed.reduce((v,s)=>v+s.arms.learned_conditioned.all_ood.work.feature_multiplies,0);
 const conditionerCost=raw.per_seed.reduce((v,s)=>v+s.arms.learned_conditioned.all_ood.work.conditioner_ops,0);
 const scratchCost=raw.per_seed.reduce((v,s)=>v+s.arms.scratch.all_ood.work.feature_multiplies,0);
 const computeRatio=(featureCost+conditionerCost)/scratchCost;
 const brier=raw.aggregate.learned_conditioned[4].unqueried_brier<=raw.aggregate[winner][4].unqueried_brier;
 const pass=gain>=.05&&seedWins>=3&&computeRatio<=1.40&&brier;
 assert(near(gain,raw.primary.gain)&&near(computeRatio,raw.primary.compute_ratio),'primary value integrity');
 assert(seedWins===raw.primary.seed_wins&&brier===raw.primary.brier_noninferior&&pass===raw.primary.passed,'primary gate integrity');
 return {pass:true,checked_seed_count:SEEDS.length,ood_tasks:SEEDS.length*48,replayed:sha(raw),scientific_gate_pass:pass,target_label_purchases:SEEDS.length*48*8,primary:raw.primary};
}
function readArchive(path){const s=readFileSync(path,'utf8').trim();if(!/^[A-Za-z0-9+/=]+$/.test(s))throw Error('invalid evidence transport');return JSON.parse(gunzipSync(Buffer.from(s,'base64')).toString('utf8'));}
export {audit,readArchive};
if(process.argv[1]?.endsWith('v4_audit.mjs')){
 const [freezeFile,archive]=process.argv.slice(2);if(!freezeFile||!archive)throw Error('usage: node v4_audit.mjs v4_prescore.json v4_results.json.gz.b64');
 console.log(JSON.stringify(audit(JSON.parse(readFileSync(freezeFile,'utf8')),readArchive(archive))));
}
