/* DOM-only unit integration: real Wasm, deterministic timers, stub canvas.
 * This is not browser rendering, pointer-device, layout or screenshot QA. */
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const {JSDOM, VirtualConsole, ResourceLoader} = require(process.argv[3] ? path.resolve(process.argv[3]) : 'jsdom');
class NoNetwork extends ResourceLoader { fetch(url) { throw new Error('unexpected resource: '+url); } }
async function waitUntil(predicate, message, timeoutMs=10000) {
  const deadline=Date.now()+timeoutMs;
  while(!predicate()) {
    if(Date.now()>=deadline) throw new Error(message);
    await new Promise(resolve=>setTimeout(resolve,10));
  }
}
(async()=>{
  const errors=[],timers=new Map();let timerId=0,exportedBlob=null,exportedName=null;
  const virtualConsole=new VirtualConsole();virtualConsole.on('jsdomError',e=>errors.push(e.message));
  const dom=new JSDOM(fs.readFileSync(process.argv[2],'utf8'),{
    runScripts:'dangerously',pretendToBeVisual:true,resources:new NoNetwork(),virtualConsole,
    beforeParse(w){
      w.WebAssembly=WebAssembly;
      w.matchMedia=()=>({matches:false});
      w.setInterval=fn=>{const id=++timerId;timers.set(id,fn);return id;};w.clearInterval=id=>timers.delete(id);
      w.HTMLCanvasElement.prototype.getContext=function(){return{createImageData:()=>({data:new Uint8ClampedArray(240*240*4)}),putImageData:()=>{}};};
      w.HTMLCanvasElement.prototype.toDataURL=()=> 'data:image/png;base64,AA==';
      w.HTMLElement.prototype.setPointerCapture=()=>{};
      w.URL.createObjectURL=blob=>{exportedBlob=blob;return 'blob:unit-test';};w.URL.revokeObjectURL=()=>{};
      w.HTMLAnchorElement.prototype.click=function(){exportedName=this.download;};
    }
  });
  const w=dom.window,d=w.document,$=id=>d.getElementById(id),ev=code=>w.eval(code);
  const click=id=>$(id).click();const input=id=>$(id).dispatchEvent(new w.Event('input',{bubbles:true}));
  const change=id=>$(id).dispatchEvent(new w.Event('change',{bubbles:true}));
  const press=(key,event='pointerdown')=>d.querySelector(`[data-key="${key}"]`).dispatchEvent(new w.MouseEvent(event,{button:0,bubbles:true,cancelable:true}));
  await waitUntil(()=>!$('live-mode').disabled,'live engine did not initialize: '+$('live-status').textContent);
  assert.equal($('live-mode').disabled,false,$('live-status').textContent);
  assert.equal(d.querySelectorAll('.scenario').length,9);
  assert.equal(ev('liveMode'),true,'bundled live engine opens the sandbox, paused');
  assert.equal(timers.size,0);
  assert.equal(ev('labEngine.fly_lab_model()'),1,'new circuit is the default, with baseline selectable');
  assert.equal(ev('labEngine.fly_lab_model_node_count()'),60);
  $('live-model').value='0';change('live-model');
  click('live-mode');
  assert.equal($('live-controls').hidden,false);
  assert.equal(ev('liveMode'),true);assert.equal(ev('live.frames.length'),1);
  const seed=ev('liveSeed'),start=ev('live.frames.at(-1).neurons[1]');
  click('burst');assert.ok(ev('live.frames.at(-1).neurons[1]')>start);
  assert.equal(ev('labEngine.fly_lab_held()'),0);
  assert.equal(ev('labEngine.fly_lab_delivered_pulse()'),18);
  click('next');assert.equal(ev('labEngine.fly_lab_delivered_pulse()'),0);
  click('movement');assert.equal(ev('labEngine.fly_lab_valid_mask()'),7);
  click('rest');assert.equal(ev('labEngine.fly_lab_valid_mask()'),0);
  // Pointer cancellation clears a held control.
  press(1);assert.equal(ev('labEngine.fly_lab_held()'),2);
  press(1,'pointercancel');assert.equal(ev('labEngine.fly_lab_held()'),0);
  // Multiple input sources on the same physical key aggregate until all release.
  const mixedKey=d.querySelector('[data-key="1"]');
  press(1);mixedKey.dispatchEvent(new w.KeyboardEvent('keydown',{code:'Space',bubbles:true,cancelable:true}));
  mixedKey.dispatchEvent(new w.KeyboardEvent('keyup',{code:'Space',bubbles:true,cancelable:true}));
  assert.equal(ev('labEngine.fly_lab_held()'),2,'pointer remains held after keyboard release');
  press(1,'pointerup');assert.equal(ev('labEngine.fly_lab_held()'),0);
  // Two pointer-held controls retain a BACK chord despite focus movement.
  press(2);press(1);assert.equal(ev('labEngine.fly_lab_route()'),1);
  press(1,'pointerup');press(2,'pointerup');
  // A keyboard hold interrupted by blur must not disable assistive activation.
  const startButton=d.querySelector('[data-key="1"]');
  startButton.focus();startButton.dispatchEvent(new w.KeyboardEvent('keydown',{code:'Space',bubbles:true,cancelable:true}));
  startButton.blur();assert.equal(ev('labEngine.fly_lab_held()'),0);
  const previousEpoch=ev('labEngine.fly_lab_epoch()');startButton.click();
  assert.equal(ev('labEngine.fly_lab_epoch()'),previousEpoch+2);
  // Modal interruption preserves both ownership and pending one-shot pulse.
  press(1);$('live-view').value='2';change('live-view');
  assert.equal(ev('labEngine.fly_lab_held()'),2);
  const before=ev('Array.from(new Uint8Array(labEngine.memory.buffer,labEngine.fly_lab_pixels(),57600)).join(",")');
  press(1,'pointerup');assert.equal(ev('labEngine.fly_lab_pulse()'),2);assert.equal(ev('labEngine.fly_lab_delivered_pulse()'),0);
  click('next');assert.equal(ev('labEngine.fly_lab_pulse()'),2);
  assert.equal(ev('Array.from(new Uint8Array(labEngine.memory.buffer,labEngine.fly_lab_pixels(),57600)).join(",")'),before);
  $('live-view').value='1';change('live-view');assert.equal(ev('labEngine.fly_lab_delivered_pulse()'),2);
  click('next');assert.equal(ev('labEngine.fly_lab_delivered_pulse()'),0);
  // Run, pause by stepping, and switch modes without leaving a timer or hold.
  click('play');assert.equal(timers.size,1);[...timers.values()][0]();
  click('next');assert.equal(timers.size,0);
  press(1);d.querySelector('.scenario').click();
  assert.equal(ev('liveMode'),false);assert.equal(ev('labEngine.fly_lab_held()'),0);assert.equal(timers.size,0);
  assert.equal($('play').textContent,'PLAY');
  click('live-mode');assert.equal(ev('liveMode'),true);
  // Window blur releases controls; the visible paused snapshot catches up.
  press(1);w.dispatchEvent(new w.Event('blur'));
  assert.equal(ev('labEngine.fly_lab_held()'),0);assert.equal(ev('live.frames.at(-1).held_mask'),0);
  // Invalid numeric entry cannot silently become a wrapped Wasm argument.
  $('live-seed').value='4294967296';click('live-reset');assert.equal(ev('liveSeed'),seed);
  $('live-seed').value=String(seed);click('live-reset');
  const baseline=ev('live.frames[0].neurons.join(",")');click('burst');click('live-reset');
  assert.equal(ev('live.frames[0].neurons.join(",")'),baseline);
  assert.throws(()=>ev('liveInteger(NaN,0,300,"test")'),/invalid test/);
  assert.throws(()=>ev('liveInteger(1.5,0,300,"test")'),/invalid test/);
  assert.throws(()=>ev('liveInteger("",0,300,"test")'),/invalid test/);
  // Ring buffer is bounded, while complete replayable input commands remain.
  for(let i=0;i<140;i++)click('next');
  assert.equal(ev('live.frames.length'),128);assert.equal(ev('live.command_history_complete'),true);
  assert.ok(ev('live.commands.length')>140);
  // Scrub uses real history without mutating the engine.
  const epoch=ev('labEngine.fly_lab_epoch()');$('timeline').value='0';input('timeline');
  assert.equal(ev('frameIndex'),0);assert.equal(ev('labEngine.fly_lab_epoch()'),epoch);
  // The actual export button includes a complete command log even after trimming.
  click('export');assert.ok(exportedBlob);
  assert.equal(exportedName,'flywatch-live-specimen.json');
  const exported=JSON.parse(await new Promise((resolve,reject)=>{
    const reader=new w.FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=reject;reader.readAsText(exportedBlob);
  }));
  assert.equal(exported.scope,'host-only');assert.equal(exported.hardware_verified,false);
  const copy=new WebAssembly.Instance(new WebAssembly.Module(Uint8Array.from(w.atob(ev('data.live_wasm')),c=>c.charCodeAt(0)))).exports;
  for(const [method,...args] of exported.scenario.commands)copy[method](...args);
  const finalNeurons=Array.from(new Int16Array(copy.memory.buffer,copy.fly_lab_activations(),64));
  assert.equal(finalNeurons.join(','),ev('Array.from(new Int16Array(labEngine.memory.buffer,labEngine.fly_lab_activations(),64)).join(",")'));
  const finalPixels=Buffer.from(new Uint8Array(copy.memory.buffer,copy.fly_lab_pixels(),57600));
  assert.equal(finalPixels.toString('hex'),ev('Array.from(new Uint8Array(labEngine.memory.buffer,labEngine.fly_lab_pixels(),57600)).map(v=>v.toString(16).padStart(2,"0")).join("")'));
  for(const name of ['route','held','active','pulse','delivered_pulse','buttons','state','epoch','view','usb','ready','valid_mask','rendered'])
    assert.equal(copy['fly_lab_'+name](),ev(`labEngine.fly_lab_${name}()`),name);
  // Switching models starts an isolated, paused session without leaking held
  // controls or assigning biological names to the abstract baseline.
  press(1);click('play');assert.equal(timers.size,1);
  $('live-model').value='1';change('live-model');
  assert.equal(timers.size,0);assert.equal(ev('labEngine.fly_lab_held()'),0);
  assert.equal(ev('live.frames.length'),1);assert.equal(ev('live.model'),1);
  assert.equal(ev('live.frames[0].node_count'),60);
  assert.equal(ev('circuitMetadata(live.frames[0]).units.length'),60);
  assert.equal(ev('circuitMetadata(live.frames[0]).edges.length'),326);
  assert.equal(d.querySelectorAll('.circuit-node').length,60);
  assert.equal(d.querySelectorAll('.cell:not([hidden])').length,60);
  assert.equal($('model-license-details').hidden,false);
  assert.match($('model-license').textContent,/MIT License/);
  assert.equal($('live-seed').disabled,true);
  assert.equal($('live-random').disabled,true);
  const inspectEpoch=ev('labEngine.fly_lab_epoch()');
  d.querySelector('[data-unit-index="34"]').dispatchEvent(new w.MouseEvent('click',{bubbles:true}));
  d.querySelector('[data-unit-index="34"]').dispatchEvent(new w.KeyboardEvent('keydown',{key:'ArrowRight',bubbles:true,cancelable:true}));
  assert.equal(ev('selectedNeuron'),35);
  assert.equal(ev('labEngine.fly_lab_epoch()'),inspectEpoch,'unit navigation does not step the model');
  const pathway=$('circuit-pathways').querySelector('button');assert.ok(pathway);pathway.click();
  assert.match($('circuit-edge-detail').textContent,/Published model strength/);
  assert.match($('circuit-edge-detail').textContent,/Implemented coefficient/);
  assert.equal(d.querySelectorAll('#model-sources a').length,3);
  assert.equal($('circuit-stimulus-controls').hidden,false);
  assert.equal(d.querySelector('.sensor-options').hidden,true);
  assert.equal(ev('live.commands[0][0]'),'fly_lab_reset_model');
  assert.equal(ev('live.commands[0][1]'),1);
  const circuitStart=ev('live.frames[0].neurons.join(",")');
  $('cue-angle').value='180';input('cue-angle');
  assert.equal(ev('labEngine.fly_lab_stimulus_angle()'),180);
  click('cue-hide');assert.equal(ev('labEngine.fly_lab_stimulus_strength()'),0);
  click('cue-return');assert.equal(ev('labEngine.fly_lab_stimulus_strength()'),768);
  click('turn-left');assert.equal(ev('labEngine.fly_lab_stimulus_turn()'),0);
  click('turn-right');assert.equal(ev('labEngine.fly_lab_stimulus_turn()'),0);
  assert.notEqual(ev('live.frames.at(-1).neurons.join(",")'),circuitStart);
  assert.equal(ev('live.frames.every(f=>f.model===1)'),true);
  assert.equal(ev('live.frames.every(f=>f.neurons.slice(60).every(value=>value===0))'),true);
  // Exact export replay includes circuit selection and every synthetic cue.
  click('export');
  const circuitExport=JSON.parse(await new Promise((resolve,reject)=>{
    const reader=new w.FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=reject;reader.readAsText(exportedBlob);
  }));
  for(const [method,...args] of circuitExport.scenario.commands)copy[method](...args);
  for(const name of ['model','model_node_count','readout_heading','readout_strength',
      'stimulus_angle','stimulus_strength','stimulus_turn','epoch'])
    assert.equal(copy['fly_lab_'+name](),ev(`labEngine.fly_lab_${name}()`),name);
  assert.equal(Array.from(new Int16Array(copy.memory.buffer,copy.fly_lab_activations(),64)).join(','),
    ev('Array.from(new Int16Array(labEngine.memory.buffer,labEngine.fly_lab_activations(),64)).join(",")'));
  assert.equal(Buffer.from(new Uint8Array(copy.memory.buffer,copy.fly_lab_pixels(),57600)).toString('hex'),
    ev('Array.from(new Uint8Array(labEngine.memory.buffer,labEngine.fly_lab_pixels(),57600)).map(v=>v.toString(16).padStart(2,"0")).join("")'));
  click('live-reset');assert.equal(ev('live.frames[0].neurons.join(",")'),circuitStart);
  const circuitEpoch=ev('labEngine.fly_lab_epoch()');
  $('live-model').value='';change('live-model');
  assert.equal(ev('labEngine.fly_lab_model()'),1);
  assert.equal(ev('labEngine.fly_lab_epoch()'),circuitEpoch);
  $('live-model').value='0';change('live-model');
  assert.equal($('circuit-stimulus-controls').hidden,true);
  assert.equal(d.querySelector('.sensor-options').hidden,false);
  assert.equal(ev('circuitMetadata(live.frames[0]).edges.length'),90);
  // Actual measured data is a static lens. Entry releases a held C control,
  // stops playback, hides activity and preserves the engine during inspection.
  press(1);click('play');assert.equal(timers.size,1);
  click('anatomy-mode');
  assert.equal(ev('anatomyMode'),true);assert.equal(ev('liveMode'),false);
  assert.equal(ev('labEngine.fly_lab_held()'),0);assert.equal(timers.size,0);
  assert.equal($('anatomy-lens').hidden,false);
  for(const selector of ['.workspace','.playback','.below','#live-controls'])
    assert.equal(d.querySelector(selector).hidden,true,selector);
  assert.equal(d.querySelectorAll('[data-anatomy-node]').length,56);
  assert.match($('anatomy-dataset-totals').textContent,/56.*762.*16,774/s);
  assert.equal(ev('data.anatomy.nodes.every(n=>typeof n.body_id==="string")'),true);
  const anatomyEpoch=ev('labEngine.fly_lab_epoch()');
  const anatomyNeurons=ev('Array.from(new Int16Array(labEngine.memory.buffer,labEngine.fly_lab_activations(),64)).join(",")');
  $('anatomy-draw').value='all';change('anatomy-draw');
  assert.equal(d.querySelectorAll('[data-anatomy-link]').length,762);
  $('anatomy-threshold').value='20';input('anatomy-threshold');
  const retained=JSON.parse(ev('JSON.stringify(data.anatomy.links.filter(e=>e.count>=20))'));
  assert.equal(d.querySelectorAll('[data-anatomy-link]').length,retained.length);
  const bigId=ev('data.anatomy.nodes.find(n=>Number(n.body_id)>4294967295).body_id');
  $('anatomy-search').value=bigId;input('anatomy-search');
  assert.equal(d.querySelectorAll('#anatomy-search-results button').length,1);
  d.querySelector('#anatomy-search-results button').click();
  assert.equal($('anatomy-cell-id').textContent,bigId);
  const selectedCell=d.querySelector('[data-anatomy-node][tabindex="0"]');
  selectedCell.dispatchEvent(new w.KeyboardEvent('keydown',{key:'ArrowRight',bubbles:true,cancelable:true}));
  for(const args of [{key:'ArrowRight'},{key:'Home'},{key:'End'},{key:' ',code:'Space'}])
    d.body.dispatchEvent(new w.KeyboardEvent('keydown',{...args,bubbles:true,cancelable:true}));
  click('anatomy-mode'); // repeated entry is idempotent
  assert.equal(ev('labEngine.fly_lab_epoch()'),anatomyEpoch);
  assert.equal(ev('Array.from(new Int16Array(labEngine.memory.buffer,labEngine.fly_lab_activations(),64)).join(",")'),anatomyNeurons);
  assert.equal(timers.size,0);
  click('anatomy-export');assert.equal(exportedName,'flywatch-measured-anatomy-visible.json');
  const anatomyExport=JSON.parse(await new Promise((resolve,reject)=>{
    const reader=new w.FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=reject;reader.readAsText(exportedBlob);
  }));
  assert.equal(anatomyExport.scope,'static-measured-anatomy');
  assert.equal(anatomyExport.nodes.length,56);
  assert.deepEqual(anatomyExport.links,retained);
  assert.equal(anatomyExport.full_supplied_totals.synapse_count_sum,16774);
  assert.equal(anatomyExport.visible_totals.synapse_count_sum,retained.reduce((n,e)=>n+e.count,0));
  assert.equal(anatomyExport.metadata.license.id,'CC-BY-4.0');
  assert.equal(anatomyExport.frames,undefined);assert.equal(anatomyExport.scenario,undefined);
  assert.equal(ev('labEngine.fly_lab_epoch()'),anatomyEpoch);
  d.querySelector('.scenario').click();
  assert.equal(ev('anatomyMode'),false);assert.equal(ev('liveMode'),false);
  assert.equal($('anatomy-lens').hidden,true);assert.equal(d.querySelector('.workspace').hidden,false);
  click('anatomy-mode');click('live-mode');
  assert.equal(ev('anatomyMode'),false);assert.equal(ev('liveMode'),true);
  assert.equal($('live-controls').hidden,false);assert.equal($('anatomy-lens').hidden,true);
  assert.equal(ev('labEngine.fly_lab_held()'),0);
  assert.equal(timers.size,0);assert.deepEqual(errors,[]);
  w.close();
  // Source-only anatomy remains useful without Wasm. A late real-Wasm load
  // must not take the user away from an anatomy lens already selected.
  for(const delayed of [false,true]){
    const variantErrors=[],vc=new VirtualConsole();vc.on('jsdomError',e=>variantErrors.push(e.message));
    let release;
    const barrier=new Promise(resolve=>{release=resolve;});
    const variant=new JSDOM(fs.readFileSync(process.argv[2],'utf8'),{
      runScripts:'dangerously',pretendToBeVisual:true,resources:new NoNetwork(),virtualConsole:vc,
      beforeParse(v){
        v.matchMedia=()=>({matches:false});
        v.WebAssembly=delayed?{Memory:WebAssembly.Memory,instantiate:async(...args)=>{await barrier;return WebAssembly.instantiate(...args);}}:undefined;
        v.HTMLCanvasElement.prototype.getContext=()=>({createImageData:()=>({data:new Uint8ClampedArray(240*240*4)}),putImageData:()=>{}});
        v.HTMLCanvasElement.prototype.toDataURL=()=> 'data:image/png;base64,AA==';
      }
    });
    const v=variant.window,vd=v.document;
    assert.equal(vd.getElementById('anatomy-mode').disabled,false);
    vd.getElementById('anatomy-mode').click();
    assert.equal(v.eval('anatomyMode'),true);
    assert.equal(v.eval('liveMode'),false);
    release();
    if(delayed) await waitUntil(()=>!vd.getElementById('live-mode').disabled,'delayed live engine did not initialize');
    assert.equal(vd.getElementById('live-mode').disabled,!delayed);
    assert.equal(v.eval('anatomyMode'),true,'async initialization preserves deliberate anatomy selection');
    assert.equal(v.eval('liveMode'),false);
    assert.equal(vd.querySelectorAll('[data-anatomy-node]').length,56);
    vd.querySelector('.scenario').click();
    assert.equal(v.eval('anatomyMode'),false);assert.equal(vd.querySelector('.workspace').hidden,false);
    if(delayed){vd.getElementById('live-mode').click();assert.equal(v.eval('liveMode'),true);}
    assert.deepEqual(variantErrors,[]);v.close();
  }
  console.log('PASS: real-Wasm controls, interruption, timers, both models, exact command replay, measured-data totals/export, anatomy isolation, repeated mode changes, no-Wasm fallback and late-engine selection. Canvas is stubbed; browser layout unverified.');
})().catch(error=>{console.error(error);process.exit(1);});
