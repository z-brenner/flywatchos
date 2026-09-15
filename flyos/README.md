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
