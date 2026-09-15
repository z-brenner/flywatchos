# FR245 13.70 neural overlay: offline split target

This target reconstructs the shared 32-neuron C model with identity `0x46594f53`
(`FYOS`) and renders the shared ASCII brain into the entire 240 by 240 logical
framebuffer. It runs inside the existing Garmin display flush path. It performs
no peripheral writes and has no writable static data, heap, runtime library,
floating point, or recursion.

The placement evidence currently permits **offline linking and emulation only**.
Its `packaging_allowed` value is false. This directory does not build an update
package or access a connected watch. The known unresolved allocation questions
remain in `artifacts/analysis/fr245-1370-second-allocation.json`.

## Exact layout

| Item | Address range | Size | Allocation |
| --- | --- | ---: | --- |
| Thumb BL hook | `0x00009a20..0x00009a23` | 4 bytes | One instruction |
| Entry and shared brain functions | `0x001f6000..0x001f6319` | 794 bytes | `0x001f6000..0x001f63ff` |
| Shared renderer and read-only tables | `0x001fa400..0x001fabfb` | 2,044 bytes | `0x001fa400..0x001fabff` |

`0x001f63ff` is exclusively reserved for a future package additive-checksum
repair byte. The linker limits primary payload to 1,023 bytes and secondary
payload to 2,048 bytes, with separate address, overflow, and overlap assertions.
The secondary segment has only four spare bytes. All source files of the shared
model/renderer are compiled directly, without copies or target-specific edits.

## Runtime contract

The entry requires a non-null framebuffer, backend word `0x1ffdb754 == 0xebfc`,
and startup byte `0x1fff223c == 1`. Any failed guard skips framebuffer and
peripheral access. All paths tail-dispatch to `0x0000e1a5` with `(framebuffer, 0)`.
An eligible path calls `0x0000f2e9` with `(0, 0, 240, 240)` after rendering.

An eligible sample reads exactly one GPIOA PDIR word at `0x400ff010`, one GPIOC
PDIR word at `0x400ff090`, and one GPIOD PDIR word at `0x400ff0d0`, in that order.
The active-low inputs C11, D10, D1, A20, A22 become mask bits LIGHT, START, BACK,
DOWN, UP. There are no GPIO writes.

RTC sampling reads seconds `0x4003d000`, prescaler `0x4003d004`, then seconds
again. A mismatch retries the same three-read sequence exactly once. A matching
sample returns `(seconds << 15) | (prescaler & 0x7fff)`. A second mismatch returns
the invalid sentinel `0xffffffff`; it never returns a mixed seconds/prescaler
sample. The shared renderer displays `PHASE`, so the sentinel is a deterministic
fallback phase rather than an asserted wall-clock value. This follows the
controller's Task 3 interface ruling, which supersedes the earlier Task 4 brief's
mixed-sample return sentence. Neither stock RTC routine `0x00009038` nor the
older-image address `0x000c4438` is called. RTC is never written.

## Stack bound

The enforced maximum target call-chain budget is **384 bytes**. GCC
`-fstack-usage` reports static frames and the build validator derives the linked
call graph from disassembly. Missing frame reports, dynamic frames, recursion,
unknown direct callees, or unexpected indirect transfers fail validation. It
conservatively adds caller frames even for tail branches.

The maximum linked chain is hook (0) → entry (96) → reconstruct (16) → step (216)
→ state update (0), totaling **328 bytes**. The rendering chain is at most
96 + 56 + 40 + 48 = 240 bytes. Unicorn independently measures SP on every executed
instruction and enforces the 384-byte budget. All target writes must be inside
the supplied framebuffer or mapped stack. This bound excludes stock dirty and
dispatch function frames and interrupt frames; live Garmin task headroom has
not been established.

## Reproduce and verify

Run from the repository root in PowerShell. The ARM GNU toolchain path can be
overridden with `-ToolchainRoot`.

```powershell
& ./flyos/target/fr245_1370_neural_overlay/build.ps1
python -B -m unittest discover -s tools/garmin-firmware/tests -p test_emulate_neural_overlay_payload.py -v
python -B -m unittest discover -s tools/garmin-firmware/tests -v
python -B tools/garmin-firmware/emulate_neural_overlay_payload.py --report artifacts/firmware/analysis/neural-overlay-emulation-1370.json --preview artifacts/firmware/analysis/neural-overlay-preview-1370.pgm
```

The build checks the machine-readable evidence flags and exact interval, hashes
the placement before compilation, and rejects a changed evidence hash during
post-link validation. The immutable firmware image hash must match its recorded
value. Every emulation reload checks placement, compiled-file, and shared-source
hashes against the build manifest; any change requires a new build. The current
placement hash and false packaging gate are carried into both manifest and report.

Outputs under `build/` include ELF, linker map, disassembly, symbols, object and
stack-usage files, hook and both payload binaries, `manifest.json`, and
`SHA256SUMS.txt`. The emulator uses Python `unicorn` and `capstone`; the native
oracle additionally requires host `gcc`. Oracle source, executable, and binary
results remain under this target's `build/` directory.

The build creates the retained native fixture under
`build/oracle/retained/tick-003da005-buttons-00/`. Its source, executable and output
hashes are included in the build manifest and both target/analysis checksum lists.
Report generation reads this validated fixture. Ordinary oracle tests use separate
`build/oracle/tests/tick-<tick>-buttons-<mask>/` paths, even for the report's exact
fixture, and cannot overwrite retained report evidence. The native compiler must
be MinGW GCC with linker `--no-insert-timestamp` support: this is feature-detected,
passed explicitly, and checked by requiring a zero PE timestamp. Unsupported
toolchains fail with a deterministic-oracle diagnostic. Clean fixture rebuilds
must preserve source, executable, and output hashes.

Unicorn executes the actual four-byte hook and both linked allocations. The
report covers all guards, released and single/all buttons, deterministic frames,
RTC evolution, one rollover retry, and a second mismatch. Every target memory
write is classified and included in a count and trace digest. Checks enforce full
frame ownership, binary palette, canaries, saved registers, entry SP, exact
dirty/dispatch arguments, and exact peripheral reads. The harness captures the
actual `FlyBrain32` at shared renderer entry and verifies all 32 fixed glyph cells
and pulse pixels; it does not implement the neural model in Python. A native
build of the same shared C sources supplies an exact framebuffer/activation oracle.
All inter-allocation branch sites must execute in the report cases.

The original dirty and dispatch bodies are intercepted at their entry points.
Scheduling, interrupt timing, DMA/FlexIO/LCD behavior, the installer, and boot or
recovery behavior are outside this emulator's scope.
