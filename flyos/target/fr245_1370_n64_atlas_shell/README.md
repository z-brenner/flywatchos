# FR245 13.70 N64 Atlas Shell

This offline-only target is an immutable fork of
`fr245_1370_neural_specimen_n64_controls`. `hook.S` and `brain64_packed.c`
are still byte-for-byte the controls sources; `renderer.c` and `overlay.c`
have been rewritten around the 64-neuron Drosophila atlas. It adds an angular
64-neuron FlyOS face and a guarded button-ownership hook to the pinned
Forerunner 245 13.70 application image. It does not build or stage a Garmin
update by itself.

Input handling is still the controls target's: the face owns START, DOWN and
UP only when two bounded scans agree that the normal watch face is the first
visible Garmin view. LIGHT and BACK always keep their Garmin behavior.
Holding BACK while pressing another button also forces that button through to
GarminOS, providing an explicit system escape chord. Five-key ownership, the
deliberate Garmin system chord, and USB detach recovery are implemented on
top of this fork in later tasks; see
`docs/superpowers/specs/2026-09-15-flyos-n64-atlas-shell-design.md`.

`renderer.c` draws the atlas defined by `flyos/display/n64_atlas_layout.h`,
the header the host preview renderer and the emulator's mapping manifest also
read: 64 pairwise-disjoint 5x5 neuron masks inside the 98-pixel safe circle,
arranged as a sensory rim, a central ring, paired mushroom-body columns, a
modulatory midline, an identity core and a descending action fan. Magnitude
is carried by density alone (1, 9, 16 and 25 lit pixels). `renderer.h`
defines the presentation flags `FLY_UI_USB`, `FLY_UI_CHORD_ARMED` and
`FLY_UI_SYSTEM`; `overlay.c` only ever sets `FLY_UI_USB`, because nothing on
this image decides a chord hold or a system session yet. There is
deliberately no charging flag.

`state.h` defines the complement-protected 16-bit key-state word codec
(`fly_state_word`, `fly_state_read_local`, `fly_state_read_mode`) shared in
semantics with the Python `pack_state`/`unpack_state` helpers in
`tools/garmin-firmware/emulate_n64_atlas_shell.py`. It is not yet included by
`overlay.c`.

Each owned press posts the watch face's normal `0x50` redraw event through the
nonblocking Garmin UI queue. The renderer names the selected input in its
footer (`START // MOTOR BURST` and friends) and drives the corresponding
neuron. A short release remains visible for one rendered frame. With no key
down, the five effect names sit in the lateral corridors at the height of the
key each one belongs to.

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
