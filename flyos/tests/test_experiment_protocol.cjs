#!/usr/bin/env node
'use strict';
// The runner only schedules the real C/Wasm. These tests never reproduce its
// neural update or renderer; replay reads the actual exported state and pixels.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

const source = path.join(__dirname, '../tools/interaction_lab_experiment_protocol.js');
const FlyExperiment = fs.existsSync(source) ? require(source) : {};
const wasmPath = process.argv[2] || path.join(__dirname, '../build/flyos-live.wasm');
const wasm = new WebAssembly.Module(fs.readFileSync(wasmPath));
const metadata = JSON.parse(fs.readFileSync(path.join(__dirname, '../sim/circuit_models.json'))).models[1];
const clone = value => JSON.parse(JSON.stringify(value));
function runner() {
  assert.equal(typeof FlyExperiment.run, 'function', 'paired experiment runner must exist');
  return FlyExperiment.run;
}
function run(config = {}) { return runner()(wasm, metadata, config); }
function rawSnapshot(api) {
  return {
    tick: api.fly_lab_epoch(), model: api.fly_lab_model(), node_count: api.fly_lab_model_node_count(),
    neurons: Array.from(new Int16Array(api.memory.buffer, api.fly_lab_activations(), 64)),
    stimulus: {angle: api.fly_lab_stimulus_angle(), strength: api.fly_lab_stimulus_strength(), turn: api.fly_lab_stimulus_turn()},
    readout_heading: api.fly_lab_readout_heading(), readout_strength: api.fly_lab_readout_strength(),
  };
}
function pixels(api) {
  return Array.from(new Uint8Array(api.memory.buffer, api.fly_lab_pixels(), api.fly_lab_pixel_count()));
}

test('default paired trial has explicit reset and post-step phase boundaries', () => {
  const result = run();
  assert.equal(result.schema, 1);
  assert.deepEqual(result.config, {protocol: 'cue-shift', warmupSteps: 32, perturbSteps: 96,
    recoverySteps: 32, baseAngle: 0, shiftAngle: 90, strength: 768, drive: 768});
  assert.deepEqual(result.phases, [
    {name: 'reset', startIndex: 0, endIndex: 0},
    {name: 'warmup', startIndex: 1, endIndex: 32},
    {name: 'perturb', startIndex: 33, endIndex: 128},
    {name: 'recovery', startIndex: 129, endIndex: 160},
  ]);
  for (const arm of [result.control, result.treatment]) {
    assert.equal(arm.frames.length, 161);
    assert.equal(arm.finalPixels.length, 57600);
    for (const frame of arm.frames) {
      assert.equal(frame.tick, frame.index);
      assert.equal(frame.neurons.length, 64);
      assert.deepEqual(frame.neurons.slice(60), [0, 0, 0, 0]);
      assert.equal(frame.model, 1);
      assert.equal(frame.node_count, 60);
      assert.equal(frame.sectorMeans.length, 8);
      assert.equal(frame.phaseStep, frame.index === 0 ? 0 : frame.index - result.phases.find(p => p.name === frame.phase).startIndex + 1);
    }
    assert.deepEqual(arm.frames[0].neurons, Array(64).fill(0));
    assert.equal(arm.frames[0].peakStatus, 'no-activity');
    assert.equal(arm.frames[0].readout_heading, -1);
  }
  assert.equal(result.comparisons.length, 161);
  assert.equal(result.summary.baselineIndex, 32);
  assert.equal(result.summary.perturbEndIndex, 128);
  assert.equal(result.summary.recoveryEndIndex, 160);
});

test('repeat runs and the entire common prefix are bit-identical and isolated from a live instance', () => {
  const live = new WebAssembly.Instance(wasm).exports;
  live.fly_lab_reset_model(1, 123);
  live.fly_lab_set_stimulus(270, 1024, -600);
  for (let i = 0; i < 19; i++) live.fly_lab_step();
  const before = Buffer.from(live.memory.buffer);
  const originalMetadata = clone(metadata);
  const first = run({protocol: 'cue-drive'}), second = run({protocol: 'cue-drive'});
  assert.deepEqual(first, second);
  assert.deepEqual(Buffer.from(live.memory.buffer), before, 'live memory must remain untouched');
  assert.deepEqual(metadata, originalMetadata, 'metadata must not be mutated');
  assert.deepEqual(first.control.frames.slice(0, 33), first.treatment.frames.slice(0, 33));
  assert.notDeepEqual(first.control.frames[128].neurons, first.treatment.frames[128].neurons);
  assert.equal(first.control.frames[128].readout_heading, first.treatment.frames[128].readout_heading,
    'coarse peak can stay unchanged despite a genuine profile effect');
  assert.ok(first.comparisons[128].profileL1 > 0);
});

test('all three protocols alter only treatment perturbation and restore the requested baseline', () => {
  for (const protocol of ['cue-shift', 'cue-loss', 'cue-drive']) {
    for (const drive of [-768, 768]) {
      const result = run({protocol, baseAngle: 315, shiftAngle: 90, drive,
        warmupSteps: 4, perturbSteps: 8, recoverySteps: 4});
      for (const [name, arm] of [['control', result.control], ['treatment', result.treatment]]) {
        for (const frame of arm.frames) {
          const expected = {angle: 315, strength: 768, turn: 0};
          if (name === 'treatment' && frame.phase === 'perturb') {
            if (protocol === 'cue-shift') expected.angle = 90;
            if (protocol === 'cue-loss') expected.strength = 0;
            if (protocol === 'cue-drive') expected.turn = drive;
          }
          assert.deepEqual(frame.stimulus, expected);
        }
      }
    }
  }
});

test('every exported snapshot and final framebuffer replay exactly in a fresh actual Wasm instance', () => {
  for (const protocol of ['cue-shift', 'cue-loss', 'cue-drive']) {
    const result = clone(run({protocol, drive: -768})); // The actual JSON export is replayable.
    for (const arm of [result.control, result.treatment]) {
      const api = new WebAssembly.Instance(wasm).exports;
      let executed = 0;
      for (const frame of arm.frames) {
        assert.ok(frame.commandCount > executed);
        while (executed < frame.commandCount) {
          const [name, ...args] = arm.commands[executed++];
          assert.ok(['fly_lab_reset_model', 'fly_lab_set_stimulus', 'fly_lab_step'].includes(name));
          api[name](...args);
        }
        const raw = rawSnapshot(api);
        for (const [key, value] of Object.entries(raw)) assert.deepEqual(frame[key], value, `${protocol}/${frame.index}/${key}`);
        const expectedMeans = result.sectors.map(sector => sector.unitIds.reduce((sum, id) => sum + raw.neurons[id], 0) / sector.unitIds.length);
        assert.deepEqual(frame.sectorMeans, expectedMeans);
        assert.equal(frame.epgRawTotal, metadata.units.filter(unit => unit.group === 'E-PG').reduce((sum, unit) => sum + raw.neurons[unit.id], 0));
        assert.equal(frame.networkRawTotal, raw.neurons.reduce((sum, value) => sum + value, 0));
      }
      assert.equal(executed, arm.commands.length, 'no hidden commands after final snapshot');
      assert.deepEqual(pixels(api), arm.finalPixels, `${protocol} final pixel roles`);
    }
  }
});

test('two independent instances are created only after bounded config and metadata validation', () => {
  runner();
  const OriginalInstance = WebAssembly.Instance;
  let instances = 0;
  WebAssembly.Instance = function (...args) { instances++; return new OriginalInstance(...args); };
  try {
    const invalid = [null, [], 'cue-shift', new Date(0), new Map(), Object.create({drive: 768}),
      {[Symbol('extra')]: 1}, Object.defineProperty({}, 'drive', {value: NaN}),
      Object.defineProperty({}, 'drive', {enumerable: true, get: () => 768}),
      {protocol: 'unknown'}, {seed: 1}, {extra: true},
      ...['warmupSteps', 'perturbSteps', 'recoverySteps'].flatMap(name => [0, -1, 1.5, '32', NaN, Infinity, 513].map(value => ({[name]: value}))),
      ...['baseAngle', 'shiftAngle'].flatMap(name => [-1, 360, 2.2, '90', NaN, Infinity].map(value => ({[name]: value}))),
      ...[-1, 1025, 0.5, '768', NaN, Infinity].map(strength => ({strength})),
      ...[-1025, 1025, 1.1, '768', NaN, Infinity].map(drive => ({drive})),
      {warmupSteps: 256, perturbSteps: 256, recoverySteps: 1}];
    for (const config of invalid) assert.throws(() => run(config), /config|protocol|steps|angle|strength|drive|unknown/i);
    assert.equal(instances, 0, 'invalid inputs must not create even one instance');
    const result = run({warmupSteps: 1, perturbSteps: 510, recoverySteps: 1});
    assert.equal(result.control.frames.length, 513);
    assert.equal(instances, 2, 'a valid paired trial creates exactly two isolated instances');
    assert.throws(() => FlyExperiment.run({}, metadata, {}), /module/i);
    assert.equal(instances, 2);
  } finally { WebAssembly.Instance = OriginalInstance; }
});

test('metadata identity, unit ordering, cue mapping and model shape fail closed before instantiation', () => {
  runner();
  const corruptions = [m => {m.id = 0;}, m => {m.key = 'something-else';}, m => {m.scale = 100;},
    m => {m.source_commit = 'unverified';}, m => {m.source_sha256 = 'unverified';},
    m => {m.node_count = 64;}, m => {m.units.pop();}, m => {delete m.units[0];}, m => {m.units[0].id = 1;},
    m => {m.units[34].group = 'P-EG';}, m => {m.units[34].cue_angle_degrees = 45;},
    m => {delete m.units[34].cue_angle_degrees;}, m => {m.units[0].cue_angle_degrees = 0;},
    m => {m.units[0].half = 'B';}];
  const OriginalInstance = WebAssembly.Instance;
  let instances = 0;
  WebAssembly.Instance = function (...args) { instances++; return new OriginalInstance(...args); };
  try {
    for (const corrupt of corruptions) {
      const changed = clone(metadata); corrupt(changed);
      assert.throws(() => FlyExperiment.run(wasm, changed, {}), /metadata/i);
    }
    assert.equal(instances, 0);
  } finally { WebAssembly.Instance = OriginalInstance; }
});

test('sector metrics normalize duplicate units, preserve fractional means and handle zeros and C ties', () => {
  assert.equal(typeof FlyExperiment.analyze, 'function', 'pure profile analysis must be testable');
  const neurons = Array(64).fill(0);
  let measured = FlyExperiment.analyze(neurons, metadata, -1, 0);
  assert.equal(measured.peakStatus, 'no-activity');
  assert.deepEqual(measured.peakTieAngles, []);
  neurons[34] = 2;
  measured = FlyExperiment.analyze(neurons, metadata, -1, 0);
  assert.equal(measured.sectorMeans[0], 0.5);
  assert.equal(measured.epgRawTotal, 2);
  assert.equal(measured.peakStatus, 'low-activity', 'missing C peak is not exact silence');
  for (const unit of metadata.units.filter(unit => unit.group === 'E-PG')) neurons[unit.id] = 100;
  measured = FlyExperiment.analyze(neurons, metadata, 0, 100);
  assert.deepEqual(measured.sectorMeans, Array(8).fill(100));
  assert.equal(measured.sectorActivity, 800, 'zero-degree duplicated units do not double its weight');
  assert.equal(measured.peakStatus, 'tied');
  assert.deepEqual(measured.peakTieAngles, [0, 45, 90, 135, 180, 225, 270, 315]);
  neurons[34] = 101;
  measured = FlyExperiment.analyze(neurons, metadata, 0, 100);
  assert.equal(measured.sectorMeans[0], 100.25);
  assert.equal(measured.peakTieAngles.length, 8, 'ties follow C integer-averaged peak, not fractional JS means');
  neurons[35] = 200; neurons[44] = 200;
  assert.equal(FlyExperiment.analyze(neurons, metadata, 45, 200).peakStatus, 'active');
  assert.throws(() => FlyExperiment.analyze(neurons.slice(0, 60), metadata, 45, 200), /activation/i);
  const sparse = neurons.slice(); delete sparse[0];
  assert.throws(() => FlyExperiment.analyze(sparse, metadata, 45, 200), /activation/i);
  assert.throws(() => FlyExperiment.analyze(neurons, metadata, 90, 200), /readout|metadata/i);
});

test('cue-off reports raw silence and retention separately from the truncated coarse peak', () => {
  const result = run({protocol: 'cue-loss'});
  const end = result.treatment.frames[128];
  assert.equal(end.epgRawTotal, 0);
  assert.equal(end.networkRawTotal, 0);
  assert.equal(end.peakStatus, 'no-activity');
  assert.equal(result.comparisons[128].treatmentRetention, 0);
  assert.equal(result.comparisons[128].profileL1Fraction, 1);
  assert.equal(result.comparisons[128].peakSeparationDegrees, null);
  const residual = result.treatment.frames.find(frame => frame.phase === 'perturb' && frame.readout_heading === -1 && frame.epgRawTotal > 0);
  assert.ok(residual, 'actual C fixture contains a sub-quantum residual before silence');
  assert.equal(residual.peakStatus, 'low-activity');
  const silence = result.summary.firstTreatmentEpgSilence;
  assert.ok(silence.index > residual.index);
  assert.equal(result.treatment.frames[silence.index].epgRawTotal, 0);
  assert.ok(result.treatment.frames[silence.index - 1].epgRawTotal > 0);
  assert.ok(result.treatment.frames[160].epgRawTotal > 0, 'baseline cue is restored');
  assert.equal(result.summary.finalProfilesIdentical, result.comparisons[160].profileL1 === 0);
});

test('zero cues avoid misleading ratios and inactive phase differences', () => {
  const result = run({protocol: 'cue-loss', strength: 0});
  for (const comparison of result.comparisons) {
    assert.equal(comparison.profileL1, 0);
    assert.equal(comparison.profileL1Fraction, null);
    assert.equal(comparison.peakSeparationDegrees, null);
    assert.equal(comparison.controlRetention, null);
    assert.equal(comparison.treatmentRetention, null);
  }
  assert.equal(result.summary.maxProfileL1, 0);
});
