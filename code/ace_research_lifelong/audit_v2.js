"use strict";
/** Independent aggregate audit; this code does not regenerate labels or call a learner. */
function auditV2(e) {
  "use strict";
  const issues=[], stats={};
  const push=(ok,msg)=>{if(!ok)issues.push(msg);};
  const cfg=e.cfg;
  push(cfg.protocol==="ACE_R2_V2_PUBLIC_SYNTHETIC","protocol mismatch");
  const methods=cfg.methods,regimes=cfg.regimes,seeds=cfg.seeds;
  const expected=methods.length*regimes.length*seeds.length;
  push(e.raw.length===expected,"wrong experiment count");
  const keySeen=new Set();let updates=0,labels=0,flips=0;
  for(const r of e.raw){
    const key=[r.regime,r.seed,r.method].join(":");
    push(!keySeen.has(key),"duplicate "+key);keySeen.add(key);
    const c=r.costs;
    push(seeds.includes(r.seed)&&regimes.includes(r.regime)&&methods.includes(r.method),"unexpected identity "+key);
    push(c.labels_observed===384,"label budget "+key);
    push(c.updates>0&&c.updates<=767,"gradient steps "+key);
    push(c.coordinate_updates>=c.updates,"coordinate lower bound "+key);
    push(c.replay_examples<=(r.method==="replay"?48:0),"replay memory "+key);
    push(c.expert_count<=4,"expert cap "+key);
    push(c.persistent_scalars<=12,"scalar budget "+key);
    push(r.final_original.length===4&&r.final_latest.length===4,"final shape "+key);
    push(r.final_original.every(x=>x>=0&&x<=1)&&r.final_latest.every(x=>x>=0&&x<=1),"accuracy bounds "+key);
    push(r.first_seen.join(",")==="0,1,2,4","first exposure "+key);
    push(r.trajectory.length===6,"trajectory count "+key);
    if(r.method==="replay")push(c.updates===767&&c.replay_examples===48,"replay exact cost "+key);
    if(r.method==="frozen")push(c.updates===64,"frozen exact cost "+key);
    if(r.method==="ewc")push(c.fisher_ops===6*64*3,"ewc fisher cost "+key);
    if(r.regime==="conflicting_flip") {
      // The original and flipped task0 labels are exact complements for every x.
      push(Math.abs(r.task0_original_final+r.flip_task0_final-1)<1e-9,"flip complement "+key);
      flips++;
    }
    labels+=c.labels_observed;updates+=c.updates;
  }
  for(const regime of regimes)for(const method of methods){
    const rows=e.raw.filter(r=>r.regime===regime&&r.method===method);
    push(rows.length===5,"missing seeds "+regime+":"+method);
    for(const key of ["final_accuracy","ood_accuracy","retention_delta_unmodified","forward_transfer_delta","shifted_adaptation_gain","flip_adaptation_gain"]){
      const m=rows.reduce((s,r)=>s+r[key],0)/rows.length;
      push(Math.abs(m-e.summary[regime][method][key])<1e-10,"mean mismatch "+regime+":"+method+":"+key);
    }
  }
  const result={
    audit_id:"R2_V2_INDEPENDENT_RESULT_MATRIX_AUDIT_V1",
    checked_groupings:regimes.length*methods.length,
    expected_trials:expected,found_trials:e.raw.length,distinct_trials:keySeen.size,
    logical_labels_across_method_runs:labels,logical_gradient_steps_across_method_runs:updates,
    flip_complement_checks:flips,
    metric_warning:"Under conflicting_flip, ood_accuracy uses original task-0 labels, not newest flipped labels. Treat as original-target compatibility diagnostic; do not interpret as latest-target OOD generalization.",
    semantic_limitations:["Comparators with fixed slots have a task-context prior and are not blinded to context locations.",
      "Flat sign tasks saturate in separated contexts. This study cannot establish a novel continual-learning mechanism.",
      "Numerical replay validates a same-origin public dataset, not an independent evaluator or unseen family."],
    issues,status:issues.length?"FAIL":"PASS"
  };
  return result;
}
module.exports={auditV2};
if(require.main===module){const fs=require("node:fs");const data=JSON.parse(fs.readFileSync(process.argv[2]||"R2_V2_RESULTS.json","utf8"));const report=auditV2(data);console.log(JSON.stringify(report,null,2));if(report.status!=="PASS")process.exitCode=1;}
