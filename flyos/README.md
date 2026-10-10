# FlyOS model and FR245 overlay targets

The portable core contains the deterministic fly network, persistence format,
framebuffer renderer, and host simulation. Target-specific directories contain
the researched GarminOS-resident overlays used by the live experiments.

Build and test from the repository root:

```powershell
cmake -S flyos -B flyos/build
cmake --build flyos/build
ctest --test-dir flyos/build --output-on-failure
```

Run `flyos/build/flyos-host.exe` to write a 240 by 240 `flyos-screen.ppm` preview.
Keyboard controls are `w/s/a/d/q`; `x` saves the host state and exits. See
[`docs/flyos-architecture.md`](../docs/flyos-architecture.md) for design and limits.

An additional freestanding Cortex-M4 structural build is under `target/k28/`.
It produces an ELF and raw binary at the observed application address but has
no working watch drivers or Garmin update wrapper and must not be installed.

The host build includes a RAM-only implementation of the validated 244-byte
official-display staging-row transformation. It does not communicate with the
display controller or panel.

The FR245 overlay targets require local, byte-pinned Garmin firmware evidence
and an ARM toolchain. Those proprietary inputs and all generated update packages
are intentionally excluded from this repository. The live N64 result is still
an overlay inside GarminOS; it is not a standalone FlyOS boot.

## Interactive replay lab

```sh
python flyos/tools/build_interaction_lab.py --exporter flyos/build/flyos-interaction-exporter --output flyos/build/interaction-lab
```

Run from the repository root after the build. On Windows, select the `.exe`
path emitted by your generator (possibly under `Debug/`). Open the generated
`index.html`; it contains all scripts, images, and scenario data and needs no
server or network. The output directory must not already exist. `trace.json`
and `SHA256SUMS` accompany the page for reproducibility.

Seven scripted scenarios expose actual C-rendered neural frames, per-neuron
telemetry, key ownership, short-tap pulses, and abstract detach redraw state.
The page provides play/pause, speed, frame stepping/scrubbing, a neuron
inspector, and per-scenario export. It starts paused and pauses when hidden.
The host policy lives in `sim/` and is never linked into a watch target.
Read [the model contract](sim/README.md) before interpreting its results.
