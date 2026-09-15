# Forerunner 245 firmware acquisition and format

## Scope and handling

All work in this document was performed on files copied into the host-side
`artifacts/firmware` tree. No firmware file was copied to the watch and no
Garmin update command was issued. Original downloads are immutable inputs under
`artifacts/firmware/originals`; generated streams and reports are under
`artifacts/firmware/analysis`.

The connected device backup identifies a non-Music Forerunner 245 system image
with part number `006-B3076-00` and version 10.40. The unit identifier is private
and is intentionally omitted.

## Acquired packages

The full machine-readable inventory, source URL, timestamps, MD5 values, and
SHA-256 values are in `artifacts/firmware/manifest.json`; GNU-style SHA-256
lines are in `artifacts/firmware/SHA256SUMS`.

| Variant/component | Version | Bytes | SHA-256 | Exact installed match? |
|---|---:|---:|---|---|
| Forerunner 245 system, `006-B3076-00` | 3.10 | 4,245,103 | `ffc802fd505cb62fe680dd50935654ef8177c8a0c74d20de3a6b32a4d185ff43` | No |
| Forerunner 245 Music system, `006-B3077-00` | 3.10 | 6,141,667 | `00cabc2996c5d7867854ca2b17de73da791c7f9b4358d1373145daa052ec8ad0` | No, different variant |
| Sensor hub | 2.50 | 302,439 | `60957fa6b154202088c97cf9dff6d9e7b6744822bf211cf1cdedb5a53e2d1259` | No |
| ANT/BLE | 3.60 | 149,210 | `ab3e87988724e684bda13a3c083d69cdc3ca0a6f3d5289eb4829442146d76462` | No |
| Forerunner 245 system, `006-B3076-00` | 13.70 | 5,120,675 | `8ebefacf6bcc00bec0fb271596abfb9618f9a3114d32b3a106fbd27d5a366adc` | No, current official release |
| GPS/CPE, `006-B3107-08` | 5.50 | 768,510 | `6e9dbe97d3dea1b40441f14cc38545d853e5d38ed8a6abfe747526e1e59a0b4e` | No; backup reports 5.30 |
| Sensor hub, `006-B3078-00` | 18.04 | 364,347 | `007b441431c0859b89628624c7ac4d47be0aece233f8b73ae115304da92d1913` | No; backup reports 18.00 |
| ANT/BLE, `006-B3204-00` | 6.15 | 174,457 | `8848f6e679ff3913b80f31b63e385d444ca3e83e3dfb54ed3253523dbf417469` | **Yes** |

The four older packages came directly from Garmin's
`download.garmin.com/software` service. The four current packages came from
Garmin URLs returned by Garmin's OMT update catalog. The OMT request used a
host-side backup of `GarminDevice.xml` after removing the Model, Extensions, and
DataType sections and replacing the unit ID with `9999999999`. The exact
sanitized request and server response were retained under
`artifacts/firmware/analysis`; no personal identifier was sent.

Garmin's current [Forerunner 245 download collection](https://www8.garmin.com/support/collection.jsp?product=010-02120-00)
directs users to Garmin Express. The catalog returned system 13.70 during this
investigation. Garmin's [10.40 release announcement](https://forums.garmin.com/sports-fitness/running-multisport/f/forerunner-245-series/297318/forerunner-245-series-software-update-10-40---live)
confirms that 10.40 was an official release.

### Exact 10.40 image availability

An archived copy of Garmin's own non-Music download page, product ID `14935`,
identifies `Forerunner245_1103Beta.zip` as the 11.03 beta archive and
`GUPDATE-1040.GCD` as its rollback file. The preserved HTML snapshot hashes to
`4dee13ab4b15758cb299e4b6daf0220ccc1582ce230c6426fc9798c1a62b0adf`.
The live Garmin ZIP URL now returns HTTP 404, and the Internet Archive CDX
index has no captured copy of that ZIP. A model-matched non-Music (`HWID 3076`)
10.40 binary has therefore **not** been acquired or hashed. The watch backup
contains version metadata but no `GUPDATE.GCD` system image.

## Confirmed GCD container structure

The acquired files match the flat record format documented by Herbert Oppmann
in [Garmin GCD Firmware Update File Format](https://www.memotech.franken.de/FileFormats/Garmin_GCD_Format.pdf).
All integer fields below are little-endian.

```text
offset  size  meaning
0x0000  6     ASCII "GARMIN"
0x0006  2     format version (100 means 1.00)
0x0008  ...   contiguous records

record:
+0       2     record ID
+2       2     body length
+4       N     body
```

Every acquired file has format version 1.00, parses without gaps to an
`0xffff` zero-length end record, and has no trailing bytes.

Important record IDs observed or documented:

| ID | Meaning | Status in these files |
|---:|---|---|
| `0x0001` | additive checkpoint | Confirmed |
| `0x0002` | zero filler | Confirmed |
| `0x0003` | compressed Garmin part number | Confirmed |
| `0x0005` | copyright string | Confirmed |
| `0x0006` | firmware descriptor field types | Confirmed |
| `0x0007` | firmware descriptor values | Confirmed |
| `0x0008` | `boot.bin` | Documented generally; **absent here** |
| `0x02bd` | `fw_all.bin` / main application | Confirmed in system packages |
| `0x0401` | external/secondary firmware data | Confirmed in radio, sensor-hub, and GPS packages |
| `0x0505` | temporary native update helper | Confirmed in system packages |
| `0xffff` | end | Confirmed |

The newer [garmin-gcd-toolkit](https://github.com/theodorebeaupre-prog/garmin-gcd-toolkit)
was tested first. Its nine-byte marker walker was developed against a nuvi
2455 and treated marker-like bytes inside these Forerunner payloads as record
boundaries. Its record counts and lengths were consequently false for these
files. The local tool uses the flat four-byte header above and fails closed on
truncated records.

## Descriptors and streams

Record `0x0006` contains pairs of field ID and field type. Record `0x0007`
contains the corresponding values. The fields used by the system images expose:

- erase flag;
- XOR byte;
- following firmware-data record ID;
- declared firmware length;
- hardware ID;
- software version and related version fields.

All acquired streams use XOR value zero. The parser concatenates only the
declared following record ID until the exact declared length is reached. It
does not scan payloads for apparent record markers.

System-package stream results:

| Package | Record | Length | HWID | SW | SHA-256 of extracted stream |
|---|---:|---:|---:|---:|---|
| non-Music 3.10 | `0x0505` | 39,424 | 3076 | 3.10 | `80a075972f46fefe7df47052c81ce73fb2032f6d31eeb3d1bd5f73c79c1d568e` |
| non-Music 3.10 | `0x02bd` | 4,201,216 | 3076 | 3.10 | `3225c50585503d331a9c0ee8faf342241207dd98825f4f0f9cf3fa23831c54ba` |
| non-Music 13.70 | `0x0505` | 37,120 | 3076 | 13.70 | `f2351f808c0510baba6aae045867d8a366646511da662a411038426107725e46` |
| non-Music 13.70 | `0x02bd` | 5,079,040 | 3076 | 13.70 | `b45be1baf98999af10f073bef52b284beb2aea6abbb7cde2ffa59fb6bcedeab6` |
| Music 3.10 | `0x0505` | 52,224 | 3077 | 3.10 | `aad6f36d72fab849c9923516de84d83213008301b234c5c721284adce230dbe7` |
| Music 3.10 | `0x02bd` | 6,084,864 | 3077 | 3.10 | `9204317d558f35c2862c210c118737df2633f33c4f59e676f655f62c46487452` |

### The `0x0505` temporary update helper

The previously unresolved `0x0505` stream is now **confirmed** to be a native
Cortex-M update helper, not a resource. Both preserved non-Music versions have
a vector table whose reset vector is `0x1ffc01f1`; when loaded at
`0x1ffc0000`, that reset handler is at file offset `0x1f0`. NXP defines
`0x1ffc0000` as the MK28FA15 `SRAM_L_BASE`, so the helper is RAM-resident.

| Version | Bytes | Runtime interval | Reset-entry literal |
|---|---:|---|---|
| 3.10 | 39,424 | `0x1ffc0000..0x1ffc99ff` | `0x1ffc3dcd` |
| 13.70 | 37,120 | `0x1ffc0000..0x1ffc90ff` | `0x1ffc3231` |

The helper's static region table repeats staging type `0x05` at
`0x68103000` (capacity `0x15000`) and main-payload type `0x0e` at
`0x68118000` (capacity `0x4ff000`). The 3.10 helper's main loop reads type
`0x0e` in chunks of at most `0x1e000` bytes and writes through destination
type `0xaf`. In both helpers, `0xaf` concatenates internal-flash child `0xab`
(`0x00003000..0x001fffff`, `0x1fd000` bytes) with external-QuadSPI child
`0xac` (`0x68617000..0x68916fff`, `0x300000` bytes). Its total capacity is
`0x4fd000`; the separate type `0x2b` mapping for internal
`0x00000000..0x00002fff` is not included. This is **confirmed** from static
function calls and pinned cross-version reports, but
it does not establish that the omitted resident loader accepts a modified
helper, how it installs the helper, or what authentication it performs first.

The main application occupies internal flash through `0x001fffff`; the
helper's `0x1ffc0000` SRAM_L interval is a separate address range and does not
overlap it. The helper is therefore a RAM-resident transient updater rather
than evidence for code stored at the top of application flash. None of the
system GCDs contains a documented `0x0008 boot.bin` record, and bytes below
application base `0x3000` remain absent from all acquired packages.

`tools/garmin-firmware/update_helper_trace.py` reproduces the vector, header,
and region-table evidence only for the pinned 3.10 and 13.70 helper hashes.

## Checksums, compression, encryption, and signatures

### Confirmed

- Every one-byte `0x0001` checkpoint makes the sum of all file bytes through
  the checkpoint equal zero modulo 256.
- All checkpoint records in all eight packages validate.
- The final file sum is `0xfe` because the following zero-length end record is
  encoded as `ff ff 00 00`.
- Descriptor XOR values are zero, and the main streams contain readable ASCII
  strings and executable Arm Thumb code.
- The `fw_all.bin` Shannon entropy is approximately 6.97-7.17 bits per byte,
  consistent with mixed code/data/resources and inconsistent with whole-image
  high-entropy encryption.
- The 3.10 GarminOS installer recomputes the additive GCD checksum. Its
  non-delta full-image fallback additionally requires the selected payload's
  byte sum to be zero modulo 256 before calling the normal writer.
- A standard SHA-1 state/finalization path compares 20-byte digests only after
  the separate delta engine recognizes the eight-byte `GDELTA01` header.

### Not established

- The additive checks and delta-only SHA-1 comparison prove integrity checks
  only. They do not show what every indirect installer backend or the device
  bootloader validates before programming or booting.
- No container-level cryptographic signature field has been identified in the
  acquired descriptor layouts. That is not evidence that cryptographic
  authentication is absent; it may be embedded in an opaque firmware region or
  implemented through device-specific trust metadata.
- Individual secondary streams with near-eight-bit entropy may be compressed,
  encrypted, or preprocessed. Their algorithms have not been identified.

The main firmware contains the text `Signature check failed on file:` near
Connect IQ VM strings. It is evidence for some file-signature check inside
GarminOS, not evidence about GCD or boot-time authentication.

## CPU and load-address evidence

Each `0x02bd` stream begins with a valid-looking little-endian Cortex-M vector
table:

| Image | Initial SP | Reset vector |
|---|---:|---:|
| non-Music 3.10 | `0x2002e388` | `0x000031f1` |
| non-Music 13.70 | `0x2001b330` | `0x000031f1` |
| Music 3.10 | `0x2003f6b8` | `0x000031f1` |

With the binary loaded at `0x3000`, the reset vector points to file offset
`0x1f0`. Capstone 5.0.7 decodes that location in all three images as a plausible
Cortex-M reset trampoline:

```text
000031f0  cpsid i
000031f2  mov.w r0, #0
000031f6  msr control, r0
000031fa  isb sy
000031fe  ldr.w sp, [pc, #8]
00003202  ldr r0, [pc, #8]
00003204  bx r0
```

The literal branch targets differ by build, while the trampoline is stable.
This locally confirms Arm Thumb/M-class code and strongly supports application
base `0x3000`. Independent analysis of a 245 Music image reached the same base
address in [Anvil Secure's GarminOS research](https://www.anvilsecure.com/blog/compromising-garmins-sport-watches-a-deep-dive-into-garminos-and-its-monkeyc-virtual-machine.html).

### Two-region executable mapping

The non-Music `fw_all` images continue beyond the K28F internal-flash window.
The mapping is now confirmed rather than treated as trailing resource data:

| File interval | Runtime interval | 3.10 length | 13.70 length |
|---|---|---:|---:|
| `[0, 0x1fd000)` | `0x00003000` through `0x001fffff` | 2,084,864 | 2,084,864 |
| `[0x1fd000, end)` | starts at `0x04600000` | 2,116,352 | 2,994,176 |

At the second boundary, little-endian words point into `0x046...`. More
decisively, internal-flash veneers near `0x001c0000` execute
`ldr.w pc, [pc]` through literal targets in that range; mapped targets decode
as coherent Thumb functions. For example, the veneer at `0x001c01e8` targets
`0x046efcd1`. The second region ends at `0x04804aff` in 3.10 and `0x048dafff`
in 13.70. Its physical backing is still unknown; the mapping alone does not
identify a flash chip or bus.

## Function-identification status

This session established executable boundaries and a reset entry point, then
used Capstone and dual-map Ghidra analysis to recover selected update and board
driver paths. Unlisted subsystem identities remain unknown.

| Target | Result |
|---|---|
| Reset handler | **Confirmed:** Thumb entry `0x31f1`; stable reset trampoline at `0x31f0` |
| Update orchestration | **Confirmed application-side parser:** 3.10 and 13.70 descriptor parsers, structural checks, family-ID handling, and file orchestration recovered; resident-loader acceptance still unknown |
| Display initialization/framebuffer | **Unknown:** no controller identity or verified function address |
| Button handling | **Confirmed electrical pin table:** GPIOC11, GPIOD10, GPIOD1, GPIOA20, GPIOA22; four logical labels and safe board sequencing unresolved |
| Filesystem/storage driver | **Strong lead:** FAT-style paths and USB/storage strings; device and function boundaries unresolved |
| RTC | **Confirmed peripheral cluster:** stable K28F RTC reads and interrupt clearing; full initialization sequence unresolved |
| Battery/PMIC | **Partial:** PMIC scheduling/telemetry recovered and backlight writes reach bus 3, address `0x28`, registers `0x2e`/`0x2f`; rail semantics and safe sequencing unknown |
| Image signature verification | **Unknown:** generic file-signature text exists, but no evidence ties it to GCD acceptance |

These are explicit limits of the current static pass; none is implemented as a target driver
in FlyOS.

## Offline metadata/checkpoint experiment

An isolated copy of the official non-Music 13.70 GCD was produced to test only
the documented checkpoint algorithm. The experiment changed the terminal byte
of record `0x0005` (copyright metadata) from `.` to `!`, kept the file length
unchanged, and recomputed every byte checkpoint. It did not change either
decoded firmware stream: their SHA-256 values are byte-identical to the
official source after extraction. The original package SHA-256 is
`8ebefacf6bcc00bec0fb271596abfb9618f9a3114d32b3a106fbd27d5a366adc`; the
analysis copy SHA-256 is
`c57ca87d0d048023c5c778cf3da09dcb99ebe7790bd8ff342159bcf41e2f650f`.

This demonstrates that the observed additive package checkpoints are
recomputable. It does **not** establish that a modified GCD would be accepted
by GarminOS or the resident loader, and it says nothing about a firmware-payload
modification, the full-image payload sum, delta-only SHA-1 handling,
cryptographic authentication, or boot recovery.
The analysis copy is prohibited from being copied to the watch.

## Reproduction

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools/garmin-firmware/download_official_firmware.ps1
python -m unittest discover -s tools/garmin-firmware/tests -v
powershell -NoProfile -ExecutionPolicy Bypass -File tools/garmin-firmware/run_analysis.ps1
```

For reproducible Ghidra work, use `run_ghidra_dual_map.ps1`. It imports the
internal-flash interval at `0x3000`, maps file offset `0x1fd000` at
`0x04600000`, and seeds vector and selected Thumb targets before analysis.
