// Static presentation of identified cells and measured EB synapse counts.
// No activation, dynamics, sign, efficacy or anatomical coordinates are inferred.
const ANATOMY_SVG_NS = 'http://www.w3.org/2000/svg';
const anatomyData = data.anatomy;
let anatomyMode = false;
const anatomyState = {cell: 0, edge: -1, threshold: 1, direction: 'both', draw: 'selected'};
let anatomyView = null;
const anatomyFormat = value => Number(value).toLocaleString('en-US');
const anatomyColor = kind => kind === 'EPG' ? '#99e9d5' : '#f2c781';

function anatomyValidate(dataset) {
  if (!dataset || dataset.schema_version !== 1 || !dataset.metadata ||
      !Array.isArray(dataset.nodes) || !dataset.nodes.length || !Array.isArray(dataset.links) || !dataset.links.length) return false;
  const ids = new Set(), pairs = new Set();
  for (const node of dataset.nodes) {
    if (!node || typeof node.body_id !== 'string' || !/^\d+$/.test(node.body_id) ||
        !['EPG', 'ER4m'].includes(node.class) || typeof node.instance !== 'string' || ids.has(node.body_id)) return false;
    ids.add(node.body_id);
  }
  let sum = 0;
  for (const link of dataset.links) {
    if (!link || !Number.isInteger(link.source) || !Number.isInteger(link.target) ||
        link.source < 0 || link.target < 0 || link.source >= dataset.nodes.length || link.target >= dataset.nodes.length ||
        dataset.nodes[link.source].class === dataset.nodes[link.target].class ||
        !Number.isSafeInteger(link.count) || link.count < 1 || pairs.has(`${link.source}:${link.target}`)) return false;
    pairs.add(`${link.source}:${link.target}`); sum += link.count;
  }
  return Number.isSafeInteger(sum);
}
const anatomyAvailable = anatomyValidate(anatomyData);
function anatomyElement(tag, attributes = {}, text = null) {
  const element = document.createElementNS(ANATOMY_SVG_NS, tag);
  for (const [key, value] of Object.entries(attributes)) element.setAttribute(key, String(value));
  if (text !== null) element.textContent = String(text);
  return element;
}
function anatomyText(id, value) { $(id).textContent = String(value ?? ''); }
function anatomySum(links) { return links.reduce((sum, link) => sum + link.count, 0); }
function anatomyCellLabel(index) {
  const node = anatomyData.nodes[index];
  return `${node.class} ${node.body_id}`;
}
function anatomyRetainedLinks() {
  return anatomyData.links.map((link, index) => ({...link, index})).filter(link => link.count >= anatomyState.threshold);
}
function anatomyCellLinks(links) {
  return links.filter(link => anatomyState.direction === 'incoming' ? link.target === anatomyState.cell :
    anatomyState.direction === 'outgoing' ? link.source === anatomyState.cell :
      link.source === anatomyState.cell || link.target === anatomyState.cell);
}
function anatomyVisibleLinks() {
  const retained = anatomyRetainedLinks();
  return anatomyState.draw === 'all' ? retained : anatomyCellLinks(retained);
}
function anatomyCloseSearch() {
  $('anatomy-search-results').hidden = true;
  $('anatomy-search').setAttribute('aria-expanded', 'false');
}
function anatomyChooseCell(index, focus = false) {
  if (!anatomyAvailable || !Number.isInteger(index) || index < 0 || index >= anatomyData.nodes.length) return;
  anatomyState.cell = index; anatomyState.edge = -1;
  anatomyCloseSearch();
  anatomyRender();
  if (focus) anatomyView.nodes[index].focus();
}
function anatomyNodeKey(event, index) {
  let next = index;
  if (event.key === 'ArrowRight' || event.key === 'ArrowDown') next = (index + 1) % anatomyData.nodes.length;
  else if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') next = (index + anatomyData.nodes.length - 1) % anatomyData.nodes.length;
  else if (event.key === 'Home') next = 0;
  else if (event.key === 'End') next = anatomyData.nodes.length - 1;
  else if (event.key !== 'Enter' && event.key !== ' ') return;
  event.preventDefault(); event.stopPropagation();
  anatomyChooseCell(next, true);
}
function anatomyBuild() {
  const svg = $('anatomy-svg');
  const definitions = anatomyElement('defs');
  for (const kind of ['EPG', 'ER4m']) {
    const arrow = anatomyElement('marker', {id: `anatomy-arrow-${kind}`, viewBox: '0 0 8 8', refX: 7, refY: 4,
      markerWidth: 7, markerHeight: 7, markerUnits: 'userSpaceOnUse', orient: 'auto'});
    arrow.append(anatomyElement('path', {d: 'M 0 0 L 8 4 L 0 8 Z', fill: anatomyColor(kind)}));
    definitions.append(arrow);
  }
  svg.append(definitions);
  const positions = [], labels = [], counts = {EPG: 0, ER4m: 0};
  for (const node of anatomyData.nodes) counts[node.class]++;
  const guides = anatomyElement('g', {'aria-hidden': 'true'});
  guides.append(anatomyElement('ellipse', {cx: 390, cy: 278, rx: 306, ry: 209, class: 'anatomy-guide'}),
    anatomyElement('ellipse', {cx: 390, cy: 278, rx: 137, ry: 93, class: 'anatomy-guide anatomy-guide-inner'}),
    anatomyElement('text', {x: 390, y: 25, 'text-anchor': 'middle', class: 'anatomy-field-label'}, 'EPG'),
    anatomyElement('text', {x: 390, y: 42, 'text-anchor': 'middle', class: 'anatomy-field-count'}, `${counts.EPG} identified cells · outer ring`),
    anatomyElement('text', {x: 390, y: 155, 'text-anchor': 'middle', class: 'anatomy-field-label'}, 'ER4m'),
    anatomyElement('text', {x: 390, y: 172, 'text-anchor': 'middle', class: 'anatomy-field-count'}, `${counts.ER4m} identified cells · inner ring`),
    anatomyElement('text', {x: 394, y: 282, 'text-anchor': 'middle', class: 'anatomy-center-label'}, 'EB'),
    anatomyElement('text', {x: 390, y: 302, 'text-anchor': 'middle', class: 'anatomy-center-note'}, 'ELLIPSOID BODY'),
    anatomyElement('text', {x: 390, y: 542, 'text-anchor': 'middle', class: 'anatomy-center-note'}, 'CLASS-ARRANGED SCHEMATIC / POSITIONS NOT MEASURED'));
  svg.append(guides);
  const ordinals = {EPG: 0, ER4m: 0};
  anatomyData.nodes.forEach((node, index) => {
    const ordinal = ordinals[node.class]++, outer = node.class === 'EPG';
    const angle = -Math.PI / 2 + ((ordinal + 0.5) / counts[node.class]) * Math.PI * 2;
    positions[index] = {x: 390 + Math.cos(angle) * (outer ? 306 : 137),
      y: 278 + Math.sin(angle) * (outer ? 209 : 93), angle};
    labels[index] = `${outer ? 'E' : 'R'}${String(ordinal + 1).padStart(2, '0')}`;
  });
  const edges = anatomyElement('g', {'aria-hidden': 'true'});
  svg.append(edges);
  const nodes = anatomyData.nodes.map((node, index) => {
    const {x, y, angle} = positions[index], color = anatomyColor(node.class);
    const group = anatomyElement('g', {'data-anatomy-node': index, role: 'button', tabindex: '-1',
      'aria-pressed': 'false', 'aria-label': `${anatomyCellLabel(index)}, ${node.instance}. Inspect supplied synapse counts.`});
    group.append(anatomyElement('circle', {cx: x, cy: y, r: 13, class: 'anatomy-node-halo'}));
    // A generous transparent hit area is shared by both class glyphs.
    group.append(anatomyElement('circle', {cx: x, cy: y, r: 15, fill: 'transparent'}));
    group.append(node.class === 'EPG'
      ? anatomyElement('circle', {cx: x, cy: y, r: 6.5, fill: '#193b36', stroke: color, class: 'anatomy-node-mark'})
      : anatomyElement('path', {d: `M ${x} ${y - 8} L ${x + 8} ${y} L ${x} ${y + 8} L ${x - 8} ${y} Z`,
          fill: '#413822', stroke: color, class: 'anatomy-node-mark'}));
    const offset = node.class === 'EPG' ? 21 : 19;
    group.append(anatomyElement('text', {x: x + Math.cos(angle) * offset,
      y: y + Math.sin(angle) * offset + 3, 'text-anchor': 'middle', class: 'anatomy-node-label'}, labels[index]));
    group.addEventListener('click', () => anatomyChooseCell(index));
    group.addEventListener('keydown', event => anatomyNodeKey(event, index));
    svg.append(group);
    return group;
  });
  anatomyView = {positions, edges, nodes, counts};
  const maxThreshold = Math.max(...anatomyData.links.map(link => link.count)) + 1;
  for (const id of ['anatomy-threshold', 'anatomy-threshold-range']) $(id).max = String(maxThreshold);
  anatomyText('anatomy-total-cells', anatomyFormat(anatomyData.nodes.length));
  anatomyText('anatomy-total-pairs', anatomyFormat(anatomyData.links.length));
  anatomyText('anatomy-total-synapses', anatomyFormat(anatomySum(anatomyData.links)));
  anatomyText('anatomy-legend-epg', `${counts.EPG} EPG`);
  anatomyText('anatomy-legend-er4m', `${counts.ER4m} ER4m`);
  anatomyRenderSources();
}
function anatomyPath(link) {
  const from = anatomyView.positions[link.source], to = anatomyView.positions[link.target];
  const dx = to.x - from.x, dy = to.y - from.y, distance = Math.hypot(dx, dy);
  const nx = -dy / distance, ny = dx / distance;
  // Reciprocal directions bend on opposite sides. Both endpoints are trimmed
  // to keep source glyphs and target arrowheads legible at every line width.
  const bend = 15;
  const control = {x: (from.x + to.x) / 2 + nx * bend, y: (from.y + to.y) / 2 + ny * bend};
  const sourceLength = Math.hypot(control.x - from.x, control.y - from.y);
  const targetLength = Math.hypot(to.x - control.x, to.y - control.y);
  const start = {x: from.x + (control.x - from.x) / sourceLength * 10,
    y: from.y + (control.y - from.y) / sourceLength * 10};
  const end = {x: to.x - (to.x - control.x) / targetLength * 12,
    y: to.y - (to.y - control.y) / targetLength * 12};
  return `M ${start.x.toFixed(2)} ${start.y.toFixed(2)} Q ${control.x.toFixed(2)} ${control.y.toFixed(2)} ${end.x.toFixed(2)} ${end.y.toFixed(2)}`;
}
function anatomyRenderEdges(visible) {
  anatomyView.edges.replaceChildren();
  // Draw the selected pair last so its exact direction stays inspectable.
  const ordered = [...visible].sort((a, b) => Number(a.index === anatomyState.edge) - Number(b.index === anatomyState.edge));
  for (const link of ordered) {
    const selectedCellPair = link.source === anatomyState.cell || link.target === anatomyState.cell;
    const selectedPair = link.index === anatomyState.edge;
    const kind = anatomyData.nodes[link.source].class;
    anatomyView.edges.append(anatomyElement('path', {'data-anatomy-link': link.index,
      class: `anatomy-link${selectedPair ? ' selected' : ''}`, d: anatomyPath(link),
      stroke: anatomyColor(kind), 'stroke-width': link.count < 10 ? 1 : link.count < 50 ? 2 : 3,
      opacity: selectedCellPair ? '.72' : '.12', 'marker-end': `url(#anatomy-arrow-${kind})`}));
  }
  anatomyView.nodes.forEach((node, index) => {
    node.setAttribute('aria-pressed', String(index === anatomyState.cell));
    node.setAttribute('tabindex', index === anatomyState.cell ? '0' : '-1');
  });
}
function anatomyRenderPair() {
  const panel = $('anatomy-pair-detail');
  panel.replaceChildren();
  const edge = anatomyData.links[anatomyState.edge];
  if (!edge) {
    panel.textContent = 'Select a measured pair to inspect its exact count and direction. Missing or filtered pairs are not evidence of absence.';
    return;
  }
  const title = document.createElement('b');
  title.textContent = `${anatomyCellLabel(edge.source)} → ${anatomyCellLabel(edge.target)}`;
  const count = document.createElement('p');
  count.textContent = `${anatomyFormat(edge.count)} synapses in the supplied EB projection.`;
  const reverse = anatomyData.links.find(link => link.source === edge.target && link.target === edge.source);
  const reciprocal = document.createElement('p');
  reciprocal.textContent = reverse
    ? `Reverse direction: ${anatomyFormat(reverse.count)} synapses in the full supplied projection${reverse.count < anatomyState.threshold ? ' (below the current display threshold)' : ''}.`
    : 'Reverse direction is not supplied in this projection; this is not evidence of absence.';
  const note = document.createElement('p');
  note.textContent = 'Count only. Sign, neurotransmitter and electrical efficacy are not supplied.';
  const partner = edge.source === anatomyState.cell ? edge.target : edge.source;
  const inspect = document.createElement('button');
  inspect.textContent = `Inspect partner ${anatomyData.nodes[partner].body_id} →`;
  inspect.addEventListener('click', () => anatomyChooseCell(partner, true));
  panel.append(title, count, reciprocal, note, inspect);
}
function anatomyRenderPartners(links) {
  const container = $('anatomy-pathways');
  const focused = container.contains(document.activeElement) ? document.activeElement.dataset.anatomyEdge : null;
  container.replaceChildren();
  const ordered = [...links].sort((a, b) => b.count - a.count || a.index - b.index);
  anatomyText('anatomy-partner-caption', `${anatomyFormat(links.length)} retained directed pairs · ${anatomyFormat(anatomySum(links))} synapses · sorted by count`);
  if (!ordered.length) {
    const empty = document.createElement('p');
    empty.textContent = 'No supplied pairs meet this direction and threshold. Try a lower threshold or another cell.';
    container.append(empty);
  }
  for (const link of ordered) {
    const incoming = link.target === anatomyState.cell;
    const partner = anatomyData.nodes[incoming ? link.source : link.target];
    const button = document.createElement('button');
    button.dataset.anatomyEdge = String(link.index);
    button.setAttribute('aria-pressed', String(link.index === anatomyState.edge));
    button.setAttribute('aria-label', `${anatomyCellLabel(link.source)} to ${anatomyCellLabel(link.target)}: ${link.count} synapses. Inspect pair.`);
    const label = document.createElement('span');
    label.textContent = `${incoming ? '←' : '→'} ${partner.class} ${partner.body_id}`;
    const direction = document.createElement('small');
    direction.textContent = incoming ? 'INCOMING · partner → selected cell' : 'OUTGOING · selected cell → partner';
    label.append(direction);
    const count = document.createElement('span');
    count.className = 'anatomy-partner-count'; count.textContent = anatomyFormat(link.count);
    const unit = document.createElement('small'); unit.textContent = 'SYNAPSES'; count.append(unit);
    button.append(label, count);
    button.addEventListener('click', () => {anatomyState.edge = link.index; anatomyRender();});
    container.append(button);
  }
  if (focused !== null) container.querySelector(`[data-anatomy-edge="${focused}"]`)?.focus();
}
function anatomyRender() {
  if (!anatomyAvailable) return;
  if (!anatomyView) anatomyBuild();
  const retained = anatomyRetainedLinks(), cellLinks = anatomyCellLinks(retained);
  if (!cellLinks.some(link => link.index === anatomyState.edge)) anatomyState.edge = -1;
  const visible = anatomyState.draw === 'all' ? retained : cellLinks;
  const node = anatomyData.nodes[anatomyState.cell];
  anatomyText('anatomy-cell-class', node.class);
  $('anatomy-cell-class').dataset.class = node.class;
  anatomyText('anatomy-cell-id', node.body_id);
  anatomyText('anatomy-cell-instance', `Instance: ${node.instance}`);
  anatomyText('anatomy-cell-incoming', anatomyFormat(anatomySum(anatomyData.links.filter(link => link.target === anatomyState.cell))));
  anatomyText('anatomy-cell-outgoing', anatomyFormat(anatomySum(anatomyData.links.filter(link => link.source === anatomyState.cell))));
  anatomyText('anatomy-visible-totals', `ON CANVAS · ${anatomyFormat(visible.length)} directed pairs · ${anatomyFormat(anatomySum(visible))} synapses · ${anatomyState.draw === 'all' ? 'all retained pairs; direction filter applies to the inspector only' : `${anatomyState.direction === 'both' ? 'incoming + outgoing' : anatomyState.direction} for the selected cell`}`);
  anatomyText('anatomy-filter-totals', `DATASET FILTER · ${anatomyFormat(retained.length)} / ${anatomyFormat(anatomyData.links.length)} supplied pairs · ${anatomyFormat(anatomySum(retained))} / ${anatomyFormat(anatomySum(anatomyData.links))} supplied synapses retained at ≥ ${anatomyFormat(anatomyState.threshold)} per pair. All ${anatomyData.nodes.length} cells remain shown.`);
  anatomyRenderEdges(visible); anatomyRenderPartners(cellLinks); anatomyRenderPair();
}
function anatomySourceLink(container, label, url) {
  if (typeof url !== 'string') return;
  let parsed;
  try { parsed = new URL(url); } catch (_) { return; }
  if (parsed.protocol !== 'https:' && parsed.protocol !== 'http:') return;
  const li = document.createElement('li'), link = document.createElement('a');
  link.href = url; link.textContent = label; link.target = '_blank'; link.rel = 'noopener noreferrer';
  li.append(link); container.append(li);
}
function anatomyRenderSources() {
  const metadata = anatomyData.metadata, source = metadata.source || {}, license = metadata.license || {};
  anatomyText('anatomy-boundary', metadata.boundary);
  anatomyText('anatomy-source-title', metadata.title);
  anatomyText('anatomy-source-revision', `${metadata.dataset || 'Source dataset'} · ${metadata.roi || 'EB'} ROI · pinned source revision ${source.commit || 'not supplied'}`);
  $('anatomy-limitations').replaceChildren();
  for (const limitation of Array.isArray(metadata.limitations) ? metadata.limitations : []) {
    const item = document.createElement('li'); item.textContent = String(limitation); $('anatomy-limitations').append(item);
  }
  $('anatomy-sources').replaceChildren();
  anatomySourceLink($('anatomy-sources'), 'Hulse et al. (2021) · The connectome of the Drosophila central complex', source.paper);
  anatomySourceLink($('anatomy-sources'), 'Hemibrain dataset · primary reconstruction paper', source.hemibrain_paper);
  anatomySourceLink($('anatomy-sources'), 'Source repository · supplied projection tables', source.repository);
  const licenseContainer = $('anatomy-license'); licenseContainer.replaceChildren();
  const licenseLabel = document.createElement('span'); licenseLabel.textContent = `Data license: ${license.id || 'not supplied'}. `;
  licenseContainer.append(licenseLabel);
  for (const [label, url] of [['Read license', license.url], ['Source license notice', license.source]]) {
    if (typeof url !== 'string' || !/^https?:\/\//.test(url)) continue;
    const link = document.createElement('a'); link.href = url; link.textContent = label;
    link.target = '_blank'; link.rel = 'noopener noreferrer'; licenseContainer.append(link, document.createTextNode(' · '));
  }
  anatomyText('anatomy-attribution', [license.attribution, license.changes].filter(Boolean).join('\n\n'));
  anatomyText('anatomy-code-license', license.repository_code_license);
}
function anatomySearch() {
  const query = $('anatomy-search').value.trim().toLowerCase();
  const container = $('anatomy-search-results'); container.replaceChildren();
  if (!query) {
    anatomyCloseSearch(); anatomyText('anatomy-search-status', 'Search the supplied cells. Body IDs are preserved exactly.'); return;
  }
  const matches = anatomyData.nodes.map((node, index) => ({node, index})).filter(({node}) =>
    `${node.body_id} ${node.class} ${node.instance}`.toLowerCase().includes(query));
  anatomyText('anatomy-search-status', matches.length ? `${matches.length} matching cells. Choose a result or press Enter for the first.` : 'No matching supplied cells. Try a body ID, instance or class.');
  for (const {node, index} of matches) {
    const button = document.createElement('button'), label = document.createElement('span'), kind = document.createElement('span');
    label.textContent = node.body_id;
    const instance = document.createElement('small'); instance.textContent = node.instance; label.append(instance);
    kind.className = 'anatomy-search-class'; kind.textContent = node.class;
    button.append(label, kind);
    button.addEventListener('click', () => {
      $('anatomy-search').value = node.body_id;
      anatomyText('anatomy-search-status', `Selected ${node.class} ${node.body_id}.`);
      anatomyChooseCell(index, true);
    });
    button.addEventListener('keydown', event => {
      if (event.key === 'Escape') {event.preventDefault(); anatomyCloseSearch(); $('anatomy-search').focus();}
      else if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
        event.preventDefault();
        const buttons = [...container.children], current = buttons.indexOf(button);
        buttons[(current + (event.key === 'ArrowDown' ? 1 : buttons.length - 1)) % buttons.length].focus();
      }
    });
    container.append(button);
  }
  container.hidden = !matches.length;
  $('anatomy-search').setAttribute('aria-expanded', String(matches.length > 0));
}
function anatomyApplyThreshold(value) {
  const threshold = Number(value), max = Number($('anatomy-threshold').max);
  if (String(value).trim() === '' || !Number.isSafeInteger(threshold) || threshold < 1 || threshold > max) {
    $('anatomy-threshold').setAttribute('aria-invalid', 'true');
    anatomyText('anatomy-threshold-hint', `Enter a whole number from 1 to ${anatomyFormat(max)}. Still showing threshold ${anatomyFormat(anatomyState.threshold)}.`);
    return;
  }
  anatomyState.threshold = threshold;
  $('anatomy-threshold').value = String(threshold); $('anatomy-threshold-range').value = String(threshold);
  $('anatomy-threshold').setAttribute('aria-invalid', 'false');
  anatomyText('anatomy-threshold-hint', 'Display filter only. The supplied dataset is unchanged.');
  anatomyRender();
}
function anatomyExportData() {
  const links = anatomyVisibleLinks().map(({source, target, count}) => ({source, target, count}));
  return {schema_version: 1, scope: 'static-measured-anatomy', metadata: anatomyData.metadata,
    nodes: anatomyData.nodes, links,
    full_supplied_totals: {node_count: anatomyData.nodes.length, edge_count: anatomyData.links.length,
      synapse_count_sum: anatomySum(anatomyData.links)},
    visible_totals: {edge_count: links.length, synapse_count_sum: anatomySum(links)},
    filter: {minimum_synapses: anatomyState.threshold, draw: anatomyState.draw, inspector_direction: anatomyState.direction,
      selected_body_id: anatomyData.nodes[anatomyState.cell].body_id,
      boundary: 'Only the supplied cross-class EB projection is eligible. This export contains the directed pairs on canvas and all supplied cell identities; missing pairs do not establish absence. The direction filter affects the canvas only in selected-cell mode.'}};
}
function enterAnatomy() {
  if (!anatomyAvailable || anatomyMode) return;
  if (typeof userLensSelected !== 'undefined') userLensSelected = true;
  if (typeof leaveReference === 'function') leaveReference();
  if (typeof leaveExperiments === 'function') leaveExperiments();
  pause();
  if (liveMode) liveReleaseAll(false);
  liveMode = false; anatomyMode = true;
  document.body.dataset.lens = 'anatomy';
  for (const selector of ['.workspace', '.playback', '.below', '#live-controls']) document.querySelector(selector).hidden = true;
  $('anatomy-lens').hidden = false;
  $('anatomy-mode').setAttribute('aria-pressed', 'true');
  $('live-mode').setAttribute('aria-pressed', 'false');
  document.querySelectorAll('.scenario').forEach(button => button.setAttribute('aria-pressed', 'false'));
  anatomyText('mode-badge', 'MEASURED / STATIC');
  anatomyText('intro-eyebrow', 'STRUCTURE → IDENTIFIED CELLS → MEASURED COUNTS');
  anatomyText('scenario-title', `${anatomyData.nodes.length} identified cells. One measured projection.`);
  anatomyText('scenario-summary', 'Inspect individual EPG and ER4m cells from the published hemibrain-derived central-complex dataset. Follow directed synapse counts within the ellipsoid body. This is a bounded structural view, with no simulated neural activity.');
  anatomyText('build-tag', 'PUBLISHED CONNECTIVITY\nSTATIC COUNTS · NO DYNAMICS');
  anatomyText('footer-mode', 'OFFLINE BY CONSTRUCTION · PINNED MEASURED DATA');
  anatomyText('footer-keys', 'ARROW KEYS SELECT CELLS · ENTER INSPECTS');
  anatomyRender();
}
function leaveAnatomy() {
  if (!anatomyMode) return;
  anatomyMode = false; delete document.body.dataset.lens;
  anatomyCloseSearch(); $('anatomy-lens').hidden = true;
  $('anatomy-mode').setAttribute('aria-pressed', 'false');
  for (const selector of ['.workspace', '.playback', '.below']) document.querySelector(selector).hidden = false;
  anatomyText('intro-eyebrow', 'Stimulus → dynamics → readout');
  $('build-tag').replaceChildren(document.createTextNode('PORTABLE C → WEBASSEMBLY'), document.createElement('br'), document.createTextNode('SYNTHETIC INPUTS · NO DEVICE'));
  anatomyText('footer-mode', 'OFFLINE BY CONSTRUCTION · REPLAYABLE C COMMANDS');
  anatomyText('footer-keys', '← / → STEP   SPACE PLAY   HOME / END');
}
if (anatomyAvailable) {
  $('anatomy-mode').disabled = false;
  anatomyText('anatomy-status', `${anatomyData.nodes.length} cells · ${anatomyFormat(anatomyData.links.length)} directed EB pairs. No simulation.`);
  $('anatomy-mode').addEventListener('click', enterAnatomy);
  $('anatomy-search').addEventListener('input', anatomySearch);
  $('anatomy-search').addEventListener('keydown', event => {
    if (event.key === 'Escape') {event.preventDefault(); anatomyCloseSearch();}
    else if ((event.key === 'Enter' || event.key === 'ArrowDown') && !$('anatomy-search-results').hidden) {
      event.preventDefault();
      const first = $('anatomy-search-results').querySelector('button');
      if (event.key === 'Enter') first?.click(); else first?.focus();
    }
  });
  document.addEventListener('click', event => {if (!event.target.closest('.anatomy-search-box')) anatomyCloseSearch();});
  $('anatomy-threshold').addEventListener('input', () => anatomyApplyThreshold($('anatomy-threshold').value));
  $('anatomy-threshold-range').addEventListener('input', () => anatomyApplyThreshold($('anatomy-threshold-range').value));
  $('anatomy-direction').addEventListener('change', () => {
    const value = $('anatomy-direction').value;
    if (!['both', 'incoming', 'outgoing'].includes(value)) return;
    anatomyState.direction = value; anatomyRender();
  });
  $('anatomy-draw').addEventListener('change', () => {
    const value = $('anatomy-draw').value;
    if (!['selected', 'all'].includes(value)) return;
    anatomyState.draw = value; anatomyRender();
  });
  $('anatomy-export').addEventListener('click', () => {
    const blob = new Blob([JSON.stringify(anatomyExportData(), null, 2)], {type: 'application/json'});
    const url = URL.createObjectURL(blob), anchor = document.createElement('a');
    anchor.href = url; anchor.download = 'flywatch-measured-anatomy-visible.json'; anchor.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  });
} else {
  anatomyText('anatomy-status', anatomyData ? 'Measured dataset unavailable: unsupported or invalid data.' : 'Measured data was not included in this bundle.');
}
