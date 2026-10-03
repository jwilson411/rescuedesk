'use strict';
const assert=require('node:assert/strict');
const RecoveryPlan=require('../recovery_plan.js');
const base=()=>({run:'synthetic-test-run',version:0,preview:'a'.repeat(64),blocked:false,cancelled:false,allowed:['1','2','3'],statuses:{'1':'MISSING','2':'MISSING','3':'MISSING'}});
let tested=0; function test(name,fn){fn();tested++;console.log('PASS '+name);}
test('preparation and discard never produce an execution request',()=>{const p=new RecoveryPlan();p.observe(base());assert.equal(p.takeRequest(),null);assert.equal(p.count,1);assert.deepEqual(p.prepare().effects,['1']);p.discard();assert.equal(p.takeRequest(),null);assert.equal(p.canPrepare,true);});
test('only reviewed prefix is requested and each plan is consumed once',()=>{const p=new RecoveryPlan();p.observe(base());p.choose(2);p.prepare();assert.deepEqual(p.takeRequest(),{preview:'a'.repeat(64),effects:['1','2']});assert.equal(p.takeRequest(),null);assert.equal(p.canPrepare,false);});
test('stepwise recovery defaults to next remaining effect',()=>{const p=new RecoveryPlan();const r=base();r.allowed=['2','3'];r.statuses['1']='VERIFIED';r.version=1;p.observe(r);assert.deepEqual(p.prepare().effects,['2']);});
test('changing selection invalidates prior plan',()=>{const p=new RecoveryPlan();p.observe(base());p.prepare();p.choose(3);assert.equal(p.takeRequest(),null);assert.deepEqual(p.prepare().effects,['1','2','3']);});
test('invalid selections cannot fall back to an old plan',()=>{for(const value of [0,4,-1,1.5,NaN,'2']){const p=new RecoveryPlan();p.observe(base());p.prepare();p.choose(value);assert.equal(p.takeRequest(),null);assert.equal(p.prepare(),null);}});
test('fresh observation invalidates prior review even if unchanged',()=>{const p=new RecoveryPlan();p.observe(base());p.prepare();p.observe(base());assert.equal(p.takeRequest(),null);});
test('cancelled conflict and UNKNOWN reports invalidate all plans',()=>{for(const mutate of [r=>r.cancelled=true,r=>r.blocked=true,r=>r.statuses['1']='CONFLICT',r=>r.statuses['1']='UNKNOWN',r=>delete r.preview]){const p=new RecoveryPlan();p.observe(base());p.prepare();const r=base();mutate(r);p.observe(r);assert.equal(p.canPrepare,false);assert.equal(p.takeRequest(),null);}});
test('malformed or noncontiguous allowed selections fail closed',()=>{for(const allowed of [[],['2'],['1','3'],['3','2'],['1','1'],['4'],['1','2','3','4']]){const p=new RecoveryPlan();const r=base();r.allowed=allowed;p.observe(r);assert.equal(p.canPrepare,false);}});
test('external report and returned plan mutations do not change prepared request',()=>{const p=new RecoveryPlan(),r=base();p.observe(r);r.allowed[0]='3';r.preview='b'.repeat(64);const plan=p.prepare();plan.effects[0]='3';plan.preview='b'.repeat(64);assert.deepEqual(p.takeRequest(),{preview:'a'.repeat(64),effects:['1']});});
test('error token change or refresh invalidation clears plans',()=>{const p=new RecoveryPlan();p.observe(base());p.prepare();p.invalidate();assert.deepEqual(p.choices,[]);assert.equal(p.takeRequest(),null);});
console.log(tested+' bounded presentation-state tests passed; no browser or network used.');
