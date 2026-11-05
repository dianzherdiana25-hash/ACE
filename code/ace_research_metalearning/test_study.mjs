// Run: node --test test_study.mjs
import test from 'node:test';
import assert from 'node:assert/strict';
import {selfTest,makeBank,freeze,scoreFrozen,episode,sourcePrior} from './study.mjs';
test('R4 split purity, bounded oracle purchases, deterministic meta fitting',()=>{assert.equal(selfTest().checks,10);});
test('reject changed prescore task-bank digest',()=>{const f=freeze(0);f.ood_digest='tampered';assert.throws(()=>scoreFrozen(f),/bank-mismatch/);});
test('frozen transfer uses zero target samples',()=>{const b=makeBank(0);const e=episode(b.train[0],'static_transfer',0,{local:1,parity:0,block:0,global:0,explore:.4},sourcePrior(b.train));assert.equal(e.work.observations,0);});
