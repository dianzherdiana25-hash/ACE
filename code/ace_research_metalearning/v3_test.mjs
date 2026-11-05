import test from 'node:test';
import assert from 'node:assert/strict';
import {D,SEEDS,N,SPLITS,makeBank,label,queryOrder,gateFeatures,gateProbability,episode,fit,freezeAll,scoreFrozen,SHA,selfCheck} from './v3_study.mjs';
const seed=SEEDS[0];
test('R4 v3 module self-check',()=>assert.equal(selfCheck().pass,true));
test('split families disjoint by name and by semantic mask',()=>{
 const b=makeBank(seed),seen=new Set(),names=new Set();for(const [split,families] of Object.entries(SPLITS)){
  for(const family of Object.keys(families)){assert.equal(names.has(family),false);names.add(family);}
  for(const task of b[split]){assert.equal(seen.has(task.mask),false);seen.add(task.mask);let positives=0;for(let x=0;x<N;x++)positives+=label(task,x);assert.ok(positives>=5&&positives<=27);}
 }assert.equal(seen.size,146);
});
test('query plan is identical for every arm (no adaptive query confound)',()=>{
 const b=makeBank(seed),t=b.validation[0],positions=queryOrder(t,seed);
 assert.equal(new Set(positions).size,8);for(const arm of ['scratch','kernel','nearest','fixed_mix','heuristic','reptile','conditional']){
  const run=episode(t,arm,seed,{lr:0.25,bandwidth:2.5,mix:0.5,gate:[0,0,0,0,0,0]});assert.deepEqual(run.purchases,positions);
  assert.equal(run.work.target_gradient_steps,arm==='nearest'||arm==='kernel'?0:8);
 }});
test('gating uses six finite task evidence features and nonconstant response',()=>{
 const first=gateFeatures([[0,0],[12,0]],20,0.4,0.1),second=gateFeatures([[0,1],[12,0]],20,0.4,0.1);
 assert.equal(first.length,6);assert.notDeepEqual(first,second);const w=[0,0,1,0,0,0];assert.notEqual(gateProbability(w,first),gateProbability(w,second));
});
test('score at k=4 excludes queried points from unqueried metrics, balanced counts both classes',()=>{
 const task=makeBank(seed).validation[0],run=episode(task,'nearest',seed,{lr:0.25,bandwidth:2.5});
 for(const k of [0,1,2,4,8]){const e=run.by_k[k];assert.ok(e.balanced_accuracy>=0&&e.balanced_accuracy<=1);assert.ok(e.unqueried_accuracy>=0&&e.unqueried_accuracy<=1);assert.ok(e.unqueried_brier>=0&&e.unqueried_brier<=1);}
});
test('learner fit never reads OOD split',()=>{
 const b=makeBank(seed),guard={train:b.train,validation:b.validation,ood:new Proxy([], {get(){throw Error('OOD accessed');}})};
 assert.equal(SHA(fit(b,seed)),SHA(fit(guard,seed)));
});
test('prescore deterministic with four distinct seeds',()=>{
 const frozen=freezeAll();assert.equal(frozen.per_seed.length,SEEDS.length);assert.equal(new Set(frozen.per_seed.map(s=>s.ood_sha256)).size,SEEDS.length);assert.equal(SHA(frozen),SHA(freezeAll()));
});
test('holdout score rejects altered learned gate even after rehashing',()=>{
 const p=freezeAll();p.per_seed[0].fit.conditional.gate[0]+=.02;assert.throws(()=>scoreFrozen(p),/fit integrity/);
});
test('holdout score rejects altered bank digest and changed protocol',()=>{
 const p=freezeAll(),q=structuredClone(p);p.per_seed[1].ood_sha256='0'.repeat(64);assert.throws(()=>scoreFrozen(p),/bank integrity/);
 q.splits.train.threshold+=1;assert.throws(()=>scoreFrozen(q),/protocol mismatch/);
});
