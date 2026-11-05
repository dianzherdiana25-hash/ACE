// R4 v6 postscore, read-only consistency audit. Does not retune / rewrite research source.
import {readFileSync,writeFileSync,existsSync} from 'node:fs';
import {pathToFileURL} from 'node:url';
import {SEEDS,N,sha,score,episode} from './v6_diagnostic.mjs';
import {bankForSeed} from './v5_study.mjs';
const ARMS=['scratch_blind','learned_blind','stress_blind','scratch_family_query'];
const FAMILY=['rotating_stencil','change_point_parity','cyclic_xor_intervals','piecewise_modulo'];
function audit(frozen,result){
 if(result.status!=='PUBLIC_EXPLORATORY_DIAGNOSTIC_NOT_CONFIRMATORY'||result.prescore_sha256!==sha(frozen))throw Error('provenance mismatch');
 if(result.per_seed?.length!==4)throw Error('seed count');
 const computed={},cost={};let totalTasks=0,flip=0,refAmbiguous=0;
 for(const arm of ARMS){computed[arm]={};for(const k of ['k4','k8'])computed[arm][k]={balanced_accuracy:0,unqueried_brier:0};cost[arm]={feature_multiply:0,route_ops:0,gradient_steps:0,purchases:0};}
 for(let i=0;i<SEEDS.length;i++){
  const seed=SEEDS[i],f=result.per_seed[i],config=frozen.per_seed[i].config;
  if(f.seed!==seed)throw Error('wrong seed');const bank=bankForSeed(seed).ood;
  for(const family of FAMILY){const entries=f.families[family],tasks=bank.filter(t=>t.family===family);
   if(entries?.length!==12||tasks.length!==12)throw Error('wrong family size');
   for(let j=0;j<12;j++){
    const entry=entries[j],task=tasks[j];if(entry.family!==family||entry.id!==task.id)throw Error('task ordering mismatch');
    totalTasks++;flip+=entry.learned_vs_scratch_k4_label_flips;refAmbiguous+=entry.oracle_pool_k4.ambiguous_unqueried/(N-4);
    for(const arm of ARMS){const kind=arm==='scratch_blind'?'scratch':arm==='learned_blind'?'learned':arm==='stress_blind'?'stress':'family_query',beta=kind==='learned'?config.beta:kind==='stress'?frozen.stress_beta:[];
     const ep=episode(task,seed,kind,config.lr,beta);
     if(ep.purchases.length!==8||new Set(ep.purchases).size!==8)throw Error('query budget');
     for(const [k,field] of [[4,'k4'],[8,'k8']]){
      const expected=entry[field][arm],actual=ep.by_k[k];
      if(Math.abs(expected.balanced_accuracy-actual.balanced_accuracy)>1e-12||Math.abs(expected.unqueried_brier-actual.unqueried_brier)>1e-12)throw Error('episode metric mismatch '+arm+' '+field);
      computed[arm][field].balanced_accuracy+=expected.balanced_accuracy;computed[arm][field].unqueried_brier+=expected.unqueried_brier;
     }
     for(const costKey of ['feature_multiply','route_ops','gradient_steps'])cost[arm][costKey]+=ep.work[costKey];cost[arm].purchases+=ep.purchases.length;
    }
   }
  }
 }
 if(totalTasks!==192)throw Error('total task count');
 for(const arm of ARMS)for(const k of ['k4','k8'])for(const metric of ['balanced_accuracy','unqueried_brier']){
  const mean=computed[arm][k][metric]/totalTasks;
  if(Math.abs(mean-result.summaries[arm][k][metric])>1e-12)throw Error('aggregate mismatch '+arm+' '+k+' '+metric);computed[arm][k][metric]=mean;
 }
 if(Math.abs(flip/(totalTasks*N)-result.attribution.learned_prediction_flip_fraction_k4)>1e-12)throw Error('prediction flip mismatch');
 if(Math.abs(refAmbiguous/totalTasks-result.attribution.oracle_pool_k4_ambiguity_fraction)>1e-12)throw Error('version-space mismatch');
 const fresh=score(frozen);if(sha(fresh)!==sha(result))throw Error('semantic replay mismatch');
 // Report operation counters separately: score() checks full-domain predictions but episode.work omits that common cost.
 return {version:'ACE-R4-v6-audit-v1',status:'PASS',data_sha256:sha(result),prescore_sha256:sha(frozen),count:totalTasks,reference_ambiguity_fraction:refAmbiguous/totalTasks,flipped_predictions_k4:flip,cost,aggregate:computed,scope:'PUBLIC_SYNTHETIC_NOT_INDEPENDENT',note:'Cost counters are incomplete: metric predictions not counted by underlying episode.work. No compute dominance claim.'};
}
export {audit};
if(process.argv[1]&&import.meta.url===pathToFileURL(process.argv[1]).href){const [p,r,out]=process.argv.slice(2);if(!p||!r||!out||existsSync(out))throw Error('usage: audit PRESCORE RESULTS UNUSED_OUT');const data=audit(JSON.parse(readFileSync(p,'utf8')),JSON.parse(readFileSync(r,'utf8')));writeFileSync(out,JSON.stringify(data,null,2)+'\n');console.log('PASS',data.count,'tasks; flips',data.flipped_predictions_k4);}
