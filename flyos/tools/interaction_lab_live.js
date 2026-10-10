// Live UI only. Neural dynamics, ownership and framebuffer rendering run in C.
const LIVE_HISTORY_LIMIT = 128;
const LIVE_COMMAND_LIMIT = 16384;
const liveKeys = new Set();
const liveSourceResets = [];
let liveHasEvent = false;
let liveSeed = 38138277;
let liveBusy = false;
let liveCanvas = null;
let liveContext = null;
const livePalette = [[8,10,9],[54,69,59],[218,231,211],[135,184,122],[184,122,135],[242,210,94]];
const circuitTopologies = new Map();

function circuitMetadata(frame) {
  const id = frame.model ?? 0;
  const metadata = data.models.find(model => model.id === id);
  if (!metadata) throw new Error('unknown model metadata');
  return {...metadata, edges: circuitTopologies.get(id) ?? [],
    topology_available: circuitTopologies.has(id)};
}
function liveReadTopology() {
  const id = labEngine.fly_lab_model();
  const metadata = data.models.find(model => model.id === id);
  const count = labEngine.fly_lab_model_node_count();
  const edgeCount = labEngine.fly_lab_edge_count();
  if (!metadata || count !== metadata.units.length || count < 1 || count > 64 ||
      edgeCount < 0 || edgeCount > 4096) throw new Error('invalid C model topology');
  const edges = [];
  for (let i = 0; i < edgeCount; i++) {
    const source = labEngine.fly_lab_edge_source(i);
    const target = labEngine.fly_lab_edge_target(i);
    const raw = labEngine.fly_lab_edge_raw_weight(i);
    const denominator = labEngine.fly_lab_edge_denominator(i);
    const sign = labEngine.fly_lab_edge_sign(i);
    const coefficientQ = labEngine.fly_lab_edge_weight_q(i);
    if (source < 0 || source >= count || target < 0 || target >= count ||
        !Number.isFinite(raw) || raw <= 0 || denominator < 1 || ![-1, 1].includes(sign) ||
        !Number.isInteger(coefficientQ)) {
      throw new Error('invalid C connection metadata');
    }
    edges.push({source, target, weight: raw * sign, raw_weight: raw,
      scale: denominator, coefficient_q: coefficientQ, sign,
      kind: sign < 0 ? 'negative' : 'positive'});
  }
  circuitTopologies.set(id, edges);
}

function liveError(error) {
  pause();
  $('live-notice').textContent = `Sandbox paused: ${error.message}. Reset the seed to start again.`;
  $('live-notice').classList.add('amber');
}
function liveCommand(name, args = []) {
  if (live.commands.length >= LIVE_COMMAND_LIMIT) {
    throw new Error('session command limit reached');
  }
  const result = labEngine[name](...args);
  live.commands.push([name, ...args]);
  return result;
}
function liveCapture(action) {
  const pixels = new Uint8Array(labEngine.memory.buffer, labEngine.fly_lab_pixels(), 57600);
  const rgba = liveContext.createImageData(240, 240);
  for (let i = 0; i < pixels.length; i++) {
    const rgb = livePalette[pixels[i]];
    if (!rgb) throw new Error('invalid C framebuffer role');
    rgba.data[i*4] = rgb[0]; rgba.data[i*4+1] = rgb[1]; rgba.data[i*4+2] = rgb[2]; rgba.data[i*4+3] = 255;
  }
  liveContext.putImageData(rgba, 0, 0);
  const neurons = Array.from(new Int16Array(labEngine.memory.buffer, labEngine.fly_lab_activations(), 64));
  const view = ['INVALID','HOME','NON_HOME'][labEngine.fly_lab_view()];
  const tick = labEngine.fly_lab_epoch();
  const frame = {
    action, detail: 'Live, persistent C network. Each model step runs the real C implementation; signals and view context are synthetic.',
    tick, view, route: liveHasEvent ? ['REJECTED','GARMIN','FLYOS'][labEngine.fly_lab_route()] : 'NONE',
    held_mask: labEngine.fly_lab_held(), active_mask: labEngine.fly_lab_active(),
    pulse_mask: labEngine.fly_lab_delivered_pulse() | labEngine.fly_lab_pulse(),
    input_buttons: labEngine.fly_lab_buttons(), usb: Boolean(labEngine.fly_lab_usb()),
    redraw_pending: false, redraw_complete: false, redraw_exhausted: false,
    attempts: 0, budget: 0, epoch: 0, enqueued: false,
    safe_callback: false, source_locked: false, usb_locked: false,
    state: labEngine.fly_lab_state(), model: labEngine.fly_lab_model(),
    node_count: labEngine.fly_lab_model_node_count(), neurons, image: liveCanvas.toDataURL('image/png'),
    stimulus: {angle: labEngine.fly_lab_stimulus_angle(),
      strength: labEngine.fly_lab_stimulus_strength(), turn: labEngine.fly_lab_stimulus_turn()},
    readout_heading: labEngine.fly_lab_readout_heading(),
    readout_strength: labEngine.fly_lab_readout_strength(),
    classifier: {source:'manual-live-context',reason:'not-run',reads:0,nodes:0,limitation:'none'}
  };
  if (frame.model === 1) frame.detail = 'Published fly heading-circuit topology; simplified fixed-point rate dynamics. The phase readout is the strongest E-PG sector, not a measured behavior or calibrated heading.';
  if (view !== 'HOME' || frame.usb) frame.detail = 'Native framebuffer preserved. The network continues on the host; pending release pulses wait for an eligible HOME frame.';
  live.frames.push(frame);
  if (live.frames.length > LIVE_HISTORY_LIMIT) live.frames.shift();
  frameIndex = live.frames.length - 1;
  $('timeline').max = frameIndex;
  $('events').replaceChildren();
  live.frames.slice(-7).forEach((f, offset) => {
    const i = Math.max(0, live.frames.length - 7) + offset;
    const button = document.createElement('button'); button.dataset.frame=String(i);
    const time = document.createElement('time'); time.textContent = pad(f.tick);
    const text = document.createElement('span'); text.textContent = f.action;
    button.append(time, text); button.addEventListener('click', () => setFrame(i));
    $('events').append(button);
  });
  render();
  // Replay uses ordinal event indices; live history shows the last seven only.
  [...$('events').children].forEach((b,i,all) => b.setAttribute('aria-current', String(i === all.length - 1)));
}
function liveStep(action = 'Neural step') {
  if (!liveMode || !labEngine || liveBusy) return;
  try { liveCommand('fly_lab_step'); liveCapture(action); } catch (error) { liveError(error); }
}
function livePlay() {
  if (!liveMode || !labEngine) return;
  pause();
  $('play').textContent = 'PAUSE'; $('play').setAttribute('aria-label','Pause live specimen');
  const delay = Number($('speed').value) / 4;
  timer = setInterval(() => liveStep('Neural step'), delay);
}
function liveReleaseAll(capture = true) {
  if (!labEngine || !live) return;
  try {
    liveSourceResets.forEach(reset => reset());
    const hadKeys = liveKeys.size > 0;
    for (const key of liveKeys) {
      liveCommand('fly_lab_event', [key, 2]);
      liveHasEvent = true;
    }
    liveKeys.clear();
    if (capture && liveMode && hadKeys) liveStep('Controls released');
    else if (hadKeys && liveMode) liveCapture('Controls safely released');
  } catch (error) { liveKeys.clear(); liveError(error); }
}
function liveButton(key, pressed) {
  if (!liveMode || !labEngine) return;
  if (pressed === liveKeys.has(key)) return;
  try {
    liveCommand('fly_lab_event', [key, pressed ? 0 : 2]); liveHasEvent = true;
    if (pressed) liveKeys.add(key); else liveKeys.delete(key);
    liveStep(`${names[key]} ${pressed ? 'pressed' : 'released'}`);
  } catch (error) { liveError(error); }
}
function liveInteger(value, minimum, maximum, name) {
  const number = Number(value);
  if (value === '' || !Number.isInteger(number) || number < minimum || number > maximum) {
    throw new Error(`invalid ${name}`);
  }
  return number;
}
function liveSensors(capture = true) {
  if (!labEngine || !live) return;
  const enabled = ['hr','motion','battery','charging'].map(id => $(id+'-on').checked);
  const mask = enabled.reduce((bits,on,i) => bits | (on ? 1<<i : 0), 0);
  const bpm = liveInteger($('hr-input').value,0,300,'heart rate');
  const motion = liveInteger($('motion-input').value,-32768,32767,'motion');
  const battery = liveInteger($('battery-input').value,0,100,'battery');
  $('hr-value').textContent = bpm; $('motion-value').textContent = motion; $('battery-value').textContent = battery;
  const channels = ['HR','motion','battery','charging'].filter((_,i) => enabled[i]);
  $('sensor-summary').textContent = channels.length ? channels.join(' + ') : 'All unavailable';
  if (!liveCommand('fly_lab_set_sensors', [mask,bpm,0,motion,battery,Number($('charging-input').checked)])) {
    throw new Error('sensor values rejected by C');
  }
  if (capture) liveStep('Synthetic signals changed');
}
function liveSetContext() {
  if (!liveMode) return;
  try {
    if (!liveCommand('fly_lab_set_context', [liveInteger($('live-view').value,0,2,'view'), Number($('live-usb').checked), 1])) throw new Error('context rejected by C');
    liveStep('Synthetic view changed');
  } catch (error) { liveError(error); }
}
function liveStimulus(capture = true) {
  if (!labEngine || !live) return;
  const angle = liveInteger($('cue-angle').value, 0, 359, 'cue angle');
  const strength = liveInteger($('cue-strength').value, 0, 1024, 'cue strength');
  const turn = liveInteger($('turn-drive').value, -1024, 1024, 'turn drive');
  if (!liveCommand('fly_lab_set_stimulus', [angle, strength, turn])) {
    throw new Error('stimulus rejected by C');
  }
  $('cue-angle-value').textContent = angle;
  $('cue-strength-value').textContent = strength;
  $('turn-drive-value').textContent = `${turn > 0 ? '+' : ''}${turn}`;
  if (capture) liveStep('Circuit stimulus changed');
}
function liveCircuitPreset(kind) {
  if (!liveMode || !labEngine || labEngine.fly_lab_model() !== 1) return;
  pause();
  try {
    if (kind === 'hide' || kind === 'return') {
      $('cue-strength').value = kind === 'hide' ? '0' : '768';
      liveStimulus(false);
      for (let i = 0; i < 8; i++) {
        liveCommand('fly_lab_step');
        liveCapture(kind === 'hide' ? 'Landmark removed' : 'Landmark restored');
      }
    } else {
      $('turn-drive').value = kind === 'left' ? '-768' : '768';
      liveStimulus(false);
      for (let i = 0; i < 12; i++) {
        liveCommand('fly_lab_step');
        liveCapture(kind === 'left' ? 'P-EN B drive (negative)' : 'P-EN A drive (positive)');
      }
      $('turn-drive').value = '0';
      liveStimulus(false); liveStep('Turn drive released');
    }
  } catch (error) { liveError(error); }
}
function liveReset() {
  if (!labEngine) return;
  pause();
  const seed = Number($('live-seed').value);
  if (!Number.isInteger(seed) || seed < 0 || seed > 4294967295) {
    $('live-notice').textContent = 'Choose a whole-number seed from 0 to 4294967295.';
    $('live-notice').classList.add('amber'); return;
  }
  let model;
  try { model = liveInteger($('live-model').value, 0, 7, 'model selection'); }
  catch (error) { liveError(error); return; }
  if (!data.models.some(item => item.id === model)) {
    liveError(new Error('unknown model selection')); return;
  }
  liveSeed = seed;
  liveSourceResets.forEach(reset => reset());
  liveKeys.clear(); liveHasEvent = false;
  const metadata = data.models.find(item => item.id === model);
  live = {id:'live-specimen',title:metadata.label,summary:metadata.description,seed:liveSeed,model,
    model_metadata:metadata,command_schema:2,command_history_complete:true,
    history_limit:LIVE_HISTORY_LIMIT,commands:[],frames:[]};
  if (!liveCommand('fly_lab_reset_model', [model, liveSeed])) {
    liveError(new Error('model rejected by C')); return;
  }
  liveReadTopology();
  live.topology = circuitTopologies.get(model);
  selectedNeuron = model === 1 ? 34 : Math.min(selectedNeuron, metadata.units.length - 1);
  $('live-view').value = '1'; $('live-usb').checked = false;
  $('hr-on').checked = false; $('motion-on').checked = false; $('charging-on').checked = false;
  $('battery-on').checked = true; $('battery-input').value = '87'; $('hr-input').value = '72';
  $('motion-input').value = '0'; $('charging-input').checked = false;
  liveSensors(false);
  $('cue-angle').value = '0'; $('cue-strength').value = '768'; $('turn-drive').value = '0';
  liveStimulus(false);
  liveCommand('fly_lab_step');
  $('live-notice').classList.remove('amber');
  $('live-notice').textContent = model === 0
    ? `Specimen ${liveSeed}. Hold the watch keys or try a burst. This baseline is hand-authored; all signals are synthetic.`
    : 'Published circuit topology with simplified rate dynamics. Move the landmark, inject a turn, or remove the cue. No calibrated clock, persistent heading memory, or validated path integration is claimed.';
  liveUpdateModelControls(metadata);
  liveCapture('Specimen seeded');
}
function liveUpdateModelControls(metadata) {
  const biological = metadata.id !== 0;
  $('circuit-stimulus-controls').hidden = !biological;
  document.querySelector('.presets').hidden = biological;
  document.querySelector('.sensor-options').hidden = biological;
  $('live-seed').disabled = biological;
  $('live-random').disabled = biological;
  $('live-reset').textContent = biological ? 'RESET CIRCUIT' : 'RESET SEED';
  $('live-seed').title = biological ? 'This circuit is deterministic and does not use a seed.' : 'Deterministic baseline seed';
  $('scenario-count').textContent = String(metadata.units.length);
  $('scenario-total').textContent = 'UNITS';
  $('scenario-title').textContent = biological ? 'A compass made of connections.' : 'A tiny network. Yours to disturb.';
  $('scenario-summary').textContent = metadata.description;
  $('model-description').textContent = metadata.description;
  $('model-basis').textContent = metadata.biological_basis;
}
function enterLive() {
  if (!labEngine || liveMode) return;
  leaveAnatomy();
  pause(); liveMode = true; pause();
  $('live-controls').hidden = false;
  $('mode-badge').textContent='LIVE C / OFFLINE';
  $('live-mode').setAttribute('aria-pressed','true');
  document.querySelectorAll('.scenario').forEach(b => b.setAttribute('aria-pressed','false'));
  $('state-label').textContent = 'NETWORK STATE';
  $('activity-label').textContent = 'ACTIVE CELLS';
  $('epoch-label').textContent = 'MODEL STEP';
  if (!live) liveReset(); else { frameIndex = live.frames.length-1; $('timeline').max=frameIndex; liveCapture('Sandbox resumed'); }
  liveUpdateModelControls(circuitMetadata(live.frames.at(-1)));
}
function livePreset(kind) {
  if (!liveMode || !labEngine || labEngine.fly_lab_model() !== 0) return;
  try {
    if (kind === 'burst') {
      // Each stimulus is an actual complete C-owned key sequence.
      const fresh = [1,4].filter(key => !liveKeys.has(key));
      fresh.forEach(key => {liveCommand('fly_lab_event',[key,0]);liveKeys.add(key);});
      liveHasEvent = true;
      for (let i=0;i<6;i++) {liveCommand('fly_lab_step');liveCapture('Motor burst');}
      fresh.forEach(key => {liveCommand('fly_lab_event',[key,2]);liveKeys.delete(key);});
      liveStep('Burst released');
    } else {
      if (kind === 'rest') {
        liveReleaseAll(false);
        ['hr','motion','battery','charging'].forEach(id => $(id+'-on').checked = false);
      } else {
        $('hr-on').checked = true; $('hr-input').value = '118';
        $('motion-on').checked = true; $('motion-input').value = '4096';
      }
      liveSensors(false); liveStep(kind === 'rest' ? 'External stimuli removed' : 'Movement signal injected');
    }
  } catch (error) { liveError(error); }
}
$('live-mode').addEventListener('click', enterLive);
$('live-reset').addEventListener('click', liveReset);
$('live-model').addEventListener('change', () => {
  if (liveMode) liveReset();
});
$('live-random').addEventListener('click', () => {
  const value = new Uint32Array(1); crypto.getRandomValues(value); $('live-seed').value=String(value[0]); liveReset();
});
$('live-view').addEventListener('change',liveSetContext); $('live-usb').addEventListener('change',liveSetContext);
for (const id of ['hr-on','hr-input','motion-on','motion-input','battery-on','battery-input','charging-on','charging-input']) {
  $(id).addEventListener('input', () => {try {liveSensors();} catch(error) {liveError(error);}});
}
$('burst').addEventListener('click',()=>livePreset('burst'));
$('movement').addEventListener('click',()=>livePreset('movement'));
$('rest').addEventListener('click',()=>livePreset('rest'));
for (const id of ['cue-angle', 'cue-strength', 'turn-drive']) {
  $(id).addEventListener('input', () => {
    if (!liveMode) return;
    try { liveStimulus(); } catch (error) { liveError(error); }
  });
}
for (const [id, kind] of [['turn-left', 'left'], ['turn-right', 'right'],
                         ['cue-hide', 'hide'], ['cue-return', 'return']]) {
  $(id).addEventListener('click', () => liveCircuitPreset(kind));
}
document.querySelectorAll('.key').forEach((button,key) => {
  let keyboardHandled = false;
  let keyboardHeld = false;
  const pointers = new Set();
  const synchronize = () => liveButton(key, keyboardHeld || pointers.size > 0);
  liveSourceResets.push(() => {keyboardHandled=false;keyboardHeld=false;pointers.clear();});
  button.addEventListener('pointerdown', event => {
    if (event.button !== 0 || !liveMode) return;
    event.preventDefault(); button.focus();
    pointers.add(event.pointerId); button.setPointerCapture(event.pointerId); synchronize();
  });
  for (const name of ['pointerup','pointercancel','lostpointercapture']) {
    button.addEventListener(name,event=>{pointers.delete(event.pointerId);synchronize();});
  }
  button.addEventListener('keydown',event=>{
    if (event.code!=='Space' && event.code!=='Enter') return;
    event.preventDefault();keyboardHandled=true;keyboardHeld=true;
    if (!event.repeat) synchronize();
  });
  button.addEventListener('keyup',event=>{
    if (event.code!=='Space' && event.code!=='Enter') return;
    event.preventDefault();keyboardHeld=false;synchronize();
    setTimeout(()=>keyboardHandled=false,0);
  });
  button.addEventListener('click',event=>{
    // Assistive activation is a tap only when no other source owns this key.
    if (event.detail===0 && !keyboardHandled && !keyboardHeld && pointers.size===0) {
      keyboardHeld=true;synchronize();keyboardHeld=false;synchronize();
    }
  });
  button.addEventListener('blur',()=>{
    keyboardHeld=false;keyboardHandled=false;synchronize();
  });
});
window.addEventListener('blur',()=>{if(liveMode){pause();liveReleaseAll(false);}});

async function initializeLive() {
  if (!data.live_wasm) {
    $('live-status').textContent='Replay bundle. Live engine was not included.'; return;
  }
  try {
    const bytes=Uint8Array.from(atob(data.live_wasm),c=>c.charCodeAt(0));
    const loaded=await WebAssembly.instantiate(bytes,{});
    const exports=loaded.instance.exports;
    const required=['fly_lab_reset','fly_lab_event','fly_lab_set_context','fly_lab_set_sensors','fly_lab_step',
      'fly_lab_pixels','fly_lab_activations','fly_lab_pixel_count','fly_lab_neuron_count','fly_lab_route',
      'fly_lab_held','fly_lab_active','fly_lab_pulse','fly_lab_delivered_pulse','fly_lab_buttons','fly_lab_state','fly_lab_epoch',
      'fly_lab_view','fly_lab_usb','fly_lab_reset_model','fly_lab_model','fly_lab_model_node_count',
      'fly_lab_edge_count','fly_lab_edge_source','fly_lab_edge_target','fly_lab_edge_raw_weight',
      'fly_lab_edge_denominator','fly_lab_edge_sign','fly_lab_edge_weight_q','fly_lab_set_stimulus',
      'fly_lab_stimulus_angle','fly_lab_stimulus_strength','fly_lab_stimulus_turn',
      'fly_lab_readout_heading','fly_lab_readout_strength'];
    if (!(exports.memory instanceof WebAssembly.Memory) || required.some(name=>typeof exports[name]!=='function') ||
        exports.fly_lab_pixel_count()!==57600 || exports.fly_lab_neuron_count()!==64) throw new Error('unsupported live engine interface');
    liveCanvas=document.createElement('canvas'); liveCanvas.width=240;liveCanvas.height=240;
    liveContext=liveCanvas.getContext('2d');if(!liveContext)throw new Error('canvas unavailable');
    labEngine=exports;
    // Cache baseline topology for historical replay even when the new circuit
    // is the first selected live model. This pre-session reset is not a replay
    // command and cannot affect the following explicit session reset.
    labEngine.fly_lab_reset(0);
    liveReadTopology();
    $('live-mode').disabled=false;
    $('live-status').textContent='Ready. Real C → WebAssembly. No server.';
    if (!anatomyMode) enterLive();
  } catch(error) {
    $('live-status').textContent='Live engine unavailable. Replays still work.';
    $('live-status').title=error.message;
  }
}
initializeLive();
