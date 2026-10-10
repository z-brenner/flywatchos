// Presentation only. The paired protocol runner owns every C command and metric.
// Completed results are immutable snapshots; no playback interval is created.
let experimentsMode = false;
let experimentsBusy = false;
let experimentsResult = null;
let experimentsSample = 0;
let experimentsBarMaximum = 1;
const experimentProtocols = {
  'cue-shift': {title: 'Shift the visual cue', question: 'Does the activity profile follow a shifted cue, and what changes when it returns?', phase: 'Treatment cue moves. Control stays fixed.'},
  'cue-loss': {title: 'Remove and restore the cue', question: 'How much activity survives without the cue, with synthetic drive also at zero?', phase: 'Treatment cue is removed. No drive in either trial.'},
  'cue-drive': {title: 'Cue versus synthetic P-EN A/B drive', question: 'Can one population drive change the profile while the winning sector stays fixed?', phase: 'Treatment receives synthetic P-EN A/B drive.'}
};
const experimentFields = [
  ['warmupSteps','experiment-warmup',1,510,'warm-up steps'],
  ['perturbSteps','experiment-perturb',1,510,'perturbation steps'],
  ['recoverySteps','experiment-recovery',1,510,'recovery steps'],
  ['baseAngle','experiment-base-angle',0,359,'baseline cue angle'],
  ['shiftAngle','experiment-shift-angle',0,359,'shifted cue angle'],
  ['strength','experiment-strength',0,1024,'cue strength'],
  ['drive','experiment-drive',-1024,1024,'P-EN A/B drive']
];
const experimentText = (id, value) => { $(id).textContent = String(value); };
const experimentNumber = value => Number.isInteger(value) ? String(value)
  : Number(value !== 0 && Math.abs(value) < 0.001 ? value.toPrecision(3) : value.toFixed(3)).toString();
const experimentsMetadata = () => data.models?.find(model => model.id === 1);
function experimentsAvailable() {
  return typeof WebAssembly !== 'undefined' && typeof WebAssembly.Module === 'function' &&
    typeof labModule !== 'undefined' && labModule instanceof WebAssembly.Module &&
    typeof labEngine !== 'undefined' && Boolean(labEngine) &&
    typeof FlyExperiment !== 'undefined' && typeof FlyExperiment.run === 'function' && Boolean(experimentsMetadata());
}
function experimentsRefreshAvailability() {
  const available = experimentsAvailable();
  $('experiments-mode').disabled = !available;
  $('experiments-run').disabled = !available || experimentsBusy;
  experimentText('experiments-status', available ? 'CX60 · identical starts, isolated C instances.' : 'Paired trials require the real C / Wasm engine. Replays and anatomy remain separate.');
}
function experimentsStatus(message, state = 'ready') {
  experimentText('experiments-status-line', message);
  $('experiments-status-line').dataset.state = state;
}
function experimentsReadConfig() {
  const protocol = $('experiments-protocol').value;
  if (!Object.hasOwn(experimentProtocols, protocol)) throw new Error('Choose a supported experiment.');
  const config = {protocol};
  for (const [key,id,minimum,maximum,label] of experimentFields) {
    const field = $(id);
    if ((key === 'drive' && protocol !== 'cue-drive') || (key === 'shiftAngle' && protocol !== 'cue-shift')) {
      config[key] = FlyExperiment.DEFAULTS[key];
      field.setAttribute('aria-invalid', 'false');
      continue;
    }
    const value = Number(field.value);
    const valid = field.value.trim() !== '' && Number.isSafeInteger(value) && value >= minimum && value <= maximum;
    field.setAttribute('aria-invalid', String(!valid));
    if (!valid) {
      const details = field.closest('details');
      if (details) details.open = true;
      field.focus();
      throw new Error(`Enter a whole number from ${minimum} to ${maximum} for ${label}.`);
    }
    config[key] = value;
  }
  if (config.warmupSteps + config.perturbSteps + config.recoverySteps > 512) {
    throw new Error('The three phases must total at most 512 model steps.');
  }
  return config;
}
function experimentsUpdateDraft(markChanged = false) {
  const protocol = $('experiments-protocol').value, info = experimentProtocols[protocol];
  if (!info) return;
  experimentText('experiment-question', info.question);
  experimentText('experiment-perturb-label', info.phase);
  $('experiment-shift-field').hidden = protocol !== 'cue-shift';
  $('experiment-drive-field').hidden = protocol !== 'cue-drive';
  const angle = $('experiment-base-angle').value, strength = $('experiment-strength').value;
  experimentText('experiment-control-plan', `Cue held at ${angle}° with strength ${strength}. No drive.`);
  const drive = Number($('experiment-drive').value), group = drive > 0 ? 'A' : drive < 0 ? 'B' : 'A/B';
  const treatment = protocol === 'cue-shift'
    ? `Same start; cue shifts to ${$('experiment-shift-angle').value}° only during perturbation.`
    : protocol === 'cue-loss'
      ? `Same start; cue strength becomes zero during perturbation, then returns to ${strength}. Drive stays zero.`
      : `Same cue throughout; synthetic P-EN-${group} drive ${drive > 0 ? '+' : ''}${experimentNumber(drive)} during perturbation, then zero.`;
  experimentText('experiment-treatment-plan', treatment);
  if (markChanged) experimentsStatus(experimentsResult
    ? 'Settings changed. Run again to apply them; charts and export still describe the previous completed trial.'
    : 'Settings changed. Run the paired trial to inspect this configuration.', 'dirty');
}
function experimentsShowSources() {
  const metadata = experimentsMetadata(), container = $('experiments-sources');
  container.replaceChildren();
  for (const source of metadata?.sources ?? []) {
    try {
      const url = new URL(source.url);
      if (url.protocol !== 'https:' || url.username || url.password) continue;
      const item = document.createElement('li'), link = document.createElement('a');
      link.href = url.href; link.textContent = source.title || url.href;
      link.target = '_blank'; link.rel = 'noopener noreferrer'; item.append(link); container.append(item);
    } catch (_) { /* An invalid citation never becomes a link. */ }
  }
  experimentText('experiment-provenance', [
    `Model source commit: ${metadata?.source_commit ?? 'Not supplied'}`,
    `Source matrix SHA-256: ${metadata?.source_sha256 ?? 'Not supplied'}`,
    `C / Wasm SHA-256: ${data.live_wasm_sha256 ?? 'Not supplied'}`,
    `Protocol JavaScript SHA-256: ${data.experiment_protocol_sha256 ?? 'Not supplied'}`
  ].join('\n'));
}
function enterExperiments() {
  if (!experimentsAvailable() || experimentsMode) return;
  if (typeof userLensSelected !== 'undefined') userLensSelected = true;
  leaveAnatomy(); pause();
  if (liveMode) liveReleaseAll(false);
  liveMode = false; experimentsMode = true;
  document.body.dataset.lens = 'experiments';
  for (const selector of ['.workspace','.playback','.below','#live-controls']) document.querySelector(selector).hidden = true;
  $('experiments-lens').hidden = false;
  $('experiments-mode').setAttribute('aria-pressed', 'true');
  $('live-mode').setAttribute('aria-pressed', 'false');
  document.querySelectorAll('.scenario').forEach(button => button.setAttribute('aria-pressed', 'false'));
  experimentText('mode-badge', 'PAIRED C / OFFLINE');
  experimentText('intro-eyebrow', 'QUESTION → PAIRED TRIAL → MEASURED MODEL RESPONSE');
  experimentText('scenario-title', 'What changes when one input changes?');
  experimentText('scenario-summary', 'Hold a control steady. Perturb an identical-start CX60 model. Compare complete activity profiles, coarse sector readouts and recovery, all from the unchanged C implementation.');
  experimentText('build-tag', 'TWO ISOLATED C INSTANCES\nSYNTHETIC INPUTS · ABSTRACT STEPS');
  experimentText('footer-mode', 'OFFLINE BY CONSTRUCTION · EXACT PAIRED C COMMANDS');
  experimentText('footer-keys', 'SCRUB STORED SAMPLES · NO AUTOPLAY');
  experimentsShowSources();
}
function leaveExperiments() {
  if (!experimentsMode) return;
  experimentsMode = false; delete document.body.dataset.lens;
  $('experiments-lens').hidden = true;
  $('experiments-mode').setAttribute('aria-pressed', 'false');
  for (const selector of ['.workspace','.playback','.below']) document.querySelector(selector).hidden = false;
  experimentText('intro-eyebrow', 'Stimulus → dynamics → readout');
  $('build-tag').replaceChildren(document.createTextNode('PORTABLE C → WEBASSEMBLY'), document.createElement('br'), document.createTextNode('SYNTHETIC INPUTS · NO DEVICE'));
  experimentText('footer-mode', 'OFFLINE BY CONSTRUCTION · REPLAYABLE C COMMANDS');
  experimentText('footer-keys', '← / → STEP   SPACE PLAY   HOME / END');
}
function experimentSvg(tag, attributes = {}, text = null) {
  const element = document.createElementNS('http://www.w3.org/2000/svg', tag);
  for (const [name,value] of Object.entries(attributes)) element.setAttribute(name, String(value));
  if (text !== null) element.textContent = String(text);
  return element;
}
function experimentsDrawChart(id, series, maximum, height, label, circular = false) {
  const svg = $(id), last = experimentsResult.control.frames.length - 1;
  const left = 53, right = 767, top = 15, bottom = height - 27;
  const x = index => left + index / Math.max(1,last) * (right-left);
  const y = value => bottom - value / maximum * (bottom-top);
  const seriesDescription = series.length === 1 ? 'The lavender line is the paired profile difference.' : 'Control is solid mint. Treatment is dashed coral.';
  svg.replaceChildren(experimentSvg('title', {}, label), experimentSvg('desc', {}, `${seriesDescription} The shaded band is the perturbation phase. A vertical line marks the selected sample.`));
  const phase = experimentsResult.phases.find(item => /perturb/i.test(item.name));
  if (phase) svg.append(experimentSvg('rect', {x:x(Math.max(0,phase.startIndex-1)),y:top,width:x(phase.endIndex)-x(Math.max(0,phase.startIndex-1)),height:bottom-top,class:'experiment-phase-band'}));
  const ticks = circular ? [0,90,180,270,315] : [0,maximum/2,maximum];
  for (const value of ticks) {
    svg.append(experimentSvg('line', {x1:left,x2:right,y1:y(value),y2:y(value),class:'experiment-grid'}));
    svg.append(experimentSvg('text', {x:left-8,y:y(value)+3,'text-anchor':'end'}, circular ? `${value}°` : experimentNumber(value)));
  }
  for (const index of [...new Set([0, ...experimentsResult.phases.map(item=>item.endIndex)])]) {
    svg.append(experimentSvg('text', {x:x(index),y:height-6,'text-anchor':index===0?'start':index===last?'end':'middle',class:'experiment-axis-label'}, String(index)));
  }
  for (const item of series) {
    let path = '', previous = null;
    for (let index=0;index<item.values.length;index++) {
      const value = item.values[index];
      if (value === null || !Number.isFinite(value) || value < 0) {previous=null;continue;}
      const continuous = previous !== null && (!circular || Math.abs(value-previous)<=180);
      const pointX = x(index).toFixed(2), pointY = y(value).toFixed(2);
      path += continuous && circular ? `H${pointX} V${pointY} ` : `${continuous?'L':'M'}${pointX},${pointY} `;
      previous = value;
    }
    svg.append(experimentSvg('path', {d:path.trim(),fill:'none',stroke:item.color,'stroke-width':2,'stroke-linejoin':'round',
      'stroke-dasharray':item.name==='treatment'?'7 4':'none','data-series':item.name}));
    if (circular) item.values.forEach((value,index)=>{
      if (value !== null && Number.isFinite(value) && value >= 0) {
        svg.append(experimentSvg('circle',{cx:x(index),cy:y(value),r:1.7,fill:item.color,'data-peak-sample':index,'data-arm':item.name}));
      }
    });
  }
  svg.append(experimentSvg('line',{x1:x(experimentsSample),x2:x(experimentsSample),y1:top,y2:bottom,class:'experiment-cursor','data-experiment-cursor':'','data-left':left,'data-right':right}));
}
function experimentsDrawResults() {
  const result = experimentsResult, frames = [...result.control.frames,...result.treatment.frames];
  experimentsBarMaximum = Math.max(1,...frames.flatMap(frame=>frame.sectorMeans));
  const strengthMax = Math.max(1,...frames.map(frame=>frame.readout_strength));
  const differenceMax = Math.max(1,...result.comparisons.map(item=>item.profileL1));
  const pair = key => ['control','treatment'].map(name=>({name,values:result[name].frames.map(frame=>frame[key]),color:name==='control'?'#99e9d5':'#efb1a5'}));
  experimentsDrawChart('experiment-sector-chart',pair('readout_heading'),315,190,'Strongest E-PG sector in each C model; 45-degree bins',true);
  experimentsDrawChart('experiment-strength-chart',pair('readout_strength'),strengthMax,145,'C peak-sector activity, raw Q10 counts');
  experimentsDrawChart('experiment-difference-chart',[{name:'difference',values:result.comparisons.map(item=>item.profileL1),color:'#dcc4ef'}],differenceMax,145,'Eight-sector absolute profile difference, raw Q10 counts');
  $('experiment-phase-jumps').replaceChildren();
  for (const phase of result.phases) {
    const button = document.createElement('button');
    button.textContent = `${phase.name.replaceAll('-',' ')} end · ${phase.endIndex}`;
    button.addEventListener('click',()=>experimentsSelectSample(phase.endIndex));
    $('experiment-phase-jumps').append(button);
  }
  experimentText('experiment-result-title', experimentProtocols[result.config.protocol].title);
  experimentText('experiment-result-caption', `${result.config.warmupSteps} warm-up / ${result.config.perturbSteps} perturbation / ${result.config.recoverySteps} recovery · ${result.control.frames.length} aligned snapshots · no calibrated clock`);
  $('experiments-scrubber').max = result.control.frames.length-1;
  const endpoint = result.phases.find(phase=>/perturb/i.test(phase.name))?.endIndex ?? result.control.frames.length-1;
  experimentsSelectSample(endpoint);
  experimentsFindings(endpoint);
}
function experimentsDrawBars(name, frame) {
  const container = $(`experiment-${name}-bars`); container.replaceChildren();
  frame.sectorMeans.forEach((value,index)=>{
    const angle = experimentsResult.sectors[index].angle;
    const bar = document.createElement('div'), amount = document.createElement('span'), track = document.createElement('span');
    const fill = document.createElement('span'), caption = document.createElement('span');
    bar.className = 'experiment-bar'; bar.dataset.sector = angle;
    bar.setAttribute('aria-label',`${angle} degrees: ${experimentNumber(value)} raw Q10 sector-mean activity`);
    bar.title = `${angle}° · ${experimentNumber(value)} raw Q10 · ${experimentNumber(value/1024)} activity units`;
    amount.className='experiment-bar-value';amount.textContent=experimentNumber(value);
    track.className='experiment-bar-track';fill.className='experiment-bar-fill';fill.style.height=`${value/experimentsBarMaximum*100}%`;
    caption.className='experiment-bar-angle';caption.textContent=`${angle}°`;
    track.append(fill);bar.append(amount,track,caption);container.append(bar);
  });
}
function experimentsSignalState(frame) {
  if (frame.epgRawTotal === 0) return 'E-PG silent: all raw E-PG activations are zero.';
  if (frame.readout_heading < 0) return 'Below integer-sector resolution; raw E-PG activity remains.';
  if (frame.peakTieAngles.length > 1) return `Tie at ${frame.peakTieAngles.join('°, ')}°; lowest angle displayed. Not a unique peak.`;
  return 'Unique strongest integer sector. This alone is not evidence of a localized heading signal.';
}
function experimentsSelectSample(index) {
  if (!experimentsResult) return;
  const last = experimentsResult.control.frames.length-1;
  experimentsSample = Math.max(0,Math.min(last,Number.isInteger(index)?index:0));
  const control = experimentsResult.control.frames[experimentsSample], comparison = experimentsResult.comparisons[experimentsSample];
  experimentText('experiment-step', experimentsSample);
  experimentText('experiment-phase', experimentsSample===0?'Initial state':control.phase);
  for (const name of ['control','treatment']) {
    const frame = experimentsResult[name].frames[experimentsSample];
    experimentText(`experiment-${name}-peak`,frame.readout_heading < 0?'Unavailable':`${frame.readout_heading}°`);
    experimentText(`experiment-${name}-state`,experimentsSignalState(frame));
    experimentText(`experiment-${name}-strength`,experimentNumber(frame.readout_strength));
    experimentsDrawBars(name,frame);
  }
  experimentText('experiment-profile-difference', experimentNumber(comparison.profileL1));
  experimentText('experiment-peak-separation', comparison.peakSeparationDegrees === null?'Unavailable':`${experimentNumber(comparison.peakSeparationDegrees)}°`);
  experimentText('experiment-retention', comparison.treatmentRetention === null?'Unavailable':`${experimentNumber(comparison.treatmentRetention)}×`);
  $('experiments-scrubber').value=experimentsSample;
  $('experiments-scrubber').setAttribute('aria-valuetext',`Step ${experimentsSample} of ${last}, ${experimentsSample===0?'initial state':control.phase}; profile difference ${experimentNumber(comparison.profileL1)} raw Q10.`);
  $('experiments-previous').disabled=experimentsSample===0;
  $('experiments-next').disabled=experimentsSample===last;
  for (const cursor of document.querySelectorAll('[data-experiment-cursor]')) {
    const x = Number(cursor.dataset.left) + experimentsSample/Math.max(1,last)*(Number(cursor.dataset.right)-Number(cursor.dataset.left));
    cursor.setAttribute('x1',String(x));cursor.setAttribute('x2',String(x));
  }
}
function experimentsFindings(endpoint) {
  const result=experimentsResult, comparison=result.comparisons[endpoint], treatment=result.treatment.frames[endpoint];
  let finding = `At the perturbation endpoint (step ${endpoint}), the eight-sector profile difference is ${experimentNumber(comparison.profileL1)} raw Q10 counts. `;
  if (treatment.epgRawTotal===0) finding+='Treatment E-PG activity is exactly zero. ';
  else if (treatment.readout_heading<0) finding+='Treatment has residual raw E-PG activity below the integer-sector readout resolution. ';
  else if (comparison.peakSeparationDegrees===0 && comparison.profileL1>0) finding+='The strongest sector matches the control while the activity profile differs. ';
  else if (comparison.peakSeparationDegrees!==null) finding+=`The unique strongest sectors are ${comparison.peakSeparationDegrees}° apart. `;
  else finding+='Peak separation is unavailable because a peak is absent or tied. ';
  finding+=`After recovery, profile difference is ${experimentNumber(result.comparisons.at(-1).profileL1)}. Restored inputs do not establish identical neural states.`;
  experimentText('experiment-findings',finding);
}
function experimentsRun() {
  if (!experimentsMode || !experimentsAvailable() || experimentsBusy) return;
  try {
    const config=experimentsReadConfig();
    experimentsBusy=true;experimentsRefreshAvailability();
    const result=FlyExperiment.run(labModule,experimentsMetadata(),config);
    // Preserve the completed protocol, not the editable form, and bind it to
    // the actual bundled sources. These fields never drive simulated activity.
    experimentsResult={...result,model_metadata:JSON.parse(JSON.stringify(experimentsMetadata())),
      artifact_provenance:{live_wasm_sha256:data.live_wasm_sha256??null,
        live_wasm_manifest_sha256:data.live_wasm_manifest_sha256??null,
        live_wasm_manifest:JSON.parse(JSON.stringify(data.live_wasm_manifest??null)),
        experiment_protocol_sha256:data.experiment_protocol_sha256??null}};
    experimentsDrawResults();
    $('experiments-results').hidden=false;$('experiments-empty').hidden=true;
    $('experiments-export').disabled=false;
    experimentsStatus(`Completed ${config.warmupSteps+config.perturbSteps+config.recoverySteps} model steps per trial. Showing the perturbation endpoint; scrub to inspect warm-up and recovery.`);
  } catch(error) {
    experimentsStatus(`${error.message}${experimentsResult?' Previous completed results are still shown.':''}`, 'error');
  } finally {experimentsBusy=false;experimentsRefreshAvailability();}
}
function experimentsExportData() {
  return experimentsResult ? JSON.parse(JSON.stringify(experimentsResult)) : null;
}
$('experiments-mode').addEventListener('click',enterExperiments);
$('experiments-run').addEventListener('click',experimentsRun);
$('experiments-protocol').addEventListener('change',()=>experimentsUpdateDraft(true));
for (const [,id] of experimentFields) $(id).addEventListener('input',()=>experimentsUpdateDraft(true));
$('experiments-scrubber').addEventListener('input',()=>experimentsSelectSample(Number($('experiments-scrubber').value)));
$('experiments-previous').addEventListener('click',()=>experimentsSelectSample(experimentsSample-1));
$('experiments-next').addEventListener('click',()=>experimentsSelectSample(experimentsSample+1));
$('experiments-export').addEventListener('click',()=>{
  if (!experimentsMode || !experimentsResult) return;
  const blob=new Blob([JSON.stringify(experimentsExportData(),null,2)],{type:'application/json'});
  const url=URL.createObjectURL(blob),anchor=document.createElement('a');
  anchor.href=url;anchor.download=`flywatch-paired-${experimentsResult.config.protocol}.json`;anchor.click();
  setTimeout(()=>URL.revokeObjectURL(url),1000);
});
experimentsUpdateDraft();
experimentsRefreshAvailability();
