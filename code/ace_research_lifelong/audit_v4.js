"use strict";
/** ACE R2 v4: independent post-hoc matrix arithmetic audit. No learner or label-generator called. */
function auditV4(report){
 "use strict";
 const p=report.protocol,errors=[];const requireTrue=(ok,reason)=>{if(!ok)errors.push(reason);};
 const mean=xs=>xs.reduce((a,b)=>a+b,0)/xs.length;
 const keys=["final_accuracy","final_known_rejection","novel_rejected","forgetting","backward_transfer","support_conditioned_forward_transfer"];
 const costKeys=["train_updates","eval_adaptation_updates","weight_coordinate_ops","penalty_ops","fisher_ops","router_predictions","stored_replay_examples","experts","persistent_numeric_scalars","forced_reuse"];
 const seen=new Set(),count=p.seeds.length*p.regimes.length*p.methods.length;
 requireTrue(report.raw.length===count,"experiment count mismatch");
 let trainLabels=0,evalSupports=0,evalQueries=0,gradientUpdates=0,routerPredicts=0;
 for(const r of report.raw){
  const id=`${r.seed}/${r.regime}/${r.method}`;
  requireTrue(!seen.has(id),"duplicate "+id);seen.add(id);
  requireTrue(p.seeds.includes(r.seed)&&p.regimes.includes(r.regime)&&p.methods.includes(r.method),"unexpected method/seed/regime "+id);
  requireTrue(r.history.length===p.schedule.length,"incomplete history "+id);
  requireTrue(r.history.every((x,i)=>x.episode===i&&x.task===p.schedule[i]),"wrong episode schedule "+id);
  requireTrue(r.history.every(x=>x.per_task.length===4&&x.rejected.length===4),"incomplete task state "+id);
  const terminal=r.history.at(-1);
  requireTrue(terminal.per_task.every(x=>x>=0&&x<=1),"illegal accuracy "+id);
  requireTrue(Math.abs(mean(terminal.per_task)-r.final_accuracy)<1e-12,"final accuracy inconsistent "+id);
  requireTrue(Math.abs(terminal.rejected.filter(Boolean).length/4-r.final_known_rejection)<1e-12,"known rejection inconsistent "+id);
  let forgetting=0;
  for(let t=0;t<4;t++){
   let peak=0;
   const first=p.schedule.indexOf(t);
   requireTrue(r.first_exposure.some(x=>x.episode===first&&x.task===t),"first exposure wrong "+id);
   requireTrue(Math.abs(r.first_after[t]-r.history[first].per_task[t])<1e-12,"first after inconsistent "+id);
   if(t>0)requireTrue(Math.abs(r.first_before[t]-r.history[first-1].per_task[t])<1e-12,"forward pretest "+id);
   for(let e=first;e<r.history.length;e++)peak=Math.max(peak,r.history[e].per_task[t]);
   forgetting+=Math.max(0,peak-terminal.per_task[t]);
  }
  forgetting/=4;
  requireTrue(Math.abs(forgetting-r.forgetting)<1e-12,"forgetting inconsistency "+id);
  requireTrue(Math.abs(mean(terminal.per_task.map((v,t)=>v-r.first_after[t]))-r.backward_transfer)<1e-12,"BWT "+id);
  requireTrue(Math.abs(mean(r.first_before.slice(1).map(v=>v-.5))-r.support_conditioned_forward_transfer)<1e-12,"FWT "+id);
  const proof=r.provenance;
  requireTrue(proof.teacher_signatures_test.length===4&&proof.train_teacher_signatures.length===8,"teacher fingerprint structure "+id);
  for(let t=0;t<4;t++){
   const [supportSig,querySig]=proof.teacher_signatures_test[t];
   requireTrue(supportSig===querySig,"eval support/query teachers mismatch "+id);
   for(let e=0;e<8;e++)if(p.schedule[e]===t)requireTrue(proof.train_teacher_signatures[e]===supportSig,"train/test teacher mismatch "+id);
  }
  requireTrue(proof.train_streams.length===8&&new Set(proof.train_streams).size===8,"train split streams "+id);
  requireTrue(proof.support_streams.length===4&&proof.query_streams.length===4,"eval split streams "+id);
  requireTrue(proof.support_streams.every((x,j)=>x!==proof.query_streams[j]),"support/query split collision "+id);
  requireTrue(r.cost.train_label_accesses===512&&r.cost.evaluation_support_label_accesses===396&&r.cost.evaluation_query_scores===3072,"label budget "+id);
  requireTrue(r.cost.train_updates===(r.method==="frozen"?64:r.method==="replay"?1023:512),"train update count "+id);
  requireTrue(r.cost.eval_adaptation_updates===(r.method==="fast_adapt"?384:0),"eval adapt budget "+id);
  requireTrue(r.cost.experts<=4,"specialist cap "+id);
  requireTrue(r.cost.stored_replay_examples===(r.method==="replay"?48:0),"replay buffer "+id);
  requireTrue(r.cost.penalty_ops===(r.method==="ewc"?6144:0)&&r.cost.fisher_ops===(r.method==="ewc"?6144:0),"EWC overhead "+id);
  trainLabels+=r.cost.train_label_accesses;evalSupports+=r.cost.evaluation_support_label_accesses;evalQueries+=r.cost.evaluation_query_scores;
  gradientUpdates+=r.cost.train_updates+r.cost.eval_adaptation_updates;routerPredicts+=r.cost.router_predictions;
 }
 for(const regime of p.regimes)for(const method of p.methods){
  const rows=report.raw.filter(r=>r.regime===regime&&r.method===method);
  requireTrue(rows.length===5,"missing seed group "+regime+"/"+method);
  for(const k of keys){
   const avg=mean(rows.map(r=>r[k]));
   requireTrue(Math.abs(avg-report.summary[regime][method][k])<1e-12,"group stat "+regime+"/"+method+"/"+k);
  }
  for(const k of costKeys){
   const avg=mean(rows.map(r=>r.cost[k]));
   requireTrue(Math.abs(avg-report.summary[regime][method][k])<1e-12,"group cost "+regime+"/"+method+"/"+k);
  }
 }
 const bySeed=[];
 for(const seed of p.seeds){
  const s=name=>report.raw.find(r=>r.seed===seed&&r.regime==="aliased"&&r.method===name);
  requireTrue(p.methods.every(n=>!!s(n)),"incomplete pairing for seed "+seed);
  bySeed.push({seed,against_context:s("evidence").final_accuracy-s("context").final_accuracy,
    transfer_effect:s("evidence").final_accuracy-s("evidence_zero").final_accuracy,
    against_fast_adapt:s("evidence").final_accuracy-s("fast_adapt").final_accuracy,
    evidence_accuracy:s("evidence").final_accuracy,
    evidence_known_reject:s("evidence").final_known_rejection,
    evidence_novel_reject:s("evidence").novel_rejected
  });
 }
 function interval(key){
  const a=bySeed.map(x=>x[key]);const boot=[];
  for(let i=0;i<5;i++)for(let j=0;j<5;j++)for(let k=0;k<5;k++)for(let q=0;q<5;q++)for(let z=0;z<5;z++)
   boot.push(mean([a[i],a[j],a[k],a[q],a[z]]));
  boot.sort((x,y)=>x-y);
  return {mean:mean(a),seed_bootstrap_95_low:boot[Math.floor(.025*boot.length)],
   seed_bootstrap_95_high:boot[Math.floor(.975*boot.length)],seed_count:5,
   interpretation:"descriptive resampling within author-visible synthetic seeds, NOT independent CI"};
 }
 const paired={
  evidence_minus_context:interval("against_context"),
  evidence_minus_zero_transfer:interval("transfer_effect"),
  evidence_minus_support_finetuning:interval("against_fast_adapt")
 };
 const a=report.summary.aliased;
 const recomputedGates={
  evidence_beats_context:a.evidence.final_accuracy-a.context.final_accuracy>=p.gates.aliased_minus_context,
  transfer_beats_no_transfer:a.evidence.final_accuracy-a.evidence_zero.final_accuracy>=p.gates.transfer_minus_zero,
  novel_rejection:a.evidence.novel_rejected>=p.gates.unknown_reject_min,
  known_false_rejection:a.evidence.final_known_rejection<=p.gates.known_reject_max,
  evidence_beats_fast_adapt:a.evidence.final_accuracy-a.fast_adapt.final_accuracy>=p.gates.aliased_minus_fast_adapt,
  absolute_accuracy:a.evidence.final_accuracy>=p.gates.aliased_min
 };
 requireTrue(JSON.stringify(recomputedGates)===JSON.stringify(report.gates),"gate drift/mismatch");
 return {
  status:errors.length?"FAIL":"PASS",issues:errors,
  run_count:report.raw.length,unique_runs:seen.size,method_regime_groups:p.methods.length*p.regimes.length,
  logical_training_label_accesses_across_runs:trainLabels,
  logical_eval_support_label_accesses_across_runs:evalSupports,
  logical_eval_query_label_scores_across_runs:evalQueries,
  logical_gradient_updates_across_runs:gradientUpdates,
  specialist_router_prediction_calls_across_runs:routerPredicts,
  paired_by_seed:bySeed,paired_bootstrap_descriptive:paired,
  gates:recomputedGates,decision:report.decision,
  caveats:[
   "No task ID is exposed to the evidence/context/SGD/EWC/replay/fast-adapt predictor, but source-level code review remains required.",
   "The same x/y teachers and sample RNG are intentionally shared between regimes; the 135 method-regime-seed runs are NOT 135 independent task samples.",
   "Each method is charged 396 evaluation-support label access events per run, of which 60 are unique per task-set regime; repeated checkpoint accesses do not constitute new labels.",
   "The evidence candidate spends expert log-loss prediction work and up to 56 persistent scalars; plain SGD uses only 12. Compute and storage cannot be treated as matched for global comparisons.",
   "The matched evidence_zero comparison isolates the effect of 0.20 weight-transfer initialization; it ties/slightly surpasses the candidate.",
   "Novel fifth-task detection is author-visible and has one support block per synthetic seed; it is not proof of real-world anomaly detection.",
   "Frozen near-zero forgetting is trivial without skill acquisition; evaluation loss cannot be treated as unbiased scientific confirmation.",
   "No GitHub Actions exact-head CI and no independently sealed task bank was executed."
  ]
 };
}
module.exports={auditV4};
if(require.main===module){const fs=require("node:fs");const row=JSON.parse(fs.readFileSync(process.argv[2]||"R2_V4_RESULTS.json","utf8"));const out=auditV4(row);console.log(JSON.stringify(out,null,2));if(out.status!=="PASS")process.exitCode=1;}
