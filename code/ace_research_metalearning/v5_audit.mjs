// Independent read-only arithmetic audit of archived v5 scores (no model refit).
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {pathToFileURL} from 'node:url';
const SHA=x=>createHash('sha256').update(JSON.stringify(x)).digest('hex');
const CLOSE=(a,b)=>Number.isFinite(a)&&Number.isFinite(b)&&Math.abs(a-b)<=1e-11;
const METRICS=['balanced_accuracy','unqueried_accuracy','unqueried_brier'];
const STEPS=[0,1,2,4,8],FAMILIES=['rotating_stencil','change_point_parity','cyclic_xor_intervals','piecewise_modulo'];
const ARMS=['scratch','nearest','joint','reptile','random_route','learned_static_route','learned_conditional_route'];
function fail(msg){throw Error('AUDIT_FAIL: '+msg);}
function audit(prescore,results){if(results.prescore_sha256!==SHA(prescore))fail('prescore SHA256 mismatch');if(prescore.per_seed.length!==4||results.per_seed.length!==4)fail('seed count');
 if(!ARMS.every(a=>results.aggregate[a])||Object.keys(results.aggregate).length!==ARMS.length)fail('arm list');
 for(let i=0;i<4;i++){
  const seed=results.per_seed[i],f=prescore.per_seed[i];if(seed.seed!==f.seed)fail('seed identity');
  if(Object.keys(seed.arms).length!==ARMS.length)fail('per seed arm count');
  for(const arm of ARMS){const a=seed.arms[arm];if(a.all_ood.tasks!==48||a.all_ood.target_purchases!==384)fail('target label budget');
   for(const family of FAMILIES)if(a.families[family]?.tasks!==12||a.families[family]?.target_purchases!==96)fail('family budget');
   for(const k of STEPS){for(const m of METRICS){const val=a.all_ood.by_k[k][m];if(!Number.isFinite(val)||val<0||val>(m==='unqueried_brier'?1:1))fail('metric domain');
     const familyAvg=FAMILIES.reduce((v,family)=>v+a.families[family].by_k[k][m],0)/4;if(!CLOSE(val,familyAvg))fail('family weighted mean '+seed.seed+':'+arm+':'+k+':'+m);
    }
   }
  }
 }
 for(const arm of ARMS)for(const k of STEPS)for(const m of METRICS){const avg=results.per_seed.reduce((s,v)=>s+v.arms[arm].all_ood.by_k[k][m],0)/4;if(!CLOSE(avg,results.aggregate[arm][k][m]))fail('aggregate '+arm+':'+k+':'+m);}
 const meta=results.aggregate.learned_conditional_route[4].balanced_accuracy;
 const best=ARMS.filter(x=>x!=='learned_conditional_route').sort((a,b)=>results.aggregate[b][4].balanced_accuracy-results.aggregate[a][4].balanced_accuracy)[0];
 if(results.primary.best_control!==best||!CLOSE(results.primary.learned_balanced_k4,meta)||!CLOSE(results.primary.control_balanced_k4,results.aggregate[best][4].balanced_accuracy))fail('primary best control');
 const advantage=meta-results.aggregate[best][4].balanced_accuracy;const seedWins=results.per_seed.filter(s=>s.arms.learned_conditional_route.all_ood.by_k[4].balanced_accuracy>s.arms[best].all_ood.by_k[4].balanced_accuracy).length;
 const cost=w=>w.feature_multiply+w.route_ops+w.nearest_pairs;
 const targetWork=results.per_seed.reduce((s,v)=>s+cost(v.arms.learned_conditional_route.all_ood.work),0);
 const baseWork=results.per_seed.reduce((s,v)=>s+cost(v.arms.scratch.all_ood.work),0);
 const ratio=targetWork/baseWork,extraBrier=results.aggregate.learned_conditional_route[4].unqueried_brier-results.aggregate[best][4].unqueried_brier;
 if(!CLOSE(advantage,results.primary.advantage)||seedWins!==results.primary.seed_wins||!CLOSE(ratio,results.primary.target_work_ratio_vs_scratch)||!CLOSE(extraBrier,results.primary.extra_brier_vs_best))fail('primary arithmetic');
 const p=prescore.primary;if(results.primary.passed!==(advantage>=p.min_absolute_gain&&seedWins>=p.min_seed_wins&&ratio<=p.max_target_compute_ratio&&extraBrier<=p.max_extra_unqueried_brier))fail('scientific gate');
 for(const a of ARMS){const total=results.per_seed.reduce((s,v)=>s+v.arms[a].all_ood.target_purchases,0);if(total!==1536)fail('total purchased labels');}
 return {status:'PASS',audit_checks:10,seed_count:4,ood_tasks:192,arms:ARMS.length,families:FAMILIES.length,per_arm_target_labels:1536,best_control:best,balanced_accuracy_learned:meta,balanced_accuracy_best:results.aggregate[best][4].balanced_accuracy,advantage,seed_wins:seedWins,compute_ratio:ratio,meta_meta_work:prescore.per_seed.reduce((s,v)=>s+v.fit.meta_logical_work,0),meta_objective_calls:prescore.per_seed.reduce((s,v)=>s+v.fit.meta_objective_calls,0),gate:'REJECTED'};
}
export {audit};
if(process.argv[1]&&import.meta.url===pathToFileURL(process.argv[1]).href){const [p,r]=process.argv.slice(2);if(!p||!r)throw Error('usage: node v5_audit.mjs PRESCORE RESULTS');console.log(JSON.stringify(audit(JSON.parse(readFileSync(p,'utf8')),JSON.parse(readFileSync(r,'utf8'))),null,2));}
