/* Isolated DOM regression tests for the circuit presentation layer.
 * Uses explicit test fixtures, not biological evidence or a native/Wasm run.
 * No browser layout, SVG appearance, touch or screenshot coverage is claimed.
 *
 * From the repository root:
 * node flyos/tests/test_interaction_lab_circuit.cjs /path/to/node_modules/jsdom
 * Omit the dependency path when jsdom is available through normal resolution.
 */
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const {JSDOM} = require(process.argv[2] ? path.resolve(process.argv[2]) : 'jsdom');
const source = path.resolve(__dirname, '../tools');
const html = fs.readFileSync(path.join(source, 'interaction_lab.html'), 'utf8')
  .replace(/<script[\s\S]*?<\/script>/g, '');
const dom = new JSDOM(html, {runScripts: 'outside-only'});
const w = dom.window;
const d = w.document;
const $ = id => d.getElementById(id);
try {
  // The surrounding app owns selection and the selected-unit sparkline.
  w.eval('var selectedNeuron=1; var renderCalls=0; var $=id=>document.getElementById(id); function renderNeuron(){renderCalls++;}');
  w.eval(fs.readFileSync(path.join(source, 'interaction_lab_circuit.js'), 'utf8'));
  assert.equal(typeof w.renderCircuit, 'function', 'circuit renderer hook is exposed');
  const model = {
    id: 0, key: 'baseline', label: 'Abstract baseline',
    description: 'Test <img src=x onerror=alert(1)>',
    biological_basis: 'Abstract software model', scale: 1024,
    units: Array.from({length: 64}, (_, id) => ({id, label: `Unit ${id}`, group: `Group ${Math.floor(id / 12)}`})),
    edges: [
      {source: 0, target: 1, weight: 1, raw_weight: 1, scale: 4, coefficient_q: 256, kind: 'excitatory'},
      {source: 1, target: 2, weight: -1, raw_weight: 1, scale: 8, coefficient_q: -128, kind: 'inhibitory'}
    ],
    sources: [
      {title: 'Unsafe', url: 'javascript:alert(1)'},
      {title: 'Safe source', url: 'https://example.org/paper'}
    ],
    approximations: ['Synthetic test only'], topology_available: true
  };
  const frame = {model: 0, tick: 1, neurons: Array.from({length: 64}, (_, i) => i === 1 ? 1024 : 0)};
  w.renderCircuit(frame, model);
  assert.equal(d.querySelectorAll('[data-circuit-neuron]').length, 64);
  assert.equal(d.querySelectorAll('[data-circuit-neuron][tabindex="0"]').length, 1);
  assert.equal($('circuit-selected-label').textContent, 'Unit 1');
  assert.equal(d.querySelectorAll('#model-sources a').length, 1, 'unsafe citation URLs are not links');
  assert.equal(d.querySelectorAll('#model-description img').length, 0, 'metadata is rendered as text');
  assert.equal($('model-description').textContent, model.description);

  // A negative connection retains its signed source strength and actual Q10 coefficient.
  d.querySelector('#circuit-pathways button[data-edge="1"]').click();
  assert.match($('circuit-edge-detail').textContent, /weight: -1/);
  assert.match($('circuit-edge-detail').textContent, /Implemented coefficient: -0\.1250 \(-128 \/ 1024\)/);
  assert.ok(d.querySelector('marker[id="circuit-direction-arrow"]'), 'directed connections have arrowheads');
  assert.equal(d.querySelector('[data-circuit-edge="1"]').getAttribute('marker-end'), 'url(#circuit-direction-arrow)');

  // Keyboard navigation changes the app selection and moves focus with its roving tab stop.
  d.querySelector('[data-circuit-neuron="1"]').dispatchEvent(new w.KeyboardEvent('keydown', {
    key: 'ArrowRight', bubbles: true, cancelable: true
  }));
  assert.equal(w.eval('selectedNeuron'), 2);
  assert.equal(d.activeElement.getAttribute('data-circuit-neuron'), '2');
  d.querySelector('[data-circuit-neuron="0"]').dispatchEvent(new w.MouseEvent('click', {bubbles: true}));
  assert.equal(w.eval('selectedNeuron'), 0);
  assert.ok(w.eval('renderCalls') >= 2);
  assert.match($('circuit-pathways').textContent, /Unit 1/);

  // Direction filters must describe only the actual supplied connections.
  $('circuit-direction').value = 'incoming';
  $('circuit-direction').dispatchEvent(new w.Event('change', {bubbles: true}));
  assert.equal(d.querySelectorAll('#circuit-pathways button').length, 0);
  $('circuit-direction').value = 'both';
  $('circuit-direction').dispatchEvent(new w.Event('change', {bubbles: true}));
  assert.equal(d.querySelectorAll('#circuit-pathways button').length, 1);

  // A smaller model changes visible identities; unsigned strengths remain explicitly unsigned.
  const small = {
    ...model, id: 1, key: 'small', license_notice: 'MIT License\nCopyright test',
    units: model.units.slice(0, 3),
    edges: [{source: 0, target: 2, weight: 5, scale: 10, kind: 'unsigned'}]
  };
  w.eval('selectedNeuron=63');
  w.renderCircuit({...frame, model: 1, neurons: [0, 128, 256]}, small);
  assert.equal(d.querySelectorAll('[data-circuit-neuron]').length, 3);
  assert.equal($('model-license').textContent, small.license_notice, 'full license notice is readable text');
  assert.equal($('model-license-details').hidden, false);
  assert.equal(w.eval('selectedNeuron'), 0);
  assert.ok(d.querySelector('.circuit-node[data-unit-index="0"]'));
  assert.match($('circuit-pathways').textContent, /unsigned/i);
  assert.equal(d.querySelectorAll('[data-circuit-neuron][tabindex="0"]').length, 1);

  // A fixed-width ABI may pad its activation buffer; padding is never presented as real units.
  const padded = {...frame, model: 1, node_count: 3, neurons: [0, 128, 256, ...Array(61).fill(0)]};
  w.renderCircuit(padded, small);
  assert.equal(d.querySelectorAll('[data-circuit-neuron]').length, 3, 'padding is not rendered as neurons');

  // Replay-only captures lack connection metadata; this is different from a zero-edge network.
  w.renderCircuit(frame, {...model, edges: [], topology_available: false});
  assert.match($('circuit-summary').textContent, /topology unavailable/);
  assert.doesNotMatch($('circuit-summary').textContent, /0 directed connections/);
  assert.equal($('model-license-details').hidden, true);

  console.log('PASS: circuit DOM rendering, safe metadata/URLs, signed source weights and Q10 coefficients, arrowheads, keyboard/focus, pathway filters, model counts, padded activations, license notice and unavailable-topology fallback. Browser layout unverified.');
} finally {
  w.close();
}
