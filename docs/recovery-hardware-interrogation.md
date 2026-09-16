# Forerunner 245 HWID 3076 — Read-Only Hardware Recovery-Feasibility Interrogation

Research date: 2026-09-16
Scope: Forerunner 245 non-Music, Garmin hardware ID `3076`, MCU `MK28FN2M0ACAU15` (Kinetis K28F).
Method: offline, read-only. No watch was accessed, opened, powered into any mode, probed, or
written during this pass. This document extends, and does not repeat, the settled security
theory in [`recovery-research.md`](recovery-research.md) and [`recovery.md`](recovery.md).

## Question

Is there a **read-only, non-destructive** way to determine whether hardware-level (SWD/JTAG or
ROM-bootloader) recovery of this specific watch is even possible — before any irreversible
action — and what does the currently available evidence say the likely answer is?

## Evidence grades

| Grade | Meaning |
|---|---|
| **Confirmed silicon** | NXP documents the K28F/Kinetis part *can* do this (capability). |
| **Documented** | Reproduced verbatim from a primary reference (NXP RM/AN, OpenOCD source). |
| **Measured (ours)** | Read directly from a captured artifact in this repository, with hash. |
| **Inferred** | Reasoned from evidence; not directly proven for this watch. |
| **Unknown** | No reliable evidence establishes it for this watch. |

The governing distinction throughout: *"the K28F CAN do X"* (silicon capability) is not
*"this watch IS configured to allow X"* (per-part state, which is **Unknown** unless a byte or a
live read proves it).

---

## 1. The read-only interrogation path — can we safely learn if recovery is possible?

### 1.1 Three layers the recovery question actually contains

The prior research occasionally blurs three separate operations. They must be kept distinct,
because only the first is read-only:

| Layer | Operation | Destructive? | Blocked when secured? |
|---|---|---|---|
| **(i)** | Read the **MDM-AP status register** over SWD | **No** — pure debug-port register read | **No** — readable even when secured |
| **(ii)** | SWD/JTAG **access to flash memory** (readout / reflash) | No (read) | **Yes** — blocked if `FSEC[SEC]≠10b` |
| **(iii)** | **Mass-erase-to-unsecure** via the debug port | **Yes** — erases *all* internal flash | Available only if `FSEC[MEEN]≠10b` |

The user's "read-only recovery path" question reduces to: **does layer (i) let us learn our
fate before ever touching layer (iii)?** The answer is **yes** — layer (i) is exactly the safe
measurement that reports both the security state (ii) and whether the destructive unlock (iii)
is even available.

### 1.2 The MDM-AP status register — exact fields (Documented)

On every Kinetis part (K28F included) the SWJ-DP exposes a dedicated **MDM-AP** (Debug Module
Access Port) in addition to the standard AHB-AP. Its Status register can be read by the debug
host **even while the core is secured and held in reset**, and reading it changes no flash
state. Register offsets and bit masks below are quoted verbatim from the OpenOCD Kinetis flash
driver `kinetis.c`, which is the reference implementation that actually performs this poll:

```c
#define MDM_REG_STAT 0x00     /* MDM-AP Status register  */
#define MDM_REG_CTRL 0x04     /* MDM-AP Control register */
#define MDM_REG_ID   0xfc     /* MDM-AP IDR (identity)   */

#define MDM_STAT_FMEACK      (1<<0)   /* Flash Mass Erase Acknowledge */
#define MDM_STAT_FREADY      (1<<1)   /* Flash Ready                  */
#define MDM_STAT_SYSSEC      (1<<2)   /* System Security (1 = secured)*/
#define MDM_STAT_SYSRES      (1<<3)   /* System Reset (0 = in reset)  */
#define MDM_STAT_FMEEN       (1<<5)   /* Flash Mass Erase Enable      */
#define MDM_STAT_BACKDOOREN  (1<<6)   /* Backdoor Access Key Enable   */
#define MDM_STAT_LPEN        (1<<7)
/* ...low-power / core-halt bits at 8..18... */

#define MDM_CTRL_FMEIP       (1<<0)   /* Flash Mass Erase In Progress (destructive trigger) */
```

The K-series reference manuals present the same register as the "MDM-AP Status Register" and
place the MDM-AP status read at debug address `0x0100_0000` (AP-select form of `MDM_REG_STAT`).
OpenOCD's own comment for the pre-erase sequence — *"Read the MDM-AP status register repeatedly
and wait for stable conditions suitable for mass erase: mass erase is enabled, flash is ready,
reset is finished"* — confirms that the host **reads** `SYSSEC`, `FMEEN`, and `FREADY` **before**
it ever writes `MDM_CTRL_FMEIP`. The read is the gate; the write is the irreversible act.

### 1.3 What each possible reading would mean for recovery feasibility

A single MDM-AP status read (layer i) sorts this watch into exactly one of three outcomes,
with **zero** flash risk:

| MDM-AP status reading | Interpretation | Recovery consequence |
|---|---|---|
| **`SYSSEC=0`** (bit 2 clear) | Part is **unsecured** (`FSEC[SEC]=10b`). SWD has full bus/flash access. | **Best case.** Non-destructive SWD flash **readout and reflash are possible** — *but* a full restore still needs bytes the project does not possess (§2.3). Recovery is feasible in principle, bounded by the missing boot prefix. |
| **`SYSSEC=1, FMEEN=1`** (bit 2 set, bit 5 set) | **Secured**, but debug **mass-erase-to-unsecure is enabled** (`FSEC[MEEN]≠10b`). | Only a **destructive** unlock is available. It erases *all* internal flash — Garmin loader, calibration, identity — and no complete restore image exists (§2.3). Not a real recovery. |
| **`SYSSEC=1, FMEEN=0`** (bit 2 set, bit 5 clear) | **Secured** and debug mass erase **disabled** (`FSEC[MEEN]=10b`). | **Worst case.** No debug recovery of any kind. If the watch is bricked into this state, SWD/JTAG cannot help at all. |
| **`FREADY=0`** transiently | Flash controller not yet initialized | Not a verdict; retry the read. Still non-destructive. |
| **`BACKDOOREN=1`** (bit 6 set) | A backdoor access key is provisioned | A known 8-byte key *could* unsecure without erase — but only if the key value is known, which it is not (Unknown). |

**Crucial nuance:** even the favourable `FMEEN=1` reading only unlocks the *destructive* path.
The only genuinely non-destructive recovery outcome is `SYSSEC=0`. The MDM-AP read tells you
which of these three worlds you are in **before** you can do anything you cannot undo. That is
the precise sense in which read-only recovery-feasibility determination is possible.

### 1.4 Non-destructiveness — grade

That the MDM-AP status read is non-destructive and works while secured is **Documented /
Confirmed silicon** (NXP AN4507 "Using Kinetis Security and Flash Protection Features"; K28F RM
debug-security section; OpenOCD `kinetis.c`). What the read would *return for this watch* is
**Unknown** until the read is actually performed — which requires physical SWD access (§3).

---

## 2. Static FSEC / FOPT determination — do we already have the bytes?

### 2.1 Where the answer lives (Documented)

The Kinetis **Flash Configuration Field (FCF)** is a 16-byte block at **internal-flash offset
`0x0000_0400`–`0x0000_040F`**:

| Offset | Field | Meaning |
|---|---|---|
| `0x400`–`0x407` | Backdoor Comparison Key | 8-byte backdoor key |
| `0x408`–`0x40B` | `FPROT0..3` | flash region protection |
| `0x40C` | **`FSEC`** | `[SEC]`, `[MEEN]`, `[FSLACC]`, `[KEYEN]` — the security state |
| `0x40D` | **`FOPT`** | `[BOOTSRC_SEL]`, `[BOOTPIN_OPT]` — boot-source / ROM-entry select |
| `0x40E`–`0x40F` | `FEPROT`/`FDPROT` | EEPROM/data protection |

`FSEC[SEC]=10b` ⇒ unsecured; any other encoding ⇒ secured. `FSEC[MEEN]=10b` ⇒ debug mass erase
disabled. These are the exact bytes that would definitively answer §1's three-way question
*without any hardware at all* — **if we possessed them.**

### 2.2 Do any captured artifacts span `0x400`–`0x40F`? — No (Measured, ours)

Every captured system package decodes to exactly two firmware payloads, and **neither lands
below internal-flash `0x3000`**:

| Package (SHA-256) | Stream 0 | Stream 1 (main app) | Lowest internal-flash address shipped |
|---|---|---|---|
| `Forerunner245_1370_GUPDATE.GCD` `8ebefacf…6adc` | `0x0505` helper, 37 120 B, loads to **SRAM `0x1ffc0000`** | `0x02bd` app, reset handler **`0x000031f1`** | **`0x00003000`** |
| `Forerunner245_310.gcd` `ffc802fd…ff43` | `0x0505` helper (reset `0x1ffc01f1` = SRAM) | `0x02bd` app, reset `0x000031f1` | **`0x00003000`** |
| `Forerunner245M_310.gcd` `00cabc29…8ad0` | `0x0505` helper (SRAM) | `0x02bd` app, reset `0x000031f1` | **`0x00003000`** |

Measured mapping for the pinned 13.70 application image
`analysis/Forerunner245_1370_GUPDATE/stream_01_fw_all_bin.bin`
(SHA-256 `b45be1ba…eab6`, `tools/garmin-firmware/update_region_map.py`):
`internal_base = 0x3000`, `internal_length = 0x1FD000` ⇒ covers **`0x00003000`–`0x001FFFFF`**.
The FCF at `0x400` sits **`0x2C00` bytes below** the first byte we hold. It is not in the file.

The reset-handler value `0x000031f1` is the *application's* vector table at `0x3000`; it is **not**
the CPU's power-on vector table at `0x0`, which lives in the resident boot prefix together with
the FCF. We possess the former and not the latter.

The 13.70 region table (`update_region_map.py`) lists payload record types
`0x0d, 0x53, 0x22, 0x56, 0x5d, 0x05, 0x0e, 0x2d, 0xac` — **no `0x2b` record**. The `0x2b`
backend that addresses `0x00000000`–`0x00002fff` appears **only** as an *addressing capability*
in the SRAM helper's dispatch table (`tools/garmin-firmware/update_af_trace.py`,
`separate_internal_prefix … included_in_0xaf: false`); the package ships **no payload** for that
region. So the boot prefix — and with it the FCF/FSEC/FOPT — is neither written by a normal
update nor present in our copy of one.

### 2.3 The 20 MB raw volume is not MCU flash (Measured, ours)

`artifacts/raw-device/forerunner245-physical-disk.img` is **20 807 680 bytes**, and its boot
sector reads OEM `GARMIN`, filesystem-type label **`FAT16`**, boot signature `0x55AA`. It is the
user-visible MTP/mass-storage volume on the *external* storage medium — not the K28F internal
program-flash address space. The FCF at internal physical `0x400` is a different address space
and cannot appear in this image. (This confirms recovery.md's "user-visible filesystem backup"
characterization.)

### 2.4 Does the firmware reference FSEC/FOPT or a runtime debug-disable? — No meaningful hit (Measured, ours)

A scan of all decompilation/analysis text for `FSEC`, `FOPT`, `MDM`, `SYSSEC`, backdoor, and
flash-security tokens returns nothing substantive. The only `FTFE` references are in the
`update_af_trace` output, where the application's own flash **writer** sector-erases and programs
**app flash at `0x3000`+** — expected, and unrelated to the FCF. This is consistent with the
FCF living in the un-captured resident loader, and with the MDM-AP not being memory-mapped to
the core (so runtime firmware would not reference it).

### 2.5 Definitive statement — what it would take to obtain FSEC/FOPT read-only

The real security configuration of this watch is **Unknown** and **cannot be derived from any
byte the project currently holds.** The only read-only ways to obtain it are:

1. **Read the FCF bytes `0x400`–`0x40F` over SWD** — possible *only if* `SYSSEC=0` (§1.3 best
   case); blocked outright if secured. This requires physical SWD access (§3).
2. **Read the MDM-AP status register over SWD** (§1.2) — this does *not* return the raw FCF
   bytes, but it returns the *decoded* `SYSSEC`/`FMEEN`/`BACKDOOREN` state, which is exactly the
   decision-relevant content of `FSEC`. It works **regardless** of security state. Also requires
   physical SWD access (§3).
3. **Obtain a legitimate copy of the resident boot-prefix image** (`0x0`–`0x2fff`) from a Garmin
   service/firmware artifact — none has been found in any pass; the resident stage that loads and
   validates the `0x0505` helper remains unavailable.

There is no desk-only (bytes-we-already-have) path. Option 2 is the minimal-information,
minimal-risk option and is the technical meaning of "read-only recovery-feasibility check."

---

## 3. Pad-map evidence status

A read-only MDM-AP query (§1) still needs electrical contact with **SWDIO** and **SWCLK** (plus
ground and a sense of VDD). Whether those nets are physically reachable is a separate,
still-open prerequisite.

| Evidence source | What it shows | Pad map? |
|---|---|---|
| FCC **IPH-03568** internal photos (grant 2019-03-26; internal-photos exhibit public 2019-05-13, ~963 KB PDF; applicant Garmin International; "Low Power Digital Transmission System Transmitter 2402–2480 MHz" = the FR245 non-Music radio cert) | PCB overview; multiple **unlabeled** gold test pads | **No** — no `SWD`/`SWCLK`/`SWDIO`/reset/clock net labels, no debug header |
| iFixit "Forerunner 245 **Music** Teardown" (guide 150396) | Board-level photos, but of the **Music** variant (different board: adds eMMC/SDRAM) | **No**, and **wrong board** for HWID 3076 |
| 52audio non-Music teardown (2024-05-07) | Confirms `MK28FN2M0ACAU15` and both board sides | **No** net names, schematic, or debug transcript |

Fresh 2026 searches for an FR245 (or same-family) SWD test-pad pinout, a board-level netlist,
or a repair-forum reprogramming procedure returned **nothing**. The public record supports only:
*manufacturing/test pads exist; their signals, voltages, and accessibility are unknown.*

**Status: the pad map is NOT publicly known.** It would have to be reverse-engineered from the
physical board (continuity-tracing candidate pads to the K28F's known SWD balls). Two flags:
(a) doing so requires opening a **glued, waterproof** assembly — outside this read-only phase;
(b) **identifying** the pads is *not* the same as it being *safe* to make electrical contact —
that is a separate, later decision, and explicitly not part of this research.

---

## 4. Bottom line

**Can the project determine recovery-feasibility read-only?** **Partially — and not from the
desk.** A single, genuinely non-destructive measurement exists and is well specified: read the
**MDM-AP status register** over SWD and inspect `SYSSEC` (bit 2), `FMEEN` (bit 5), `BACKDOOREN`
(bit 6). That read reports our exact fate — unsecured / secured-but-erasable /
secured-and-locked — **before** any irreversible action, and it works even when the part is
secured. So the *method* to learn feasibility safely is confirmed. **However**, it is not
achievable from captured data alone: it needs physical electrical contact with SWDIO/SWCLK,
whose location on this board is unknown and reachable only by opening a glued case — steps that
lie outside read-only-from-data and outside this phase.

**Is the real FSEC/FOPT obtainable from captured data?** **No.** Definitively not. Every captured
package ships only the SRAM `0x0505` helper and the `0x02bd` application based at `0x3000`; the
FCF at `0x400` lives in the resident boot prefix `0x0`–`0x2fff`, which the project has never
acquired and which normal updates never write. The 20 MB image is a FAT16 user volume, not MCU
flash. The bytes simply are not in our possession, and no offline analysis can conjure them.

**Pad-map status:** **Unknown / not public.** FCC IPH-03568 and both teardowns show only
unlabeled test pads; the Music teardown is the wrong board. A pad map would require board-level
reverse engineering.

**Honest verdict on whether hardware recovery is likely possible:** **Unknowable without
probing.** The K28F *can* be recovered over SWD **only** in the `SYSSEC=0` case, and even then a
*complete* restore is bounded by the missing `0x0`–`0x2fff` boot prefix (no full restore image
exists). The circumstantial evidence — Garmin ships no user recovery path, no documented preboot
loader, no debug header, and a locked-down consumer-wearable production posture is
industry-typical — **leans toward the part being secured**, quite possibly with mass-erase
disabled (`FMEEN=0`), which would make even destructive recovery unavailable. That lean is
**Inferred, not Confirmed**; it must not be stated as fact. Fail-closed reading: **assume
recovery is unavailable until an MDM-AP read proves otherwise.**

**Smallest safe next step (option, not a recommendation):** the minimal-risk, maximal-information
action that *could* collapse the unknown is a **single read-only MDM-AP status-register query**
over SWD (layer i only — no `MDM_CTRL_FMEIP` write, no flash access). Its two hard prerequisites
are (1) reverse-engineering the SWDIO/SWCLK pad locations and (2) a decision to open the case and
make electrical contact — both of which are **physical actions outside this research's read-only
scope and are not undertaken or recommended here.** This document only establishes that such a
read *is* the correct safe measurement and *what each outcome would mean.*

---

## Sources

- OpenOCD, `src/flash/nor/kinetis.c` (MDM-AP register offsets and `MDM_STAT_*`/`MDM_CTRL_*` bit
  masks; pre-mass-erase status-poll sequence). https://openocd.org/doc-release/doxygen/kinetis_8c_source.html
- NXP/Freescale, *Using Kinetis Security and Flash Protection Features*, AN4507 Rev. 1
  (MDM-AP status/control, `FSEC[SEC]`/`FSEC[MEEN]` mass-erase gating, secured-state debug block).
  https://www.nxp.com/docs/en/application-note/AN4507.pdf
- NXP, *Kinetis K28F MCU Sub-Family Reference Manual*, Rev. 4, 2017-08 (Flash Configuration
  Field at `0x400`–`0x40F`; `FSEC`/`FOPT` definitions; MDM-AP status register; ROM boot).
  Public mirror: https://www.ftcelectronics.jp/datasheets-b7/MK28FN2M0CAU15R.pdf
- NXP, *Kinetis K28F MCU Sub-Family Data Sheet*, Rev. 4 (K28 SWJ-DP, ROM bootloader, dual-bank
  flash). https://www.nxp.com/docs/en/data-sheet/K28P210M150SF5.pdf
- FCC ID **IPH-03568** (Garmin International; grant 2019-03-26; internal-photos exhibit public
  2019-05-13). https://fccid.io/IPH-03568
- iFixit, *Garmin Forerunner 245 **Music** Teardown* (guide 150396) — Music variant board only.
  https://www.ifixit.com/Teardown/Garmin+Forerunner+245+Music+Teardown/150396
- 52audio, *Teardown report: Garmin Forerunner 245* (non-Music), 2024-05-07.
  https://www.52audio.com/archives/198399.html
- Captured artifacts (this repo): `artifacts/firmware/manifest.json`,
  `artifacts/firmware/SHA256SUMS`,
  `artifacts/firmware/analysis/Forerunner245_1370_GUPDATE/analysis.json`,
  `artifacts/firmware/analysis/update-regions-1370.json`,
  `artifacts/firmware/analysis/update-af-1370.json`,
  `artifacts/raw-device/forerunner245-physical-disk.img` (FAT16, 20 807 680 B).
