"use strict";
/** R2 v4 source; fixed prescore protocol, no eval()/exec(), external calls or secret bank. */
function runV4() {
 "use strict";
 const P={
  id:"R2_V4_PRESCORE_SUPPORT_RETRIEVAL",
  seeds:[5,17,31,53,79],
  regimes:["distinct","aliased","shifted"],
  methods:["frozen","sgd","ewc","replay","context","evidence","evidence_zero","fast_adapt","oracle"],
  schedule:[0,1,2,0,3,1,2,0],
  feature_dim:12,train_per_episode:64,train_support:12,
  eval_support:12,eval_query:96,novelty_support:12,
  max_experts:4,replay_max:48,
  rate:.16,ewc_strength:2.5,init_transfer:.20,
  novelty_distance:.22,evidence_loss_threshold:.61,
  noise:0.02,
  gates:{aliased_minus_context:.15,transfer_minus_zero:.025,
   unknown_reject_min:.65,known_reject_max:.20,
   aliased_minus_fast_adapt:.03,aliased_min:.75},
  interpretation:"Public exploratory, repeated eval-support labels; no sealed confirmatory holdout"
 };
 const mean=a=>a.reduce((s,x)=>s+x,0)/a.length;
 const rand=seed=>{let z=(seed>>>0)||1;return()=>{z^=z<<13;z^=z>>>17;z^=z<<5;return (z>>>0)/4294967296;};};
 function makeTeacher(seed,task){
  const r=rand(((seed+3)*104729+(task+11)*40009)>>>0);
  const order=Array.from({length:P.feature_dim},(_,i)=>i);
  for(let k=order.length-1;k>0;k--){const i=Math.floor(r()*(k+1));[order[k],order[i]]=[order[i],order[k]];}
  const w=Array(P.feature_dim).fill(0);
  for(const j of order.slice(0,4))w[j]=(r()<.5?-1:1)*(.7+.9*r());
  return w;
 }
 function signature(w){
  let h=2166136261>>>0;
  for(const ch of w.map(v=>v.toFixed(8)).join("|")){h^=ch.charCodeAt(0);h=Math.imul(h,16777619)>>>0;}
  return h.toString(16).padStart(8,"0");
 }
 function bank(seed,task,regime,episode,split,count){
  const w=makeTeacher(seed,task);
  const sid={train:1,support:2,query:3,novel:4}[split];
  if(!sid)throw Error("unknown split");
  const seed0=(((seed+1)*433494437+(task+1)*131071+sid*9929+
     (split==="train"?(episode+1)*65537:0))>>>0);
  const r=rand(seed0);
  const centers=[-.9,-.3,.3,.9,0];
  const base=regime==="aliased"?0:centers[task];
  const flipContext=regime==="shifted"&&episode>=3&&task<4;
  const center=flipContext?-base:base;
  const rows=[];
  for(let i=0;i<count;i++){
    const x=Array.from({length:P.feature_dim},()=>r()*2-1);
    const score=x.reduce((s,v,k)=>s+v*w[k],0);
    const raw=score>=0?1:0;
    const y=r()<P.noise?1-raw:raw;
    const c=center+(r()-.5)*.04;
    rows.push({x,y,c,task,uid:`${seed}|${task}|${split}|${split==="train"?episode:0}|${i}`});
  }
  return {rows,signature:signature(w),stream_id:`${seed}|${task}|${split}|${split==="train"?episode:0}`};
 }
 const sigmoid=z=>z>=20?1:z<=-20?0:1/(1+Math.exp(-z));
 function newModel(method){
  const expert=()=>({w:Array(P.feature_dim).fill(0),centroid:0,seen:0});
  return {method,w:Array(P.feature_dim).fill(0),fisher:Array(P.feature_dim).fill(0),
   anchor:Array(P.feature_dim).fill(0),
   experts:method==="oracle"?Array.from({length:4},expert):[],
   replay:[],seen:0,
   train_updates:0,eval_updates:0,weight_ops:0,penalty_ops:0,
   fisher_ops:0,router_predictions:0,heads_created:0,
   forced_reuse:0};
 }
 const dot=(a,b)=>a.reduce((s,x,i)=>s+x*b[i],0);
 function ce(p,y){
  const x=Math.min(1-1e-12,Math.max(1e-12,p));
  return -(y*Math.log(x)+(1-y)*Math.log(1-x));
 }
 function avgLoss(m,head,rows){
  let s=0;
  for(const p of rows){s+=ce(sigmoid(dot(head.w,p.x)),p.y);m.router_predictions++;}
  return s/rows.length;
 }
 function candidateHead(m,rows,allowNovel){
  if(m.experts.length===0){
   if(allowNovel){m.experts.push({w:Array(P.feature_dim).fill(0),centroid:0,seen:0});m.heads_created++;return {k:0,novel:true,loss:Math.log(2)};}
   return {k:-1,novel:true,loss:Infinity};
  }
  const losses=m.experts.map(e=>avgLoss(m,e,rows));
  let j=0;
  for(let k=1;k<losses.length;k++)if(losses[k]<losses[j])j=k;
  const novel=losses[j]>P.evidence_loss_threshold;
  if(novel&&allowNovel&&m.experts.length<P.max_experts){
   const w=Array(P.feature_dim).fill(0);
   if(m.method==="evidence")
    for(let k=0;k<P.feature_dim;k++)w[k]=P.init_transfer*m.experts[j].w[k];
   m.experts.push({w,centroid:0,seen:0});m.heads_created++;
   return {k:m.experts.length-1,novel:true,loss:losses[j]};
  }
  if(novel&&allowNovel&&m.experts.length>=P.max_experts)m.forced_reuse++;
  return {k:j,novel,loss:losses[j]};
 }
 function contextHead(m,rows,allowNovel){
  const c=mean(rows.map(p=>p.c));
  if(!m.experts.length){
   if(!allowNovel)return {k:-1,novel:true};
   m.experts.push({w:Array(P.feature_dim).fill(0),centroid:c,seen:0});m.heads_created++;
   return {k:0,novel:true};
  }
  let k=0;
  for(let j=1;j<m.experts.length;j++)
   if(Math.abs(m.experts[j].centroid-c)<Math.abs(m.experts[k].centroid-c))k=j;
  if(Math.abs(m.experts[k].centroid-c)>P.novelty_distance&&allowNovel&&m.experts.length<P.max_experts){
   m.experts.push({w:Array(P.feature_dim).fill(0),centroid:c,seen:0});m.heads_created++;
   return {k:m.experts.length-1,novel:true};
  }
  return {k,novel:false};
 }
 function gradient(w,p,scale){
  const delta=(p.y-sigmoid(dot(w,p.x)))*P.rate;
  for(let i=0;i<P.feature_dim;i++)w[i]+=scale*delta*p.x[i];
 }
 function trainUpdate(m,p,headIndex){
  if(["context","evidence","evidence_zero","oracle"].includes(m.method)){
   if(headIndex<0||headIndex>=m.experts.length)throw Error("undefined expert");
   const e=m.experts[headIndex];
   gradient(e.w,p,1);
   if(m.method==="context"){e.centroid=(e.centroid*e.seen+p.c)/(e.seen+1);e.seen++;}
  }else{
   const pr=sigmoid(dot(m.w,p.x));
   for(let j=0;j<P.feature_dim;j++){
    const pen=m.method==="ewc"?P.ewc_strength*m.fisher[j]*(m.w[j]-m.anchor[j]):0;
    m.w[j]+=P.rate*((p.y-pr)*p.x[j]-pen);
    if(m.method==="ewc")m.penalty_ops++;
   }
  }
  m.train_updates++;
  m.weight_ops+=P.feature_dim;
 }
 function consolidate(m,rows){
  for(let k=0;k<P.feature_dim;k++){
   let s=0;
   for(const p of rows){
    const q=sigmoid(dot(m.w,p.x));
    s+=q*(1-q)*p.x[k]*p.x[k]/rows.length;
    m.fisher_ops++;
   }
   m.fisher[k]+=s;
   m.anchor[k]=m.w[k];
  }
 }
 function evaluate(m,support,query){
  let w,abstain=false;
  const method=m.method;
  if(method==="evidence"||method==="evidence_zero"){
   const r=candidateHead(m,support,false);
   abstain=r.novel;
   if(r.k>=0)w=m.experts[r.k].w;
  }else if(method==="context"){
   const r=contextHead(m,support,false);
   if(r.k>=0)w=m.experts[r.k].w;
  }else if(method==="oracle"){
   if(support[0].task>=0&&support[0].task<4)w=m.experts[support[0].task].w;
   else abstain=true;
  }else if(method==="fast_adapt"){
   w=m.w.slice();
   for(const p of support){gradient(w,p,1);m.eval_updates++;m.weight_ops+=P.feature_dim;}
  }else w=m.w;
  if(!w)abstain=true;
  let correct=0;
  for(const p of query)if(!abstain&&Number(sigmoid(dot(w,p.x))>=.5)===p.y)correct++;
  return {accuracy:correct/query.length,abstained:abstain};
 }
 function train(m,rows){
  const method=m.method;
  const sup=rows.slice(0,P.train_support);
  let k=-1;
  if(method==="evidence"||method==="evidence_zero")k=candidateHead(m,sup,true).k;
  else if(method==="context")k=contextHead(m,sup,true).k;
  else if(method==="oracle")k=rows[0].task;
  if(method==="frozen"&&m.train_updates>=P.train_per_episode)return;
  const r=rand(m.seen*131+17); // No task ID or task-derived UID in non-oracle sampling.
  for(const p of rows){
   trainUpdate(m,p,k);
   if(method==="replay"){
    if(m.replay.length){
     trainUpdate(m,m.replay[Math.floor(r()*m.replay.length)],-1);
    }
    m.seen++;
    if(m.replay.length<P.replay_max)m.replay.push(p);
    else {const z=Math.floor(r()*m.seen);if(z<P.replay_max)m.replay[z]=p;}
   }
  }
  if(method==="ewc")consolidate(m,rows);
 }
 function trial(seed,regime,method){
  const m=newModel(method),history=[],firstAfter=Array(4).fill(null),beforeFirst=Array(4).fill(null);
  const trainSigs=[],trainStreams=[];
  const testSigs=[],supportStreams=[],queryStreams=[];
  for(let t=0;t<4;t++){
   const sup=bank(seed,t,regime,7,"support",P.eval_support);
   const query=bank(seed,t,regime,7,"query",P.eval_query);
   testSigs.push([sup.signature,query.signature]);
   supportStreams.push(sup.stream_id);queryStreams.push(query.stream_id);
  }
  let prev=null;
  for(let ep=0;ep<P.schedule.length;ep++){
   const task=P.schedule[ep],tr=bank(seed,task,regime,ep,"train",P.train_per_episode);
   trainSigs.push(tr.signature);trainStreams.push(tr.stream_id);
   if(firstAfter[task]===null&&ep!==0)beforeFirst[task]=prev.per_task[task];
   train(m,tr.rows);
   const accuracy=[],rejected=[];
   for(let t=0;t<4;t++){
    const support=bank(seed,t,regime,ep,"support",P.eval_support);
    const query=bank(seed,t,regime,ep,"query",P.eval_query);
    const out=evaluate(m,support.rows,query.rows);
    accuracy.push(out.accuracy);rejected.push(out.abstained);
   }
   if(firstAfter[task]===null)firstAfter[task]=accuracy[task];
   const snap={episode:ep,task,per_task:accuracy,rejected,mean:mean(accuracy),
    mean_seen:mean(accuracy.filter((_,t)=>P.schedule.slice(0,ep+1).includes(t)))};
   history.push(snap);prev=snap;
  }
  const final=history.at(-1).per_task;
  const novelSup=bank(seed,4,regime,7,"novel",P.novelty_support);
  let novelRejected=false;
  if(method==="evidence"||method==="evidence_zero")novelRejected=candidateHead(m,novelSup.rows,false).novel;
  const unknownSupportLabels=P.novelty_support;
  const firstExposure=P.schedule.map((t,i)=>P.schedule.indexOf(t)===i?{episode:i,task:t}:null).filter(Boolean);
  let forgetting=0;
  for(let t=0;t<4;t++){
   const firstEp=P.schedule.indexOf(t);
   let best=0;
   for(let ep=firstEp;ep<history.length;ep++)best=Math.max(best,history[ep].per_task[t]);
   forgetting+=Math.max(0,best-final[t]);
  }
  const knownReject=history.at(-1).rejected.filter(Boolean).length/4;
  const cost={
   train_label_accesses:P.schedule.length*P.train_per_episode,
   evaluation_support_label_accesses:P.schedule.length*4*P.eval_support+unknownSupportLabels,
   evaluation_query_scores:P.schedule.length*4*P.eval_query,
   train_updates:m.train_updates,eval_adaptation_updates:m.eval_updates,
   weight_coordinate_ops:m.weight_ops,penalty_ops:m.penalty_ops,fisher_ops:m.fisher_ops,
   router_predictions:m.router_predictions,
   stored_replay_examples:m.replay.length,
   experts:m.experts.length,
   persistent_numeric_scalars:["context","evidence","evidence_zero","oracle"].includes(method)?
    m.experts.length*(P.feature_dim+2):method==="ewc"?P.feature_dim*3:P.feature_dim,
   created_experts:m.heads_created,forced_reuse:m.forced_reuse
  };
  const fwt=mean(beforeFirst.slice(1).map(x=>x-.5));
  return {seed,regime,method,
   final_accuracy:mean(final),final_by_task:final,final_known_rejection:knownReject,
   novel_rejected:novelRejected?1:0,forgetting:forgetting/4,
   backward_transfer:mean(final.map((v,t)=>v-firstAfter[t])),
   support_conditioned_forward_transfer:fwt,
   first_after:firstAfter,first_before:beforeFirst,history,cost,
   provenance:{teacher_signatures_test:testSigs,train_teacher_signatures:trainSigs,
     train_streams:trainStreams,support_streams:supportStreams,query_streams:queryStreams,
     novel_teacher_signature:novelSup.signature,
     novelty_stream:novelSup.stream_id},
   first_exposure:firstExposure
  };
 }
 const raw=[];
 for(const regime of P.regimes)for(const seed of P.seeds)for(const method of P.methods)
  raw.push(trial(seed,regime,method));
 const summary={};
 const stat=["final_accuracy","final_known_rejection","novel_rejected","forgetting",
  "backward_transfer","support_conditioned_forward_transfer"];
 const costFields=["train_updates","eval_adaptation_updates","weight_coordinate_ops",
  "penalty_ops","fisher_ops","router_predictions","stored_replay_examples",
  "experts","persistent_numeric_scalars","forced_reuse"];
 for(const regime of P.regimes){
  summary[regime]={};
  for(const method of P.methods){
   const rows=raw.filter(r=>r.regime===regime&&r.method===method);
   const s={};
   for(const k of stat)s[k]=mean(rows.map(x=>x[k]));
   for(const k of costFields)s[k]=mean(rows.map(x=>x.cost[k]));
   summary[regime][method]=s;
  }
 }
 const a=summary.aliased;
 const gates={
  evidence_beats_context:a.evidence.final_accuracy-a.context.final_accuracy>=P.gates.aliased_minus_context,
  transfer_beats_no_transfer:a.evidence.final_accuracy-a.evidence_zero.final_accuracy>=P.gates.transfer_minus_zero,
  novel_rejection:a.evidence.novel_rejected>=P.gates.unknown_reject_min,
  known_false_rejection:a.evidence.final_known_rejection<=P.gates.known_reject_max,
  evidence_beats_fast_adapt:a.evidence.final_accuracy-a.fast_adapt.final_accuracy>=P.gates.aliased_minus_fast_adapt,
  absolute_accuracy:a.evidence.final_accuracy>=P.gates.aliased_min
 };
 return {protocol:P,summary,gates,decision:Object.values(gates).every(Boolean)?
  "PUBLIC_DEVELOPMENT_GATES_PASS_NEEDS_INDEPENDENT_CONFIRMATION":"HOLD_NO_VALIDATED_LIFELONG_GAIN",raw};
}
function testV4(fn){
 const a=fn(),b=fn(),p=a.protocol;function check(x,m){if(!x)throw Error("R2V4:"+m);}
 check(JSON.stringify(a)===JSON.stringify(b),"replay");
 check(a.raw.length===p.seeds.length*p.regimes.length*p.methods.length,"count");
 const ids=new Set(),stat=["final_accuracy","final_known_rejection","novel_rejected","forgetting","backward_transfer","support_conditioned_forward_transfer"];
 for(const r of a.raw){
  const id=[r.seed,r.regime,r.method].join(":");
  check(!ids.has(id),"identity duplicate "+id);ids.add(id);
  check(r.history.length===8,"trajectory "+id);
  check(r.history.every((h,i)=>h.task===p.schedule[i]&&h.episode===i),"sequence "+id);
  check(r.history.every(h=>h.per_task.length===4&&h.per_task.every(v=>v>=0&&v<=1)),"scores "+id);
  check(r.first_exposure.map(x=>x.task).join(",")==="0,1,2,3","first exposure "+id);
  check(r.provenance.train_teacher_signatures.length===8,"train signatures "+id);
  check(r.provenance.teacher_signatures_test.length===4,"test signatures "+id);
  for(let task=0;task<4;task++){
   const sig=r.provenance.teacher_signatures_test[task][0];
   check(sig===r.provenance.teacher_signatures_test[task][1],"support/query teacher "+id);
   for(let ep=0;ep<8;ep++)if(p.schedule[ep]===task)
    check(sig===r.provenance.train_teacher_signatures[ep],"train/test teacher "+id);
  }
  check(r.provenance.novel_teacher_signature!==r.provenance.teacher_signatures_test[0][0],
   "novelty teacher collision "+id);
  check(new Set(r.provenance.train_streams).size===8,"training stream IDs "+id);
  check(new Set(r.provenance.support_streams).size===4&&new Set(r.provenance.query_streams).size===4,"eval streams "+id);
  check(r.cost.train_label_accesses===512&&r.cost.evaluation_support_label_accesses===396,"label accounting "+id);
  check(r.cost.evaluation_query_scores===3072,"query accounting "+id);
  const expected=r.method==="frozen"?64:r.method==="replay"?1023:512;
  check(r.cost.train_updates===expected,"training update budget "+id);
  check(r.cost.stored_replay_examples===(r.method==="replay"?48:0),"replay cap "+id);
  check(r.cost.experts<=4&&r.cost.experts>=0,"expert cap "+id);
  check(r.cost.penalty_ops===(r.method==="ewc"?6144:0),"ewc penalty "+id);
  check(r.cost.fisher_ops===(r.method==="ewc"?6144:0),"ewc fisher "+id);
  check(r.cost.eval_adaptation_updates===(r.method==="fast_adapt"?384:0),"fast adapt cost "+id);
  check(r.cost.persistent_numeric_scalars<=56,"scalar cap "+id);
  check(stat.every(k=>Number.isFinite(r[k])),"finite results "+id);
  check(r.final_accuracy>=0&&r.final_accuracy<=1&&r.forgetting>=0&&r.forgetting<=1,"metric range "+id);
 }
 for(const regime of p.regimes)for(const method of p.methods){
  const group=a.raw.filter(r=>r.regime===regime&&r.method===method);
  check(group.length===p.seeds.length,"group length");
  for(const k of stat){
   const v=group.reduce((s,r)=>s+r[k],0)/group.length;
   check(Math.abs(v-a.summary[regime][method][k])<1e-11,"group aggregate "+regime+"/"+method+"/"+k);
  }
 }
 return {result:"PASS",categories:20,runs:a.raw.length,
  level:"exact source executable V8 when read back; not independent scientific custody"};
}
module.exports={runV4,testV4};
if(require.main===module){console.error(JSON.stringify(testV4(runV4)));process.stdout.write(JSON.stringify(runV4(),null,2)+"\n");}
