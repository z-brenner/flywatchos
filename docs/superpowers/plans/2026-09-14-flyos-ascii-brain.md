# FlyOS ASCII Brain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and verify an offline Forerunner 245 GarminOS overlay candidate whose full-screen ASCII fly brain visualizes the live activation of a deterministic 32-neuron fixed-point network.

**Architecture:** Keep the proven guarded display-flush hook and split the new runtime across the existing 1 KiB allocation and one independently proven unused firmware interval. Share a small 32-neuron model and coordinate table between host tests, preview tooling, and freestanding Cortex-M4 target code; package only when placement, memory-access emulation, strict reconstruction, and restore validation all pass.

**Tech Stack:** Freestanding C11, ARM Thumb assembly, GNU Arm Embedded Toolchain, Python 3, unittest, Unicorn, Pillow for an offline preview, PowerShell, existing Garmin `.GCD` tools.

**Spec:** `docs/superpowers/specs/2026-09-14-flyos-ascii-brain-design.md`, supplemented for Task 5 only by `docs/superpowers/specs/2026-09-14-flyos-neural-offline-package-addendum.md`.

## Global Constraints

- Keep the connected watch read-only throughout this plan; do not create, copy, rename, or delete any file on `D:`.
- Target only the pinned non-Music Forerunner 245 13.70 reconstructed image and retain the hook at `0x00009a20`.
- Simulate exactly 32 signed Q5.10 neurons using integer arithmetic, fixed sparse connections, and no heap, recursion, floating point, or peripheral writes.
- Reconstruct runtime state deterministically from the identity seed, stable RTC tick, and button mask; do not add on-watch persistence writes.
- Render exactly one fixed in-bounds glyph position for every neuron and clear all 57,600 logical framebuffer bytes on every eligible flush.
- Permit offline linking and emulation after a second allocation passes byte, reference, decoded-unit, pointer-scan, and overflow checks; permit target packaging only after section/update-metadata/resource/checksum coverage is also resolved.
- Preserve the semantic placement result `packaging_allowed: false`; emit synthetic 13.73 overlay and synthetic 13.74 official-code restore packages only when a separate exact decision says `offline_quarantine_construction_allowed: true`, and only into the resolved local quarantine root.
- Hash and log every firmware input and output with SHA-256.

---

### Task 1: Host 32-neuron reference model

**Files:**
- Create: `flyos/fly/brain32.h`
- Create: `flyos/fly/brain32.c`
- Create: `flyos/tests/test_brain32.c`
- Modify: `flyos/CMakeLists.txt`

**Interfaces:**
- Consumes: button mask bits 0 through 4 in the physical order defined by the spec.
- Produces: `FlyBrain32`, `fly_brain32_seed(FlyBrain32 *, uint32_t, uint32_t)`, `fly_brain32_step(FlyBrain32 *, uint8_t)`, `fly_brain32_reconstruct(FlyBrain32 *, uint32_t, uint32_t, uint8_t)`, `fly_brain32_level(const FlyBrain32 *, unsigned)`, and `fly_brain32_state(const FlyBrain32 *)`.

- [ ] **Step 1: Write deterministic model tests**

Create tests that assert identical seed/epoch/input tuples produce byte-identical state, adjacent epochs evolve, all four glyph levels are reachable, each pressed button immediately drives its corresponding sensory neuron above its unpressed twin, and 10,000 steps stay inside `[-16384, 16383]`.

- [ ] **Step 2: Run the new test and verify it fails**

Run: `cmake -S flyos -B flyos/build` then `cmake --build flyos/build --target flyos-brain32-tests`.

Expected: FAIL because `brain32.h` and its implementation do not exist.

- [ ] **Step 3: Implement the fixed-point sparse network**

Define `FLY_BRAIN_NEURONS 32u`, a struct containing `int16_t activation[32]`, `uint32_t rng_state`, `uint32_t epoch`, and `uint8_t state`. Implement xorshift32, saturating Q5.10 arithmetic, fixed edge tables for the five populations, bounded reconstruction of eight steps, the thresholds `128`, `256`, and `512` on absolute activation for levels 1 through 3, and state selection from neurons 29 through 31.

- [ ] **Step 4: Run model tests and the existing host suite**

Run: `cmake --build flyos/build --target flyos-brain32-tests flyos-tests` then `ctest --test-dir flyos/build --output-on-failure`.

Expected: PASS with deterministic behavior and no regression in the existing 64-neuron research model.

- [ ] **Step 5: Commit the model unit**

Commit: `feat(flyos): add deterministic 32-neuron watch model`

### Task 2: ASCII brain renderer and preview

**Files:**
- Create: `flyos/display/brain_ascii.h`
- Create: `flyos/display/brain_ascii.c`
- Create: `flyos/tests/test_brain_ascii.c`
- Create: `flyos/tools/render_brain_preview.py`
- Create: `artifacts/previews/flyos-ascii-brain.png`
- Modify: `flyos/CMakeLists.txt`

**Interfaces:**
- Consumes: `FlyBrain32` and `fly_brain32_level()` from Task 1.
- Produces: `FlyBrainPoint fly_brain_points[32]`, `fly_brain_ascii_render(uint8_t framebuffer[57600], const FlyBrain32 *, uint32_t, uint8_t)`, and a 240 by 240 preview image.

- [ ] **Step 1: Write coordinate and correspondence tests**

Assert 32 coordinates are distinct and lie within the brain interior, the renderer writes no guard bytes before or after a 57,600-byte framebuffer, the whole frame is initialized, and changing neuron `n` changes its glyph cell for every `n` from 0 through 31. Assert the four activation levels render visibly distinct `.`, `o`, `O`, and `@` pixel patterns.

- [ ] **Step 2: Run renderer tests and verify they fail**

Run: `cmake -S flyos -B flyos/build` then `cmake --build flyos/build --target flyos-brain-ascii-tests`.

Expected: FAIL because the renderer has not been implemented.

- [ ] **Step 3: Implement the scientific ASCII plate**

Use a compact bitmap font, fixed bilateral silhouette strokes, fixed neuron coordinates, sparse fixed connections, and activation pulse marks. Draw `FLY//32`, time or `PHASE`, `STATE`, phase/age, and `L 1 2 3 4`. Use only `0x00` and `0xff`, and clear the framebuffer before drawing.

- [ ] **Step 4: Generate and inspect the preview**

Run: `python flyos/tools/render_brain_preview.py --output artifacts/previews/flyos-ascii-brain.png`

Expected: a 240 by 240 image containing the full plate, a recognizable bilateral fly-brain outline, all 32 neuron glyphs, readable status fields, and no clipped pixels.

- [ ] **Step 5: Run renderer and host suites**

Run: `cmake --build flyos/build --target flyos-brain-ascii-tests flyos-tests` then `ctest --test-dir flyos/build --output-on-failure`.

Expected: PASS.

- [ ] **Step 6: Commit the renderer unit**

Commit: `feat(flyos): render live ASCII brain activity`

### Task 3: RTC and second-allocation evidence

**Files:**
- Create: `tools/garmin-firmware/find_overlay_allocation.py`
- Create: `tools/garmin-firmware/tests/test_find_overlay_allocation.py`
- Create: `artifacts/analysis/fr245-1370-second-allocation.json`
- Create: `docs/neural-overlay-placement.md`
- Modify: `docs/investigation-log.md`

**Interfaces:**
- Consumes: the pinned reconstructed 13.70 image, existing Ghidra reference exports, section maps, and RTC evidence around `0x4003d000`.
- Produces: a machine-readable interval with start, end, fill byte, every evidence source, a Boolean `link_and_emulate_allowed`, and a Boolean `packaging_allowed`; plus the approved stable RTC read algorithm.

- [ ] **Step 1: Write allocation-scanner tests**

Use synthetic images and reference lists to assert the scanner rejects a non-erased byte, a target reference in the middle or at either boundary, overlap with a protected interval, inadequate branch reach, and missing evidence input; assert it accepts only a fully covered clean interval.

- [ ] **Step 2: Run scanner tests and verify they fail**

Run: `python tools/garmin-firmware/tests/test_find_overlay_allocation.py -v`

Expected: FAIL because the scanner does not exist.

- [ ] **Step 3: Implement the conservative scanner**

Parse explicit image, base address, minimum length, protected intervals, reference targets, and section/metadata intervals. Return no candidate unless all evidence inputs exist and cover the requested image. Emit JSON with rejected candidates and exact reasons as well as the selected interval.

- [ ] **Step 4: Audit the pinned image and RTC reads**

Run the scanner against the reconstructed 13.70 code image and inspect disassembly/Ghidra evidence for `0x4003d000`, `0x4003d004`, and pinned function `0x00009038`. Use `0x000c4438` only as the older 3.10 cross-version comparison. Document whether direct stable reads are side-effect-free and whether a second allocation satisfies every spec check.

- [ ] **Step 5: Gate the result**

Set `link_and_emulate_allowed` true only if the exact bytes, decoded units, references, pointer scans, branch reach, and RTC reads are proven. Set `packaging_allowed` true only if the section/update-metadata/resource/checksum overlap checks are also proven. If only the first gate is true, execute Task 4 offline and keep Task 5 blocked.

- [ ] **Step 6: Run scanner and existing firmware tests**

Run: `python -m unittest discover -s tools/garmin-firmware/tests -p 'test_*.py' -v`

Expected: PASS.

- [ ] **Step 7: Commit the evidence unit**

Commit: `tools(firmware): prove neural overlay placement`

### Task 4: Split freestanding target and emulator

**Files:**
- Create: `flyos/target/fr245_1370_neural_overlay/overlay.c`
- Create: `flyos/target/fr245_1370_neural_overlay/hook.S`
- Create: `flyos/target/fr245_1370_neural_overlay/linker.ld`
- Create: `flyos/target/fr245_1370_neural_overlay/build.ps1`
- Create: `flyos/target/fr245_1370_neural_overlay/README.md`
- Create: `tools/garmin-firmware/emulate_neural_overlay_payload.py`
- Create: `tools/garmin-firmware/tests/test_emulate_neural_overlay_payload.py`

**Interfaces:**
- Consumes: Task 1 model semantics, Task 2 layout, and the exact accepted allocation/RTC contract from Task 3.
- Produces: a four-byte hook, one binary per linker allocation, ELF/map/disassembly files, and an emulator report for target behavior and memory access.

- [ ] **Step 1: Write emulator failure tests**

Test all three display guards, five button combinations, RTC rollover between stable reads, all 32 glyph levels, framebuffer canaries, dirty/dispatch calls, stack bounds, and rejection of any write outside framebuffer/stack. Require the build and emulator to fail if placement evidence says `link_and_emulate_allowed` is false; a false `packaging_allowed` still permits offline Task 4 artifacts.

- [ ] **Step 2: Run emulator tests and verify they fail**

Run: `python tools/garmin-firmware/tests/test_emulate_neural_overlay_payload.py -v`

Expected: FAIL because the neural target and emulator do not exist.

- [ ] **Step 3: Implement and link the target**

Port the exact model and renderer semantics without libc. Keep the hook and proven guard/dirty/dispatch behavior. Read only the three GPIO PDIR words and two RTC registers. Add linker assertions for both exact allocation bounds and build-time checks for undefined symbols, hook length, segment overlap, and branch range.

- [ ] **Step 4: Build and emulate**

Run: `powershell -ExecutionPolicy Bypass -File flyos/target/fr245_1370_neural_overlay/build.ps1` and `python tools/garmin-firmware/emulate_neural_overlay_payload.py --self-test`.

Expected: both PASS, with SHA-256 output for every build artifact and no unauthorized memory access.

- [ ] **Step 5: Run all target and host tests**

Run: `python -m unittest discover -s tools/garmin-firmware/tests -p 'test_*.py' -v` and `ctest --test-dir flyos/build --output-on-failure`.

Expected: PASS.

- [ ] **Step 6: Commit the target unit**

Commit: `feat(flyos): build emulated FR245 neural overlay`

### Task 5: Quarantined candidate, restore wrapper, and audit report

**Files:**
- Create: `tools/garmin-firmware/neural_overlay_version_strategy.py`
- Create: `tools/garmin-firmware/tests/test_neural_overlay_version_strategy.py`
- Create: `artifacts/firmware/quarantine/Forerunner245_1373-flyos-neural-overlay.gcd.analysis-only.DO_NOT_INSTALL`
- Create: `artifacts/firmware/quarantine/Forerunner245_1374-official-payload-restore.gcd.analysis-only.DO_NOT_INSTALL`
- Create: `docs/neural-overlay-live-proposal.md`
- Modify: `docs/boot-chain.md`
- Modify: `docs/recovery.md`
- Modify: `docs/session-report.md`
- Modify: `docs/investigation-log.md`

**Interfaces:**
- Consumes: verified target binaries and hashes from Task 4, pinned official 13.70 payload, existing package builders/validators, Task 3 placement evidence, and the exact offline-construction decision required by the addendum.
- Produces: two quarantined `.GCD` artifacts, strict validation reports, hashes, and the exact live-write approval brief.

- [ ] **Step 1: Write strict packaging tests**

Assert the 13.73 candidate changes only the declared version fields, four-byte hook, declared payload intervals, and required package checksums. Assert the 13.74 wrapper reconstructs official 13.70 code/resource content except for the coherent decoded header and explicitly named additive repair byte. Reject mismatched HWID, a missing/false/mismatched offline-construction decision, changed provenance, wrong version ordering, unexpected differing ranges, output alias/escape, or any output outside the exact local quarantine root.

- [ ] **Step 2: Run package tests and verify they fail**

Run: `python tools/garmin-firmware/tests/test_neural_overlay_version_strategy.py -v`

Expected: FAIL because the strategy script does not exist.

- [ ] **Step 3: Implement guarded package construction**

Reuse existing parsers and validators without weakening their generic rules. Preserve `packaging_allowed: false`; require a separate `offline_quarantine_construction_allowed: true`, exact build/evidence/review hashes, HWID 3076, and pinned official input hashes before writing outputs. Produce machine-readable changed-range, containment, and restoration reports.

- [ ] **Step 4: Build and validate both packages offline**

Run the strategy script, strict reconstruction, `gcd_candidate_verify.py`, `full_image_validator.py`, and the complete firmware unittest suite.

Expected: all checks PASS; no file is written to `D:`.

- [ ] **Step 5: Record evidence and exact next-action risks**

Document package filenames, sizes, SHA-256 values, all modified address ranges, validation results, the nonzero brick risk, recovery limits, and official restoration procedure. Keep the feasibility verdict YELLOW unless standalone boot or full nonboot recovery has separately been demonstrated.

- [ ] **Step 6: Verify the connected device was untouched**

Read `D:\Garmin`, confirm `GUPDATE.GCD` and `force.tmp` are absent, record volume health, and compare a fresh read-only file manifest with the last preserved manifest while excluding expected device-generated timestamps from equality claims.

- [ ] **Step 7: Run the complete verification suite**

Run all host tests, all firmware Python tests, both target build scripts, strict package verification, and SHA-256 hashing.

Expected: PASS with the exact counts and hashes recorded in `docs/investigation-log.md`.

- [ ] **Step 8: Commit the offline release unit**

Commit: `build(flyos): prepare neural overlay and restore pair`
