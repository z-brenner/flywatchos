/* Actual isolated Wasm versus native C and independently derived SI fixtures. */
'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {execFileSync}=require('node:child_process');
const module_=new WebAssembly.Module(fs.readFileSync(process.argv[2]));
assert.deepEqual(WebAssembly.Module.imports(module_),[]);
const api=new WebAssembly.Instance(module_,{}).exports;
api._initialize();
assert.equal(api.memory.buffer.byteLength,131072); assert.throws(()=>api.memory.grow(1));
const native=JSON.parse(execFileSync(process.argv[3],[],{encoding:'utf8',timeout:30000}));
const oracle=JSON.parse(fs.readFileSync(path.join(__dirname,'data/rate_reference_oracle.json')));
let worst=0;
const state=()=>Array.from(new Float64Array(api.memory.buffer,api.fly_rate_state(),60));
function near(actual,expected) {
    assert.equal(actual.length,60); assert.equal(expected.length,60);
    actual.forEach((x,i)=>{
        assert(Number.isFinite(x)); const error=Math.abs(x-expected[i]); worst=Math.max(worst,error);
        assert(error<=1e-10+Math.abs(expected[i])*1e-11,`unit${i}: ${x} vs ${expected[i]}`);
    });
}
function advance(epoch) {
    while(api.fly_rate_epoch()<epoch) assert.equal(api.fly_rate_step(Math.min(1000,epoch-api.fly_rate_epoch())),1);
    assert.equal(api.fly_rate_epoch(),epoch); assert.equal(api.fly_rate_time_ms(),epoch*.1);
}
api.fly_rate_reset(); assert.equal(api.fly_rate_set_stimulus(90,200,0),1);
for (const [epoch,expected] of Object.entries(oracle.snapshots)) {
    if(Number(epoch)>7500) assert.equal(api.fly_rate_set_stimulus(90,0,0),1);
    advance(Number(epoch)); near(state(),expected); near(state(),native.snapshots[epoch]);
    state().forEach((x,i)=>assert(Math.abs(api.fly_rate_transfer(i)-Math.tanh(x))<1e-14));
}
api.fly_rate_reset();
new Float64Array(api.memory.buffer,api.fly_rate_state(),60).set(oracle.signed_initial_one_step.initial_u);
assert.equal(api.fly_rate_set_stimulus(225,80,-30),1); assert.equal(api.fly_rate_step(1),1);
near(state(),oracle.signed_initial_one_step.expected_u); near(state(),native.signed_initial_one_step);
for(const turn of [-50,50]) {
    api.fly_rate_reset(); api.fly_rate_set_stimulus(90,200,0); advance(7500);
    api.fly_rate_set_stimulus(90,0,0); advance(10000);
    api.fly_rate_set_stimulus(90,0,turn); advance(20000);
    api.fly_rate_set_stimulus(90,0,0); advance(40000);
    near(state(),oracle.turn_probes[turn].expected_u); near(state(),native.turn_probes[turn]);
}
api.fly_rate_reset(); advance(40000); assert(state().every(x=>x===0));
api.fly_rate_reset(); assert.equal(api.fly_rate_set_stimulus(90,123,-45),1); advance(100);
const saved=state();
for(const angle of [NaN,Infinity,-Infinity,-1,360,1.5]) assert.equal(api.fly_rate_set_stimulus(angle,0,0),0);
for(const cue of [NaN,Infinity,-Infinity,-1,200.1]) assert.equal(api.fly_rate_set_stimulus(0,cue,0),0);
for(const turn of [NaN,Infinity,-Infinity,-200.1,200.1]) assert.equal(api.fly_rate_set_stimulus(0,0,turn),0);
for(const steps of [NaN,Infinity,-Infinity,0,-1,.5,1001,1e30]) assert.equal(api.fly_rate_step(steps),0);
assert.deepEqual(state(),saved); assert.equal(api.fly_rate_epoch(),100);
assert.equal(api.fly_rate_stimulus_angle(),90); assert.equal(api.fly_rate_stimulus_cue(),123); assert.equal(api.fly_rate_stimulus_turn(),-45);
new Float64Array(api.memory.buffer,api.fly_rate_state(),60)[59]=NaN;
assert.equal(api.fly_rate_step(100),0); assert.equal(api.fly_rate_epoch(),100);
assert.deepEqual(state().slice(0,59),saved.slice(0,59));
api.fly_rate_reset(); assert(state().every(x=>x===0));
const other=new WebAssembly.Instance(module_,{}).exports; other.fly_rate_reset();
api.fly_rate_set_stimulus(0,200,0); api.fly_rate_step(1000);
assert(Array.from(new Float64Array(other.memory.buffer,other.fly_rate_state(),60)).every(x=>x===0));
console.log(`Reference native/Wasm/SI oracle passed; maximum absolute error ${worst}; independent instances, invalid inputs and finite signed state checked.`);
