# Forerunner 245 low-level driver leads

## Scope and evidence rules

This pass used only the preserved non-Music 3.10 and 13.70 `fw_all.bin`
streams. It did not access the watch. The input files were opened read-only and
generated reports were written beside the existing offline analysis artifacts.

Addresses below are virtual addresses for a raw image loaded at `0x3000`. To
obtain a file offset, subtract `0x3000`. Every address is specific to the exact
image hash in this table and must not be transferred to another version.

| Image | Bytes | SHA-256 |
|---|---:|---|
| non-Music 3.10 `fw_all.bin` | 4,201,216 | `3225c50585503d331a9c0ee8faf342241207dd98825f4f0f9cf3fa23831c54ba` |
| non-Music 13.70 `fw_all.bin` | 5,079,040 | `b45be1baf98999af10f073bef52b284beb2aea6abbb7cde2ffa59fb6bcedeab6` |

The reproducible scanner reports three distinct kinds of evidence:

1. printable source paths, diagnostic text, and workspace names;
2. aligned little-endian words that fall in known K28F peripheral ranges;
3. Thumb `ldr` instructions whose PC-relative address resolves exactly to one
   of those word slots.

Instruction and peripheral scans stop at virtual address `0x00200000`, the end
of the K28F's 2 MiB internal-flash window. Printable strings are inventoried
across the whole stream and marked when they fall beyond that window. This
prevents resource bytes appended to `fw_all.bin` from being promoted to code
merely because they happen to decode as Thumb instructions.

A string or aligned word alone may be coincidental data. A PC-relative load is
an instruction-level lead, but still does not establish a function's purpose
without surrounding behavior. Ghidra was used to confirm function ownership
where its raw-binary analysis produced a function; Capstone was used to verify
the instruction and literal address independently.

## Results at a glance

| Subsystem | Best evidence | Result |
|---|---|---|
| RTC | Stable reads and writes through K28F RTC base `0x4003d000`; matching source path | **Confirmed driver cluster and several callable routines** |
| USB | 24 literal loads into K28F USB high-speed/PHY blocks in each version, plus `HWM_usb main` and USB-manager paths | **Confirmed low-level controller cluster** |
| Buttons | Matching five-entry key workspace, pin table, and PORT interrupt-clear sequence in both versions | **Confirmed five-key GPIO map by internal index; physical button labels remain partly unknown** |
| Battery/PMIC | Matching telemetry and PMIC service code; bus-3 address `0x28` register transactions | **Confirmed transaction endpoint; most register and rail meanings unknown** |
| FAT/TFS storage | FAT16 parsing and check-disk paths plus Garmin TFS/UFS strings | **Confirmed filesystem code; physical storage backend unknown** |
| Backlight | Cross-version policy-to-PMIC call chain ending in writes to registers `0x2e` and `0x2f` | **Confirmed brightness-control path; electrical register semantics still unnamed** |
| Display/framebuffer | Cross-version display semaphore, 240x240 byte framebuffer, dirty rectangles, pixel conversion, FLEXIO0/DMA transfer engine, and pin-mux setup | **Confirmed software-to-peripheral path; external panel identity and wire roles remain unknown** |

## RTC

This is the strongest target-driver result. The scanner found 15 aligned
literals containing the K28F RTC base `0x4003d000` and 19 resolving Thumb
literal loads in **each** firmware version. The corresponding code ranges are
`0x000c41ca` through `0x000c4e3e` in 3.10 and `0x00007b96` through
`0x00009472` in 13.70. The nearby source paths are:

- 3.10: `0x000c4f4c`, `HWM/core/garminos/processor/kinetis/hwm_rtc.c: 142`
- 13.70: `0x00009508`, the same path and line

Two small routines survived with nearly identical behavior across the large
version change:

| Behavior observed in disassembly | 3.10 | 13.70 | Confidence |
|---|---:|---:|---|
| Repeatedly read RTC seconds at `+0x00` and prescaler at `+0x04` until a consistent sample is obtained, then scale the result | `0x000c41c8` | `0x00007b94` | **Confirmed** |
| Repeated stable seconds/prescaler read returning a packed tick value | `0x000c4438` | `0x00009038` | **Confirmed** |
| Clear bit `0x04` in the register at RTC base `+0x1c` | `0x000c4478` | `0x000090b4` | **Confirmed instruction semantics; event meaning not named** |

The 13.70 initialization area around `0x00008ddc` accesses offsets `+0x10`,
`+0x14`, and `+0x1c`, including a stabilization delay. This is a strong RTC
initialization lead. A FlyOS RTC driver can use these routines to guide an
offline register model, but it still needs the K28F reference manual and board
clock-source configuration before target code is credible.

## USB

Both images contain exactly 13 aligned literal slots referenced by exactly 24
Thumb literal loads in the K28F `0x400a1000`-`0x400a2fff` USB high-speed and
PHY range. The clusters are:

| Image | Resolving code range | Text anchors |
|---|---|---|
| 3.10 | `0x000c863c`-`0x000ca53c` | `HWM_usb main` at `0x000c98fc`; USB-manager path at `0x000cff88` |
| 13.70 | `0x0001ba38`-`0x0001d8ba` | `HWM_usb main` at `0x0001cc90`; USB-manager path at `0x00020814` |

Within the 3.10 Ghidra project, examples of functions owning direct controller
loads include `0x000c8604`-`0x000c867b`, `0x000c86c4`-`0x000c87e9`,
`0x000c884c`-`0x000c889f`, `0x000c9260`-`0x000c934f`, and
`0x000c94fc`-`0x000c963d`. The PHY-side functions include
`0x000ca4b4`-`0x000ca4fb` and `0x000ca50c`-`0x000ca59d`.

This confirms that the main firmware contains a native K28F USB high-speed
driver. It does not yet identify endpoint descriptors, the safe initialization
order, clocking, or the exact boundary between controller, PHY, Garmin USB
manager, and mass-storage class code.

## Buttons and key handling

The two images retain the same generic key-manager structure:

| Evidence | 3.10 | 13.70 |
|---|---:|---:|
| `&hwm_key_ws[key_id].workq_isr_item` string | `0x000b8e38` | `0x0000f7c0` |
| Code load of that name through a literal slot | `0x000b8c92` | `0x0000f80a` |
| ISR work-item setup routine | `0x000b8c64` | `0x0000f7e4` |
| `&hwm_key_ws[key_id].workq_item` string | `0x000b9160` | `0x0000fa84` |
| Deferred work-item setup routine | `0x000b8f24` | `0x0000faa4` |

Both deferred setup routines accept indices zero through four (`cmp r0,#4`)
and calculate a 56-byte workspace stride. The corresponding five-row board pin
table is at `0x000b8e5c` in 3.10 and `0x0000f9bc` in 13.70. Each row is an
encoded pin word followed by the stable value `5`:

| Key-manager index | 3.10 encoded word | 13.70 encoded word | Decoded GPIO | Confidence |
|---:|---:|---:|---|---|
| 0 | `0x04b` | `0x14b` | GPIOC pin 11; 13.70 adds flag `0x100` | **Confirmed pin; flag meaning unknown** |
| 1 | `0x06a` | `0x06a` | GPIOD pin 10 | **Confirmed** |
| 2 | `0x061` | `0x061` | GPIOD pin 1 | **Confirmed** |
| 3 | `0x014` | `0x014` | GPIOA pin 20 | **Confirmed** |
| 4 | `0x016` | `0x016` | GPIOA pin 22 | **Confirmed** |

The decode is not based on the table's appearance alone. The interrupt path at
`0x000b8d78` in 3.10 and `0x0000f8fe` in 13.70 takes bits 5 through 7 as a
port index, adds `index * 0x1000` to `0x40049000` (PORTA), takes the low five
bits as the pin number, and writes `1 << pin` to offset `0xa0`. On Kinetis K28
that offset is `PORTx_ISFR`, so the operation clears the selected pin's pending
interrupt flag. This independently confirms the port/pin interpretation.

The registration routines at `0x000b8da4` and `0x0000f928` iterate all five
rows. They then apply additional configuration to encoded pins `0x14`, `0x16`,
`0x61`, and `0x6a`, omitting index zero. Index zero also gains the high `0x100`
flag in 13.70. Those two facts make index zero a strong candidate for the
special LIGHT/power/wake key. The 13.70 deferred routine at `0x0000faa4` also
schedules index zero after `0x2ee` ticks while indices one through four use 500,
adding a third independent distinction. These facts still do not prove the
printed button label or the scheduler tick duration.
No trustworthy evidence yet maps indices one through four to UP, DOWN, START,
and BACK, or establishes active level and pull configuration. A FlyOS input
driver can preserve this numeric map while leaving the human-readable labels
unassigned.

The 13.70 call graph also establishes where this fits into board startup. The
hardware-main dispatcher at `0x0002387c`, located immediately after the
`HWM_main_workq`, GPS work-queue, USB-manager, and RTC work-item names, calls
the display-subsystem initialization routine `0x0000f258`. Later in that same
dispatcher, `0x0000fa18` calls `0x0000f928` to register the five pins. The
interrupt-side routine `0x0000f688` reads the selected bit from
`GPIOx_PDIR` (`0x400ff010 + port * 0x40`), adjusts the edge configuration, and
queues the per-key deferred work at `0x0000faa4`. This is a complete static
path from the board dispatcher to GPIO input and debounce scheduling. It does
not reveal the printed label for each internal index.

## Battery and PMIC

The same battery telemetry routine is recognizable in both images:

- 3.10 function `0x000b53c4`-`0x000b553f`, with its long
  `Time(ms),gtime,SOC,...PMIC VBatt...` format string at `0x000b6498`;
- 13.70 function beginning `0x0000cab0`, with the corresponding format string
  at `0x0000ddf8`.

These functions gather state of charge, fuel-gauge battery voltage,
temperature, charge rate, charger state, open-circuit voltage, PMIC battery
voltage, hibernation state, and event flags. They are telemetry aggregation
routines rather than single-register battery APIs, but their callees are a
focused next set for decompilation.

PMIC scheduler setup also survives nearly unchanged:

| Evidence | 3.10 | 13.70 |
|---|---:|---:|
| PMIC work-item setup routine | `0x000b9d0c` | `0x000108a0` |
| `&pmic_workq_item` | `0x000ba990` | `0x0001088c` |
| `&pmic_smphr` | `0x000ba9a4` | `0x00010ee8` |
| `&pmic_event` | `0x000ba9b0` | `0x00010ef4` |

The firmware also contains `hwm_batt_nonvol.c: 67` in both versions. The PMIC
transaction wrapper is now identified as `0x000b9c60` in 3.10 and
`0x000107d8` in 13.70. Both call the version-specific bus routine with bus ID
`3`, device address `0x28`, a one-byte register address, and caller-provided
data. This is confirmed transaction behavior and is consistent with the PMIC
cluster, but it does not by itself prove a seven-bit versus wire-format address
convention or name the chip registers. Rail assignments, charger settings,
power-off sequence, and safe initialization order remain unknown.

## Storage and filesystems

FAT/TFS code is directly visible and consistent with the connected FAT16
volume:

| Evidence | 3.10 | 13.70 |
|---|---:|---:|
| `tfs_fat_chkdsk failed...` string | `0x0010e3f4` | `0x000a526c` |
| Code loading that string | `0x0010e006` | `0x000a53fe` |
| First code load of `FAT16    ` | `0x001132da` | `0x000ab2ec` |
| `HWM_TFS` string | `0x000d1784` | `0x00021df8` |
| `hwm_rgn_ufs.c: 40` path | `0x000d365c` | `0x00023208` |

No resolving code load of an SDHC-range literal was found in either image. The
analysis also did not identify a flash-chip part number or a trustworthy block
device boundary. These results establish FAT/TFS parsing and a Garmin UFS
region layer, but do not determine whether the non-Music model's accessible
volume resides in internal flash, external serial flash, eMMC, or another
medium.

## Backlight

The backlight control path is reproducible across the two images:

| Layer | 3.10 | 13.70 | Observed behavior |
|---|---:|---:|---|
| Policy/scheduling | `0x0017ba10` | `0x047fcd54` | Selects/clamps requested mode, brightness, and timeout |
| Brightness clamp | `0x000b49a0` | `0x0000bb5c` | Bounds a floating-point percentage, converts it to an integer, and calls the low-level setter |
| Register-value conversion | `0x000b9d94` | `0x00010928` | Below 4% emits zero; 4-100% maps into a value with bit `0x20`; over 100% emits `0x35` |
| Bus transaction wrapper | `0x000b9c60` | `0x000107d8` | Serializes one-byte writes through bus 3, device address `0x28` |

The last two stages write the converted byte first to register `0x2e` and then
to register `0x2f`. The same two-register order, thresholds, and bus/device
arguments survive the major version change, making this a **confirmed
backlight brightness-control path**. The scanner reports the instruction-level
signatures at `0x000b9dc0`/`0x000b9dcc` and
`0x0001093c`/`0x00010948`.

For 13.70, the second firmware region is mapped from file offset `0x1fd000` to
runtime `0x04600000`. Under that mapping the WBL source path is at
`0x047fd4ff`, and the policy function at `0x047fcd54` reaches the internal
clamp through a veneer at `0x048d6928`. This removes the earlier ambiguity
caused by treating the trailing region as flat data.

The device at address `0x28`, register names, enable polarity, LED current
limits, and relationship between registers `0x2e` and `0x2f` are not named by
the static evidence. These writes must not be copied into FlyOS until they are
matched to authoritative PMIC documentation and the surrounding power sequence.

## Display path

The physical display path is now recovered far enough to identify the main
buffer, update tracker, conversion stage, K28F peripheral, DMA handoff, and
pin-mux set. The external panel part and the individual wire meanings remain
unknown.

The board-startup routine at `0x000b86f4` in 3.10 and `0x0000f258` in 13.70
initializes a semaphore named `&dspl_smphr` and clears exactly `0xe100` bytes.
`0xe100` is 57,600, exactly `240 * 240`, and the cleared pointer is subsequently
consumed as the display source. This establishes a one-byte-per-pixel logical
framebuffer:

| Evidence | 3.10 | 13.70 |
|---|---:|---:|
| `&dspl_smphr` string | `0x000b8750` | `0x0000f24c` |
| Display init | `0x000b86f4` | `0x0000f258` |
| `mov.w r2,#0xe100` clear site | `0x000b8706` | `0x0000f26a` |
| Logical framebuffer | `0x3400e9cc` | `0x1ffde6e8` |
| Dirty-rectangle accumulator | `0x000b8794` | `0x0000f2e8` |
| Dirty-list copy/query | `0x000b8768` | `0x0000f2c0` |

Both rectangle accumulators clamp coordinates to 240, align rectangle edges
to eight pixels, store eight bytes per entry, and cap the list at 100 entries.
A full-screen `(0,0,240,240)` update receives special treatment. The 3.10
framebuffer resides in the external-memory address range while 13.70 places it
in the K28F SRAM range, so the absolute backing address is version-specific.

The update path is also homologous across the versions:

| Layer | 3.10 | 13.70 | Observed behavior |
|---|---:|---:|---|
| Locked update wrapper | `0x000d0700` | `0x00009a10` | Holds the display-update semaphore and invokes the active display backend |
| Hardware/backend setup | `0x000bf1a0` | `0x0000e4f8` | Registers `&dspl_detached_event`, interrupt/DMA callbacks, and the transfer engine |
| Rectangle-aware flush | `0x000bf5dc` | `0x0000e98c` | Reads dirty rectangles and selects full or partial conversion |
| Pixel-layout converter | `0x000bf54c` | `0x0000e8fc` | Converts 240-byte source rows into a 244-byte-stride transfer layout |
| Transfer kickoff/wait | `0x000bf424` | `0x0000e7c4` | Drives two GPIOE control bits and starts/waits for the DMA-backed transfer |
| Transfer staging buffer | `0x34000468` | `0x1ffcd294` | 244 bytes per row; full frame is `0xe4c0` bytes |

The converter's masks and split writes show that the one-byte logical pixels
are repacked into a panel-oriented bit layout. The exact bit-to-color mapping
and on-wire row framing have not yet been named.

### Converter model and offline instruction oracle

The converter is self-contained after its entry dispatcher: it reads four
configuration bytes, source pixels, and the existing staging buffer, and it
writes the staging buffer without calling another function. This made it
possible to validate a host transcription against the original Thumb
instructions in an isolated Unicorn VM. The VM maps copies of the preserved
firmware and synthetic buffers; it does not access the watch or write either
firmware artifact.

For the ordinary full-row path, every 240-byte source row becomes this
244-byte staging row:

```text
00 | 120 bytes from mask 0xea | 00 | 00 | 120 bytes from mask 0x15 | 00
```

For each adjacent source-pixel pair `(a,b)`, the corresponding packed bytes
are exactly:

```text
primary   = ((a & 0xea) >> 1) | (b & 0xea)
secondary =  (a & 0x15)       | ((b & 0x15) << 1)
```

The masks are complements and partition all eight source bits, but the static
result does not identify those bits as specific panel colors or signals. Four
source pixels produce two primary and two secondary bytes. Partial updates
round the horizontal interval outward to four-pixel words and update only the
corresponding packed bytes; they leave the framing bytes and other staging
bytes untouched. The reverse flag maps source row `y` to staging row
`239 - y` and reverses pixel order within each row, which is an exact
180-degree layout transform at the converter boundary.

The host model also transcribes the three-byte entry dispatcher. It selects
one of two addressing bodies and may expand a rectangle to full rows or a full
frame. In 3.10 the three gate bytes have distinct addresses; their preserved
values are all zero. In 13.70 all three pointer literals alias one byte, whose
preserved value is zero, so only `(0,0,0)` and `(1,1,1)` can exist in that
image. The runtime reverse byte is RAM-backed in both versions, so its startup
value cannot be obtained from the firmware file alone.

`display_row_model.py --verify` checked zero, ramp, and deterministic
pseudorandom source frames; full, partial, unaligned, and 179/180-byte
threshold rectangles; both reverse states; both gate states representable in
13.70; and all eight gate combinations in 3.10. A separate sweep exercised all
65,536 ordered input-pixel pairs. All 186 model-to-instruction comparisons
passed. Sixty-three directly comparable cases also produced identical staging
buffers in 3.10 and 13.70. The JSON verification report has SHA-256
`45dd56f563e81555120b04ef947d6798fd2ed508894abf05e890d758e2c7f122`.

This proves the software conversion and staging offsets for inputs satisfying
the observed caller contract. It does not prove the external panel's color
encoding, interpret the four framing bytes electrically, or validate the
FLEXIO/DMA setup and panel-command sequence.

The low-level display object is the two-word pair `<0x400df000,0x46>` at
`0x000bed78` in 3.10 and `0x0000e210` in 13.70. NXP's MK28FA15 device header
and startup table identify `0x400df000` as `FLEXIO0_BASE` and IRQ number
`0x46` (70 decimal) as `FLEXIO0_IRQn`; including the 16 Cortex-M exception
slots, its vector-table index is 86. The same code uses DMA base `0x40008000`,
DMAMUX base `0x40021000`, and DMA channels 29 and 30. These constants were
cross-checked against NXP's legacy MCUXpresso SDK at commit
`8a289764d763ad06e0c3a05c885644ed98b970af` (`MK28FA15.h` and
`startup_MK28FA15.S`). This is **confirmed FLEXIO0 plus DMA display transport**,
not an SPI2 transaction.

The pin setup is stable despite a change in the pin-configuration API. Function
`0x000d0600` in 3.10 passes the pin and mux separately; `0x000098fc` in 13.70
encodes the mux in the high bits of the pin value. Together they configure:

| Pins | Mux selection observed |
|---|---:|
| PTE6, PTE7 | ALT2 |
| PTE8, PTE11 | ALT3 |
| PTE12, PTE13, PTE16, PTE17, PTE18, PTE19 | ALT7 |
| PTE9, PTE10 | ALT1 / GPIO |

The transfer routine uses GPIOE base `0x400ff100` and masks `0x200` and
`0x400`, confirming direct manipulation of PTE9 and PTE10. Static analysis does
not establish which alternate-function pin is data, clock, latch, chip-select,
or another panel signal. A follow-up decode recovered all initial FlexIO
register values, a six-bit parallel transmit shifter fed by DMA channel 29, and
a second control shifter fed by DMA channel 30; see `docs/display-flexio.md`.
The code also proves that PTE9 pulses high around transfer start while PTE10 is
driven high, but it does not name their electrical functions. The external
panel/controller, package-pin mapping, selected FlexIO clock rate, power-up
delay units, and full safe reset sequence remain open. The init sequence is
evidence for the existing firmware, not yet a safe FlyOS driver recipe.

Two earlier string leads are explicitly excluded. The K28F SPI2 initializer at
`0x000c0ea0` in 3.10 and `0x00015704` in 13.70 belongs to the Apollo sensor-hub
transport/update cluster. In the mapped 13.70 external region,
`&hmd_screen_smphr` at `0x0472adac` sits with `temp.fit` and `ScrnCfgDA.fit`
handling, indicating a screen-configuration FIT service rather than the panel
driver. The generic `display` string at `0x00136478` in 3.10 is likewise part
of serialization code.

## Reproduction

Install the pinned Capstone version and regenerate both machine-readable
reports:

```powershell
python -m pip install capstone==5.0.7
python tools/garmin-firmware/driver_leads.py `
  artifacts/firmware/analysis/Forerunner245_310/stream_01_fw_all_bin.bin `
  --output artifacts/firmware/analysis/Forerunner245_310/driver-leads.json
python tools/garmin-firmware/driver_leads.py `
  artifacts/firmware/analysis/Forerunner245_1370_GUPDATE/stream_01_fw_all_bin.bin `
  --output artifacts/firmware/analysis/Forerunner245_1370_GUPDATE/driver-leads.json
```

After generating the seeded Ghidra projects described in the firmware-tooling
README, reproduce the 3.10 function-ownership check with:

```powershell
tools/ghidra/ghidra_12.1.3_PUBLIC/support/analyzeHeadless.bat `
  artifacts/firmware/ghidra-code FR245_310_CODE `
  -process stream_01_fw_all_bin.bin -noanalysis `
  -scriptPath tools/garmin-firmware/ghidra_scripts `
  -postScript DriverLeadReport.java 3.10
```

Generate the dual-region projects used to resolve the 13.70 WBL function and
its veneer into internal flash with:

```powershell
powershell -ExecutionPolicy Bypass -File `
  tools/garmin-firmware/run_ghidra_dual_map.ps1
```

Reproduce the display-converter model check against both preserved Thumb
routines:

```powershell
python -m pip install unicorn==2.1.4
python tools/garmin-firmware/display_row_model.py --verify `
  --output artifacts/firmware/analysis/display-row-verification.json
```

Generated Ghidra projects and JSON reports remain under the ignored
`artifacts/` tree. Neither command communicates with the watch.

The generated report hashes for this run are:

- 3.10: `fbae5bab04c9e9612a577d7e71eae7411b71c332b838c384d3522da6389f0bcb`
- 13.70: `8bb948af0eb97692ef4e8025d47a691af2e1ac41969c10a70e5317f5704a9e11`

## Best next offline work

The safest useful input work is to map the five internal indices to printed
button labels through additional offline event-table analysis. No live GPIO
probe is justified. For the display, decode the recovered FLEXIO0 register,
timer, shifter, DMA, and PTE mux setup against the K28F reference manual, then
relate the now-tested 244-byte row format to those transfers. The backlight writes
should remain out of FlyOS until address `0x28` and registers `0x2e`/`0x2f` are
matched to authoritative PMIC documentation and the surrounding power sequence.
