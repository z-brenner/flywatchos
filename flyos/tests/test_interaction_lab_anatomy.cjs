/* Static anatomy DOM tests use a small, explicitly synthetic data fixture.
 * No anatomy measurements, Wasm behavior, browser layout or screenshot proof
 * are inferred from this test. Full-bundle lifecycle tests live separately.
 * node flyos/tests/test_interaction_lab_anatomy.cjs [path/to/node_modules/jsdom]
 */
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const {JSDOM} = require(process.argv[2] ? path.resolve(process.argv[2]) : 'jsdom');
const source = path.resolve(__dirname, '../tools');
const html = fs.readFileSync(path.join(source, 'interaction_lab.html'), 'utf8')
  .replace(/<script[\s\S]*?<\/script>/g, '');
const fixture = {
  schema_version: 1,
  metadata: {
    title: 'Fixture <img src=x onerror=alert(1)>', roi: 'EB',
    boundary: 'Only the supplied directed cross-class EB projection.',
    limitations: ['Within-class and external connections are not supplied.'],
    source: {paper: 'https://example.org/paper', repository: 'javascript:alert(1)', commit: 'fixture'},
    license: {id: 'CC-BY-4.0', url: 'https://creativecommons.org/licenses/by/4.0/',
      attribution: 'Fixture attribution', changes: 'Fixture changes', repository_code_license: 'Fixture: data license does not license upstream analysis code.', source: 'https://example.org/license'}
  },
  nodes: [
    {body_id: '10000000001', class: 'EPG', instance: 'EPG_a'},
    {body_id: '10000000002', class: 'EPG', instance: 'EPG_b'},
    {body_id: '10000000003', class: 'ER4m', instance: 'ER4m_a'},
    {body_id: '10000000004', class: 'ER4m', instance: 'ER4m_b'}
  ],
  links: [
    {source: 0, target: 2, count: 10}, {source: 2, target: 0, count: 40},
    {source: 1, target: 2, count: 3}, {source: 3, target: 0, count: 2},
    {source: 1, target: 3, count: 60}
  ]
};
function makeDom(dataset = fixture) {
  const dom = new JSDOM(html, {runScripts: 'outside-only'}), w = dom.window;
  w.data = {anatomy: dataset};
  w.eval(`var $=id=>document.getElementById(id); var liveMode=true; var released=0; var paused=0;
    function pause(){paused++;} function liveReleaseAll(){released++;}`);
  const filename = path.join(source, 'interaction_lab_anatomy.js');
  w.eval(fs.existsSync(filename) ? fs.readFileSync(filename, 'utf8') : '');
  return dom;
}
const dom = makeDom(), w = dom.window, d = w.document, $ = id => d.getElementById(id);
const input = id => $(id).dispatchEvent(new w.Event('input', {bubbles: true}));
const change = id => $(id).dispatchEvent(new w.Event('change', {bubbles: true}));
try {
  assert.equal(typeof w.enterAnatomy, 'function', 'static anatomy entry hook exists');
  assert.equal($('anatomy-mode').disabled, false, 'measured data does not require Wasm');
  $('anatomy-mode').click();
  assert.equal(d.body.dataset.lens, 'anatomy');
  assert.equal(w.eval('liveMode'), false);
  assert.equal(w.released, 1, 'entry releases any active live controls');
  assert.ok(w.paused > 0, 'entry pauses the existing timer');
  assert.equal($('anatomy-lens').hidden, false);
  for (const selector of ['.workspace', '.playback', '.below', '#live-controls']) {
    assert.equal(d.querySelector(selector).hidden, true, `${selector} stays out of the static lens`);
  }
  assert.equal(d.querySelectorAll('[data-anatomy-node]').length, 4);
  assert.equal(d.querySelectorAll('[data-anatomy-node][tabindex="0"]').length, 1);
  assert.equal($('anatomy-cell-id').textContent, '10000000001');
  assert.match($('anatomy-dataset-totals').textContent, /4.*5.*115/s);
  assert.equal(d.querySelectorAll('#anatomy-pathways button[data-anatomy-edge]').length, 3);
  assert.equal(d.querySelectorAll('[data-anatomy-link]').length, 3, 'default drawing contains selected-cell pairs');
  assert.equal(d.querySelector('[data-anatomy-link="0"]').getAttribute('marker-end'), 'url(#anatomy-arrow-EPG)');
  assert.equal(d.querySelector('[data-anatomy-link="1"]').getAttribute('marker-end'), 'url(#anatomy-arrow-ER4m)');
  d.querySelector('[data-anatomy-edge="0"]').click();
  assert.match($('anatomy-pair-detail').textContent, /10000000001.*→.*10000000003/s);
  assert.match($('anatomy-pair-detail').textContent, /10 synapses/);
  assert.match($('anatomy-pair-detail').textContent, /40 synapses/);

  $('anatomy-direction').value = 'outgoing'; change('anatomy-direction');
  assert.equal(d.querySelectorAll('[data-anatomy-edge]').length, 1);
  $('anatomy-threshold').value = '11'; input('anatomy-threshold');
  assert.equal(d.querySelectorAll('[data-anatomy-edge]').length, 0);
  assert.match($('anatomy-pathways').textContent, /No supplied pairs meet/);
  assert.match($('anatomy-visible-totals').textContent, /0.*pairs.*0.*synapses/s);
  assert.match($('anatomy-filter-totals').textContent, /2.*5.*100.*115/s);
  assert.match($('anatomy-pair-detail').textContent, /not evidence of absence/);
  $('anatomy-threshold').value = '-1'; input('anatomy-threshold');
  assert.equal($('anatomy-threshold').getAttribute('aria-invalid'), 'true');
  assert.match($('anatomy-filter-totals').textContent, /2.*5.*100.*115/s, 'invalid threshold does not change the applied filter');
  $('anatomy-threshold').value = ''; input('anatomy-threshold');
  assert.equal($('anatomy-threshold').getAttribute('aria-invalid'), 'true');
  $('anatomy-threshold').value = '1.5'; input('anatomy-threshold');
  assert.equal($('anatomy-threshold').getAttribute('aria-invalid'), 'true');
  $('anatomy-threshold').value = '1'; input('anatomy-threshold');
  assert.equal($('anatomy-threshold').getAttribute('aria-invalid'), 'false');

  $('anatomy-search').value = '10000000004'; input('anatomy-search');
  d.querySelector('#anatomy-search-results button').click();
  assert.equal($('anatomy-cell-id').textContent, '10000000004');
  assert.equal($('anatomy-search-results').hidden, true);
  d.querySelector('[data-anatomy-edge="3"]').click();
  assert.match($('anatomy-pair-detail').textContent, /Reverse direction is not supplied/);
  assert.doesNotMatch($('anatomy-pair-detail').textContent, /0 synapses/);
  $('anatomy-search').value = '<img src=x onerror=alert(1)>'; input('anatomy-search');
  assert.match($('anatomy-search-status').textContent, /No matching/);
  assert.equal(d.querySelectorAll('#anatomy-search-results img').length, 0);
  $('anatomy-search').value = 'EPG'; input('anatomy-search');
  assert.equal(d.querySelectorAll('#anatomy-search-results button').length, 2);
  $('anatomy-search').dispatchEvent(new w.KeyboardEvent('keydown', {key: 'Escape', bubbles: true}));
  assert.equal($('anatomy-search-results').hidden, true);

  d.querySelector('[data-anatomy-node="3"]').dispatchEvent(new w.KeyboardEvent('keydown', {
    key: 'ArrowRight', bubbles: true, cancelable: true
  }));
  assert.equal($('anatomy-cell-id').textContent, '10000000001');
  assert.equal(d.activeElement.getAttribute('data-anatomy-node'), '0');
  assert.equal(d.querySelectorAll('[data-anatomy-node][tabindex="0"]').length, 1);
  $('anatomy-direction').value = 'both'; change('anatomy-direction');
  $('anatomy-draw').value = 'all'; change('anatomy-draw');
  assert.equal(d.querySelectorAll('[data-anatomy-link]').length, 5);
  assert.match($('anatomy-visible-totals').textContent, /5.*pairs.*115.*synapses/s);

  const exported = w.anatomyExportData();
  assert.equal(exported.scope, 'static-measured-anatomy');
  assert.equal(exported.links.length, 5);
  assert.equal(exported.nodes.length, 4);
  assert.equal(exported.metadata.license.attribution, 'Fixture attribution');
  assert.equal(exported.activation, undefined);
  assert.equal(exported.frames, undefined);
  assert.match(exported.filter.boundary, /supplied/);
  assert.equal(d.querySelectorAll('#anatomy-sources a').length, 1, 'unsafe source URL is not turned into a link');
  assert.equal($('anatomy-attribution').textContent.includes('Fixture attribution'), true);
  assert.ok($('anatomy-code-license'), 'repository-code license distinction is shown');
  assert.equal($('anatomy-code-license').textContent, fixture.metadata.license.repository_code_license);
  assert.equal($('anatomy-source-title').textContent, fixture.metadata.title, 'metadata is rendered as text');
  assert.equal(d.querySelectorAll('#anatomy-source-title img').length, 0);
  w.leaveAnatomy();
  assert.equal(d.body.dataset.lens, undefined);
  assert.equal($('anatomy-lens').hidden, true);
  for (const selector of ['.workspace', '.playback', '.below']) assert.equal(d.querySelector(selector).hidden, false);

  for (const invalid of [null, {...fixture, schema_version: 2}, {...fixture, links: [{source: 0, target: 2, count: 0}]},
    {...fixture, links: [{source: 0, target: 4, count: 3}]}, {...fixture, links: [{source: 0, target: 1, count: 3}]}]) {
    const broken = makeDom(invalid);
    try {
      assert.equal(broken.window.document.getElementById('anatomy-mode').disabled, true, 'missing/invalid anatomy fails closed');
      assert.equal(broken.window.document.getElementById('anatomy-lens').hidden, true);
    } finally { broken.window.close(); }
  }
  console.log('PASS: static anatomy cells, directed measured counts, honest filters, pair inspection, body-ID search, keyboard focus, metadata safety, CC BY attribution, static export and missing-data fallback. Browser layout unverified.');
} finally { w.close(); }
