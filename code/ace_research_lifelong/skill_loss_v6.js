"use strict";
/** Diagnostic posthoc per-skill audit; independently checks mean vs worst-case forgetting. */
function skillLossV6(record){
 "use strict";
 const threshold=0.20;
 const methods=record.protocol.methods;
 const out={audit_id:"ACE_R2_V6_SKILL_LEVEL_FORGETTING_CANARY",threshold_absolute_accuracy_drop:threshold,
   by_method:{},critical_findings:[],status:"PASS"};
 function assert(cond,msg){if(!cond){out.critical_findings.push(msg);out.status="FAIL";}}
 for(const method of methods){
   const rows=record.runs.filter(r=>r.method===method);
   const details=[];
   for(const r of rows){
     assert(r.initial_old.length===4&&r.after_old.length===4,"bad task matrix "+method);
     for(let task=0;task<4;task++){
       details.push({seed:r.seed,family:r.family,novelty:r.novelty,task,
         before:r.initial_old[task],after:r.after_old[task],
         drop:r.initial_old[task]-r.after_old[task]});
     }
   }
   assert(details.length===80,"wrong per-skill cases "+method);
   const sort=details.slice().sort((a,b)=>b.drop-a.drop);
   const fam={};
   for(const family of record.protocol.families){
     const subset=details.filter(x=>x.family===family);
     fam[family]={old_skill_cases:subset.length,
       severe:subset.filter(x=>x.drop>=threshold).length,
       mean_change:subset.reduce((s,x)=>s+x.drop,0)/subset.length};
   }
   out.by_method[method]={
     task_scenario_count:details.length,
     severe_forgetting_count:details.filter(x=>x.drop>=threshold).length,
     max_accuracy_drop:sort[0].drop,
     largest_losses:sort.slice(0,5),
     by_family:fam,
     mean_accuracy_drop:details.reduce((s,x)=>s+x.drop,0)/details.length
   };
   assert(Math.abs(out.by_method[method].mean_accuracy_drop-record.summary[method].old_accuracy_drop)<1e-12,
     "summary mismatch "+method);
 }
 out.comparison={
   candidate_severe:out.by_method.merge_closest.severe_forgetting_count,
   eviction_severe:out.by_method.evict_first.severe_forgetting_count,
   expanded_capacity_severe:out.by_method.expand5.severe_forgetting_count,
   candidate_worst_drop:out.by_method.merge_closest.max_accuracy_drop
 };
 out.caveats=[
  "Severe threshold 20 percentage points is a POST-HOC failure diagnostic, not one of the prescore acceptance gates.",
  "80 old-task measurements per method represent 20 paired scenarios times four tasks, not independent samples.",
  "This audit uses recorded accuracy and cannot independently rerun the learner or test every possible task boundary.",
  "If max/mean forgetting diverge, safety assessment should not rely on mean-only acceptance."
 ];
 return out;
}
module.exports={skillLossV6};
if(require.main===module){const fs=require("node:fs"),r=JSON.parse(fs.readFileSync(process.argv[2]||"R2_V6_RESULTS.json","utf8"));const audit=skillLossV6(r);console.log(JSON.stringify(audit,null,2));if(audit.status!=="PASS")process.exitCode=1;}
