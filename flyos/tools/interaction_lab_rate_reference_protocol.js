// Bounded scheduling and explicit measurements. Only C/Wasm updates neural state.
// This source-derived deterministic core is not the publication's full pipeline.
const FlyRateReference = (() => {
  'use strict';
  const SAMPLE_MS=5, MAX_MS=6000, DT_MS=0.1;
  const DEFAULTS=Object.freeze({protocol:'cue-loss',warmupMs:750,perturbMs:3250,recoveryMs:750,
    baseAngle:90,shiftAngle:180,cue:200,drive:100});
  const SOURCE_COMMIT='dfb95dfeaad0da2df0f7f687846d4df44079a483';
  const SOURCE_SHA256='abfdcb2918e3637e41d4ba7b7438e512f545dac6553ce89d5cfddb49de044b12';
  const REQUIRED_EXPORTS=['fly_rate_reset','fly_rate_set_stimulus','fly_rate_step','fly_rate_state',
    'fly_rate_transfer','fly_rate_unit_count','fly_rate_epoch','fly_rate_time_ms','fly_rate_dt_ms',
    'fly_rate_stimulus_angle','fly_rate_stimulus_cue','fly_rate_stimulus_turn'];
  function bounded(value,minimum,maximum,name,integer=false){
    if(typeof value!=='number'||!Number.isFinite(value)||value<minimum||value>maximum||(integer&&!Number.isSafeInteger(value)))
      throw Error(`Invalid ${name}: expected ${integer?'a whole number':'a number'} from ${minimum} to ${maximum}.`);
    return value===0?0:value;
  }
  function configuration(input={}){
    if(!input||typeof input!=='object'||Array.isArray(input)||
      (Object.getPrototypeOf(input)!==Object.prototype&&Object.getPrototypeOf(input)!==null))throw Error('Invalid reference config: expected a plain object.');
    for(const key of Reflect.ownKeys(input)){
      if(!Object.hasOwn(DEFAULTS,key))throw Error(`Unknown reference config field: ${String(key)}.`);
      const descriptor=Object.getOwnPropertyDescriptor(input,key);
      if(!descriptor.enumerable||!Object.hasOwn(descriptor,'value'))throw Error('Reference config fields must be enumerable values.');
    }
    const c={...DEFAULTS,...input};
    if(!['cue-loss','cue-shift','cue-drive'].includes(c.protocol))throw Error('Unknown reference protocol.');
    for(const key of ['warmupMs','perturbMs','recoveryMs']){
      c[key]=bounded(c[key],SAMPLE_MS,MAX_MS,key,true);
      if(c[key]%SAMPLE_MS)throw Error(`Reference ${key} must be a multiple of ${SAMPLE_MS} model ms.`);
    }
    if(c.warmupMs+c.perturbMs+c.recoveryMs>MAX_MS)throw Error(`Reference phases must total at most ${MAX_MS} model ms.`);
    for(const key of ['baseAngle','shiftAngle'])c[key]=bounded(c[key],0,359,key,true);
    c.cue=bounded(c.cue,0,200,'cue');c.drive=bounded(c.drive,-200,200,'drive');
    return c;
  }
  function verifiedSectors(metadata){
    if(!metadata||metadata.id!==1||metadata.key!=='pisokas-cx60'||metadata.node_count!==60||metadata.scale!==1024||
      metadata.source_commit!==SOURCE_COMMIT||metadata.source_sha256!==SOURCE_SHA256||!Array.isArray(metadata.units)||metadata.units.length!==60)
      throw Error('Reference topology metadata does not match the pinned source.');
    const map=new Map();
    metadata.units.forEach((unit,index)=>{
      const group=index<16?'P-EN':index<34?'P-EG':index<52?'E-PG':'Delta7';
      const half=index<8||(index>=16&&index<25)||(index>=34&&index<43)?'A':'B';
      if(!unit||unit.id!==index||unit.group!==group||(index<52&&unit.half!==half))throw Error('Reference metadata unit ordering mismatch.');
      if(group==='E-PG'){
        const angle=((index-34)%9)%8*45;
        if(unit.cue_angle_degrees!==angle)throw Error('Reference metadata cue-sector mismatch.');
        if(!map.has(angle))map.set(angle,[]);map.get(angle).push(index);
      }else if(Object.hasOwn(unit,'cue_angle_degrees'))throw Error('Reference sector assigned to a non E-PG unit.');
    });
    return [...map].sort((a,b)=>a[0]-b[0]).map(([angle,unitIds])=>({angle,unitIds}));
  }
  function profile(neurons,sectors){
    if(!Array.isArray(neurons)||neurons.length!==60||Array.from(neurons).some(value=>typeof value!=='number'||!Number.isFinite(value)))throw Error('Invalid signed reference state.');
    const sectorMeans=sectors.map(s=>s.unitIds.reduce((sum,id)=>sum+neurons[id],0)/s.unitIds.length);
    const positiveSectorMeans=sectors.map(s=>s.unitIds.reduce((sum,id)=>sum+Math.max(0,neurons[id]),0)/s.unitIds.length);
    const positiveMass=positiveSectorMeans.reduce((a,b)=>a+b,0);
    const x=positiveSectorMeans.reduce((sum,value,i)=>sum+value*Math.cos(sectors[i].angle*Math.PI/180),0);
    const y=positiveSectorMeans.reduce((sum,value,i)=>sum+value*Math.sin(sectors[i].angle*Math.PI/180),0);
    const vectorCoherence=positiveMass>1e-12?Math.min(1,Math.hypot(x,y)/positiveMass):null;
    let vectorAngleDegrees=vectorCoherence!==null&&vectorCoherence>1e-9?(Math.atan2(y,x)*180/Math.PI+360)%360:null;
    if(vectorAngleDegrees!==null&&Math.abs(vectorAngleDegrees-360)<1e-10)vectorAngleDegrees=0;
    const ids=sectors.flatMap(s=>s.unitIds);
    return {sectorMeans,positiveSectorMeans,positiveMass,vectorAngleDegrees,vectorCoherence,
      epgRms:Math.sqrt(ids.reduce((sum,id)=>sum+neurons[id]*neurons[id],0)/ids.length),
      epgMinimum:Math.min(...ids.map(id=>neurons[id])),epgMaximum:Math.max(...ids.map(id=>neurons[id]))};
  }
  function analyze(neurons,metadata){return profile(neurons,verifiedSectors(metadata));}
  function verifyModule(module){
    if(!(module instanceof WebAssembly.Module)||WebAssembly.Module.imports(module).length!==0)throw Error('Reference requires the import-free C/Wasm module.');
    const exports=WebAssembly.Module.exports(module);
    if(!exports.some(x=>x.name==='memory'&&x.kind==='memory')||REQUIRED_EXPORTS.some(name=>!exports.some(x=>x.name===name&&x.kind==='function')))
      throw Error('Reference C/Wasm module is missing required exports.');
  }
  function cancelled(signal){if(signal?.aborted)throw Error('Reference run cancelled.');}
  const yieldTurn=()=>new Promise(resolve=>setTimeout(resolve,0));
  async function run(module,metadata,input={},options={}){
    const config=configuration(input),sectors=verifiedSectors(metadata);verifyModule(module);cancelled(options.signal);
    const counts=[config.warmupMs,config.perturbMs,config.recoveryMs].map(ms=>ms/SAMPLE_MS);
    let end=0;
    const phases=[{name:'reset',startIndex:0,endIndex:0,startMs:0,endMs:0},...['warmup','perturb','recovery'].map((name,i)=>{
      const start=end;end+=counts[i];return {name,startIndex:start+1,endIndex:end,startMs:start*SAMPLE_MS,endMs:end*SAMPLE_MS};
    })];
    let progress=0;
    async function trial(treatment){
      const api=new WebAssembly.Instance(module).exports,commands=[],frames=[];
      if(typeof api._initialize==='function')api._initialize();
      function command(name,...args){
        const result=api[name](...args);
        if(name!=='fly_rate_reset'&&result!==1)throw Error(`Reference C rejected ${name}.`);
        commands.push([name,...args]);
      }
      function stimulus(perturb){
        const altered=treatment&&perturb;
        command('fly_rate_set_stimulus',altered&&config.protocol==='cue-shift'?config.shiftAngle:config.baseAngle,
          altered&&config.protocol==='cue-loss'?0:config.cue,altered&&config.protocol==='cue-drive'?config.drive:0);
      }
      function capture(index,phase,phaseMs){
        const neurons=Array.from(new Float64Array(api.memory.buffer,api.fly_rate_state(),60));
        const transfers=Array.from({length:60},(_,i)=>api.fly_rate_transfer(i));
        if(transfers.some(value=>!Number.isFinite(value)||value< -1||value>1))throw Error('Invalid signed transfer output.');
        const epoch=api.fly_rate_epoch(),timeMs=api.fly_rate_time_ms();
        if(epoch!==index*SAMPLE_MS/DT_MS||Math.abs(timeMs-index*SAMPLE_MS)>1e-9)throw Error('Reference model-time contract mismatch.');
        frames.push({index,phase,phaseMs,epoch,timeMs,commandCount:commands.length,neurons,transfers,
          stimulus:{angle:api.fly_rate_stimulus_angle(),cue:api.fly_rate_stimulus_cue(),turn:api.fly_rate_stimulus_turn()},...profile(neurons,sectors)});
      }
      command('fly_rate_reset');
      if(api.fly_rate_unit_count()!==60||api.fly_rate_dt_ms()!==DT_MS||api.memory.buffer.byteLength!==131072)throw Error('Reference C model contract mismatch.');
      stimulus(false);capture(0,'reset',0);
      for(const phase of phases.slice(1)){
        if(phase.name!=='warmup')stimulus(phase.name==='perturb');
        for(let index=phase.startIndex;index<=phase.endIndex;index++){
          cancelled(options.signal);command('fly_rate_step',SAMPLE_MS/DT_MS);capture(index,phase.name,(index-phase.startIndex+1)*SAMPLE_MS);progress++;
          if(progress%40===0){options.onProgress?.(progress/(2*end));await yieldTurn();cancelled(options.signal);}
        }
      }
      return {commands,frames};
    }
    const control=await trial(false),treatment=await trial(true);cancelled(options.signal);
    return {schema:1,config,model:{key:'pisokas-source-rate-reference',unit_count:60,source_commit:SOURCE_COMMIT,topology_matrix_sha256:SOURCE_SHA256,
      dynamics:'Deterministic signed tanh rate-core reference',dtMs:DT_MS,tauMs:20,noise:false},sectors,phases,control,treatment,
      semantics:{activity:'neurons contains all 60 signed dimensionless u=100(V−V0) states. transfers contains signed tanh(u). Neither is Hz or measured firing rate.',
        time:'timeMs is physical model time from the source electrical parameters, with 0.1 ms Euler updates. This is not calibrated fly or watch timing.',
        samples:'Reset is sample 0. Later snapshots follow 50 C updates, every 5 model ms. Brief events between saved samples are not resolved.',
        profile:'sectorMeans averages signed E-PG u by source cue sector. Sector 0 averages four units; each other sector averages two. No negative clipping in this profile.',
        direction:'positiveSectorMeans rectifies each E-PG u before duplicate-sector averaging. vectorAngleDegrees is its circular direction at 0,45,…315 degrees; unavailable when mass≤1e-12 or normalized resultant≤1e-9. This is a separate display convention, not the source P-EN-A decoder or a calibrated heading. vectorCoherence is normalized resultant, not confidence.',
        amplitude:'epgRms is the root mean square of all 18 signed E-PG units. Nonzero amplitude or a stable direction does not establish heading memory.',
        forcing:'Synthetic triangular E-PG cue with 90-degree half-width and direct normalized rate-equivalent input, not Hz. The source centered 100 ms / global-maximum normalized spike-input pipeline and Gaussian noise are omitted.',
        drive:'Positive drive targets P-EN A indices 0–7; negative targets P-EN B indices 8–15. Sign is not a validated physical turning direction.',
        replay:'Replay each arm commands through frame.commandCount (exclusive) to recover that exact C snapshot. Control and treatment use separate Wasm memories.',
        comparison:'Compare paired arms within this reference. The separate fixed-point CX60 baseline uses abstract steps and raw Q10 counts. Phase correspondence is not time, input-amplitude or activity equivalence.'}};
  }
  return Object.freeze({DEFAULTS,SAMPLE_MS,MAX_MS,configuration,analyze,verifyModule,run});
})();
if(typeof module!=='undefined'&&module.exports)module.exports=FlyRateReference;
