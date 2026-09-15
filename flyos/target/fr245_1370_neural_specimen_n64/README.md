# FR245 13.70 Neural Specimen N64

Offline-only GarminOS-resident target for the 64-neuron FlyOS face. It renders
the angular fly-head specimen only while the pinned Garmin watch-face predicate
is affirmative. BACK and every false or malformed home state pass through to
the original Garmin display unchanged.

Build from the repository root:

```powershell
flyos\target\fr245_1370_neural_specimen_n64\build.ps1
python -B -m unittest tools/garmin-firmware/tests/test_emulate_neural_specimen_n64.py -v
```

The build first verifies the pinned 13.70 image, runtime-state report, exact
signal and palette allowlists, and two-envelope allocation. It produces an ELF,
map, disassembly, `.su` files, extracted hook/primary/secondary binaries,
process-private deterministic host oracle, manifest, and SHA-256 ledger under
`build/`. Pass `-BuildRoot <empty-directory>` for an isolated rebuild and
`-EvidenceRoot artifacts/analysis` to deterministically generate the emulator
report, default/battery-100/saturated PPM+PNG previews, and evidence manifest.

Exact current bounds are documented in
`docs/neural-specimen-n64-placement.md`. This target cannot build or stage a GCD
and does not touch a connected watch.
