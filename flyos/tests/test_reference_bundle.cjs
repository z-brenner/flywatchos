/* Actual generated dual-Wasm integration. Stub canvas/DOM is not browser QA. */
'use strict';
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {JSDOM,VirtualConsole,ResourceLoader}=require(path.resolve(process.argv[3]));
const html=fs.readFileSync(process.argv[2],'utf8');
const marker='<script id="lab-data" type="application/json">';
const raw=html.split(marker)[1].split('</script>')[0],data=JSON.parse(raw);
class NoNetwork extends ResourceLoader{fetch(url){throw Error('Unexpected network resource '+url);}}
async function until(test,label){const end=Date.now()+30000;while(!test()){if(Date.now()>end)throw Error(label);await new Promise(r=>setTimeout(r,10));}}
function makeDom(kind='ready'){
  let release,blob,download;const gate=new Promise(r=>{release=r;});const errors=[],timers=new Map();let timer=0;
  const vc=new VirtualConsole();vc.on('jsdomError',e=>errors.push(e.message));
  const refBytes=Buffer.from(data.rate_reference_wasm||'','base64');
  const modified={...data};if(kind==='missing')delete modified.rate_reference_wasm;
  const content=kind==='missing'?html.replace(raw,JSON.stringify(modified).replaceAll('<','\\u003c')):html;
  const waitReference=async bytes=>{if(bytes?.byteLength===refBytes.length){if(kind==='delayed')await gate;if(kind==='rejected')throw Error('Deliberate reference rejection');}};
  const dom=new JSDOM(content,{runScripts:'dangerously',resources:new NoNetwork(),virtualConsole:vc,beforeParse(w){
    w.WebAssembly={Memory:WebAssembly.Memory,Module:WebAssembly.Module,Instance:WebAssembly.Instance,
      compile:async bytes=>{await waitReference(bytes);return WebAssembly.compile(bytes);},
      instantiate:async(...args)=>{await waitReference(args[0]);return WebAssembly.instantiate(...args);}};
    w.matchMedia=()=>({matches:true});w.HTMLCanvasElement.prototype.getContext=()=>({createImageData:()=>({data:new Uint8ClampedArray(240*240*4)}),putImageData:()=>{}});
    w.HTMLCanvasElement.prototype.toDataURL=()=> 'data:image/png;base64,AA==';w.HTMLElement.prototype.setPointerCapture=()=>{};
    w.setInterval=fn=>{const id=++timer;timers.set(id,fn);return id;};w.clearInterval=id=>timers.delete(id);
    w.URL.createObjectURL=value=>{blob=value;return 'blob:test';};w.URL.revokeObjectURL=()=>{};
    w.HTMLAnchorElement.prototype.click=function(){download=this.download;};
  }});
  return {dom,w:dom.window,d:dom.window.document,release,errors,timers,getBlob:()=>blob,getDownload:()=>download};
}
(async()=>{
  assert.ok(data.rate_reference_wasm,'real reference artifact must be bundled');
  const {w,d,errors,timers,getBlob,getDownload}=makeDom(),$=id=>d.getElementById(id),ev=code=>w.eval(code);
  try{
    await until(()=>!$('reference-mode').disabled,'both real modules failed to initialize');
    const originalLive=ev('Array.from(new Uint8Array(labEngine.memory.buffer)).join(",")');
    $('reference-mode').click();assert.equal(d.body.dataset.lens,'reference');assert.equal(timers.size,0);
    $('reference-run').click();await until(()=>!$('reference-export').disabled,'real comparison did not complete');
    const saved=JSON.parse(ev('JSON.stringify(referenceExportData())'));
    assert.equal(saved.scope,'host-only-reference-comparison');
    assert.equal(saved.reference.config.baseAngle,90);assert.equal(saved.reference.config.protocol,'cue-loss');
    assert.equal(saved.reference.control.frames.length,951);assert.equal(saved.baseline.control.frames.length,161);
    assert.deepEqual(saved.reference.control.frames.slice(0,151),saved.reference.treatment.frames.slice(0,151));
    assert.equal(ev('Array.from(new Uint8Array(labEngine.memory.buffer)).join(",")'),originalLive,'reference experiments never mutate live state');
    const end=saved.reference.treatment.frames[800],start=saved.reference.treatment.frames[150];
    assert.equal(end.timeMs,4000);assert.equal(end.epoch,40000);assert.ok(end.epgRms>0);
    assert.ok(Math.abs(start.vectorAngleDegrees-90.217)<.002);
    assert.ok(Math.abs(end.vectorAngleDegrees-155.564)<.002,'reference reveals source-core directional drift');
    assert.ok(end.neurons.some(x=>x<0),'negative states survive capture');
    assert.match($('reference-observation').textContent,/drift|direction/i);
    assert.equal(saved.artifact_provenance.rate_reference_wasm_sha256,data.rate_reference_wasm_sha256);
    assert.equal(saved.artifact_provenance.rate_reference_protocol_sha256,data.rate_reference_protocol_sha256);
    assert.deepEqual(saved.artifact_provenance.rate_reference_wasm_manifest,data.rate_reference_wasm_manifest);
    assert.equal(saved.artifact_provenance.rate_reference_wasm_manifest_sha256,data.rate_reference_wasm_manifest_sha256);
    const module=new WebAssembly.Module(Buffer.from(data.rate_reference_wasm,'base64'));
    for(const arm of [saved.reference.control,saved.reference.treatment]){
      const api=new WebAssembly.Instance(module).exports;api._initialize();let at=0;
      for(const frame of arm.frames){
        while(at<frame.commandCount){const [name,...args]=arm.commands[at++];api[name](...args);}
        assert.deepEqual(Array.from(new Float64Array(api.memory.buffer,api.fly_rate_state(),60)),frame.neurons);
        assert.deepEqual(Array.from({length:60},(_,i)=>api.fly_rate_transfer(i)),frame.transfers);
      }
      assert.equal(at,arm.commands.length);
    }
    $('reference-export').click();assert.match(getDownload(),/\.json$/);
    const downloaded=JSON.parse(await new Promise((resolve,reject)=>{const reader=new w.FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=reject;reader.readAsText(getBlob());}));
    assert.deepEqual(downloaded,saved,'actual download is the completed run');
    const svg=w.referenceFigureSvg();assert.match(svg,/model ms/);assert.match(svg,/abstract steps/);assert.doesNotMatch(svg,/NaN|Infinity/);
    const figure=new w.DOMParser().parseFromString(svg,'image/svg+xml');
    assert.equal(figure.querySelector('parsererror'),null,'exported figure must be valid XML');
    assert.ok(figure.querySelector('text.reference-figure-title'),'export title has explicit CSS typography');
    assert.ok([...figure.querySelectorAll('[data-negative]')].every(rect=>rect.getAttribute('shape-rendering')==='crispEdges'),'heatmap cells avoid antialias striping');
    $('reference-protocol').value='cue-shift';$('reference-protocol').dispatchEvent(new w.Event('change',{bubbles:true}));
    assert.deepEqual(JSON.parse(ev('JSON.stringify(referenceExportData())')),saved,'draft input cannot relabel an export');
    $('reference-run').click();$('reference-cancel').click();await until(()=>!$('reference-run').disabled,'cancel failed');
    assert.deepEqual(JSON.parse(ev('JSON.stringify(referenceExportData())')),saved,'cancel preserves completed evidence');
    $('reference-protocol').value='cue-shift';$('reference-protocol').dispatchEvent(new w.Event('change',{bubbles:true}));
    $('reference-run').click();await until(()=>!$('reference-run').disabled,'cue shift did not complete');
    let shifted=JSON.parse(ev('JSON.stringify(referenceExportData())'));
    assert.equal(shifted.reference.treatment.frames[151].stimulus.angle,180);
    assert.equal(shifted.baseline.treatment.frames[33].stimulus.angle,180);
    $('reference-protocol').value='cue-drive';$('reference-protocol').dispatchEvent(new w.Event('change',{bubbles:true}));
    $('reference-drive-sign').value='-1';$('reference-drive-sign').dispatchEvent(new w.Event('change',{bubbles:true}));
    $('reference-run').click();await until(()=>!$('reference-run').disabled,'drive comparison did not complete');
    let driven=JSON.parse(ev('JSON.stringify(referenceExportData())'));
    assert.equal(driven.reference.treatment.frames[151].stimulus.turn,-100);
    assert.equal(driven.baseline.treatment.frames[33].stimulus.turn,-768);
    $('reference-run').click();$('experiments-mode').click();await new Promise(r=>setTimeout(r,25));
    assert.equal(d.body.dataset.lens,'experiments');assert.deepEqual(JSON.parse(ev('JSON.stringify(referenceExportData())')),driven);
    $('reference-mode').click();
    $('reference-run').click();$('anatomy-mode').click();await new Promise(r=>setTimeout(r,25));
    assert.equal(d.body.dataset.lens,'anatomy');assert.deepEqual(JSON.parse(ev('JSON.stringify(referenceExportData())')),driven);
    $('live-mode').click();assert.equal(ev('liveMode'),true);assert.equal(ev('Array.from(new Uint8Array(labEngine.memory.buffer)).join(",")'),originalLive);
    assert.deepEqual(errors,[]);
  }finally{w.close();}
  for(const kind of ['missing','delayed','rejected']){
    const h=makeDom(kind),$=id=>h.d.getElementById(id);
    try{
      await until(()=>!$('live-mode').disabled,'baseline unavailable during reference fallback');
      assert.equal($('reference-mode').disabled,true);
      $('anatomy-mode').click();assert.equal(h.d.body.dataset.lens,'anatomy');
      if(kind==='delayed'){h.release();await until(()=>!$('reference-mode').disabled,'late reference engine failed');assert.equal(h.d.body.dataset.lens,'anatomy','late module must not steal navigation');}
      assert.deepEqual(h.errors,[]);
    }finally{h.w.close();}
  }
  console.log('PASS: actual dual-Wasm comparison, all-snapshot replay, drift/negative-state evidence, artifact binding, immutable download, cancel/leave races, baseline isolation and missing/delayed/rejected reference fallback. Browser layout unverified.');
})().catch(error=>{console.error(error);process.exitCode=1;});
