/* Source-rate protocol validation and exact C/Wasm command replay.
 * Fixture measurements below test definitions, not biological behavior.
 * node flyos/tests/test_rate_reference_protocol.cjs path/to/flyos-rate-reference.wasm
 */
'use strict';
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const filename=path.resolve(__dirname,'../tools/interaction_lab_rate_reference_protocol.js');
assert.ok(fs.existsSync(filename),'source-rate protocol runner exists');
const R=require(filename);
const metadata=JSON.parse(fs.readFileSync(path.resolve(__dirname,'../sim/circuit_models.json'),'utf8')).models.find(m=>m.id===1);
const zero=Array(60).fill(0);
assert.equal(R.SAMPLE_MS,5);assert.equal(R.MAX_MS,6000);
assert.deepEqual(R.configuration({}),R.DEFAULTS);
for(const value of [null,[],42])assert.throws(()=>R.configuration(value),/config/i);
for(const config of [{unknown:1},{warmupMs:1},{warmupMs:0},{perturbMs:6000},{cue:201},{drive:-201},{baseAngle:360},{baseAngle:1.2},{protocol:'unknown'},{cue:NaN}])assert.throws(()=>R.configuration(config));
const getter={};Object.defineProperty(getter,'cue',{get(){throw Error('must not execute');},enumerable:true});assert.throws(()=>R.configuration(getter),/value/i);
let measured=R.analyze(zero,metadata);assert.equal(measured.vectorAngleDegrees,null);assert.equal(measured.vectorCoherence,null);assert.equal(measured.epgRms,0);
let signed=[...zero];signed[34]=-4;signed[42]=4;signed[43]=-4;signed[51]=4;
measured=R.analyze(signed,metadata);assert.equal(measured.sectorMeans[0],0);assert.ok(measured.epgRms>0);assert.equal(measured.positiveSectorMeans[0],2);assert.equal(measured.vectorAngleDegrees,0,'rectify individual units before duplicate-sector averaging');
let directed=[...zero];directed[36]=2;directed[45]=2;
measured=R.analyze(directed,metadata);assert.ok(Math.abs(measured.vectorAngleDegrees-90)<1e-10);assert.equal(measured.vectorCoherence,1);
let uniform=[...zero];for(let i=34;i<52;i++)uniform[i]=1;
assert.equal(R.analyze(uniform,metadata).vectorAngleDegrees,null,'uniform positive activity has no direction');
let invalid=JSON.parse(JSON.stringify(metadata));invalid.units[34].cue_angle_degrees=45;assert.throws(()=>R.analyze(zero,invalid),/sector/i);
assert.throws(()=>R.analyze(Array(59).fill(0),metadata),/state/i);assert.throws(()=>R.analyze(Array(60),metadata),/state/i);assert.throws(()=>R.analyze([...zero.slice(0,59),NaN],metadata),/state/i);
(async()=>{
  assert.ok(process.argv[2],'a real source-rate Wasm path is required for execution tests');
  const module=new WebAssembly.Module(fs.readFileSync(process.argv[2]));
  const config={warmupMs:10,perturbMs:20,recoveryMs:10};
  const result=await R.run(module,metadata,config);
  assert.equal(result.control.frames.length,9);assert.equal(result.treatment.frames.length,9);
  assert.deepEqual(result.control.frames.slice(0,3),result.treatment.frames.slice(0,3));
  assert.equal(result.phases[1].endIndex,2);assert.equal(result.phases[2].endIndex,6);
  for(const arm of [result.control,result.treatment]){
    const api=new WebAssembly.Instance(module).exports;let at=0;
    for(const f of arm.frames){
      while(at<f.commandCount){const [name,...args]=arm.commands[at++];api[name](...args);}
      assert.deepEqual(Array.from(new Float64Array(api.memory.buffer,api.fly_rate_state(),60)),f.neurons);
      assert.deepEqual(Array.from({length:60},(_,i)=>api.fly_rate_transfer(i)),f.transfers);
      assert.equal(api.fly_rate_epoch(),f.epoch);assert.equal(api.fly_rate_time_ms(),f.timeMs);
      assert.equal(f.epoch,f.index*50);assert.equal(f.timeMs,f.index*5);
      assert.deepEqual(R.analyze(f.neurons,metadata).sectorMeans,f.sectorMeans);
    }
    assert.equal(at,arm.commands.length);
  }
  assert.deepEqual(await R.run(module,metadata,config),result,'complete repeated runs are deterministic');
  for(const protocol of ['cue-shift','cue-drive']){
    const run=await R.run(module,metadata,{...config,protocol,drive:-100});
    assert.notDeepEqual(run.treatment.frames[6].neurons,run.control.frames[6].neurons);
    assert.equal(run.treatment.frames[3].stimulus.angle,protocol==='cue-shift'?180:90);
    assert.equal(run.treatment.frames[3].stimulus.turn,protocol==='cue-drive'?-100:0);
    assert.equal(run.treatment.frames[7].stimulus.turn,0);
  }
  const abort=new AbortController();let progress=0;
  await assert.rejects(R.run(module,metadata,{warmupMs:100,perturbMs:100,recoveryMs:100},{signal:abort.signal,onProgress(){progress++;abort.abort();}}),/cancel/i);
  assert.ok(progress>0);assert.equal(abort.signal.aborted,true);
  const before=new AbortController();before.abort();await assert.rejects(R.run(module,metadata,config,{signal:before.signal}),/cancel/i);
  await assert.rejects(R.run(new WebAssembly.Module(Uint8Array.from([0,97,115,109,1,0,0,0])),metadata,config),/export/i);
  assert.match(result.semantics.activity,/signed/i);assert.match(result.semantics.time,/model/i);assert.match(result.semantics.forcing,/synthetic/i);
  assert.equal(Object.hasOwn(result,'crossModelL1'),false);
  console.log('PASS: reference config, signed measurements, ambiguous-direction masking, exact command replay, isolated deterministic arms, protocols and cancellation. No biological validation.');
})().catch(error=>{console.error(error);process.exitCode=1;});
