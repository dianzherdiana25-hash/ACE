"use strict";
/** ACE R2-v2: deterministic, independent public synthetic extension. No external labels, no frozen E1.4 sources. */
function researchV2() {
  "use strict";
  const cfg={
    protocol:"ACE_R2_V2_PUBLIC_SYNTHETIC",
    seeds:[7,13,29,43,61], task_count:4,
    sequence:[0,1,2,0,3,0], n_train_per_episode:64, n_eval_per_task:128,
    contexts:[-0.75,-0.25,0.25,0.75], slope:[1,-1,1,-1],
    methods:["frozen","sgd","ewc","replay","selective","no_transfer","fixed_slots","oracle"],
    regimes:["separated","overlap","shifted_revisit","conflicting_flip"],
    capacity_experts:4, replay_cap:48, novelty_radius:0.19,
    learning_rate:0.28, ewc_lambda:2.0,
    exploratory_gates:{
      min_separated_final:0.85,
      min_separated_old_task_retention:0.9,
      min_overlapping_accuracy:0.75,
      min_shifted_accuracy:0.85,
      min_flip_adaptation_gain:0.20,
      min_margin_over_equal_capacity:0.03
    },
    isolation:"All generated labels public and deterministic; no secret bank or task ID except explicit oracle upper bound"
  };
  function mean(a){return a.reduce((s,x)=>s+x,0)/a.length;}
  function rng(seed){let x=(seed>>>0)||1;return ()=>{x^=x<<13;x^=x>>>17;x^=x<<5;return (x>>>0)/4294967296;};}
  function center(task,regime){
    return regime==="overlap"?[-.24,-.08,.08,.24][task]:cfg.contexts[task];
  }
  function dataset(seed,task,regime,split,phase="original"){
    const n=split==="train"?64:128;
    const offset=split==="train"?0:split==="ood"?84000:42000;
    const r=rng((seed*12289 + task*70001 + offset + (phase==="shifted"?111:phase==="flipped"?222:0)+regime.length*1009)>>>0);
    const shifted=phase==="shifted";
    const flip=phase==="flipped" && task===0;
    const width=regime==="overlap"?0.16:0.025;
    let rows=[];
    for(let i=0;i<n;i++){
      const mag=.06+.94*r();
      const x=i%2===0?mag:-mag;
      const c=center(task,regime)+(r()*2-1)*width+(shifted?.14:split==="ood"?.10:0);
      const s=cfg.slope[task]*(flip?-1:1);
      rows.push({x,c,task,y:(s*x>0?1:0)});
    }
    return rows;
  }
  function sigmoid(x){return x>25?1:x< -25?0:1/(1+Math.exp(-x));}
  function phi(p){return [p.x,p.x*p.c,p.x*p.c*p.c];}
  function closest(protos,c){
    let ix=-1,d=Infinity;
    for(let i=0;i<protos.length;i++){let v=Math.abs(protos[i].center-c);if(v<d){ix=i;d=v;}}
    return {ix,d};
  }
  function init(method,regime){
    return {method,regime,global:[0,0,0],fisher:[0,0,0],anchor:[0,0,0],experts:
      (method==="fixed_slots"||method==="oracle")?Array.from({length:4},(_,i)=>({center:center(i,regime),w:0,n:0})):[],
      replay:[],seen:0,updates:0,coordinate_updates:0,ewc_penalty_ops:0,fisher_ops:0,expert_creations:0,novelty_saturations:0};
  }
  function prediction(m,p){
    const mode=m.method;
    if(["selective","no_transfer","fixed_slots","oracle"].includes(mode)){
      const i=mode==="oracle"?p.task:closest(m.experts,p.c).ix;
      return i<0?.5:sigmoid(m.experts[i].w*p.x);
    }
    const f=phi(p);
    return sigmoid(m.global.reduce((s,v,i)=>s+v*f[i],0));
  }
  function acc(m,rows){
    let ok=0;
    for(const p of rows){if((prediction(m,p)>=.5?1:0)===p.y)ok++;}
    return ok/rows.length;
  }
  function update(m,p){
    if(["selective","no_transfer","fixed_slots","oracle"].includes(m.method)){
      let nearest=closest(m.experts,p.c),j=nearest.ix;
      if(["selective","no_transfer"].includes(m.method) && (j<0||nearest.d>cfg.novelty_radius)){
        if(m.experts.length<cfg.capacity_experts){
          const w=m.method==="selective"&&j>=0?0.25*m.experts[j].w:0;
          m.experts.push({center:p.c,w,n:0});
          j=m.experts.length-1;
          m.expert_creations++;
        }else{
          j=nearest.ix;m.novelty_saturations++;
        }
      }
      if(m.method==="oracle")j=p.task;
      const e=m.experts[j],pr=sigmoid(e.w*p.x);
      e.w+=cfg.learning_rate*(p.y-pr)*p.x;
      if(m.method!=="fixed_slots"&&m.method!=="oracle"){
        e.center=(e.center*e.n+p.c)/(e.n+1);e.n++;
      }
      m.coordinate_updates++;
    }else{
      const f=phi(p),pr=prediction(m,p);
      for(let i=0;i<3;i++){
        const penalty=m.method==="ewc"?cfg.ewc_lambda*m.fisher[i]*(m.global[i]-m.anchor[i]):0;
        m.global[i]+=cfg.learning_rate*((p.y-pr)*f[i]-penalty);
        if(m.method==="ewc")m.ewc_penalty_ops++;
        m.coordinate_updates++;
      }
    }
    m.updates++;
  }
  function consolidate(m,bank){
    for(let j=0;j<3;j++){
      let f=0;
      for(const p of bank){let q=prediction(m,p);f+=q*(1-q)*phi(p)[j]**2/bank.length;m.fisher_ops++;}
      m.fisher[j]+=f;
      m.anchor[j]=m.global[j];
    }
  }
  function single(seed,regime,method){
    const m=init(method,regime);
    const test=Array.from({length:4},(_,t)=>dataset(seed+1000,t,regime,"test"));
    const shifted=dataset(seed+1110,0,regime,"test","shifted");
    const flipped=dataset(seed+1190,0,regime,"test","flipped");
    const ood=Array.from({length:4},(_,t)=>dataset(seed+2000,t,regime,"ood"));
    const first_seen=[-1,-1,-1,-1];
    let post_first=[null,null,null,null],pre_first=[null,null,null,null],per_step=[];
    let pre_shift=null,pre_flip=null;
    const random=rng(seed*3181+921);
    for(let ep=0;ep<cfg.sequence.length;ep++){
      const task=cfg.sequence[ep];
      if(ep===5){pre_shift=acc(m,shifted);pre_flip=acc(m,flipped);}
      let phase="original";
      if(regime==="shifted_revisit"&&task===0&&ep>=3)phase="shifted";
      if(regime==="conflicting_flip"&&ep===5)phase="flipped";
      const bank=dataset(seed+ep*557,task,regime,"train",phase);
      if(first_seen[task]===-1){first_seen[task]=ep;pre_first[task]=acc(m,test[task]);}
      if(method!=="frozen"||ep===0) {
        for(const p of bank){
          update(m,p);
          if(method==="replay"){
            if(m.replay.length)update(m,m.replay[Math.floor(random()*m.replay.length)]);
            m.seen++;
            if(m.replay.length<cfg.replay_cap)m.replay.push(p);
            else {const z=Math.floor(random()*m.seen);if(z<cfg.replay_cap)m.replay[z]=p;}
          }
        }
        if(method==="ewc")consolidate(m,bank);
      }
      if(first_seen[task]===ep)post_first[task]=acc(m,test[task]);
      per_step.push({episode:ep,task,phase,accuracy:test.map(b=>acc(m,b)),new_phase_accuracy:
        phase==="flipped"?acc(m,flipped):phase==="shifted"?acc(m,shifted):null});
    }
    const final=test.map(b=>acc(m,b));
    const latestFinal=final.slice();
    if(regime==="shifted_revisit")latestFinal[0]=acc(m,shifted);
    if(regime==="conflicting_flip")latestFinal[0]=acc(m,flipped);
    const transfer=mean(pre_first.slice(1).map(x=>x-.5));
    const ret=mean([1,2,3].map(t=>final[t]-post_first[t]));
    const original_task0=final[0];
    const unseenShifted=acc(m,shifted),unseenFlip=acc(m,flipped);
    return {
      seed,regime,method,
      final_original:final,final_latest:latestFinal,
      final_accuracy:mean(latestFinal),ood_accuracy:mean(ood.map(b=>acc(m,b))),
      retention_delta_unmodified:ret,forward_transfer_delta:transfer,
      task0_original_final:original_task0,shifted_task0_final:unseenShifted,
      shifted_adaptation_gain:pre_shift===null?0:unseenShifted-pre_shift,
      flip_task0_final:unseenFlip,flip_adaptation_gain:pre_flip===null?0:unseenFlip-pre_flip,
      first_seen,pre_first,post_first,trajectory:per_step,
      costs:{
        labels_observed:cfg.sequence.length*64,updates:m.updates,
        coordinate_updates:m.coordinate_updates,
        ewc_penalty_ops:m.ewc_penalty_ops,fisher_ops:m.fisher_ops,
        replay_examples:m.replay.length,
        persistent_scalars:m.method==="ewc"?9:
          ["selective","no_transfer","fixed_slots","oracle"].includes(m.method)?m.experts.length*3:3,
        expert_count:m.experts.length,expert_creations:m.expert_creations,
        novelty_saturations:m.novelty_saturations
      }
    };
  }
  const raw=[];
  for(const regime of cfg.regimes)for(const seed of cfg.seeds)for(const method of cfg.methods)raw.push(single(seed,regime,method));
  const summary={};
  const keys=["final_accuracy","ood_accuracy","retention_delta_unmodified","forward_transfer_delta",
     "task0_original_final","shifted_task0_final","shifted_adaptation_gain","flip_task0_final","flip_adaptation_gain"];
  for(const regime of cfg.regimes){
    summary[regime]={};
    for(const method of cfg.methods){
      const subset=raw.filter(x=>x.regime===regime&&x.method===method);
      const averages=Object.fromEntries(keys.map(k=>[k,mean(subset.map(x=>x[k]))]));
      for(const k of ["updates","coordinate_updates","ewc_penalty_ops","fisher_ops","replay_examples","persistent_scalars","expert_count","novelty_saturations"]){
        averages[k]=mean(subset.map(x=>x.costs[k]));
      }
      summary[regime][method]=averages;
    }
  }
  const s=summary,se=s.separated.selective,ov=s.overlap.selective,sh=s.shifted_revisit.selective,fl=s.conflicting_flip.selective;
  const equalCapacity=Math.max(s.separated.no_transfer.final_accuracy,s.separated.fixed_slots.final_accuracy);
  const gates={
    separated:se.final_accuracy>=cfg.exploratory_gates.min_separated_final,
    retention:se.retention_delta_unmodified>=- (1-cfg.exploratory_gates.min_separated_old_task_retention),
    overlap:ov.final_accuracy>=cfg.exploratory_gates.min_overlapping_accuracy,
    shifted:sh.final_accuracy>=cfg.exploratory_gates.min_shifted_accuracy,
    flip_adaptation:fl.flip_adaptation_gain>=cfg.exploratory_gates.min_flip_adaptation_gain,
    capacity_matched_gain:se.final_accuracy-equalCapacity>=cfg.exploratory_gates.min_margin_over_equal_capacity
  };
  return {cfg,summary,gates,decision:Object.values(gates).every(Boolean)?"EXPLORATORY_GATE_MET_NOT_CONFIRMED":"HOLD_NO_VALIDATED_LIFELONG_ADVANTAGE",raw};
}
function testV2(fn){
  const a=fn(),b=fn(),json=JSON.stringify(a);
  if(json!==JSON.stringify(b))throw Error("R2 v2 deterministic mismatch");
  if(a.raw.length!==160)throw Error("missing 160 experiment runs");
  if(a.raw.some(r=>r.costs.labels_observed!==384))throw Error("stream budgets differ");
  if(a.raw.some(r=>r.costs.replay_examples>48))throw Error("replay buffer overflow");
  if(a.raw.some(r=>r.costs.expert_count>4))throw Error("expert budget overflow");
  if(a.raw.some(r=>r.costs.updates>767))throw Error("update budget exceeded");
  if(a.raw.some(r=>r.costs.persistent_scalars>12))throw Error("persistent scalar budget overflow");
  if(a.raw.some(r=>r.final_latest.some(v=>v<0||v>1)))throw Error("bad accuracy");
  if(a.raw.some(r=>r.first_seen.join(",")!=="0,1,2,4"))throw Error("episode split error");
  if(a.raw.some(r=>r.trajectory.length!==6))throw Error("missing trajectory");
  if(a.raw.filter(r=>r.method==="frozen").some(r=>r.costs.updates!==64))throw Error("incorrect frozen updates");
  if(a.raw.filter(r=>r.method==="replay").some(r=>r.costs.updates!==767))throw Error("incorrect replay updates");
  if(a.raw.filter(r=>r.method==="oracle").some(r=>r.costs.expert_count!==4))throw Error("oracle expert count");
  if(a.raw.filter(r=>r.method==="ewc").some(r=>r.costs.fisher_ops!==1152))throw Error("EWC Fisher budget");
  if(!a.summary.separated.selective || !a.summary.overlap.oracle)throw Error("missing comparators");
  return {assertions:15,result:"PASS",scope:"same-isolate deterministic and budget checks; no exact-head CI"};
}
module.exports={researchV2,testV2};
if(require.main===module){console.error(JSON.stringify(testV2(researchV2)));process.stdout.write(JSON.stringify(researchV2(),null,2)+"\n");}
