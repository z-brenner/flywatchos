# Forerunner 245 offline update-validation trace

## Scope and confidence

This analysis used only preserved, extracted non-Music `fw_all` images. No USB
command was sent and no file was written to the watch. Addresses below use the
documented Cortex-M application base `0x3000` unless stated otherwise.

| Image | Size | SHA-256 |
|---|---:|---|
| 3.10 `fw_all` | 4,201,216 | `3225c50585503d331a9c0ee8faf342241207dd98825f4f0f9cf3fa23831c54ba` |
| 13.70 `fw_all` | 5,079,040 | `b45be1baf98999af10f073bef52b284beb2aea6abbb7cde2ffa59fb6bcedeab6` |

Both start with plausible Cortex-M vectors and reset to `0x31f1`. Each image
uses two executable mappings. File offsets `[0, 0x1fd000)` map to K28F internal
flash at `0x00003000`; file offsets from `0x1fd000` onward map to a second region
beginning at `0x04600000`. The second mapping is confirmed by vector-like words
at the boundary and by internal-flash `ldr.w pc, [pc]` veneers whose literals
point to coherent Thumb functions in the `0x046...` range.

Confidence terms:

- **Confirmed:** exact bytes, decoded instruction, or reproducible reference.
- **Strongly inferred:** behavior follows directly from a short instruction
  sequence, but external functions remain unnamed.
- **Unresolved:** present in the image without a proved call-graph connection.

## The 3.10 system-update path

The 3.10 image provides the clearest executable path.

| Evidence | Address | Finding |
|---|---:|---|
| Full pathname | `0x000a06c0` | `0:/Garmin/GUPDATE.GCD` |
| Pointer slot | `0x000a0490` | exact little-endian pointer to the pathname |
| Function | `0x000a0474` | loads the path at `0x000a0478` |
| Caller | `0x000ce154` | calls the function at `0x000ce15c` |
| Parser opener | `0x000a0184` | loads the same path through slot `0x000a018c`, then tail-branches to `0x0009fdac` |

At `0x000a0474`, the function passes the pathname and `0x20` to
`0x0010aecc`. A negative return produces `false`; a nonnegative return is
passed to `0x0010ab74` and produces `true`. This is **strongly inferred** to be
an existence/open-and-close test.

The caller at `0x000ce154` returns immediately when that test is false. When it
is true, it calls `0x000a0184`, then repeatedly calls helpers around
`0x0009fd10` with small record IDs including `0x0e` and `0x05`. Later paths use
additional IDs and lengths. This is **confirmed** as application-side
`GUPDATE.GCD` orchestration and **strongly inferred** as a structured
update-file parser. The current trace does not prove that these IDs correspond
directly to the outer flat GCD records reproduced by `gcd_inspect.py`.

A different `GUPDATE.GCD` at `0x000d719c` appears among strings used to produce
`GarminDevice.xml`, next to `gup%04d.gcd`, `SoftwareVersion`, and `UpdateFile`.
Its Thumb literal reference is `0x000d611a` via pointer slot `0x000d62b4`.
That path describes update files to host software; it is not evidence of image
authentication.

## The 13.70 system-update anchor

Ghidra 12.1.3 identifies `FUN_00009b60`. At `0x00009b82`, the function loads a
literal pointer from `0x00009b98` to:

```text
..\..\..\HWM\k28\hwm_system_update.c
```

It then sets `r1` to `0xef`, clears `r2`, and calls `0x000033e8`. The
source-file/line call sequence is **confirmed** and is strongly characteristic
of an assertion or diagnostic path in the K28 system-update module. It anchors
that module in executable code but does not expose a signature or acceptance
decision.

Under the confirmed second mapping, the 13.70 pathname strings are at
`0x04762b94` (`0:/Garmin/GUPDATE.GCD`) and `0x0477225c` (`GUPDATE.GCD`). Function
`FUN_04762bac`, immediately after the full pathname, constructs parser state,
calls an internal-flash veneer at `0x000356b0`, and calls `FUN_04762784`.
`FUN_04762784` is the 13.70 counterpart of the 3.10 descriptor parser: it maps
record `0x02bd` to internal type `0x0e`, `0x03c1` to type `0x05`, and adds
record/type handling for `0x0008`/`0x0c`. Ghidra did not recover a direct pointer
xref from the pathname bytes, so the adjacency is an anchor rather than proof
that `FUN_04762bac` directly opens that literal path.

## The visible signature check is for Connect IQ

In 3.10, `Signature check failed on file:` is at `0x00131f98`. An exact pointer
at `0x00131590` is loaded by executable code at `0x00131494`, inside the
function beginning `0x0013142c`.

The surrounding string cluster contains:

- `0:/Garmin/Apps/TEMP/` at `0x00131f80`;
- `0:/Garmin/Apps/CIQSTORE.PUB` at `0x00131fbc`;
- `..\..\..\TVM\vm\tvm_cache.c: 142` at `0x001321ec`.

The equivalent 13.70 cluster contains `0:/Garmin/Apps/TEMP/` at `0x003ba340`,
`CIQTEST.PUB` at `0x003ba807`, and the signature error at `0x003bad8c`.
This cross-version context **strongly ties the message to Connect IQ app/cache
verification**, not to system `GUPDATE.GCD` acceptance. It cannot be cited as
evidence that the main system image is signed.

## Cryptographic material scan

Exact standard initial-state word sequences occur in both images:

| Primitive marker | 3.10 addresses | 13.70 addresses |
|---|---|---|
| SHA-256 | `0x00003820`, `0x000a3f58` | `0x00205980`, `0x0036b018`, `0x0036b244` |
| SHA-1 | `0x000a19d8`, `0x001c0b8c` | `0x00369d78`, `0x004d72ec` |
| MD5 four-word prefix | `0x000a19d8`, `0x00176cec`, `0x001c0b8c` | `0x0003a558`, `0x00369d78`, `0x004d72ec` |

The MD5 prefix is also the first four words of the reported SHA-1 state, so
overlapping hits are not independent proof of MD5. The initial constant scan
established only that hash implementations were bundled. The later focused
trace below connects the 3.10 SHA-1 implementation specifically to the
`GDELTA01` delta engine; it does not connect SHA-1 to the ordinary full-image
fallback.

No PEM certificate or PEM public-key marker occurs in either image. That does
not rule out raw modulus/exponent data, elliptic-curve points, symmetric keys,
or verification performed solely by the omitted resident loader.

The outer GCD record stream has reproducible unkeyed additive checkpoints and
no identified signature record. Those checkpoints detect accidental damage;
they do not authenticate an image.

## Bounded Ghidra decompilation

Both non-Music application streams were first imported over `0x00003000`
through `0x001fffff`, the documented K28F internal-flash window. A second pass
maps the remaining bytes at `0x04600000`. `SeedThumbFunctions.java` seeds the
117 vector targets and selected cross-region targets before analysis. The 3.10
second region ends at `0x04804aff`; the 13.70 second region ends at
`0x048dafff`.

The 3.10 decompiler trace confirms the following application-side update path:

- `FUN_000a0474` opens `0:/Garmin/GUPDATE.GCD` through `FUN_0010aecc` and
  closes it through `FUN_0010ab74`, functioning as an existence/open test.
- Caller `FUN_000ce154` invokes that test and then `FUN_000a0184` to parse the
  file. It requests parsed internal types `0x0e` and `0x05` through
  `FUN_0009fd10` and performs additional record handling and cleanup.
- `FUN_000a0184` enters `FUN_0009fdac`, which allocates parser state, opens the
  file, and parses structured descriptors. It recognizes record IDs `0x02bd`
  and `0x03c1`, mapping them to internal types `0x0e` and `0x05`, along with
  descriptor fields `0x000b`, `0x1008`-`0x100a`, `0x100c`, `0x100d`,
  `0x1014`, `0x1015`, and `0x2015`.
- `FUN_0009fd10` searches the parsed descriptors by internal type and accepts
  identifier field values `0` or `0x0c04` on this device-family path.

This establishes an application-side container parser and family/identifier
check. No call to a proved cryptographic verifier appears in this decompiled
orchestration slice. It still cannot establish what the resident loader checks
before installing or booting an image.

The complete decompiler export is stored locally at
`artifacts/firmware/analysis/decompile-update-310.txt` with SHA-256
`dfc1bf48cdd5adaca352df45d8ff8e82b23b8f695467dd609e05918d3ec6ad09`.

The dual-map exports are
`artifacts/firmware/analysis/decompile-update-310-dual.txt` and
`decompile-update-1370-dual.txt`. They resolve cross-region veneers and confirm
the 13.70 parser relationship above. Automatic function discovery in the
second region remains conservative because code and embedded data are mixed.

### Parser preconditions and image markers

A second bounded decompiler pass resolves more of the 3.10 parser without
crossing into the missing loader:

- `FUN_0009ee8c` opens the requested file and stores its handle.
- `FUN_0009ee54` reads offset zero and compares eight bytes with the literal
  `GARMINd\0` at `0x0009ef88`.
- `FUN_0009ee10` reads the last four file bytes and requires `ff ff 00 00`.
- `FUN_0009edb8` is the parser's seek/read wrapper.
- `FUN_000a0278` reads typed payload fragments across successive GCD records.
- `FUN_000cdfb8` scans a typed payload for the paired 32-bit image markers
  `0x389db9f0` and `0xc762460f`, then returns the matching offset.
- `FUN_0000b660` searches another region for the same marker pair and an
  `0xa55a` trailer while returning header/version data. In caller
  `FUN_000ce154`, it is used to compare staged metadata with existing state.
- `FUN_000cc230` reads and writes a one-byte value under internal setting ID
  `0x0285`; its exact semantic name is not established.

These are structural and compatibility checks. None is a keyed authenticity
check, and none proves that the loader omits one. The second export is stored
at `artifacts/firmware/analysis/decompile-update-310-stage2.txt`, SHA-256
`a05c3ef17a41e7a1b158b1df9fd8f704e64a42036e6f46e5474b58b760254b6e`.

### Application installer and integrity checks

Tracing the sole recognized caller of `FUN_000ce154` exposes the next update
state-machine layer:

- `FUN_000cd22c` invokes registered update-information providers, including
  `FUN_000ce154`, and publishes the resulting 0x44-byte update state.
- `FUN_000ce3c8` parses `GUPDATE.GCD`, installs internal type `0x05` and then
  type `0x0e` according to state flags, records success/failure, and schedules
  a system event after successful completion.
- Its worker `FUN_000ce038` first reaches `FUN_0009eeac` through
  `FUN_000a069c`. `FUN_0009eeac` reads the GCD up to its four-byte terminator,
  accumulates bytes with `FUN_0017533c`, and accepts only a zero low byte. This
  is the same unkeyed additive integrity property reproduced by the local GCD
  parser.
- `FUN_000a0494` walks records of the selected internal type and writes their
  bodies in chunks through a registered destination backend
  (`FUN_000d29e8`, `FUN_000d2b50`, and `FUN_000d2a10`). The backend trace below
  identifies the medium as external QuadSPI flash.
- `FUN_000cc464` is the callback-driven delta engine. Its header path reads
  `0x48` bytes and requires the eight-byte `GDELTA01` magic at `0x000cc92c`
  before reaching the SHA-1 initialization, finalization, and 20-byte
  comparison. The observed SHA-1 check therefore applies to delta handling;
  it is not a demonstrated check on the ordinary full-image payload.
- When `FUN_000ce038` takes the non-delta full-image fallback, it determines
  the selected type's payload length, reads it in chunks of at most `0x100`
  bytes, accumulates the bytes with `FUN_0017533c`, requires the low byte of
  the sum to be zero, and only then calls the normal writer `FUN_000a0494`.
  This is an unkeyed integrity check. Unnamed callbacks and the omitted
  resident loader could still impose separate authentication.

This proves that GarminOS contains a concrete package installation path. The
ordinary full-image path is directly observed to use additive integrity checks;
the traced SHA-1 comparison belongs to the separate `GDELTA01` path. Neither
result identifies the resident loader's subsequent boot policy or a safe
failure rollback.

`tools/garmin-firmware/full_image_validator.py` reproduces only the confirmed
ordinary full-image checks: all outer GCD prefix checkpoints, absence of the
`GDELTA01` prefix, and a zero low byte for the decoded type-`0x02bd` payload
sum. It reports that both the official 13.70 package and the checksum-repaired
offline payload experiment pass those limited checks. This is evidence about
the traced GarminOS branch only; neither package was submitted to a device,
and the result says nothing about resident-loader authentication or recovery.
The official and laboratory JSON reports have SHA-256
`ca3fe52d2063f5cea76102d316e5b512edc06c0414c2ab56cf8c2257b56c678a`
and `0b995fb48a65b0b4ed8a9899b1afb4ccc5eb6de8d9fd87152ae0309edb2cc5d8`.

The registered backend's static type table supplies stable logical
destinations in both 3.10 and 13.70:

| Internal type | Outer GCD record | Garmin logical address | Capacity |
|---:|---:|---:|---:|
| `0x05` | `0x03c1` | `0x68103000` | `0x15000` (86,016 bytes) |
| `0x0e` | `0x02bd` main application | `0x68118000` | `0x4ff000` (5,238,784 bytes) |

In 3.10 the table is at `0x000d3178`; the two descriptors are at
`0x000d3120` and `0x000d31d8`. In 13.70 the corresponding table is at
`0x00022d28`, with descriptors at `0x00022cd8` and `0x00022d80`. The local
`update_region_map.py` scanner reproduces this result. The table alone did not
identify a physical medium; the independent backend trace below shows that its
addresses are passed to the K28 QuadSPI AHB window.

Generated region reports hash to
`2a057559845a5ca05b43044f3eb21a10623454486fa9d28db1800afb247f4424`
(3.10) and
`41f4b481f1507c88d91c92afc6fc26dffc981323f78165ddfb93b82dd9214caa`
(13.70).

The supporting exports and SHA-256 values are:

| Export | SHA-256 |
|---|---|
| `decompile-update-310-handoff.txt` | `c48388f08e934e1bd9c3a68bb38ca6dde0d58d85a82bab43cb66d81d08fdb10a` |
| `decompile-update-310-callers.txt` | `723f08b5e34f31811627ca17c6e661b5dd78b4287d6d3dcf9d6810e39f741c02` |
| `decompile-update-310-installer.txt` | `c827daaac4c9121b769c2e229fafbee52ef52fce1fbe5609df84d31e39a7a118` |
| `decompile-update-310-validator.txt` | `d2e94b69ca0fa086c0086a3ccdbe9527709c103c7f282cd75141a22799bc9030` |
| `decompile-update-310-restart.txt` | `7a659b8e9835f96795f85e6faa044534d02d0a1338bcdc78748bcde2cf861262` |

The dual-map parser exports hash to
`781d12600ffeac43b325252af23ec92105389da27aae83798e148c9595c08e03`
(3.10) and
`172b42a12da1d6d572bd3e84e393392bfd2734b0395b5ee84b79fba3862284b0`
(13.70).

### External QuadSPI update backend

This layer is **confirmed** in both acquired non-Music images:

- The registered backend object points to the region table above and a
  ten-entry method table. In 3.10 the initializer is `FUN_000d30f0`, the
  method table is at `0x000d3150`, and the source anchor is
  `HWM\region\hwm_rgn_ufs.c: 40` at `0x000d365c`. The 13.70 counterparts are
  `FUN_00022cb4`, `0x00022d00`, and `0x00023208`.
- The backend's low-level routines access peripheral base `0x400da000` and
  memory addresses formed with `address | 0x68000000`. NXP's pinned K28F SDK
  header defines `0x400da000` as `QuadSPI0_BASE`; its feature header defines
  `0x68000000` as `FSL_FEATURE_QSPI_AMBA_BASE`. This identifies the physical
  medium as external QuadSPI flash. The source abbreviation `ufs` is an
  internal Garmin name here and is not evidence for JEDEC Universal Flash
  Storage.
- Reads use ordinary AHB memory copies from the `0x68xxxxxx` window. Writes
  use the QuadSPI register block, split work at 256-byte page boundaries, and
  launch LUT sequence `0x14`. The code has separate 4 KiB and 64 KiB erase
  paths, using LUT sequences `0x1c` and `0x20` respectively. The all-`0xff`
  blank check before each erase and one-way bit programming are strongly
  characteristic of serial NOR flash. The exact flash part number remains
  unknown.

The type `0x0e` write order is also **confirmed**:

1. `FUN_000a0494` (3.10) and `FUN_047623b4` (13.70) call the generic erase
   method before reading and writing the first payload fragment.
2. A whole-region erase request supplies offset and length zero. The backend
   expands that to `0x68118000` through `0x68616fff`, skips sectors already all
   `0xff`, uses 4 KiB erases until 64 KiB alignment, 64 KiB erases for the
   aligned middle, and 4 KiB erases for the tail.
3. The record writer reads at most `0x100` bytes per iteration and writes
   monotonically increasing destination offsets. The low-level programmer
   independently prevents a transfer from crossing a 256-byte page boundary.
4. The generic finish method is called after the last record. Its QuadSPI
   implementation reports success only when the lower-level ready check is
   true.

The main region reserves a status location at offset `0x4fd000`, physical
address `0x68615000`, two 4 KiB sectors before the region's exclusive end at
`0x68617000`. Both versions contain two exact references to this offset. The
3.10 helper first treats an erased byte as logical zero by XORing it with
`0xff`; on an installation failure, `FUN_000cbf8c` requests logical bit zero
to become one, which clears the corresponding physical flash bit. On success,
the orchestrator checks the logical failure bit, closes the region, and sends
a restart request. The 13.70 function anchored to
`HWM\k28\hwm_system_update.c: 239` has the same failure-marker/close behavior.

This is the narrowest supported handoff model:

```text
GUPDATE.GCD type 0x0e
    -> erase external QuadSPI staging region 0x68118000..0x68616fff
    -> stream composite fw_all bytes into that region
    -> leave or set the one-way failure marker at 0x68615000
    -> request a GarminOS restart
    -> resident loader behavior is unobserved
```

The `0x0505` stream supplies a further, separate update stage. It is a native
Cortex-M image with vectors at `0x1ffc0000` and an entry at `0x1ffc01f1`.
NXP's MK28FA15 memory map defines `0x1ffc0000` as `SRAM_L_BASE`, so this is a
RAM-resident helper, not code placed at the top of internal flash.
The 3.10 main loop reads type `0x0e` through its region dispatcher, then writes
the same chunks through destination type `0xaf`; its maximum transfer chunk is
`0x1e000` bytes. Its static table contains the same type-`0x05` and type-`0x0e`
QuadSPI regions. The helper code includes both QuadSPI literals and K28 internal
flash-controller literals. This **confirms** a post-restart copy stage is
present in the package.

The compound `0xaf` backend is now fully mapped for both acquired helpers. It
concatenates child `0xab`, which covers internal flash
`0x00003000..0x001fffff` (`0x1fd000` bytes), and child `0xac`, which covers
external QuadSPI `0x68617000..0x68916fff` (`0x300000` bytes). It erases the
internal child before the external child, splits writes at their boundary, and
checksums the completed destination. A separate type `0x2b` maps internal
`0x00000000..0x00002fff` but is not part of `0xaf`; the observed normal main
copy does not address that resident prefix.

On the recovered success path, the helper finalizes the update state and calls
the function pointer stored at internal address `0x00003004`, the application
reset vector. This shows a direct helper-to-application handoff after the copy.
It does not reveal the earlier resident-loader decision to validate and launch
the helper.

The omitted resident stage below `0x3000` must still decide whether and how to
install and invoke this helper. Therefore static analysis still cannot say
whether it authenticates the helper, uses a rollback slot, recovers from an
interruption while the helper is being installed, or rejects modified bytes.
The helper occupies `0x1ffc0000..0x1ffc99ff` in 3.10 and
`0x1ffc0000..0x1ffc90ff` in 13.70, both within SRAM_L. These addresses do not
overlap the main application's `0x00003000..0x001fffff` internal-flash range.
How the resident stage copies the helper into RAM, validates it, and handles
interruption remains unknown, so this correction does not make a normal update
demonstrably reversible.

`tools/garmin-firmware/update_af_trace.py` reproduces the compound mapping for
the pinned helpers. The tool hashes to
`03d450496c9bbd642be2a70673b4110beb40ac7458dabb5f875dc714567cf18b`;
the 3.10 and 13.70 reports hash to
`0d2a5e1298450906f5a47537cf9441b0e8c0ec60970acea3af0420491a21bc22`
and `715019810acca7c5d235a50464265f94d6937466ccab0827d6c8652782cb69c9`.
Focused scans of both helper binaries found no embedded standard SHA-1,
SHA-256, or MD5 initial-state set and no PEM certificate/public-key marker.
Those negative scans narrow the helper itself but cannot exclude custom,
hardware-backed, or resident-loader authentication.

`tools/garmin-firmware/update_helper_trace.py` hash-pins both helper inputs and
reproduces their vector/header anchors and static region maps. Its generated
reports hash to `911c4fe1660c5271ed6c7dd6e9539adfcf8b1fc935ac97292fd494458b958905`
(3.10) and `4121bbae3d1c8ff3987e390763a5de48f21117a93382ab68c37a7b31cb9fcf4d`
(13.70). The focused 3.10 copy-loop export is
`decompile-0505-copy-310.txt`, SHA-256
`3649f50b8f0a97ea6a43b76ffc667ef6232e2381a22a1e133d38eae05c83f0ed`.

The reproducible storage-anchor reports are
`artifacts/firmware/analysis/update-storage-310.json` (SHA-256
`3c2905ec2d1c7e526a03b12aece5bd9e793cbedf26512b5e77bb7a0194fdef33`)
and `update-storage-1370.json` (SHA-256
`5187216295a7a1e5b16b26a7f07b3ea6e93468b1d0419ad8544b80c79682a3c9`).
The focused Ghidra exports hash to:

| Export | SHA-256 |
|---|---|
| `decompile-update-310-ufs.txt` | `8944de91a7cf6923a5057221ca42132e61140a53e4ed60c1f1d3e84aef7257c4` |
| `decompile-update-310-ufs-lowlevel.txt` | `9dbaa4dcd882351863792d192eaa97aeec9d7697a95beeccc226e84ad81e5caa` |
| `decompile-update-1370-ufs.txt` | `6d04f783a3d3b747ede5721c764a5a65371a581cb42354e990ded3966dd026eb` |
| `decompile-update-1370-main-writer.txt` | `53314f58355176ecbc09abeb08818f509f3f94d65263aaf65be3dfbdc0adc8b4` |

The pinned NXP headers used for the address identification are from legacy
MCUXpresso SDK commit `8a289764d763ad06e0c3a05c885644ed98b970af`:
[`MK28FA15.h`](https://raw.githubusercontent.com/nxp-mcuxpresso/legacy-mcux-sdk/8a289764d763ad06e0c3a05c885644ed98b970af/devices/MK28FA15/MK28FA15.h)
and
[`MK28FA15_features.h`](https://raw.githubusercontent.com/nxp-mcuxpresso/legacy-mcux-sdk/8a289764d763ad06e0c3a05c885644ed98b970af/devices/MK28FA15/MK28FA15_features.h).
Their preserved local SHA-256 values are
`b7aeba5e14f1a814726c8e688defdd427ef4693dd942ccbb0a578f40c153516a`
and `a1cebc9aa4c2b6fb8fec2eaa66ec789f99729de82ec13a78f3fbd2e7c3624cf2`.

## Security conclusion

The application parses, validates, and writes update streams. The directly
observed ordinary full-image checks are unkeyed additive sums plus record/image
structure and compatibility fields. A 20-byte SHA-1 comparison is confirmed
only inside the separately gated `GDELTA01` path. There
is still no evidence that a modified system image would pass every indirect
backend check or the resident loader. The loader below `0x3000` is absent from
both update images and remains capable of enforcing a hidden signature,
device-family policy, anti-rollback rule, or secure-boot decision.

The feasibility verdict therefore remains **YELLOW**. This analysis rules out
using the Connect IQ signature message as proof of system-image signing, but it
does not establish that system images are unsigned or safely replaceable.

## Reproduction

Generate the byte-level reports:

```powershell
python tools/garmin-firmware/firmware_security_scan.py `
  artifacts/firmware/analysis/Forerunner245_310/stream_01_fw_all_bin.bin `
  --output artifacts/firmware/analysis/update-security-310.json

python tools/garmin-firmware/firmware_security_scan.py `
  artifacts/firmware/analysis/Forerunner245_1370_GUPDATE/stream_01_fw_all_bin.bin `
  --output artifacts/firmware/analysis/update-security-1370.json
```

Reproduce the pinned storage anchors:

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

Reproduce the temporary-helper fingerprints:

```powershell
python tools/garmin-firmware/update_helper_trace.py `
  artifacts/firmware/analysis/inspect-310/stream_00_firmware_0505_bin.bin `
  --version 3.10 `
  --output artifacts/firmware/analysis/update-helper-310.json

python tools/garmin-firmware/update_helper_trace.py `
  artifacts/firmware/analysis/inspect-1370/stream_00_firmware_0505_bin.bin `
  --version 13.70 `
  --output artifacts/firmware/analysis/update-helper-1370.json
```

Reproduce the confirmed ordinary full-image checks:

```powershell
python tools/garmin-firmware/full_image_validator.py `
  artifacts/firmware/originals/Forerunner245_1370_GUPDATE.GCD `
  --report artifacts/firmware/analysis/full-image-validation-official-1370.json

python tools/garmin-firmware/full_image_validator.py `
  artifacts/firmware/mutation-lab/Forerunner245_1370_payload-lab.GCD `
  --report artifacts/firmware/analysis/full-image-validation-mutated-1370.json
```

The validator source has SHA-256
`f37fd6622f958e5fa4a265d176e534fcfae491ac783a60c1679f2ab506707fd7`.
It does not implement the delta path or the resident loader.

Run the internal-flash-only project with
`tools/garmin-firmware/run_ghidra_analysis.ps1`, or reproduce the two-region
projects with `run_ghidra_dual_map.ps1`. `MapExternalSegment.java` maps file
offset `0x1fd000` at `0x04600000`; `SeedThumbFunctions.java` seeds vector and
selected cross-region targets. Generated projects and reports remain under the
ignored `artifacts/firmware/` tree.
