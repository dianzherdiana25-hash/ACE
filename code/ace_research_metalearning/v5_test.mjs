import test from 'node:test';
import assert from 'node:assert/strict';
import {SEEDS,ARMS,SHA,bankForSeed,label,queryOrder,directionalStep,episode,summary,fit,freezeAll,scoreFrozen,checks} from './v5_study.mjs';

test('seven internal checks: split purity, budgets, deterministic learning, fail closed',()=>assert.equal(checks().checks,7));
test('bank family counts and split masks unique',()=>{const b=bankForSeed(SEEDS[1]);assert.equal(b.train.length,66);assert.equal(b.validation.length,32);assert.equal(b.ood.length,48);const all=[...b.train,...b.validation,...b.ood];assert.equal(new Set(all.map(t=>t.mask)).size,all.length);});
test('all arms receive same eight blind target queries',()=>{const t=bankForSeed(SEEDS[0]).ood[0],c={lr:.3,beta:[.5,-.4,.3,-.2,.1,.4]};let first;for(const arm of ARMS){const result=episode(t,arm,SEEDS[0],c);if(!first)first=result.purchases;assert.deepEqual(result.purchases,first);assert.equal(result.purchases.length,8);}});
test('target generator is repeatable across independent calls',()=>assert.equal(SHA(bankForSeed(SEEDS[2])),SHA(bankForSeed(SEEDS[2]))));
test('every label input stays within legal 32-point domain',()=>{const t=bankForSeed(SEEDS[0]).train[0];assert.throws(()=>label(t,-1),/invalid input/);assert.throws(()=>label(t,32),/invalid input/);});
test('routing is not simply a diagonal update after two labels',()=>{const {directionalStep:step}= {directionalStep};const zeros=()=>({feature_multiply:0,gradient_steps:0,route_ops:0,predictions:0,nearest_pairs:0});const w1=zeros(),w2=zeros(),plain=Array(20).fill(0),routed=plain.slice(),a={mean:[0,0,0],count:0},b={mean:[0,0,0],count:0};const beta=[1,-1,1,-1,1,-1];step(plain,a,4,1,.25,beta,'none',w1);step(routed,b,4,1,.25,beta,'conditional',w2);step(plain,a,11,0,.25,beta,'none',w1);step(routed,b,11,0,.25,beta,'conditional',w2);assert.ok(routed.some((x,i)=>Math.abs(x-plain[i])>1e-12));assert.ok(w2.route_ops>0);});
test('only acquired observations count toward performance at k4',()=>{const t=bankForSeed(SEEDS[3]).ood[0],out=episode(t,'scratch',SEEDS[3],{lr:.3});assert.ok(out.by_k[4].balanced_accuracy>=0&&out.by_k[4].balanced_accuracy<=1);assert.equal(out.work.gradient_steps,8);});
test('frozen fit cannot be changed before scoring',()=>{const f=freezeAll();f.per_seed[0].fit.directional.conditional.selected.beta[0]+=.09;assert.throws(()=>scoreFrozen(f),/fit integrity/);});
test('protocol cannot be forged',()=>{const f=freezeAll();f.primary.min_seed_wins=1;assert.throws(()=>scoreFrozen(f),/protocol mismatch/);});
test('metadata bank digests catch replacement',()=>{const f=freezeAll();f.per_seed[0].ood_sha256='0'.repeat(64);assert.throws(()=>scoreFrozen(f),/bank integrity/);});
