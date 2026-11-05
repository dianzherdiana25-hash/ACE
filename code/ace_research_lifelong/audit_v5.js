"use strict";
/** R2-v5 output-only audit: independently recomputes calibration, decisions, metrics, and preregistered gates. */
function auditV5(record){
  "use strict";
  const p=record.protocol,fail=[];
  const check=(value,why)=>{if(!value)fail.push(why);};
  const mean=a=>a.reduce((s,x)=>s+x,0)/a.length;
  const q90=a=>{const sorted=a.slice().sort((a,b)=>a-b);return sorted[Math.ceil(.9*sorted.length)-1];};
  const mkeys=["known_fpr","shifted_fpr","unrelated_tpr","near_tpr","unknown_tpr",
                "known_accuracy_with_abstention","accuracy_if_accepted"];
  const allMethods=p.methods;
  const seenSeeds=new Set();let trainLabels=0,calSupports=0,evaluationSupports=0,routerPredictions=0;
  const paired=[];
  check(p.id==="ACE_R2_V5_ARCHIVE_NOVELTY_PUBLIC","protocol identity");
  check(record.runs.length===p.seeds.length,"run count");
  for(const r of record.runs){
    const id=r.seed;
    check(p.seeds.includes(id)&&!seenSeeds.has(id),"seed identity "+id);seenSeeds.add(id);
    check(r.archive_hash_before===r.archive_hash_after,"archive mutability "+id);
    check(r.archive_heads>0&&r.archive_heads<=4,"head count "+id);
    check(r.training.updates===512&&r.training.labels===512,"training budget "+id);
    check(r.training.teacher_signatures.length===8,"train teacher shape "+id);
    check(new Set(r.training.streams).size===8,"training stream distinct "+id);
    check(r.calibration.rows.length===48&&r.calibration.all_probe_rows.length===48,"calibration shape "+id);
    check(r.calibration.accesses===48*16,"calibration label costs "+id);
    const glob=q90(r.calibration.rows.map(x=>x.score));
    check(Math.abs(glob-r.calibration.global_threshold)<1e-12,"calibration quantile "+id);
    for(let k=0;k<r.archive_heads;k++){
      const subset=r.calibration.rows.filter(x=>x.best===k).map(x=>x.score);
      const val=subset.length>=4?q90(subset):glob;
      check(Math.abs(val-r.calibration.slot_thresholds[k])<1e-12,"slot quantile "+id+"/"+k);
    }
    check(r.evaluation.support_label_accesses===192*16,"evaluation support labels "+id);
    check(r.evaluation.head_score_evaluations===192*16*r.archive_heads,"evaluation scoring "+id);
    for(const kind of ["known","shift","unrelated","near"]){
      const rows=r.evaluation.kind_rows[kind];
      check(rows.length===48,"rows "+id+"/"+kind);
      check(new Set(rows.map(x=>x.stream)).size===48,"duplicate stream "+id+"/"+kind);
      for(const z of rows){
        const task=z.task, base=r.query_provenance[task].signature;
        check(Number.isFinite(z.score)&&z.score>=0,"score "+id+"/"+kind);
        check(z.best>=0&&z.best<r.archive_heads,"best-head bounds "+id+"/"+kind);
        check(allMethods.every(m=>typeof z.decisions[m]==="boolean"),"decision shape "+id+"/"+kind);
        if(kind==="known"||kind==="shift")
          check(z.teacher_signature===base,"known/shift teacher function "+id+"/"+kind);
        if(kind==="unrelated")
          check(z.teacher_signature===r.unrelated_signatures[task]&&z.teacher_signature!==base,
                "unrelated teacher collision "+id);
        if(kind==="near")
          check(z.teacher_signature===r.near_signatures[task]&&z.teacher_signature!==base,
                "near teacher collision "+id);
        for(const m of allMethods){
          const threshold=m==="always_reuse"?Infinity:m==="fixed61"?.61:
            m==="slot_q90"?r.calibration.slot_thresholds[z.best]:r.calibration.global_threshold;
          const expected=z.score>threshold||(m==="global_q90_margin"&&z.gap<p.margin_gate);
          check(expected===z.decisions[m],"decision recomputation "+id+"/"+kind+"/"+m);
        }
      }
    }
    for(const m of allMethods){
      const stat=r.evaluation.per_method[m];
      const counts=stat.raw_counts;
      const a=Object.fromEntries(["known","shift","unrelated","near"].map(kind=>[
        kind,r.evaluation.kind_rows[kind].filter(row=>row.decisions[m]).length]));
      check(a.known===counts.known_rej&&a.shift===counts.shift_rej&&
           a.unrelated===counts.unrelated_rej&&a.near===counts.near_rej,
            "reject event tally "+id+"/"+m);
      check(a.known+counts.accepted_known===48,"accepted known tally "+id+"/"+m);
      check(counts.known_correct>=0&&counts.known_correct<=counts.accepted_known*96,"query scoring bounds "+id+"/"+m);
      const reconstructed={
        known_fpr:a.known/48,
        shifted_fpr:a.shift/48,
        unrelated_tpr:a.unrelated/48,
        near_tpr:a.near/48,
        unknown_tpr:(a.unrelated+a.near)/96,
        known_accuracy_with_abstention:counts.known_correct/(48*96),
        accuracy_if_accepted:counts.accepted_known?counts.known_correct/(counts.accepted_known*96):0
      };
      for(const key of mkeys)
        check(Math.abs(reconstructed[key]-stat[key])<1e-12,"metric "+id+"/"+m+"/"+key);
    }
    const e=r.evaluation.per_method;
    paired.push({
      seed:id,
      slot_minus_global_unknown_tpr:e.slot_q90.unknown_tpr-e.global_q90.unknown_tpr,
      global_minus_fixed_unrelated_tpr:e.global_q90.unrelated_tpr-e.fixed61.unrelated_tpr,
      global_known_fpr:e.global_q90.known_fpr,
      slot_known_fpr:e.slot_q90.known_fpr
    });
    trainLabels+=r.training.labels;
    calSupports+=r.calibration.accesses;
    evaluationSupports+=r.evaluation.support_label_accesses;
    routerPredictions+=r.training.router_predictions+r.evaluation.head_score_evaluations+
                      r.calibration.all_probe_rows.length*16*r.archive_heads;
  }
  for(const m of allMethods)for(const key of mkeys){
    const v=mean(record.runs.map(r=>r.evaluation.per_method[m][key]));
    check(Math.abs(v-record.summary[m][key])<1e-12,"across seed summary "+m+"/"+key);
  }
  const G=record.summary.global_q90,S=record.summary.slot_q90,F=record.summary.fixed61;
  const gates={
    global_unrelated_gain:G.unrelated_tpr-F.unrelated_tpr>=p.gates.global_vs_fixed_unrelated_gain&&G.known_fpr<=p.gates.max_known_fpr,
    near_novelty:G.near_tpr>=p.gates.min_near_tpr,
    context_shift_control:G.shifted_fpr<=p.gates.max_shift_fpr,
    preserved_known_accuracy:G.known_accuracy_with_abstention>=p.gates.min_known_accuracy,
    slot_beats_global:S.unknown_tpr-G.unknown_tpr>=p.gates.min_slot_gain&&S.known_fpr<=p.gates.max_known_fpr
  };
  check(JSON.stringify(gates)===JSON.stringify(record.gates),"gate mismatch");
  const descriptive={};
  for(const key of ["slot_minus_global_unknown_tpr","global_minus_fixed_unrelated_tpr"]){
    const v=paired.map(row=>row[key]),bootstrap=[];
    for(let a=0;a<5;a++)for(let b=0;b<5;b++)for(let c=0;c<5;c++)for(let d=0;d<5;d++)for(let e=0;e<5;e++){
      bootstrap.push(mean([v[a],v[b],v[c],v[d],v[e]]));
    }
    bootstrap.sort((a,b)=>a-b);
    descriptive[key]={mean:mean(v),seed_resample_low_95:bootstrap[Math.floor(bootstrap.length*.025)],
      seed_resample_high_95:bootstrap[Math.floor(bootstrap.length*.975)],n_seed:5,
      caveat:"descriptive public synthetic seed bootstrap, not independent inferential CI"};
  }
  return {status:fail.length?"FAIL":"PASS",errors:fail,
    protocol:p.id,
    expected_seeds:p.seeds.length,validated_seeds:seenSeeds.size,
    calibration_blocks:record.runs.length*48,
    known_blocks:record.runs.length*48,
    unrelated_blocks:record.runs.length*48,
    near_blocks:record.runs.length*48,
    shift_blocks:record.runs.length*48,
    logical_train_label_accesses:trainLabels,
    logical_calibration_label_accesses:calSupports,
    logical_evaluation_support_accesses:evaluationSupports,
    logical_expert_prediction_calls:routerPredictions,
    gates,paired_seeds:paired,descriptive,
    limitations:[
      "Independent arithmetic auditor reads stored result rows, not separate model weights or oracle implementations.",
      "Evaluation support queries are repeated across methods on a common archive, so method scores are correlated; no independent test custody.",
      "Unknown teacher near-variants differ by a single large coefficient sign; this is controlled synthetic novelty, not new natural-world capabilities.",
      "Inference support labels are visible to the detector; this is not zero-shot recognition.",
      "No task-ID oracle was available to the detector, but direct source review rather than this matrix audit is required to verify absence of leaks.",
      "Head weights frozen by source-level hash, not by independent external process",
      "Per-slot q90 is a precommitted comparator not a discovered generally superior algorithm.",
      "No exact-head clean-checkout Node CI verified; scientific generalization remains HOLD."
    ]};
}
module.exports={auditV5};
if(require.main===module){const fs=require("node:fs");const raw=JSON.parse(fs.readFileSync(process.argv[2]||"R2_V5_RESULTS.json","utf8"));const a=auditV5(raw);console.log(JSON.stringify(a,null,2));if(a.status!=="PASS")process.exitCode=1;}
