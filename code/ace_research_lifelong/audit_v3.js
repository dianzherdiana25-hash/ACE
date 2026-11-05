"use strict";
/* R2 independent aggregation/audit. No learner invocation or label generation. */
function auditV3(record){
  "use strict";
  const p=record.protocol,errors=[];
  const assert=(ok,msg)=>{if(!ok)errors.push(msg)};
  const unique=new Set();
  const group={};
  const expected=p.seeds.length*p.families.length*p.regimes.length*p.methods.length;
  assert(record.results.length===expected,"row_count");
  let labels=0,updates=0,penalties=0,fisher=0;
  for(const r of record.results){
    const id=[r.seed,r.family,r.regime,r.method].join(";");
    assert(!unique.has(id),"duplicate "+id);unique.add(id);
    assert(p.seeds.includes(r.seed)&&p.families.includes(r.family)&&p.regimes.includes(r.regime)&&p.methods.includes(r.method),"unexpected identity "+id);
    const provenance=r.provenance||{};
    assert(provenance.train_rule_seeds?.length===p.episodes.length&&provenance.train_rule_seeds.every(x=>x===r.seed),"training teacher differs "+id);
    assert(provenance.test_rule_seeds?.length===4&&provenance.test_rule_seeds.every(x=>x===r.seed),"test teacher differs "+id);
    assert(provenance.ood_rule_seeds?.length===4&&provenance.ood_rule_seeds.every(x=>x===r.seed),"OOD teacher differs "+id);
    const c=r.costs;
    assert(c.new_labels===512,"label budget "+id);
    assert(c.updates===(r.method==="frozen"?64:r.method==="replay"?1023:512),"gradient budget "+id);
    assert(c.coordinate_ops===c.updates*(["selective","no_transfer","fixed_slots","oracle"].includes(r.method)?16:48),"coordinate budget "+id);
    assert(c.experts<=4,"expert cap "+id);
    assert(c.replay_examples===(r.method==="replay"?48:0),"replay buffer "+id);
    assert(c.penalty_ops===(r.method==="ewc"?24576:0),"EWC penalty workload "+id);
    assert(c.fisher_ops===(r.method==="ewc"?24576:0),"EWC fisher workload "+id);
    assert(r.trajectory.length===8&&r.trajectory.every((e,i)=>e.episode===i&&e.task===p.episodes[i]),"trajectory "+id);
    assert(r.final_by_task.length===4&&r.final_by_task.every(x=>x>=0&&x<=1),"final metrics "+id);
    const finalMean=r.final_by_task.reduce((s,x)=>s+x,0)/4;
    assert(Math.abs(finalMean-r.final_accuracy)<1e-12,"final aggregation "+id);
    labels+=c.new_labels;updates+=c.updates;penalties+=c.penalty_ops;fisher+=c.fisher_ops;
    const groupKey=r.family+"/"+r.regime+"/"+r.method;
    (group[groupKey]??=[]).push(r);
  }
  for(const family of p.families)for(const regime of p.regimes)for(const method of p.methods){
    const g=group[family+"/"+regime+"/"+method]||[];
    assert(g.length===p.seeds.length,"missing seeds in "+family+"/"+regime+"/"+method);
    for(const k of ["final_accuracy","average_forgetting","backward_transfer","forward_transfer","ood_accuracy"]){
      const mean=g.reduce((s,x)=>s+x[k],0)/g.length;
      assert(Math.abs(mean-record.summary[family+"/"+regime][method][k])<1e-12,"summary mismatch "+family+"/"+regime+"/"+method+"/"+k);
    }
  }
  const perSeed=[];
  for(const seed of p.seeds){
    const ds=[],rs=[],drift=[];
    for(const family of p.families)for(const regime of p.regimes){
      const s=record.summary[family+"/"+regime],find=(method)=>record.results.find(r=>r.seed===seed&&r.family===family&&r.regime===regime&&r.method===method);
      const selective=find("selective"),equal=Math.max(find("no_transfer").final_accuracy,find("fixed_slots").final_accuracy);
      ds.push(selective.final_accuracy-equal);
      rs.push(selective.final_accuracy-find("replay").final_accuracy);
      drift.push(selective.final_accuracy-selective.ood_accuracy);
    }
    const mean=a=>a.reduce((s,v)=>s+v,0)/a.length;
    perSeed.push({seed,delta_capacity:mean(ds),delta_replay:mean(rs),ood_drop:mean(drift)});
  }
  const mean=a=>a.reduce((s,v)=>s+v,0)/a.length;
  function interval(key){
    const seedValues=perSeed.map(x=>x[key]);const sampled=[];
    // Exact 4^4 clustered with replacement over the four public seeds, not an independent CI.
    for(let a=0;a<4;a++)for(let b=0;b<4;b++)for(let c=0;c<4;c++)for(let d=0;d<4;d++)sampled.push(mean([seedValues[a],seedValues[b],seedValues[c],seedValues[d]]));
    sampled.sort((a,b)=>a-b);
    return {mean:mean(seedValues),cluster_seed_resampling_min95:sampled[6],cluster_seed_resampling_max95:sampled[249],support_seeds:4,method:"exact 4^4 seed bootstrap replicates (descriptive only)"};
  }
  const paired={
    selective_minus_matched_capacity:interval("delta_capacity"),
    selective_minus_replay:interval("delta_replay"),
    selective_ood_drop:interval("ood_drop")
  };
  assert(Math.abs(paired.selective_minus_replay.mean-(record.aggregate.candidate_final-record.aggregate.replay_reference))<1e-12,"replay contrast");
  // groupwise strongest comparator differs from per-seed strongest; report rather than silently equalize.
  const groupwiseContrast=record.aggregate.candidate_final-record.aggregate.equal_capacity_reference;
  const seedwiseContrast=paired.selective_minus_matched_capacity.mean;
  const caveats=[
    "Gate's equal-capacity reference takes max of group means; seed-paired contrast takes max per seed and is a more stringent estimand.",
    "Teacher weights are intentionally shared across train/test/ood for each seed/family/task, with disjoint data RNG streams. This corrects the earlier invalid v3.",
    "4 seeds and synthetic teacher families are not an independent sample of real-world tasks. Bootstrap intervals are descriptive, not confirmatory.",
    "Frozen learner's zero forgetting can be misleading because it barely acquires new tasks.",
    "The task-ID oracle is privileged and not a deployable comparator.",
    "No exact-head GitHub Actions CI or independent blinded holdout has been run."
  ];
  const output={
    audit_id:"R2_V3_CORRECTED_INDEPENDENT_AGGREGATE_AUDIT_V1",
    rows_expected:expected,rows_validated:unique.size,groups:Object.keys(group).length,
    logical_labels_recounted:labels,gradient_updates_recounted:updates,ewc_penalty_coordinates:penalties,ewc_fisher_coordinates:fisher,
    per_seed:perSeed,paired_descriptive:paired,groupwise_capacity_contrast:groupwiseContrast,
    seedwise_capacity_contrast:seedwiseContrast,
    gate_recorded:record.gates,decision_recorded:record.decision,
    limitations:caveats,
    findings:errors,status:errors.length?"FAIL":"PASS"
  };
  return output;
}
module.exports={auditV3};
if(require.main===module){const fs=require("node:fs"),data=JSON.parse(fs.readFileSync(process.argv[2]||"R2_V3_RESULTS.json","utf8"));const a=auditV3(data);console.log(JSON.stringify(a,null,2));if(a.status!=="PASS")process.exitCode=1;}
