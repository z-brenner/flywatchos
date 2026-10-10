// Presentation only: all activations and implemented connections come from C.
// Diagram positions are readability choices, never anatomical coordinates.
const CIRCUIT_SVG_NS = 'http://www.w3.org/2000/svg';
let circuitView = null;
let circuitInitialized = false;
let circuitSelectedEdge = -1;
let circuitPathwaySignature = '';

function circuitElement(tag, attributes = {}, text = null) {
  const element = document.createElementNS(CIRCUIT_SVG_NS, tag);
  for (const [key, value] of Object.entries(attributes)) element.setAttribute(key, String(value));
  if (text !== null) element.textContent = String(text);
  return element;
}
function circuitText(id, value) {
  const element = $(id);
  if (element) element.textContent = String(value ?? '');
}
function circuitFallback(frame) {
  const count = frame.neurons.length;
  return {id: frame.model ?? 0, key: 'abstract-baseline', label: 'Brain64 · abstract baseline', scale: 1024,
    description: 'A synthetic software network. These are abstract model units, not identified fly neurons.',
    biological_basis: 'No biological reconstruction is claimed for this baseline.',
    units: Array.from({length: count}, (_, id) => ({id, label: `Unit ${String(id).padStart(2, '0')}`, group: `Units ${Math.floor(id / 12) + 1}`})),
    edges: [], sources: [], approximations: ['Seeded dynamics and synthetic watch inputs.']};
}
function circuitConnectionKind(edge) {
  if (edge.kind === 'unsigned' || edge.sign === 0) return 'unsigned';
  const coefficient = Number(edge.coefficient_q ?? edge.weight ?? 0);
  if (Number(edge.sign) < 0 || coefficient < 0 || edge.kind === 'inhibitory') return 'inhibitory';
  if (Number(edge.sign) > 0 || coefficient > 0 || edge.kind === 'excitatory') return 'excitatory';
  return 'unsigned';
}
function circuitConnectionColor(edge) {
  return {excitatory: '#99e9d5', inhibitory: '#efb1a5', unsigned: '#9eb9d9'}[circuitConnectionKind(edge)];
}
function circuitUnitLabel(model, index) {
  return model.units[index]?.label ?? `Unit ${index}`;
}
function circuitGroupLabel(unit) {
  return String(unit.group ?? 'Model units');
}
function circuitChooseNeuron(index, focus = false) {
  if (!circuitView || !Number.isInteger(index) || index < 0 || index >= circuitView.model.units.length) return;
  selectedNeuron = index;
  circuitSelectedEdge = -1;
  renderNeuron();
  renderCircuit(circuitView.frame, circuitView.model);
  if (focus) circuitView.nodes[index].group.focus();
}
function circuitNodeKey(event, index) {
  let next = index;
  if (event.key === 'ArrowRight' || event.key === 'ArrowDown') next = (index + 1) % circuitView.nodes.length;
  else if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') next = (index + circuitView.nodes.length - 1) % circuitView.nodes.length;
  else if (event.key === 'Home') next = 0;
  else if (event.key === 'End') next = circuitView.nodes.length - 1;
  else if (event.key !== 'Enter' && event.key !== ' ') return;
  event.preventDefault();
  event.stopPropagation();
  circuitChooseNeuron(next, true);
}
function circuitMakeLayout(model) {
  const groups = new Map();
  model.units.forEach((unit, index) => {
    const group = circuitGroupLabel(unit);
    if (!groups.has(group)) groups.set(group, []);
    groups.get(group).push(index);
  });
  const positions = [], lanes = [];
  const laneWidth = 880 / Math.max(1, groups.size);
  [...groups.entries()].forEach(([label, indices], groupIndex) => {
    const center = 40 + laneWidth * (groupIndex + 0.5);
    const columns = Math.min(Math.max(2, Math.ceil(Math.sqrt(indices.length))), Math.max(2, Math.floor((laneWidth - 25) / 35)));
    const rows = Math.ceil(indices.length / columns);
    const stepX = Math.min(43, (laneWidth - 32) / Math.max(1, columns - 1));
    const stepY = Math.min(49, 260 / Math.max(1, rows - 1));
    indices.forEach((index, ordinal) => {
      positions[index] = {x: center + ((ordinal % columns) - (columns - 1) / 2) * stepX,
        y: 238 + (Math.floor(ordinal / columns) - (rows - 1) / 2) * stepY};
    });
    lanes.push({label, center, width: laneWidth, count: indices.length});
  });
  return {positions, lanes};
}
function circuitBuild(model, frame, signature) {
  const svg = $('circuit-svg');
  const layout = circuitMakeLayout(model);
  svg.replaceChildren();
  svg.append(circuitElement('title', {id: 'circuit-svg-title'}, `${model.label}: selectable model units`),
    circuitElement('desc', {id: 'circuit-svg-desc'}, 'Schematic positions, not anatomical geometry. Arrow keys select units; Enter or Space inspects one. Connections and activations are from the implemented C model.'));
  const definitions = circuitElement('defs');
  const arrow = circuitElement('marker', {id: 'circuit-direction-arrow', viewBox: '0 0 8 8', refX: 20, refY: 4, markerWidth: 8, markerHeight: 8, markerUnits: 'userSpaceOnUse', orient: 'auto'});
  arrow.append(circuitElement('path', {d: 'M 0 0 L 8 4 L 0 8 Z', fill: '#a9c8cd'}));
  definitions.append(arrow); svg.append(definitions);
  const backdrop = circuitElement('g', {'aria-hidden': 'true'});
  layout.lanes.forEach(lane => {
    backdrop.append(circuitElement('rect', {x: lane.center - lane.width / 2 + 6, y: 83, width: Math.max(1, lane.width - 12), height: 305, rx: 9, fill: '#162633', opacity: '.42'}),
      circuitElement('text', {x: lane.center, y: 48, 'text-anchor': 'middle', class: 'population-label'}, lane.label),
      circuitElement('text', {x: lane.center, y: 65, 'text-anchor': 'middle', class: 'population-count'}, `${lane.count} units`));
  });
  svg.append(backdrop);
  const edgeLayer = circuitElement('g', {'aria-hidden': 'true'});
  const edges = model.edges.map((edge, index) => {
    const from = layout.positions[edge.source], to = layout.positions[edge.target];
    if (!from || !to) return null;
    let path;
    if (edge.source === edge.target) {
      path = `M ${from.x - 5} ${from.y - 7} C ${from.x - 34} ${from.y - 35}, ${from.x + 34} ${from.y - 35}, ${from.x + 5} ${from.y - 7}`;
    } else if (Math.abs(from.x - to.x) < 45) {
      const bend = from.x + (from.y < to.y ? -32 : 32);
      path = `M ${from.x} ${from.y} Q ${bend} ${(from.y + to.y) / 2} ${to.x} ${to.y}`;
    } else {
      const middle = (from.x + to.x) / 2;
      path = `M ${from.x} ${from.y} C ${middle} ${from.y}, ${middle} ${to.y}, ${to.x} ${to.y}`;
    }
    const element = circuitElement('path', {d: path, class: 'circuit-edge', 'data-circuit-edge': index});
    edgeLayer.append(element);
    return element;
  });
  svg.append(edgeLayer);
  const nodeLayer = circuitElement('g');
  const nodes = model.units.map((unit, index) => {
    const point = layout.positions[index];
    const group = circuitElement('g', {transform: `translate(${point.x} ${point.y})`, role: 'button', tabindex: '-1', 'data-circuit-neuron': index, 'data-unit-index': index, class: 'circuit-node', 'aria-pressed': 'false'});
    const hit = circuitElement('circle', {r: 19, fill: 'transparent'});
    const ring = circuitElement('circle', {r: 14, class: 'node-ring'});
    const core = circuitElement('circle', {r: 7, fill: '#2a4652', stroke: '#78949a', 'stroke-width': '1'});
    const label = circuitElement('text', {x: 0, y: 27, 'text-anchor': 'middle', class: 'node-label'}, String(unit.id ?? index).padStart(2, '0'));
    group.append(hit, ring, core, label);
    group.addEventListener('click', () => circuitChooseNeuron(index));
    group.addEventListener('keydown', event => circuitNodeKey(event, index));
    nodeLayer.append(group);
    return {group, core, ring};
  });
  svg.append(nodeLayer);
  circuitView = {model, frame, signature, nodes, edges};
  circuitSelectedEdge = -1;
  circuitPathwaySignature = '';
  circuitText('circuit-title', model.label);
  circuitText('model-description', model.description);
  circuitText('model-basis', Number(model.id) === 1 ? 'PUBLISHED MODEL TOPOLOGY' : 'ABSTRACT BASELINE');
  circuitText('model-biological-basis', model.biological_basis);
  $('model-approximations').replaceChildren();
  const approximations = Array.isArray(model.approximations) ? model.approximations : [model.approximations].filter(Boolean);
  approximations.forEach(text => {const li = document.createElement('li'); li.textContent = String(text); $('model-approximations').append(li);});
  circuitText('model-license', model.license_notice ?? '');
  $('model-license-details').hidden = Number(model.id) !== 1 || !model.license_notice;
  $('model-sources').replaceChildren();
  (model.sources ?? []).forEach(source => {
    const li = document.createElement('li');
    let valid = false;
    try {valid = new URL(source.url).protocol === 'https:';} catch (_) { /* Plain text remains safe. */ }
    if (valid) {
      const a = document.createElement('a'); a.href = source.url; a.target = '_blank'; a.rel = 'noopener noreferrer';
      a.textContent = source.title ?? source.url; li.append(a);
    } else li.textContent = source.title ?? 'Source link unavailable';
    $('model-sources').append(li);
  });
}
function circuitWeightDescription(edge, model) {
  const kind = circuitConnectionKind(edge);
  const raw = Number(edge.raw_weight ?? Math.abs(Number(edge.weight ?? 0)));
  const denominator = Number(edge.scale ?? 1);
  const implemented = Number.isFinite(Number(edge.coefficient_q)) ? Number(edge.coefficient_q) / 1024 : Number(edge.weight ?? 0) / denominator;
  const sourceStrength = kind === 'inhibitory' ? -raw : raw;
  const sourceLabel = Number(model.id) === 1 ? 'Published model strength' : 'Abstract source weight';
  return {kind, summary: `${kind} · coefficient ${implemented.toFixed(4)}`,
    detail: `${sourceLabel}: ${sourceStrength}. Normalization denominator: ${denominator}. Implemented coefficient: ${implemented.toFixed(4)}${Number.isFinite(Number(edge.coefficient_q)) ? ` (${edge.coefficient_q} / 1024)` : ''}. ${Number(model.id) === 1 ? 'Source strengths are model parameters, not measured synapse counts.' : 'Baseline contributions use signed floor division before their connection sign is applied.'} ${kind === 'unsigned' ? 'Unsigned strength does not establish excitation or inhibition.' : 'Connection sign is a model assumption, not an identified neurotransmitter.'}`};
}
function circuitRenderPathways(model) {
  const direction = $('circuit-direction').value;
  const matching = model.edges.map((edge, index) => ({edge, index})).filter(({edge}) =>
    (direction !== 'outgoing' && edge.target === selectedNeuron) || (direction !== 'incoming' && edge.source === selectedNeuron));
  if (!matching.some(item => item.index === circuitSelectedEdge)) circuitSelectedEdge = -1;
  const signature = `${circuitView.signature}|${selectedNeuron}|${direction}`;
  if (signature !== circuitPathwaySignature) {
    circuitPathwaySignature = signature;
    $('circuit-pathways').replaceChildren();
    matching.forEach(({edge, index}) => {
      const button = document.createElement('button'); button.dataset.edge = String(index);
      const title = document.createElement('span'); title.textContent = `${circuitUnitLabel(model, edge.source)} → ${circuitUnitLabel(model, edge.target)}`;
      const detail = document.createElement('small'); detail.textContent = circuitWeightDescription(edge, model).summary;
      button.append(title, detail);
      button.addEventListener('click', () => {circuitSelectedEdge = index; renderCircuit(circuitView.frame, circuitView.model);});
      $('circuit-pathways').append(button);
    });
    if (!matching.length) {const p = document.createElement('p'); p.textContent = model.edges.length ? 'No implemented connections in this direction.' : 'Connection metadata is not available in this capture.'; $('circuit-pathways').append(p);}
  }
  $('circuit-pathways').querySelectorAll('button').forEach(button => button.setAttribute('aria-pressed', String(Number(button.dataset.edge) === circuitSelectedEdge)));
  const edge = model.edges[circuitSelectedEdge];
  circuitText('circuit-edge-detail', edge ? `${circuitUnitLabel(model, edge.source)} → ${circuitUnitLabel(model, edge.target)}. ${circuitWeightDescription(edge, model).detail}` : `${matching.length} connected pathways in this view. Select one to inspect source strength and the implemented coefficient. Connection sign does not identify a neurotransmitter.`);
  circuitView.edges.forEach((path, index) => {
    if (!path) return;
    const connected = matching.some(item => item.index === index);
    path.classList.toggle('connected', connected);
    path.classList.toggle('selected', index === circuitSelectedEdge);
    if (connected) path.setAttribute('marker-end', 'url(#circuit-direction-arrow)');
    else path.removeAttribute('marker-end');
    path.style.stroke = connected ? circuitConnectionColor(model.edges[index]) : '#41606b';
    path.style.strokeDasharray = circuitConnectionKind(model.edges[index]) === 'inhibitory' ? '4 3' : 'none';
  });
}
function renderCircuit(frame, metadata) {
  if (!$('circuit-svg') || !frame || !Array.isArray(frame.neurons) || !frame.neurons.length) return;
  initCircuit();
  const model = metadata?.units?.length ? metadata : circuitFallback(frame);
  // Metadata ids are activation indices. Refuse mismatched data rather than drawing invented values.
  if (model.units.length > frame.neurons.length || (frame.node_count !== undefined && frame.node_count !== model.units.length) || model.units.some((unit, index) => Number(unit.id) !== index)) {
    circuitText('circuit-summary', 'Circuit metadata does not match this captured model. Diagram unavailable.');
    $('circuit-svg').replaceChildren(); circuitView = null; return;
  }
  if (!Array.isArray(model.edges)) model.edges = [];
  const signature = JSON.stringify([model.id, model.key, model.units.map(unit => [unit.id, unit.label, unit.group]), model.edges]);
  if (!Number.isInteger(selectedNeuron) || selectedNeuron < 0 || selectedNeuron >= model.units.length) selectedNeuron = 0;
  if (!circuitView || circuitView.signature !== signature) circuitBuild(model, frame, signature);
  circuitView.frame = frame; circuitView.model = model;
  const scale = Number(model.scale) > 0 ? Number(model.scale) : 1024;
  const peak = Math.max(scale, ...frame.neurons.slice(0, model.units.length).map(value => Math.abs(value)));
  circuitView.nodes.forEach((node, index) => {
    const value = frame.neurons[index], amount = Math.min(1, Math.abs(value) / peak);
    node.group.setAttribute('aria-pressed', String(index === selectedNeuron));
    node.group.setAttribute('tabindex', index === selectedNeuron ? '0' : '-1');
    node.group.setAttribute('aria-label', `${circuitUnitLabel(model, index)}, ${circuitGroupLabel(model.units[index])}, activation ${(value / scale).toFixed(3)}`);
    node.core.setAttribute('r', String(6 + amount * 4));
    node.core.setAttribute('fill', value < 0 ? `rgb(${Math.round(66 + 173 * amount)},${Math.round(54 + 123 * amount)},${Math.round(62 + 103 * amount)})` : `rgb(${Math.round(38 + 115 * amount)},${Math.round(67 + 166 * amount)},${Math.round(77 + 136 * amount)})`);
    node.core.setAttribute('stroke', value < 0 ? '#a7837e' : '#749f9d');
  });
  document.querySelectorAll('.cell').forEach((cell, index) => cell.tabIndex = index === selectedNeuron ? 0 : -1);
  const unit = model.units[selectedNeuron];
  circuitText('circuit-selected-label', unit.label);
  circuitText('circuit-selected-role', `${circuitGroupLabel(unit)}${unit.role ? ` · ${unit.role}` : ''}`);
  circuitText('model-basis', Number(model.id) === 1 ? 'PUBLISHED TOPOLOGY' : 'ABSTRACT BASELINE');
  circuitText('circuit-unit-count', `${model.units.length} UNITS`);
  circuitText('circuit-trace-caption', Number(model.id) === 1 ? 'MODEL ACTIVITY / CAPTURED FRAMES. Arbitrary rate units; not a measured neural recording.' : 'ACTIVATION / CAPTURED FRAMES. Signed model value; not a measured firing rate.');
  const topologySummary = model.topology_available === false ? 'topology unavailable in this replay' : `${model.edges.length} directed connections`;
  const summary = `${model.units.length} model units · ${topologySummary} · step ${frame.tick ?? 0}`;
  const hasHeading = Number(model.id) === 1 && Number.isInteger(frame.readout_heading) && frame.readout_heading >= 0;
  const readout = hasHeading ? `Peak sector ${frame.readout_heading}°` : Number(model.id) === 1 ? 'No peak sector' : 'Abstract network state';
  circuitText('circuit-readout', readout);
  circuitText('circuit-summary', `${summary}${hasHeading ? ` · strongest E-PG sector ${frame.readout_heading}° · peak ${(Number(frame.readout_strength) / scale).toFixed(3)} model units` : ''}`);
  circuitRenderPathways(model);
}
function initCircuit() {
  if (circuitInitialized || !$('circuit-svg')) return;
  circuitInitialized = true;
  $('circuit-direction').addEventListener('change', () => {
    circuitSelectedEdge = -1;
    if (circuitView) renderCircuit(circuitView.frame, circuitView.model);
  });
  $('population').addEventListener('keydown', event => {
    const cell = event.target.closest('.cell');
    if (!cell || !circuitView) return;
    const index = [...$('population').children].indexOf(cell);
    circuitNodeKey(event, index);
  });
}

initCircuit();
