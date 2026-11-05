"use strict";
/** R2 v6: prescored finite-memory fifth-task acquisition benchmark. No external code or live ACE changes. */
function runV6() {
 "use strict";
 const C={
   id:"ACE_R2_V6_FIFTH_SKILL_CAPACITY",
   seeds:[11,23,47,89,131],
   families:["related_pair","orthogonal"],
   novelties:["unrelated","near"],
   methods:["frozen4","evict_first","merge_random","merge_closest","expand5","oracle_merge","shared_sgd","shared_replay"],
   feature_dim:12,old_task_count:4,old_train_per_task:256,
   new_train:192,admission_support:16,
   calibration_per_task:32,calibration_block_size:16,
   eval_support:16,eval_query:128,
   noise:0.02,learning_rate:.16,archive_capacity:4,
   replay_capacity:48,calibration_quantile:.90,
   gating:{
    candidate_vs_evict:.025,candidate_vs_random:.015,
    min_old_accuracy:.72,max_old_drop:.10,
    min_new_accuracy:.78,min_admit_rate_per_novelty:.65,
    max_cross_family_gap:.05
   },
   level:"Public author-visible development; initial archive supervised with known task boundaries"
 };
 function rand(s) {let z=(s>>>0)||1;return()=>{z^=z<<13;z^=z>>>17;z^=z<<5;return(z>>>0)/4294967296;};}
 const mean=a=>a.reduce((s,x)=>s+x,0)/a.length;
 function signature(x){let h=2166136261>>>0;for(const ch of JSON.stringify(x)){h^=ch.charCodeAt(0);h=Math.imul(h,16777619)>>>0;}return h.toString(16).padStart(8,"0");}
 function sparse(seed,salt,k){
   const r=rand((seed*109681 +salt*23917+5381)>>>0);
   const ids=Array.from({length:12},(_,i)=>i);
   for(let j=ids.length-1;j>0;j--){let t=Math.floor(r()*(j+1));[ids[j],ids[t]]=[ids[t],ids[j]];}
   const w=Array(12).fill(0);
   for(const j of ids.slice(0,k))w[j]=(r()<.5?-1:1)*(.8+.7*r());
   return w;
 }
 function teachers(seed,family,mode){
   let old=[];
   if(family==="related_pair"){
     const first=sparse(seed,1,4),noise=sparse(seed,8,4);
     old=[first,first.map((v,i)=>.92*v+.08*noise[i]),sparse(seed,3,4),sparse(seed,4,4)];
   }else{
     for(let t=0;t<4;t++){
       const r=rand(seed*3571+t*45017+170);
       const w=Array(12).fill(0);
       for(let j=3*t;j<3*t+3;j++)w[j]=(r()<.5?-1:1)*(.8+.7*r());
       old.push(w);
     }
   }
   const novel=mode==="near"?old[3].slice():sparse(seed,29,4);
   if(mode==="near"){
     let idx=0;for(let i=1;i<12;i++)if(Math.abs(novel[i])>Math.abs(novel[idx]))idx=i;
     novel[idx]=-novel[idx];
   }
   return old.concat([novel]);
 }
 const roleIndex={old_train:1,calibration:2,eval_support:3,eval_query:4,new_train:5};
 function bank(seed,family,novelty,task,role,block,count,teacherSet){
   const roleCode=roleIndex[role];
   if(!roleCode)throw Error("split invalid");
   const familyId=family==="related_pair"?11:19,noveltyId=novelty==="near"?29:7;
   const rngSeed=(seed*200003+familyId*17011+noveltyId*2311+task*4129+roleCode*70001+(block+1)*34721)>>>0;
   const r=rand(rngSeed),w=teacherSet[task],rows=[];
   for(let i=0;i<count;i++){
     const x=Array.from({length:12},()=>2*r()-1);
     const yraw=x.reduce((s,v,j)=>s+v*w[j],0)>=0?1:0;
     const y=r()<C.noise?1-yraw:yraw;
     rows.push({x,y});
   }
   return {rows,rule_signature:signature(w),stream:`${seed}/${family}/${novelty}/${task}/${role}/${block}`};
 }
 function sigmoid(z){return z>25?1:z< -25?0:1/(1+Math.exp(-z));}
 const dot=(a,b)=>a.reduce((s,v,i)=>s+v*b[i],0);
 function ce(w,p){
   let q=sigmoid(dot(w,p.x));
   q=Math.min(1-1e-12,Math.max(1e-12,q));
   return -p.y*Math.log(q)-(1-p.y)*Math.log(1-q);
 }
 function meanLoss(w,rows){return mean(rows.map(p=>ce(w,p)));}
 function best(model,rows){
   let k=-1,loss=Infinity;
   for(let j=0;j<model.heads.length;j++){
     const v=meanLoss(model.heads[j],rows);
     model.probe_ops+=rows.length;
     if(v<loss){loss=v;k=j;}
   }
   return {k,loss};
 }
 function sgdUpdate(w,p){
   const q=sigmoid(dot(w,p.x)),d=C.learning_rate*(p.y-q);
   for(let i=0;i<12;i++)w[i]+=d*p.x[i];
 }
 function prepare(seed,family,mode){
   const ws=teachers(seed,family,mode),oldTrain=[],cal=[],supports=[],queries=[];
   const signatureRows=ws.map(signature);
   for(let t=0;t<4;t++){
     oldTrain.push(bank(seed,family,mode,t,"old_train",0,C.old_train_per_task,ws));
     const groups=[];
     for(let k=0;k<2;k++)groups.push(bank(seed,family,mode,t,"calibration",k,16,ws));
     cal.push(groups);
   }
   for(let t=0;t<5;t++){
     supports.push(bank(seed,family,mode,t,"eval_support",0,16,ws));
     queries.push(bank(seed,family,mode,t,"eval_query",0,128,ws));
   }
   const novel=bank(seed,family,mode,4,"new_train",0,192,ws);
   const allStreams=[
     ...oldTrain.map(x=>x.stream),...cal.flat().map(x=>x.stream),
     ...supports.map(x=>x.stream),...queries.map(x=>x.stream),novel.stream];
   if(new Set(allStreams).size!==allStreams.length)throw Error("same stream twice");
   for(let t=0;t<5;t++){
     const actual=[...supports,...queries,novel].filter(x=>x.rule_signature===signatureRows[t]);
     if(!actual.length)throw Error("rule signature mismatch");
   }
   if(signatureRows[3]===signatureRows[4])throw Error("novel teacher identical to old");
   return {ws,oldTrain,cal,supports,queries,novel,signatures:signatureRows,streams:allStreams};
 }
 function trainArchive(pre){
   const heads=[];let updates=0;
   for(let task=0;task<4;task++){
     const w=Array(12).fill(0);
     for(const p of pre.oldTrain[task].rows){sgdUpdate(w,p);updates++;}
     heads.push(w);
   }
   return {heads,updates};
 }
 function trainShared(pre,replay,seed){
   let w=Array(12).fill(0),buffer=[],count=0,updates=0,coordinateOps=0;
   const r=rand(seed*8191+391);
   function step(p){sgdUpdate(w,p);updates++;coordinateOps+=12;}
   for(const pack of pre.oldTrain){
     for(const p of pack.rows){
       step(p);
       if(replay&&buffer.length)step(buffer[Math.floor(r()*buffer.length)]);
       if(replay){
         count++;
         if(buffer.length<C.replay_capacity)buffer.push(p);
         else{const j=Math.floor(r()*count);if(j<C.replay_capacity)buffer[j]=p;}
       }
     }
   }
   return {w,buffer,count,updates,coordinateOps,r};
 }
 function quantile(vals){
   const a=vals.slice().sort((a,b)=>a-b);
   return a[Math.ceil(C.calibration_quantile*a.length)-1];
 }
 function scoreQuery(w,query){
   let ok=0;for(const p of query)if(Number(sigmoid(dot(w,p.x))>=.5)===p.y)ok++;
   return ok/query.length;
 }
 function evalExperts(model,pre,tasks){
   const per=[],route=[];
   for(let t=0;t<tasks;t++){
     const found=best(model,pre.supports[t].rows);
     per.push(scoreQuery(model.heads[found.k],pre.queries[t].rows));
     route.push(found.k);
   }
   return {per,route};
 }
 function evaluateShared(w,pre,tasks){
   return {per:Array.from({length:tasks},(_,t)=>scoreQuery(w,pre.queries[t].rows)),
      route:Array(tasks).fill(-1)};
 }
 function mergePair(heads,method,seed,family,mode){
   if(heads.length!==4)throw Error("expected exactly four");
   let pair=[0,1],distance=Infinity;
   if(method==="merge_random"){
     const r=rand(seed*100003+(family==="related_pair"?7:19)+(mode==="near"?31:43));
     const choices=[];for(let a=0;a<4;a++)for(let b=a+1;b<4;b++)choices.push([a,b]);
     pair=choices[Math.floor(r()*choices.length)];
   }else{
     for(let a=0;a<4;a++)for(let b=a+1;b<4;b++){
       let d=0;for(let j=0;j<12;j++)d+=(heads[a][j]-heads[b][j])**2;
       if(d<distance){distance=d;pair=[a,b];}
     }
   }
   const merged=heads[pair[0]].map((v,j)=>(v+heads[pair[1]][j])/2);
   heads[pair[0]]=merged;
   heads.splice(pair[1],1);
   return {pair,distance,heads};
 }
 function trial(seed,family,mode,method){
   const pre=prepare(seed,family,mode),known=trainArchive(pre);
   const expMethods=["frozen4","evict_first","merge_random","merge_closest","expand5","oracle_merge"];
   const isExpert=expMethods.includes(method);
   const model=isExpert?{heads:known.heads.map(w=>w.slice()),probe_ops:0}:null;
   let sh=null;
   if(!isExpert)sh=trainShared(pre,method==="shared_replay",seed);
   const before=isExpert?evalExperts(model,pre,4):evaluateShared(sh.w,pre,4);
   const beforeMean=mean(before.per);
   // All experts share the exact same originally trained four heads; no training or
   // detector is given the novel teacher/task identifier.
   const calScores=[];
   let threshold=null,detectorScore=null,admitted=false,admissionHead=-1,mergedPair=null;
   let extraTrainUpdates=0,probePredictions=0,oldHeadSignature=signature(known.heads);
   if(isExpert){
     for(const groups of pre.cal)for(const group of groups){
       const q=best(model,group.rows);
       calScores.push(q.loss);
     }
     threshold=quantile(calScores);
     const support=pre.novel.rows.slice(0,C.admission_support);
     const novelBefore=best(model,support);
     detectorScore=novelBefore.loss;
     admitted=method==="oracle_merge"?true:novelBefore.loss>threshold;
     if(method==="frozen4")admitted=false;
     admissionHead=novelBefore.k;
     if(method!=="frozen4"){
       if(admitted){
         if(method==="evict_first"){
           model.heads.shift();model.heads.push(Array(12).fill(0));admissionHead=model.heads.length-1;
         }else if(method==="expand5"){
           model.heads.push(Array(12).fill(0));admissionHead=model.heads.length-1;
         }else{
           const merged=mergePair(model.heads,method,seed,family,mode);
           mergedPair=merged.pair;
           model.heads.push(Array(12).fill(0));admissionHead=model.heads.length-1;
         }
       }
       for(const p of pre.novel.rows){sgdUpdate(model.heads[admissionHead],p);extraTrainUpdates++;}
     }
     probePredictions=model.probe_ops;
   }else{
     for(const p of pre.novel.rows){
       sgdUpdate(sh.w,p);extraTrainUpdates++;sh.updates++;sh.coordinateOps+=12;
       if(method==="shared_replay"&&sh.buffer.length){
         const q=sh.buffer[Math.floor(sh.r()*sh.buffer.length)];
         sgdUpdate(sh.w,q);extraTrainUpdates++;sh.updates++;sh.coordinateOps+=12;
       }
       if(method==="shared_replay"){
         sh.count++;if(sh.buffer.length<48)sh.buffer.push(p);
         else{const k=Math.floor(sh.r()*sh.count);if(k<48)sh.buffer[k]=p;}
       }
     }
   }
   const after=isExpert?evalExperts(model,pre,5):evaluateShared(sh.w,pre,5);
   if(isExpert)probePredictions=model.probe_ops;
   const terminalOld=mean(after.per.slice(0,4)),terminalNew=after.per[4];
   const oldDrop=beforeMean-terminalOld;
   const cost={
     initial_supervised_labels:1024,calibration_label_accesses:128,
     novel_train_labels:method==="frozen4"?0:192,
     novel_observed_labels:192,
     evaluation_support_label_accesses:9*16,
     evaluation_query_label_scores:9*128,
     train_updates:(isExpert?known.updates:sh.updates-extraTrainUpdates)+extraTrainUpdates,
     novel_train_gradient_updates:extraTrainUpdates,
     score_probe_predictions:probePredictions,
     weight_scalars:isExpert?model.heads.length*12:12,
     replay_examples:sh?sh.buffer.length:0,
     max_head_count:isExpert?model.heads.length:0
   };
   const provenance={
     known_teacher_signatures:pre.signatures.slice(0,4),
     new_teacher_signature:pre.signatures[4],
     known_data_streams:pre.oldTrain.map(x=>x.stream),
     calibration_streams:pre.cal.flat().map(x=>x.stream),
     eval_support_streams:pre.supports.map(x=>x.stream),
     eval_query_streams:pre.queries.map(x=>x.stream),
     novel_train_stream:pre.novel.stream,
     initial_archive_signature:oldHeadSignature
   };
   return {seed,family,novelty:mode,method,
     initial_old:before.per,after_old:after.per.slice(0,4),after_new:terminalNew,
     initial_old_mean:beforeMean,terminal_old_mean:terminalOld,old_accuracy_drop:oldDrop,
     final_joint:mean(after.per),before_routes:before.route,after_routes:after.route,
     admitted,admission_head:admissionHead,novelty_score:detectorScore,
     calibration_q90:threshold,calibration_scores:calScores,
     merged_pair:mergedPair,provenance,cost};
 }
 const runs=[];
 for(const family of C.families)for(const novelty of C.novelties)for(const seed of C.seeds)for(const method of C.methods){
   runs.push(trial(seed,family,novelty,method));
 }
 const summary={};
 const fields=["initial_old_mean","terminal_old_mean","old_accuracy_drop","after_new","final_joint"];
 for(const method of C.methods){
   const rows=runs.filter(r=>r.method===method);
   summary[method]=Object.fromEntries(fields.map(k=>[k,mean(rows.map(r=>r[k]))]));
   summary[method].admit_rate=mean(rows.map(r=>Number(r.admitted)));
   summary[method].new_train_updates=mean(rows.map(r=>r.cost.novel_train_gradient_updates));
 }
 const comparisons={};
 for(const family of C.families)for(const novelty of C.novelties) {
   const key=family+"/"+novelty;
   comparisons[key]={};
   for(const method of C.methods) {
     const rows=runs.filter(r=>r.family===family&&r.novelty===novelty&&r.method===method);
     comparisons[key][method]={joint:mean(rows.map(r=>r.final_joint)),
        old:mean(rows.map(r=>r.terminal_old_mean)),new:mean(rows.map(r=>r.after_new)),
        admitted:mean(rows.map(r=>Number(r.admitted)))};
   }
 }
 const pairAdv={
   against_evict:summary.merge_closest.final_joint-summary.evict_first.final_joint,
   against_random:summary.merge_closest.final_joint-summary.merge_random.final_joint
 };
 const avgByFamily=Object.fromEntries(C.families.map(f=>[f,mean(runs.filter(r=>r.method==="merge_closest"&&r.family===f).map(r=>r.final_joint))]));
 const novelRates=Object.fromEntries(C.novelties.map(m=>[m,mean(runs.filter(r=>r.method==="merge_closest"&&r.novelty===m).map(r=>Number(r.admitted)))]));
 const gates={
   matched_capacity_advantage:pairAdv.against_evict>=C.gating.candidate_vs_evict&&pairAdv.against_random>=C.gating.candidate_vs_random,
   old_retention:summary.merge_closest.terminal_old_mean>=C.gating.min_old_accuracy&&summary.merge_closest.old_accuracy_drop<=C.gating.max_old_drop,
   new_skill:summary.merge_closest.after_new>=C.gating.min_new_accuracy,
   novel_admission:novelRates.unrelated>=C.gating.min_admit_rate_per_novelty&&novelRates.near>=C.gating.min_admit_rate_per_novelty,
   cross_family_robustness:Math.abs(avgByFamily.orthogonal-avgByFamily.related_pair)<=C.gating.max_cross_family_gap
 };
 return {protocol:C,summary,comparisons,pair_advantages:pairAdv,novel_admission_rates:novelRates,
   family_joint:avgByFamily,gates,decision:Object.values(gates).every(Boolean)?
    "EXPLORATORY_DEVELOPMENT_SUCCESS_NOT_CONFIRMED":"HOLD_NO_VALIDATED_LIFELONG_SKILL_ADMISSION",
   runs};
}
function testV6(fn){
 const a=fn(),b=fn(),C=a.protocol;
 function ok(cond,reason){if(!cond)throw Error("R2V6 "+reason);}
 ok(JSON.stringify(a)===JSON.stringify(b),"determinism");
 ok(a.runs.length===C.methods.length*C.seeds.length*C.families.length*C.novelties.length,"run count");
 const ids=new Set(),knownSignatures=new Map(),comparisons=["frozen4","evict_first","merge_random","merge_closest","expand5","oracle_merge"];
 for(const r of a.runs){
   const id=[r.seed,r.family,r.novelty,r.method].join("/");
   ok(!ids.has(id),"duplicate "+id);ids.add(id);
   ok(r.initial_old.length===4&&r.after_old.length===4,"skill shapes "+id);
   ok(r.initial_old.concat(r.after_old,[r.after_new]).every(x=>x>=0&&x<=1),"metric bounds "+id);
   ok(Math.abs(r.final_joint-(r.after_old.reduce((s,x)=>s+x,0)+r.after_new)/5)<1e-12,"joint metric "+id);
   ok(Math.abs(r.terminal_old_mean-r.after_old.reduce((s,x)=>s+x,0)/4)<1e-12,"old mean "+id);
   ok(Math.abs(r.old_accuracy_drop-(r.initial_old_mean-r.terminal_old_mean))<1e-12,"old drop "+id);
   ok(r.cost.initial_supervised_labels===1024&&r.cost.calibration_label_accesses===128,"initial data "+id);
   ok(r.cost.novel_observed_labels===192&&r.cost.evaluation_support_label_accesses===144,"new/support data "+id);
   ok(r.cost.evaluation_query_label_scores===1152,"evaluation work "+id);
   const ex=comparisons.includes(r.method);
   if(ex){
     ok(r.cost.weight_scalars===(r.method==="expand5"&&r.admitted?60:48),"expert capacity "+id);
     ok(r.provenance.initial_archive_signature.length===8,"source archive hash "+id);
     ok(r.calibration_scores.length===8&&Number.isFinite(r.calibration_q90),"calibration shape "+id);
     ok(r.cost.max_head_count<=(r.method==="expand5"?5:4),"head cap "+id);
     ok(r.cost.replay_examples===0,"no expert replay "+id);
     ok(r.cost.train_updates===(r.method==="frozen4"?1024:1216),"expert updates "+id);
     ok(r.cost.novel_train_gradient_updates===(r.method==="frozen4"?0:192),"novel updates "+id);
     ok(r.merged_pair===null||r.merged_pair.length===2,"merge provenance "+id);
     if(r.method==="oracle_merge")ok(r.admitted,"oracle must admit");
   }else{
     ok(r.cost.weight_scalars===12,"shared weights "+id);
     ok(r.cost.train_updates===(r.method==="shared_replay"?2431:1216),"shared updates "+id);
     ok(r.cost.replay_examples===(r.method==="shared_replay"?48:0),"shared replay buffer "+id);
   }
   ok(r.provenance.known_teacher_signatures.length===4&&r.provenance.new_teacher_signature.length===8,"rule fingerprints "+id);
   ok(r.provenance.new_teacher_signature!==r.provenance.known_teacher_signatures[3],"new teacher not equal old "+id);
   ok(new Set(r.provenance.known_data_streams.concat(r.provenance.calibration_streams,
        r.provenance.eval_support_streams,r.provenance.eval_query_streams,
        [r.provenance.novel_train_stream])).size===4+8+5+5+1,"split uniqueness "+id);
   const scen=[r.seed,r.family,r.novelty].join("/");
   if(ex){
     if(knownSignatures.has(scen))ok(knownSignatures.get(scen)===r.provenance.initial_archive_signature,"archive mismatch across expert methods "+id);
     knownSignatures.set(scen,r.provenance.initial_archive_signature);
   }
 }
 for(const method of C.methods){
   const rows=a.runs.filter(r=>r.method===method);
   ok(rows.length===20,"missing group "+method);
   for(const key of ["initial_old_mean","terminal_old_mean","old_accuracy_drop","after_new","final_joint"]){
     const avg=rows.reduce((s,r)=>s+r[key],0)/rows.length;
     ok(Math.abs(avg-a.summary[method][key])<1e-12,"aggregate "+method+"/"+key);
   }
 }
 return {status:"PASS",invariant_families:18,run_count:a.runs.length,scope:"V8 deterministic arithmetic; no Node CI"};
}
module.exports={runV6,testV6};
if(require.main===module){console.error(JSON.stringify(testV6(runV6)));process.stdout.write(JSON.stringify(runV6(),null,2)+"\n");}
