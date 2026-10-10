// Presentation and lifecycle only. Both protocol runners own their C commands.
let referenceMode=false,referenceModule=null,referenceResult=null,referenceBusy=false;
let referenceRunId=0,referenceAbort=null;
const referenceSamples={rate:0,baseline:0},referenceScales={rate:1,baseline:1};
const referenceProtocols={
  'cue-loss':{title:'Cue off → cue restored',question:'Remove the synthetic cue from two separate models. Inspect signed state, surviving amplitude and profile drift alongside each model’s steady-cue control.'},
  'cue-shift':{title:'Cue shifts → cue restored',question:'Move the synthetic cue, then restore it. Inspect each model’s full profile and its own directional readout alongside a steady-cue control.'},
  'cue-drive':{title:'P-EN drive → drive removed',question:'Keep the cue in place and drive one P-EN half. Inspect signed profile changes without assuming physical turning, calibrated input equivalence or successful path integration.'}
};
const referenceText=(id,value)=>{$(id).textContent=String(value);};
const referenceNumber=value=>{
  if(!Number.isFinite(value))return 'unavailable';
  if(value===0)return '0';
  return Number(Math.abs(value)<.001?value.toPrecision(3):value.toFixed(3)).toString();
};
const referenceMetadata=()=>data.models?.find(model=>model.id===1);
function referenceAvailable(){
  return typeof WebAssembly!=='undefined'&&typeof WebAssembly.Module==='function'&&referenceModule instanceof WebAssembly.Module&&
    typeof labModule!=='undefined'&&labModule instanceof WebAssembly.Module&&typeof labEngine!=='undefined'&&Boolean(labEngine)&&
    typeof FlyRateReference!=='undefined'&&typeof FlyRateReference.run==='function'&&
    typeof FlyExperiment!=='undefined'&&typeof FlyExperiment.run==='function'&&Boolean(referenceMetadata())&&Boolean(data.rate_reference_model);
}
function referenceRefreshAvailability(){
  const ready=referenceAvailable();$('reference-mode').disabled=!ready;$('reference-run').disabled=!ready||referenceBusy;
  if(ready)referenceText('reference-status','Signed source-rate dynamics · separate model comparison.');
}
function referenceStatus(message,state='ready'){referenceText('reference-status-line',message);$('reference-status-line').dataset.state=state;}
function referenceUpdateDraft(changed=false){
  const protocol=$('reference-protocol').value,info=referenceProtocols[protocol];if(!info)return;
  referenceText('reference-plan-title',protocol==='cue-loss'?'When the cue disappears, what remains?':protocol==='cue-shift'?'What follows a relocated cue?':'What changes under P-EN drive?');
  referenceText('reference-question',info.question);
  $('reference-shift-field').hidden=protocol!=='cue-shift';$('reference-drive-field').hidden=protocol!=='cue-drive';
  if(changed)referenceStatus(referenceBusy?'Settings changed. The running trial still uses its captured settings.':referenceResult?
    'Settings changed. Run again to apply them; charts and exports still describe the previous completed run.':'Settings changed. Run to inspect this configuration.','dirty');
}
function referenceDraftSignature(){
  const protocol=$('reference-protocol').value;
  return JSON.stringify([protocol,$('reference-base-angle').value,protocol==='cue-shift'?$('reference-shift-angle').value:null,protocol==='cue-drive'?$('reference-drive-sign').value:null]);
}
function referenceReadConfig(){
  const protocol=$('reference-protocol').value;if(!Object.hasOwn(referenceProtocols,protocol))throw Error('Choose a supported reference protocol.');
  const config={...FlyRateReference.DEFAULTS,protocol};
  for(const [key,id]of [['baseAngle','reference-base-angle'],['shiftAngle','reference-shift-angle']]){
    const field=$(id);field.setAttribute('aria-invalid','false');
    if(key==='shiftAngle'&&protocol!=='cue-shift')continue;
    const value=Number(field.value);
    if(field.value.trim()===''||!Number.isSafeInteger(value)||value<0||value>359){field.setAttribute('aria-invalid','true');field.focus();throw Error('Enter a whole cue angle from 0 to 359 degrees.');}
    config[key]=value;
  }
  if(protocol==='cue-drive'){
    const sign=Number($('reference-drive-sign').value);if(sign!==1&&sign!==-1)throw Error('Choose P-EN half A or B.');
    config.drive=sign*Math.abs(FlyRateReference.DEFAULTS.drive);
  }
  return config;
}
function referenceShowSources(){
  $('reference-sources').replaceChildren();const seen=new Set();
  for(const metadata of [data.rate_reference_model,referenceMetadata()])for(const source of [
    ...(metadata?.sources??[]),{url:metadata?.source_url,title:'Pinned source rate equation / flyLI2.m'},
    {url:metadata?.paper,title:'Pisokas, Heinze & Webb / eLife 2020'}]){
    try{const url=new URL(source.url);if(url.protocol!=='https:'||url.username||url.password||seen.has(url.href))continue;seen.add(url.href);
      const li=document.createElement('li'),a=document.createElement('a');a.href=url.href;a.textContent=source.title||url.href;a.target='_blank';a.rel='noopener noreferrer';li.append(a);$('reference-sources').append(li);
    }catch(_){/* Invalid attribution is never made clickable. */}
  }
  referenceText('reference-provenance',[
    `Source commit: ${data.rate_reference_model?.source_commit??referenceMetadata()?.source_commit??'Not supplied'}`,
    `Reference C / Wasm SHA-256: ${data.rate_reference_wasm_sha256??'Not supplied'}`,
    `Reference protocol SHA-256: ${data.rate_reference_protocol_sha256??'Not supplied'}`,
    `Baseline C / Wasm SHA-256: ${data.live_wasm_sha256??'Not supplied'}`,
    `Baseline protocol SHA-256: ${data.experiment_protocol_sha256??'Not supplied'}`
  ].join('\n'));
}
function enterReference(){
  if(!referenceAvailable()||referenceMode)return;
  if(typeof userLensSelected!=='undefined')userLensSelected=true;
  leaveExperiments();leaveAnatomy();pause();if(liveMode)liveReleaseAll(false);liveMode=false;referenceMode=true;
  document.body.dataset.lens='reference';
  for(const selector of ['.workspace','.playback','.below','#live-controls'])document.querySelector(selector).hidden=true;
  $('reference-lens').hidden=false;$('reference-mode').setAttribute('aria-pressed','true');$('live-mode').setAttribute('aria-pressed','false');
  document.querySelectorAll('.scenario').forEach(button=>button.setAttribute('aria-pressed','false'));
  referenceText('mode-badge','SOURCE-RATE / OFFLINE');referenceText('intro-eyebrow','SOURCE EQUATION → SIGNED STATE → OBSERVED LIMITS');
  referenceText('scenario-title','A closer model. A clearer test.');
  referenceText('scenario-summary','A deterministic source-derived rate core beside the unchanged fixed-point adaptation. Inspect what survives, what shifts and where the models differ, with each clock and activity scale kept explicit.');
  referenceText('build-tag','TWO MODELS · FOUR ISOLATED C INSTANCES\nSIGNED REFERENCE · SYNTHETIC INPUTS');
  referenceText('footer-mode','OFFLINE BY CONSTRUCTION · INDEPENDENT MODEL AXES');referenceText('footer-keys','SCRUB SAVED SAMPLES · EXPORT EXACT C COMMANDS');
  referenceShowSources();
}
function referenceCancel(message='Run cancelled. Previous completed results are unchanged.'){
  if(!referenceBusy)return;
  referenceRunId++;referenceAbort?.abort();referenceAbort=null;referenceBusy=false;$('reference-cancel').hidden=true;referenceRefreshAvailability();referenceStatus(message,'cancelled');
}
function leaveReference(){
  if(!referenceMode)return;
  referenceCancel('Run cancelled on navigation. Previous completed results are unchanged.');referenceMode=false;delete document.body.dataset.lens;
  $('reference-lens').hidden=true;$('reference-mode').setAttribute('aria-pressed','false');
  for(const selector of ['.workspace','.playback','.below'])document.querySelector(selector).hidden=false;
  referenceText('intro-eyebrow','Stimulus → dynamics → readout');
  $('build-tag').replaceChildren(document.createTextNode('PORTABLE C → WEBASSEMBLY'),document.createElement('br'),document.createTextNode('SYNTHETIC INPUTS · NO DEVICE'));
  referenceText('footer-mode','OFFLINE BY CONSTRUCTION · REPLAYABLE C COMMANDS');referenceText('footer-keys','← / → STEP   SPACE PLAY   HOME / END');
}
function referenceSvg(tag,attributes={},text=null){
  const node=document.createElementNS('http://www.w3.org/2000/svg',tag);
  for(const[key,value]of Object.entries(attributes))node.setAttribute(key,String(value));if(text!==null)node.textContent=String(text);return node;
}
function referenceChartStart(svg,title,description){svg.replaceChildren(referenceSvg('title',{},title),referenceSvg('desc',{},description));}
const referenceRun=key=>key==='rate'?referenceResult.reference:referenceResult.baseline;
const referenceTime=(key,frame)=>key==='rate'?frame.timeMs:frame.index;
const referenceTimeUnit=key=>key==='rate'?'model ms':'abstract steps';
const referenceActivityUnit=key=>key==='rate'?'signed u':'raw Q10';
function referenceFrameDirection(key,frame){
  if(key==='rate')return frame.vectorAngleDegrees;
  return frame.readout_heading>=0&&frame.peakTieAngles?.length===1?frame.readout_heading:null;
}
function referenceColor(value,limit){
  const origin=[20,33,44],target=value<0?[239,177,165]:[153,233,213],amount=Math.pow(Math.min(1,Math.abs(value)/limit),.65);
  return '#'+origin.map((base,i)=>Math.round(base+(target[i]-base)*amount).toString(16).padStart(2,'0')).join('');
}
function referenceDrawMap(key){
  const run=referenceRun(key),frames=run.treatment.frames,svg=$(`reference-${key}-map`),limit=referenceScales[key];
  const left=42,right=550,top=13,row=18,width=(right-left)/frames.length;
  referenceChartStart(svg,`${key==='rate'?'Signed reference':'Fixed-point baseline'} treatment E-PG profile over ${referenceTimeUnit(key)}`,
    `Eight source cue sectors, duplicate-normalized. ${key==='rate'?'Coral is negative, dark is zero and mint is positive signed u.':'Dark is zero and mint is positive raw Q10.'} Each column is one stored sample. No spatial smoothing or normalized comparison between models.`);
  for(let sector=0;sector<8;sector++){
    frames.forEach((frame,index)=>svg.append(referenceSvg('rect',{x:(left+index*width).toFixed(3),y:top+sector*row,width:(width+.025).toFixed(3),height:row-.5,
      fill:referenceColor(frame.sectorMeans[sector],limit),'shape-rendering':'crispEdges','data-negative':frame.sectorMeans[sector]<0?'true':'false'})));
    svg.append(referenceSvg('text',{x:left-7,y:top+sector*row+12,'text-anchor':'end'},`${sector*45}°`));
  }
  for(const phase of run.phases.slice(1)){
    const x=left+(phase.endIndex+.5)/frames.length*(right-left);
    svg.append(referenceSvg('line',{x1:x,x2:x,y1:top,y2:top+row*8,stroke:'#cad5e2','stroke-opacity':'.35','stroke-dasharray':'2 3'}));
  }
  for(const i of [0,...run.phases.slice(1).map(p=>p.endIndex)]){
    const x=left+(i+.5)/frames.length*(right-left);
    svg.append(referenceSvg('text',{x,y:174,'text-anchor':i===0?'start':i===frames.length-1?'end':'middle'},referenceNumber(referenceTime(key,frames[i]))));
  }
  svg.append(referenceSvg('text',{x:right,y:191,'text-anchor':'end',class:'reference-axis-title'},referenceTimeUnit(key)));
  svg.append(referenceSvg('line',{x1:left,x2:left,y1:top,y2:top+row*8,class:'reference-cursor','data-reference-cursor':key,'data-map':'true'}));
  referenceText(`reference-${key}-scale-low`,key==='rate'?`−${referenceNumber(limit)}`:'0');referenceText(`reference-${key}-scale-high`,referenceNumber(limit));
}
function referenceDrawTrajectory(key){
  const run=referenceRun(key),svg=$(`reference-${key}-trajectory`),last=run.treatment.frames.length-1,left=42,right=550,top=13,bottom=112;
  const x=index=>left+index/Math.max(1,last)*(right-left),y=value=>bottom-value/360*(bottom-top);
  referenceChartStart(svg,key==='rate'?'Positive E-PG profile direction in the source-rate model':'Unique strongest baseline C sector',
    'Control is solid pale gray; treatment is dashed amber. Missing directions and 360-degree wraps break the line. The two models use different readout definitions.');
  for(const angle of [0,180,360]){svg.append(referenceSvg('line',{x1:left,x2:right,y1:y(angle),y2:y(angle),class:'reference-grid'}));svg.append(referenceSvg('text',{x:left-7,y:y(angle)+3,'text-anchor':'end'},`${angle}°`));}
  for(const arm of ['control','treatment']){
    let d='',previous=null;
    run[arm].frames.forEach((frame,index)=>{
      const value=referenceFrameDirection(key,frame);
      if(value===null||!Number.isFinite(value)){previous=null;return;}
      const continued=previous!==null&&Math.abs(previous-value)<=180;
      d+=continued?(key==='baseline'?`H${x(index).toFixed(2)}V${y(value).toFixed(2)} `:`L${x(index).toFixed(2)},${y(value).toFixed(2)} `):`M${x(index).toFixed(2)},${y(value).toFixed(2)} `;
      if(!continued)svg.append(referenceSvg('circle',{cx:x(index),cy:y(value),r:1.8,fill:arm==='control'?'#dbe6f0':'#f2c781','data-direction-point':arm}));previous=value;
    });
    svg.append(referenceSvg('path',{d:d.trim(),fill:'none',stroke:arm==='control'?'#dbe6f0':'#f2c781','stroke-width':1.8,'stroke-dasharray':arm==='control'?'none':'5 3','data-series':arm}));
  }
  for(const index of [0,last])svg.append(referenceSvg('text',{x:x(index),y:130,'text-anchor':index?'end':'start'},referenceNumber(referenceTime(key,run.treatment.frames[index]))));
  svg.append(referenceSvg('text',{x:right,y:144,'text-anchor':'end',class:'reference-axis-title'},referenceTimeUnit(key)));
  svg.append(referenceSvg('line',{x1:left,x2:left,y1:top,y2:bottom,class:'reference-cursor','data-reference-cursor':key}));
}
function referenceDrawProfile(key,index){
  const run=referenceRun(key),svg=$(`reference-${key}-profile`),left=42,right=540,top=15,bottom=165,max=referenceScales[key],min=key==='rate'?-max:0;
  const x=sector=>left+sector/7*(right-left),y=value=>bottom-(value-min)/(max-min)*(bottom-top);
  referenceChartStart(svg,`${referenceActivityUnit(key)} E-PG sector profiles at selected ${referenceTimeUnit(key)} sample`,
    'Control is solid pale gray with circles; treatment is dashed amber with squares. The zero line remains visible. Source cue sectors are schematic, not anatomical positions.');
  for(const value of min===0?[0,max/2,max]:[min,0,max]){
    const line=referenceSvg('line',{x1:left,x2:right,y1:y(value),y2:y(value),class:value===0?'reference-zero':'reference-grid'});
    if(value===0)line.setAttribute('data-zero-line','true');svg.append(line);svg.append(referenceSvg('text',{x:left-7,y:y(value)+3,'text-anchor':'end'},referenceNumber(value)));
  }
  for(let sector=0;sector<8;sector++)svg.append(referenceSvg('text',{x:x(sector),y:184,'text-anchor':'middle'},`${sector*45}°`));
  for(const arm of ['control','treatment']){
    const values=run[arm].frames[index].sectorMeans,color=arm==='control'?'#dbe6f0':'#f2c781';
    svg.append(referenceSvg('path',{d:values.map((v,i)=>`${i?'L':'M'}${x(i).toFixed(2)},${y(v).toFixed(2)}`).join(' '),fill:'none',stroke:color,'stroke-width':2,'stroke-dasharray':arm==='control'?'none':'6 4','data-series':arm}));
    values.forEach((value,sector)=>{
      const point=arm==='control'?referenceSvg('circle',{cx:x(sector),cy:y(value),r:2.7,fill:color}):referenceSvg('rect',{x:x(sector)-2.8,y:y(value)-2.8,width:5.6,height:5.6,fill:color});
      point.append(referenceSvg('title',{},`${arm}: ${sector*45} degrees, ${referenceNumber(value)} ${referenceActivityUnit(key)}`));svg.append(point);
    });
  }
}
function referenceSelectSample(key,index){
  if(!referenceResult)return;const run=referenceRun(key),last=run.treatment.frames.length-1;
  referenceSamples[key]=Math.max(0,Math.min(last,Number.isInteger(index)?index:0));const at=referenceSamples[key],frame=run.treatment.frames[at];
  $(`reference-${key}-scrubber`).value=at;$(`reference-${key}-scrubber`).setAttribute('aria-valuetext',`${referenceNumber(referenceTime(key,frame))} ${referenceTimeUnit(key)}, ${frame.phase}`);
  referenceText(`reference-${key}-position`,`${referenceNumber(referenceTime(key,frame))} ${referenceTimeUnit(key)}`);referenceText(`reference-${key}-phase`,frame.phase.toUpperCase());
  const direction=referenceFrameDirection(key,frame);referenceText(`reference-${key}-direction`,direction===null?'unavailable':`${referenceNumber(direction)}°`);
  referenceText(`reference-${key}-amplitude`,key==='rate'?`${referenceNumber(frame.epgRms)} u RMS`:`${referenceNumber(frame.readout_strength)} Q10`);
  referenceText(`reference-${key}-readout-note`,key==='rate'
    ?`Treatment state range: ${referenceNumber(frame.epgMinimum)} to ${referenceNumber(frame.epgMaximum)} u. ${direction===null?'No resolved positive-profile direction.':'Positive-profile direction is a display convention, not decoded heading.'}`
    :frame.epgRawTotal===0?'All raw E-PG activations are exactly zero.':frame.readout_heading<0?'Raw E-PG state remains below integer-sector resolution.':frame.peakTieAngles?.length>1?'C peak is tied; no unique sector is plotted.':'Unique strongest 45° C sector. This alone does not establish a localized heading signal.');
  document.querySelectorAll(`[data-reference-cursor="${key}"]`).forEach(line=>{
    const position=line.dataset.map?42+(at+.5)/(last+1)*508:42+at/Math.max(1,last)*508;line.setAttribute('x1',position);line.setAttribute('x2',position);
  });
  referenceDrawProfile(key,at);
}
function referencePhaseIndex(run,name){return run.phases.find(phase=>phase.name===name)?.endIndex??run.treatment.frames.length-1;}
function referenceObservations(){
  const rate=referenceResult.reference,base=referenceResult.baseline;
  const warm=rate.treatment.frames[referencePhaseIndex(rate,'warmup')],end=rate.treatment.frames[referencePhaseIndex(rate,'perturb')],control=rate.control.frames[end.index];
  const drift=warm.vectorAngleDegrees===null||end.vectorAngleDegrees===null?null:Math.abs(((end.vectorAngleDegrees-warm.vectorAngleDegrees+540)%360)-180);
  let text=`At perturbation end (${referenceNumber(end.timeMs)} model ms), treatment E-PG RMS is ${referenceNumber(end.epgRms)} u; the steady-cue control is ${referenceNumber(control.epgRms)} u. `;
  text+=drift===null?'A directional change is unavailable because an endpoint has no resolved positive-profile direction. '
    :`Its positive-profile direction changes by ${referenceNumber(drift)}° from warm-up (${referenceNumber(warm.vectorAngleDegrees)}° → ${referenceNumber(end.vectorAngleDegrees)}°). `;
  text+=rate.config.protocol==='cue-loss'?(end.epgRms>0?'Activity persists at this sampled endpoint; the directional drift must be considered separately. This does not establish reliable heading memory.':'The sampled E-PG state is zero. There is no persistent activity to interpret as memory.'):'These are within-model observations under synthetic inputs, not calibrated heading performance.';
  referenceText('reference-observation',text);
  const b=base.treatment.frames[referencePhaseIndex(base,'perturb')],c=base.control.frames[b.index];
  referenceText('reference-baseline-observation',`At perturbation end (abstract step ${b.index}), treatment C peak-sector activity is ${referenceNumber(b.readout_strength)} raw Q10; control is ${referenceNumber(c.readout_strength)}. `+
    (b.epgRawTotal===0?'All treatment E-PG activations are exactly zero. ':b.readout_heading<0?'Raw E-PG activity remains below the integer-sector readout resolution. ':`The treatment C strongest sector is ${b.readout_heading}°${b.peakTieAngles?.length>1?' (tied)':''}. `)+
    'Its activity units, clock, forcing and decoder differ from the reference. The two endpoints are corresponding protocol phases only.');
}
function referenceDrawResults(){
  for(const key of ['rate','baseline']){
    const run=referenceRun(key);referenceScales[key]=Math.max(.000001,...[...run.control.frames,...run.treatment.frames].flatMap(f=>f.sectorMeans.map(Math.abs)));
    referenceText(`reference-${key}-map-unit`,referenceActivityUnit(key).toUpperCase());referenceText(`reference-${key}-profile-unit`,referenceActivityUnit(key).toUpperCase());
    referenceText(`reference-${key}-trajectory-label`,key==='rate'?'POSITIVE E-PG PROFILE DIRECTION':'UNIQUE STRONGEST C SECTOR');
    referenceText(`reference-${key}-direction-label`,key==='rate'?'TREATMENT / POSITIVE PROFILE DIRECTION':'TREATMENT / UNIQUE C PEAK');
    referenceText(`reference-${key}-amplitude-label`,key==='rate'?'TREATMENT / SIGNED E-PG RMS':'TREATMENT / C PEAK-SECTOR ACTIVITY');
    $(`reference-${key}-scrubber`).max=run.treatment.frames.length-1;
    referenceDrawMap(key);referenceDrawTrajectory(key);referenceSelectSample(key,referencePhaseIndex(run,'perturb'));
  }
  referenceText('reference-result-title',referenceProtocols[referenceResult.reference.config.protocol].title);
  referenceText('reference-result-caption',`Applied cue ${referenceResult.reference.config.baseAngle}° · reference samples every 5 model ms · baseline samples every abstract step. Shared buttons select phase endpoints, not equal times.`);
  referenceObservations();
}
function referenceProvenance(){
  const keys=['rate_reference_wasm_sha256','rate_reference_wasm_manifest_sha256','rate_reference_wasm_manifest','rate_reference_protocol_sha256',
    'live_wasm_sha256','live_wasm_manifest_sha256','live_wasm_manifest','experiment_protocol_sha256'];
  return Object.fromEntries(keys.map(key=>[key,JSON.parse(JSON.stringify(data[key]??null))]));
}
async function referenceRunComparison(){
  if(!referenceMode||!referenceAvailable()||referenceBusy)return;
  let config;try{config=referenceReadConfig();}catch(error){referenceStatus(error.message,'error');return;}
  const draftSignature=referenceDraftSignature();
  const id=++referenceRunId;referenceBusy=true;referenceAbort=new AbortController();const signal=referenceAbort.signal;
  $('reference-cancel').hidden=false;referenceRefreshAvailability();referenceStatus('Running isolated C instances. You can cancel or leave this lens without changing the live specimen.','running');
  const baseConfig={...FlyExperiment.DEFAULTS,protocol:config.protocol,baseAngle:config.baseAngle,shiftAngle:config.shiftAngle,drive:Math.sign(config.drive)*768};
  const provenance=referenceProvenance();
  const modelMetadata={reference:JSON.parse(JSON.stringify(data.rate_reference_model)),baseline:JSON.parse(JSON.stringify(referenceMetadata()))};
  try{
    const reference=await FlyRateReference.run(referenceModule,referenceMetadata(),config,{signal,onProgress:fraction=>{
      if(id===referenceRunId&&referenceMode)referenceStatus(`Running reference · ${Math.round(fraction*100)}% of stored samples. Previous completed charts remain unchanged.`,'running');
    }});
    if(id!==referenceRunId||signal.aborted||!referenceMode)return;
    const baseline=FlyExperiment.run(labModule,referenceMetadata(),baseConfig);
    if(id!==referenceRunId||signal.aborted||!referenceMode)return;
    const next={schema:1,scope:'host-only-reference-comparison',hardware_verified:false,reference,baseline,model_metadata:modelMetadata,artifact_provenance:provenance,
      comparison_boundary:'Independent clocks, inputs, state units and decoders. Only protocol phases correspond. No cross-model raw error or biological validation is implied.'};
    // Commit only after both complete. Discarded or failed runs never leak partial snapshots.
    referenceResult=next;referenceDrawResults();$('reference-results').hidden=false;$('reference-empty').hidden=true;
    $('reference-export').disabled=false;$('reference-export-svg').disabled=false;
    const draftChanged=referenceDraftSignature()!==draftSignature;
    referenceStatus(`Completed both model pairs. Showing perturbation endpoints.${draftChanged?' Draft settings changed during the run; charts and exports use the settings captured at Run.':''}`,draftChanged?'dirty':'ready');
  }catch(error){if(id===referenceRunId&&!signal.aborted)referenceStatus(`${error.message}${referenceResult?' Previous completed results are still shown.':''}`,'error');}
  finally{if(id===referenceRunId){referenceBusy=false;referenceAbort=null;$('reference-cancel').hidden=true;referenceRefreshAvailability();}}
}
function referenceExportData(){return referenceResult?JSON.parse(JSON.stringify(referenceResult)):null;}
function referenceFigureSvg(){
  if(!referenceResult)return null;
  const figure=referenceSvg('svg',{viewBox:'0 0 1180 790',width:1180,height:790});
  figure.append(referenceSvg('title',{},'FlyWatch source-rate comparison: independently scaled C model results'),
    referenceSvg('desc',{},'Actual completed-run data. Each model has its own time and state units; the source-rate core omits noise and the original spike-input preprocessing. This is an exported data figure, not a browser screenshot.'),
    referenceSvg('rect',{width:1180,height:790,fill:'#0b1017'}));
  const style=referenceSvg('style',{},'text{font:11px monospace;fill:#aab7ca}text.reference-figure-title{font-size:18px;fill:#edf3f7}.reference-axis-title{fill:#d8c8ff}.reference-grid{stroke:#304053;stroke-width:1}.reference-zero{stroke:#8191a8;stroke-width:1;stroke-dasharray:3 3}.reference-cursor{stroke:#fff;stroke-width:1;stroke-dasharray:3 3;opacity:.75}');figure.append(style);
  figure.append(referenceSvg('text',{x:24,y:29,class:'reference-figure-title'},`FlyWatch / ${referenceProtocols[referenceResult.reference.config.protocol].title}`));
  figure.append(referenceSvg('text',{x:24,y:52},'Independent clocks and amplitudes. Synthetic inputs. Noise off. No biological validation.'));
  for(const[key,offset]of [['rate',20],['baseline',610]]){
    const run=referenceRun(key),frame=run.treatment.frames[referenceSamples[key]];
    figure.append(referenceSvg('text',{x:offset+10,y:84},`${key==='rate'?'SOURCE-RATE':'FIXED-POINT CX60'} / ${referenceActivityUnit(key)} / ${referenceTimeUnit(key)}`));
    figure.append(referenceSvg('text',{x:offset+10,y:105},`Selected ${referenceNumber(referenceTime(key,frame))} ${referenceTimeUnit(key)} · ${frame.phase}`));
    for(const[id,y,height]of [['map',125,195],['trajectory',347,145],['profile',524,195]]){
      const chart=$(`reference-${key}-${id}`).cloneNode(true);chart.removeAttribute('id');chart.setAttribute('x',offset);chart.setAttribute('y',y);chart.setAttribute('width',560);chart.setAttribute('height',height);figure.append(chart);
    }
    figure.append(referenceSvg('text',{x:offset+10,y:337},`Activity scale ${key==='rate'?'-':''}${key==='rate'?referenceNumber(referenceScales[key]):'0'} to ${referenceNumber(referenceScales[key])} ${referenceActivityUnit(key)}`));
    figure.append(referenceSvg('text',{x:offset+10,y:513},key==='rate'?'Positive E-PG direction (separate display convention)':'Unique strongest C sector (integer 45-degree bins)'));
  }
  figure.append(referenceSvg('text',{x:24,y:751},'Profiles: pale solid/circles = control; amber dashed/squares = treatment. Reference map: coral negative, mint positive.'));
  figure.append(referenceSvg('text',{x:24,y:775},`Source ${referenceMetadata()?.source_commit??'not supplied'} · exact commands and build identities in JSON export.`));
  return new XMLSerializer().serializeToString(figure);
}
function referenceDownload(contents,type,extension){
  if(!referenceMode||!referenceResult||contents===null)return;
  const blob=new Blob([contents],{type}),url=URL.createObjectURL(blob),a=document.createElement('a');
  a.href=url;a.download=`flywatch-reference-${referenceResult.reference.config.protocol}.${extension}`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
$('reference-mode').addEventListener('click',enterReference);$('reference-run').addEventListener('click',referenceRunComparison);
$('reference-cancel').addEventListener('click',()=>referenceCancel());
$('reference-protocol').addEventListener('change',()=>referenceUpdateDraft(true));$('reference-drive-sign').addEventListener('change',()=>referenceUpdateDraft(true));
for(const id of ['reference-base-angle','reference-shift-angle'])$(id).addEventListener('input',()=>referenceUpdateDraft(true));
for(const key of ['rate','baseline'])$(`reference-${key}-scrubber`).addEventListener('input',()=>referenceSelectSample(key,Number($(`reference-${key}-scrubber`).value)));
for(const button of document.querySelectorAll('[data-reference-phase]'))button.addEventListener('click',()=>{
  if(!referenceMode||!referenceResult)return;for(const key of ['rate','baseline'])referenceSelectSample(key,referencePhaseIndex(referenceRun(key),button.dataset.referencePhase));
});
$('reference-export').addEventListener('click',()=>referenceDownload(JSON.stringify(referenceExportData(),null,2),'application/json','json'));
$('reference-export-svg').addEventListener('click',()=>referenceDownload(referenceFigureSvg(),'image/svg+xml','svg'));
referenceUpdateDraft();referenceRefreshAvailability();
(async()=>{
  if(!data.rate_reference_wasm)return;
  if(typeof WebAssembly==='undefined'||typeof WebAssembly.instantiate!=='function'){referenceText('reference-status','Source-rate Wasm is unavailable. Other offline lenses remain independent.');return;}
  try{
    const bytes=Uint8Array.from(atob(data.rate_reference_wasm),character=>character.charCodeAt(0));
    const result=await WebAssembly.instantiate(bytes);FlyRateReference.verifyModule(result.module);referenceModule=result.module;
    referenceText('reference-status','Source-rate engine ready; waiting for baseline C engine.');referenceRefreshAvailability();
  }catch(error){referenceModule=null;referenceText('reference-status',`Source-rate engine unavailable: ${error.message}`);referenceRefreshAvailability();}
})();
