# Forerunner 245 boot and update chain

## Evidence standard

This document labels direct observations as **confirmed**, conclusions supported
by several observations as **strongly inferred**, and hypotheses without enough
device-specific evidence as **unknown/speculative**. The custom-execution claim
below rests on a live visual result from a hash-pinned changed-instruction
package, not on file-format checksums alone.

## Current model

```text
NXP K28F mask ROM
    |
    v
Garmin-owned first-stage/bootloader region below application address 0x3000
    +--> normal boot: main GarminOS application
    |                 (GCD record 0x02bd, vector table based at 0x3000)
    |
    `--> update path, strongly inferred: temporary helper
                         (GCD record 0x0505, SRAM_L vector table at 0x1ffc0000)
                         reads staged type 0x0e and writes compound type 0xaf
                         0xaf = internal app 0x3000..0x1fffff
                                + external 0x68617000..0x68916fff
    |
    +--> GPS/CPE firmware       part 006-B3107-08
    +--> sensor-hub firmware    part 006-B3078-00
    +--> ANT/BLE firmware       part 006-B3204-00
```

### Mask ROM

The main MCU identified in the hardware research is NXP's K28F. NXP documents a
32 KiB ROM with a built-in bootloader and Arm SWJ-DP debug support in the
[K28F datasheet](https://www.nxp.com/docs/en/data-sheet/K28P210M150SF5.pdf).
This is a **confirmed silicon capability**. The Garmin board's ROM-boot entry
straps, exposed interfaces, security configuration, and debug-lock state are
unknown.

### Garmin bootloader region

The extracted main application has an absolute reset vector of `0x31f1` and
valid code at `0x31f0` when loaded at `0x3000`. The update package contains no
`0x0008 boot.bin` record and no bytes for addresses below `0x3000` in the main
stream. A resident Garmin stage below `0x3000` that validates/selects the
application is therefore **strongly inferred**. Its exact size and behavior are
unknown. [Anvil Secure independently inferred a missing loader below `0x3000`](https://www.anvilsecure.com/blog/compromising-garmins-sport-watches-a-deep-dive-into-garminos-and-its-monkeyc-virtual-machine.html)
from a 245 Music beta image.

### GarminOS application

Arm Cortex-M vector tables, valid Thumb reset code, Kinetis source-path strings,
and normal source paths such as `HWM/core/garminos` make the architecture
**confirmed** for the acquired images. The application contains:

- `0:/Garmin/GUPDATE.GCD` and `GUPDATE.GCD` strings;
- `HWM/k28/hwm_system_update.c` in 13.70;
- `HWM/core/garminos/service/software-update/hwm_update.c`;
- USB-manager, Kinetis RTC, DMA, I2C, ADC, and Bluetooth-host source paths;
- user-facing update state and error strings.

These establish that update orchestration runs within the main GarminOS image.
They do not expose the resident loader's acceptance policy.

The 3.10 installer state machine and the equivalent 13.70 static region table
map GCD record `0x02bd` (internal type `0x0e`) to Garmin logical region
`0x68118000`, capacity `0x4ff000`. GCD record `0x03c1` (type `0x05`) maps to
`0x68103000`, capacity `0x15000`. GarminOS streams records through registered
backend functions after additive checks on the ordinary full-image path. Its
traced SHA-1 comparison is gated by the separate `GDELTA01` delta path. Static
tracing identifies that backend as the K28 QuadSPI controller and the logical
addresses as its `0x68000000` AHB flash window. The resident loader's boot
validation remains unknown.

### Staging and restart handoff

The 3.10 and 13.70 application images register the same region backend, anchored
by `HWM\region\hwm_rgn_ufs.c: 40`. It accesses K28 `QuadSPI0_BASE` at
`0x400da000`; NXP defines its external-flash AHB window at `0x68000000`.
Therefore type `0x0e` is **confirmed** to occupy external QuadSPI flash at
`0x68118000..0x68616fff`.

The application-side order is **confirmed**:

```text
validate GCD structure/checksums
    -> erase type 0x0e region (blank-aware 4 KiB/64 KiB operations)
    -> program sequential payload bytes (256-byte page boundaries)
    -> finish/ready check
    -> preserve success or program failure bit at 0x68615000
    -> request restart
```

The failure bit is stored at type-`0x0e` offset `0x4fd000`. The software maps
an erased physical byte (`0xff`) to logical zero; marking failure clears the
corresponding flash bit, so the marker can be changed without another erase.
The same offset and failure-marker helper are present in both versions.

The staged `fw_all` payload combines bytes destined for internal application
address `0x3000` and the segment mapped at `0x04600000`. The GCD also contains
a separate native `0x0505` helper that runs from K28 SRAM_L
(`SRAM_L_BASE = 0x1ffc0000`). Its 3.10 loop reads staged type `0x0e` and writes a
compound destination type `0xaf`; both versions expose the same `0x05` and
`0x0e` QuadSPI region map. This makes a transient copy stage **confirmed**.

The `0xaf` composition is now **confirmed** in both helpers. Child `0xab`
maps compound offsets `0..0x1fcfff` to K28 internal flash
`0x00003000..0x001fffff`; child `0xac` maps the next `0x300000` bytes to
external QuadSPI `0x68617000..0x68916fff`. The helper erases child `0xab`
first, then `0xac`, copies monotonically in chunks up to `0x1e000`, and
checksums the destination. A separate type `0x2b` exposes internal
`0x00000000..0x00002fff`, but it is not a child of `0xaf`. The observed normal
main-image copy therefore replaces the application and its external executable
region without overwriting the resident prefix below `0x3000`.

After a successful copy and destination checksum, the recovered helper path
calls the application reset-vector pointer at `0x00003004`. The helper therefore
hands control directly to the newly written application. Authentication before
the resident stage launches this RAM helper remains unobserved.

The omitted code below `0x3000` must still decide whether and how to install
and transfer control to that helper. Its exact copy order, authentication
checks, failure recovery, rollback behavior, and behavior on an interrupted
helper install remain **unknown**. A malformed or interrupted `0xaf` copy can
erase or partially program the entire application while leaving the resident
prefix intact; whether that prefix can recover such a failure is unproven.
This does not prove that arbitrary data is accepted.

### Secondary processors

The backed-up `GarminDevice.xml` and Garmin's current update catalog describe
the GPS/CPE, sensor hub, and ANT/BLE components as independently updateable.
Their packages use GCD record `0x0401`, often across multiple descriptor-defined
streams. Some GPS streams have entropy near eight bits per byte, so their
encoding requires separate analysis. The main MCU cannot be assumed to execute
these streams.

## Update integrity versus boot authentication

All acquired GCD files use byte-valued checkpoint records that make each prefix
sum zero modulo 256. This is an unkeyed checksum. The 3.10 application installer
also checks a selected non-delta full-image payload by requiring its additive
sum's low byte to be zero before calling the normal writer. Its 20-byte SHA-1
comparison is gated by `GDELTA01` and belongs to delta handling. These observed
integrity checks can detect damage but do not, by themselves, authenticate an
update.

The unresolved question is whether an indirect installer backend or Garmin's
resident loader performs a separate keyed or public-key check. The visible
signature-failure text belongs to the Connect IQ subsystem and cannot be
attributed to system-image verification.

No acquired GCD descriptor exposes a recognized RSA/ECDSA signature record.
This narrows where authentication could reside but does not establish that
updates are unsigned.

## Native code execution evidence

The exact synthetic-13.72 package, SHA-256
`6394fd73cc3e7a5660a6fe9cde3cc0b6617c21f8a24f2b6319b328882d662713`,
was installed through the normal update path. After restart, the user reported
that the entire display showed the new full-screen FlyOS face with `FLY LIVES`
and its fly specimen. The package replaces the official call at `0x00009a20`
with a branch to a 974-byte custom Thumb body at `0x001f6000`. That body owns
all 57,600 framebuffer bytes before calling GarminOS's dirty-rectangle and
display-dispatch functions. The visible full-screen result is direct evidence
that the changed branch and custom Thumb body executed persistently after a
normal update and reboot.

This execution remains inside GarminOS. It relies on GarminOS to boot,
initialize the display, provide the framebuffer and locks, and dispatch display
updates. It does not demonstrate a replacement bootloader or standalone FlyOS
initializing the MCU and panel.

Anvil Secure demonstrated historical native code execution through a Connect IQ
memory-corruption vulnerability, published as
[CVE-2023-23300](https://github.com/anvilsecure/garmin-ciq-app-research/blob/main/advisories/CVE-2023-23300.md).
That evidence shows that vulnerable GarminOS versions could be compromised at
runtime. It does **not** demonstrate any of the following:

- acceptance of a modified GCD;
- execution before GarminOS;
- persistence across reboot;
- bypass of a loader signature check;
- exploitability of the connected watch's 10.40 build.

The live watch was not tested for the vulnerability.

## Security decision table

| Question | Evidence | Result |
|---|---|---|
| Are updates unsigned? | Both the resource proof and exact 13.72 changed-code package were accepted and booted without an exposed signature edit | **Strong evidence for the tested main full-image path; generality unknown** |
| Are updates only checksum-validated? | The 13.72 package passed after descriptor/header, hook, new Thumb body, and additive-checksum changes | **Demonstrated for the tested main-image mutation; other components unknown** |
| Are cryptographic signatures enforced? | The live device accepted and executed changed main instructions and a new code body without any signature edit | **No enforced signature covering the tested main-code ranges was observed** |
| Does secure boot exist? | K28F has security/crypto capabilities; Garmin configuration not recovered | **Unknown** |
| Is there a bootloader exploit? | No 245-specific loader exploit found | **No public evidence found** |
| Can recovery accept arbitrary images? | No 245-specific proof | **Unknown** |
| Are SWD/JTAG ports unlocked? | MCU supports them; watch routing/locks unknown | **Unknown** |
| Is an MCU ROM loader present? | NXP documents it in K28F | **Yes in silicon; accessibility unknown** |

Tools such as [garmin-flash-tool](https://github.com/naturalgeek/garmin-flash-tool)
demonstrate GUSB recovery of the MAIN region on a GPSMAP 276Cx. Its author
explicitly limits verification to that model. It is comparative protocol
evidence and provides no safe basis for sending commands to a Forerunner 245.

## Feasibility techniques

| Technique | Evidence | Risk | Reversible? | Hardware modification? | Likelihood |
|---|---|---:|---|---|---|
| Modified GCD through normal Garmin updater | Exact 13.72 installed, booted, executed a custom Thumb hook/body, and controlled the full framebuffer | High | 13.73 wrapper is available only while GarminOS/USB works; nonboot recovery unknown | No | Demonstrated for a GarminOS-resident application overlay |
| Runtime code execution on an old vulnerable GarminOS | Historical public exploit class | Medium/high | Runtime may be; persistence unknown | No | Unknown for 10.40 |
| 245 preboot/recovery protocol | No device-specific transcript or implementation | High | Unknown | No if present | Unknown |
| NXP ROM bootloader | Confirmed MCU capability | Extreme without a complete restore image | Unknown | Possibly requires opening/probing | Low/unknown |
| SWD/JTAG | Confirmed MCU capability | High | Depends on protection and complete backup | Likely requires opening/probing | Unknown |
| New bootloader vulnerability | No candidate identified | High | Unknown | No/unknown | Unknown |

## Verdict

**YELLOW - persistent custom Thumb execution and full-frame control are
demonstrated, but standalone FlyOS and nonboot recovery remain unproven.**

The exact 13.72 live proof crossed the normal update, boot, and changed-code
execution boundaries. The user observed the intended full-screen `FLY LIVES`
and fly output generated by the new Thumb body. This establishes a persistent
custom-code foothold in the GarminOS application. It does not establish
unrestricted arbitrary-image acceptance, replacement of the resident loader,
standalone hardware initialization, secure-boot state for other components, or
recovery from a nonbooting application.

GREEN still requires a Forerunner 245-specific recovery path shown to restore
an official image when the normal GarminOS/USB path is unavailable, plus the
independent clock, memory, panel, and input initialization needed for a
standalone FlyOS boot.

## Safest continuation

The bounded Ghidra pass has now confirmed that the 3.10 application opens
`GUPDATE.GCD`, parses structured descriptor records, maps IDs `0x02bd` and
`0x03c1`, and checks device-family identifier `0x0c04`. It did not reveal a
proved cryptographic-verifier call in that application-side orchestration
slice.

Read-only inspection after the live 13.72 result found USB status OK, a healthy
volume, the expected model/part, software version 1370, and neither
`GUPDATE.GCD` nor `force.tmp`. The safest immediate continuation is to press
each physical key while observing the five on-screen input markers. The exact
13.73 recovery wrapper restores official 13.70 code/resources behind higher
admission metadata, but it has not been installed and only helps while GarminOS
and its USB updater still run. No nonboot recovery path is known.

## Live full-screen custom Thumb proof (2026-09-14)

The installed file was the 5,120,675-byte synthetic-13.72 package with SHA-256
`6394fd73cc3e7a5660a6fe9cde3cc0b6617c21f8a24f2b6319b328882d662713`.
The user reported that the whole screen showed `FLY LIVES` and the fly after
installation. This matches the unique output of the package's custom 974-byte
Thumb renderer and demonstrates full-frame framebuffer control through the
normal Garmin update and boot chain.

Post-install USB verification succeeded: the reconnected device reports OK,
the volume is healthy, model/part is Forerunner 245 `006-B3076-00`, software
version is 1370, and both `GUPDATE.GCD` and `force.tmp` are absent. Physical
button-marker behavior has not yet been observed. The prepared 13.73
official-code recovery wrapper has SHA-256
`869d62ab829ac7b75a079effd4d7d0b1e71a5e8a0d1c7d2c94fa686d907aa4e6`.
It remains uninstalled and cannot recover an application failure that prevents
GarminOS or normal USB from starting.

## Live matched-13.69 resource proof (2026-09-14)

The approved 5,120,675-byte candidate was staged as `GUPDATE.GCD`; the guarded
host-side readback matched SHA-256
`d89d52ca82586d7cea003c2f5b65b854790b572246164064fe3df079fa36ca2f`.
Windows then safely ejected the volume. After physical disconnection, the watch
offered the update, the user selected **Install now**, and subsequently reported
seeing `FLY LIVES 2ALIVE` before reconnecting the cable.

Read-only inspection after reconnection found a healthy HWID-3076 volume,
`GarminDevice.xml` software version 1370, and neither `GUPDATE.GCD` nor
`force.tmp`. This confirms normal USB mass-storage service and consumption of
the staged file. It also falsifies the restoration assumption that changing
the two identified 1370 fields to 1369 would make official 13.70 a normal
forward update: the device's public current-version source remains 1370, so
official 13.70 is a same-version package under the recovered application-side
selection rule.

This is direct evidence that this checksum-repaired, matched-version resource
mutation was accepted by the normal device update path and that the resulting
application booted far enough to resolve and render the changed About-page
resource. It falsifies the earlier working hypothesis that every change to the
tested descriptor/header/resource bytes must fail an immutable manufacturer
signature check. It does not establish that every GCD is unsigned or that code
bytes, helper bytes, other components, or the resident prefix can be changed.
It also does not prove official 13.70 same-version restoration, executable
overlay behavior, arbitrary code execution, or recovery after a failed
application update.

## Offline neural package pair (2026-09-14)

The exact neural target was wrapped locally as coherent synthetic versions
13.73 and 13.74. The candidate and restore are each 5,120,675 bytes with
SHA-256 values
`4ec78eabd23a880ad5d4e9ff52e688e62397480a32070316b2748b70b771c9d7`
and
`4d47edfcaeb3585bd026ac89c8cc9fbeaa9168032d9569aa3885bfdb4880ffa4`,
respectively. Exact reconstruction, record-layout, stream-length, HWID 3076,
helper equality, additive, checkpoint, and full-image checks pass offline.

The candidate changes the decoded header version, the hook at `0x00009a20`,
the complete approved allocation envelopes `0x001f6000..0x001f63ff` and
`0x001fa400..0x001fabff`, and enumerated additive/checkpoint bytes. The restore
reconstructs official 13.70 hook/code/resource bytes throughout both
allocations and elsewhere, apart from its coherent 13.74 header/descriptor and
enumerated additive/checkpoint repairs. It is not a byte-identical official
package.

The recovered helper erases internal `0x00003000..0x001fffff` and external
QSPI `0x68617000..0x68916fff`. The decoded main programs the external portion
only through `0x688f1fff`; `0x688f2000..0x68916fff` remains erased. The package
decision retains `packaging_allowed:false` and `live_staging_allowed:false`.
No nonboot recovery is known, and feasibility remains **YELLOW**.

## Offline Neural Specimen N64 wrappers (2026-09-15)

The next monotonic wrapper after the live-proven synthetic 13.73 overlay is the
offline-only synthetic 13.74 N64 candidate. Its official-code recovery wrapper
is synthetic 13.75. The candidate and restore SHA-256 values are respectively
`3a4a4af6355c132571c1158667cc43c96bf5da7a67737ab028267930e71134cd`
and `ccd2a29c51a41a436111239c7181e1cb0cea1f2fac1c48d600fff6dec103e5da`.

Both retain the official 0x0505 helper byte-for-byte and the official GCD
record layout. The candidate changes only coherent version metadata, the
4-byte display hook, the two audited payload envelopes, the reserved primary
additive byte, the final main additive byte, and affected outer checkpoint.
The restore returns the hook and complete primary/secondary envelopes to
official 13.70 content; only coherent 13.75 metadata and its named additive and
checkpoint repairs differ from official.

These results prove reproducible package construction and the known visible
integrity checks. They do not prove resident-loader acceptance, secure-boot
bypass, standalone FlyOS boot, or recovery when GarminOS/USB cannot enumerate.
The live staging tool explicitly blocks both artifacts pending a separate exact
approval.
