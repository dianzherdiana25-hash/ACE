"use strict";
// ACE Research R3: standalone closed-interpreter architecture pilot. No third-party dependencies.
const r3Study = function r3Study() {
  "use strict";
  const INPUTS = 4, MAX_GATES = 4, CAP = 120, MAX_PROPOSALS = 12000;
  const OPS = ["AND","OR","XOR"], ARMS = ["fixed","config","random","evolve"];
  const DEV = ["masked_xor","and_pairs"], CONFIRM = ["cross_parity","mixed_xor"];
  const LAMBDA = 0.015, BEAM = 12, SHORTLIST = 12;
  function assert(ok,msg){if(!ok)throw new Error(msg);}
  function rng(seed) {
    let s=(seed>>>0)||1;
    return function(){s=(Math.imul(s,1664525)+1013904223)>>>0;return s/4294967296;};
  }
  function rand(r,n){return Math.floor(r()*n);}
  function clone(g){return {gates:g.gates.map(t=>({...t})),out:g.out};}
  function valid(g){
    if(!g||!Array.isArray(g.gates)||g.gates.length>MAX_GATES||!Number.isInteger(g.out)||g.out<0||g.out>=INPUTS+g.gates.length)throw Error("invalid graph output/size");
    g.gates.forEach((t,i)=>{
      if(!OPS.includes(t.op)||!Number.isInteger(t.a)||!Number.isInteger(t.b)||t.a<0||t.b<0||t.a>=INPUTS+i||t.b>=INPUTS+i)throw Error("invalid op/edge");
    });
    return true;
  }
  function predict(g,x) {
    valid(g);
    if(x.length!==INPUTS||x.some(t=>t!==0&&t!==1))throw Error("invalid input");
    const vals=x.slice();
    for(const t of g.gates) {
      const a=vals[t.a], b=vals[t.b];
      vals.push(t.op==="AND"?(a&b):(t.op==="OR"?(a|b):(a^b)));
    }
    return vals[g.out];
  }
  function target(task,x) {
    const [a,b,c,d]=x;
    switch(task){
      case "masked_xor":return (a^b)&c;
      case "and_pairs":return (a&b)|(c&d);
      case "cross_parity":return (a^c)^(b^d);
      case "mixed_xor":return (a|d)^(b&c);
      default:throw Error("unknown task");
    }
  }
  function split(task,seed) {
    const idx=[...Array(16).keys()];
    const taskCode=[...task].reduce((s,c)=>((Math.imul(s,31)+c.charCodeAt(0))>>>0),17);
    const r=rng((taskCode^(Math.imul(seed+1,19937)))>>>0);
    for(let i=idx.length-1;i>0;i--){let j=rand(r,i+1);[idx[i],idx[j]]=[idx[j],idx[i]];}
    const bits=k=>[k&1,(k>>1)&1,(k>>2)&1,(k>>3)&1];
    const x=idx.map(bits);
    return {train:x.slice(0,8),valid:x.slice(8,12),test:x.slice(12,16)};
  }
  function randomGraph(r){
    const n=rand(r,MAX_GATES+1),gates=[];
    for(let i=0;i<n;i++)gates.push({op:OPS[rand(r,3)],a:rand(r,INPUTS+i),b:rand(r,INPUTS+i)});
    return {gates,out:rand(r,INPUTS+n)};
  }
  function mutate(g,r){
    const q=clone(g),moves=["out"];
    if(q.gates.length){moves.push("rewire","operator","delete");}
    if(q.gates.length<MAX_GATES)moves.push("add","add","add");
    const move=moves[rand(r,moves.length)];
    if(move==="out")q.out=rand(r,INPUTS+q.gates.length);
    else if(move==="add"){
      const id=INPUTS+q.gates.length;
      q.gates.push({op:OPS[rand(r,3)],a:rand(r,id),b:rand(r,id)});
      q.out=id;
    }else if(move==="delete"){
      q.gates.pop();
      q.out=q.gates.length?INPUTS+q.gates.length-1:rand(r,INPUTS);
    }else{
      const i=rand(r,q.gates.length);
      if(move==="operator"){
        const options=OPS.filter(x=>x!==q.gates[i].op);
        q.gates[i].op=options[rand(r,options.length)];
      } else {
        q.gates[i][rand(r,2)?"a":"b"]=rand(r,INPUTS+i);
      }
    }
    valid(q);return q;
  }
  function fixedGraph(){return {gates:[{op:"XOR",a:0,b:1},{op:"XOR",a:2,b:3},{op:"AND",a:4,b:5}],out:6};}
  function graphKey(g){return JSON.stringify(g);}
  function runCase(task,seed,arm,flipHoldout=false) {
    const {train,valid:validPts,test}=split(task,seed);
    const code=[...task].reduce((s,c)=>((Math.imul(s,33)+c.charCodeAt(0))>>>0),5381);
    const r=rng((code^Math.imul(seed+1,809)^ARMS.indexOf(arm)*13007)>>>0);
    const seen=new Map();let proposals=0,gateOps=0;
    function evaluate(g,points,flip=false) {
      const labels=[];
      let wrong=0;
      for(const x of points){
        const v=predict(g,x);gateOps+=g.gates.length;
        labels.push(v);wrong+=(v!==(target(task,x)^(flip?1:0)));
      }
      return {error:wrong/points.length,signature:labels.join("")};
    }
    function admit(g){
      proposals++;
      const key=graphKey(g);
      if(seen.has(key)||seen.size>=CAP)return;
      valid(g);
      const result=evaluate(g,train);
      seen.set(key,{graph:g,score:result.error,signature:result.signature});
    }
    if(arm==="fixed"){admit(fixedGraph());}
    else if(arm==="config") {
      for(const p of OPS)for(const q of OPS)for(const t of OPS){
        admit({gates:[{op:p,a:0,b:1},{op:q,a:2,b:3},{op:t,a:4,b:5}],out:6});
      }
    }else if(arm==="random"){
      while(seen.size<CAP&&proposals<MAX_PROPOSALS)admit(randomGraph(r));
    }else if(arm==="evolve"){
      for(let i=0;i<INPUTS;i++)admit({gates:[],out:i});
      for(let a=0;a<INPUTS;a++)for(let b=a;b<INPUTS;b++)for(const op of OPS)
        admit({gates:[{op,a,b}],out:INPUTS});
      while(seen.size<CAP&&proposals<MAX_PROPOSALS){
        const ordered=[...seen.values()].sort((x,y)=>x.score+LAMBDA*x.graph.gates.length-y.score-LAMBDA*y.graph.gates.length||x.graph.gates.length-y.graph.gates.length||graphKey(x.graph).localeCompare(graphKey(y.graph)));
        const sigs=new Set(),beam=[];
        for(const entry of ordered)if(!sigs.has(entry.signature)){
          sigs.add(entry.signature);beam.push(entry.graph);if(beam.length>=BEAM)break;
        }
        admit(mutate(beam[rand(r,beam.length)],r));
      }
    }else throw Error("bad arm");
    const ordered=[...seen.values()].sort((x,y)=>x.score+LAMBDA*x.graph.gates.length-y.score-LAMBDA*y.graph.gates.length||x.graph.gates.length-y.graph.gates.length||graphKey(x.graph).localeCompare(graphKey(y.graph)));
    const shortlist=ordered.slice(0,SHORTLIST);
    const finalists=shortlist.map(e=>{
      const v=evaluate(e.graph,validPts);
      return {...e,validation:v.error,rank:v.error+LAMBDA*e.graph.gates.length};
    }).sort((a,b)=>a.rank-b.rank||a.graph.gates.length-b.graph.gates.length||graphKey(a.graph).localeCompare(graphKey(b.graph)));
    const winner=finalists[0];
    const testError=evaluate(winner.graph,test,flipHoldout).error;
    return {task,seed,arm,train_error:winner.score,validation_error:winner.validation,test_error:testError,
      exact_test:Number(testError===0),selected:winner.graph,candidates:seen.size,proposals,gate_ops:gateOps};
  }
  function bank(tasks){
    const rows=[];
    for(const task of tasks)for(let seed=0;seed<6;seed++)for(const arm of ARMS)rows.push(runCase(task,seed,arm));
    const arms={};
    for(const arm of ARMS){
      const t=rows.filter(x=>x.arm===arm),avg=k=>t.reduce((s,x)=>s+x[k],0)/t.length;
      arms[arm]={cases:t.length,accuracy:+(1-avg("test_error")).toFixed(6),
        perfect:t.reduce((s,x)=>s+x.exact_test,0),
        candidates:t.reduce((s,x)=>s+x.candidates,0),
        gate_ops:t.reduce((s,x)=>s+x.gate_ops,0),
        mean_gate_count:+(t.reduce((s,x)=>s+x.selected.gates.length,0)/t.length).toFixed(4)};
    }
    return {summary:arms,rows};
  }
  function selfTest(){
    let rejected=0;
    for(const g of [{gates:[{op:"EVAL",a:0,b:1}],out:4},{gates:[{op:"AND",a:4,b:0}],out:4},{gates:[],out:4}]){
      try{valid(g);}catch{rejected++;}
    }
    assert(rejected===3,"graph validator admits illegal candidate");
    const r=rng(31),structural=new Set();let g={gates:[],out:0};
    for(let i=0;i<500;i++){g=mutate(g,r);valid(g);structural.add(graphKey(g));}
    assert(structural.size>70,"mutations not exploring architectures");
    const one=runCase("mixed_xor",3,"evolve"),two=runCase("mixed_xor",3,"evolve"),flipped=runCase("mixed_xor",3,"evolve",true);
    assert(JSON.stringify(one)===JSON.stringify(two),"nondeterministic study");
    assert(graphKey(one.selected)===graphKey(flipped.selected)&&Math.abs(one.test_error+flipped.test_error-1)<1e-8,"holdout influenced search");
    for(const arm of ARMS) {
      const v=runCase("cross_parity",2,arm);
      assert(v.candidates<=CAP&&v.proposals<=MAX_PROPOSALS,"search exceeded limits");
    }
    const s=split("and_pairs",3);
    assert(new Set([...s.train,...s.valid,...s.test].map(x=>x.join(""))).size===16,"split overlap");
    return {checks:["invalid op/edge/output rejection","500 structural mutations","deterministic repeat","holdout label flip preserves selected architecture","bounded candidates and proposals","disjoint splits"],passed:6};
  }
  return {protocol:{id:"ACE-R3-JS-PILOT-v1",inputs:INPUTS,max_gates:MAX_GATES,candidates_per_search:CAP,
    max_proposals:MAX_PROPOSALS,beam:BEAM,shortlist:SHORTLIST,regularizer:LAMBDA,
    train_validation_test:[8,4,4],seeds:6,closed_ops:OPS,
    note:"author-visible synthetic tasks; not independent evidence, no arbitrary code execution"},
    tests:selfTest(),development:bank(DEV),confirmation:bank(CONFIRM)};
};
if (typeof module !== "undefined") {
  module.exports = {r3Study};
  if (require.main === module) process.stdout.write(JSON.stringify(r3Study(),null,2)+"\n");
}
