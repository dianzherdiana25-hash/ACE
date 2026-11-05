"use strict";
/** R2-v3 public synthetic, non-privileged learner experiment; no external oracle or frozen E1.4 data. */
function runV3() {
  "use strict";
  const C = {
    id:"R2_LIFELONG_V3_PUBLIC_DEVELOPMENT",
    seeds:[7,19,43,91],
    families:["sparse_linear","compositional","rotating"],
    regimes:["separated","overlap"],
    methods:["frozen","sgd","ewc","replay","selective","no_transfer","fixed_slots","oracle"],
    episodes:[0,1,2,0,3,1,2,0],
    center:[-0.9,-0.3,0.3,0.9], overlap_center:[-.18,-.06,.06,.18],
    examples_per_episode:64, eval_examples_per_task:96, eval_shift:0.16,
    feature_dim:16, replay_cap:48, max_experts:4,
    novelty_radius:0.21, rate:0.09, ewc_strength:3.0, transfer_fraction:0.2,
    noise_prob:0.03,
    gates:{
      min_mean_final:0.68, max_avg_forgetting:0.10,
      min_mean_advantage_equal_capacity:0.025,
      min_mean_advantage_replay:0.025,
      max_ood_drop:0.05
    },
    evaluator:"public author-visible split, not confirmatory; task ID privileged only for oracle"
  };
  function rand(seed){
    let s=(seed>>>0)||1;
    return ()=>{s^=s<<13;s^=s>>>17;s^=s<<5;return (s>>>0)/4294967296;};
  }
  function avg(a){return a.reduce((s,x)=>s+x,0)/a.length;}
  function phi(x){
    return x.concat([x[0]*x[1],x[2]*x[3],x[4]*x[5],x[6]*x[7],x[1]*x[7],x[3]*x[8]]);
  }
  function teacher(seed,family,t){
    const r=rand(seed*1009+C.families.indexOf(family)*1613+707);
    const base=Array(16).fill(0), rules=[];
    for(let task=0;task<4;task++){
      const w=base.slice();
      const linear=Array.from({length:10},(_,i)=>i),pairs=Array.from({length:6},(_,i)=>i+10);
      for(let n=linear.length-1;n>0;n--){const k=Math.floor(r()*(n+1));[linear[k],linear[n]]=[linear[n],linear[k]];}
      for(let n=pairs.length-1;n>0;n--){const k=Math.floor(r()*(n+1));[pairs[k],pairs[n]]=[pairs[n],pairs[k]];}
      const lind=family==="compositional"?1:3, pc=family==="sparse_linear"?0:3;
      for(const ix of linear.slice(0,lind))w[ix]=(r()<0.5?-1:1)*(0.7+0.8*r());
      for(const ix of pairs.slice(0,pc))w[ix]=(r()<0.5?-1:1)*(0.7+0.8*r());
      rules.push(w);
    }
    if(family==="rotating"){
      const w=rules[0];
      for(let i=1;i<4;i++){
        rules[i]=Array(16).fill(0);
        for(let j=0;j<10;j++)rules[i][(j+2*i)%10]=w[j];
      }
    }
    return rules[t];
  }
  function bank(ruleSeed,drawSeed,family,regime,episode,task,split){
    const r=rand(drawSeed*131071+C.families.indexOf(family)*7919+C.regimes.indexOf(regime)*601+
      task*10007+episode*2221+(split==="train"?1:split==="ood"?900001:400001));
    const n=split==="train"?C.examples_per_episode:C.eval_examples_per_task;
    const w=teacher(ruleSeed,family,task);
    const cen=(regime==="separated"?C.center:C.overlap_center)[task];
    const jitter=regime==="separated"?0.03:0.23;
    const ans=[];
    for(let i=0;i<n;i++){
      const x=Array.from({length:10},()=>r()<0.5?-1:1);
      const f=phi(x),v=w.reduce((s,wi,j)=>s+wi*f[j],0);
      const y=((v>=0?1:0)^(r()<C.noise_prob?1:0));
      const c=cen+(r()*2-1)*jitter+(split==="ood"?C.eval_shift:0);
      ans.push({f,c,y,task,rule_seed:ruleSeed});
    }
    return ans;
  }
  function sigmoid(z){return z>20?1:z< -20?0:1/(1+Math.exp(-z));}
  function nearest(experts,c){
    let ix=-1,d=Infinity;
    for(let k=0;k<experts.length;k++){
      const dst=Math.abs(experts[k].c-c);
      if(dst<d){ix=k;d=dst;}
    }
    return {ix,d};
  }
  function init(method,regime){
    const d=C.feature_dim;
    return {
      method,w:Array(d*3).fill(0),fisher:Array(d*3).fill(0),anchor:Array(d*3).fill(0),
      experts:(method==="fixed_slots"||method==="oracle")?
        (regime==="separated"?C.center:C.overlap_center).map(c=>({c,w:Array(d).fill(0),n:0})):[],
      buffer:[],seen:0,
      updates:0,coordinate_ops:0,penalty_ops:0,fisher_ops:0,create_count:0,saturations:0
    };
  }
  function output(m,p){
    if(["selective","no_transfer","fixed_slots","oracle"].includes(m.method)){
      const k=m.method==="oracle"?p.task:nearest(m.experts,p.c).ix;
      return k<0?0.5:sigmoid(p.f.reduce((sum,f,j)=>sum+f*m.experts[k].w[j],0));
    }
    let z=0;
    for(let j=0;j<C.feature_dim;j++){
      z+=m.w[j]*p.f[j]+m.w[j+C.feature_dim]*p.c*p.f[j]+m.w[j+2*C.feature_dim]*p.c*p.c*p.f[j];
    }
    return sigmoid(z);
  }
  function accuracy(m,b){
    let good=0;
    for(const p of b){if(Number(output(m,p)>=0.5)===p.y)good++;}
    return good/b.length;
  }
  function update(m,p){
    const z=output(m,p),delta=(p.y-z)*C.rate;
    if(["selective","no_transfer","fixed_slots","oracle"].includes(m.method)){
      const a=nearest(m.experts,p.c);
      let i=a.ix;
      if(["selective","no_transfer"].includes(m.method)&&(i<0||a.d>C.novelty_radius)){
        if(m.experts.length<C.max_experts){
          const initw=Array(C.feature_dim).fill(0);
          if(m.method==="selective"&&i>=0)for(let j=0;j<C.feature_dim;j++)initw[j]=C.transfer_fraction*m.experts[i].w[j];
          m.experts.push({c:p.c,w:initw,n:0});i=m.experts.length-1;m.create_count++;
        }else{m.saturations++;}
      }
      if(m.method==="oracle")i=p.task;
      const e=m.experts[i];
      for(let j=0;j<C.feature_dim;j++){e.w[j]+=delta*p.f[j];m.coordinate_ops++;}
      if(m.method==="selective"||m.method==="no_transfer"){
        e.c=(e.c*e.n+p.c)/(e.n+1);e.n++;
      }
    }else{
      for(let j=0;j<C.feature_dim*3;j++){
        const f=p.f[j%C.feature_dim]*(j<C.feature_dim?1:j<2*C.feature_dim?p.c:p.c*p.c);
        const penalty=m.method==="ewc"?C.ewc_strength*m.fisher[j]*(m.w[j]-m.anchor[j]):0;
        m.w[j]+=delta*f-C.rate*penalty;
        if(m.method==="ewc")m.penalty_ops++;
        m.coordinate_ops++;
      }
    }
    m.updates++;
  }
  function consolidate(m,rows){
    for(let j=0;j<C.feature_dim*3;j++){
      let total=0;
      for(const p of rows){
        const q=output(m,p),f=p.f[j%C.feature_dim]*(j<C.feature_dim?1:j<2*C.feature_dim?p.c:p.c*p.c);
        total+=q*(1-q)*f*f/rows.length;m.fisher_ops++;
      }
      m.fisher[j]+=total;m.anchor[j]=m.w[j];
    }
  }
  function trial(seed,family,regime,method){
    const m=init(method,regime);
    const test=Array.from({length:4},(_,t)=>bank(seed,seed+200,family,regime,0,t,"test"));
    const ood=Array.from({length:4},(_,t)=>bank(seed,seed+300,family,regime,0,t,"ood"));
    const records=[],rng=rand(seed*7717+71),first=Array(4).fill(null),zeroShot=Array(4).fill(null);
    const snapshots=[],trainRuleSeeds=[];
    for(let ep=0;ep<C.episodes.length;ep++){
      const task=C.episodes[ep],train=bank(seed,seed,family,regime,ep,task,"train");
      trainRuleSeeds.push(train[0].rule_seed);
      if(first[task]===null)zeroShot[task]=accuracy(m,test[task]);
      if(method!=="frozen"||ep===0) {
        for(const p of train) {
          update(m,p);
          if(method==="replay"){
            if(m.buffer.length)update(m,m.buffer[Math.floor(rng()*m.buffer.length)]);
            m.seen++;
            if(m.buffer.length<C.replay_cap)m.buffer.push(p);
            else{const k=Math.floor(rng()*m.seen);if(k<C.replay_cap)m.buffer[k]=p;}
          }
        }
        if(method==="ewc")consolidate(m,train);
      }
      const accs=test.map(b=>accuracy(m,b));
      if(first[task]===null)first[task]=accs[task];
      snapshots.push(accs);
      records.push({episode:ep,task,per_task:accs,current_task:accs[task],mean_seen:
        avg(accs.filter((_,k)=>C.episodes.slice(0,ep+1).includes(k)))});
    }
    const final=snapshots.at(-1);
    let forget=0;
    for(let t=0;t<4;t++){
      const peak=Math.max(...snapshots.filter((_,ep)=>ep>=C.episodes.indexOf(t)).map(a=>a[t]));
      forget+=Math.max(0,peak-final[t]);
    }
    forget/=4;
    const bwt=avg(final.map((x,t)=>x-first[t]));
    const fwt=avg(zeroShot.slice(1).map(x=>x-0.5));
    const memoryScalars=["selective","no_transfer","fixed_slots","oracle"].includes(method)?
      m.experts.length*(C.feature_dim+2):method==="ewc"?C.feature_dim*9:C.feature_dim*3;
    return {seed,family,regime,method,final_accuracy:avg(final),
      average_forgetting:forget,backward_transfer:bwt,forward_transfer:fwt,
      ood_accuracy:avg(ood.map(b=>accuracy(m,b))),final_by_task:final,first_by_task:first,
      trajectory:records,
      provenance:{train_rule_seeds:trainRuleSeeds,test_rule_seeds:test.map(b=>b[0].rule_seed),ood_rule_seeds:ood.map(b=>b[0].rule_seed)},
      costs:{new_labels:C.episodes.length*C.examples_per_episode,updates:m.updates,
        coordinate_ops:m.coordinate_ops,penalty_ops:m.penalty_ops,fisher_ops:m.fisher_ops,
        replay_examples:m.buffer.length,persistent_scalars:memoryScalars,
        experts:m.experts.length,created:m.create_count,saturations:m.saturations}};
  }
  const results=[];
  for(const family of C.families)for(const regime of C.regimes)for(const seed of C.seeds)for(const method of C.methods)
    results.push(trial(seed,family,regime,method));
  const summary={};
  for(const family of C.families)for(const regime of C.regimes){
    const key=family+"/"+regime;
    summary[key]={};
    for(const method of C.methods){
      const rows=results.filter(r=>r.family===family&&r.regime===regime&&r.method===method);
      const keys=["final_accuracy","average_forgetting","backward_transfer","forward_transfer","ood_accuracy"];
      const rec={};
      for(const k of keys)rec[k]=avg(rows.map(r=>r[k]));
      for(const k of ["updates","coordinate_ops","penalty_ops","fisher_ops","replay_examples","persistent_scalars","experts","saturations"])
        rec[k]=avg(rows.map(r=>r.costs[k]));
      summary[key][method]=rec;
    }
  }
  const sample=C.families.flatMap(f=>C.regimes.map(g=>({f,g,s:summary[f+"/"+g]})));
  const selectiveFinal=avg(sample.map(v=>v.s.selective.final_accuracy));
  const selectiveOOD=avg(sample.map(v=>v.s.selective.ood_accuracy));
  const selectiveForget=avg(sample.map(v=>v.s.selective.average_forgetting));
  const matched=avg(sample.map(v=>Math.max(v.s.no_transfer.final_accuracy,v.s.fixed_slots.final_accuracy)));
  const replay=avg(sample.map(v=>v.s.replay.final_accuracy));
  const gates={
    mean_final:selectiveFinal>=C.gates.min_mean_final,
    retention:selectiveForget<=C.gates.max_avg_forgetting,
    equal_capacity_advantage:selectiveFinal-matched>=C.gates.min_mean_advantage_equal_capacity,
    replay_advantage:selectiveFinal-replay>=C.gates.min_mean_advantage_replay,
    context_shift_robustness:selectiveFinal-selectiveOOD<=C.gates.max_ood_drop
  };
  return {protocol:C,results,summary,aggregate:{
    candidate_final:selectiveFinal,candidate_ood:selectiveOOD,candidate_forgetting:selectiveForget,
    equal_capacity_reference:matched,replay_reference:replay},gates,
    decision:Object.values(gates).every(Boolean)?"EXPLORATORY_ONLY_NEEDS_BLIND_CONFIRMATION":"HOLD_NO_VALIDATED_SUPERIORITY"};
}
function testV3(f){
  const a=f(),b=f(),p=a.protocol;
  function guard(cond,msg){if(!cond)throw Error(msg);}
  guard(JSON.stringify(a)===JSON.stringify(b),"determinism");
  guard(a.results.length===p.seeds.length*p.families.length*p.regimes.length*p.methods.length,"matrix");
  const ids=new Set();
  for(const x of a.results){
    const id=[x.family,x.regime,x.seed,x.method].join("/");
    guard(!ids.has(id),"duplicate "+id);ids.add(id);
    guard(x.trajectory.length===p.episodes.length,"episode trajectory");
    guard(x.provenance.train_rule_seeds.every(z=>z===x.seed)&&x.provenance.test_rule_seeds.every(z=>z===x.seed)&&x.provenance.ood_rule_seeds.every(z=>z===x.seed),"split rule identity mismatch");
    guard(x.trajectory.every((row,i)=>row.episode===i&&row.task===p.episodes[i]),"episode leakage");
    guard(x.costs.new_labels===p.episodes.length*p.examples_per_episode,"labels");
    guard(x.costs.updates===(
      x.method==="frozen"?64:x.method==="replay"?1023:512),"updates");
    guard(x.costs.replay_examples===(x.method==="replay"?48:0),"replay capacity");
    guard(x.costs.experts<=p.max_experts,"expert capacity");
    guard(x.costs.persistent_scalars>=0&&Number.isFinite(x.costs.persistent_scalars),"memory");
    guard(x.final_by_task.length===4&&x.first_by_task.length===4,"task matrix");
    guard([x.final_accuracy,x.ood_accuracy,x.average_forgetting].every(n=>n>=0&&n<=1),"metric bounds");
    guard(x.trajectory.every(v=>v.per_task.length===4&&v.per_task.every(n=>n>=0&&n<=1)),"intermediate metrics");
    guard(x.costs.fisher_ops===(x.method==="ewc"?512*48:0),"fisher cost");
    guard(x.costs.penalty_ops===(x.method==="ewc"?512*48:0),"penalty cost");
    guard(x.costs.coordinate_ops===(x.costs.updates*(["selective","no_transfer","fixed_slots","oracle"].includes(x.method)?16:48)),"coordinate ops");
  }
  const metricKeys=["final_accuracy","ood_accuracy","average_forgetting","backward_transfer","forward_transfer"];
  for(const family of p.families)for(const regime of p.regimes)for(const method of p.methods){
    const rows=a.results.filter(x=>x.family===family&&x.regime===regime&&x.method===method);
    guard(rows.length===p.seeds.length,"group length");
    for(const k of metricKeys){
      const mean=rows.reduce((s,x)=>s+x[k],0)/rows.length;
      guard(Math.abs(mean-a.summary[family+"/"+regime][method][k])<1e-12,"aggregation "+k);
    }
  }
  return {status:"PASS",invariant_categories:17,run_count:a.results.length,notes:"direct same-isolate replay; not GitHub exact-head CI"};
}
module.exports={runV3,testV3};
if(require.main===module){console.error(JSON.stringify(testV3(runV3)));process.stdout.write(JSON.stringify(runV3(),null,2)+"\n");}
