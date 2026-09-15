# Forerunner 245 HWID 3076 Recovery and Security Research

Research date: 2026-09-13  
Scope: Forerunner 245 non-Music, Garmin hardware ID `3076`  
Method: public-source research only. The connected watch was not accessed, reset, placed in a special mode, probed, or written during this pass.

## Result

No public source found in this pass demonstrates a safe, repeatable recovery path for a
Forerunner 245 non-Music (`HWID 3076`) after its Garmin application or resident bootloader
has been replaced. Garmin documents normal USB update, restart, and user-data reset
operations. It does not document a 245 preboot firmware loader, an emergency USB restore
sequence, or bootloader repair.

The K28F MCU does contain a mask-ROM bootloader and supports conditional entry through a
`BOOTCFG0` function multiplexed with NMI. That silicon feature does not by itself provide a
recovery path on the watch: its availability is controlled by the production flash
configuration, the watch's NMI/RESET routing and enabled loader peripherals are unknown, and
MCU flash security may prevent readout.

Historical native-code execution has been demonstrated through Connect IQ vulnerabilities on
the **Forerunner 245 Music**. The public research does not establish that the same bugs are
present on non-Music firmware 10.40, does not provide a persistent bootloader bypass, and did
not include the resident bootloader in its firmware image.

These findings do not justify a live write or a claim of arbitrary persistent firmware
execution. Recovery readiness remains **unproven**.

## Evidence grades

| Grade | Meaning |
|---|---|
| Direct | Source explicitly covers Forerunner 245 non-Music or HWID 3076. |
| Family | Source covers the 245 family but may combine Music and non-Music variants. |
| Related model | Demonstrated on another Garmin device; useful only as a comparison. |
| MCU capability | NXP documents a K28F silicon feature; Garmin's board/configuration is still unknown. |
| Anecdotal | User report without a reproducible technical transcript or independent verification. |

## Garmin-documented host and restore behavior

### Normal operating USB modes

The 245 family manual exposes `USB Mode` with two choices: MTP and Garmin mode. It separately
describes `Software Update` as installing an update already downloaded through Garmin
Express. This is a normal-runtime setting, not evidence of a preboot loader.^1 Garmin's
Device Interface SDK documents USB and serial protocols for waypoints, routes, and track
logs; it does not specify a firmware-flashing protocol.^2

The official 245 software collection directs users to Garmin Express to keep device software
current.^3 The normal update flow requires enough working firmware to enumerate, receive an
update, and run the on-watch installer. Garmin's historical non-Music beta instructions are
more explicit: copy `GUPDATE.GCD` to `\GARMIN`, disconnect, approve the update on the watch,
and wait. Their downgrade procedure warns that settings are reset.^4

**Evidence grade:** Direct/family.  
**Recovery implication:** official updates are an application restore candidate only while
normal USB storage/MTP and Garmin's installer survive. They do not prove recovery from a bad
application image, damaged loader, or non-enumerating state.

### Restart, reset, and diagnostic mode

Garmin documents holding `LIGHT` for 15 seconds to turn the watch off and then holding it for
one second to start it. The manual warns that data or settings may be erased.^5 Garmin also
documents reset menu options that can restore defaults or delete activities and user data.^6
Neither operation is a firmware reflash.

Garmin forum reports show that the 245 family has a button-accessible diagnostic/test screen.
In a 2020 Forerunner 245 Music thread, a Garmin representative described holding
`LIGHT+START/STOP` for 15 seconds as the correct exit process and suggested Garmin Express;
the report involved a stuck button and never identified a loader protocol.^7 Another 2021
report remained stuck in test mode after support's reset sequence and was replaced by
Garmin.^8

**Evidence grade:** Family/anecdotal.  
**Recovery implication:** diagnostic/test mode must not be treated as a preboot firmware
loader. Public reports do not show raw USB commands, accepted image regions, or arbitrary
image execution.

### No published 245 preboot procedure found

Searches of Garmin's 245 manual, support collection, product-update pages, and Garmin forum
staff posts found no Garmin-authored procedure for:

- forcing HWID 3076 into a USB preboot/programming interface;
- restoring firmware when the watch stops enumerating normally;
- writing a MAIN region with Garmin `Updater.exe`/RGN tooling;
- restoring or replacing the resident bootloader; or
- recovering from a rejected or malformed application image.

This is an absence-of-evidence finding, bounded by the sources and search date above. It is
not proof that Garmin service tools or an undocumented loader do not exist.

## Garmin USB preboot protocol: comparative evidence only

Garmin's vendor ID and GUSB protocol are used by many Garmin products, but support and region
semantics vary by family. A current open-source `garmin-flash-tool` documents a preboot
interface at `091e:0003`, three endpoints, a 12-byte GUSB header, product query, and a
MAIN-region write sequence.^9 The repository reports a successful recovery of one
GPSMAP 276Cx (`HWID 2479`) after a bad MAIN write.

The author explicitly limits the tested profile to that GPSMAP model and warns that assuming
loader region `14` is MAIN on an unverified device can brick it. The documented D-pad-Up
entry sequence, removable-battery power cycle, image size/hash guard, and region numbers all
belong to the GPSMAP 276Cx. None is evidence for HWID 3076.

| GUSB observation | Demonstrated scope | Relevance to HWID 3076 |
|---|---|---|
| Garmin preboot USB `091e:0003` exists | GPSMAP 276Cx and older Garmin handheld families | Shows a protocol worth recognizing if independently observed; does not prove the 245 exposes it. |
| Product reply can include HWID/version | GPSMAP 276Cx tool implementation | A future read-only transcript could identify a loader, but no 245 transcript is public. |
| MAIN write uses loader region `14` | GPSMAP 276Cx | Must not be reused on a watch without model-specific proof. |
| Successful MAIN recovery while BOOT survives | One GPSMAP 276Cx | Establishes feasibility for that handheld only. |
| BOOT region deliberately excluded | Tool safety policy | Confirms that even this tool is not a bootloader-repair method. |

The generic Garmin Device Interface SDK and the preboot flasher are separate evidence. The
published data-transfer SDK does not authenticate or document the flasher's write commands.

## Forerunner 245 recovery reports

Public 245 reports are mixed and do not establish a dependable restore path:

| Date | Report | Result | Evidentiary limit |
|---|---|---|---|
| 2020-01-07 thread; successful reply posted 2021-02-15 | Watch stuck at Garmin triangle; a user reported `START+BACK` reset at boot worked, with later thank-you replies.^10 | User-data reset appears to recover some boot failures. | Anecdotal; no firmware reflash, USB transcript, version/HWID, or proof of loader recovery. Reset is destructive to personal data/settings. |
| 2021-06-02 | Boot loop immediately after update to 7.20; both suggested button-reset methods failed and the watch was returned for repair.^11 | No field recovery. | Anecdotal, but directly counters any claim that the reset sequence is reliable for update failures. |
| 2021-11-12 | Stuck diagnostic/test mode; support's reset sequence and another exit combination did not work; device returned/replaced.^8 | No field recovery. | Test mode is not shown to be a loader. |

No public report found in this pass showed HWID 3076 successfully recovered by preboot USB,
an RGN transfer, ROM bootloader, SWD/JTAG, or a complete official image restore. Garmin
replacement/repair is a service outcome, not a documented user recovery mechanism.

## Published runtime exploits

Anvil Secure published its GarminOS/Connect IQ work on 2023-04-21 (updated 2023-05-26).
The target is explicitly a **Forerunner 245 Music**.^12 The work demonstrates multiple
Connect IQ parser/VM vulnerabilities, including CVE-2023-23300, where an oversized key to
`Toybox.Cryptography.Cipher.initialize` can corrupt memory and reach native control flow.^13
Garmin told the researcher the issues were fixed in Connect IQ API 3.1.x as applicable; the
published research does not map the fix to non-Music system firmware 10.40.

Three limits are decisive for this project:

1. The demonstrated hardware/firmware target is the Music variant, not HWID 3076.
2. The extracted update image begins at `0x3000`; the researcher states the likely
   `0x0000`-`0x2fff` bootloader region is absent.^12 The work therefore did not establish a
   bootloader vulnerability or update-signature bypass.
3. The RSA discussion in the article concerns Connect IQ `.PRG` application signatures.
   Developer-signed app acceptance must not be generalized to Garmin `.GCD` firmware
   authentication.

Atredis' earlier native-code demonstrations target a Forerunner 235, another model and
firmware generation.^14 They are useful background for GarminOS attack surfaces, not a 245
non-Music exploit.

**Finding:** there is public evidence that historical GarminOS runtime vulnerabilities can
yield transient native execution. There is no public, model-matched proof that HWID 3076
firmware 10.40 is vulnerable, that such execution persists across reset, or that it can safely
replace the application while preserving a recovery path.

## K28F ROM loader and flash security

### Confirmed silicon capabilities

The photographed non-Music teardown identifies `MK28FN2M0ACAU15` as the main MCU.^15 NXP's
K28F datasheet specifies 2 MiB dual-bank flash, 1 MiB SRAM, USB full/high-speed controllers,
Arm SWJ-DP debug, and a 32 KiB ROM containing a built-in bootloader.^16 These are MCU
capabilities, not evidence of how Garmin configured the production part.

### K28-specific entry configuration

The K28F reference manual's `FOPT` definition selects internal Flash or ROM boot with
`BOOTSRC_SEL` in bits 7:6. `BOOTPIN_OPT` is bit 1. When that bit is zero, asserting the
NMI-multiplexed `BOOTCFG0` function at reset forces ROM boot; when it is one, only
`BOOTSRC_SEL` determines the boot source.^17 This creates a possible silicon-level entry
mechanism, but not a demonstrated watch procedure:

- the NMI/`BOOTCFG0` recipe works only if Garmin's bootloader flash configuration programs
  `BOOTPIN_OPT=0` and if the required NMI and RESET signals can actually be controlled;
- a blank K28 or one configured through `FOPT` can enter ROM, but a Garmin production image
  may select normal internal-flash boot;
- resident Garmin code could call the ROM entry point, but that requires working, cooperative
  firmware; and
- there is no public evidence that a 245 button or test pad changes `FOPT` boot selection.

An NXP support example on the FRDM-K28F development board confirms another board-dependent
detail: the ROM loader uses USB full speed and required a board jumper to route that USB path
before `blhost` worked.^18 That is useful proof that K28 ROM USB depends on board routing; it
does not identify the Forerunner charging-contact routing or Garmin's enabled ROM transports.

NXP's generic MCU bootloader documentation lists configurable UART, I2C, SPI, CAN, USB HID,
and USB MSC transports, with support varying by target. Its default USB HID identity is
`1fc9:007f` (legacy `15a2:0073`).^19 This is a separate protocol and identity from Garmin's
GUSB preboot `091e:0003`. Observing one must not be used to infer the other.

### Flash security and debug recovery

NXP documents Kinetis security through the flash configuration field. `FSEC[SEC]=10b` is the
unsecured state; other encodings are secure. In the secure state, JTAG/SWD cannot access
internal registers or memory except limited debug-status/control state.^20 If
`FSEC[MEEN]` permits it, the debug port may request a mass erase to unsecure the MCU, but all
internal flash code/data is destroyed. If `MEEN=10b`, that debug mass erase is disabled.
A backdoor key helps only if firmware provisioned and exposes a known key mechanism.

Therefore:

- visible SWD/JTAG pads would not prove readable flash;
- a debugger's automatic "unlock" can mean destructive mass erase;
- SWD cannot be called a backup or recovery method until pad mapping and the actual security
  state are known without erase; and
- even a successful K28 mass erase would not restore Garmin boot code, calibration,
  secondary-processor firmware, or private device material.

No live debug connection or security-state read was attempted.

## FCC and teardown evidence for debug pads

The FCC filing for product code `03568` was submitted 2019-03-26. Its internal-photo exhibit
was made public 2019-05-13; the filing records a 986,604-byte PDF with SHA-256
`5c020ac382b8ad23dd6ee6b2442c3fca112ea195f78a046c141476aa10285d66`.^21 Visual review
shows multiple unlabeled gold test pads, but no readable `SWD`, `JTAG`, `UART`, clock, reset,
or ground labels and no connectorized debug header.

The FCC board shown includes the Winbond SDRAM and Samsung eMMC parts also documented in the
Forerunner 245 **Music** teardown.^22 It must not be used as proof of pad routing on the
non-Music HWID 3076 PCB. A later photographed non-Music teardown clearly identifies the K28F
and both sides of the board, but likewise publishes no pad net names, schematic, debug
transcript, or security-state measurement.^15

**Finding:** public photographs support only the statement that manufacturing/test pads
exist. Their signals, voltage levels, production accessibility, and security state remain
unknown. Opening the watch would also compromise a glued waterproof assembly and is outside
this read-only phase.

## Recovery/security technique table

| Technique | Evidence for HWID 3076 | Risk | Reversible? | Hardware modification? | Current likelihood |
|---|---|---|---|---|---|
| Garmin Express / normal `GUPDATE.GCD` | Direct normal-update documentation | Medium: writes application and update metadata; interruption behavior unknown | Probably for valid official images while normal loader survives; not demonstrated | No | High for routine official update; low as brick recovery |
| Button restart | Direct family manual | Low to medium; Garmin warns data/settings may be erased | Usually | No | High for transient hang only |
| Button master reset | Anecdotal 245 successes and failures | High personal-data loss; no firmware repair guarantee | Data loss is irreversible | No | Medium for corrupt settings; low for broken firmware |
| Diagnostic/test mode | Family forum evidence only | Unknown; may be hard to exit | Unknown | No | Low as a firmware recovery path |
| Garmin GUSB preboot | Successful only on GPSMAP 276Cx; no HWID 3076 transcript | Extreme if any handheld region assumption is reused | Unknown | No if exposed | Unknown/low |
| Historical Connect IQ native exploit | Demonstrated on 245 Music, with coordinated fixes | High crash/data corruption; version mismatch; no persistence | Transient in demonstrated form | No | Low/unknown on non-Music 10.40 |
| K28 ROM bootloader | Confirmed in silicon; Garmin entry/config/routing unknown | Extreme: erase/program commands write flash | Depends on configuration and complete restore image | Possibly requires opening/probing | Low/unknown |
| SWD/JTAG readout | MCU capability only; no verified pad map or security state | High; tools may offer destructive mass erase | Read-only attach could be reversible, but auto-unlock is not | Opening/probing required | Unknown |
| SWD/JTAG mass erase | NXP-documented if `MEEN` allows | Certain loss of all K28 internal flash, including Garmin loader | No complete restore image exists | Opening/probing required | Technically possible in some configurations; unacceptable |
| Bootloader exploit/signature bypass | No model-specific candidate found | Extreme brick risk | Unknown | No/unknown | Unknown/low |
| Garmin depot repair/replacement | Seen in user reports | Device leaves user control; data likely lost | Service-dependent | Service action | Plausible consumer recovery, not a research restore path |

## Material recovery conclusions

1. **Application image broken:** some triangle/boot failures have been recovered by a
   destructive button reset, while a post-update 7.20 boot loop resisted both reset methods
   and required repair. There is still no demonstrated 245 MAIN-region reflash path.
2. **Filesystem corrupted:** reset may clear user/settings corruption, but it is destructive
   and does not prove restoration of hidden storage or firmware partitions.
3. **Update interrupted:** dual-bank flash exists in silicon; no source proves Garmin uses it
   atomically or retains a rollback image.
4. **Bootloader damaged:** K28 ROM survives and has a conditional NMI/`BOOTCFG0` entry path,
   but Garmin's `FOPT` setting, watch signal routing, loader peripherals, and security state
   are unknown. No 245 procedure demonstrates that the conditions can be met.
5. **Signature failure:** no public HWID 3076 validation trace establishes whether failure is
   rejected before erase or after any persistent state change.
6. **No USB enumeration:** Garmin documents restart only. No 245-specific forced USB loader
   or field restore was found.

The new evidence strengthens the warning against treating K28 ROM or generic Garmin GUSB as
a safety net. It does not change the core feasibility verdict to GREEN.

## Safest next recovery experiment

Continue offline. Recover and analyze the resident Garmin bootloader bytes, if they can be
obtained from a legitimate firmware/service artifact without using the live watch. The
specific questions are:

1. Does it expose a 245/GUSB preboot enumeration path?
2. Which image regions and record types does it accept?
3. Does it authenticate MAIN cryptographically, and before which erase/write operation?
4. What does the K28 flash configuration field set for `FSEC` and `FOPT`?
5. Does it call or configure the NXP ROM loader, and which USB controller/pins are used?

Only after those questions are answered should a separate proposal consider observing a
special mode on the live watch. That proposal must specify the exact button sequence, expected
USB identity, exit procedure, data-loss risk, and evidence that no command or write occurs.

## Sources

1. Garmin, [Forerunner 245/245 Music Owner's Manual — System Settings](https://www8.garmin.com/manuals/webhelp/forerunner245/EN-US/GUID-1500E73F-F386-49AF-A542-25D4B1655A08.html), manual revision v8, accessed 2026-09-13.
2. Garmin, [Device Interface SDK](https://www8.garmin.com/support/commProtocol.html), accessed 2026-09-13.
3. Garmin, [Forerunner 245 Software Update Collection](https://www8.garmin.com/support/collection.jsp?product=010-02120-11), accessed 2026-09-13.
4. Garmin, [Forerunner 245 Beta 2.82 — Notification Reboots](https://forums.garmin.com/sports-fitness/running-multisport/f/forerunner-245-series/166279/forerunner-245-beta-2-82---notification-reboots), posted 2019-06-28, accessed 2026-09-13.
5. Garmin, [Restarting the Device](https://www8.garmin.com/manuals/webhelp/forerunner245/EN-US/GUID-FE7137DB-B929-4BD6-B76F-EC5E27AD50B3.html), Forerunner 245/245 Music Owner's Manual, accessed 2026-09-13.
6. Garmin, [Resetting All Default Settings](https://www8.garmin.com/manuals/webhelp/forerunner245/EN-GB/GUID-1D4D7BAD-1F1A-4EBC-9C74-8D75CCBBF950.html), Forerunner 245/245 Music Owner's Manual, accessed 2026-09-13.
7. Garmin Forums, [Stuck on diagnostic screen — Forced test mode](https://forums.garmin.com/sports-fitness/running-multisport/f/forerunner-245-series/245582/stuck-on-diagnostic-screen---forced-test-mode-how-to-exist-this-screen), first posted 2020-11-13, Garmin representative reply 2020-11-16, accessed 2026-09-13.
8. Garmin Forums, [Forerunner 245 stuck in Test Mode](https://forums.garmin.com/sports-fitness/running-multisport/f/forerunner-245-series/277867/forerunner-245-stuck-in-test-mode), first posted 2021-11-12, accessed 2026-09-13.
9. naturalgeek, [`garmin-flash-tool`](https://github.com/naturalgeek/garmin-flash-tool), 2026 repository state, accessed 2026-09-13. Related-model evidence only; tested profile is GPSMAP 276Cx HWID 2479.
10. Garmin Forums, [Forerunner 245 frozen — after restart it stays on the triangle](https://forums.garmin.com/sports-fitness/running-multisport/f/forerunner-245-series/211872/forerunner-245-frozen---after-restart-it-stays-on-the-triangle), first posted 2020-01-07; reported FR245 reset success 2021-02-15, accessed 2026-09-13.
11. Garmin Forums, [Reboot loop after upgrade to 7.20](https://forums.garmin.com/sports-fitness/running-multisport/f/forerunner-245-series/264982/reboot-loop-after-upgrade-to-7-20), first posted 2021-06-02, failed recovery reported 2021-06-04, accessed 2026-09-13.
12. Tao Sauvage, Anvil Secure, [Compromising Garmin's Sport Watches: A Deep Dive into GarminOS and its MonkeyC Virtual Machine](https://www.anvilsecure.com/blog/compromising-garmins-sport-watches-a-deep-dive-into-garminos-and-its-monkeyc-virtual-machine.html), published 2023-04-21, updated 2023-05-26.
13. Anvil Secure, [CVE-2023-23300 advisory and proof of concept](https://github.com/anvilsecure/garmin-ciq-app-research/blob/main/advisories/CVE-2023-23300.md), repository accessed 2026-09-13; see also [NVD CVE-2023-23300](https://nvd.nist.gov/vuln/detail/CVE-2023-23300), published 2023-05-23.
14. Dionysus Blazakis, Atredis Partners, [A Watch, a Virtual Machine, and Broken Abstractions](https://www.atredis.com/blog/2020/11/4/garmin-forerunner-235-dion-blazakis/), 2020-11-04.
15. 52audio, [Teardown report: Garmin Forerunner 245](https://www.52audio.com/archives/198399.html), 2024-05-07. Independent photographed teardown of the non-Music model.
16. NXP Semiconductors, [Kinetis K28F MCU Sub-Family Data Sheet](https://www.nxp.com/docs/en/data-sheet/K28P210M150SF5.pdf), Rev. 4, 2017-03.
17. NXP Semiconductors, *Kinetis K28F MCU Sub-Family Reference Manual*, Rev. 4, 2017-08, [public mirror of the NXP document](https://www.ftcelectronics.jp/datasheets-b7/MK28FN2M0CAU15R.pdf). NXP's [K28 product page](https://www.nxp.com/products/K28_150) identifies document `K28P210M150SF5RM`, Rev. 4, but currently requires an account for the official download.
18. NXP Community, [Cannot connect to K28 via FRDM-K28F using blhost](https://community.nxp.com/t5/MCU-Bootloader/Cannot-connect-to-K28-via-FRDM-K28F-using-blhost/m-p/757260/highlight/true), NXP technical-support reply 2017-11-15.
19. NXP, [MCU Bootloader — Supported peripherals](https://mcuxpresso.nxp.com/mcuxsdk/25.09.00/html/middleware/mcu_bootloader/docs/MCU_Bootloader_Reference_Manual/topics/supported_peripherals_001.html), MCUXpresso SDK 25.09.00 documentation.
20. NXP/Freescale, [Using Kinetis Security and Flash Protection Features](https://www.nxp.com/docs/en/application-note/AN4507.pdf), AN4507 Rev. 1, 2012-06.
21. FCC filing mirror, [IPH-03568 Internal Photos, Document ID 4215004](https://fccid.io/IPH-03568/Internal-Photos/Internal-Photos-4215004), submitted 2019-03-26, public 2019-05-13. The page links its FCC.gov source and records the exhibit hash.
22. Kyle Westhaus, iFixit, [Garmin Forerunner 245 Music Teardown](https://documents.cdn.ifixit.com/pdf/ifixit/guide_150396_en.pdf), 2022 teardown PDF.
