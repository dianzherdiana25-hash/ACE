"use strict";
/** ACE R2v6 output-only independent numerical auditor. No training or teacher generation invoked. */
function auditV6(x) {
 "use strict";
 const p=x.protocol,errors=[];
 const check=(ok,msg)=>{if(!ok)errors.push(msg);};
 const mean=a=>a.reduce((s,y)=>s+y,0)/a.length;
 const key=r=>[r.seed,r.family,r.novelty,r.method].join("/");
 const ids=new Set();const scenarioMap=new Map();
 let labelsSeen=0,calibrationLabels=0,updateCalls=0,supportLabels=0,queryScores=0,probes=0;
 check(p.id==="ACE_R2_V6_FIFTH_SKILL_CAPACITY","protocol mismatch");
 check(x.runs.length===5*2*2*8,"run count");
 const expertMethods=["frozen4","evict_first","merge_random","merge_closest","expand5","oracle_merge"];
 for(const r of x.runs){
   const id=key(r);
   check(!ids.has(id),"duplicate "+id);ids.add(id);
   check(p.seeds.includes(r.seed)&&p.families.includes(r.family)&&p.novelties.includes(r.novelty)&&p.methods.includes(r.method),"unexpected identity "+id);
   const scenario=[r.seed,r.family,r.novelty].join("/");
   if(!scenarioMap.has(scenario))scenarioMap.set(scenario,[]);
   scenarioMap.get(scenario).push(r);
   check(r.initial_old.length===4&&r.after_old.length===4,"4-old shape "+id);
   check(r.initial_old.concat(r.after_old,[r.after_new]).every(v=>v>=0&&v<=1),"scores bounded "+id);
   const init=mean(r.initial_old),finalOld=mean(r.after_old),finalAll=(4*finalOld+r.after_new)/5;
   check(Math.abs(init-r.initial_old_mean)<1e-12,"initial old mean "+id);
   check(Math.abs(finalOld-r.terminal_old_mean)<1e-12,"final old mean "+id);
   check(Math.abs(finalAll-r.final_joint)<1e-12,"joint mean "+id);
   check(Math.abs(r.old_accuracy_drop-(init-finalOld))<1e-12,"old drop "+id);
   check(r.cost.initial_supervised_labels===1024,"known label budget "+id);
   check(r.cost.calibration_label_accesses===128,"calibration label budget "+id);
   check(r.cost.novel_observed_labels===192,"novel label budget "+id);
   check(r.cost.novel_train_labels===(r.method==="frozen4"?0:192),"novel training label consumption "+id);
   check(r.cost.evaluation_support_label_accesses===144,"evaluation support accesses "+id);
   check(r.cost.evaluation_query_label_scores===1152,"evaluation query scores "+id);
   const isExpert=expertMethods.includes(r.method);
   check(r.cost.train_updates===(r.method==="frozen4"?1024:r.method==="shared_replay"?2431:1216),"grad update count "+id);
   check(r.cost.novel_train_gradient_updates===(r.method==="frozen4"?0:r.method==="shared_replay"?384:192),"novel gradient count "+id);
   check(r.cost.weight_scalars===(isExpert?(r.method==="expand5"&&r.admitted?60:48):12),"weight scalars "+id);
   check(r.cost.replay_examples===(r.method==="shared_replay"?48:0),"replay buffer "+id);
   check(r.provenance.known_teacher_signatures.length===4,"teacher provenance "+id);
   check(r.provenance.new_teacher_signature!==r.provenance.known_teacher_signatures[3],"novel teacher must differ "+id);
   check(r.provenance.initial_archive_signature.length===8,"initial archive signature "+id);
   const streams=r.provenance.known_data_streams.concat(r.provenance.calibration_streams,r.provenance.eval_support_streams,r.provenance.eval_query_streams,[r.provenance.novel_train_stream]);
   check(streams.length===23&&new Set(streams).size===23,"data stream isolation "+id);
   if(isExpert){
     check(r.calibration_scores.length===8&&Number.isFinite(r.calibration_q90),"calibration score presence "+id);
     const sorted=r.calibration_scores.slice().sort((a,b)=>a-b);
     const quant=sorted[Math.ceil(.90*sorted.length)-1];
     check(Math.abs(quant-r.calibration_q90)<1e-12,"frozen threshold q90 "+id);
     check(r.method==="oracle_merge"||r.method==="frozen4"||
       r.admitted===(r.novelty_score>quant),"no task-ID detection "+id);
     check(r.cost.max_head_count<=(r.method==="expand5"?5:4),"expert cap "+id);
     if(r.merged_pair!==null)
       check(r.merged_pair.length===2&&r.merged_pair[0]>=0&&r.merged_pair[1]<=3&&r.merged_pair[0]<r.merged_pair[1],"merge provenance "+id);
   }else{
     check(r.calibration_scores.length===0&&r.novelty_score===null,"shared not novelty detector "+id);
     check(r.cost.max_head_count===0,"shared no experts "+id);
   }
   labelsSeen+=r.cost.initial_supervised_labels+r.cost.novel_observed_labels;
   calibrationLabels+=r.cost.calibration_label_accesses;
   supportLabels+=r.cost.evaluation_support_label_accesses;
   queryScores+=r.cost.evaluation_query_label_scores;
   updateCalls+=r.cost.train_updates;
   probes+=r.cost.score_probe_predictions;
 }
 const pairing=[];
 for(const [sc,rows] of scenarioMap){
   check(rows.length===8,"paired method count "+sc);
   const m=Object.fromEntries(rows.map(r=>[r.method,r]));
   check(Object.keys(m).length===8,"missing comparator "+sc);
   const e=expertMethods.map(n=>m[n]);
   const s0=e[0];
   for(const r of e){
     check(r.provenance.initial_archive_signature===s0.provenance.initial_archive_signature,"initial weights across methods "+sc);
     check(Math.abs(r.initial_old_mean-s0.initial_old_mean)<1e-12,"initial old skill mismatch "+sc);
     check(r.calibration_q90===s0.calibration_q90,"calibration threshold mismatch "+sc);
     check(r.novelty_score===s0.novelty_score,"novelty score mismatch "+sc);
     check(r.provenance.known_teacher_signatures.join("/")===s0.provenance.known_teacher_signatures.join("/"),"teacher mismatch across arms "+sc);
     check(r.provenance.eval_query_streams.join("/")===s0.provenance.eval_query_streams.join("/"),"test stream mismatch across arms "+sc);
   }
   check(m.oracle_merge.admitted,"oracle forced admission "+sc);
   check(Math.abs(m.merge_closest.after_new-m.oracle_merge.after_new)<1e-12 || !m.merge_closest.admitted,"oracle/candidate difference when admitted "+sc);
   pairing.push({scenario:sc,seed:m.merge_closest.seed,family:m.merge_closest.family,novelty:m.merge_closest.novelty,
     candidate_minus_evict:m.merge_closest.final_joint-m.evict_first.final_joint,
     candidate_minus_random:m.merge_closest.final_joint-m.merge_random.final_joint,
     candidate_minus_expand:m.merge_closest.final_joint-m.expand5.final_joint,
     merge_pair:m.merge_closest.merged_pair,
     candidate_old_drop:m.merge_closest.old_accuracy_drop,
     candidate_new_accuracy:m.merge_closest.after_new,
     admitted:m.merge_closest.admitted});
 }
 function summary(method){
   const rows=x.runs.filter(r=>r.method===method);
   check(rows.length===20,"method count "+method);
   const keys=["initial_old_mean","terminal_old_mean","old_accuracy_drop","after_new","final_joint"];
   const v=Object.fromEntries(keys.map(k=>[k,mean(rows.map(r=>r[k]))]));
   v.admit_rate=mean(rows.map(r=>Number(r.admitted)));
   v.new_train_updates=mean(rows.map(r=>r.cost.novel_train_gradient_updates));
   for(const k of Object.keys(v))check(Math.abs(v[k]-x.summary[method][k])<1e-12,"summary "+method+"/"+k);
   return v;
 }
 const recalculated={};for(const m of p.methods)recalculated[m]=summary(m);
 for(const family of p.families)for(const novelty of p.novelties){
   const sc=x.comparisons[family+"/"+novelty];
   for(const m of p.methods){
     const rows=x.runs.filter(r=>r.family===family&&r.novelty===novelty&&r.method===m);
     for(const [k,rawKey] of [["joint","final_joint"],["old","terminal_old_mean"],["new","after_new"]]){
       check(Math.abs(mean(rows.map(r=>r[rawKey]))-sc[m][k])<1e-12,"scenario summary "+family+"/"+novelty+"/"+m+"/"+k);
     }
     check(Math.abs(mean(rows.map(r=>Number(r.admitted)))-sc[m].admitted)<1e-12,"scenario admission "+family+"/"+novelty+"/"+m);
   }
 }
 const candidate=recalculated.merge_closest;
 const advantages={
   against_evict:candidate.final_joint-recalculated.evict_first.final_joint,
   against_random:candidate.final_joint-recalculated.merge_random.final_joint
 };
 for(const k of Object.keys(advantages))check(Math.abs(advantages[k]-x.pair_advantages[k])<1e-12,"advantage "+k);
 const familyJoint=Object.fromEntries(p.families.map(f=>[f,mean(x.runs.filter(r=>r.family===f&&r.method==="merge_closest").map(r=>r.final_joint))]));
 const admissions=Object.fromEntries(p.novelties.map(n=>[n,mean(x.runs.filter(r=>r.novelty===n&&r.method==="merge_closest").map(r=>Number(r.admitted)))]));
 const g={
   matched_capacity_advantage:advantages.against_evict>=p.gating.candidate_vs_evict&&advantages.against_random>=p.gating.candidate_vs_random,
   old_retention:candidate.terminal_old_mean>=p.gating.min_old_accuracy&&candidate.old_accuracy_drop<=p.gating.max_old_drop,
   new_skill:candidate.after_new>=p.gating.min_new_accuracy,
   novel_admission:admissions.unrelated>=p.gating.min_admit_rate_per_novelty&&admissions.near>=p.gating.min_admit_rate_per_novelty,
   cross_family_robustness:Math.abs(familyJoint.orthogonal-familyJoint.related_pair)<=p.gating.max_cross_family_gap
 };
 check(JSON.stringify(g)===JSON.stringify(x.gates),"prescore gate mismatch");
 const seedContrasts=[];
 for(const seed of p.seeds){
   const rows=pairing.filter(r=>r.seed===seed);
   check(rows.length===4,"seed paired count "+seed);
   seedContrasts.push({seed,delta_evict:mean(rows.map(r=>r.candidate_minus_evict)),
     delta_random:mean(rows.map(r=>r.candidate_minus_random)),
     delta_expand:mean(rows.map(r=>r.candidate_minus_expand))});
 }
 const descriptive={};
 for(const metric of ["delta_evict","delta_random","delta_expand"]){
   const vals=seedContrasts.map(s=>s[metric]),boot=[];
   for(let a=0;a<5;a++)for(let b=0;b<5;b++)for(let c=0;c<5;c++)for(let d=0;d<5;d++)for(let e=0;e<5;e++){
     boot.push(mean([vals[a],vals[b],vals[c],vals[d],vals[e]]));
   }
   boot.sort((a,b)=>a-b);
   descriptive[metric]={
     seed_mean:mean(vals),seed_bootstrap_low:boot[Math.floor(boot.length*.025)],
     seed_bootstrap_high:boot[Math.floor(boot.length*.975)],
     note:"5-seed exact-resample descriptive range only, not independent scientific CI"
   };
 }
 const pairCounts={};
 for(const row of pairing){const k=(row.merge_pair||["no","pair"]).join("-");pairCounts[k]=(pairCounts[k]||0)+1;}
 return {status:errors.length?"FAIL":"PASS",errors,raw_trials:x.runs.length,paired_scenarios:scenarioMap.size,
   logical_training_examples_shown:labelsSeen,calibration_label_accesses:calibrationLabels,
   evaluation_support_label_accesses:supportLabels,evaluation_query_label_scores:queryScores,
   gradient_updates:updateCalls,expert_support_score_calls:probes,
   recomputed_gates:g,pair_advantages:advantages,
   family_joint:familyJoint,admission_rates:admissions,seedContrasts,descriptive,
   selected_pair_counts:pairCounts,
   caveats:[
    "Output-only auditor cannot independently reproduce source-level head-weight geometry or prove closest-pair selection beyond recorded metadata.",
    "Initial archive is trained with supervised old task boundaries; novel admission and test retrieval use labeled support without task ID.",
    "Novel task detection passed 100% in this particular public synthetic test and is not a valid general novelty-detection guarantee.",
    "Old/new support and query evaluation is repeated across candidate and controls, producing correlated arms; 160 method runs are only 20 distinct task scenarios.",
    "Expanded five-head archive is a capacity upper bound, not a matched-memory comparator.",
    "Archive merging has no learned compression objective: weight averaging may destroy skills in orthogonal regimes.",
    "5 seeds and synthetic teachers are not independent externally held out confirmation; Node exact-head CI not run."
   ]};
}
module.exports={auditV6};
if(require.main===module){const fs=require("node:fs"),x=JSON.parse(fs.readFileSync(process.argv[2]||"R2_V6_RESULTS.json","utf8"));const out=auditV6(x);console.log(JSON.stringify(out,null,2));if(out.status!=="PASS")process.exitCode=1;}
