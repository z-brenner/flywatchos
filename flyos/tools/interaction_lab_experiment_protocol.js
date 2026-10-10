// Scheduling and measurements only. Every neural update and pixel is produced
// by an isolated instance of the unchanged C/WebAssembly bridge.
const FlyExperiment = (() => {
  'use strict';
  const MAX_STEPS = 512;
  const DEFAULTS = Object.freeze({protocol: 'cue-shift', warmupSteps: 32,
    perturbSteps: 96, recoverySteps: 32, baseAngle: 0, shiftAngle: 90,
    strength: 768, drive: 768});
  const SOURCE_COMMIT = 'dfb95dfeaad0da2df0f7f687846d4df44079a483';
  const SOURCE_SHA256 = 'abfdcb2918e3637e41d4ba7b7438e512f545dac6553ce89d5cfddb49de044b12';
  const PROTOCOLS = Object.freeze(['cue-shift', 'cue-loss', 'cue-drive']);
  const REQUIRED_EXPORTS = ['fly_lab_reset_model', 'fly_lab_set_stimulus', 'fly_lab_step',
    'fly_lab_epoch', 'fly_lab_model', 'fly_lab_model_node_count', 'fly_lab_neuron_count',
    'fly_lab_activations', 'fly_lab_pixels', 'fly_lab_pixel_count', 'fly_lab_stimulus_angle',
    'fly_lab_stimulus_strength', 'fly_lab_stimulus_turn', 'fly_lab_readout_heading',
    'fly_lab_readout_strength', 'fly_lab_edge_count'];

  function integer(value, minimum, maximum, name) {
    if (!Number.isInteger(value) || value < minimum || value > maximum) {
      throw new Error(`Invalid ${name}: expected an integer from ${minimum} to ${maximum}.`);
    }
    return value === 0 ? 0 : value;
  }
  function configuration(input) {
    if (!input || typeof input !== 'object' || Array.isArray(input) ||
        (Object.getPrototypeOf(input) !== Object.prototype && Object.getPrototypeOf(input) !== null)) {
      throw new Error('Invalid experiment config: expected a plain object.');
    }
    for (const key of Reflect.ownKeys(input)) {
      if (!Object.hasOwn(DEFAULTS, key)) throw new Error(`Unknown config field: ${String(key)}.`);
      const descriptor = Object.getOwnPropertyDescriptor(input, key);
      if (!descriptor.enumerable || !Object.hasOwn(descriptor, 'value')) {
        throw new Error(`Invalid config field: ${key} must be an enumerable value.`);
      }
    }
    const config = {...DEFAULTS, ...input};
    if (!PROTOCOLS.includes(config.protocol)) throw new Error('Unknown experiment protocol.');
    for (const key of ['warmupSteps', 'perturbSteps', 'recoverySteps']) {
      config[key] = integer(config[key], 1, MAX_STEPS, `${key} steps`);
    }
    if (config.warmupSteps + config.perturbSteps + config.recoverySteps > MAX_STEPS) {
      throw new Error(`Experiment steps must total at most ${MAX_STEPS}.`);
    }
    for (const key of ['baseAngle', 'shiftAngle']) config[key] = integer(config[key], 0, 359, `${key} angle`);
    config.strength = integer(config.strength, 0, 1024, 'strength');
    config.drive = integer(config.drive, -1024, 1024, 'drive');
    return config;
  }

  function verifiedSectors(metadata) {
    if (!metadata || metadata.id !== 1 || metadata.key !== 'pisokas-cx60' ||
        metadata.node_count !== 60 || metadata.scale !== 1024 ||
        metadata.source_commit !== SOURCE_COMMIT || metadata.source_sha256 !== SOURCE_SHA256 ||
        !Array.isArray(metadata.units) || metadata.units.length !== 60) {
      throw new Error('CX60 metadata identity does not match the pinned model.');
    }
    const sectors = new Map();
    for (let index = 0; index < metadata.units.length; index++) {
      const unit = metadata.units[index];
      const group = index < 16 ? 'P-EN' : index < 34 ? 'P-EG' : index < 52 ? 'E-PG' : 'Delta7';
      const half = index < 8 || (index >= 16 && index < 25) || (index >= 34 && index < 43) ? 'A' : 'B';
      if (!unit || unit.id !== index || unit.group !== group || (index < 52 && unit.half !== half)) {
        throw new Error('CX60 metadata unit ordering or population mismatch.');
      }
      if (group === 'E-PG') {
        // This guard is the pinned source mapping, not a neural update. Actual
        // analysis groups the verified metadata IDs by cue_angle_degrees.
        const expectedAngle = ((index - 34) % 9) % 8 * 45;
        if (unit.cue_angle_degrees !== expectedAngle) throw new Error('CX60 metadata cue-sector mismatch.');
        if (!sectors.has(unit.cue_angle_degrees)) sectors.set(unit.cue_angle_degrees, []);
        sectors.get(unit.cue_angle_degrees).push(unit.id);
      } else if (Object.hasOwn(unit, 'cue_angle_degrees')) {
        throw new Error('CX60 metadata assigns an E-PG cue sector to a different population.');
      }
    }
    return [...sectors].sort((a, b) => a[0] - b[0]).map(([angle, unitIds]) => ({angle, unitIds}));
  }

  function profile(neurons, sectors, heading, strength) {
    if (!Array.isArray(neurons) || neurons.length !== 64 ||
        Array.from(neurons).some((value, index) => !Number.isInteger(value) || value < 0 || value > 16383 || (index >= 60 && value !== 0))) {
      throw new Error('Invalid CX60 activation buffer.');
    }
    const sectorMeans = sectors.map(sector => sector.unitIds.reduce((sum, id) => sum + neurons[id], 0) / sector.unitIds.length);
    const epgRawTotal = sectors.reduce((total, sector) => total + sector.unitIds.reduce((sum, id) => sum + neurons[id], 0), 0);
    // C readout truncates each mean to integer Q10 before selecting its maximum.
    // Keep untruncated means for profile comparison; ties below describe C only.
    const cMeans = sectorMeans.map(value => Math.floor(value));
    const maximum = Math.max(...cMeans);
    const peakTieAngles = maximum === 0 ? [] : sectors.filter((_, index) => cMeans[index] === maximum).map(sector => sector.angle);
    if (strength !== maximum || heading !== (maximum === 0 ? -1 : peakTieAngles[0])) {
      throw new Error('C readout does not match the verified metadata and activation buffer.');
    }
    return {sectorMeans, epgRawTotal,
      networkRawTotal: neurons.reduce((sum, value) => sum + value, 0),
      sectorActivity: sectorMeans.reduce((sum, value) => sum + value, 0),
      peakStatus: epgRawTotal === 0 ? 'no-activity' : maximum === 0 ? 'low-activity' : peakTieAngles.length > 1 ? 'tied' : 'active',
      peakTieAngles};
  }

  // Public measurement helper: useful for auditing zero, residual and tied
  // profiles without pretending those fixtures are extra model executions.
  function analyze(neurons, metadata, heading, strength) {
    return profile(neurons, verifiedSectors(metadata), heading, strength);
  }

  function verifyModule(module) {
    if (!(module instanceof WebAssembly.Module) || WebAssembly.Module.imports(module).length !== 0) {
      throw new Error('Experiment requires the import-free C/WebAssembly module.');
    }
    const exports = WebAssembly.Module.exports(module);
    if (!exports.some(item => item.name === 'memory' && item.kind === 'memory') ||
        REQUIRED_EXPORTS.some(name => !exports.some(item => item.name === name && item.kind === 'function'))) {
      throw new Error('C/WebAssembly module is missing required experiment exports.');
    }
  }
  function phasesFor(config) {
    const perturbEnd = config.warmupSteps + config.perturbSteps;
    return [{name: 'reset', startIndex: 0, endIndex: 0},
      {name: 'warmup', startIndex: 1, endIndex: config.warmupSteps},
      {name: 'perturb', startIndex: config.warmupSteps + 1, endIndex: perturbEnd},
      {name: 'recovery', startIndex: perturbEnd + 1, endIndex: perturbEnd + config.recoverySteps}];
  }
  function trial(module, sectors, config, phases, treatment) {
    const api = new WebAssembly.Instance(module).exports;
    const commands = [], frames = [];
    function command(name, ...args) {
      const result = api[name](...args);
      if (name !== 'fly_lab_step' && result !== 1) throw new Error(`C rejected experiment command ${name}.`);
      commands.push([name, ...args]);
    }
    function stimulus(perturb) {
      const altered = treatment && perturb;
      command('fly_lab_set_stimulus', altered && config.protocol === 'cue-shift' ? config.shiftAngle : config.baseAngle,
        altered && config.protocol === 'cue-loss' ? 0 : config.strength,
        altered && config.protocol === 'cue-drive' ? config.drive : 0);
    }
    function capture(index, phase, phaseStep) {
      const neurons = Array.from(new Int16Array(api.memory.buffer, api.fly_lab_activations(), 64));
      const heading = api.fly_lab_readout_heading(), strength = api.fly_lab_readout_strength();
      frames.push({index, phase, phaseStep, commandCount: commands.length,
        tick: api.fly_lab_epoch(), model: api.fly_lab_model(), node_count: api.fly_lab_model_node_count(),
        neurons, stimulus: {angle: api.fly_lab_stimulus_angle(), strength: api.fly_lab_stimulus_strength(), turn: api.fly_lab_stimulus_turn()},
        readout_heading: heading, readout_strength: strength,
        ...profile(neurons, sectors, heading, strength)});
    }
    command('fly_lab_reset_model', 1, 0); // CX60 is noiseless and seed-independent.
    if (api.fly_lab_model() !== 1 || api.fly_lab_model_node_count() !== 60 ||
        api.fly_lab_neuron_count() !== 64 || api.fly_lab_pixel_count() !== 57600 ||
        api.fly_lab_edge_count() !== 326 || api.memory.buffer.byteLength !== 131072) {
      throw new Error('C/WebAssembly experiment model does not match CX60 metadata.');
    }
    stimulus(false);
    capture(0, 'reset', 0);
    for (const phase of phases.slice(1)) {
      // Both arms log the same boundary setter count, including unchanged
      // control setters. Each frame's commandCount unambiguously ends its log.
      if (phase.name !== 'warmup') stimulus(phase.name === 'perturb');
      for (let index = phase.startIndex; index <= phase.endIndex; index++) {
        command('fly_lab_step');
        capture(index, phase.name, index - phase.startIndex + 1);
      }
    }
    const finalPixels = Array.from(new Uint8Array(api.memory.buffer, api.fly_lab_pixels(), 57600));
    if (finalPixels.some(value => value > 5)) throw new Error('Invalid C framebuffer palette role.');
    return {commands, frames, finalPixels};
  }
  function compare(control, treatment, baselineIndex) {
    const controlBaseline = control.frames[baselineIndex].sectorActivity;
    const treatmentBaseline = treatment.frames[baselineIndex].sectorActivity;
    return control.frames.map((frame, index) => {
      const other = treatment.frames[index];
      const profileL1 = frame.sectorMeans.reduce((sum, value, sector) => sum + Math.abs(value - other.sectorMeans[sector]), 0);
      const denominator = frame.sectorActivity + other.sectorActivity;
      const distance = Math.abs(frame.readout_heading - other.readout_heading);
      return {index, phase: frame.phase, profileL1,
        profileL1Fraction: denominator === 0 ? null : profileL1 / denominator,
        peakSeparationDegrees: frame.peakStatus === 'active' && other.peakStatus === 'active' ? Math.min(distance, 360 - distance) : null,
        controlRetention: controlBaseline === 0 ? null : frame.sectorActivity / controlBaseline,
        treatmentRetention: treatmentBaseline === 0 ? null : other.sectorActivity / treatmentBaseline};
    });
  }
  function run(module, modelMetadata, input = {}) {
    // All config and metadata validation precedes any instance construction or
    // commands. No references to the live UI, its instance, timers or state.
    const config = configuration(input);
    const sectors = verifiedSectors(modelMetadata);
    verifyModule(module);
    const phases = phasesFor(config);
    const control = trial(module, sectors, config, phases, false);
    const treatment = trial(module, sectors, config, phases, true);
    const comparisons = compare(control, treatment, config.warmupSteps);
    const firstSilence = key => {
      const frame = treatment.frames.find(item => item.phase === 'perturb' && item[key] === 0);
      return frame ? {index: frame.index, phaseStep: frame.phaseStep} : null;
    };
    const final = comparisons[comparisons.length - 1];
    const fractions = comparisons.map(item => item.profileL1Fraction).filter(value => value !== null);
    return {schema: 1, config,
      model: {id: 1, key: modelMetadata.key, source_commit: SOURCE_COMMIT, source_sha256: SOURCE_SHA256},
      sectors, phases, control, treatment, comparisons,
      summary: {baselineIndex: config.warmupSteps, perturbEndIndex: phases[2].endIndex, recoveryEndIndex: phases[3].endIndex,
        maxProfileL1: Math.max(...comparisons.map(item => item.profileL1)),
        maxProfileL1Fraction: fractions.length ? Math.max(...fractions) : null,
        perturbEnd: {...comparisons[phases[2].endIndex]}, recoveryEnd: {...final},
        firstTreatmentEpgSilence: firstSilence('epgRawTotal'), firstTreatmentNetworkSilence: firstSilence('networkRawTotal'),
        finalProfilesIdentical: final.profileL1 === 0},
      semantics: {
        samples: 'Sample 0 is reset with the configured baseline stimulus and no step. Every later sample is after exactly one C step with that sample\'s phase stimulus. Phase steps are one-based.',
        replay: 'Replay commands in order through frame.commandCount (exclusive array end) to recover that exact snapshot. finalPixels is the final 240 by 240 indexed C framebuffer.',
        time: 'Steps are abstract model time, not milliseconds. No calibrated biological dynamics or behavior is claimed.',
        profile: 'Each sectorMean is the untruncated arithmetic mean of E-PG units with that verified cue angle. Sector 0 has four units; every other sector has two.',
        peak: 'The preserved C readout is the strongest integer-truncated sector mean, not a population-vector heading. Lowest-angle sector wins a C tie. An active status means only a unique positive C peak, not heading reliability.',
        silence: 'No-activity means all E-PG activations are exactly zero. Low-activity means raw E-PG activity remains but integer-truncated C sector means are zero. Whole-circuit silence uses all 60 actual units.',
        divergence: 'profileL1 is the sum of absolute paired sector-mean differences. profileL1Fraction divides by the sum of both sectorActivity values; it is null if both profiles are zero. It describes amplitude and shape differences, not biological distance.',
        retention: 'Retention is relative E-PG sector activity, with each arm\'s warm-up endpoint equal to 1. It can exceed 1 and does not measure memory. A zero baseline produces null. Compare with the evolving paired control.',
        drive: 'Positive drive targets P-EN A, negative drive targets P-EN B. Sign does not establish clockwise/counterclockwise rotation or angular velocity.',
      }};
  }
  return Object.freeze({DEFAULTS, MAX_STEPS, PROTOCOLS, run, analyze});
})();

if (typeof module !== 'undefined' && module.exports) module.exports = FlyExperiment;
