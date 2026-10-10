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
and pinned topology/provenance checks (14 CTest targets). Some
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
```

The test uses the real embedded WebAssembly and a DOM implementation with
network loading disabled, deterministic interval callbacks, and stub canvas
encoding. It checks bursts, signals, pointer/keyboard interruption, BACK
chords, mode switching, timers, blur release, modal pulse delivery, seed resets,
input validation, bounded history, scrubbing, model-switch isolation, circuit
stimuli, unit/pathway inspection, license/source presentation, and exact
exported-command replay for both models. It does not establish browser
layout, canvas appearance, mobile responsiveness or physical pointer capture.

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
a seventh provenance test independently reruns MAT extraction and requires
byte-identical CSV/nodes/manifest; otherwise that test is explicitly skipped.

The numerical tests check all eight cue sectors, duplicate-sector averaging,
quiescence, cue-off decay, deterministic bounded rates, invalid input rejection
and model padding. These are implementation checks, not measured behavioral
validation. See [`../sim/CX60.md`](../sim/CX60.md).
