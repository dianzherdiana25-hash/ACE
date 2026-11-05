"use strict";
// R2: stdlib-free, public deterministic sequential synthetic lifelong-learning benchmark.
// No sealed ACE research banks, external labels or task IDs at inference.
function experiment() {
  "use strict";
  const PROTOCOL = {
    id: "R2_PUBLIC_DEVELOPMENT_V1",
    seeds: [11,23,47,89,131],
    tasks: 4,
    train_per_task: 96,
    test_per_task: 192,
    slopes: [1,1,-1,-1],
    contexts: [-0.75,-0.25,0.25,0.75],
    modes: ["identifiable","collapsed"],
    methods: ["frozen","sgd","ewc","replay","selective","fixed_slots"],
    thresholds: {retention_min:0.95, ood_min:0.90, margin_above_best_non_oracle:0.03, negative_control_max:0.65},
    eval_note: "Public author-visible deterministic development benchmark, not independent confirmation",
  };
  function rng(seed) {
    let z = seed >>> 0;
    return function() { z ^= z << 13; z ^= z >>> 17; z ^= z << 5; return (z >>> 0) / 4294967296; };
  }
  function points(seed, task, mode, split) {
    const n = split === "train" ? 96 : 192;
    const offset = split === "train" ? 0 : split === "ood" ? 200000 : 100000;
    const r = rng((seed*1103 + task*99991 + offset + (mode === "collapsed" ? 31337:0)) >>> 0);
    const center = mode === "collapsed" ? 0 : PROTOCOL.contexts[task];
    const slope = PROTOCOL.slopes[task];
    const out = [];
    for (let k=0;k<n;k++) {
      const magnitude = 0.08 + 0.92*r();
      const x = (r()<0.5?-1:1)*magnitude;
      const c = mode === "collapsed" ? 0 : center + (r()-0.5)*0.06 + (split==="ood"?0.12:0);
      out.push({x,c,y:slope*x>0?1:0});
    }
    return out;
  }
  function sigmoid(z) { return z>20?1:z< -20?0:1/(1+Math.exp(-z)); }
  function features(p) { return [p.x,p.x*p.c,p.x*p.c*p.c]; }
  function nearest(protos,c) {
    let pick=-1,dist=Infinity;
    for(let j=0;j<protos.length;j++) {
      const d=Math.abs(protos[j].center-c);
      if(d<dist) {dist=d;pick=j;}
    }
    return {pick,dist};
  }
  function model(method) {
    return {method,w:[0,0,0],fisher:[0,0,0],anchor:[0,0,0],protos:[],updates:0,penalty_ops:0,buffer:[],seen:0};
  }
  function prob(m,p) {
    if(m.method==="selective" || m.method==="fixed_slots") {
      const ix=nearest(m.protos,p.c).pick;
      return ix<0?0.5:sigmoid(m.protos[ix].w*p.x);
    }
    const phi=features(p);
    return sigmoid(m.w.reduce((a,v,j)=>a+v*phi[j],0));
  }
  function accuracy(m,bank) {
    let correct=0;
    for(const p of bank) { const yes=prob(m,p)>=0.5?1:0; if(yes===p.y)correct++; }
    return correct/bank.length;
  }
  function update(m,p,which) {
    const lr=0.24;
    if(m.method==="selective" || m.method==="fixed_slots") {
      const q=nearest(m.protos,p.c);
      let i=q.pick;
      if(m.method==="selective" && (i<0 || q.dist>0.19)) {
        if(m.protos.length>=PROTOCOL.tasks) throw new Error("prototype cap");
        m.protos.push({center:p.c,w:i>=0?m.protos[i].w*0.35:0,n:0});
        i=m.protos.length-1;
      }
      const a=m.protos[i], pr=sigmoid(a.w*p.x);
      a.w+=lr*(p.y-pr)*p.x;
      a.center=(a.center*a.n+p.c)/(a.n+1); a.n++;
    } else {
      const phi=features(p), pr=prob(m,p);
      for(let j=0;j<3;j++){
        const penalty=which==="ewc"?3.0*m.fisher[j]*(m.w[j]-m.anchor[j]):0;
        m.w[j]+=lr*((p.y-pr)*phi[j]-penalty);
        if(which==="ewc")m.penalty_ops++;
      }
    }
    m.updates++;
  }
  function finalizeEWC(m,bank) {
    for(let j=0;j<3;j++) {
      let f=0;
      for(const p of bank) {
        const q=prob(m,p),phi=features(p);
        f+=q*(1-q)*phi[j]*phi[j]/bank.length;
      }
      m.fisher[j]+=f;
      m.anchor[j]=m.w[j];
    }
  }
  function study(seed,mode,method) {
    const m=model(method);
    if(method==="fixed_slots") m.protos=PROTOCOL.contexts.map(c=>({center:c,w:0,n:0}));
    const evalBank=Array.from({length:4},(_,t)=>points(seed+8000,t,mode,"test"));
    const oodBank=Array.from({length:4},(_,t)=>points(seed+9000,t,mode,"ood"));
    const before=[],immediate=[],matrices=[];
    let prior=[];
    const rr=rng(seed*7001+88);
    for(let t=0;t<4;t++){
      before.push(accuracy(m,evalBank[t]));
      const bank=points(seed,t,mode,"train");
      if(method!=="frozen" || t===0) {
        for(const p of bank) {
          update(m,p,method);
          if(method==="replay" && m.buffer.length) {
            update(m,m.buffer[Math.floor(rr()*m.buffer.length)],method);
          }
          if(method==="replay") {
            m.seen++;
            if(m.buffer.length<64) m.buffer.push(p);
            else {
              const idx=Math.floor(rr()*m.seen);
              if(idx<64)m.buffer[idx]=p;
            }
          }
        }
        if(method==="ewc")finalizeEWC(m,bank);
      }
      prior.push(bank.length);
      immediate.push(accuracy(m,evalBank[t]));
      matrices.push(evalBank.map(b=>accuracy(m,b)));
    }
    const final=matrices[3];
    const mean=a=>a.reduce((x,y)=>x+y,0)/a.length;
    const oldFinal=mean(final.slice(0,3)),oldAtLearn=mean(immediate.slice(0,3));
    const backward=mean(final.slice(0,3).map((v,i)=>v-immediate[i]));
    const forward=mean(before.slice(1).map(v=>v-0.5));
    const memory_items=m.buffer.length;
    const weights=m.method==="selective"||m.method==="fixed_slots" ? m.protos.length : 3;
    const scalars=weights+(m.method==="selective"||m.method==="fixed_slots"?m.protos.length*2:0)+(method==="ewc"?6:0);
    return {seed,mode,method,first_learned:immediate,prelearn:before,final,
      mean_final:mean(final),old_final:oldFinal,old_learned:oldAtLearn,
      retention_fraction:oldAtLearn?oldFinal/oldAtLearn:0,
      backward_transfer:backward,forward_transfer:forward,
      ood_mean_final:mean(oodBank.map(b=>accuracy(m,b))),
      compute:{gradient_updates:m.updates,penalty_coord_ops:m.penalty_ops,ewc_fisher_samples:method==="ewc"?384:0},
      memory:{weight_and_metadata_scalars:scalars,replay_examples:memory_items,expert_count:m.protos.length},
      observed_train_labels:prior.reduce((x,y)=>x+y,0)};
  }
  const results=[];
  for(const mode of PROTOCOL.modes)for(const seed of PROTOCOL.seeds)for(const method of PROTOCOL.methods)results.push(study(seed,mode,method));
  function avg(rows,key) {return rows.reduce((a,r)=>a+r[key],0)/rows.length;}
  const summary={};
  for(const mode of PROTOCOL.modes) {
    summary[mode]={};
    for(const method of PROTOCOL.methods){
      const rows=results.filter(r=>r.mode===mode&&r.method===method);
      summary[mode][method]={
        mean_final:avg(rows,"mean_final"),mean_old_final:avg(rows,"old_final"),
        retention_fraction:avg(rows,"retention_fraction"),
        backward_transfer:avg(rows,"backward_transfer"),
        forward_transfer:avg(rows,"forward_transfer"),
        ood_mean_final:avg(rows,"ood_mean_final"),
        mean_gradient_updates:avg(rows.map(r=>({v:r.compute.gradient_updates})),"v"),
        mean_memory_scalars:avg(rows.map(r=>({v:r.memory.weight_and_metadata_scalars})),"v"),
        replay_examples:rows[0].memory.replay_examples,
        experts:rows[0].memory.expert_count,
      };
    }
  }
  const s=summary.identifiable;
  const best=Math.max(s.frozen.mean_final,s.sgd.mean_final,s.ewc.mean_final,s.replay.mean_final,s.fixed_slots.mean_final);
  const sel=s.selective;
  const gate={
    retention:sel.retention_fraction>=PROTOCOL.thresholds.retention_min,
    ood:sel.ood_mean_final>=PROTOCOL.thresholds.ood_min,
    superiority:sel.mean_final-best>=PROTOCOL.thresholds.margin_above_best_non_oracle,
    negative_control:summary.collapsed.selective.mean_final<=PROTOCOL.thresholds.negative_control_max,
  };
  return {protocol:PROTOCOL,summary,gate,scientific_gate:Object.values(gate).every(Boolean)?"DEVELOPMENT_GATE_MET_INDEPENDENT_CONFIRMATION_REQUIRED":"HOLD_NO_SUPERIORITY",results};
}
function tests(experiment) {
  const r=experiment(), rr=experiment();
  if(JSON.stringify(r)!==JSON.stringify(rr)) throw Error("non-deterministic replay");
  if(r.results.length!==60) throw Error("experiment count wrong");
  for(const e of r.results){
    if(e.observed_train_labels!==384)throw Error("unequal observed labels");
    if(e.method==="selective"&&e.memory.expert_count>4)throw Error("capacity cap");
    if(e.method==="replay"&&e.memory.replay_examples!==64)throw Error("replay cap");
    if(e.method!=="replay"&&e.memory.replay_examples!==0)throw Error("unexpected replay");
    if(e.final.some(x=>x<0||x>1))throw Error("accuracy bounds");
    if(e.compute.gradient_updates>767)throw Error("unbounded training");
    if(e.method==="frozen"&&e.compute.gradient_updates!==96)throw Error("frozen control");
  }
  if(r.summary.identifiable.selective.retention_fraction<0.95)throw Error("retention mechanism failed");
  if(r.summary.collapsed.selective.mean_final>0.65)throw Error("negative control failed");
  return {tests:10,status:"PASS"};
}
module.exports={experiment,tests};
if (require.main===module) { const check=tests(experiment); console.error(JSON.stringify(check)); process.stdout.write(JSON.stringify(experiment(),null,2)+"\n"); }
