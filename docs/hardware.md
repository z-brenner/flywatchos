# Garmin Forerunner 245 Hardware Assessment

This document records public evidence for the Forerunner 245 family. It does not replace
an inventory of the connected watch. Component-level teardowns exist for both a
**Forerunner 245** and a **Forerunner 245 Music**; later board revisions may differ.

## Confidence labels

- **Confirmed**: stated by Garmin/NXP or visibly identified on a documented 245-family board.
- **Strongly inferred**: supported by multiple compatible observations, but not established
  for the connected unit.
- **Speculative**: plausible and useful as a research lead, but unsupported by enough
  model-specific evidence to guide hardware access or firmware writes.

## System overview

| Subsystem | Finding | Confidence and limits |
|---|---|---|
| Main MCU | NXP Kinetis `MK28FN2M0ACAU15`, Arm Cortex-M4F | **Confirmed — both non-Music and Music teardown units.** Not yet read directly from the connected watch. |
| MCU clock and memory | Up to 150 MHz; 2 MiB dual-bank program flash; 1 MiB SRAM; 32 KiB boot ROM | **Confirmed — NXP K28F specification.** Silicon capability does not prove Garmin enables every feature. |
| External RAM | Winbond `W987D6HBGX6E`, a 128-Mbit (16 MiB) low-power SDRAM part | **Confirmed — package marking on teardown board; capacity from vendor datasheet.** |
| Bulk storage | Samsung `KLM4G1FETE-B041` eMMC, nominally 4 GB | **Confirmed — 245 Music teardown.** Garmin advertises 4 GB memory for that model; accessible capacity is lower. Non-Music storage may differ. |
| Display | 240×240 round, sunlight-readable transflective memory-in-pixel panel; 64-color Connect IQ target; K28F FLEXIO0/DMA transport on a recovered PTE pin set | **Panel properties confirmed by Garmin; transport confirmed by matching 3.10/13.70 static traces.** External panel/controller identity and signal roles remain unknown. |
| Buttons | LIGHT = GPIOC11, START/STOP = GPIOD10, BACK = GPIOD1, DOWN = GPIOA20, UP = GPIOA22 | **GPIO map confirmed by matching 3.10/13.70 static traces and live marker observation on the installed overlay.** Inputs are active-low; debounce and wake behavior remain unresolved. |
| Sensor hub | Ambiq Micro Apollo2 | **Confirmed — both teardown units.** Its Garmin firmware and interprocessor protocol are unknown. |
| Motion/e-compass | STMicroelectronics `LSM303AGR` accelerometer + magnetometer on the Music board; unidentified six-axis device on the non-Music board | **Confirmed only for the photographed units.** The exact non-Music motion part remains unknown. |
| GNSS | Airoha `AG3335MN` on the non-Music board; Sony `D5603` on the Music board | **Confirmed — photographed teardown units.** This demonstrates a variant difference and does not establish every production revision. |
| ANT/Bluetooth | Cypress/Infineon `CYW20719` coprocessor | **Confirmed — both teardown units.** Host interface and firmware authentication are unknown. |
| Wi-Fi | Microchip/Atmel `ATWILC1000B-UU` | **Confirmed — Music teardown.** The non-Music model is not expected to contain Wi-Fi. |
| RF front end | Qorvo `RFFM6205` | **Confirmed — Music teardown.** |
| Power management | Maxim Integrated/ADI `MAX20303` family (`MAX20303B` marking on Music board) | **Confirmed — both teardown units.** Rail assignments, charger settings, and startup sequencing are unknown. |
| Battery | Garmin `361-00086-11` / `361-0086-11`, 3.8 V, 180 mAh | **Confirmed — both teardown units.** |
| Heart-rate assembly | Separate sensor flex using an ADI `MAX86141` optical AFE on the non-Music board | **Confirmed — non-Music teardown unit.** The exact Music-board AFE is not established by the cited source. |
| USB | Four external charging/USB contacts; K28F supports both high-speed and full-speed USB | Contacts are **confirmed** and MCU capability is **confirmed**. Which K28 controller, PHY path, pins, and Garmin protocol are used remain **unknown**. |

Garmin's Connect IQ device table describes both 245 variants as 240×240, round,
64-color MIP targets.^1 Garmin's retail specifications independently describe the panel as
a 1.2-inch, 240×240 sunlight-visible transflective MIP display and list GPS, GLONASS,
Galileo, compass, accelerometer, Bluetooth, ANT+, and Wi-Fi for the Music model.^2

The May 2022 iFixit teardown identifies the main K28F, external Winbond SDRAM, Apollo2,
eMMC, Wi-Fi device, PMIC, CYW20719 radio, Sony GNSS device, RF front end, LSM303AGR, and
battery from board markings and photographs.^3 This is the strongest public board-level
evidence found for the Music model, but it represents one unit rather than every revision.
An independent photographed teardown of a non-Music 245 identifies the same K28F, Apollo2,
MAX20303-family PMIC, and CYW20719, plus an Airoha AG3335MN GNSS receiver and MAX86141 optical
AFE.^4 It does not identify the non-Music external storage device or display controller.

## Main MCU implications

NXP documents the K28F as an Arm Cortex-M4F MCU with DSP instructions and a single-precision
FPU. It includes dual-bank internal flash, 1 MiB SRAM, an SDRAM controller, dual QuadSPI,
SDHC, high-speed and full-speed USB, RTC, GPIO, I²C, SPI, LPUART, cryptographic acceleration,
and a 32 KiB ROM containing a built-in bootloader.^5 These capabilities make a small custom
runtime technically credible once board wiring and boot authorization are known.

The following distinctions are critical:

- The presence of ROM bootloader code does **not** establish an accessible boot mode.
- Dual-bank flash does **not** establish that Garmin implements rollback or A/B recovery.
- Cryptographic accelerators do **not** establish secure boot, and their absence would not
  establish that firmware is unsigned.
- A part's debug capability does **not** establish that the board exposes it or that Garmin
  left it unlocked.

## Display and controls

Only geometry, technology, and application-visible palette are confirmed. The controller,
command set, external controller identity, individual wire roles, reset polarity, power rail,
FlexIO timing, and refresh constraints remain unknown. Static firmware analysis has now
recovered a one-byte 240×240 logical framebuffer, dirty-rectangle handling, a 244-byte-row
transfer layout, FLEXIO0/DMA transport, and twelve PTE pins; see `docs/driver-leads.md`.
These findings still require a complete safe initialization model before a target driver is built.

The five user-visible buttons are documented, and static analysis confirms that the five
internal key indices use GPIOC11, GPIOD10, GPIOD1, GPIOA20, and GPIOA22. Live observation
of the installed full-screen overlay resolves them as LIGHT, START/STOP, BACK, DOWN, and UP
respectively. All five observations agree with the active-low GPIO model. Debounce, pulls,
and wake behavior remain unresolved. The standalone FlyOS target driver remains
`UNIMPLEMENTED` because it must configure clocks, ports, wake, and interrupt handling
without relying on GarminOS.

## Sensor and radio partitioning

The board uses multiple programmable devices. A minimal custom OS cannot assume the K28F
directly owns every sensor:

```text
K28F main MCU
 ├─ Apollo2 sensor hub → motion and low-power sampling (protocol unknown)
 ├─ CYW20719 → ANT/Bluetooth (transport and image format unknown)
 ├─ GNSS coprocessor → position/time (transport unknown)
 ├─ ATWILC1000B → Wi-Fi on Music model (transport unknown)
 ├─ eMMC/SDRAM → bulk storage and working memory
 └─ display/PMIC/buttons → partial pin maps recovered; sequencing unresolved
```

This partitioning implies that replacing GarminOS alone may still require compatible Garmin
firmware on the radio and sensor-hub devices, plus reconstruction of their private host
protocols.

## Debug interfaces

NXP specifies Serial Wire Debug/JTAG, trace, and multiple UARTs on the K28F.^5 The public
teardown shows test pads, but does not establish their nets. Debug accessibility, security
state, mass-erase behavior, and whether opening the watch can preserve water resistance are
all unknown. Accordingly:

| Claim | Status |
|---|---|
| The MCU implements SWD/JTAG | **Confirmed** |
| Candidate pads exist on the PCB | **Strongly inferred** from photographs |
| A candidate pad is SWDIO/SWCLK/UART | **Speculative** until traced |
| Debug access is unlocked | **Unknown** |
| Debug access can dump flash without erase | **Unknown** |

No physical probing, disassembly, glitching, or debug attachment is part of the current
investigation.

## Hardware gaps that block a target build

1. Exact board/model revision of the connected unit.
2. External display controller, FLEXIO timing/signal assignment, power, and exact transfer format.
3. Button index-to-label mapping, active levels, pulls, and wake behavior.
4. Clock-tree and watchdog configuration needed before C runtime startup.
5. PMIC rail map and safe sequencing.
6. eMMC and SDRAM pin/configuration values.
7. Interprocessor protocols for the sensor hub, GNSS, and radio.
8. Debug pad routing and lock state.

## Sources

1. Garmin Developers, “[Compatible Devices](https://developer.garmin.com/connect-iq/compatible-devices/),” Forerunner 245 and 245 Music entries.
2. Garmin, “[Forerunner 245 Music specifications](https://ph.garmin.com/products/wearables/forerunner-245-music-black-lava/).”
3. Kyle Westhaus, “[Garmin Forerunner 245 Music Teardown](https://www.ifixit.com/Teardown/Garmin+Forerunner+245+Music+Teardown/150396),” iFixit, May 25, 2022.
4. 52audio, “[Garmin Forerunner 245 teardown](https://www.52audio.com/archives/198399.html),” photographed non-Music board and component markings, 2024 (Chinese).
5. NXP Semiconductors, “[Kinetis K28F MCU Sub-Family Data Sheet](https://www.nxp.com/docs/en/data-sheet/K28P210M150SF5.pdf),” Rev. 4, March 2017.
6. Ambiq Micro, “[Apollo2 SoC Datasheet](https://ambiq.com/wp-content/uploads/2020/10/Apollo2-MCU-Datasheet.pdf),” v1.3.
7. STMicroelectronics, “[LSM303AGR product page](https://www.st.com/en/mems-and-sensors/lsm303agr.html).”
8. FCC, “[IPH-03568 internal photographs](https://fccid.io/IPH-03568/Internal-Photos/Internal-Photos-4215004),” Garmin model 03568.
