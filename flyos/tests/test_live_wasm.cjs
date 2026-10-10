#!/usr/bin/env node
'use strict';
/* Exact C-native vs C-Wasm differential test. JS generates fixture commands
 * and reads the exported buffers; it contains no neural or renderer model. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const {spawnSync} = require('node:child_process');

assert.equal(process.argv.length, 4, 'usage: node test_live_wasm.cjs module.wasm native-trace');
const module_ = new WebAssembly.Module(fs.readFileSync(process.argv[2]));
assert.deepEqual(WebAssembly.Module.imports(module_), [], 'module must need no host/WASI imports');
const api = new WebAssembly.Instance(module_).exports;
assert.equal(api.memory.buffer.byteLength, 131072);
assert.throws(() => api.memory.grow(1), RangeError);

const commands = [
  ['R', 0x245f1a5], ['T'],
  ['E', 1, 0], ['T'], ['E', 1, 1], ['E', 1, 2], ['T'], ['T'],
  ['E', 3, 0], ['E', 4, 0], ['T'], ['C', 2, 0, 1], ['T'],
  ['E', 3, 2], ['E', 4, 2], ['T'], ['T'], ['C', 1, 1, 1], ['T'],
  ['C', 0, 0, 1], ['T'], ['C', 1, 0, 1], ['T'], ['T'],
  ['E', 0, 0], ['E', 0, 1], ['E', 0, 2], ['E', 2, 0],
  ['E', 1, 0], ['E', 2, 2], ['E', 1, 1], ['E', 1, 2], ['T'],
  ['C', 2, 0, 1], ['E', 3, 0], ['C', 1, 0, 1], ['E', 3, 2], ['T'],
  ['S', 15, 300, -300, -32768, 100, 1], ...Array.from({length: 24}, () => ['T']),
  ['S', 15, 0, 300, 32767, 0, 0], ['T'],
  ['S', 0, 300, 300, 32767, 100, 1], ['T'],
  ['E', -1, 0], ['E', 5, 0], ['E', 1, -1], ['E', 1, 3],
  ['E', 2147483647, -2147483648], ['E', 3, 2], ['T'],
  ['C', -1, 0, 1], ['C', 3, 0, 1], ['C', 1, 2, 1], ['C', 1, 0, 2],
  ['S', 16, 0, 0, 0, 0, 0], ['S', 15, 301, 0, 0, 0, 0],
  ['S', 15, 0, -301, 0, 0, 0], ['S', 15, 0, 0, 32768, 0, 0],
  ['S', 15, 0, 0, 0, 101, 0], ['S', 15, 0, 0, 0, 0, 2], ['T'],
  ['R', 0], ['T'], ['R', 0xffffffff], ['T'],
  ['M', 1, 0], ['T'], ['I', 90, 1024, 0], ...Array.from({length: 32}, () => ['T']),
  ['I', 270, 768, 0], ...Array.from({length: 32}, () => ['T']),
  ['I', 359, 0, -1024], ...Array.from({length: 16}, () => ['T']),
  ['I', 0, 1024, 1024], ['T'], ['S', 15, 300, 300, 32767, 100, 1], ['T'],
  ['E', 1, 0], ['C', 2, 0, 1], ['E', 1, 2], ['T'], ['C', 1, 0, 1], ['T'],
  ['I', -1, 0, 0], ['I', 360, 0, 0], ['I', 0, -1, 0], ['I', 0, 1025, 0],
  ['I', 0, 0, -1025], ['I', 0, 0, 1025], ['I', 2147483647, -2147483648, 0],
  ['M', -1, 0], ['M', 2, 0], ['M', 2147483647, 0], ['T'],
  ['M', 0, 0x245f1a5], ['T'], ['M', 1, 0xffffffff], ['T'], ['R', 0], ['T'],
];

// Deterministic command variation exercises owner latches and malformed
// arguments, not neuron math. Every command is executed in both C builds.
let fixtureSeed = 0xdeadbeef;
function pick(limit) {
  fixtureSeed = (Math.imul(fixtureSeed, 1664525) + 1013904223) >>> 0;
  return fixtureSeed % limit;
}
for (let i = 0; i < 160; i++) {
  switch (pick(9)) {
    case 0: commands.push(['E', pick(7) - 1, pick(4)]); break;
    case 1: commands.push(['C', pick(4), pick(2), pick(2)]); break;
    case 2: commands.push(['S', pick(16), pick(301), pick(601) - 300,
                          pick(65536) - 32768, pick(101), pick(2)]); break;
    case 3: commands.push(['M', pick(4) - 1, pick(0xffffffff)]); break;
    case 4: commands.push(['I', pick(362) - 1, pick(1026) - 1, pick(2051) - 1025]); break;
    default: commands.push(['T']); break;
  }
}

const native = spawnSync(process.argv[3], [], {
  input: commands.map(command => command.join(' ')).join('\n') + '\n',
  encoding: 'utf8', maxBuffer: 128 * 1024 * 1024,
});
if (native.error) throw native.error;
assert.equal(native.status, 0, native.stderr);
assert.equal(native.stderr, '');
const expected = native.stdout.trim().split('\n').map(line => JSON.parse(line));
assert.equal(expected.length, commands.length);

const stablePixels = api.fly_lab_pixels(), stableNeurons = api.fly_lab_activations();
const methods = {R:'reset', E:'event', C:'set_context', S:'set_sensors', T:'step', M:'reset_model', I:'set_stimulus'};
const scalarNames = ['route', 'held', 'active', 'pulse', 'delivered_pulse',
  'buttons', 'state', 'epoch', 'view', 'usb', 'ready', 'valid_mask', 'rendered',
  'model', 'model_node_count', 'edge_count', 'stimulus_angle', 'stimulus_strength',
  'stimulus_turn', 'readout_heading', 'readout_strength'];
for (const [index, command] of commands.entries()) {
  const label = `command ${index}: ${command.join(' ')}`;
  const result = api['fly_lab_' + methods[command[0]]](...command.slice(1));
  const got = {result: result === undefined ? 0 : result};
  for (const name of scalarNames) got[name] = api['fly_lab_' + name]() >>> 0;
  // route=-1 is the intentional reset sentinel; other fields are uint32.
  got.route = api.fly_lab_route();
  got.stimulus_turn = api.fly_lab_stimulus_turn();
  got.readout_heading = api.fly_lab_readout_heading();
  got.edges = Array.from({length: api.fly_lab_edge_count()}, (_, e) => [
    api.fly_lab_edge_source(e), api.fly_lab_edge_target(e), api.fly_lab_edge_raw_weight(e),
    api.fly_lab_edge_denominator(e), api.fly_lab_edge_sign(e), api.fly_lab_edge_weight_q(e)]);
  assert.equal(api.fly_lab_model_node_count(), api.fly_lab_model() ? 60 : 64, label);
  for (const e of [-2147483648, -1, api.fly_lab_edge_count(), 2147483647]) {
    assert.equal(api.fly_lab_edge_source(e), -1, label);
    assert.equal(api.fly_lab_edge_target(e), -1, label);
    assert.equal(api.fly_lab_edge_raw_weight(e), 0, label);
    assert.equal(api.fly_lab_edge_denominator(e), 0, label);
    assert.equal(api.fly_lab_edge_sign(e), 0, label);
    assert.equal(api.fly_lab_edge_weight_q(e), 0, label);
  }
  got.owners = Array.from({length: 5}, (_, key) => api.fly_lab_owner(key));
  assert.equal(api.fly_lab_pixel_count(), 57600, label);
  assert.equal(api.fly_lab_neuron_count(), 64, label);
  assert.equal(api.fly_lab_pixels(), stablePixels, label);
  assert.equal(api.fly_lab_activations(), stableNeurons, label);
  const buffer = api.memory.buffer;
  got.neurons = [...new Int16Array(buffer, api.fly_lab_activations(), 64)];
  const pixels = new Uint8Array(buffer, api.fly_lab_pixels(), 57600);
  got.pixels = Buffer.from(pixels.map(value => value + 48)).toString('ascii');
  assert.deepEqual(got, expected[index], label);
}
console.log(`live Wasm: ${commands.length} exact native/Wasm snapshots matched (64 activations + 57,600 pixels each); no imports; fixed 128 KiB memory`);
