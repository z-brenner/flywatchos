# FORERUNNER 245 CUSTOM FIRMWARE

**Hardware:** Connected non-Music Forerunner 245 (`006-B3076-00`) built around
an NXP Kinetis K28F Arm Cortex-M4F (2 MiB internal flash, 1 MiB SRAM). Public
non-Music teardown evidence identifies an Apollo2 sensor hub, CYW20719 ANT/BLE
radio, AG3335MN GNSS receiver, MAX20303 power-management IC, and MAX86141
optical AFE. The 240x240 transflective MIP panel uses a confirmed K28
FLEXIO0/DMA path, a 57,600-byte logical framebuffer, and twelve PTE pins. The
five key inputs map to GPIOC11, GPIOD10, GPIOD1, GPIOA20, and GPIOA22. Panel
identity, signal roles/timing, and the non-Music external-storage part remain
unknown. The row converter and the two firmware generations' identical FlexIO
setup are decoded: DMA29 feeds a six-bit parallel pixel shifter and DMA30 a
coordinated control shifter. This is still a static transport description, not
a safe panel-init sequence.

**Firmware:** Before the live proof, the connected watch reported system 10.40.
After installation and reconnection, `GarminDevice.xml` reports system 13.70.
Eight official Garmin
GCD packages were preserved and SHA-256 hashed, including non-Music system 3.10
and system 13.70. A 2026-09-13/14 recheck of Garmin's update collection still
showed 13.70 as the latest Garmin-published Forerunner 245 system version.
Garmin's archived non-Music 11.03 beta page proves its
rollback file was named `GUPDATE-1040.GCD`, but the removed ZIP was not archived,
so the exact non-Music 10.40 image was not acquired.
Offline parsing shows flat little-endian GCD records, unkeyed additive
checkpoints, unencrypted Arm Thumb payloads, and a main application vector
table based at `0x3000` with reset vector `0x31f1`. A second executable region
maps at `0x04600000`. The installer recomputes the additive checksum, performs
an additional additive low-byte check on non-delta full images, and sends main
type `0x0e` to Garmin logical region
`0x68118000` with `0x4ff000` capacity; 3.10 and 13.70 contain the same mapping.
That region is confirmed external QuadSPI flash: an update erases it, streams
the composite application image in page-bounded writes, records failure state,
and requests restart. The package also contains a native temporary update helper
at MK28 SRAM_L base `0x1ffc0000`; it does not overlap internal application
flash. Its recovered 3.10 copy loop reads type `0x0e` and writes
compound destination type `0xaf`. Both helper versions show that `0xaf`
replaces internal application flash `0x3000..0x1fffff` and a 3 MiB external
QuadSPI region while excluding the resident prefix below `0x3000`. The resident
stage that installs and launches this helper is absent from the packages. The
helper's successful path checksums the destination and calls the new
application reset vector at `0x3004` directly.

**Live resource proof:** The matched-13.69 resource candidate is a
5,120,675-byte package whose main descriptor and installed-image header are
both changed from 13.70 to 13.69 and whose About-page resource reads
`FLY LIVES 2ALIVE`. Its SHA-256 is
`d89d52ca82586d7cea003c2f5b65b854790b572246164064fe3df079fa36ca2f`.
The exact `flyos-visible-proof-matched1369` profile passes and permits only the
20 enumerated version, label, and checksum changes. The guarded staging
readback matched the SHA-256 above, Windows safely ejected the volume, the user
accepted the on-watch installation, and the booted watch displayed
`FLY LIVES 2ALIVE`. Read-only reconnect evidence shows a healthy HWID-3076
volume, `GarminDevice.xml` software version 1370, and neither `GUPDATE.GCD` nor
`force.tmp`. This demonstrates persistent acceptance and rendering of the
controlled resource mutation plus continued normal USB mass-storage service.
It also falsifies the assumption that the edited descriptor/header fields make
the installed system publicly report 13.69. Official 13.70 is therefore a
same-version restore candidate, whose acceptance remains uncertain.

**Live executable proof:** The exact 5,120,675-byte synthetic-13.72 package,
SHA-256
`6394fd73cc3e7a5660a6fe9cde3cc0b6617c21f8a24f2b6319b328882d662713`,
was accepted through the normal Garmin updater after the successful bounded
13.71 experiment. The user reported that the restarted watch's entire screen
showed the full-screen FlyOS face, including `FLY LIVES` and the fly. The
package changes the display-path call at `0x00009a20` to branch to a 974-byte
custom Thumb payload at `0x001f6000`; the official image contains `0xff` in
the exact `0x001f6000..0x001f63ff` allocation and the static range audit found
zero destination references into that allocation. The observed full-frame
output therefore demonstrates persistent execution of changed Thumb
instructions and control of GarminOS's 57,600-byte framebuffer through the
normal update and boot path.

This is a GarminOS-resident overlay, not standalone FlyOS. It depends on the
official GarminOS boot path, scheduler, display initialization, framebuffer,
locking, dirty-rectangle service, and original display dispatcher. It does not
demonstrate replacement of the resident loader, independent clock/memory/panel
initialization, or a custom kernel booting without GarminOS. Read-only
post-install inspection found the reconnected USB device OK, the volume
healthy, model Forerunner 245 part `006-B3076-00`, software version 1370, and
neither `GUPDATE.GCD` nor `force.tmp`. Live button observation mapped top-left
`L` to LIGHT, middle-left `4` to UP, bottom-left `3` to DOWN, top-right `1` to
START/STOP, and bottom-right `2` to BACK. All five agree with the active-low
GPIO model.

**Boot protections:** The presumed resident loader below `0x3000` is absent
from the update packages. The successful live proofs show that the normal
update/boot path does not enforce an immutable manufacturer signature over the
tested main descriptor, installed-image header, resource, changed application
instructions, new code body, and repaired additive-checksum bytes.
Authentication of other components or ranges remains possible. No
Forerunner-245-specific arbitrary-image recovery path, persistent exploit,
secure-boot determination, or unlocked debug-port evidence was found. The
visible `Signature check failed on file:` text belongs to Connect IQ app/cache
validation. The directly observed system-update checks are unkeyed additive
checks for ordinary full images and a SHA-1 comparison in the separately gated
`GDELTA01` delta path. The 13.72 live proof establishes acceptance and
execution of the tested changed-instruction/new-code mutation. It does not
establish unrestricted arbitrary-image acceptance or control before GarminOS.
Neither preserved helper contains standard SHA-1/SHA-256/MD5 initial-state
sets or PEM key markers, but the missing resident stage can still authenticate
the package or helper by an unidentified mechanism.

**Recovery:** A verified file-by-file backup, a complete 20,807,680-byte raw
image of the normal FAT16 volume, and the official current 13.70 application
package are available. They are not a full flash backup and cannot be assumed
to recover a damaged loader, option bytes, calibration/identity data, or all
secondary processors. Recovery from a broken application is unproven;
recovery from a damaged bootloader is unknown and likely requires service or
debug access. The 2026-09-13/14 public-source recheck found no documented
Forerunner-245/HWID-3076 preboot loader, emergency USB reflash, or recovery
procedure when normal USB enumeration is lost.

The 13.72-modified system boots, renders the full-screen overlay, and retains
healthy USB mass storage. The exact 13.73 recovery wrapper, SHA-256
`869d62ab829ac7b75a079effd4d7d0b1e71a5e8a0d1c7d2c94fa686d907aa4e6`,
restores Garmin's official 13.70 executable code and resources while retaining
synthetic forward-version metadata. It remains uninstalled and is usable only
if GarminOS boots far enough to expose USB mass storage and run its updater.
It cannot recover a watch that no longer boots or enumerates, and no
Forerunner-245-specific nonboot recovery method has been demonstrated.

The fail-closed staging script was subsequently run in its explicitly approved
candidate mode. It revalidated the watch and copied the exact candidate to
`GUPDATE.GCD`; forced flush, size verification, and full watch-side SHA-256
readback succeeded. Windows safely ejected the volume. The user disconnected,
selected **Install now**, and reported the changed resource after boot. The
earlier independent **NO-GO / `hold_for_evidence`** assessment was therefore
conservative for this resource mutation, but its recovery objection remains
valid for executable experiments and failed-update scenarios.

**Custom firmware feasibility: YELLOW**

**Biggest unknown:** Whether the resident loader can recover a nonbooting
application, followed by the hardware initialization needed to turn the
demonstrated GarminOS-resident code execution into a standalone FlyOS boot.

**Safest next step:** Keep the demonstrated full-screen overlay stable while
developing the tiny neural-state and persistence layer offline. Do not install
the 13.73 recovery wrapper or another overlay until that separate action is
explicitly approved; the wrapper is not a nonboot recovery mechanism.

Do not proceed to a watch write, special mode, or protocol experiment without
a separate, explicit approval for that exact action.

## Offline neural overlay construction (2026-09-14)

The quarantined coherent-13.73 neural candidate is 5,120,675 bytes, SHA-256
`4ec78eabd23a880ad5d4e9ff52e688e62397480a32070316b2748b70b771c9d7`.
The coherent-13.74 official-code restore wrapper is 5,120,675 bytes, SHA-256
`4d47edfcaeb3585bd026ac89c8cc9fbeaa9168032d9569aa3885bfdb4880ffa4`.
The dedicated exact profile, opt-in generic profiles, full-image validation,
record layout, stream lengths, HWID, version coherence, helper identity,
additive sum, and all five outer checkpoints pass offline.

The candidate contains the reviewed 4-byte hook, 794-byte primary segment,
and 2,044-byte secondary segment inside their complete 1,024-byte and
2,048-byte allocation envelopes. The restore returns both allocations and the
hook to official content; only coherent 13.74 admission metadata and named
repair bytes differ from official. It is not byte-identical to Garmin's 13.70
package.

The controlling offline-construction decision remains
`packaging_allowed:false` and `live_staging_allowed:false`. At construction
and review time the staging guard had no neural mode. No connected watch was
accessed for package construction. The restore still depends on a booting
GarminOS/USB path; no nonboot recovery is known. Custom-firmware feasibility
therefore remains **YELLOW**.

The controller then performed the required post-build read-only device check.
The GARMIN FAT removable volume was Healthy/OK with 15,509,504 bytes free;
`GUPDATE.GCD` and `force.tmp` were absent and no personal content was opened.
A timestamp-excluded comparison found 264 content/size-identical files between
the 266-file baseline and 268-file current manifest, with three expected
device-generated additions, one rotated event-log removal, and one changed
debug error log. The check recorded `watch_mutated:false` and kept
`live_staging_allowed:false`.

The Task 5 review provenance and transaction findings are resolved offline.
The amended decision SHA-256 is
`1179e1caded279c30ea21ff6403c11072b2bb937b01dc846590a7217f2e06dfa`;
it directly pins and the builder validates the current emulator source and its
focused test. The new report-only `refresh` path reconstructed and verified the
existing package files without changing their bytes, sizes, creation times, or
last-write times. Superseded reports remain in the local analysis archive.
Injected write, flush, and fsync failures now remove every newly created
partial file, while pre-existing destinations are preserved and cleanup
failure is fatal. These fixes did not access a connected device and did not
change the live policy.

## Live neural FlyOS result

After the exact candidate, destination, rewrite scope, permanent-brick risk,
recovery limits, and restore wrapper were presented, the user explicitly
approved staging the coherent-13.73 neural candidate. Only that approved
profile was enabled. The guarded copy used create-new semantics, forced a
device flush, and verified all 5,120,675 watch-side bytes by SHA-256. The
readback matched
`4ec78eabd23a880ad5d4e9ff52e688e62397480a32070316b2748b70b771c9d7`.
Windows then safely ejected the volume.

The user accepted the update with the top-right START button and reported the
ASCII brain after reboot. Pressing all five watch buttons changed the neuron
glyphs, demonstrating live input-dependent activity from the installed
32-neuron fixed-point network. After reconnection, the expected FR245 USB
identity, Healthy/OK FAT volume, and public version 1370 remained intact;
`GUPDATE.GCD` and `force.tmp` were absent. The restore wrapper was not staged.

This completes the GarminOS-resident FlyOS neural-display goal. It does not
replace the resident loader or independently initialize the MCU/display, and
no recovery path is known if a future image prevents GarminOS or USB from
booting. Overall custom-firmware feasibility remains **YELLOW**.

## Neural Specimen N64 offline package result

The reviewed 64-neuron target was packaged only into the local quarantine.
The synthetic 13.74 candidate is 5,120,675 bytes with SHA-256
`3a4a4af6355c132571c1158667cc43c96bf5da7a67737ab028267930e71134cd`.
The synthetic 13.75 official-code restore wrapper has the same size and SHA-256
`ccd2a29c51a41a436111239c7181e1cb0cea1f2fac1c48d600fff6dec103e5da`.

The candidate contains the exact reviewed 4-byte hook, 1,016-byte primary
segment, and 2,034-byte secondary segment. The restore carries official 13.70
code/resources across the hook and both full allocation envelopes and retains
the official helper stream. Both packages preserve package length and record
structure and pass exact reconstruction, additive/checkpoint, generic-profile,
and full-image checks. Packaged segment hashes bind directly to the completed
64-neuron emulator evidence.

No live file was staged. The staging script explicitly rejects the new modes,
names, paths, basenames, and hashes. Brick risk remains nonzero, no nonboot
recovery is known, and the restore depends on GarminOS/USB remaining functional.
Separate exact approval is required before any live write. Feasibility remains
**YELLOW**.

This N64 result is a GarminOS-resident application overlay. It is not
standalone FlyOS, a bootloader replacement, or evidence of arbitrary-image or
arbitrary-boot execution. The N64 build has no valid HR BPM, motion, or charging
telemetry: it renders `HR --` and `MOTION --`, does not let those unavailable
channels drive the model, and leaves Garmin's stock non-home charging, USB,
update, notification, menu, and critical screens unchanged.

The N64 live proposal now includes the exact conditional restore sequence.
Only while GarminOS and USB storage still boot, it requires a read-only identity
and Healthy/OK-volume preflight with no pending `GUPDATE.GCD`, exact verification
of the 5,120,675-byte 13.75 restore wrapper SHA-256
`ccd2a29c51a41a436111239c7181e1cb0cea1f2fac1c48d600fff6dec103e5da`,
separate exact approval, and a temporary independently audited restore profile
because the current guard blocks the artifact. The future approved action would
copy with create-new atomic placement to `D:\Garmin\GUPDATE.GCD`, rehash the
destination, safely eject, use Garmin's normal on-watch install UI, then
reconnect for read-only official-code behavior, version, and accessible-file
verification. Every identity, health, pending-file, hash, write, eject, UI, and
post-boot mismatch is an abort condition. This procedure cannot recover loss of
USB enumeration, an early-boot failure that prevents the updater, or loader
damage.

The final package-custody review found and fixed a validate-then-reopen race.
All pinned inputs now remain immutable byte snapshots through construction and
reporting, repeated manifest references reuse one validated snapshot, and every
created package/report is reread from its final path. Lexical traversal,
symlink/reparse, hardlink, overwrite, short-write, cleanup, and rollback cases
fail closed. The final focused suite discovered 21 tests: 20 passed and the
ordinary-symlink case explicitly skipped because this Windows process lacks
symlink privilege; a real NTFS junction/reparse alias was created and rejected.
The exact target Unicorn suite passed 20/20. The candidate and restore bytes
remain unchanged at the hashes above; no live/device path was accessed during
the fixes.
