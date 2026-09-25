# FlyOS standalone K28 application design

Date: 2026-09-24

## Intent

FlyOS will replace the GarminOS application on the Forerunner 245 non-Music
(HWID 3076). The Garmin-owned resident loader below address `0x00003000` remains
as the launch and update boundary, but no GarminOS application code or service
may execute after the loader transfers control to FlyOS.

This is an evidence-first standalone firmware project, not another overlay.
The first implementation is offline-only. It must not produce or stage an
installable GCD until the project separately satisfies the existing recovery
and exact-artifact approval gates.

## Current evidence

- The resident loader accepts a full application image whose vector table is
  based at `0x00003000`; the official reset vector is `0x000031f1`.
- The normal updater's application destination is internal flash
  `0x00003000..0x001fffff` plus external QuadSPI
  `0x68617000..0x68916fff`. The resident prefix below `0x00003000` is outside
  this destination.
- Persistent custom Thumb execution, framebuffer rendering, raw button reads,
  and exact display-row packing are demonstrated, but only after GarminOS has
  initialized the hardware.
- `flyos/target/k28` already builds a freestanding Cortex-M4 image with a
  124-entry vector table, `.data`/`.bss` startup, a 64-neuron loop, and a
  RAM-only framebuffer.
- The standalone skeleton has no proved clock, watchdog, SRAM, power, panel,
  button-initialization, storage, USB, interrupt, or recovery contract. Its
  current SRAM boundary is provisional and is not a live-use claim.
- No FR245-specific nonboot recovery path is demonstrated. Retaining the
  resident loader does not by itself prove that it can recover a broken
  standalone application.

## Approaches considered

### Direct application replacement — selected

Recover the minimum official reset and board-initialization contracts, encode
them as small standalone drivers, and link FlyOS at `0x00003000`. This is the
only approach that meets the requirement that GarminOS be absent at runtime
while retaining the known loader boundary.

### Progressive shadow kernel — rejected

Continue running inside GarminOS while replacing services one by one. This is
useful as a measurement technique, but it is not the target architecture and
must not become the production runtime.

### Bootloader replacement — rejected

Replace the resident prefix as well as the application. The prefix is not
acquired, the device security state is unknown, and no nonboot restore path is
proved. It also contradicts the agreed decision to retain the resident loader.

## Definition of standalone

After the resident loader branches to the application reset vector:

- every executed application instruction belongs to the FlyOS image;
- no call, branch, vector, callback, data dependency, lock, task, or queue
  refers to the former GarminOS application;
- FlyOS establishes its own memory, clock, watchdog, interrupt, timing,
  display, and input state from reset;
- optional hardware remains disabled or untouched until its initialization
  contract is proved;
- the 64-neuron simulation and UI run in a cooperative FlyOS loop.

The retained loader is firmware infrastructure, not a runtime OS service.

## Architecture

### 1. Evidence receipts

Every target MMIO write must have a machine-readable receipt containing:

- source firmware SHA-256 and runtime base;
- source function/address and instruction bytes;
- register address, width, value or value mask;
- ordering and branch preconditions;
- confidence grade: statically confirmed, strongly inferred, or unknown.

Unknown writes are never copied into target code. A generated allowlist is the
single input shared by tests and the target build.

### 2. Boot contract

`Reset_Handler` remains at `0x000031f0`. It performs only this ordered sequence:

1. establish the proved stack and vector-table state;
2. initialize `.data` and `.bss` within the proved SRAM map;
3. apply the recovered watchdog policy;
4. apply the recovered core, bus, and peripheral clock policy;
5. initialize only the memory and buses required by the first milestone;
6. enter `flyos_target_main`.

No C code that may use initialized data runs before steps 1–2. Interrupts stay
masked until all enabled vectors and peripherals have handlers.

### 3. Hardware abstraction

New K28 board code is split into narrow units:

- `board_memory`: SRAM bounds, vector relocation, stack, `.data`, and `.bss`;
- `board_watchdog`: exact recovered watchdog transaction;
- `board_clock`: exact recovered clock tree and frequency facts;
- `board_time`: polling clock first; interrupts only after their contract is
  proved;
- `board_display`: panel power/reset, pin mux, FlexIO/DMA or equivalent
  transport, and the already proved row packer;
- `board_buttons`: pin mux/pulls plus the known active-low GPIO reads and
  deterministic debounce;
- `board_power`: only the rails required for MCU and display operation.

Drivers access MMIO through a tiny backend. The target backend performs
volatile reads/writes; the host backend records transactions for exact tests.
No generic hardware framework or dynamic allocation is introduced.

### 4. FlyOS runtime

The first runtime is deliberately cooperative and polling-based:

1. sample time and buttons;
2. update the 64-neuron state;
3. render the atlas UI into the 240×240 logical framebuffer;
4. transfer a complete or dirty frame through `board_display`;
5. service the watchdog according to the recovered policy;
6. enter a bounded idle interval.

This avoids claiming an RTOS, scheduler, DMA interrupt model, or low-power mode
before those contracts exist. Persistence, sensors, radio, GNSS, ANT/BLE, FIT,
and USB are outside the first milestone.

### 5. Failure behavior

- Every unexpected interrupt lands in a typed fault handler, never a silent
  infinite `WFI` with an unexplained peripheral still active.
- Host and instruction-level tests capture the fault reason and last completed
  boot stage.
- The offline image contains no guessed reset, erase, update, or recovery
  operation.
- No installable package is minted merely because the binary links or emulates.
  A package gate requires a separate safety review of boot behavior, loader
  compatibility, interruption behavior, and restore limitations.

## Evidence and implementation milestones

### Milestone A — reset-path contract

Recover the official reset call graph through the minimum clock/watchdog/memory
state needed to execute from internal flash and RAM. Deliver receipts, an MMIO
allowlist, and tests. Do not modify target MMIO code before the tests exist.

### Milestone B — emulated board-support package

Implement the boot and board units against the recording MMIO backend. Prove
exact transaction order, widths, masks, bounded polling, stack/SRAM limits, and
absence of writes outside the allowlist.

### Milestone C — standalone display loop

Connect the existing Brain64/atlas renderer to the recovered display transport.
Prove a complete expected panel transaction and framebuffer result under
instruction-level emulation. Add active-low button polling only after pin setup
is proved.

### Milestone D — immutable offline image

Build a deterministic flat image at `0x00003000`; verify vectors, sections,
branch closure, MMIO closure, no GarminOS symbol/address dependency, and exact
reconstruction from source. Name and policy must remain analysis-only and
non-installable.

### Milestone E — separate live-readiness decision

Only after A–D pass may the project assess whether a GCD can honestly be built.
That decision remains subject to `docs/recovery.md`, an independent safety
review, exact hashes/regions/restore disclosure, and a new artifact-specific
owner approval. This design does not pre-authorize a watch write.

## Verification

The minimum acceptance suite for the offline standalone image is:

- host unit tests for each boot/driver transaction;
- negative tests for reordered, missing, extra, wrong-width, and unbounded MMIO;
- ARM build with no undefined symbols and no writable executable data;
- vector-table, reset-vector, section, stack, and SRAM-bound checks;
- disassembly closure showing no branch into GarminOS application code;
- Unicorn reset-to-main execution with all MMIO reads scripted and every write
  checked against the receipt allowlist;
- exact display-frame and row-transport comparison;
- deterministic image SHA-256 across two clean builds;
- static scan proving no package/staging path is enabled.

## Explicit non-goals for the first implementation

- replacing or modifying the resident loader;
- flashing or staging the standalone image;
- claiming recovery from a nonbooting application;
- radio, GNSS, ANT/BLE, sensors, activity recording, FIT, USB mass storage, or
  Garmin compatibility;
- speculative register writes, signature bypasses, debug probing, or physical
  watch modification.

## Success criteria

The architecture phase is complete when the repository contains a reviewed,
deterministic standalone FlyOS application image that reaches the atlas loop in
instruction-level emulation using only recovered hardware contracts and no
GarminOS runtime dependency. Live installation is a later, independent safety
decision.
