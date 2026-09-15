# FlyOS ASCII Brain Overlay Design

## Scope and evidence boundary

This increment builds a GarminOS-resident FlyOS overlay for the non-Music Forerunner 245 firmware 13.70 image. It keeps the already demonstrated display-flush interposition and five read-only GPIO inputs. It does not replace the Garmin bootloader, initialize hardware from reset, bypass a signature check, or write persistent state from the watch.

The deliverable is an offline, reproducible candidate and a matching official-code restore wrapper. Neither artifact may be copied to the connected watch as part of implementation or validation. A live write remains a separate action requiring the artifact hash, byte destination, affected update regions, brick risk, known recovery limits, and restoration procedure to be presented for exact approval.

## Runtime model

The overlay simulates exactly 32 signed fixed-point neurons:

| IDs | Population | Role |
|---|---|---|
| 0-4 | sensory | LIGHT, START, BACK, DOWN, UP button inputs |
| 5-12 | heading | eight-node central-complex-inspired recurrent ring |
| 13-24 | association | sparse excitatory and inhibitory recurrent integration |
| 25-28 | identity | slow recurrent motif biased by a compiled device-local identity seed |
| 29-31 | action | movement, arousal, and rest output channels |

Activations are signed Q5.10 integers clamped to `[-16384, 16383]`. A step uses only integer adds, shifts, comparisons, and a deterministic xorshift32 noise source. Each neuron decays by one quarter of its previous value and receives a fixed sparse list of weighted source activations. Button sensory neurons receive an immediate positive drive while their active-low GPIO input is pressed. The heading ring has neighbor excitation and opposite-node inhibition. The identity motif changes slowly and biases the association and action populations. No floating point, heap allocation, recursion, library calls, or peripheral writes are permitted.

For this first on-watch neural build, network state is reconstructed deterministically from a compiled identity seed, a stable RTC tick, and the current button mask on every eligible display flush. The renderer derives a coarse epoch from the RTC and advances a bounded number of steps from a deterministic epoch seed. This gives stable identity and evolving activity without claiming learned history survives reset. File-backed or flash-backed persistence is deferred until Garmin's filesystem write API, wear behavior, atomicity, and recovery path are independently understood and approved.

## Time source

The implementation may read the Kinetis RTC time-seconds and prescaler registers at `0x4003d000` and `0x4003d004` only after offline disassembly confirms those addresses and read-only semantics for the pinned image. The stable packed-tick routine in the pinned 13.70 image is at `0x00009038`; `0x000c4438` is its older 3.10 counterpart and must not be called by this target because the routine's stabilization loops are unbounded. Target code must use a bounded sequence: read seconds, read prescaler, read seconds again, and retry once if the seconds values differ. A stable sample returns `(seconds << 15) | (prescaler & 0x7fff)`; a second mismatch returns sentinel `0xffffffff`. It must never write an RTC register. If the static audit cannot support these exact reads, the overlay must use a deterministic framebuffer-call counter only in host/emulation builds and the target package must not be produced.

## ASCII brain display

The overlay owns all 240 by 240 logical framebuffer bytes on each eligible flush. It clears the entire frame before drawing, so no Garmin UI pixels remain visible.

The home screen resembles a monochrome scientific terminal plate:

- a sparse top line with `FLY//32`, a compact clock or epoch phase, and an activity marker;
- a bilateral fly-brain silhouette drawn from ASCII punctuation and line segments;
- exactly 32 fixed neuron positions inside the silhouette, one position per simulated neuron ID;
- a glyph selected directly from each neuron's absolute activation: `.` below 1/8 scale, `o` below 1/4, `O` below 1/2, and `@` at or above 1/2;
- sparse fixed connection strokes whose pulse marks appear only when the source activation crosses the `O` threshold;
- bottom status fields for `STATE`, identity age/phase, and five button markers in the confirmed physical order.

The mapping from neuron ID to screen coordinate is a compile-time table and is shared by the target renderer and host preview tests. Tests must prove there are 32 distinct in-bounds coordinates and that changing one neuron changes the pixels only in that neuron's glyph cell plus explicitly documented connection-pulse pixels. Each displayed activation therefore corresponds to the simulated neuron with the same ID.

The palette remains two logical values, `0x00` ink and `0xff` background. Apparent intensity comes from glyph density rather than unverified grayscale values. Time is shown only if the RTC read audit succeeds; otherwise the field is labeled `PHASE`.

## Input mapping

The target performs exactly one read of each GPIO PDIR word per sample and no GPIO register writes:

| Bit | Physical button | GPIO |
|---|---|---|
| 0 | top-left LIGHT | GPIOC11 |
| 1 | top-right START/STOP | GPIOD10 |
| 2 | bottom-right BACK | GPIOD1 |
| 3 | bottom-left DOWN | GPIOA20 |
| 4 | middle-left UP | GPIOA22 |

Inputs are active-low. The displayed bottom markers follow the user's observed labels `L 1 2 3 4` while the neural engine uses the physical meanings above.

## Firmware placement and hook

The patch at `0x00009a20` remains one four-byte Thumb `BL` to the overlay entry. The existing verified allocation `0x001f6000..0x001f63ff` may contain only the entry shim and code/data that fit its exact 1 KiB bound. A second interval may be used only if all of these checks pass against the pinned reconstructed 13.70 image:

1. every byte in the interval has the expected erased/padding value;
2. no decoded instruction, literal pool, relocation-like pointer, or Ghidra reference targets any byte in the interval;
3. the interval does not overlap a section boundary, update metadata, resource directory, checksum/signature field, or any interval already used by the full-screen overlay;
4. start and end addresses are recorded, and linker assertions prevent overflow;
5. full-image validation and Unicorn execution cover every inter-allocation branch.

Failure of any check stops target packaging. Host simulation and preview may still be delivered, but no installable or quarantine-named `.GCD` candidate may be emitted.

The overlay must retain the proven guards: non-null framebuffer, active backend value `0x0000ebfc`, and startup-complete byte equal to one. It must call the original dirty-region function for the full screen and tail-dispatch to the original display backend.

## Build, emulation, and package validation

The target is compiled for Cortex-M4 Thumb with soft-float and no runtime library. Build outputs include ELF, map, disassembly, hook binary, and every payload segment with SHA-256 hashes. The host model and renderer have deterministic tests. Unicorn emulation verifies:

- guard failures do not draw or read GPIO/RTC;
- an eligible flush clears exactly 57,600 framebuffer bytes and draws in bounds;
- GPIO and RTC accesses are confined to the approved read-only addresses;
- no write occurs outside the supplied framebuffer and emulated stack;
- all 32 activation levels affect their mapped display cells;
- the original dirty and dispatch calls occur with the proven arguments.

If placement and emulation succeed, the package builder creates a synthetic 13.73 overlay candidate in quarantine and a synthetic 13.74 restore wrapper containing the byte-exact official 13.70 code/resource payload. Both must pass strict reconstruction, package inspection, full-image validation, and the repository test suite. All inputs and outputs are hashed and logged.

## Recovery and safety

The known recovery mechanism requires GarminOS and USB mass storage to remain operational. The 13.74 wrapper can restore official application and resource contents after a successful boot. Recovery from a damaged bootloader, early crash before USB enumeration, or corrupted update machinery remains unknown. The candidate must therefore be described as a nonzero brick risk even after offline validation.

No live watch write, reset, downgrade, filesystem mutation, or speculative boot/security bypass is part of this design. The safest next experiment after offline completion is a user-approved copy of the single verified 13.73 candidate to `D:\Garmin\GUPDATE.GCD`, followed by the user's physical install action, only while the 13.74 restore wrapper and preserved official firmware are locally available.
