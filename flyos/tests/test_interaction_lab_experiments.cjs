/* Focused DOM behavior uses an explicitly synthetic protocol result fixture.
 * It does not validate scientific results, Wasm execution, layout or screenshots.
 * Real-Wasm protocol and full-bundle lifecycle tests are separate.
 * node flyos/tests/test_interaction_lab_experiments.cjs [path/to/node_modules/jsdom]
 */
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const {JSDOM} = require(process.argv[2] ? path.resolve(process.argv[2]) : 'jsdom');
const source = path.resolve(__dirname, '../tools');
const html = fs.readFileSync(path.join(source, 'interaction_lab.html'), 'utf8').replace(/<script[\s\S]*?<\/script>/g, '');
const defaults = {protocol:'cue-shift',warmupSteps:32,perturbSteps:96,recoverySteps:32,baseAngle:0,shiftAngle:90,strength:768,drive:768};
const metadata = {id:1,key:'fixture-cx60',scale:1024,units:[],sources:[{title:'Fixture source',url:'https://example.org/source'},{title:'Unsafe source',url:'javascript:alert(1)'},{title:'HTTP source',url:'http://example.org/source'},{title:'Credential source',url:'https://someone:password@example.org/source'}]};
const frame = (index, heading, means, rawTotal=means.reduce((a,b)=>a+b,0)*2, tie=[]) => ({
  index,phase:index===0?'initial':index<=1?'warmup':index<=3?'perturbation':'recovery',phaseStep:1,commandCount:3+index,
  tick:index,model:1,node_count:60,neurons:Array(64).fill(0),stimulus:{angle:0,strength:768,turn:0},
  readout_heading:heading,readout_strength:Math.max(...means),sectorMeans:means,
  epgRawTotal:rawTotal,networkRawTotal:rawTotal,sectorActivity:means.reduce((a,b)=>a+b,0),peakStatus:'fixture',peakTieAngles:tie
});
function fixture(config) {
  const c=[frame(0,-1,Array(8).fill(0)),frame(1,0,[100,40,0,0,0,0,0,40]),frame(2,0,[100,40,0,0,0,0,0,40]),frame(3,0,[100,40,0,0,0,0,0,40]),frame(4,0,[100,40,0,0,0,0,0,40])];
  const t=[c[0],c[1],frame(2,90,[0,40,100,40,0,0,0,0]),frame(3,-1,Array(8).fill(0),2),frame(4,0,[100,100,0,0,0,0,0,0],400,[0,45])];
  return {schema:1,config:{...config},model:{id:1,key:'fixture-cx60'},sectors:Array.from({length:8},(_,i)=>({angle:i*45,unitIds:[i]})),
    phases:[{name:'warmup',startIndex:1,endIndex:1},{name:'perturbation',startIndex:2,endIndex:3},{name:'recovery',startIndex:4,endIndex:4}],
    control:{commands:[['fly_lab_reset_model',1,0],['fly_lab_step']],frames:c,finalPixels:[0]},treatment:{commands:[['fly_lab_reset_model',1,0],['fly_lab_set_stimulus',90,768,0],['fly_lab_step']],frames:t,finalPixels:[0]},
    comparisons:c.map((_,index)=>({index,profileL1:[0,0,280,180,100][index],profileL1Fraction:[null,0,.777,1,.263][index],peakSeparationDegrees:index===2?90:index===1?0:null,controlRetention:index?1:null,treatmentRetention:index===3?0.00001:index?1:null})),summary:{fixture:true}};
}
function makeDom() {
  const dom=new JSDOM(html,{runScripts:'outside-only'}),w=dom.window;
  w.data={models:[metadata],live_wasm_sha256:'a'.repeat(64),experiment_protocol_sha256:'b'.repeat(64),live_wasm_manifest_sha256:'c'.repeat(64),live_wasm_manifest:{schema:1,sha256:'a'.repeat(64),source_sha256:{'fixture.c':'d'.repeat(64)}}};w.WebAssembly=WebAssembly;
  w.eval(`var $=id=>document.getElementById(id); var liveMode=true, anatomyMode=false, labEngine=null, labModule=null, paused=0, released=0;
    function pause(){paused++;} function liveReleaseAll(){released++;} function leaveAnatomy(){anatomyMode=false;}`);
  const filename=path.join(source,'interaction_lab_experiments.js');w.eval(fs.existsSync(filename)?fs.readFileSync(filename,'utf8'):'');
  return dom;
}
(async()=>{
const dom=makeDom(),w=dom.window,d=w.document,$=id=>d.getElementById(id);
const input=id=>$(id).dispatchEvent(new w.Event('input',{bubbles:true}));
const change=id=>$(id).dispatchEvent(new w.Event('change',{bubbles:true}));
try {
  assert.equal(typeof w.enterExperiments,'function','paired experiment entry hook exists');
  assert.equal($('experiments-mode').disabled,true,'no real compiled module means no experiments');
  w.enterExperiments();assert.notEqual(d.body.dataset.lens,'experiments');
  let calls=0,lastConfig=null,fail=false;
  w.labModule=new WebAssembly.Module(Uint8Array.from([0,97,115,109,1,0,0,0]));w.labEngine={};
  w.FlyExperiment={DEFAULTS:defaults,MAX_STEPS:512,run(module,model,config){assert.equal(module,w.labModule);assert.equal(model,metadata);calls++;lastConfig={...config};if(fail)throw new Error('Fixture run failed');return fixture(config);}};
  w.experimentsRefreshAvailability();assert.equal($('experiments-mode').disabled,false);
  $('experiments-mode').click();assert.equal(d.body.dataset.lens,'experiments');
  assert.equal($('experiments-mode').getAttribute('aria-pressed'),'true');assert.equal(w.eval('liveMode'),false);assert.equal(w.released,1);assert.ok(w.paused>0);
  for(const selector of ['.workspace','.playback','.below','#live-controls'])assert.equal(d.querySelector(selector).hidden,true,selector);
  assert.equal($('experiments-lens').hidden,false);assert.equal(calls,0,'entry never silently runs');
  assert.equal($('experiments-run').disabled,false);assert.equal($('experiments-export').disabled,true);
  assert.equal($('experiments-protocol').value,'cue-shift');
  $('experiments-run').click();assert.equal(calls,1);assert.deepEqual(lastConfig,defaults);
  assert.equal($('experiments-results').hidden,false);assert.equal($('experiments-empty').hidden,true);
  assert.equal($('experiments-scrubber').max,'4');assert.equal($('experiments-scrubber').value,'3','default sample is the perturbation endpoint');assert.equal($('experiments-export').disabled,false);
  assert.equal(d.querySelectorAll('#experiment-control-bars [data-sector]').length,8);
  assert.equal(d.querySelectorAll('#experiment-treatment-bars [data-sector]').length,8);
  assert.ok(d.querySelector('#experiment-sector-chart [data-series="control"]'));
  assert.equal(d.querySelector('.experiment-plots svg').id,'experiment-difference-chart','profile divergence is the primary chart');
  assert.ok(d.querySelector('#experiment-strength-chart [data-series="treatment"]'));
  assert.ok(d.querySelector('#experiment-difference-chart [data-series="difference"]'));
  assert.doesNotMatch(d.querySelector('#experiment-sector-chart [data-series="treatment"]').getAttribute('d'),/L/,'coarse sectors are discrete steps, never interpolated headings');
  w.experimentsDrawChart('experiment-sector-chart',[{name:'control',values:[315,0,null,90,null],color:'#99e9d5'}],315,190,'Wrap and isolated peak fixture',true);
  const wrapPath=d.querySelector('#experiment-sector-chart [data-series="control"]').getAttribute('d');
  assert.equal((wrapPath.match(/M/g)||[]).length,3,'wrap and missing values break the path');
  assert.equal(d.querySelectorAll('#experiment-sector-chart [data-peak-sample]').length,3,'isolated valid peaks remain visible');
  w.experimentsDrawResults();
  $('experiments-scrubber').value='2';input('experiments-scrubber');
  assert.match($('experiment-step').textContent,/2/);assert.match($('experiment-phase').textContent,/perturb/i);
  assert.match($('experiment-control-peak').textContent,/0°/);assert.match($('experiment-treatment-peak').textContent,/90°/);
  assert.match($('experiment-profile-difference').textContent,/280/);
  assert.equal($('experiments-scrubber').getAttribute('aria-valuetext').includes('perturb'),true);
  $('experiments-next').click();assert.equal($('experiments-scrubber').value,'3');
  assert.match($('experiment-treatment-peak').textContent,/unavailable/i);
  assert.match($('experiment-treatment-state').textContent,/below integer-sector resolution/i);
  assert.doesNotMatch($('experiment-treatment-state').textContent,/silent/i,'residual raw activation is not called silent');
  assert.notEqual($('experiment-retention').textContent,'0×','tiny nonzero relative activity never rounds to exact zero');
  $('experiments-scrubber').value='0';input('experiments-scrubber');assert.match($('experiment-treatment-state').textContent,/silent/i);
  $('experiments-scrubber').value='4';input('experiments-scrubber');assert.match($('experiment-treatment-state').textContent,/tie.*lowest/i);
  assert.equal($('experiments-next').disabled,true);$('experiments-previous').click();assert.equal($('experiments-scrubber').value,'3');
  const saved=w.experimentsExportData();assert.equal(saved.control.commands[0][0],'fly_lab_reset_model');assert.equal(saved.treatment.commands[1][0],'fly_lab_set_stimulus');
  assert.equal(saved.artifact_provenance.live_wasm_sha256,'a'.repeat(64));assert.equal(saved.artifact_provenance.experiment_protocol_sha256,'b'.repeat(64));
  assert.equal(saved.model_metadata.key,'fixture-cx60');
  assert.equal(saved.artifact_provenance.live_wasm_manifest_sha256,'c'.repeat(64));
  assert.equal(saved.artifact_provenance.live_wasm_manifest.source_sha256['fixture.c'],'d'.repeat(64));
  let blob=null,filename=null;w.URL.createObjectURL=value=>{blob=value;return 'blob:test';};w.URL.revokeObjectURL=()=>{};
  w.HTMLAnchorElement.prototype.click=function(){filename=this.download;};
  $('experiments-export').click();assert.equal(filename,'flywatch-paired-cue-shift.json');assert.ok(blob);
  const exported=JSON.parse(await new Promise((resolve,reject)=>{const reader=new w.FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=reject;reader.readAsText(blob);}));
  assert.deepEqual(exported,JSON.parse(JSON.stringify(saved)),'actual download contains the committed result');
  saved.config.protocol='modified-copy';assert.equal(w.experimentsExportData().config.protocol,'cue-shift','export snapshots cannot modify the completed run');
  assert.equal(exported.config.protocol,'cue-shift');assert.equal(saved.control.frames.length,5);assert.equal(saved.comparisons.length,5);
  $('experiments-protocol').value='cue-drive';change('experiments-protocol');assert.match($('experiments-status-line').textContent,/changed.*run/i);
  assert.equal(w.experimentsExportData().config.protocol,'cue-shift','editing parameters never relabels an existing result');
  assert.equal($('experiment-shift-field').hidden,true);assert.equal($('experiment-drive-field').hidden,false);
  $('experiment-drive').value='-768';input('experiment-drive');$('experiments-run').click();assert.equal(lastConfig.drive,-768);assert.equal(lastConfig.protocol,'cue-drive');
  assert.match($('experiment-treatment-plan').textContent,/P-EN/);
  $('experiment-warmup').value='';$('experiments-run').click();assert.equal(calls,2);assert.match($('experiments-status-line').textContent,/whole number/i);
  $('experiment-warmup').value='513';$('experiments-run').click();assert.equal(calls,2);
  $('experiment-warmup').value='32';$('experiment-perturb').value='481';$('experiments-run').click();assert.equal(calls,2);assert.match($('experiments-status-line').textContent,/512/);
  $('experiment-perturb').value='96';fail=true;$('experiments-run').click();assert.match($('experiments-status-line').textContent,/Fixture run failed/);assert.equal($('experiments-run').disabled,false);
  assert.equal(w.experimentsExportData().config.protocol,'cue-drive','failed run preserves previous result with honest status');
  fail=false;$('experiment-drive').value='';$('experiment-shift-angle').value='';$('experiments-protocol').value='cue-loss';change('experiments-protocol');
  const beforeLoss=calls;$('experiments-run').click();assert.equal(calls,beforeLoss+1,'invalid hidden parameters do not block a different protocol');
  assert.equal(lastConfig.protocol,'cue-loss');assert.equal(lastConfig.drive,defaults.drive);assert.equal(lastConfig.shiftAngle,defaults.shiftAngle);
  $('experiments-protocol').value='cue-drive';change('experiments-protocol');$('experiments-run').click();
  assert.equal($('experiment-drive').closest('details').open,true,'invalid active field is revealed for correction');
  assert.equal(d.querySelectorAll('#experiments-sources a').length,1,'unsafe sources never become clickable');
  w.leaveExperiments();assert.equal($('experiments-mode').getAttribute('aria-pressed'),'false');assert.equal(d.body.dataset.lens,undefined);assert.equal($('experiments-lens').hidden,true);
  for(const selector of ['.workspace','.playback','.below'])assert.equal(d.querySelector(selector).hidden,false);
  const oldCalls=calls;$('experiments-run').click();assert.equal(calls,oldCalls,'hidden controls cannot launch a run');
  assert.equal($('experiments-mode').getAttribute('aria-pressed'),'false');
  console.log('PASS: paired experiment fixture DOM: fail-closed capability, mode isolation, default run, aligned charts, scrub, activity bars, honest residual/tie readouts, config validation, immutable export, error recovery and safe sources. Layout unverified.');
} finally {w.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
