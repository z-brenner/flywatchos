/* Actual bundled C/Wasm integration. jsdom + stub canvas is not browser/layout QA. */
'use strict';
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {JSDOM,VirtualConsole,ResourceLoader}=require(path.resolve(process.argv[3]));
const html=fs.readFileSync(process.argv[2],'utf8');
class NoNetwork extends ResourceLoader {fetch(url){throw new Error('unexpected resource '+url);}}
async function waitUntil(predicate,label){const end=Date.now()+10000;while(!predicate()){if(Date.now()>end)throw Error(label);await new Promise(r=>setTimeout(r,10));}}
function makeDom(kind='ready'){
  const errors=[],timers=new Map();let timerId=0,blob=null,download=null,release;
  const gate=new Promise(resolve=>{release=resolve;});const vc=new VirtualConsole();vc.on('jsdomError',e=>errors.push(e.message));
  const dom=new JSDOM(html,{runScripts:'dangerously',pretendToBeVisual:true,resources:new NoNetwork(),virtualConsole:vc,beforeParse(w){
    w.matchMedia=()=>({matches:false});
    w.WebAssembly=kind==='missing'?undefined:kind==='ready'?WebAssembly:{Memory:WebAssembly.Memory,Module:WebAssembly.Module,Instance:WebAssembly.Instance,
      instantiate:async(...args)=>{await gate;if(kind==='reject')throw new Error('deliberate test rejection');return WebAssembly.instantiate(...args);}};
    w.setInterval=fn=>{const id=++timerId;timers.set(id,fn);return id;};w.clearInterval=id=>timers.delete(id);
    w.HTMLCanvasElement.prototype.getContext=()=>({createImageData:()=>({data:new Uint8ClampedArray(240*240*4)}),putImageData:()=>{}});
    w.HTMLCanvasElement.prototype.toDataURL=()=> 'data:image/png;base64,AA==';
    w.HTMLElement.prototype.setPointerCapture=()=>{};
    w.URL.createObjectURL=value=>{blob=value;return 'blob:test';};w.URL.revokeObjectURL=()=>{};
    w.HTMLAnchorElement.prototype.click=function(){download=this.download;};
  }});
  return {dom,w:dom.window,d:dom.window.document,errors,timers,release,getBlob:()=>blob,getDownload:()=>download};
}
function readBlob(w,blob){return new Promise((resolve,reject)=>{const r=new w.FileReader();r.onload=()=>resolve(r.result);r.onerror=reject;r.readAsText(blob);});}
(async()=>{
  const {dom,w,d,errors,timers,getBlob,getDownload}=makeDom();
  const $=id=>d.getElementById(id),ev=code=>w.eval(code),click=id=>$(id).click();
  const input=id=>$(id).dispatchEvent(new w.Event('input',{bubbles:true}));
  const change=id=>$(id).dispatchEvent(new w.Event('change',{bubbles:true}));
  assert.ok($('experiments-mode'),'paired experiment lens is bundled');
  await waitUntil(()=>!$('live-mode').disabled,'real live Wasm did not initialize');
  assert.equal($('experiments-mode').disabled,false);
  $('live-model').value='0';change('live-model');
  d.querySelector('[data-key="1"]').dispatchEvent(new w.MouseEvent('pointerdown',{button:0,bubbles:true,cancelable:true}));
  click('play');assert.equal(timers.size,1);assert.equal(ev('labEngine.fly_lab_held()'),2);
  click('experiments-mode');assert.equal(ev('experimentsMode'),true);assert.equal(ev('liveMode'),false);
  assert.equal(ev('labEngine.fly_lab_held()'),0);assert.equal(timers.size,0);
  const liveMemory=ev('Array.from(new Uint8Array(labEngine.memory.buffer)).join(",")');
  assert.equal($('experiments-export').disabled,true);click('experiments-run');
  assert.equal($('experiments-export').disabled,false,$('experiments-status-line').textContent);
  let saved=JSON.parse(ev('JSON.stringify(experimentsExportData())'));
  assert.equal(saved.artifact_provenance.live_wasm_sha256,ev('data.live_wasm_sha256'));
  assert.equal(saved.artifact_provenance.live_wasm_manifest_sha256,ev('data.live_wasm_manifest_sha256'));
  assert.deepEqual(saved.artifact_provenance.live_wasm_manifest,JSON.parse(ev('JSON.stringify(data.live_wasm_manifest)')));
  assert.equal(saved.artifact_provenance.live_wasm_manifest.sha256,saved.artifact_provenance.live_wasm_sha256);
  assert.equal(saved.artifact_provenance.live_wasm_manifest.hardware_verified,false);
  assert.ok(saved.artifact_provenance.live_wasm_manifest.source_sha256['sim/cx_circuit.c']);
  assert.equal(saved.artifact_provenance.experiment_protocol_sha256,ev('data.experiment_protocol_sha256'));
  assert.equal(saved.model_metadata.source_commit,'dfb95dfeaad0da2df0f7f687846d4df44079a483');
  assert.match(saved.model_metadata.license_notice,/MIT License/);
  assert.equal(saved.config.protocol,'cue-shift');assert.equal(saved.control.frames.length,161);
  assert.deepEqual(saved.control.frames.slice(0,33),saved.treatment.frames.slice(0,33));
  assert.equal(saved.treatment.frames[36].readout_heading,90);
  assert.equal(Number($('experiments-scrubber').value),128,'default inspection highlights intervention end');
  for(const args of [{key:'ArrowRight'},{key:' ',code:'Space'},{key:'Home'},{key:'End'}])
    d.body.dispatchEvent(new w.KeyboardEvent('keydown',{...args,bubbles:true,cancelable:true}));
  assert.equal(timers.size,0);assert.equal(ev('Array.from(new Uint8Array(labEngine.memory.buffer)).join(",")'),liveMemory);
  const original=JSON.stringify(saved);
  $('experiments-protocol').value='cue-loss';change('experiments-protocol');
  assert.equal(ev('JSON.stringify(experimentsExportData())'),original,'draft controls never relabel committed results');
  click('experiments-run');saved=JSON.parse(ev('JSON.stringify(experimentsExportData())'));
  assert.equal(saved.config.protocol,'cue-loss');
  assert.deepEqual(saved.summary.firstTreatmentEpgSilence,{index:80,phaseStep:48});
  assert.deepEqual(saved.summary.firstTreatmentNetworkSilence,{index:84,phaseStep:52});
  $('experiments-scrubber').value='79';input('experiments-scrubber');
  assert.match($('experiment-treatment-state').textContent,/below integer-sector resolution/i);
  assert.doesNotMatch($('experiment-treatment-state').textContent,/silent/i);
  $('experiments-scrubber').value='80';input('experiments-scrubber');
  assert.match($('experiment-treatment-state').textContent,/silent/i);
  const model=new WebAssembly.Module(Uint8Array.from(w.atob(ev('data.live_wasm')),c=>c.charCodeAt(0)));
  click('experiments-export');assert.match(getDownload(),/\.json$/);
  const downloaded=JSON.parse(await readBlob(w,getBlob()));assert.deepEqual(downloaded,saved);
  for(const arm of [downloaded.control,downloaded.treatment]){
    const api=new WebAssembly.Instance(model).exports;let at=0;
    for(const frame of arm.frames){
      while(at<frame.commandCount){const [method,...args]=arm.commands[at++];api[method](...args);}
      assert.deepEqual(Array.from(new Int16Array(api.memory.buffer,api.fly_lab_activations(),64)),frame.neurons);
      assert.equal(api.fly_lab_epoch(),frame.index);assert.equal(api.fly_lab_readout_heading(),frame.readout_heading);
      assert.equal(api.fly_lab_readout_strength(),frame.readout_strength);
    }
    assert.equal(at,arm.commands.length);
    assert.deepEqual(Array.from(new Uint8Array(api.memory.buffer,api.fly_lab_pixels(),57600)),arm.finalPixels);
  }
  // Source comparison describes the documented default, never every custom run.
  $('experiment-perturb').value='1';input('experiment-perturb');click('experiments-run');
  let custom=JSON.parse(ev('JSON.stringify(experimentsExportData())'));
  assert.equal(custom.summary.firstTreatmentEpgSilence,null,'one loss step does not establish decay to silence');
  assert.match($('experiments-source-comparison').textContent,/documented default cue-loss configuration/i);
  assert.doesNotMatch($('experiments-source-comparison').textContent,/In our cue-loss trial/i);
  $('experiment-strength').value='0';input('experiment-strength');click('experiments-run');
  custom=JSON.parse(ev('JSON.stringify(experimentsExportData())'));
  assert.ok(custom.treatment.frames.every(frame=>frame.epgRawTotal===0),'zero-strength trial starts silent rather than decaying');
  assert.match($('experiments-source-comparison').textContent,/already-silent/i);
  $('experiment-strength').value='768';input('experiment-strength');
  $('experiment-perturb').value='96';input('experiment-perturb');
  $('experiments-protocol').value='cue-drive';change('experiments-protocol');
  $('experiment-drive').value='-768';input('experiment-drive');click('experiments-run');
  saved=JSON.parse(ev('JSON.stringify(experimentsExportData())'));
  assert.equal(saved.treatment.frames[128].readout_heading,saved.control.frames[128].readout_heading);
  assert.equal(saved.comparisons[128].profileL1,639.5,'documented default drive result');
  assert.equal(saved.comparisons[160].profileL1,14.5,'recovery retains a measurable paired difference');
  assert.ok(saved.comparisons[128].profileL1>0,'unchanged coarse peak can hide an activity-profile response');
  click('experiments-run');assert.equal(ev('JSON.stringify(experimentsExportData())'),JSON.stringify(saved),'same run is deterministic');
  assert.equal(ev('Array.from(new Uint8Array(labEngine.memory.buffer)).join(",")'),liveMemory);
  for(let i=0;i<3;i++){
    click('anatomy-mode');assert.equal(ev('experimentsMode'),false);assert.equal(ev('anatomyMode'),true);
    assert.equal($('experiments-lens').hidden,true);assert.equal(d.querySelectorAll('[data-anatomy-node]').length,56);
    click('experiments-mode');assert.equal(ev('anatomyMode'),false);assert.equal(ev('experimentsMode'),true);
    d.querySelectorAll('.scenario')[i].click();assert.equal(ev('experimentsMode'),false);assert.equal(ev('liveMode'),false);
    click('experiments-mode');click('live-mode');assert.equal(ev('experimentsMode'),false);assert.equal(ev('liveMode'),true);
    click('experiments-mode');
  }
  assert.equal(timers.size,0);assert.deepEqual(errors,[]);dom.window.close();

  for(const [kind,choice] of [['missing','anatomy'],['reject','anatomy'],['delayed','anatomy'],['delayed','replay'],
      ['delayed','play'],['delayed','scrub'],['delayed','unit']]){
    const v=makeDom(kind),$v=id=>v.d.getElementById(id);
    assert.equal($v('experiments-mode').disabled,true);v.w.enterExperiments();
    assert.equal(v.w.eval('experimentsMode'),false);
    if(choice==='anatomy')$v('anatomy-mode').click();
    else if(choice==='replay')v.d.querySelectorAll('.scenario')[2].click();
    else if(choice==='play')$v('play').click();
    else if(choice==='scrub'){$v('timeline').value='2';$v('timeline').dispatchEvent(new v.w.Event('input',{bubbles:true}));}
    else v.d.querySelectorAll('.cell')[5].click();
    v.release();
    if(kind==='delayed')await waitUntil(()=>!$v('live-mode').disabled,'delayed engine not ready');
    else await new Promise(r=>setTimeout(r,30));
    assert.equal($v('experiments-mode').disabled,kind!=='delayed');
    assert.equal(v.w.eval('liveMode'),false,'late engine never overrides explicit navigation');
    assert.equal(v.w.eval('anatomyMode'),choice==='anatomy');
    if(choice==='replay')assert.equal(v.w.eval('scenarioIndex'),2);
    if(choice==='play')assert.equal(v.timers.size,1,'deliberate replay playback survives late initialization');
    if(choice==='scrub')assert.equal(v.w.eval('frameIndex'),2,'deliberate replay sample survives late initialization');
    if(choice==='unit')assert.equal(v.w.eval('selectedNeuron'),5,'deliberate unit inspection survives late initialization');
    if(kind==='delayed'){$v('experiments-mode').click();$v('experiments-run').click();assert.equal($v('experiments-export').disabled,false);}
    assert.deepEqual(v.errors,[]);v.dom.window.close();
  }
  console.log('PASS: actual-Wasm paired bundle isolation, measured limitations, all-snapshot export replay, form/result separation, deterministic repeats, cross-lens lifecycle and delayed/missing/rejected engine handling. Browser layout unverified.');
})().catch(error=>{console.error(error);process.exit(1);});
