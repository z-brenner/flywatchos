# Forerunner 245 Recovery Assessment

## Current conclusion

There is no established, Forerunner-245-specific recovery path from a damaged Garmin
bootloader. Normal Garmin software installation is evidence for recovery only while the
watch boots far enough to enumerate normally and accept a package. Recovery capability
must be demonstrated read-only before any experimental write is considered.

The public-source evidence behind this assessment is recorded in
[`recovery-research.md`](recovery-research.md). The 2026-09-13 research pass specifically
targets the non-Music `HWID 3076` and distinguishes model-matched evidence from Garmin
handheld recovery behavior and generic K28F capabilities.

The last user-observed installed build is the synthetic-13.76 N64 controls
overlay; that observation is not a readback of internal flash. The public
software version remains 1370. On 2026-09-16, a read-only host check found
the expected Garmin `091e:2c04` mass-storage device, a Healthy FAT `GARMIN`
volume, and no pending `GUPDATE.GCD` or `force.tmp`. The quarantined 13.78
HOME diagnostic and 13.79 restore were not staged or installed.

## Evidence levels

- **Known**: Garmin documents the operation for the 245 family.
- **Partial**: the prerequisite or outcome is documented, but it does not cover arbitrary
  or malformed firmware.
- **Unknown**: no reliable 245-specific evidence demonstrates recovery for that failure.

## Documented operations

### Restart

Garmin documents holding `LIGHT` for 15 seconds to turn off an unresponsive 245, then holding
`LIGHT` for one second to turn it on. Garmin warns that even this restart may erase data or
settings.^1 It is therefore a recovery action, not part of passive inventory.

### Normal software update

The manual documents software updates through Garmin Connect and Garmin Express.^2 Historical
Garmin beta instructions also document placing `GUPDATE.GCD` in `\Garmin`, disconnecting,
and approving the update on the watch. The same instructions state that reverting to an
older version resets settings to defaults.^3 These procedures write flash and must not be
used during read-only investigation.

### Factory reset

Garmin documents several reset options, including a destructive option that deletes
activities, user information, settings, and stored music.^4 A factory reset is not a
firmware recovery guarantee and is prohibited without exact approval.

## Failure scenarios

| Scenario | Expected surviving component | Recovery evidence | Status | Data/brick risk |
|---|---|---|---|---|
| 1. Application image broken | ROM and Garmin bootloader may remain | A user reported recovering one triangle hang with a destructive button reset, but a 7.20 post-update boot loop resisted both reset sequences and required repair. No published 245 MAIN-region reflash was found.^6,7 The package's temporary helper copies staged type `0x0e` to an unresolved destination type `0xaf`, so an update can reach the application region after reboot. | **Unknown** | High. Could range from settings recovery to a non-enumerating watch. |
| 2. Filesystem corrupted | Internal program flash may remain intact | Normal reset/format behavior exists, but no source proves recovery when eMMC metadata prevents normal boot | **Partial/unknown** | High personal-data loss; firmware may still fail to boot. |
| 3. Update interrupted | Depends on Garmin transaction design | K28F has dual-bank flash, but no evidence establishes that Garmin uses it atomically or retains a rollback image | **Unknown** | High. Power loss could affect application or loader-owned metadata. |
| 4. Bootloader damaged | K28F mask ROM survives | K28F supports conditional ROM entry through an NMI-multiplexed `BOOTCFG0` function when `FOPT[BOOTPIN_OPT]=0`. Garmin's production setting, watch signal routing, enabled transports, and security state are unknown.^8 | **Unknown; no user recovery established** | Extreme. Likely service/debug intervention or permanent brick. |
| 5. Signature failure | Bootloader should remain if validation precedes erase | Update authentication and failure ordering have not been demonstrated | **Unknown** | Could be a safe rejection or a failed update state. Must not test live. |
| 6. Device no longer enumerates over USB | Possibly ROM or bootloader | Restart is documented; no Garmin-documented 245 preboot USB recovery sequence was found. A public GUSB recovery tool is proven only on GPSMAP 276Cx HWID 2479 and explicitly treats other region mappings as untested.^9 | **Unknown** | High. Lack of normal USB removes the only current non-invasive host path. |

## What can and cannot be called a backup

A copy of the user-visible volume is valuable but is not a complete restoration image. It
does not establish possession of:

- K28F bootloader or protected flash regions;
- the exact installed main application image;
- sensor-hub, radio, or GNSS firmware;
- eMMC partitions hidden from MTP/mass storage;
- calibration, pairing, identity, or security material;
- option bytes and flash-security configuration.

The normal-mode FAT volume is now preserved both file-by-file and as a complete
20,807,680-byte raw image. All 204 visible files extracted from that image match
the file-level SHA-256 manifest. This strengthens filesystem recovery only; the
volume still does not expose the resident loader or the other regions listed
above.

"Complete backup" should be used only after every executable and device-specific region is
inventoried and a restoration method is demonstrated. Until then, the accessible copy is
called a **user-visible filesystem backup**.

## Available official restore artifacts

Garmin's current update catalog supplied the non-Music `006-B3076-00` system package
version 13.70. It is preserved locally as `Forerunner245_1370_GUPDATE.GCD` (5,120,675 bytes,
SHA-256 `8ebefacf6bcc00bec0fb271596abfb9618f9a3114d32b3a106fbd27d5a366adc`). This is the
best available official application restore artifact for a watch that still reaches the
normal Garmin updater. It is now a same-public-version package for the connected
watch and is skipped by the recovered normal forward-version comparison; it is
not a demonstrated restore path for the installed synthetic-13.76 overlay.

A synthetic-13.77 official-code wrapper (5,120,675 bytes, SHA-256
`724c8fe8bdafd6857116cbb28951e9f2934badab09616a716e450e6676fb3c4d`)
and a synthetic-13.79 wrapper (5,120,675 bytes, SHA-256
`7a4fc373c0ceb7d0fbdaffa3bdacde0bc92668c17ebec389d6d4573d8a8c58fe`)
are preserved in local quarantine. Both carry the official 13.70 executable
and resources behind newer coherent version/checksum metadata. Neither is an
official Garmin package or a demonstrated nonboot restore. They can help only
if GarminOS, the normal USB volume, and the on-watch updater still function.

The exact installed 10.40 system image was not present on the mounted volume. An archived
copy of Garmin's non-Music product `14935` page names the 11.03 beta archive
`Forerunner245_1103Beta.zip` and its rollback file `GUPDATE-1040.GCD`. This establishes
model-matched provenance, but the Garmin download now returns 404 and the archive index has
no captured ZIP, so the binary itself is still unavailable.^11 Historical non-Music 3.10 is also
preserved for analysis, but it is not treated as a safe recovery image:
it is a major downgrade and Garmin documents that downgrade operations can reset settings.

None of these packages can restore a damaged resident bootloader, unknown option bytes,
calibration/identity data, or firmware in secondary processors unless the surviving Garmin
loader explicitly supports that operation.

The current static analysis also shows that a normal system package contains a
temporary `0x0505` helper that is intended to run at `0x1ffc0000` and copy the
staged main payload from type `0x0e` into compound destination type `0xaf`.
NXP defines `0x1ffc0000` as SRAM_L, so the helper does not overlap the final
main image in internal flash. Static analysis maps `0xaf` to internal
application flash `0x00003000..0x001fffff` followed by external QuadSPI
`0x68617000..0x68916fff`; the separate resident prefix below `0x3000` is not
part of this normal copy target. The resident stage that loads, validates, and
launches the RAM helper is still unavailable. An interrupted application copy therefore remains an
unresolved recovery risk; a normal package write is still not demonstrated to
be reversible.

## Preconditions for any future write proposal

Before requesting approval for a write, the proposal must state:

1. exact bytes/artifact and SHA-256;
2. target component, region, partition, and expected previous contents;
3. validation performed by the receiving loader;
4. predicted behavior for interruption, checksum failure, and signature failure;
5. known entry sequence for recovery, demonstrated without writing;
6. exact official restore artifact and its SHA-256;
7. whether recovery covers the application only or also the bootloader;
8. brick-risk severity, evidence, and unresolved assumptions; do not invent a
   numerical probability when the evidence cannot support one.

A user-visible backup and a downloadable GCD do not satisfy these preconditions by
themselves.

## Safest recovery research sequence

The sequence below stops before any special-mode or write action:

1. Inventory normal USB descriptors, interfaces, volumes, and `GarminDevice.xml` read-only.
2. Back up every accessible file with timestamps and SHA-256 hashes.
3. Keep attempting legitimate acquisition of the exact 10.40 image; preserve and hash it if
   found. Until then, record the official current 13.70 package as an application-only
   recovery candidate, not a demonstrated recovery path.
4. Compare that package with the accessible `GUPDATE.GCD`, if present, without moving or
   renaming either file.
5. Analyze the update parser and boot decision offline to determine image boundaries,
   authentication, erase order, and failure behavior.
6. Document a candidate read-only recovery-mode observation separately. Entering it still
   requires a specific decision because Garmin does not document a 245 preboot loader.

Do not treat the diagnostic/test screen as that loader. Public 245 reports identify the
screen but publish no flashing protocol, image regions, or recovery transcript. Likewise, do
not attach a debugger on the assumption that it is read-only: NXP documents that a secured
Kinetis part blocks memory access and some debug tools may offer a destructive mass erase to
unlock it. Mass erase can also be disabled by `FSEC[MEEN]`.^10

No loader command, firmware transfer, downgrade, reset, or update-file placement belongs in
this sequence.

## Neural 13.74 restore wrapper (offline only)

The quarantined file
`Forerunner245_1374-official-payload-restore.gcd.analysis-only.DO_NOT_INSTALL`
is 5,120,675 bytes with SHA-256
`4d47edfcaeb3585bd026ac89c8cc9fbeaa9168032d9569aa3885bfdb4880ffa4`.
It carries official 13.70 hook, code, and resource bytes behind coherent
synthetic 13.74 descriptor/header metadata, plus the exact additive and outer
checkpoint repairs required by that version change. It is not byte-identical
to the official package.

This wrapper is only a possible application restore while GarminOS, USB mass
storage, and the normal updater still work. The updater/helper erase scope is
internal `0x00003000..0x001fffff` and external QSPI
`0x68617000..0x68916fff`; the 0x4d8000-byte decoded main programs external
through `0x688f1fff`, leaving `0x688f2000..0x68916fff` erased. No nonboot
recovery path is known. `packaging_allowed:false` and
`live_staging_allowed:false` remain in force, so no transfer or installation
is authorized. Feasibility remains **YELLOW**.

## Sources

1. Garmin, "[Restarting the Device](https://www8.garmin.com/manuals/webhelp/forerunner245/EN-US/GUID-FE7137DB-B929-4BD6-B76F-EC5E27AD50B3.html)," Forerunner 245/245 Music Owner's Manual.
2. Garmin, "[Forerunner 245/245 Music Owner's Manual](https://www8.garmin.com/manuals/webhelp/forerunner245/EN-US/Forerunner_245_OM_EN-US.pdf)," software-update and troubleshooting sections.
3. Garmin, "[Forerunner 245 series Beta Software Version 8.78](https://forums.garmin.com/sports-fitness/running-multisport/f/forerunner-245-series/285488/forerunner-245-series---beta-software-version-8-78---now-available)," installation and downgrade instructions.
4. Garmin, "[Resetting All Default Settings](https://www8.garmin.com/manuals/webhelp/forerunner245/EN-GB/GUID-1D4D7BAD-1F1A-4EBC-9C74-8D75CCBBF950.html)," Forerunner 245/245 Music Owner's Manual.
5. NXP Semiconductors, "[Kinetis K28F MCU Sub-Family Data Sheet](https://www.nxp.com/docs/en/data-sheet/K28P210M150SF5.pdf)," boot-ROM and dual-bank-flash capabilities.
6. Garmin Forums, "[Forerunner 245 frozen - after restart it stays on the triangle](https://forums.garmin.com/sports-fitness/running-multisport/f/forerunner-245-series/211872/forerunner-245-frozen---after-restart-it-stays-on-the-triangle)," first posted 2020-01-07; user-reported reset success 2021-02-15.
7. Garmin Forums, "[Reboot loop after upgrade to 7.20](https://forums.garmin.com/sports-fitness/running-multisport/f/forerunner-245-series/264982/reboot-loop-after-upgrade-to-7-20)," 2021-06-02 through 2021-06-04.
8. NXP Semiconductors, *Kinetis K28F MCU Sub-Family Reference Manual*, Rev. 4, 2017-08, [public mirror](https://www.ftcelectronics.jp/datasheets-b7/MK28FN2M0CAU15R.pdf); see the `FOPT` definition and ROM boot sequence.
9. naturalgeek, "[`garmin-flash-tool`](https://github.com/naturalgeek/garmin-flash-tool)," GPSMAP 276Cx HWID 2479 recovery implementation, repository accessed 2026-09-13.
10. NXP/Freescale, "[Using Kinetis Security and Flash Protection Features](https://www.nxp.com/docs/en/application-note/AN4507.pdf)," AN4507 Rev. 1, 2012-06.
11. Garmin, "[Forerunner 245 software version 11.03 Beta](https://web.archive.org/web/20220720063806/https://www8.garmin.com/support/download_details.jsp?id=14935)," archived 2022-07-20; non-Music beta and 10.40 rollback filenames.
