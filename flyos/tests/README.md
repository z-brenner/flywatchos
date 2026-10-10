# Host and interactive-lab tests

From the repository root:

```sh
cmake -S flyos -B flyos/build
cmake --build flyos/build
ctest --test-dir flyos/build --output-on-failure
```

The host suite now includes the original model/renderer/persistence tests,
input/redraw policy, bounded synthetic view classification, live bridge,
standalone bundle checks, fail-closed WebAssembly-builder checks, CX60 dynamics
and pinned topology/anatomy provenance checks (19 CTest targets). Some
fake-executable build-failure tests require POSIX/Node and report explicit skips
when unavailable. No test here supplies proprietary firmware or accesses a watch.

## Real C to WebAssembly

Tested toolchain: Zig 0.14.1 (isolated PyPI `ziglang` package), Python 3.12,
Node 24.19.0. Compiler installation needs a registry or local wheel cache. The build
script never installs software by itself.

```sh
python -m venv /tmp/flywatchos-tools
/tmp/flywatchos-tools/bin/python -m pip install ziglang==0.14.1
/tmp/flywatchos-tools/bin/python flyos/tools/build_live_wasm.py
node flyos/tests/test_live_wasm.cjs flyos/build/flyos-live.wasm flyos/build/flyos-live-bridge-trace
```

On Windows, use your chosen environment's `Scripts/python.exe` and the native
trace executable's `.exe` path, possibly under `Debug/`. You can also pass
`--zig /path/to/zig` and `--node /path/to/node` to the builder.

The emitted module must import nothing, expose the expected API, fit its fixed
128 KiB memory, refuse memory growth, and execute a reset/step before output is
accepted. Its generated provenance file records source hashes, compiler version,
module hash and export list. Generated files and compiler caches stay in the
ignored build directory. No WASI host, filesystem, clock or network is needed.

The differential test compares 361 native/Wasm snapshots, each including all
64 signed activations, 57,600 indexed pixels, owners, pulse and state fields.
It also compares every source/target, raw fitted strength, sign and implemented
coefficient for both model graphs. This is host equivalence, not biological,
target or firmware validation.

## Standalone bundle

```sh
python flyos/tools/build_interaction_lab.py --exporter flyos/build/flyos-interaction-exporter --wasm flyos/build/flyos-live.wasm --output flyos/build/live-lab
```

Use a new output directory. The HTML embeds every image, scenario, script and
Wasm byte. `trace.json` and `SHA256SUMS` accompany it. Omit `--wasm` for a smaller
replay-only page; live mode then reports that the engine was not bundled.

## Optional DOM/state integration tests

Install the test dependency in the ignored build tree or another isolated
location, not systemwide:

```sh
npm install --prefix flyos/build/ui-tests --no-audit --no-fund jsdom@26.1.0
node flyos/tests/test_interaction_lab_ui.cjs flyos/build/live-lab/index.html flyos/build/ui-tests/node_modules/jsdom
node flyos/tests/test_interaction_lab_circuit.cjs flyos/build/ui-tests/node_modules/jsdom
node flyos/tests/test_interaction_lab_anatomy.cjs flyos/build/ui-tests/node_modules/jsdom
node flyos/tests/test_experiment_protocol.cjs flyos/build/flyos-live.wasm
node flyos/tests/test_interaction_lab_experiments.cjs flyos/build/ui-tests/node_modules/jsdom
node flyos/tests/test_experiment_bundle.cjs flyos/build/live-lab/index.html flyos/build/ui-tests/node_modules/jsdom
```

The test uses the real embedded WebAssembly and a DOM implementation with
network loading disabled, deterministic interval callbacks, and stub canvas
encoding. It checks bursts, signals, pointer/keyboard interruption, BACK
chords, mode switching, timers, blur release, modal pulse delivery, seed resets,
input validation, bounded history, scrubbing, model-switch isolation, circuit
stimuli, unit/pathway inspection, license/source presentation, and exact
exported-command replay for both models. It does not establish browser
layout, canvas appearance, mobile responsiveness or physical pointer capture.

The separate anatomy suite uses a small synthetic fixture to check body-ID
search, directed pair counts, reciprocal inspection, honest filtered totals,
keyboard focus, metadata safety and static export. Full-bundle integration
checks the measured dataset and transitions between live, anatomy and replay
views without allowing anatomy navigation to step the C model.

Paired experiments have separate actual-Wasm protocol tests, synthetic-fixture
DOM tests and full-bundle actual-Wasm integration. They verify identical starts,
isolated live memory, all-snapshot command-prefix replay and final pixels,
512-step limits, sector metadata, residual/tied/silent readouts, same-time
profile comparison, immutable completed exports, repeated lens changes and
delayed/missing/rejected engines. Plot/metric checks are implementation evidence,
not biological validation or browser visual proof. See
[`../sim/EXPERIMENTS.md`](../sim/EXPERIMENTS.md).

Actual browser execution was unavailable during this milestone. Browser visual
and device-interaction QA remains open and is not inferred from these tests.

## Scientific provenance

```sh
python flyos/tools/generate_cx_data.py --check
python flyos/tests/test_cx_provenance.py
```

These checks require no network. They pin the original MAT and source hashes,
all 326 generated edges, orientation sentinels, category/strength mapping,
model metadata and full MIT notice. Both generation scripts reject optimized
Python so integrity assertions cannot silently disappear. If SciPy is present,
two optional provenance tests rerun MAT extraction, require byte-identical
CSV/nodes/manifest, and simulate Windows default newline translation. Otherwise
those two checks are explicitly skipped. Nine tests run with SciPy, including
the readout-metadata guard distinguishing a missing integer peak from silence.

The numerical tests check all eight cue sectors, duplicate-sector averaging,
quiescence, cue-off decay, deterministic bounded rates, invalid input rejection
and model padding. These are implementation checks, not measured behavioral
validation. See [`../sim/CX60.md`](../sim/CX60.md).

```sh
python flyos/tools/generate_hulse_data.py --check
python flyos/tests/test_hulse_provenance.py
```

The anatomy checks decompress the byte-pinned public source tables and
independently regenerate cell IDs, directed counts, metadata and attribution.
They do not infer missing connections, synaptic signs, physical geometry or
dynamics. See the [source contract](../sim/data/hulse2021/README.md).

## Complete public-only check

[`../../ci/README.md`](../../ci/README.md) documents the pinned dependencies
and one-command aggregate runner used by GitHub Actions. SciPy re-extraction
is mandatory there, and missing private firmware/platform checks remain
explicit skips. The runner refuses known private-input locations and does not
build, package, stage or flash firmware.

## Independent source-equation reference

The separate reference module preserves signed tanh rate dynamics at the source
0.1 ms Euler timestep, with explicitly omitted noise and controlled direct
current input. It does not replace the original module or measured anatomy.

```sh
python flyos/tools/generate_rate_reference.py --check
python flyos/tests/generate_rate_reference_oracle.py --check
python flyos/tests/test_rate_reference_convergence.py
python flyos/tools/build_rate_reference_wasm.py --output flyos/build/flyos-rate-reference.wasm
python flyos/tests/test_rate_reference_oracle.py flyos/build/flyos-rate-reference-trace
node flyos/tests/test_rate_reference_wasm.cjs flyos/build/flyos-rate-reference.wasm flyos/build/flyos-rate-reference-trace
node flyos/tests/test_rate_reference_protocol.cjs flyos/build/flyos-rate-reference.wasm
python flyos/tools/build_interaction_lab.py --exporter flyos/build/flyos-interaction-exporter --wasm flyos/build/flyos-live.wasm --reference-wasm flyos/build/flyos-rate-reference.wasm --output flyos/build/reference-lab
node flyos/tests/test_interaction_lab_reference.cjs ci/node_modules/jsdom
node flyos/tests/test_reference_bundle.cjs flyos/build/reference-lab/index.html ci/node_modules/jsdom
```

The complete CI runner performs these checks with mandatory NumPy/SciPy. The
independent oracle reads the original MAT and integrates the SI-voltage form,
not the production generated table. Timestep refinement checks all 60 states
at 801 common samples, including cue-loss transients. Native/Wasm comparison
uses a declared floating-point tolerance; original baseline comparisons remain
bit-exact. Builder tests reject missing/stale/malformed source identities and
exercise compile, validator and paired-install failures.

Protocol and real-bundle tests verify signed/ambiguous readouts, all-snapshot
command replay, deterministic repeats, cancellation, independent memories,
phase/input mapping, missing/delayed/rejected reference engines, immutable
exports and navigation races. SVG/data checks are not browser layout QA.
See [`../sim/RATE_REFERENCE.md`](../sim/RATE_REFERENCE.md).
