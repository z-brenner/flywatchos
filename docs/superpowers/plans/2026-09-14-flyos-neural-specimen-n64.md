# FlyOS Neural Specimen N64 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and validate an offline FR245 GarminOS-resident N64 overlay with a 64-neuron model, a redesigned fly-head face, honest sensor adapters, and Garmin system-screen coexistence.

**Architecture:** A pure fixed-point `FlyBrain64` consumes a validity-tagged input snapshot. A renderer maps exactly 64 activations into an 8x8 scientific fly-head plate. The target wrapper supplies only proven read-only inputs, yields to Garmin critical UI, and uses only independently audited firmware allocations.

**Tech Stack:** C11 host code, Cortex-M4 Thumb/soft-float GCC target, CMake/CTest, Python `unittest`, Unicorn, Capstone, Ghidra, existing GCD reconstruction tools.

**Spec:** `docs/superpowers/specs/2026-09-14-flyos-neural-specimen-n64-design.md`

## Global Constraints

- No live watch write, reset, erase, flash, downgrade, or filesystem mutation.
- Preserve GarminOS button ownership and all critical system screens.
- Use only proved side-effect-free reads; no direct sensor-bus or PMIC transactions.
- Exactly 64 Q5.10 neurons; optional invalid inputs contribute zero and display `--`.
- Target-owned stack call chain must remain at or below 384 bytes.
- All artifacts stay offline, quarantined, SHA-256 hashed, and absent from `tools/live-proof/stage-gupdate.ps1`.

---

### Task 1: Fixed-point Brain64 and input contract

**Files:**
- Create: `flyos/fly/brain64.h`
- Create: `flyos/fly/brain64.c`
- Create: `flyos/tests/test_brain64.c`
- Modify: `flyos/CMakeLists.txt`

**Interfaces:**
- Produces: `FlyBrainInputs`, `FlyBrain64`, `fly_brain64_seed`, `fly_brain64_step`, `fly_brain64_reconstruct`, `fly_brain64_level`, `fly_brain64_state`.

- [ ] Write tests that require exactly 64 activations, deterministic reconstruction, clamping over 10,000 steps, five independent button drives, zero contribution from invalid optional channels, and changed cardiac/motion/power populations when their validity bits are set.
- [ ] Run `cmake --build flyos/build; ctest --test-dir flyos/build -R brain64 --output-on-failure` and record the expected RED failure because the Brain64 API does not exist.
- [ ] Implement the public input structure with `buttons`, `valid_mask`, `heart_rate_bpm`, `heart_rate_delta`, `motion`, `battery_percent`, and `charging`; implement the population layout from the spec using one `int16_t previous[64]` snapshot and deterministic sparse integer connections.
- [ ] Rebuild and run the focused test to GREEN, then run all CTest tests.

### Task 2: N64 renderer and golden previews

**Files:**
- Create: `flyos/display/neural_specimen.h`
- Create: `flyos/display/neural_specimen.c`
- Create: `flyos/tests/test_neural_specimen.c`
- Create: `flyos/tools/render_neural_specimen_preview.py`
- Modify: `flyos/CMakeLists.txt`

**Interfaces:**
- Consumes: `FlyBrain64` and `FlyBrainInputs` from Task 1.
- Produces: `fly_neural_specimen_points[64]` and `fly_neural_specimen_render(uint8_t framebuffer[57600], const FlyBrain64 *, const FlyBrainInputs *, uint32_t rtc_tick)`.

- [ ] Write failing tests for 64 distinct non-overlapping in-bounds cells, circular safe-area bounds, direct neuron-to-cell change locality, all four density levels, `--` for invalid sensors, physical button cause/effect labels, and full framebuffer ownership.
- [ ] Run the focused renderer test and record RED because the renderer is missing.
- [ ] Implement the centered `PHASE`/`FLYOS // N64` header, one angular head contour, antennae, faceted eye hatching, procedural 8x8 cells, status/event rails, and contextual labels. Use semantic color constants with a monochrome target fallback until Task 3 proves raw values.
- [ ] Generate host previews for quiet, each button, optional-sensor valid/invalid, charging, USB, and update/pass-through states; store PNG/PPM outputs beneath `artifacts/firmware/analysis/n64-previews/` with a SHA-256 manifest.
- [ ] Run the focused test and all CTest tests to GREEN.

### Task 3: Read-only Garmin state and color evidence

**Files:**
- Create: `tools/garmin-firmware/fr245_runtime_state.py`
- Create: `tools/garmin-firmware/tests/test_fr245_runtime_state.py`
- Create: `docs/runtime-state.md`
- Create: `artifacts/firmware/analysis/fr245-1370-runtime-state.json`

**Interfaces:**
- Produces an allowlist of image-bound read-only addresses/getters for home view, charging/USB, battery, HR, motion, and update pending; each entry has `status`, `validity_semantics`, and `side_effect_free`.
- Produces raw framebuffer color-role values only if supported by converter/resource evidence.

- [ ] Write failing scanner/report-schema tests requiring every requested signal and rejecting any enabled signal without a pinned address/getter, validity semantics, and side-effect-free evidence.
- [ ] Run the focused Python test and record RED because the analyzer is missing.
- [ ] Decompile the known USB, battery/PMIC, display/view, update, HR, and sensor-hub clusters from the pinned 13.70 Ghidra project. Record unavailable signals honestly; do not substitute peripheral transactions.
- [ ] Implement the reproducible evidence reporter and tests. Only mark a signal enabled when the static path proves a pure getter or stable RAM snapshot and Unicorn can allowlist every read.
- [ ] Recover framebuffer color encoding from the converter and resources. If exact hue mapping remains unproved, emit `target_palette_status: unavailable` and keep the live target monochrome.

### Task 4: Target integration, coexistence, allocation, and emulation

**Files:**
- Create: `flyos/target/fr245_1370_neural_specimen_n64/`
- Create: `tools/garmin-firmware/emulate_neural_specimen_n64.py`
- Create: `tools/garmin-firmware/tests/test_emulate_neural_specimen_n64.py`
- Create: `artifacts/analysis/fr245-1370-n64-allocation.json`
- Create: `docs/neural-specimen-n64-placement.md`

**Interfaces:**
- Consumes Tasks 1-3.
- Produces a hook and bounded payload segments plus manifest, disassembly, stack report, emulator report, and preview.

- [ ] Write failing emulator tests for guards, exact allowlisted reads, no out-of-frame/stack writes, BACK pass-through, unchanged non-home/critical frames, 64 cell correspondence, original dirty/dispatch calls, saved registers, and the 384-byte stack ceiling.
- [ ] Run the focused test and record RED because the target is missing.
- [ ] Audit candidate intervals from the pinned decoded image using byte, Ghidra reference, section, metadata, pointer, and cross-version checks; fail closed if sufficient space is not proved.
- [ ] Implement the target wrapper and linker assertions. Enable only Task 3 signals marked proved; invalid optional inputs remain zero/`--`.
- [ ] Build and run Unicorn until the focused tests, target build, and all firmware tests pass.

### Task 5: Quarantined package pair and independent review

**Files:**
- Modify or create a version-specific offline strategy under `tools/garmin-firmware/`.
- Create candidate and official-code restore wrappers only beneath `artifacts/firmware/quarantine/`, both ending `.analysis-only.DO_NOT_INSTALL`.
- Create build, strict verification, emulator, full-image, reconstruction, risk, and SHA-256 reports beneath `artifacts/firmware/analysis/`.
- Modify: `docs/investigation-log.md`, `docs/session-report.md`, `docs/boot-chain.md`.

**Interfaces:**
- Consumes the exact Task 4 binaries and pinned official 13.70 GCD.
- Produces no enabled live staging profile.

- [ ] Write failing package-strategy tests for exact versions, allowed ranges, reconstruction, create-new semantics, cleanup faults, immutable inputs, quarantine-only paths, and rejection by the live staging script.
- [ ] Run focused tests and record RED for the missing N64 strategy/profile.
- [ ] Construct candidate and restore packages offline, enumerate every changed byte/range, hash every input/output, and retain the official helper stream.
- [ ] Run exact reconstruction, generic verifier profiles, full-image validation, target/emulator suites, full Python discovery, CTest, and checksum-ledger verification.
- [ ] Obtain independent spec, quality, allocation, stack, read-allowlist, and recovery-risk reviews. Resolve all Critical/Important findings and record remaining uncertainties.
- [ ] Present the exact candidate hash, size, destination, flash ranges, brick risk, recovery limits, and restore procedure for a separate live-write decision. Do not stage it.
