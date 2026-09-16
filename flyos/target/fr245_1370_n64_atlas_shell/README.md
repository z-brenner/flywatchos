# FR245 13.70 N64 Atlas Shell

This offline-only target is an immutable fork of
`fr245_1370_neural_specimen_n64_controls`, forked byte-for-byte at
`hook.S`, `overlay.c`, `renderer.c`, and `brain64_packed.c`. It adds an
angular 64-neuron FlyOS face and a guarded button-ownership hook to the
pinned Forerunner 245 13.70 application image. It does not build or stage a
Garmin update by itself.

The forked source's runtime behavior is currently unchanged from the controls
target: the face owns START, DOWN, and UP only when two bounded scans agree
that the normal watch face is the first visible Garmin view. LIGHT and BACK
always keep their Garmin behavior. Holding BACK while pressing another button
also forces that button through to GarminOS, providing an explicit system
escape chord. Five-key ownership, the deliberate Garmin system chord, the
64-neuron atlas renderer, and USB detach recovery are implemented on top of
this fork in later tasks; see
`docs/superpowers/specs/2026-09-15-flyos-n64-atlas-shell-design.md`.

`state.h` defines the complement-protected 16-bit key-state word codec
(`fly_state_word`, `fly_state_read_local`, `fly_state_read_mode`) shared in
semantics with the Python `pack_state`/`unpack_state` helpers in
`tools/garmin-firmware/emulate_n64_atlas_shell.py`. It is not yet included by
`overlay.c`.

Each owned press posts the watch face's normal `0x50` redraw event through the
nonblocking Garmin UI queue. The renderer shows the selected input in its
footer and drives the corresponding neuron amber. A short release remains
visible for one rendered frame.

Build and emulate from the repository root:

```powershell
flyos\target\fr245_1370_n64_atlas_shell\build.ps1
python -B -m unittest tools/garmin-firmware/tests/test_emulate_n64_atlas_shell.py -v
```

The build requires the local pinned firmware evidence and ARM toolchain. It
produces an ELF, map, disassembly, hook binaries, payload binaries, manifest,
and SHA-256 ledger in an isolated build directory. Generated files are not
source-controlled.

The display hook is fixed at `0x00009a20`; the pre-publisher key hook is fixed
at `0x0000fa48`. The payload uses only the two previously audited application
flash envelopes at `0x001f6000` and `0x001fa400`. The linker rejects overflows,
writable static storage, and undefined symbols.
