import test from 'node:test';
import assert from 'node:assert/strict';
import {checks,makeBank,queryOrder,label,episode,fit,freezeAll,scoreFrozen} from './v4_study.mjs';

test('v4: deterministic, disjoint, bounded bank and no fit leakage',()=>{
 const out=checks(); assert.equal(out.pass,true);assert.equal(out.masks,146);
});
test('v4: blind same-order target purchases and no duplicate labels',()=>{
 const task=makeBank(907).validation[0],query=queryOrder(907);
 for(const arm of ['scratch','nearest','reptile','fixed_diag','joint_finetune','untrained_conditioned','learned_conditioned']){
 const e=episode(task,arm,907,{lr:0.25,beta:[.5,1,-.5],diag:[.7,1,1.4]});
 assert.deepEqual(e.purchases,query);assert.equal(e.work.grad_steps,arm==='nearest'?0:8);
 }
});
test('v4: conditional update depends on observed label history',()=>{
 const taskA={family:'manually-designed',id:0,mask:0x55555555};
 const taskB={family:'manually-designed',id:0,mask:0x0f0f0f0f};
 const cfg={lr:0.3,beta:[0.8,-0.5,1.1]};
 const a=episode(taskA,'learned_conditioned',907,cfg),b=episode(taskB,'learned_conditioned',907,cfg);
 assert.notDeepEqual(a.by_k[8],b.by_k[8]);assert.ok(a.work.conditioner_ops>0);
});
test('v4: source/validation fitting deterministic and novel OOD ignored',()=>{
 const b=makeBank(907);const f=fit(b,907);
 assert.deepEqual(f,fit({train:b.train,validation:b.validation,ood:new Proxy([],{get(){throw Error('leak')}})},907));
});
test('v4: integrity fails closed on mutated freeze record',()=>{
 const freeze=freezeAll();freeze.per_seed[0].fit.learned.beta[0]+=.5;
 assert.throws(()=>scoreFrozen(freeze),/fit integrity/);
});
test('v4: OOD task families distinct from source and validation',()=>{
 const b=makeBank(907),f=new Set([...b.train,...b.validation].map(t=>t.family));
 assert.ok(b.ood.every(t=>!f.has(t.family)));
 assert.ok(b.ood.every(t=>Array.from({length:32},(_,x)=>label(t,x)).reduce((a,z)=>a+z,0)>=5));
});
