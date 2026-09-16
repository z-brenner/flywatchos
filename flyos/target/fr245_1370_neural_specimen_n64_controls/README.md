# FR245 13.70 Neural Specimen N64 controls

This offline-only target adds an angular 64-neuron FlyOS face and a guarded
button-ownership hook to the pinned Forerunner 245 13.70 application image.
It does not build or stage a Garmin update by itself.

The face owns START, DOWN, and UP only when two bounded scans agree that the
normal watch face is the first visible Garmin view. LIGHT and BACK always keep
their Garmin behavior. Holding BACK while pressing another button also forces
that button through to GarminOS, providing an explicit system escape chord.

Each owned press posts the watch face's normal `0x50` redraw event through the
nonblocking Garmin UI queue. The renderer shows the selected input in its
footer and drives the corresponding neuron amber. A short release remains
visible for one rendered frame.

Build and emulate from the repository root:

```powershell
flyos\target\fr245_1370_neural_specimen_n64_controls\build.ps1
python -B -m unittest tools/garmin-firmware/tests/test_emulate_neural_specimen_n64_controls.py -v
```

The build requires the local pinned firmware evidence and ARM toolchain. It
produces an ELF, map, disassembly, hook binaries, payload binaries, manifest,
and SHA-256 ledger in an isolated build directory. Generated files are not
source-controlled.

The display hook is fixed at `0x00009a20`; the pre-publisher key hook is fixed
at `0x0000fa48`. The payload uses only the two previously audited application
flash envelopes at `0x001f6000` and `0x001fa400`. The linker rejects overflows,
writable static storage, and undefined symbols.

See `docs/neural-specimen-n64-controls-placement.md` for the exact runtime
gate, button policy, memory ownership, stack bound, and remaining risks.
