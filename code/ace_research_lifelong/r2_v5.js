"use strict";
/** ACE R2-v5: pre-score public lifelong memory novelty protection experiment. No external evaluators or arbitrary code. */
function runV5() {
  "use strict";
  const C = {
    id:"ACE_R2_V5_ARCHIVE_NOVELTY_PUBLIC",
    protocol_ref:"R2_V5_PRESCORE_PROTOCOL.md",
    seeds:[5,17,31,53,79],
    methods:["always_reuse","fixed61","global_q90","slot_q90","global_q90_margin"],
    schedule:[0,1,2,0,3,1,2,0],
    dim:12,train_per_episode:64,train_router_support:12,
    max_heads:4,rate:0.16,old_reuse_threshold:0.61,cal_q:0.90,
    per_block:16,blocks_per_condition_per_task:12,
    known_query_per_task:96,noise:0.02,
    margin_gate:0.02,
    gates:{
      global_vs_fixed_unrelated_gain:0.10,
      max_known_fpr:0.15,
      min_near_tpr:0.50,
      max_shift_fpr:0.15,
      min_known_accuracy:0.75,
      min_slot_gain:0.03
    },
    statement:"Public calibration/evaluation; no external oracle; no autonomous activation"
  };
  const avg = x => x.reduce((a,b)=>a+b,0)/x.length;
  function rng(seed) {
    let s=(seed>>>0)||1;
    return ()=>{s^=s<<13;s^=s>>>17;s^=s<<5;return (s>>>0)/4294967296;};
  }
  function teacher(seed,task) {
    if(task>=8 && task<=11){
      const w=teacher(seed,task-8).slice();
      let major=0;
      for(let i=1;i<w.length;i++)if(Math.abs(w[i])>Math.abs(w[major]))major=i;
      w[major]=-w[major];
      return w;
    }
    const r=rng(((seed+3)*104729+(task+11)*40009)>>>0);
    const order=Array.from({length:C.dim},(_,i)=>i);
    for(let i=order.length-1;i>0;i--){
      const j=Math.floor(r()*(i+1));[order[i],order[j]]=[order[j],order[i]];
    }
    const w=Array(C.dim).fill(0);
    for(const i of order.slice(0,4))w[i]=(r()<.5?-1:1)*(.7+.9*r());
    return w;
  }
  function hash(data) {
    let h=2166136261>>>0;
    for(const ch of JSON.stringify(data)){h^=ch.charCodeAt(0);h=Math.imul(h,16777619)>>>0;}
    return h.toString(16).padStart(8,"0");
  }
  function samples(seed,task,split,block,count) {
    const seedFlag={train:111,cal:223,known:331,unrelated:447,near:541,shift:631,query:739}[split];
    if(!seedFlag)throw Error("bad split");
    const r=rng((seed*92171+(task+1)*131071+seedFlag*10079+(block+1)*8093)>>>0);
    const w=teacher(seed,task);
    const rows=[];
    for(let n=0;n<count;n++){
      const x=Array.from({length:C.dim},()=>2*r()-1);
      const val=x.reduce((s,v,i)=>s+v*w[i],0);
      const truth=val>=0?1:0;
      const y=r()<C.noise?1-truth:truth;
      const c=split==="shift" ? 1.35+(r()-.5)*.02 : (r()-.5)*.02;
      rows.push({x,y,c});
    }
    return {rows,teacher_signature:hash(w),sample_stream:[seed,task,split,block].join(":")};
  }
  function sigmoid(z){return z>25?1:z< -25?0:1/(1+Math.exp(-z));}
  const dot=(a,b)=>a.reduce((s,x,i)=>s+x*b[i],0);
  function loss(w,rows) {
    let s=0;
    for(const p of rows){
      const q=Math.max(1e-10,Math.min(1-1e-10,sigmoid(dot(w,p.x))));
      s-=p.y*Math.log(q)+(1-p.y)*Math.log(1-q);
    }
    return s/rows.length;
  }
  function probe(archive,rows){
    const losses=archive.map(h=>loss(h.w,rows));
    const indexes=losses.map((_,i)=>i).sort((a,b)=>losses[a]-losses[b]||a-b);
    return {best:indexes[0]??-1,score:indexes.length?losses[indexes[0]]:Infinity,
      gap:indexes.length>1?losses[indexes[1]]-losses[indexes[0]]:Infinity,
      count:indexes.length};
  }
  function learn(seed){
    const experts=[];let updates=0,router_predictions=0,creations=0,forced=0;
    const train_signatures=[],train_streams=[];
    for(let episode=0;episode<C.schedule.length;episode++){
      const task=C.schedule[episode];
      const bank=samples(seed,task,"train",episode,C.train_per_episode);
      train_signatures.push(bank.teacher_signature);
      train_streams.push(bank.sample_stream);
      const support=bank.rows.slice(0,C.train_router_support);
      let route=probe(experts,support);
      router_predictions+=experts.length*support.length;
      let idx=route.best;
      if((idx<0||route.score>C.old_reuse_threshold)&&experts.length<C.max_heads){
        experts.push({w:Array(C.dim).fill(0)});
        idx=experts.length-1;creations++;
      }else if(route.score>C.old_reuse_threshold&&experts.length>=C.max_heads)forced++;
      for(const p of bank.rows){
        const head=experts[idx];
        const q=sigmoid(dot(head.w,p.x));
        for(let k=0;k<C.dim;k++)head.w[k]+=C.rate*(p.y-q)*p.x[k];
        updates++;
      }
    }
    return {experts,updates,router_predictions,creations,forced,train_signatures,train_streams};
  }
  function quantile(a,q){
    if(!a.length)throw Error("empty calibration group");
    const s=a.slice().sort((x,y)=>x-y);
    return s[Math.ceil(q*s.length)-1];
  }
  function analyzeSeed(seed) {
    const trained=learn(seed),archive=trained.experts;
    const archiveHash=hash(archive);
    const calibration=[];
    const probesByKind={cal:[],known:[],unrelated:[],near:[],shift:[]};
    const expectedSignatures={known:[],unknown:[],near:[]};
    const knownQuery=[];
    for(let t=0;t<4;t++){
      const query=samples(seed,t,"query",0,C.known_query_per_task);
      knownQuery.push(query);
      expectedSignatures.known.push(query.teacher_signature);
      expectedSignatures.unknown.push(teacher(seed,4+t));
      expectedSignatures.near.push(hash(teacher(seed,8+t)));
      for(let block=0;block<C.blocks_per_condition_per_task;block++){
        const cal=samples(seed,t,"cal",block,C.per_block);
        const r=probe(archive,cal.rows);
        calibration.push({task:t,block,best:r.best,score:r.score});
        probesByKind.cal.push({task:t,block,score:r.score,gap:r.gap,best:r.best,
          teacher_signature:cal.teacher_signature,stream:cal.sample_stream});
      }
    }
    const globalThreshold=quantile(calibration.map(x=>x.score),C.cal_q);
    const slotThresholds=archive.map((_,i)=>{
      const group=calibration.filter(x=>x.best===i).map(x=>x.score);
      return group.length>=4?quantile(group,C.cal_q):globalThreshold;
    });
    const methodThreshold=(method,pr)=>{
      if(method==="always_reuse")return Infinity;
      if(method==="fixed61")return C.old_reuse_threshold;
      if(method==="slot_q90")return slotThresholds[pr.best];
      return globalThreshold;
    };
    const counts={};
    for(const m of C.methods)counts[m]={known_rej:0,known_correct:0,shift_rej:0,unrelated_rej:0,near_rej:0,accepted_known:0};
    let evalExpertPredictions=0,evalQueryPredictions=0;
    for(let t=0;t<4;t++)for(let block=0;block<C.blocks_per_condition_per_task;block++){
      for(const kind of ["known","unrelated","near","shift"]){
        const task=kind==="unrelated"?4+t:kind==="near"?8+t:t;
        const s=samples(seed,task,kind,block,C.per_block);
        const scored=probe(archive,s.rows);
        evalExpertPredictions+=archive.length*s.rows.length;
        const row={task:t,source_task:task,kind,block,score:scored.score,gap:scored.gap,best:scored.best,
          teacher_signature:s.teacher_signature,stream:s.sample_stream,decisions:{}};
        for(const m of C.methods){
          const thr=methodThreshold(m,scored);
          const reject=scored.score>thr||(m==="global_q90_margin"&&scored.gap<C.margin_gate);
          row.decisions[m]=reject;
          const stat=counts[m];
          if(kind==="known"){
            if(reject)stat.known_rej++;
            else {
              stat.accepted_known++;
              const head=archive[scored.best];
              for(const q of knownQuery[t].rows) {
                if(Number(sigmoid(dot(head.w,q.x))>=.5)===q.y)stat.known_correct++;
                evalQueryPredictions++;
              }
            }
          }
          else if(kind==="unrelated"&&reject)stat.unrelated_rej++;
          else if(kind==="near"&&reject)stat.near_rej++;
          else if(kind==="shift"&&reject)stat.shift_rej++;
        }
        probesByKind[kind].push(row);
      }
    }
    if(hash(archive)!==archiveHash)throw Error("archive mutated by novelty evaluation");
    const denom=4*C.blocks_per_condition_per_task;
    const metrics={};
    for(const m of C.methods) {
      const z=counts[m];
      metrics[m]={
        known_fpr:z.known_rej/denom,
        shifted_fpr:z.shift_rej/denom,
        unrelated_tpr:z.unrelated_rej/denom,
        near_tpr:z.near_rej/denom,
        unknown_tpr:(z.unrelated_rej+z.near_rej)/(2*denom),
        known_accuracy_with_abstention:z.known_correct/(denom*C.known_query_per_task),
        accuracy_if_accepted:z.accepted_known?z.known_correct/(z.accepted_known*C.known_query_per_task):0,
        raw_counts:z
      };
    }
    return {
      seed,archive_hash_before:archiveHash,archive_hash_after:hash(archive),
      archive_heads:archive.length,
      training:{updates:trained.updates,router_predictions:trained.router_predictions,
        creations:trained.creations,forced_reuse:trained.forced,
        labels:C.schedule.length*C.train_per_episode,
        teacher_signatures:trained.train_signatures,streams:trained.train_streams},
      calibration:{global_threshold:globalThreshold,slot_thresholds:slotThresholds,
        rows:calibration,accesses:calibration.length*C.per_block,
        all_probe_rows:probesByKind.cal},
      evaluation:{kind_rows:Object.fromEntries(Object.entries(probesByKind).filter(([k])=>k!=="cal")),
        per_method:metrics,
        support_label_accesses:4*4*C.blocks_per_condition_per_task*C.per_block,
        head_score_evaluations:evalExpertPredictions,
        query_prediction_evaluations:evalQueryPredictions},
      query_provenance:knownQuery.map(z=>({signature:z.teacher_signature,stream:z.sample_stream})),
      near_signatures:expectedSignatures.near,
      unrelated_signatures:expectedSignatures.unknown.map(w=>hash(w))
    };
  }
  const runs=C.seeds.map(seed=>analyzeSeed(seed)),summary={};
  const keys=["known_fpr","shifted_fpr","unrelated_tpr","near_tpr","unknown_tpr","known_accuracy_with_abstention","accuracy_if_accepted"];
  for(const m of C.methods){
    summary[m]=Object.fromEntries(keys.map(k=>[k,avg(runs.map(r=>r.evaluation.per_method[m][k]))]));
  }
  const g=summary.global_q90,s=summary.slot_q90,f=summary.fixed61;
  const gates={
    global_unrelated_gain:g.unrelated_tpr-f.unrelated_tpr>=C.gates.global_vs_fixed_unrelated_gain
       &&g.known_fpr<=C.gates.max_known_fpr,
    near_novelty:g.near_tpr>=C.gates.min_near_tpr,
    context_shift_control:g.shifted_fpr<=C.gates.max_shift_fpr,
    preserved_known_accuracy:g.known_accuracy_with_abstention>=C.gates.min_known_accuracy,
    slot_beats_global:s.unknown_tpr-g.unknown_tpr>=C.gates.min_slot_gain&&s.known_fpr<=C.gates.max_known_fpr
  };
  return {protocol:C,summary,gates,decision:Object.values(gates).every(Boolean)?
    "PUBLIC_DEVELOPMENT_GATE_ONLY_INDEPENDENT_CONFIRMATION_REQUIRED":"HOLD_NO_VALIDATED_MEMORY_PROTECTION",runs};
}
function testV5(fn){
  const a=fn(),b=fn(),p=a.protocol;
  function check(z,m){if(!z)throw Error("R2V5 "+m);}
  check(JSON.stringify(a)===JSON.stringify(b),"determinism");
  check(a.runs.length===5,"seed runs");
  const identifiers=new Set();
  const kindCounts={known:48,unrelated:48,near:48,shift:48};
  for(const r of a.runs) {
    check(p.seeds.includes(r.seed)&&!identifiers.has(r.seed),"seed identity");
    identifiers.add(r.seed);
    check(r.archive_hash_before===r.archive_hash_after,"frozen archive");
    check(r.archive_heads>0&&r.archive_heads<=4,"head count");
    check(r.training.updates===512&&r.training.labels===512,"training budget");
    check(r.training.teacher_signatures.length===8&&r.training.streams.length===8,"training provenance");
    check(new Set(r.training.streams).size===8,"unique train streams");
    check(r.calibration.rows.length===48,"calibration size");
    check(r.calibration.accesses===48*16,"calibration label calls");
    check(r.evaluation.support_label_accesses===192*16,"eval support calls");
    check(r.evaluation.head_score_evaluations===192*16*r.archive_heads,"routing compute");
    check(r.calibration.slot_thresholds.length===r.archive_heads,"slot threshold shape");
    check(r.calibration.rows.every(x=>x.best>=0&&x.best<r.archive_heads),"calibration routing");
    for(const kind of Object.keys(kindCounts)){
      const rows=r.evaluation.kind_rows[kind];
      check(rows.length===kindCounts[kind],"kind sample count "+kind);
      check(new Set(rows.map(x=>x.stream)).size===48,"stream collision "+kind);
      for(const z of rows){
        check(Object.keys(z.decisions).length===p.methods.length,"method decision shape");
        check(z.score>=0&&Number.isFinite(z.score),"finite loss");
        check(z.best>=0&&z.best<r.archive_heads,"head selection");
        const q=r.query_provenance[z.task].signature;
        if(kind==="known"||kind==="shift")check(z.teacher_signature===q,"same teacher control "+kind);
        if(kind==="near")check(z.teacher_signature===r.near_signatures[z.task],"near teacher provenance");
        if(kind==="unrelated")check(z.teacher_signature===r.unrelated_signatures[z.task],"unrelated teacher provenance");
      }
    }
    for(const m of p.methods){
      const z=r.evaluation.per_method[m],raw=z.raw_counts;
      check(raw.known_rej<=48&&raw.shift_rej<=48&&raw.near_rej<=48&&raw.unrelated_rej<=48,"outcome bounds");
      check(z.known_accuracy_with_abstention>=0&&z.known_accuracy_with_abstention<=1,"accuracy bounds");
      check(raw.accepted_known+raw.known_rej===48,"known accounting");
      const expected=Object.values(r.evaluation.kind_rows).reduce((acc,rows)=>{
        const key=rows[0].kind;
        const reject=rows.filter(x=>x.decisions[m]).length;
        acc[key]=reject;return acc;
      },{});
      check(expected.known===raw.known_rej&&expected.shift===raw.shift_rej
        &&expected.near===raw.near_rej&&expected.unrelated===raw.unrelated_rej,"decision accounting");
    }
  }
  for(const m of p.methods){
    for(const key of ["known_fpr","shifted_fpr","unrelated_tpr","near_tpr","unknown_tpr","known_accuracy_with_abstention","accuracy_if_accepted"]){
      const v=a.runs.reduce((s,r)=>s+r.evaluation.per_method[m][key],0)/5;
      check(Math.abs(v-a.summary[m][key])<1e-12,"summary "+m+":"+key);
    }
  }
  return {status:"PASS",assertion_families:18,seed_runs:a.runs.length,checks:"equal supports, immutable archive, novelty/control provenance, thresholds and gates"};
}
module.exports={runV5,testV5};
if(require.main===module){console.error(JSON.stringify(testV5(runV5)));process.stdout.write(JSON.stringify(runV5(),null,2)+"\n");}
