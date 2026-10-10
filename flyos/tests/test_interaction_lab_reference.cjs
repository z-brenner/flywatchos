/* Synthetic protocol fixtures exercise UI state, not scientific or browser results. */
'use strict';
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {JSDOM}=require(path.resolve(process.argv[2]));
const source=path.resolve(__dirname,'../tools');
const html=fs.readFileSync(path.join(source,'interaction_lab.html'),'utf8').replace(/<script[\s\S]*?<\/script>/g,'');
const defaults={protocol:'cue-loss',warmupMs:750,perturbMs:3250,recoveryMs:750,baseAngle:90,shiftAngle:180,cue:200,drive:100};
const baselineDefaults={protocol:'cue-shift',warmupSteps:32,perturbSteps:96,recoverySteps:32,baseAngle:0,shiftAngle:90,strength:768,drive:768};
const sectors=Array.from({length:8},(_,i)=>({angle:i*45,unitIds:[i]}));
function fixture(config,rate=true){
  const profiles=[[0,0,0,0,0,0,0,0],[0,1,3,1,-1,-1,-1,0],[0,0,1,2,0,-1,-1,0],[0,1,3,1,-1,-1,-1,0]];
  const frames=profiles.map((v,index)=>({index,phase:['reset','warmup','perturb','recovery'][index],timeMs:[0,750,4000,4750][index],
    neurons:Array(rate?60:64).fill(index),transfers:Array(60).fill(0),sectorMeans:rate?v:v.map(x=>Math.max(0,x)*1024),
    positiveSectorMeans:v.map(x=>Math.max(0,x)),epgRms:index?2:0,vectorAngleDegrees:index?[0,90,155.6,90][index]:null,
    vectorCoherence:index?.74:null,epgMinimum:index?-1:0,epgMaximum:index?3:0,readout_heading:index?90:-1,
    readout_strength:index?3072:0,epgRawTotal:index?6144:0,peakTieAngles:index?[90]:[]}));
  return {schema:1,config:{...config},model:{key:rate?'fixture-rate':'fixture-baseline'},sectors,
    phases:[{name:'reset',startIndex:0,endIndex:0},{name:'warmup',startIndex:1,endIndex:1},{name:'perturb',startIndex:2,endIndex:2},{name:'recovery',startIndex:3,endIndex:3}],
    control:{commands:[['reset']],frames:frames.map(f=>({...f,vectorAngleDegrees:f.index?90:null}))},
    treatment:{commands:[['reset']],frames},semantics:{fixture:true},summary:{fixture:true}};
}
const dom=new JSDOM(html,{runScripts:'outside-only'}),w=dom.window,d=w.document,$=id=>d.getElementById(id);
w.data={models:[{id:1,key:'fixture-cx60',sources:[{url:'https://example.org/source',title:'Fixture source'}]}],
  rate_reference_model:{key:'fixture-rate',source_url:'https://example.org/source-core',paper:'https://example.org/paper',sources:[{url:'https://example.org/rate',title:'Fixture rate source'},{url:'javascript:bad',title:'Unsafe'},{url:'https://a:b@example.org',title:'Credentials'}]},
  rate_reference_wasm_sha256:'a'.repeat(64),rate_reference_protocol_sha256:'b'.repeat(64),live_wasm_sha256:'c'.repeat(64)};
w.WebAssembly=WebAssembly;
w.eval(`var $=id=>document.getElementById(id), liveMode=true, anatomyMode=false, experimentsMode=false, labModule=null,labEngine=null,userLensSelected=false,paused=0,released=0;
function pause(){paused++;}function liveReleaseAll(){released++;}function leaveAnatomy(){anatomyMode=false;}function leaveExperiments(){experimentsMode=false;}`);
const file=path.join(source,'interaction_lab_reference.js');if(fs.existsSync(file))w.eval(fs.readFileSync(file,'utf8')+'\nwindow.fixtureSetReferenceModule = value => {referenceModule=value;};');
const tick=()=>new Promise(r=>setTimeout(r,0));
const input=id=>$(id).dispatchEvent(new w.Event('input',{bubbles:true}));
const change=id=>$(id).dispatchEvent(new w.Event('change',{bubbles:true}));
(async()=>{try{
  assert.equal(typeof w.enterReference,'function','reference lens entry exists');
  assert.equal($('reference-mode').disabled,true);w.enterReference();assert.notEqual(d.body.dataset.lens,'reference');
  const module=new WebAssembly.Module(Uint8Array.from([0,97,115,109,1,0,0,0]));w.labModule=module;w.labEngine={};
  let calls=0,fail=false,hold=false,resolveRun=null,lastConfig=null;
  w.FlyRateReference={DEFAULTS:defaults,run(module,meta,c,options){calls++;lastConfig={...c};if(fail)return Promise.reject(Error('Fixture failure'));if(hold)return new Promise(resolve=>{resolveRun=()=>resolve(fixture(c));});return Promise.resolve(fixture(c));}};
  w.FlyExperiment={DEFAULTS:baselineDefaults,run(module,meta,c){return fixture(c,false);}};
  w.fixtureSetReferenceModule(module);w.referenceRefreshAvailability();assert.equal($('reference-mode').disabled,false);
  $('reference-mode').click();assert.equal(d.body.dataset.lens,'reference');assert.equal(w.released,1);assert.equal(w.eval('liveMode'),false);assert.equal(w.eval('userLensSelected'),true);
  for(const selector of ['.workspace','.playback','.below','#live-controls'])assert.equal(d.querySelector(selector).hidden,true);
  assert.equal(calls,0,'entry never silently runs');assert.equal($('reference-export').disabled,true);
  $('reference-run').click();await tick();
  assert.equal(calls,1);assert.equal(lastConfig.protocol,'cue-loss');assert.equal(lastConfig.baseAngle,90);
  assert.equal($('reference-results').hidden,false);assert.equal($('reference-rate-scrubber').value,'2');assert.equal($('reference-baseline-scrubber').value,'2');
  assert.match($('reference-rate-position').textContent,/4000.*ms/i);assert.match($('reference-baseline-position').textContent,/2.*step/i);
  assert.ok(d.querySelector('#reference-rate-profile [data-zero-line]'),'signed profile shows its zero reference');
  assert.ok(d.querySelector('#reference-rate-map [data-negative="true"]'),'negative signed means are present');
  assert.match($('reference-observation').textContent,/65\.6/);assert.match($('reference-observation').textContent,/drift|direction/i);
  assert.doesNotMatch($('reference-observation').textContent,/memory proven|validates|confidence/i);
  const snapshot=JSON.stringify(w.referenceExportData());
  $('reference-protocol').value='cue-shift';change('reference-protocol');
  assert.equal(JSON.stringify(w.referenceExportData()),snapshot,'draft edits never relabel completed results');
  assert.match($('reference-status-line').textContent,/changed/i);
  $('reference-rate-scrubber').value='0';input('reference-rate-scrubber');assert.match($('reference-rate-direction').textContent,/unavailable/i);
  assert.equal($('reference-baseline-scrubber').value,'2','scrubbers remain independent');
  d.querySelector('[data-reference-phase="recovery"]').click();assert.equal($('reference-rate-scrubber').value,'3');assert.equal($('reference-baseline-scrubber').value,'3');
  $('reference-base-angle').value='';$('reference-run').click();await tick();assert.equal(calls,1);assert.equal($('reference-base-angle').getAttribute('aria-invalid'),'true');
  $('reference-base-angle').value='90';$('reference-protocol').value='cue-loss';change('reference-protocol');$('reference-shift-angle').value='';$('reference-run').click();await tick();assert.equal(calls,2,'unused invalid field is ignored');
  fail=true;$('reference-run').click();await tick();assert.match($('reference-status-line').textContent,/Fixture failure/);assert.equal($('reference-run').disabled,false);assert.ok(w.referenceExportData());fail=false;
  hold=true;const old=JSON.stringify(w.referenceExportData());$('reference-run').click();assert.equal($('reference-cancel').hidden,false);assert.equal($('reference-run').disabled,true);
  $('reference-cancel').click();assert.match($('reference-status-line').textContent,/cancel/i);resolveRun();await tick();assert.equal(JSON.stringify(w.referenceExportData()),old,'cancelled result never commits');
  $('reference-run').click();w.leaveReference();resolveRun();await tick();assert.equal($('reference-lens').hidden,true);assert.equal(JSON.stringify(w.referenceExportData()),old,'leaving lens invalidates pending result');
  const before=calls;$('reference-run').click();assert.equal(calls,before,'hidden controls cannot run');
  w.enterReference();$('reference-run').click();$('reference-base-angle').value='';input('reference-base-angle');$('reference-protocol').focus();resolveRun();await tick();assert.equal(d.activeElement,$('reference-protocol'),'completed run never focuses an invalid unrun draft');assert.equal($('reference-status-line').dataset.state,'dirty','invalid in-flight draft does not turn completed run into an error');$('reference-base-angle').value='90';input('reference-base-angle');hold=false;$('reference-run').click();await tick();assert.equal($('reference-export').disabled,false);
  const exported=w.referenceExportData();exported.reference.config.protocol='tampered';assert.equal(w.referenceExportData().reference.config.protocol,'cue-loss');
  assert.equal(w.referenceExportData().artifact_provenance.rate_reference_wasm_sha256,'a'.repeat(64));
  assert.equal(d.querySelectorAll('#reference-sources a').length,4,'safe source_url and paper links survive without sources-array dependence');
  const svg=w.referenceFigureSvg();assert.equal(new w.DOMParser().parseFromString(svg,'image/svg+xml').querySelector('parsererror'),null,'exported SVG is well-formed standalone XML');assert.match(svg,/model ms/);assert.match(svg,/abstract steps/);assert.match(svg,/signed u/);assert.doesNotMatch(svg,/NaN|Infinity/);
  let blob,download;w.URL.createObjectURL=v=>{blob=v;return 'blob:test';};w.URL.revokeObjectURL=()=>{};w.HTMLAnchorElement.prototype.click=function(){download=this.download;};
  $('reference-export').click();assert.match(download,/\.json$/);assert.ok(blob);$('reference-export-svg').click();assert.match(download,/\.svg$/);
  console.log('PASS: reference fixture DOM validates signed charts, independent axes, drift text, immutable exports, validation, cancel/leave races and safe sources. Browser layout unverified.');
}finally{w.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
