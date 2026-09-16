# Investigation log

## 2026-09-13 — normal-mode inventory and backup

- Confirmed the host is Windows 11 Pro 64-bit, build 26200.
- Enumerated the connected watch using Windows PnP, storage, partition, and volume metadata only.
- Identified USB VID/PID `091e:2c04` and a single non-composite USB mass-storage function using SCSI transparent commands over bulk-only transport.
- Confirmed the mounted `GARMIN` volume is FAT16 and approximately 20.7 MB.
- Copied every accessible file and directory from the normal mounted volume to `artifacts/original-device-files/` with copy-only Robocopy options. No mirror, purge, move, delete, or source-write option was used.
- Backed up 204 files in 53 directories, totaling 4,630,156 bytes.
- Generated a per-file SHA-256 manifest and independently verified all 204 destination files against the live source; zero missing or mismatched files.
- Preserved all file timestamps. Forty-nine directory timestamps matched; four source directories reported the unrepresentable Windows epoch year 1601.
- Parsed the copied `GarminDevice.xml`: Forerunner 245, part/HWID `006-B3076-00`, installed software `10.40`, Connect IQ VM `3.3.1`. Unit ID was present and remains redacted.
- Classified the copied artifacts without exposing private filenames or file contents. No accessible update package or bootloader image was found.
- Did not enter diagnostic, recovery, preboot, or ROM-loader modes.
- Did not send Garmin protocol commands, install software, flash, erase, repartition, reset, downgrade, or otherwise write to the watch.
- Stored backup manifests under `artifacts/manifests/` and documented sanitized results in `docs/device-inventory.md`.
- Added `/artifacts/` to the repository `.gitignore` so the private device backup, exact-path manifests, and firmware binaries cannot be committed accidentally.

## 2026-09-13 — public hardware research and offline firmware analysis

- Correlated the connected non-Music model/HWID with photographed non-Music and Music teardowns and NXP documentation. Recorded confidence per component in `docs/hardware.md`.
- Confirmed the main processor family as NXP Kinetis K28F / Arm Cortex-M4F. Display-controller identity, non-Music external-storage part, button GPIOs, power sequencing, and debug accessibility remain unknown.
- Downloaded eight official Garmin packages to `artifacts/firmware/originals/`, preserved server timestamps, and recorded SHA-256 for every package. No package was copied to the watch.
- Acquired current non-Music system 13.70 plus current GPS 5.50, sensor-hub 18.04, and ANT/BLE 6.15 packages. The ANT/BLE package matches the component version reported by the backup.
- Confirmed that Garmin's former 11.03 beta bundle contained a 10.40 rollback image, but its origin URL now returns 404 and the archive copy was unavailable during this session. No exact 10.40 system image was obtained.
- Implemented a read-only GCD parser/extractor in `tools/garmin-firmware/`. It validates flat records, additive checkpoints, descriptor fields, stream lengths, SHA-256 hashes, and vector-table candidates.
- Parsed all eight packages. System packages contain a `0x02bd` application stream with an Arm Cortex-M vector table, reset vector `0x31f1`, and a strongly supported load address of `0x3000`; no bootloader record was present.
- Found no recognized cryptographic signature field in the outer GCD records. This does not establish that the resident loader accepts unsigned images; the loader and its authentication policy are absent from the packages.
- Recorded a YELLOW feasibility verdict and a six-scenario recovery assessment. No Forerunner-245-specific recovery from a damaged resident loader was established.

## 2026-09-13 — host-only FlyOS proof of concept

- Created a C11 host scaffold under `flyos/` with a 64-neuron signed Q8.8 network, deterministic evolution, five logical buttons, a 240×240 four-color framebuffer, and explicit unimplemented hardware stubs.
- Implemented versioned alternating persistence slots with CRC-32 validation and fallback from a corrupt newest slot. Irreversible lifecycle behavior remains disabled.
- Rendered and visually inspected the limited-palette `FLY LIVES` instrument face.
- Verified strict debug and release builds and host tests. Replaced standard `assert` checks with always-active test checks after release-mode verification exposed that `NDEBUG` disabled the original assertions.
- The scaffold is not a Garmin image and makes no claim of working display, button, power, storage, or boot code for the watch.
- No diagnostic mode, recovery mode, firmware transfer, flash write, filesystem write, reset, downgrade, or other modification of the watch occurred.

## 2026-09-13 — offline update-validation trace

- Installed Ghidra locally and analyzed copies of the extracted non-Music 3.10 and 13.70 `fw_all` streams at the supported application base `0x3000`.
- Added a reproducible byte-level scanner for update strings, exact pointer slots, Thumb literal loads, hash initial states, and PEM markers.
- Traced the 3.10 `0:/Garmin/GUPDATE.GCD` path through executable code at `0x000a0474`, caller `0x000ce154`, and parser opener `0x000a0184`.
- Confirmed the 13.70 K28 system-update source reference from code at `0x00009b82` in Ghidra function `FUN_00009b60`.
- Separated the `GarminDevice.xml` update-file metadata path from executable system-update handling.
- Tied the visible `Signature check failed on file:` path to the Connect IQ app/cache subsystem through adjacent `Garmin/Apps/TEMP`, `CIQSTORE.PUB`, and `tvm_cache.c` evidence. It is not evidence of system-image authentication.
- Found standard SHA-256, SHA-1, and MD5 initial-state constants, but no proved call-graph connection from system-update code to those primitives and no PEM certificate/public-key marker.
- Recorded the secondary memory-region mapping as unresolved because the extracted images exceed K28F internal flash and flat analysis produces unmapped high-address calls.
- Kept the verdict YELLOW: the resident loader below `0x3000`, its authentication policy, and safe failure/recovery behavior remain absent and unknown.
- All work in this phase was offline. Original downloaded packages and the live watch were not changed.

## 2026-09-13 — offline hardware-driver trace

- Added a reproducible Capstone scanner that inventories driver strings,
  K28F peripheral literals, and exact PC-relative Thumb loads in the executable
  internal-flash window. Generated and hashed reports for non-Music 3.10 and
  13.70 under the ignored firmware-analysis tree.
- Confirmed matching RTC clusters in both versions through 19 loads of the
  `0x4003d000` base. Identified stable seconds/prescaler read routines and an
  interrupt-register bit-clear routine at version-specific addresses.
- Confirmed matching native K28F USB high-speed/PHY clusters through 24
  resolving loads in each version and corroborating `HWM_usb main` and
  USB-manager strings.
- Recovered generic key-manager ISR/deferred-work setup in both versions. A
  later pass recovered the five GPIO pins and board-init path described below.
- Identified matching PMIC scheduler and battery-telemetry routines. A later
  pass recovered the bus endpoint and backlight register-write path described
  below; charger configuration and rail mapping remain unknown.
- Confirmed FAT16/TFS parsing code and a Garmin UFS region layer. The physical
  non-Music storage medium and block driver remain unknown.
- Found a 3.10 backlight work-item lead. A later pass recovered its PMIC write
  path, while the panel controller, framebuffer, and display-init sequence
  remain unknown.
- Kept all work offline and did not access or modify the watch or the preserved
  original firmware packages.

## 2026-09-13 — bounded Ghidra decompilation

- Installed official Ghidra 12.1.3 locally from the NSA GitHub release. The
  preserved archive SHA-256 is
  `93a5d11a9ad510622acaaf908c556a7b9b764d338e78a7567f3689bf5081fd54`
  and matches the publisher's checksum. Fixed and verified the installer's
  default-path handling so its documented command now reruns idempotently.
- Corrected the raw-import boundary to the K28F internal-flash interval
  `0x00003000` through `0x001fffff`; trailing stream bytes are no longer
  misclassified as executable code while their runtime mapping is unknown.
- Seeded 117 in-range Cortex-M vector targets and completed headless analysis
  for both non-Music 3.10 and 13.70 application streams.
- Decompiled the 3.10 `GUPDATE.GCD` orchestration path. Confirmed an open/close
  existence check, structured descriptor parsing, mapping of GCD IDs `0x02bd`
  and `0x03c1`, and device-family identifier handling for `0x0c04`.
- Found no proved cryptographic-verifier call in this application-side slice.
  The absent resident loader remains the decisive security unknown, so the
  feasibility verdict remains YELLOW.
- Stored the decompiler export under the ignored analysis tree with SHA-256
  `dfc1bf48cdd5adaca352df45d8ff8e82b23b8f695467dd609e05918d3ec6ad09`.
- Performed only offline analysis. The watch and original firmware artifacts
  were not written or modified.

## 2026-09-13 — freestanding FlyOS target skeleton

- Installed and SHA-256-verified Arm GNU Toolchain 15.2.Rel1 locally from the
  official Arm release asset. The preserved archive hash is
  `b40db54536d2fdf0ff21f4316b56c1fc4d3b782b792c5b298bcbeaf5eccedb96`.
- Added a freestanding Cortex-M4 target under `flyos/target/k28/`, linked at the
  observed application base `0x3000`.
- Matched the official `0x1f0`-byte vector layout and produced reset vector
  `0x31f1`. Added build-time rejection for an unexpected stack/reset vector or
  undefined symbol.
- Built a 1,464-byte raw binary with 57,740 bytes of BSS. It runs the integer
  fly network and renders `FLY LIVES` into a volatile RAM-only framebuffer.
- Marked the output non-installable because clock, watchdog, power, physical
  display, buttons, storage, and Garmin update-wrapper code remain absent.
- Did not package, transfer, or write the target binary to the watch.

## 2026-09-13 — update-parser preconditions

- Decompiled the next application-side layer below the 3.10 update
  orchestrator.
- Confirmed `GARMINd\0` header and `ff ff 00 00` trailer checks, typed record
  reads, paired image-marker scanning, and comparison with existing region
  metadata.
- Confirmed that these are unkeyed structure/compatibility checks. No
  cryptographic acceptance or loader installation decision was found.
- Preserved the second decompiler export with SHA-256
  `a05c3ef17a41e7a1b158b1df9fd8f704e64a42036e6f46e5474b58b760254b6e`.

## 2026-09-13 — raw normal-mode volume backup

- Opened the connected Garmin FAT volume through a read-only Windows raw-volume
  handle and copied its complete 20,807,680 bytes to the ignored host artifact
  tree.
- Recorded SHA-256
  `256d1794be151fe435a0ef61eeb6dcbabdea8fc8e49029ef36199df94723087`.
- Extracted the image locally and independently matched all 204 visible files
  against the original backup manifest.
- Sent no command or data to the watch and performed no source write. This is
  still only the exported FAT volume, not a K28 flash or bootloader dump.

## 2026-09-13 - button and backlight static trace

- Recovered one five-row key table in each non-Music image. The stable pin map
  by internal key index is GPIOC11, GPIOD10, GPIOD1, GPIOA20, and GPIOA22.
  Version 13.70 adds an unresolved `0x100` behavior flag to index zero.
- The 13.70 deferred key routine uses a distinct `0x2ee`-tick delay for index
  zero and 500 for the other four indices. This strengthens the LIGHT/power
  inference without proving the physical label or scheduler tick duration.
- Independently verified the pin encoding in both versions: the interrupt path
  constructs `PORTA + port * 0x1000` and writes `1 << pin` to `PORTx_ISFR`.
  The 13.70 handler also reads the corresponding `GPIOx_PDIR` bit before
  scheduling deferred debounce work.
- Recovered the 13.70 board call graph from hardware-main dispatcher
  `0x0002387c` through display initialization at `0x0000f258` and later key
  registration at `0x0000f928`. Internal key indices are not yet mapped to four
  of the five printed button labels; index zero is only strongly inferred as
  LIGHT/power.
- Recovered the same backlight path across 3.10 and 13.70. The final converter
  writes one byte to registers `0x2e` then `0x2f` through bus 3, device address
  `0x28`. The controller's register names and safe power sequencing remain
  unknown, so these writes were not copied into FlyOS.
- Applied the established second-region mapping (file offset `0x1fd000` to
  runtime `0x04600000`) to locate the 13.70 WBL policy function at
  `0x047fcd54` and resolve its veneer to the internal brightness path.
- Confirmed that K28F SPI2 belongs to the Apollo sensor-hub transport/update
  cluster rather than the panel bus. A subsequent display-focused pass
  recovered the actual FLEXIO0/DMA display path recorded below.
- Updated `driver_leads.py` to report the key-pin table, cross-version
  `0x2e`/`0x2f` register-write signature, display framebuffer clear, and
  FLEXIO0 display object. Current report hashes are recorded in
  `docs/driver-leads.md`.
- All work in this pass was offline. The connected watch and preserved source
  firmware files were not accessed or modified.

## 2026-09-13 - dual executable map and installer trace

- Confirmed file offset `0x1fd000` of each non-Music `fw_all` stream maps to
  runtime `0x04600000`. Internal-flash absolute veneers resolve into coherent
  Thumb functions in this region.
- Rebuilt Ghidra projects with both executable regions and confirmed matching
  3.10/13.70 GCD descriptor parsers. The 13.70 parser handles `0x02bd`,
  `0x03c1`, and additionally `0x0008`.
- Traced the 3.10 parser into its installer state machine. The application
  checks the unkeyed GCD byte sum, performs SHA-1 digest comparisons, and writes
  selected typed streams through registered destination backends.
- Recovered the same static destinations from 3.10 and 13.70: type `0x05` uses
  logical region `0x68103000`/`0x15000`, while main type `0x0e` uses
  `0x68118000`/`0x4ff000`.
- Did not identify the physical medium behind those logical regions, erase
  order, rollback behavior, or any acceptance decision in the absent resident
  loader.
- Generated and SHA-256-hashed reproducible decompiler exports beneath the
  ignored firmware-analysis tree. No watch access or modification occurred.

## 2026-09-13 - FLEXIO display static trace

- Corrected the earlier classification of 13.70 function `0x0000f258`: it is
  the display-subsystem initializer called by the hardware-main dispatcher.
  Its 3.10 counterpart is `0x000b86f4`.
- Both initializers reference `&dspl_smphr` and clear exactly `0xe100`
  (57,600) bytes, establishing a 240 by 240 one-byte logical framebuffer at
  `0x3400e9cc` in 3.10 and `0x1ffde6e8` in 13.70.
- Recovered cross-version dirty-rectangle accumulators at `0x000b8794` and
  `0x0000f2e8`. They clamp to 240 by 240, align updates to eight pixels, and
  store at most 100 eight-byte rectangles.
- Traced updates from the logical framebuffer through the rectangle-aware
  flush functions (`0x000bf5dc` / `0x0000e98c`) and pixel-layout converters
  (`0x000bf54c` / `0x0000e8fc`) into 244-byte-stride staging buffers at
  `0x34000468` / `0x1ffcd294`.
- Identified the physical engine object `<0x400df000,0x46>` at `0x000bed78` /
  `0x0000e210`. NXP's pinned MK28FA15 SDK header and startup table confirm
  these values as `FLEXIO0_BASE` and `FLEXIO0_IRQn`. The path uses DMA base
  `0x40008000`, DMAMUX base `0x40021000`, and DMA channels 29 and 30.
- Recovered the stable display pin set: PTE6/PTE7 ALT2, PTE8/PTE11 ALT3,
  PTE12/PTE13/PTE16-PTE19 ALT7, and PTE9/PTE10 as GPIO. Transfer code writes
  the PTE9/PTE10 masks through GPIOE base `0x400ff100`.
- The external panel part, FlexIO shifter/timer-to-wire assignments, signal
  polarity, clock rate, row framing, exact color packing, and safe complete
  power sequence remain unknown. No hardware driver was added to FlyOS.
- All display analysis was offline against preserved copies. The watch and
  original firmware artifacts were not accessed or modified.

## 2026-09-13 - display converter offline oracle

- Transcribed the self-contained display pixel converter into
  `tools/garmin-firmware/display_row_model.py` and validated it against the
  original 3.10 and 13.70 Thumb instructions in Unicorn 2.1.4.
- Established the 244-byte row structure as a zero framing byte, 120 bytes
  derived with mask `0xea`, another zero, then the same framing around 120
  bytes derived with complementary mask `0x15`.
- Confirmed partial-update word rounding and exact preservation of untouched
  staging bytes. Confirmed that the runtime reverse flag applies a 180-degree
  row/pixel layout transform at this boundary.
- Ran 186 model-to-instruction comparisons across three fixed source vectors,
  all 65,536 ordered input-pixel pairs, full and partial rectangles, both
  reverse states, dispatch thresholds, and representable gate configurations.
  All passed. Sixty-three shared cases were also byte-identical between
  firmware 3.10 and 13.70.
- Wrote the ignored verification report with SHA-256
  `45dd56f563e81555120b04ef947d6798fd2ed508894abf05e890d758e2c7f122`.
  The model script SHA-256 for this pass was
  `c1348e6b928de233cb36558e496b8cdcc33e70f2b1daca035f27b117b0ff8b1f`.
- This result validates software layout only. Pixel color meaning, the
  electrical role of row-framing bytes, panel identity, FLEXIO timing, and the
  safe panel power/command sequence remain unknown. No watch access occurred.

## 2026-09-13 - QuadSPI update-storage trace

- Traced the registered region backend in non-Music 3.10 and 13.70 from the
  static type table through its method table and low-level storage routines.
- Confirmed that the backend anchored by `HWM\region\hwm_rgn_ufs.c: 40`
  accesses the K28 QuadSPI peripheral at `0x400da000` and its external-flash
  AHB window at `0x68000000`. Pinned NXP SDK headers independently identify
  those addresses as `QuadSPI0_BASE` and `FSL_FEATURE_QSPI_AMBA_BASE`.
- Confirmed that main update type `0x0e` is staged in external QuadSPI flash at
  `0x68118000..0x68616fff`. A whole-region request uses blank-aware 4 KiB
  erases at unaligned edges and 64 KiB erases in the aligned middle, followed
  by sequential programming that respects 256-byte page boundaries.
- Identified the type-`0x0e` status location at offset `0x4fd000`, physical
  address `0x68615000`. Erased `0xff` represents logical zero; the failure path
  clears a physical bit to mark failure without another erase. Both versions
  contain the same offset and helper behavior.
- Confirmed the application-side handoff ends in a restart request after a
  successful write. The resident loader remains absent, so its final-copy
  order, signature policy, rollback logic, and malformed-image recovery are
  still unknown.
- Added `update_storage_trace.py` and generated hash-pinned anchor reports for
  both versions. All work was offline against preserved firmware copies; the
  connected watch was not accessed or modified.

## 2026-09-13 - Native `0x0505` update-helper trace

- Extracted both non-Music `0x0505` streams as their own Cortex-M images and
  analyzed them offline with Ghidra at `0x1ffc0000`. Both have reset vector
  `0x1ffc01f1` at file offset `0x1f0`; 3.10 occupies 39,424 bytes through
  `0x1ffc99ff`, and 13.70 occupies 37,120 bytes through `0x1ffc90ff`.
- Confirmed that this stream is a temporary updater, not a resource: its static
  region table includes type `0x05` at `0x68103000` and type `0x0e` at
  `0x68118000`, matching the application-side staging map.
- Confirmed in the 3.10 helper's main loop that it reads type `0x0e` in chunks
  capped at `0x1e000` bytes and writes those chunks through destination type
  `0xaf`. That destination is a compound backend; its complete physical map is
  not yet recovered. The helper includes both QuadSPI and K28 internal-flash
  controller paths.
- The resident stage below `0x3000` remains absent. It must install and launch
  this helper after staging, but its authentication, rollback, interruption,
  and recovery policy are still unknown. The helper overlaps the final main
  application range, so a normal update cannot be treated as reversible.
- Added `update_helper_trace.py`, which hash-pins both helper streams and
  validates their vectors, header markers, and static region maps. The tool
  SHA-256 is `c7f0cb4968f61fa760e5eda05af46f2f67c6b15392a2475130c43035ba2f52ab`.
  The generated reports hash to
  `911c4fe1660c5271ed6c7dd6e9539adfcf8b1fc935ac97292fd494458b958905`
  (3.10) and
  `4121bbae3d1c8ff3987e390763a5de48f21117a93382ab68c37a7b31cb9fcf4d`
  (13.70). No watch access occurred.

## 2026-09-13 - Display FlexIO/DMA register decode

- Decoded the packed NXP-style FlexIO configuration tables called by display
  setup in non-Music 3.10 and 13.70. All initial `TIMCTL`, `TIMCFG`, `TIMCMP`,
  `SHIFTCTL`, and `SHIFTCFG` values are identical across the two releases.
- Confirmed shifter 0 as a six-bit parallel transmitter controlled by timer 7.
  eDMA channel 29 uses DMAMUX group-1 source 1 (`FLEXIO0 channel 0`) to stream
  32-bit words from the 244-byte-row staging buffer to `SHIFTBUF[0]`.
- Confirmed a second eDMA stream: channel 30 uses group-1 source 7
  (`FLEXIO0 channel 6`) and writes 32-bit control words to `SHIFTBUF[6]`.
  `SHIFTSDEN |= 0x41` enables both request sources.
- Decoded the transfer GPIO sequence: PTE10 is set high, PTE9 is set high
  after 21 timing units, FlexIO is enabled after at least 40 units, and PTE9 is
  cleared after another 42 units. Signal names and the timing unit remain
  unknown.
- Added the hash-pinned offline extractor
  `tools/garmin-firmware/display_flexio_config.py`, generated the two JSON
  reports, and documented the register tables and remaining blockers in
  `docs/display-flexio.md`.
- No watch access occurred. The recovered values are still not a safe hardware
  initialization recipe because panel identity, net mapping, clock rate, and
  power/reset ordering remain unresolved.

## 2026-09-13 - Public CIQ execution-path review

- Preserved the public `anvilsecure/garmin-ciq-app-research` repository at Git
  commit `216749fe32a81f33e20959db0de680c470bbbffe` and generated a recursive
  SHA-256 manifest. The manifest SHA-256 is
  `ea550fedbc2171d1824d0c2ab10878d2000b86762509a5f327069b60f9d8ba52`.
- Confirmed it concerns historical Connect IQ virtual-machine vulnerabilities
  on a Forerunner 245 **Music**, rather than a Garmin GCD bootloader bypass or
  unsigned-system-image installation path. Its documented virtual pointers are
  firmware-version-specific.
- The connected watch is non-Music HWID 3076 on system 10.40; applicability of
  any published vulnerability is unproven. The included public demonstration
  for another model reads memory and uploads it remotely, so no source artifact
  was executed or sent to the watch.
- Recorded the model/version applicability, privacy constraint, and resulting
  non-applicability to persistent FlyOS boot in
  `docs/ciq-execution-path-assessment.md`. The boot-chain verdict remains
  YELLOW. No watch access occurred.

## 2026-09-13 - Exact 10.40 acquisition follow-up

- Performed a read-only search of the local Garmin application/cache roots;
  none were present on this computer.
- Queried the four plausible historical Garmin download names for the
  non-Music and Music 10.40 GCD and 11.03 beta ZIP. All returned HTTP 404.
- The exact non-Music HWID-3076 10.40 system image remains unavailable. The
  preserved 3.10 and 13.70 non-Music packages remain the only system images
  used for offline static analysis. No watch access occurred.

## 2026-09-13 - GCD metadata/checkpoint laboratory experiment

- Added `gcd_mutation_lab.py` and its isolated test. The tool accepts only
  SHA-256-pinned non-Music system packages, changes only the final byte in the
  copyright metadata record, and offers no firmware-stream or descriptor
  mutation mode.
- Produced `Forerunner245_1370_metadata_only.GCD` from the preserved official
  13.70 image. The source hashes to
  `8ebefacf6bcc00bec0fb271596abfb9618f9a3114d32b3a106fbd27d5a366adc`; the
  metadata-only copy hashes to
  `c57ca87d0d048023c5c778cf3da09dcb99ebe7790bd8ff342159bcf41e2f650f`.
- Confirmed every documented byte checkpoint in the copy validates and both
  extracted decoded firmware streams remain byte-identical to the official
  package. This validates only the observed checksum layer. It does not test
  device acceptance, loader authentication, SHA-1 validation, or a firmware
  payload modification. The copy is prohibited from being copied to the watch.
- No watch access occurred.

## 2026-09-13 - USB availability observation

- The final host-only health query found that the normal `D:` volume was no
  longer mounted. Windows still identified the same `VID_091E&PID_2C04` USB
  mass-storage instance, but reported `CM_PROB_FAILED_START` (Code 10).
- A scoped Windows disable/enable request for that USB instance failed with a
  generic host-side error before it changed the binding. No reset, update,
  file write, flash operation, or watch protocol command was issued.
- Further device investigation requires the normal USB mass-storage volume to
  enumerate again. This observation is separate from the offline GCD work.

## 2026-09-13 - USB restored and filesystem observation preserved

- The same Garmin USB instance subsequently returned to `CM_PROB_NONE`; Windows
  reports a healthy FAT volume as `D:` and identifies it as Garmin FR245 Flash.
- Compared the live filesystem read-only with the original 204-file manifest.
  The current volume contains 208 files: four newly observed files, no missing
  original files, and two files whose current SHA-256 differs from the original
  backup.
- Preserved the four newly observed files, with timestamps and verified hashes,
  in `artifacts/device-observation-post-reconnect/`. The SHA-256 manifest and
  summary hash to `b7aae8d98a027c83ca3c94bc0b80a558a08c970924724ae469bbe3b36a5d1417`
  and `8f1fb027b28773f0156f3093b5c7b7036cdf5b5e588fa663a50cae2b8c498220`.
- Preserved current versions of the two changed pre-existing files separately,
  preserving the original backup unchanged. Its comparison manifest and summary
  hash to `4bb89695c41cb8bf9ad4f8c03b53d5524a15368c2628d5f697abed32dbb2cc4b`
  and `d9dda1db8c3d4b8e565b586568e4966c9777ac43b72b2e55f0dc23cd43e8267b`.
- No file, update, command, or firmware data was written to the watch.

## 2026-09-13 - Main-payload checksum laboratory experiment

- Added `gcd_payload_mutation_lab.py`, restricted to the SHA-256-pinned
  non-Music 13.70 package. It alters one pinned printable `13.70` byte sequence
  inside the main `0x02bd` payload to `13.71`, then recomputes the documented
  outer one-byte checkpoints.
- The generated analysis-only package hashes to
  `d4c37a44d965501ae74c1911e7329774af18c28e20ce0134f4361224c97ce16f`; its
  report hashes to
  `8ee8c82a952e1d1fbf6225b22fd4c571e524289e710a0741af3c709318068754`.
- All local parser/checkpoint tests pass. This proves only that a payload change
  can retain the observed outer package structure and additive checksum. It
  neither regenerates nor bypasses the application SHA-1 comparison, any
  cryptographic authentication, or the omitted resident-loader policy. The
  generated package is prohibited from being copied to the watch.
- No watch access occurred.

## 2026-09-13 - SHA-1 comparison-source trace

- Decompiled the application-side callback construction and copy engine into
  `decompile-update-310-digest-source.txt`, SHA-256
  `f1ea63a7602703e2cae03f630ffb1b92ff7bec34fc5e92d4e4f46c445e6e3e5f`.
- Confirmed that the SHA-1 result is compared through a callback-driven copy
  engine, not against a simple visible outer-GCD descriptor field. The engine
  receives the expected 20 bytes through an internal backend/header callback.
- This rules out treating the recomputed outer byte checkpoints as sufficient
  validation. The exact expected-digest derivation and the resident loader's
  independent policy remain unresolved. No watch access occurred.

## 2026-09-13 - update-path and helper-address corrections

- Corrected the earlier `0x0505` helper classification. NXP's MK28FA15 memory
  map defines `0x1ffc0000` as `SRAM_L_BASE`; the helper runs from RAM and does
  not overlap the application's `0x00003000..0x001fffff` internal-flash range.
  Earlier log statements describing top-of-flash placement or overlap are
  superseded by this address-map correction.
- Corrected the earlier broad SHA-1 attribution. `FUN_000cc464` reaches SHA-1
  only after its callback-fed header path recognizes `GDELTA01`, so the traced
  digest comparison belongs to delta handling. In the non-delta full-image
  fallback, `FUN_000ce038` sums the selected payload in at most `0x100`-byte
  chunks, requires the low byte to be zero, and then calls `FUN_000a0494`.
  Earlier log statements implying a SHA-1 check on an ordinary full image are
  superseded by this control-flow correction.
- Added `full_image_validator.py` to reproduce only the confirmed ordinary
  full-image checks. Its SHA-256 is
  `f37fd6622f958e5fa4a265d176e534fcfae491ac783a60c1679f2ab506707fd7`.
  Official and laboratory report hashes are
  `ca3fe52d2063f5cea76102d316e5b512edc06c0414c2ab56cf8c2257b56c678a`
  and `0b995fb48a65b0b4ed8a9899b1afb4ccc5eb6de8d9fd87152ae0309edb2cc5d8`.
- These corrections do not establish device acceptance, arbitrary execution,
  loader authentication policy, rollback, or recovery. No watch access
  occurred.

## 2026-09-13 - exact 10.40 package provenance recovered

- Recovered Garmin's archived non-Music product `14935` support page from the
  2022-07-20 Internet Archive snapshot. It identifies the official beta archive
  as `Forerunner245_1103Beta.zip`, describes version 11.03 as changes from
  10.40, and names the included rollback image `GUPDATE-1040.GCD`.
- Preserved the HTML evidence as
  `artifacts/firmware/analysis/garmin-14935-20220720063806.html`, SHA-256
  `4dee13ab4b15758cb299e4b6daf0220ccc1582ce230c6426fc9798c1a62b0adf`.
- The exact live Garmin ZIP URL returns HTTP 404, and the Internet Archive CDX
  query has no captured ZIP. The exact connected-version binary remains
  unavailable, so no unverified mirror was accepted as an original artifact.
- No watch access occurred.

## 2026-09-13 - FlyOS target staging-row integration

- Added the byte-exact Garmin 240-byte to 244-byte row converter to the
  freestanding K28 build. Each target loop now converts the first `FLY LIVES`
  text row and retains the staged bytes in RAM for debugger or emulator
  inspection; it still performs no peripheral access.
- The rebuilt target ELF is 59,628 bytes including BSS and hashes to
  `1fec065efb01f0675f6532a9da814d613339b15ac730c987391d8bc8114c81d8`;
  its flat binary hashes to
  `381e6071ac55cae620bc61d787f2ac5b07ffd039fae0a54f03ef7915459d108a`.
- The host test and all 12 firmware-tool tests pass. The target remains marked
  non-installable because display transport, clocks, power sequencing, input,
  storage, and the update wrapper are incomplete.
- No watch access occurred.

## 2026-09-13 - compound update destination resolved

- Resolved type `0xaf` in both RAM-resident helpers. It concatenates internal
  child `0xab` (`0x00003000..0x001fffff`, `0x1fd000` bytes) and external
  QuadSPI child `0xac` (`0x68617000..0x68916fff`, `0x300000` bytes).
- The normal `0xaf` rewrite erases the internal child before the external
  child, copies in monotonically increasing chunks up to `0x1e000`, and
  checksums the destination. A separate type `0x2b` maps internal
  `0x00000000..0x00002fff` but is not an `0xaf` child.
- Added `update_af_trace.py`, SHA-256
  `03d450496c9bbd642be2a70673b4110beb40ac7458dabb5f875dc714567cf18b`.
  Its 3.10 and 13.70 reports hash to
  `0d2a5e1298450906f5a47537cf9441b0e8c0ec60970acea3af0420491a21bc22`
  and `715019810acca7c5d235a50464265f94d6937466ccab0827d6c8652782cb69c9`.
- This proves that the observed main-image copy excludes the resident prefix;
  it does not prove loader acceptance or recovery from a partially erased
  application. No watch access occurred.
- The recovered success path calls the application reset-vector pointer at
  `0x00003004` after copy/checksum completion. Separate static scans of both
  helper binaries found no standard SHA-1/SHA-256/MD5 initial-state set and no
  PEM certificate or public-key marker. This is negative evidence about the
  helper only; resident-loader authentication remains unknown. The 3.10 and
  13.70 scan reports hash to
  `fd4363767c8b664deb0cd5fbbf745244f05399286538446ec44e3fb3019e6f16`
  and `0a047c9f0b08108e40af58841034440d337cbc2f8afe6ebb06575a6fe81cf8eb`.

## 2026-09-13 - independent payload-mutation audit

- Independently verified that the 13.70 laboratory package differs from the
  official source at exactly two bytes: the `13.70` to `13.71` text edit and
  the final-byte additive compensation. Its inner sum and all five unchanged
  outer checkpoints validate.
- Preserved the audit as `payload-mutation-audit-1370.json`, SHA-256
  `4b972575cb94d7284cb856ed422697b153eef076463d764529ccd0ee62eaa73d`.
- Added a same-path guard to `gcd_payload_mutation_lab.py` so an input can never
  also be its output. The corrected tool hashes to
  `07bd727cb5a48f04837d24da11021b2482f065befa3057a7938e63bf96b9ed41`.
- Application and resident-loader acceptance remain unproven. No watch access
  occurred.

## 2026-09-13 - checksum-neutral visible-resource candidate

- Identified the unique non-Music 13.70 English `Software Version` resource at
  decoded main-stream offset `0x43eaa4` (raw GCD `0x448d1a`) beside `Unit ID`
  and `Bluetooth MAC Address`. A unique `About` label at `0x442524` lies in the
  System-settings label cluster. Garmin documents that System -> About shows
  the unit ID and software version. The same resource ordering persists in
  3.10. This strongly supports About-page display use, although the indirect
  localization-resolver call site remains unresolved.
- Added `build_visible_proof_candidate.py`, SHA-256
  `6bd15e28111ac17613d3a0b9c4df71fa5747b433f881e8a4c9959e5f43632a3d`.
  It changes exactly 16 bytes from `Software Version` to
  `FLY LIVES 2ALIVE`; both strings are 16 bytes and have additive low byte
  `0x51`. The NUL terminator, every surrounding byte, all checkpoint records,
  and all version fields stay unchanged.
- Generated only a quarantined artifact with an intentionally unrecognized
  suffix. Its SHA-256 is
  `b6e61518890d8082d96baf9bd89dcb131317f40060136093c9250e343a8ab4ba`;
  the complete diff report hashes to
  `6874e052a16de2c59513a5f0c26a73d9d11865ad3c32f29025de183d9d4fb259`.
  An independent `full_image_validator.py` run confirms all five outer prefix
  sums and the non-delta main-stream additive low byte; its report hashes to
  `938f66109a7eac2e51e33bc2c1b80369e93fd24093a60ace1e06ce72f29a5e0a`.
  The independent package-layout/diff verifier also returns `PASS`; its report
  hashes to
  `8112702ac52b2ca8bce861734741c98608bd83d3dda255464fad413b90f40653`.
- The experiment does not model loader authentication, acceptance, rollback,
  or recovery and does not demonstrate code execution. The candidate was not
  renamed, installed, executed, or copied to a device. No watch access
  occurred.

## 2026-09-13 - offline version and restore-candidate audit

- Recovered the 13.70 component selector at `FUN_001cd670`: the normal path
  schedules an incoming component only when its descriptor version is newer
  than the installed/current component version; descriptor field `0x0b`
  supplies an override flag but is zero in official 13.70. No `force.tmp`
  literal or model-specific sentinel path was found.
- The unchanged visible candidate therefore leaves official 13.70 subject to a
  same-version skip. Identified main header version `1370` at decoded `0x22c`
  plus the separate descriptor, event, display, and product-info version
  surfaces. The current-version reader's ultimate source and resident-loader
  policy remain unresolved.
- Added a fail-closed comparison/verifier report and two distinct quarantined
  restore hypotheses. The header-only package hashes to
  `da4e5d5f2d19ae8312cf56937873495547ea3c74142a26ae535c1059aa75b90b`.
  The stronger matched main descriptor/header 13.69 package hashes to
  `d89d52ca82586d7cea003c2f5b65b854790b572246164064fe3df079fa36ca2f`;
  its exact profile permits only its twenty enumerated descriptor, payload,
  checksum, and outer-checkpoint byte changes.
- The matched hypothesis is numerically newer than installed 10.40 and leaves
  official 13.70 numerically newer, but loader acceptance, signature policy,
  and recovery are not proven. All 29 firmware-tool tests pass. No watch
  access, transfer, staging, restart, or write occurred.

## 2026-09-13/14 - bounded live-proof preparation and independent hold

- Finalized the matched-13.69 visible-resource candidate at
  `artifacts/firmware/quarantine/Forerunner245_1369-matched-fly-visible.gcd.analysis-only.DO_NOT_INSTALL`.
  It is 5,120,675 bytes and has SHA-256
  `d89d52ca82586d7cea003c2f5b65b854790b572246164064fe3df079fa36ca2f`.
  Relative to official 13.70, exactly 20 raw bytes change: the main descriptor
  and installed-image header both become 13.69, the 16-byte About-page resource
  becomes `FLY LIVES 2ALIVE`, and two additive-checksum bytes are repaired.
- The exact named verifier profile `flyos-visible-proof-matched1369` passes and
  pins all 20 changes. The official 13.70 helper remains byte-identical. This
  verifies package identity, layout, the intended diff, and the recovered
  application-side checks; it does not exercise the absent resident loader.
- The restore hypothesis is now concrete: the connected 10.40 installation
  should treat matched 13.69 as newer, while an accepted candidate that boots
  and reports 13.69 should treat preserved official 13.70 as a normal forward
  update. The installed-version source, resident consistency checks, and that
  restoration sequence remain unproved. It provides no recovery if the watch
  cannot boot or enumerate normally.
- Built a separate same-version 13.70 overlay candidate, SHA-256
  `2ff367c2e7a80ec9ea2397352cba99c1f4d3212ab6dbea561050715155b1bf76`.
  It hooks the locked display path at `0x00009a20`, installs a 275-byte Thumb
  payload at `0x001f6000`, draws `FLY LIVES` into the live framebuffer, marks
  the rectangle dirty, and resumes Garmin's original flush. The exact reserved
  interval `0x001f6000..0x001f63ff` is erased in the official image and has
  zero Ghidra static references. The wider erased tail is not wholly free: it
  has 19 later data references. The overlay remains offline and is not the
  proposed first live experiment.
- Added a fail-closed staging guard at `tools/live-proof/stage-gupdate.ps1`.
  Its candidate dry run, performed without `-Execute`, verified the pinned
  candidate hash and size, connected model/part/version, the drive association
  to the live Garmin FR245 USB disk and VID `091E` / PID `2C04` parent, healthy
  GARMIN FAT volume, free space, and absence of `Garmin/GUPDATE.GCD`. Catchable
  copy, flush, and readback failures now remove only the file newly created by
  that invocation; forced termination or USB loss can still prevent cleanup.
  The dry run created no file. The script was not run in execute mode, and no
  update was staged, installed, or accepted.
- An independent audit returned **NO-GO / `hold_for_evidence`** for every live
  candidate under the required reversibility standard. The matched-13.69
  resource candidate is the strongest restore-oriented hypothesis; the
  executable overlay has additional runtime-hook risk. In either case, an
  accepted update rewrites the complete internal application and external
  code/resource regions, while resident-loader validation/failure ordering and
  recovery without a booting application remain unknown.
- A 2026-09-13/14 public-web recheck of Garmin's Forerunner 245 update
  collection and support/manual material still showed 13.70 as the latest
  Garmin-published system version. It found no Garmin-documented HWID-3076
  preboot loader, emergency USB reflash, or recovery procedure for a watch that
  no longer enumerates normally. This is a dated absence-of-evidence finding,
  not proof that Garmin service tooling or an undocumented loader does not
  exist.
- Feasibility remains **YELLOW**. The largest unknowns are the resident
  loader's authentication and pre-erase failure behavior, plus recovery when
  the normal application and USB mass-storage path are unavailable.

## 2026-09-13 - approved matched-13.69 staging

- Received explicit approval for the exact live action documented in
  `docs/live-proof-proposal.md`: stage the matched-13.69 resource candidate,
  verify its watch-side hash, safely eject, and accept the on-watch update with
  the disclosed application/QSPI rewrite and nonboot brick risk.
- Ran `tools/live-proof/stage-gupdate.ps1 -Mode Candidate1369 -Execute`. The
  guard revalidated the connected HWID-3076 Forerunner 245, reported software
  10.40, healthy GARMIN FAT volume, USB VID `091E` / PID `2C04`, pinned source
  size 5,120,675 bytes, and source SHA-256
  `d89d52ca82586d7cea003c2f5b65b854790b572246164064fe3df079fa36ca2f`.
- The guarded copy, forced flush, full watch-side readback, length check, and
  SHA-256 check completed successfully. `D:\Garmin\GUPDATE.GCD` matched the
  approved SHA-256 exactly.
- Requested Windows' removable-volume Eject verb. It succeeded and `D:`
  disappeared. Subsequent read-only polling found neither the USB parent nor
  the volume. The host cannot observe or press the watch's physical update
  confirmation; device-side acceptance and installation remain pending direct
  observation.

## 2026-09-14 - matched-13.69 live resource proof succeeded

- After physical disconnection, the watch offered the staged update. The user
  selected **Install now** and later reported that the watch displayed
  `FLY LIVES 2ALIVE`; the USB cable was then reconnected.
- The installed package is tied to the prior guarded full readback: 5,120,675
  bytes, SHA-256
  `d89d52ca82586d7cea003c2f5b65b854790b572246164064fe3df079fa36ca2f`.
  The conversation establishes successful on-watch acceptance and rendering;
  it does not yet establish the displayed installed-version value or host-side
  USB enumeration after reconnection.
- This proves that the normal update and boot path accepts this controlled
  combination of main-descriptor version, installed-image-header version,
  About-page resource, and repaired additive-checksum changes. It proves that
  the updated application booted far enough to resolve and render the changed
  resource persistently across the update restart.
- The result falsifies an unconditional immutable-signature requirement over
  the particular changed bytes. It does not prove that every GCD is unsigned,
  that changed machine instructions are accepted or executed, that the helper
  or resident loader can be replaced, or that arbitrary firmware can boot.
- At this point in the sequence, official restoration, USB/update-service
  continuity, loader failure ordering, and recovery from a nonbooting
  application remained untested. The following read-only reconnect check
  resolved USB continuity and corrected the forward-restore assumption.
  Feasibility remains **YELLOW**.

## 2026-09-14 - read-only post-install reconnect verification

- Host-side read-only inspection after reconnection found the HWID-3076 Garmin
  volume healthy and accessible. `GarminDevice.xml` reports software version
  1370. The updater consumed the staged file: `GUPDATE.GCD` is absent, and no
  `force.tmp` file is present.
- Combined with the user's observation of `FLY LIVES 2ALIVE`, this confirms a
  normally booting modified application with working USB mass storage after the
  update. It does not by itself test all watch functions or recovery.
- The 1370 result falsifies the working assumption that changing the main GCD
  descriptor and installed-image header to 1369 controls the device's public
  current-version value. That value is sourced elsewhere or restored/derived
  during installation.
- Preserved official 13.70 must now be treated as a same-version package, not a
  proven forward restore. The recovered GarminOS selector ordinarily skips a
  same-version component when its override field is zero. Resident-loader
  policy remains unknown, so staging official 13.70 is not yet a demonstrated
  restoration path.

## 2026-09-14 - scientific fly overlay payload refined offline

- Expanded the 13.70 in-app overlay payload from the text-only plate into a
  140 by 22 pixel scientific specimen frame containing a 21 by 16 pixel dorsal
  fly silhouette and `FLY LIVES`. The known display lock wrapper, hook address
  `0x00009a20`, payload address `0x001f6000`, original dispatcher, and exact
  1 KiB audited cave allocation remain unchanged.
- The linked Thumb payload is 451 bytes with SHA-256
  `62ea46c67c565f571789d1437de318de785d90a2fef0a79d702b6d2ba6b3dee1`.
  Unicorn execution changed all 3,080 bytes in the declared rectangle and no
  framebuffer byte outside it; it confirmed 146 fly pixels, 428 text pixels,
  the complete frame, the exact dirty call, original dispatch, preserved
  `r4..r11`, and restored stack pointer.
- Built the quarantined analysis-only package
  `Forerunner245_1370_flyos-scientific-fly-overlay.gcd.analysis-only.DO_NOT_INSTALL`,
  SHA-256
  `7af3031b222e472f9fab54e148112c56d41a93b30340d5a55899be57c818c9df`.
  Its 452 changed main-stream bytes are confined to the four-byte hook and
  exact cave allocation. The helper and descriptors remain byte-identical,
  the main additive sum is zero, all outer checkpoints pass, and independent
  generic comparison reports PASS.
- No watch volume was accessed and no file was staged or installed during this
  overlay refinement. The payload remains separate from the unresolved
  same-version admission and restoration strategy.

## 2026-09-14 - full-screen custom Thumb overlay succeeded live

- Following the successful bounded 13.71 overlay experiment, the exact
  synthetic-13.72 full-screen package was installed through the normal Garmin
  update flow. It is 5,120,675 bytes and has SHA-256
  `6394fd73cc3e7a5660a6fe9cde3cc0b6617c21f8a24f2b6319b328882d662713`.
- After restart, the user reported that the whole screen showed `FLY LIVES`
  and the fly. That output is unique to the package's changed branch at
  `0x00009a20` and new 974-byte Thumb payload at `0x001f6000`. This is direct
  evidence that the normal updater accepted the tested changed instructions,
  that the custom Thumb body executed persistently after boot, and that it
  controlled the complete 57,600-byte GarminOS framebuffer.
- This is a GarminOS-resident overlay rather than standalone FlyOS. It relies
  on GarminOS boot, display initialization, framebuffer/lock state,
  dirty-rectangle handling, and original display dispatch. It does not prove
  replacement of the resident loader or independent MCU/display startup.
- Read-only post-install inspection found the reconnected USB device OK, the
  volume healthy, model Forerunner 245 part `006-B3076-00`,
  `GarminDevice.xml` software version 1370, and neither `GUPDATE.GCD` nor
  `force.tmp`. Subsequent brief presses resolved every marker: top-left `L` =
  LIGHT, middle-left `4` = UP, bottom-left `3` = DOWN, top-right `1` =
  START/STOP, and bottom-right `2` = BACK. All five observations agree with
  the active-low GPIO model.
- The prepared 13.73 official-code recovery wrapper is 5,120,675 bytes with
  SHA-256
  `869d62ab829ac7b75a079effd4d7d0b1e71a5e8a0d1c7d2c94fa686d907aa4e6`.
  It remains uninstalled. It restores official 13.70 executable code and
  resources behind synthetic forward-version metadata, but it is usable only
  if GarminOS boots and exposes its normal USB updater. It cannot recover a
  nonenumerating/nonbooting watch, and no FR245-specific nonboot recovery path
  is demonstrated.
- Feasibility remains **YELLOW**: custom Thumb execution and full-frame display
  control are now demonstrated, while standalone FlyOS boot and reliable
  nonboot recovery remain unresolved.

## 2026-09-14 - neural overlay package pair constructed offline

- Validated the byte-pinned offline decision SHA-256
  `1179e1caded279c30ea21ff6403c11072b2bb937b01dc846590a7217f2e06dfa`,
  all decision-referenced input/review/segment hashes, and every file/source
  hash inside the pinned target manifest before creating an output.
- Built
  `Forerunner245_1373-flyos-neural-overlay.gcd.analysis-only.DO_NOT_INSTALL`,
  5,120,675 bytes, SHA-256
  `4ec78eabd23a880ad5d4e9ff52e688e62397480a32070316b2748b70b771c9d7`.
  The decoded main is 5,079,040 bytes with SHA-256
  `3b944f381d33be65ade1d6f27f99ad3d911c32f1a8d4e092455ae581e9584a35`.
  Its 2,773 changed decoded bytes are confined to the coherent header version,
  4-byte hook, reviewed primary/secondary allocation envelopes, and the final
  additive repair. The primary repair at runtime `0x001f63ff` is `0xaf`.
- Built
  `Forerunner245_1374-official-payload-restore.gcd.analysis-only.DO_NOT_INSTALL`,
  5,120,675 bytes, SHA-256
  `4d47edfcaeb3585bd026ac89c8cc9fbeaa9168032d9569aa3885bfdb4880ffa4`.
  Its decoded main SHA-256 is
  `6a3c21760fb0dcaa1b682e05d91732971b3c15d2ca75e6964d48a8d1bef83082`.
  It restores official hook/code/resources, including both full allocations;
  only decoded offsets `0x22c` and `0x4d7fff` differ. Raw differences are
  `0x00a160`, `0x00a392`, `0x4e2299`, and `0x4e229e`. It is not byte-identical
  to official 13.70.
- Exact reconstruction, opt-in `gcd_candidate_verify.py` neural profiles, and
  `full_image_validator.py` passed for both files. Both retain the exact
  official record layout and stream lengths, HWID 3076, byte-identical helper
  stream/descriptor, decoded-main sum zero, and five valid outer checkpoints.
- The helper erase ranges are internal `0x00003000..0x001fffff` and external
  QSPI `0x68617000..0x68916fff`. The decoded main programs external QSPI only
  through `0x688f1fff`, leaving `0x688f2000..0x68916fff` erased.
- `packaging_allowed:false` and `live_staging_allowed:false` remain unchanged.
  The existing staging guard has no neural profile. No watch or `D:` path was
  accessed during construction. No nonboot recovery is known; feasibility
  remains **YELLOW**.
- Controller-owned post-build read-only verification recorded a Healthy/OK
  GARMIN FAT volume, 15,509,504 bytes free, and absence of both `GUPDATE.GCD`
  and `force.tmp`. The 268-file current manifest was compared by relative
  path, size, and SHA-256 against the 266-file baseline with timestamps
  excluded: 264 were identical, with three expected device-generated
  additions, one rotated event log, and one changed debug error log. The
  private manifest stays local; the check mutated nothing.

## 2026-09-14 - Task 5 provenance and transaction review fixes

- Amended the construction decision to directly pin the current 37,126-byte
  emulator source SHA-256
  `c97c00599537f741fc7bd1bd7bad7070beac6d37f6c574c22f79842e1cf2094c`
  and the 9,025-byte focused test SHA-256
  `336d9fba531c386e80f79c1db3a8543c496b9c236932a916afe1319c54df709b`.
  Both are checked as decision inputs before construction or verification.
- Reran the complete emulator evidence: `PASS_OFFLINE_ONLY`, 15 cases, stack
  bound 328 bytes, and `packaging_allowed:false`. The emulation report remained
  byte-identical with SHA-256
  `0254a39b72b50b76559ab28d2287fb7a22ff1b50ecea5eee38c1b00daf4a0bc6`.
- Added a report-only `refresh` mode. It opens the existing candidate and
  restore read-only, requires byte-exact reconstruction under the amended
  decision, and replaces only the build and strict reports with rollback.
  Two consecutive runs were deterministic. Pre/post package sizes, hashes,
  creation times, and last-write times matched exactly; neither package was
  overwritten or recreated.
- Archived the superseded six core reports and checksum ledger beneath
  `artifacts/firmware/analysis/archive/task-5-pre-emulator-source-pin/` before
  refresh.
- Fixed transactional creation so each path enters the cleanup set immediately
  after exclusive open. Injected write, flush, and fsync failures leave no
  partial file; a pre-existing file is preserved; cleanup failure becomes a
  fatal error naming the unconfirmed path.
- `packaging_allowed:false` and `live_staging_allowed:false` remain unchanged.
  No watch, removable volume, or `D:` path was accessed for these fixes.
- Independent Task 5 re-review reports **SPEC PASS / QUALITY PASS**, with both
  prior findings resolved. The final review SHA-256 is
  `0d509811b60063bffd90ae94019f9202bbf4da4a5341298c2a8d5e0270295617`.
- The refreshed release-risk audit reports **PASS** for offline artifact
  release and proposal accuracy, while retaining **HOLD** for a live write.
  It independently matched 10/10 current hashes, 15/15 checksum-ledger
  entries, every build/strict check, and all five refresh checks. Its SHA-256
  is `12f64a7ad2cc1564508005ee31b622bba472ae8e9972ce191b2bd03d204c5d5e`.

## 2026-09-14 - exact neural candidate staged after approval

- After receiving explicit approval for the fully specified action, enabled
  only the exact `NeuralOverlay1373` staging profile. The restore wrapper was
  not enabled or staged.
- A dry run revalidated the connected Forerunner 245, reported version 1370,
  healthy GARMIN FAT volume, free space, pinned source, and absence of
  `GUPDATE.GCD` and `force.tmp`.
- Created `D:\Garmin\GUPDATE.GCD` with create-new semantics, flushed it to the
  device, closed it, and performed a complete watch-side SHA-256 readback.
  Size was 5,120,675 bytes and SHA-256 was
  `4ec78eabd23a880ad5d4e9ff52e688e62397480a32070316b2748b70b771c9d7`.
- The sanitized staging receipt SHA-256 is
  `43f7c82ecb19f88c41834c673c9637e760509410a18d565a0bf888834a3466a5`.
  The detailed staging output containing device identifiers remains local and
  private.
- Requested safe eject through the Windows shell and confirmed that `D:` was
  no longer mounted. The eject receipt SHA-256 is
  `58ec975ececdc4b91dd889e3d424c50a63404738a8e01fd7181c53bf0c0ad33e`.
- Installation has not yet been observed. No reset, button selection, restore,
  retry, or other device action was performed by the host.

## 2026-09-14 - neural overlay boot observed live

- The user reported that the update began after pressing the top-right START
  button.
- After the updater completed and the watch rebooted, the user reported seeing
  a brain with neurons on the display. That full-screen output is unique to
  the synthetic-13.73 neural payload and constitutes direct evidence that the
  staged package was accepted, installed, booted, and reached the custom
  renderer.
- This demonstrates GarminOS-resident execution of the 32-neuron FlyOS model
  and ASCII brain display. It does not demonstrate standalone FlyOS boot or a
  nonboot recovery path.
- Button-driven activation changes and post-install USB/filesystem health have
  not yet been observed.
- The user then pressed all five buttons and reported that the neuron glyphs
  changed. This confirms that GPIO-derived inputs affect the live 32-neuron
  state and its four-level ASCII activation rendering.
- After reconnection, a read-only check found the expected Forerunner 245,
  part `006-B3076-00`, USB VID/PID `091e:2c04`, public software version 1370,
  PnP status OK, and a Healthy/OK GARMIN FAT volume. `GUPDATE.GCD` and
  `force.tmp` were absent, confirming that the updater consumed the staged
  file. The sanitized device-check report SHA-256 is
  `a544536d40bf966aacd43ea806546b282a3c2a4a98615ac5fe5a1fc1d822ae88`.
- A fresh private 281-file manifest was compared against the 268-file
  pre-install manifest with timestamps excluded. 263 files were identical;
  the remaining changes were routine operational files. The manifest and
  comparison SHA-256 values are
  `2bc6a930bcf0b6be31f87530dc8689fe298eb36fde786308b7dc10026ef38d45`
  and `ddd7577d24eddd56a5b0cbf04a4b3ae59f3f004c5130b2a0258266730001ed45`.
  Their private relative paths and hashes remain local.
- Result: live GarminOS-resident FlyOS displays the ASCII brain, runs the
  deterministic 32-neuron fixed-point network, and reacts to all five buttons.
  Standalone boot and nonboot recovery remain unresolved, so feasibility stays
  **YELLOW**.
- Removed the one-use neural candidate from the staging guard after successful
  installation. Both neural candidate and restore modes are rejected again;
  another write would require a new exact approval.

## 2026-09-15 - Neural Specimen N64 packages built offline

- Constructed a synthetic 13.74 N64 candidate and synthetic 13.75
  official-code restore wrapper from the byte-pinned official 13.70 GCD.
- Both outputs are confined to `artifacts/firmware/quarantine/`, end in
  `.analysis-only.DO_NOT_INSTALL`, and were created with exclusive create-new
  semantics. No watch or removable volume was accessed.
- Candidate: 5,120,675 bytes, SHA-256
  `3a4a4af6355c132571c1158667cc43c96bf5da7a67737ab028267930e71134cd`.
  Restore: 5,120,675 bytes, SHA-256
  `ccd2a29c51a41a436111239c7181e1cb0cea1f2fac1c48d600fff6dec103e5da`.
- Exact reconstruction, helper identity, record layout, decoded additive sum,
  five outer checkpoints, full-image validation, exact segment placement, and
  binding to the reviewed 64-neuron Unicorn evidence all pass offline.
- The live staging tool now explicitly denies both N64 modes, filenames,
  relative paths, basenames, and hashes before package or device access. Tests
  also inject alias profiles by path, basename, and hash and confirm rejection.
- Feasibility remains **YELLOW**. The official-code restore requires a booting
  GarminOS/USB update path; there is no known nonboot recovery.

## 2026-09-15 - N64 package custody and transaction review fixes

- An independent review found that the first package tool validated pinned
  paths and then reopened them for construction. The tool now loads each unique
  path once into an immutable byte snapshot and reuses that exact snapshot for
  parsing, construction, exact verification, attestation, and hashing.
- Duplicate decision/manifest references share a canonical snapshot and must
  agree on size and SHA-256. A regression mutates every second read of the
  official GCD and the three target binaries; construction now performs exactly
  one read of each and reproduces the fixed candidate/restore hashes.
- Output validation now rejects lexical `..` traversal, symlink/reparse aliases,
  hardlinks, alternate parents, and pre-existing finals. Transaction tests cover
  pure short writes, write/flush/fsync faults, cleanup-unlink failure, post-write
  corruption, final report corruption, rollback, and safe retry.
- The focused package suite passed 18/18 in 133.344 seconds. The exact N64
  Unicorn target suite then passed 20/20 in 216.344 seconds. The build/strict
  reports were refreshed transactionally; both package hashes and filesystem
  metadata were unchanged, and the eight-entry package ledger rehashed exactly.
- No watch, removable volume, `D:` path, updater directory, or `GUPDATE.GCD` was
  accessed. Live staging remains disabled and feasibility remains **YELLOW**.
## 2026-09-15 - N64 final offline verification and read-only USB poll

- Fresh complete firmware-analysis discovery passed 159 tests in 662.637 seconds with one explicit host-capability skip for privileged ordinary-symlink creation; the exercised NTFS-junction alias test passed.
- Fresh shared C/CTest passed 7/7 tests.
- Fresh in-memory exact package verification passed all eight reconstruction/full-image/policy checks. Candidate SHA-256 remained `3a4a4af6355c132571c1158667cc43c96bf5da7a67737ab028267930e71134cd`; restore SHA-256 remained `ccd2a29c51a41a436111239c7181e1cb0cea1f2fac1c48d600fff6dec103e5da`.
- A direct staging-guard invocation for blocked mode `NeuralSpecimenN64Overlay1374` exited before device work with the expected explicit N64 path/hash rejection.
- A final read-only Windows poll observed one present `VID_091E&PID_2C04` device. The Garmin filesystem was not consistently mounted/readable during the poll (`D:\Garmin` and `GarminDevice.xml` were unavailable), so no staging preflight was attempted. No `GUPDATE.GCD` was created or copied.

## 2026-09-15 - approved N64 live staging and safe eject

- Received the user's exact approval for the disclosed 13.74 N64 candidate write to `D:\Garmin\GUPDATE.GCD` after presenting the complete application/QSPI rewrite ranges, nonzero brick risk, recovery limits, and pinned restore procedure.
- Revalidated one connected HWID-3076 Forerunner 245, reported software 13.70, healthy GARMIN FAT volume, no existing `GUPDATE.GCD` or temporary file, and the pinned 5,120,675-byte candidate SHA-256 `3a4a4af6355c132571c1158667cc43c96bf5da7a67737ab028267930e71134cd`.
- Copied to a same-directory temporary file with create-new semantics, forced a flush, verified its complete SHA-256, atomically renamed it to `GUPDATE.GCD`, and independently re-read the final file. The final size and SHA-256 matched exactly; the temporary file was absent.
- Re-enabled the staging denylist before eject. Both the N64 candidate and restore modes are again blocked from repeat staging; the locked script SHA-256 is `d7aecb958c37504a4536be73139bae32c2ba297773399e61dbe2ee7da5e4aed5`.
- Requested Windows safe eject and confirmed that `D:` was no longer mounted. Installation has not yet been observed; no host reset or button action was performed.
- Sanitized staging receipt: `artifacts/analysis/neural-specimen-n64-live-staging-1374.json`; SHA-256 `357a1178fc8ca1cfbfba0766f4cc9446b5b3fa77120a69e59734719dc45a7021`. Hardware identifiers remain local and are omitted from the receipt.

## 2026-09-15 - N64 controls and round-screen redesign completed offline

- Traced the pinned key-event builder at `0x0000fa48` and confirmed that the
  downstream publisher invokes 13 independent subscribers without using their
  return values. View-level consumption therefore cannot prevent Garmin
  navigation. The controls target intercepts before publication with a six-byte
  Thumb branch and replays the exact original prologue for native events.
- START, DOWN, and UP are owned only for a stable, dual-scanned home view. LIGHT
  and BACK always pass; confirmed USB mass-storage states, non-home views, and a
  BACK-held escape chord pass all keys. Ownership is latched through release.
  Every new press first clears a stale ownership value, fixing an independently
  found interrupted-sequence hazard.
- Owned presses request the watch face's stock `0x50` redraw event through the
  existing UI queue with timeout zero. The key worker never draws directly.
  Exact 16-bit status values use only the audited unused final halfwords of the
  three controlled-key records.
- Reworked the face as a tapered 8 by 8 neural field in an angular fly-head
  contour with antennas. The footer now names effects (`START>BURST`,
  `DOWN>CALM`, `UP>PULSE`, `LIGHT>LUX`) and the idle prompt is `PRESS>KEYS`.
  A visual audit across idle, held, and acknowledgement states found bounding
  box `x=52..188`, `y=22..208` and maximum radius 98.509 inside the required
  100-pixel circle. Each controlled input lights its mapped neuron amber and
  produces distinct downstream activity.
- Packed the unchanged 90-edge Brain64 graph into 16-bit edge words for the
  target only. Exhaustive differential verification across 4,704 fixtures
  produced 658,560 byte-identical output bytes, SHA-256
  `1d08e04d5597a7ddcabf94c82c9e2bb200aba223713ab7b22a82425336ef2105`.
- Final controls build: display hook 4 bytes, key hook 6 bytes, primary 996 of
  1,023 usable bytes, secondary 2,044 of 2,048 bytes, and exact 384-byte maximum
  target-owned stack chain. Manifest SHA-256 is
  `28243fab77447f1ce12ad05680878868afe4482dd7465ee3a12c17ae2e6322f8`.
- A fresh independent controls run passed 19/19 tests in 176.377 seconds. It
  covers hook bytes, original publisher replay, ownership and escape sequences,
  stale-latch recovery, nonblocking queue failures, exact reads and confined
  writes, stack/register ABI, every cross-segment branch, the host Brain64
  oracle, all 64 direct cells, six reviewed colors, and strict round geometry.
- Created an immutable controls construction decision, SHA-256
  `15bc970f3277ffb61f2562ac52fc5f779f9fe7e47c116f7f79bf4fba025d1f54`,
  which chains to the prior full N64 decision and allows only offline local
  quarantine construction. Live staging remains false.
- Constructed synthetic 13.76 candidate and synthetic 13.77 official-code
  restore packages offline with create-new semantics. Both are 5,120,675 bytes.
  Candidate SHA-256:
  `9dc61b99cebacc50f121b9145ddfab21445344fac6f70a4ab68dde205fcf84de`.
  Restore SHA-256:
  `724c8fe8bdafd6857116cbb28951e9f2934badab09616a716e450e6676fb3c4d`.
  Exact reconstruction, record layout, official helper identity, decoded
  additive sum, five checkpoints, complete official-code restore, and confirmed
  application-side full-image checks pass. A fresh package suite passed 10/10
  tests in 54.379 seconds.
- The live staging tool explicitly blocks both controls modes, names, paths,
  basenames, and hashes before package or device access. No watch, removable
  volume, updater directory, or `GUPDATE.GCD` was accessed during this work.
  Feasibility remains **YELLOW** because recovery still requires a booting
  GarminOS/USB updater and no nonboot recovery path is known.
