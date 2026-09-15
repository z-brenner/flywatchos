# FR245 13.70 read-only button overlay input

## Result

The running GarminOS image already configures and owns all five button pins.
An in-app overlay can observe them without touching GPIO direction, output,
pull, mux, edge, interrupt, or clock registers.  The sampler needs three
volatile reads of `GPIOx_PDIR` and no peripheral writes.

| Internal key | Encoded pin | PDIR address | Mask | Physical label | Confidence |
|---:|---:|---:|---:|---|---|
| 0 | `0x14b` | `GPIOC_PDIR = 0x400ff090` | `0x00000800` | LIGHT/power | Strongly inferred |
| 1 | `0x06a` | `GPIOD_PDIR = 0x400ff0d0` | `0x00000400` | unresolved | Confirmed pin only |
| 2 | `0x061` | `GPIOD_PDIR = 0x400ff0d0` | `0x00000002` | unresolved | Confirmed pin only |
| 3 | `0x014` | `GPIOA_PDIR = 0x400ff010` | `0x00100000` | unresolved | Confirmed pin only |
| 4 | `0x016` | `GPIOA_PDIR = 0x400ff010` | `0x00400000` | unresolved | Confirmed pin only |

The table is at runtime `0x0000f9bc` in the pinned 13.70 main image.  Its five
rows are `(0x14b,5)`, `(0x06a,5)`, `(0x061,5)`, `(0x014,5)`, and
`(0x016,5)`.  The same pins occur at `0x000b8e5c` in 3.10; only key zero lacks
the later `0x100` behavior flag.  That cross-version match rules out a chance
five-row data interpretation.

## Address and polarity evidence

The interrupt handler at `0x0000f688` decodes bits 5 through 7 of the encoded
word as the GPIO port and its low five bits as the pin.  It reads offset
`0x10` from `0x400ff000 + port * 0x40`, exactly the K28F `GPIOx_PDIR`
register layout.  This yields:

```text
GPIOA_PDIR = 0x400ff010
GPIOC_PDIR = 0x400ff090
GPIOD_PDIR = 0x400ff0d0
```

The registration routine at `0x0000f928` starts each key in Garmin's internal
mode 5.  `0x00017dd4` maps mode 5 to K28 `PORTx_PCRn.IRQC = 8` and mode 4 to
`IRQC = 12`.  NXP defines these values as interrupt on logic zero and
interrupt on logic one.  The handler reads PDIR and alternates modes 5 and 4,
allowing it to observe both levels while it schedules deferred debounce work.

This is strong evidence that button assertion is active-low: Garmin initially
waits for logic zero and subsequently switches to logic one.  Calling zero a
physical *press* still assumes ordinary startup with the controls released;
no live electrical trace was captured.  The overlay should therefore expose
the raw five-bit active-low state first and use it to map indices 1 through 4
empirically.

NXP's API documentation names the two interrupt modes:
<https://mcuxpresso.nxp.com/api_doc/dev/271/group__port.html>.

## Safe sampler

Snapshot each port once so keys sharing a port come from the same read:

```c
static uint32_t fr245_buttons_read(void) {
    uint32_t a = *(volatile const uint32_t *)0x400ff010u;
    uint32_t c = *(volatile const uint32_t *)0x400ff090u;
    uint32_t d = *(volatile const uint32_t *)0x400ff0d0u;

    return (((c & 0x00000800u) == 0u) << 0) |
           (((d & 0x00000400u) == 0u) << 1) |
           (((d & 0x00000002u) == 0u) << 2) |
           (((a & 0x00100000u) == 0u) << 3) |
           (((a & 0x00400000u) == 0u) << 4);
}
```

These PDIR accesses are side-effect-free register reads.  They do not clear
interrupt flags; `PORTx_ISFR` would do that only when written.  They also do
not call Garmin's key manager or disturb its debounce state.  This is suitable
inside the confirmed display hook after `startup_complete == 1`, when GarminOS
has initialized the GPIOs.  The framebuffer and normal dirty-rectangle call
remain the overlay's only output path.

## Compact indicator

Reserve a bottom status rail, for example `y = 218..237`.  Draw five outlined
12-by-12 cells centered at `x = 48, 84, 120, 156, 192`.  Fill a cell black
while its raw key bit is asserted; leave it white with a one-pixel black border
when released.  Label the cells `0 1 2 3 4`, or `L 1 2 3 4`, until an observed
press maps the remaining physical labels.  This is readable on a 240-pixel MIP
display and costs only one five-bit sample per frame.

The display hook runs on redraws rather than on a fixed timer.  Holding a key
or GarminOS reacting to it causes redraws, but the indicator is diagnostic and
must not be presented as a complete input event loop.  A later standalone
FlyOS driver will need explicit debounce and wake handling.

## Offline verification

`tools/garmin-firmware/fr245_button_input.py` contains the address table and a
host-only snapshot decoder.  Its unit tests cover released, each individual
assertion, combined assertions, and exactly one read of each PDIR word.

For Unicorn validation of a compiled overlay, map page `0x400ff000`, seed the
three PDIR words with `0xffffffff`, then clear a button mask to assert it.  A
`UC_HOOK_MEM_READ` assertion should accept only the three addresses above, and
a `UC_HOOK_MEM_WRITE` assertion should fail any write in
`0x400ff000..0x400fffff`.  This proves the compiled payload follows the
read-only design; it does not emulate board electricity, switch bounce, or
GarminOS scheduling.

The full-screen overlay now implements this sampler.  Its 974-byte
`overlay.bin` has SHA-256
`358d71190321f7dd9d51de8ac3c913e370b0fc23a25e7541d072d2ac83941ffb`.
Instruction-level tests recorded, in order, exactly one 32-bit read from
`GPIOA_PDIR`, `GPIOC_PDIR`, and `GPIOD_PDIR`, and zero writes anywhere in the
K28 GPIO page.  With each of the five masks independently pulled low, only
that key's 12-by-12 marker at `y = 214..225` changed.  With the display startup
guard false, the payload performed no GPIO read and no framebuffer draw.

Reproduce these checks with:

```text
python -m unittest tools.garmin-firmware.tests.test_fr245_button_input -v
python -m unittest tools.garmin-firmware.tests.test_emulate_fullscreen_overlay_payload -v
powershell -NoProfile -ExecutionPolicy Bypass -File flyos/target/fr245_1370_fullscreen_overlay/test-build.ps1
```

Evidence artifacts:

- `artifacts/firmware/analysis/decompile-buttons-1370.txt`
- `artifacts/firmware/analysis/decompile-gpio-config-1370.txt`
- `docs/driver-leads.md`

## Live physical mapping (2026-09-14)

Brief presses on the installed full-screen overlay resolved every marker:

| Physical position | Marker | Garmin button name |
|---|---|---|
| Top left | `L` | LIGHT |
| Middle left | `4` | UP |
| Bottom left | `3` | DOWN |
| Top right | `1` | START/STOP |
| Bottom right | `2` | BACK |

All five observations agree with the recovered GPIO assignments and the
active-low interpretation.
