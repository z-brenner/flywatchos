# Garmin firmware offline tooling

These tools never access the watch and never open input firmware for writing.

Acquire the pinned official Garmin packages and regenerate SHA-256 metadata:

```powershell
powershell -ExecutionPolicy Bypass -File tools/garmin-firmware/download_official_firmware.ps1
```

Parse each GCD, validate additive checkpoints, and extract decoded firmware
streams into the generated analysis tree:

```powershell
powershell -ExecutionPolicy Bypass -File tools/garmin-firmware/run_analysis.ps1
```

Run the parser tests:

```powershell
python -m unittest discover -s tools/garmin-firmware/tests -v
```

Import and analyze only the K28F internal-flash part of the non-Music 3.10 and
13.70 `fw_all` streams at base address `0x3000`. This bounded compatibility
pass is capped at `0x1fd000` bytes, ending at K28F address `0x1fffff`:

```powershell
powershell -ExecutionPolicy Bypass -File tools/garmin-firmware/run_ghidra_analysis.ps1
```

The `SeedCortexM.java` pre-analysis script reads the vector table, enables Thumb
mode for in-image handler targets, and seeds the reset handler before Ghidra's
normal analyzers run. Ghidra projects and logs are generated under the ignored
`artifacts/firmware/ghidra-code/` directory.

Reproduce the bounded 3.10 update-path decompiler export from that analyzed
project:

```powershell
powershell -ExecutionPolicy Bypass -File `
  tools/garmin-firmware/run_ghidra_decompile.ps1
```

The fixed address list covers the confirmed `GUPDATE.GCD` existence check,
parser entry, descriptor lookup, and filesystem open/close callees. The output
is written beneath the ignored analysis tree and never opens the firmware or
watch for writing.

The `fw_all` stream has a second executable region: file offset `0x1fd000`
maps to runtime address `0x04600000`. Rebuild both projects with internal flash
and that region in one address space using:

```powershell
powershell -ExecutionPolicy Bypass -File `
  tools/garmin-firmware/run_ghidra_dual_map.ps1
```

`MapExternalSegment.java` performs the second mapping before analysis. This
lets Ghidra resolve the `ldr.w pc, [pc]` veneers near the end of internal flash
to their external targets instead of reporting them as unmapped calls.

Generate conservative byte-level update/security anchor reports without
Ghidra:

```powershell
python tools/garmin-firmware/firmware_security_scan.py `
  artifacts/firmware/analysis/Forerunner245_310/stream_01_fw_all_bin.bin `
  --output artifacts/firmware/analysis/update-security-310.json
```

The report includes exact string addresses, exact pointer slots, Thumb-1
literal-load sites, common hash initial states, and explicit limitations. The
Ghidra `ExportUpdateEvidence.java` post-script emits recognized references and
containing functions for the same anchors.

Recover the GarminOS logical destination table for update types `0x05` and
`0x0e` from an extracted main stream:

```powershell
python tools/garmin-firmware/update_region_map.py `
  artifacts/firmware/analysis/Forerunner245_310/stream_01_fw_all_bin.bin `
  --output artifacts/firmware/analysis/update-regions-310.json
```

The scanner understands both executable mappings and dereferences the static
type table. Reported `0x68xxxxxx` values are Garmin logical-region addresses;
the tool does not assign them to a physical flash or storage chip.

Reproduce the cross-version update-storage anchors after the Ghidra trace:

```powershell
python tools/garmin-firmware/update_storage_trace.py `
  artifacts/firmware/analysis/Forerunner245_310/stream_01_fw_all_bin.bin `
  --version 3.10 `
  --output artifacts/firmware/analysis/update-storage-310.json

python tools/garmin-firmware/update_storage_trace.py `
  artifacts/firmware/analysis/Forerunner245_1370_GUPDATE/stream_01_fw_all_bin.bin `
  --version 13.70 `
  --output artifacts/firmware/analysis/update-storage-1370.json
```

This read-only tool pins each input by SHA-256, verifies the registered
`hwm_rgn_ufs` object/table, the QuadSPI peripheral literal, type-`0x0e`
destination, and its tail status offset. Method semantics and ordering come
from the focused Ghidra exports documented in `docs/update-validation.md`.

Generate the conservative driver-lead reports used by `docs/driver-leads.md`:

```powershell
python tools/garmin-firmware/driver_leads.py `
  artifacts/firmware/analysis/Forerunner245_310/stream_01_fw_all_bin.bin `
  --output artifacts/firmware/analysis/Forerunner245_310/driver-leads.json
python tools/garmin-firmware/driver_leads.py `
  artifacts/firmware/analysis/Forerunner245_1370_GUPDATE/stream_01_fw_all_bin.bin `
  --output artifacts/firmware/analysis/Forerunner245_1370_GUPDATE/driver-leads.json
```

This requires Capstone 5 (`python -m pip install capstone==5.0.7`). The report
records string locations, direct pointer slots, K28F peripheral-address
literals, and Thumb PC-relative loads that resolve to those literal slots. It
also reports the five-row encoded key-pin table and the cross-version
`0x2e`/`0x2f` backlight register-write signature. Display-specific results
include the `&dspl_smphr`-adjacent 57,600-byte framebuffer clear and the
`<FLEXIO0_BASE,FLEXIO0_IRQn>` object shared by both versions. It does not
assign names to unidentified functions or chip registers. By default it only decodes
addresses below `0x200000`, the end of the MCU's internal-flash window; later
stream bytes are inventoried as strings but are not treated as executable.

Decode the packed NXP-style FlexIO timer and shifter configurations used by
the display transport:

```powershell
python tools/garmin-firmware/display_flexio_config.py `
  artifacts/firmware/analysis/Forerunner245_1370_GUPDATE/stream_01_fw_all_bin.bin `
  --version 13.70 `
  --output artifacts/firmware/analysis/display-flexio-1370.json
```

This extractor is locked to the known SHA-256 hashes of the non-Music 3.10
and 13.70 streams. It emits exact `TIMCTL`, `TIMCFG`, `TIMCMP`, `SHIFTCTL`,
and `SHIFTCFG` values; the two releases decode identically. The associated DMA
request routing and the remaining signal-level unknowns are documented in
`docs/display-flexio.md`.

`gcd_inspect.py` implements the flat GCD record layout described by Herbert
Oppmann. It does not use the newer nine-byte marker heuristic because that
heuristic produced false record boundaries inside these Forerunner payloads.

Create the constrained, **offline-only** checksum experiment used to establish
what the documented byte checkpoints cover:

```powershell
python tools/garmin-firmware/gcd_mutation_lab.py `
  artifacts/firmware/originals/Forerunner245_1370_GUPDATE.GCD `
  artifacts/firmware/mutation-lab/Forerunner245_1370_metadata_only.GCD `
  --report artifacts/firmware/mutation-lab/metadata-only-report.json
```

The tool accepts only SHA-256-pinned non-Music source images and changes only
the terminal byte of the copyright metadata record. It then recomputes the
observed one-byte additive checkpoints. It has no option to alter firmware
payloads or descriptor fields. Its output must never be copied to the watch;
device acceptance and resident-loader policy remain untested.

Reproduce the confirmed application-side checks for an ordinary, non-delta
full-image package:

```powershell
python tools/garmin-firmware/full_image_validator.py `
  artifacts/firmware/originals/Forerunner245_1370_GUPDATE.GCD `
  --report artifacts/firmware/analysis/full-image-validation-official-1370.json
```

The validator requires valid outer additive checkpoints, rejects a
`GDELTA01` main-stream prefix, and requires the decoded type-`0x02bd` byte
sum's low byte to be zero. It deliberately does not model delta SHA-1 handling,
resident-loader authentication, version policy, installation, rollback, or
recovery. A passing report is not evidence of device acceptance.

Trace the separately extracted `0x0505` update helper without executing it:

```powershell
python tools/garmin-firmware/update_helper_trace.py `
  artifacts/firmware/analysis/inspect-310/stream_00_firmware_0505_bin.bin `
  --version 3.10 `
  --output artifacts/firmware/analysis/update-helper-310.json
```

The helper is hash-pinned and is only accepted at its observed SRAM_L load
address, `0x1ffc0000`. The report validates the independent native vector
table and its static source-region map. It does not execute the image, identify
the compound destination, or establish the omitted resident loader's
update-authentication policy.

Reproduce the compound `0xaf` destination map:

```powershell
python tools/garmin-firmware/update_af_trace.py `
  artifacts/firmware/analysis/inspect-310/stream_00_firmware_0505_bin.bin `
  --version 3.10 `
  --output artifacts/firmware/analysis/update-af-310.json
```

The hash-pinned report maps `0xaf` to internal application flash
`0x00003000..0x001fffff` followed by external QuadSPI
`0x68617000..0x68916fff`. The separate internal prefix below `0x3000` is not an
`0xaf` child. The tool performs no device I/O and does not model loader policy.

Reproduce the host-side model of the display pixel converter and compare it
byte for byte with the preserved 3.10 and 13.70 Thumb routines in an isolated
Unicorn VM:

```powershell
python -m pip install unicorn==2.1.4
python tools/garmin-firmware/display_row_model.py --verify `
  --output artifacts/firmware/analysis/display-row-verification.json
```

The emulator maps only local firmware copies plus synthetic source, staging,
stack, and flag memory. The model covers the observed in-bounds 240 by 240
caller contract. Passing this check validates conversion bytes and staging
offsets; it does not identify panel colors, wire signals, or safe hardware
initialization.

Build the checksum-neutral, **offline-only** visible-resource candidate:

```powershell
python tools/garmin-firmware/build_visible_proof_candidate.py `
  artifacts/firmware/originals/Forerunner245_1370_GUPDATE.GCD `
  artifacts/firmware/quarantine/Forerunner245_1370_fly-visible.gcd.analysis-only.DO_NOT_INSTALL `
  --report artifacts/firmware/quarantine/visible-proof-report.json

python tools/garmin-firmware/gcd_candidate_verify.py `
  artifacts/firmware/quarantine/Forerunner245_1370_fly-visible.gcd.analysis-only.DO_NOT_INSTALL `
  --official artifacts/firmware/originals/Forerunner245_1370_GUPDATE.GCD `
  --report artifacts/firmware/quarantine/visible-proof-candidate-verification.json
```

The builder accepts only the SHA-256-pinned official non-Music 13.70 package.
It changes the unique 16-byte English `Software Version` resource to
`FLY LIVES 2ALIVE`, which has the same length and additive low byte. It asserts
the expected resource contexts, exact offset, unchanged surrounding bytes,
unchanged checkpoint records, and all confirmed application-side full-image
checks. Output is restricted to a `quarantine` directory and must end in the
unrecognized `.gcd.analysis-only.DO_NOT_INSTALL` suffix. It must never be
renamed to `GUPDATE.GCD` or copied to a watch. Display use is strongly inferred
from the resource clusters and Garmin's documented About-page fields; the
indirect localization resolver call site and resident-loader policy remain
unresolved. See `docs/visible-proof-candidate.md`.
