# Neural overlay live proposal and execution record

## Current decision

The neural package pair was constructed and verified **offline** before the
separate live action was approved. The fields below describe the offline
construction gate and remain part of its provenance:

- `offline_quarantine_construction_allowed: true`
- `packaging_allowed: false`
- `live_staging_allowed: false`
- feasibility: **YELLOW**

No package was copied, renamed, linked, or redirected to a watch, removable
volume, Garmin application, or updater-visible directory during construction.
After independent review passed and the exact live risk was disclosed, the
user approved the 13.73 candidate. Only that exact profile was then added to
`tools/live-proof/stage-gupdate.ps1`; the 13.74 restore remained unavailable.
The one-use candidate profile was removed after the verified installation, so
the staging guard again rejects every neural mode.

## Exact local artifacts

Both files are under the resolved local root
`<workspace>\artifacts\firmware\quarantine` and deliberately end in
`.gcd.analysis-only.DO_NOT_INSTALL`.

| Purpose | Filename | Size | SHA-256 |
| --- | --- | ---: | --- |
| Neural candidate | `Forerunner245_1373-flyos-neural-overlay.gcd.analysis-only.DO_NOT_INSTALL` | 5,120,675 | `4ec78eabd23a880ad5d4e9ff52e688e62397480a32070316b2748b70b771c9d7` |
| Official-code restore wrapper | `Forerunner245_1374-official-payload-restore.gcd.analysis-only.DO_NOT_INSTALL` | 5,120,675 | `4d47edfcaeb3585bd026ac89c8cc9fbeaa9168032d9569aa3885bfdb4880ffa4` |

The pinned official source is
`artifacts/firmware/originals/Forerunner245_1370_GUPDATE.GCD`, 5,120,675
bytes, SHA-256
`8ebefacf6bcc00bec0fb271596abfb9618f9a3114d32b3a106fbd27d5a366adc`.

## Exact candidate content

The 13.73 descriptor and decoded header are coherent and the HWID is 3076.
Runtime version mirrors remain at official 13.70. The helper stream and helper
descriptor are byte-identical to official. Relative to the decoded official
main stream, changes are confined to:

| Purpose | Runtime range | Decoded-main range |
| --- | --- | --- |
| Embedded header version | `0x0000322c..0x0000322d` | `0x0000022c..0x0000022d` |
| Display hook | `0x00009a20..0x00009a23` | `0x00006a20..0x00006a23` |
| Primary allocation | `0x001f6000..0x001f63ff` | `0x001f3000..0x001f33ff` |
| Secondary allocation | `0x001fa400..0x001fabff` | `0x001f7400..0x001f7bff` |
| Final decoded-main additive repair | external `0x688f1fff` | `0x004d7fff` |

The compiled hook is 4 bytes. The primary compiled segment is 794 bytes; its
allocation is filled from official `0xff` bytes and its last byte at runtime
`0x001f63ff` is the additive repair (`0xff` to `0xaf`). The secondary compiled
segment is 2,044 bytes and its final four allocation bytes remain official
`0xff`. Package-level descriptor/checkpoint repair bytes are separately
enumerated in the machine report.

The 13.74 wrapper restores the official 13.70 hook and every official byte in
both full allocations. Its decoded main differs from official only at header
offset `0x22c` and final additive byte `0x4d7fff`; its raw GCD differs at
`0x00a160`, `0x00a392`, `0x4e2299`, and `0x4e229e`. It is not byte-identical
to the official package.

## Rewrite scope and risk

A later live action, if separately approved, would use the exact destination
`D:\Garmin\GUPDATE.GCD`. The recovered helper behavior erases internal flash
`0x00003000..0x001fffff` and external QSPI
`0x68617000..0x68916fff`. The 0x4d8000-byte decoded main then programs internal
`0x00003000..0x001fffff` and external
`0x68617000..0x688f1fff`; external
`0x688f2000..0x68916fff` remains erased. This corrects the older assumption
that decoded offset `0x4d7fff` maps to `0x68916fff`.

Installing either file has a nonzero, unquantified brick risk. The restore
wrapper depends on GarminOS booting, USB mass storage enumerating, and the
normal updater running. No Forerunner 245/HWID-3076 recovery path is known if
the application no longer boots or enumerates. Standalone FlyOS boot is not
demonstrated. These limits keep feasibility **YELLOW**.

The package is first staged in external QSPI: helper staging type `0x05` uses
`0x68103000..0x68117fff`; main staging type `0x0e` uses
`0x68118000..0x68616fff`, with failure marker `0x68615000`. A staging failure
can therefore leave a one-way marker or partial state before the later helper
rewrite. The secondary allocation still lacks a complete proprietary semantic
ownership/reservation inventory, despite clean bytes and reference scans.
Live stack headroom, interrupt interaction, scheduling, DMA, FlexIO, and LCD
timing have not been proved by the offline emulator.

The currently observed watch state is the installed synthetic-13.72
full-screen GarminOS overlay while its public software version remains 1370.
The available backups cover accessible FAT files and a normal-volume image,
not resident loader flash, option bytes, calibration/identity data, or every
secondary processor. Before any later action treats
`D:\Garmin\GUPDATE.GCD` as the destination, a fresh controller-owned read-only
check must establish the exact mounted device identity, current version,
healthy volume, adequate space, and absence of `GUPDATE.GCD` and `force.tmp`.

## Offline evidence

Exact reconstruction, both opt-in generic profiles, and both full-image
validator runs report PASS. The authoritative reports are:

- `artifacts/firmware/analysis/neural-overlay-package-build-1373-1374.json`
- `artifacts/firmware/analysis/neural-overlay-package-strict-verification-1373-1374.json`
- `artifacts/firmware/analysis/neural-overlay-generic-verification-1373.json`
- `artifacts/firmware/analysis/neural-restore-generic-verification-1374.json`
- `artifacts/firmware/analysis/neural-overlay-full-image-validation-1373.json`
- `artifacts/firmware/analysis/neural-restore-full-image-validation-1374.json`

The amended construction decision SHA-256 is
`1179e1caded279c30ea21ff6403c11072b2bb937b01dc846590a7217f2e06dfa`.
It directly pins the current emulator source and focused test. A deterministic
report-only refresh reconstructed both existing packages under that decision
without changing their bytes, sizes, creation times, or last-write times. The
superseded reports and ledger remain in the local analysis archive.

The user subsequently gave explicit approval for the exact 13.73 candidate,
destination, and staging action after receiving these facts. That approval did
not authorize the restore wrapper or any other image.

The controller's post-build read-only check at `2026-09-14T14:51:19Z` found
one expected Garmin USB device, a healthy/OK GARMIN FAT volume, 15,509,504
bytes free, and neither `GUPDATE.GCD` nor `force.tmp`. A fresh 268-file
content/size manifest was compared with the 266-file preserved baseline while
excluding timestamps: 264 entries were identical; the remaining additions,
rotation, and changed debug log were device-generated operational files. The
check mutated nothing. The private path/hash manifest remains local and is not
reproduced here.

## Observed live result

The staging guard created `D:\Garmin\GUPDATE.GCD` with create-new semantics,
flushed it, and verified the complete watch-side file as 5,120,675 bytes with
SHA-256
`4ec78eabd23a880ad5d4e9ff52e688e62397480a32070316b2748b70b771c9d7`.
Windows safely ejected the volume. The user selected the update with the
top-right START button and reported the ASCII neural brain after reboot. All
five buttons changed the displayed neuron glyphs.

Read-only post-install inspection found the expected FR245 USB identity,
Healthy/OK GARMIN FAT volume, and public software version 1370.
`GUPDATE.GCD` and `force.tmp` were absent. The restore was not staged. This is
direct evidence for the GarminOS-resident 32-neuron model, input sampling, and
full-screen renderer; it does not establish standalone FlyOS boot or nonboot
recovery. Feasibility remains **YELLOW**.
