# Forerunner 245 display FlexIO/DMA decode

## Scope

This note decodes the display transport found in the preserved non-Music 3.10
and 13.70 firmware images. The work is entirely offline. No watch device path
was opened and no bytes were sent to the watch.

The register names and field meanings come from NXP's MK28FA15 header and
FlexIO/eDMA drivers at pinned MCUXpresso SDK commit
`8a289764d763ad06e0c3a05c885644ed98b970af`:

- `devices/MK28FA15/MK28FA15.h`
- `drivers/flexio/fsl_flexio.h`
- `drivers/flexio/fsl_flexio.c`
- `drivers/edma/fsl_edma.h`

Primary source URLs:

- <https://github.com/nxp-mcuxpresso/legacy-mcux-sdk/blob/8a289764d763ad06e0c3a05c885644ed98b970af/devices/MK28FA15/MK28FA15.h>
- <https://github.com/nxp-mcuxpresso/legacy-mcux-sdk/blob/8a289764d763ad06e0c3a05c885644ed98b970af/drivers/flexio/fsl_flexio.c>
- <https://github.com/nxp-mcuxpresso/legacy-mcux-sdk/blob/8a289764d763ad06e0c3a05c885644ed98b970af/drivers/edma/fsl_edma.h>

## Cross-version result

The setup routines at `0x000bf84c` in 3.10 and `0x0000ec04` in 13.70 make
the same sequence of NXP-style `FLEXIO_SetTimerConfig` and
`FLEXIO_SetShifterConfig` calls. Their packed configuration structures decode
to **identical register values** in both releases. This is stronger than a
single-version interpretation because the code, structures, register values,
and call order all survive a large firmware reorganization.

The peripheral is `FLEXIO0` at `0x400df000`. Initialization also sets
`SIM_SCGC2[FLEXIO]` through address `0x4004802c`, software-resets FlexIO,
and initially leaves `CTRL[FLEXEN]` clear. The later transfer paths set
`CTRL[FLEXEN]` when their DMA descriptors and mode-specific configuration are
ready.

## Initial shifter configuration

| Shifter | `SHIFTCTL` | `SHIFTCFG` | Decoded behavior |
|---:|---:|---:|---|
| 0 | `0x07030202` | `0x00050000` | Transmit, controlled by timer 7, active-high output beginning at FlexIO pin 2, six-bit parallel width, no start or stop bit |
| 2 | `0x03030d02` | `0x00000020` | Transmit, timer 3, active-high output on FlexIO pin 13, low stop bit |
| 3 | `0x04030c02` | `0x00000020` | Transmit, timer 4, active-high output on FlexIO pin 12, low stop bit |
| 4 | `0x05031c02` | `0x00000021` | Transmit, timer 5, active-high output on FlexIO pin 28, low stop bit; load data on first shift |

Shifter 0 is the high-confidence pixel-data engine. The display conversion
produces six effective color bits from each logical byte, shifter 0 is set to a
six-bit parallel width, and DMA channel 29 streams the 244-byte-row staging
buffer into `SHIFTBUF[0]`. This supports the interpretation that FlexIO pins
2 through 7 are six parallel pixel-data lanes. It does not map those FlexIO
indices to specific package pins or panel connector nets.

Initialization also writes `SHIFTBUF[2] = 0x00000002`,
`SHIFTBUF[3] = 0x55555555`, and `SHIFTBUF[4] = 0xffffffff`, then clears all
eight shifter-error and timer-status flags by writing `0xff` to `SHIFTERR` and
`TIMSTAT`.

## Initial timer configuration

| Timer | `TIMCTL` | `TIMCFG` | `TIMCMP` | Key decoded fields |
|---:|---:|---:|---:|---|
| 0 | `0x00431b03` | `0x00000000` | `0x000f` | Single 16-bit, system FlexIO clock, always enabled, output on FlexIO pin 27 |
| 1 | `0x0bc31103` | `0x03070600` | `0x0556` | Single 16-bit, internal timer-2 trigger active low, output on pin 17, reset on both trigger edges, enable on trigger rising edge |
| 2 | `0x03430e03` | `0x00100600` | `0x00f3` | Single 16-bit, internal timer-0 trigger, decrement on trigger edges, output on pin 14, enable on trigger rising edge |
| 3 | `0x0b401b01` | `0x00272700` | `0x1f01` | Dual 8-bit baud/bit, internal timer-2 trigger, pin 27 input, decrement/shift from pin input, reset and enable on both trigger edges |
| 4 | `0x1a401b83` | `0x00202500` | `0x00f3` | Single 16-bit, internal FlexIO pin-13 trigger, pin 27 active-low input, decrement/shift from pin input |
| 5 | `0x03400e01` | `0x00102400` | `0x3f79` | Dual 8-bit baud/bit, internal timer-0 trigger, pin 14 input, decrement on trigger edges, enable on pin rising edge |
| 6 | `0x38400d03` | `0x00000300` | `0x000f` | Single 16-bit, internal FlexIO pin-28 trigger, pin 13 input, enable while trigger and pin are high |
| 7 | `0x1b401f01` | `0x00002600` | `0x070f` | Dual 8-bit baud/bit, internal timer-6 trigger, pin 31 input, enable on trigger rising edge |

Here “system FlexIO clock” means the module clock selected by
`SIM_SOPT2[FLEXIOSRC]`, following NXP's `TIMDEC=0` definition. The static
display-local code proves the FlexIO clock gate and timer divider values, but
does not yet prove the selected source or its frequency. Therefore no pixel
clock in hertz is claimed.

The transfer kickoff path resets the module and replaces timer 2 with
`TIMCTL=0x00430e03`, `TIMCFG=0x00000000`, and `TIMCMP=0x0f90` before enabling
the timer-2 interrupt. Other states in the display state machine replace
additional timers and shifters. The table above is an initialization snapshot,
not a complete safe panel-power or refresh recipe.

## DMA configuration

The two display DMA paths use eDMA base `0x40008000` and DMAMUX base
`0x40021000`:

| eDMA channel | DMAMUX source | FlexIO destination | Observed payload |
|---:|---:|---|---|
| 29 | group-1 source 1, `FLEXIO0 channel 0` | `SHIFTBUF[0]` at `0x400df200` | 32-bit memory-to-peripheral transfers, 4 bytes per request, from the 244-byte-row display staging buffer |
| 30 | group-1 source 7, `FLEXIO0 channel 6` | `SHIFTBUF[6]` at `0x400df218` | 32-bit memory-to-peripheral transfers, 4 bytes per request, from a generated control/bit-mask buffer |

The firmware enables both request sources with `SHIFTSDEN |= 0x41`. In the
mode that uses channel 30, shifter 6 is configured as a serial transmitter on
FlexIO pin 14, controlled by timer 2. This establishes two coordinated DMA-fed
FlexIO streams: a six-lane pixel stream and a control stream. It still does not
identify the panel protocol or row/column signal names.

## GPIO control sequence

The transfer kickoff routine directly controls GPIOE through
`GPIOE_BASE=0x400ff100`:

1. write `0x400` to `GPIOE_PSOR`, driving PTE10 high;
2. wait 21 scheduler/timer units;
3. write `0x200` to `GPIOE_PSOR`, driving PTE9 high;
4. wait until at least 40 units have elapsed while preparing the transfer;
5. set `FLEXIO_CTRL[FLEXEN]`;
6. wait 42 units;
7. write `0x200` to `GPIOE_PCOR`, driving PTE9 low.

These levels and delays are confirmed instruction behavior. PTE9 is a
high-going pulse around transfer start. The electrical meaning of PTE9 and
PTE10, the scheduler time unit, and the required power/reset ordering remain
unknown, so this sequence is not ready to execute on hardware.

## Reproduction

Decode the two preserved images:

```powershell
python tools/garmin-firmware/display_flexio_config.py `
  artifacts/firmware/analysis/Forerunner245_310/stream_01_fw_all_bin.bin `
  --version 3.10 `
  --output artifacts/firmware/analysis/display-flexio-310.json

python tools/garmin-firmware/display_flexio_config.py `
  artifacts/firmware/analysis/Forerunner245_1370_GUPDATE/stream_01_fw_all_bin.bin `
  --version 13.70 `
  --output artifacts/firmware/analysis/display-flexio-1370.json
```

The script rejects any input whose SHA-256 does not match its selected known
image. Current report hashes are:

- 3.10 JSON: `837da05e589d31bae99eeedac57cb89f8789e089dd5c2be31f9f10d495910eda`
- 13.70 JSON: `e66e854355778f6ca1c8b5a2b845cc981a2c91cc5a4426ecd78ab460d83de977`

Supporting Ghidra report hashes are:

- `decompile-display-lowlevel-310.txt`: `8b2e416cfc57512d4c7d0be28d142384694b4de0874ad018222aed8ead1bd1ef`
- `decompile-display-lowlevel-1370.txt`: `54f642c39aeca7797bbe957525caeb970e6b5c7754edc5531b093e19f16e6d4d`
- `decompile-flexio-hal-1370.txt`: `276314d8283510384f1b9d9dbf2ba73e63e22ea5dabe71cdb526f9d03827b238`
- `decompile-edma-hal-1370.txt`: `fbfdd551c99a8efb5defdb0af5b6481f6594583c47a8c658bd2682781290d0a2`

## Remaining blockers

The static decode does not establish:

- `SIM_SOPT2[FLEXIOSRC]` and the resulting FlexIO clock frequency;
- the mapping from FlexIO pin indices to the configured PTE package pins;
- panel connector net names, active voltage levels, and signal direction;
- the external panel/controller part number and command protocol;
- the meaning and unit of the 21/40/42 waits;
- display rail enable, reset, and safe shutdown ordering;
- whether the state machine's other configuration modes are required for every
  frame or only attachment/recovery cases.

Until those points are resolved, copying these register values into FlyOS
would be a static experiment only and would not be safe to run on the watch.
