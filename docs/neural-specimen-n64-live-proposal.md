# FR245 Neural Specimen N64 live-write proposal

Status: **OFFLINE ONLY — NOT APPROVED FOR LIVE STAGING**

This proposal describes a possible future write. It does not authorize it. A
separate, exact user approval is still required before any file is copied to
the watch.

**Feasibility verdict: YELLOW.** This candidate is a GarminOS-resident
application overlay. It does not replace the bootloader or GarminOS, does not
boot as standalone FlyOS, does not initialize the hardware from reset, and does
not prove arbitrary-image or arbitrary-boot execution.

## Exact candidate

- Source: `artifacts/firmware/quarantine/Forerunner245_1374-flyos-neural-specimen-n64.gcd.analysis-only.DO_NOT_INSTALL`
- Size: 5,120,675 bytes
- SHA-256: `3a4a4af6355c132571c1158667cc43c96bf5da7a67737ab028267930e71134cd`
- Possible destination if separately approved: `D:\Garmin\GUPDATE.GCD`
- Wrapper version: synthetic 13.74; HWID 3076; official base 13.70.
- Official source GCD SHA-256: `8ebefacf6bcc00bec0fb271596abfb9618f9a3114d32b3a106fbd27d5a366adc`.

The package keeps the official record layout and official helper stream. In
the decoded main image it writes:

| Purpose | Runtime range | Bytes |
|---|---:|---:|
| Display hook | `0x00009a20..0x00009a23` | 4 |
| N64 primary payload | `0x001f6000..0x001f63f7` | 1,016 |
| Primary additive repair | `0x001f63ff` | 1 |
| N64 secondary payload | `0x001fa400..0x001fabf1` | 2,034 |
| Coherent header version | decoded `0x22c` | 1 changed byte |
| Final main additive repair | decoded `0x4d7fff` | 1 |

The raw GCD also changes the coherent descriptor byte at `0xa160` and the
outer checkpoint byte at `0x4e229e`. Every actual changed range is enumerated
in `artifacts/firmware/analysis/neural-specimen-n64-exact-differences-1374-1375.json`.

This is a full-image update, not a small in-place patch. The recovered official
helper erases internal application flash `0x00003000..0x001fffff` and external
QSPI `0x68617000..0x68916fff`. The decoded main programs the internal
application image and external `0x68617000..0x688f1fff`; the external erase
tail `0x688f2000..0x68916fff` is not populated by the main stream. The resident
prefix `0x00000000..0x00002fff` is outside that observed helper rewrite, but
loader-owned state is not fully acquired.

## Runtime scope and unavailable telemetry

The N64 overlay draws only after an affirmative GarminOS home/watch-face check.
BACK forces unconditional pass-through. Garmin-owned non-home screens,
including charging, USB, update, notification, menu, and critical views, pass
through unchanged; START remains Garmin's native update-confirmation control.

Heart-rate BPM, motion, and charging telemetry are unavailable in this build
and do not drive the neural model. The face therefore shows exact `HR --` and
`MOTION --`; it does not claim a charging state. A cached, validated battery
percentage may show as `B n`, and `USB MS` means only the two confirmed cached
mass-storage states. Neither value is a charging-telemetry substitute.

## Risk and recovery

Brick risk is nonzero. Validation proves package structure, the known additive
checks, exact payload placement, and offline emulation. It does not prove the
resident loader's complete policy or live scheduler/stack headroom. The target
uses exactly the 384-byte target-owned stack ceiling, with zero measured
margin. A view-state freshness race can briefly paint the overlay after the
last home-view check.

No known nonboot recovery exists. If GarminOS or its normal USB update service
does not boot, the prepared restore cannot be installed by the known method.

The restore is:

- `artifacts/firmware/quarantine/Forerunner245_1375-official-payload-restore-n64.gcd.analysis-only.DO_NOT_INSTALL`
- Size: 5,120,675 bytes
- SHA-256: `ccd2a29c51a41a436111239c7181e1cb0cea1f2fac1c48d600fff6dec103e5da`

It is a synthetic 13.75 wrapper carrying the official 13.70 application,
resources, complete hook/allocation contents, and official helper stream. It
is not byte-identical official firmware. Restoration requires GarminOS and
normal USB update handling to remain functional and to accept the wrapper.

### Exact conditional restore procedure

This procedure is available only while GarminOS boots normally and its USB
mass-storage update path still enumerates. It is a future proposal, not current
authorization.

1. Reconnect the normally booting watch and perform a read-only preflight.
   Require the expected non-Music Forerunner 245 identity (HWID 3076 / part
   `006-B3076-00`), Garmin USB VID/PID `091e:2c04`, and a Healthy/OK `GARMIN`
   FAT volume. Require enough free space and confirm that
   `D:\Garmin\GUPDATE.GCD`, `force.tmp`, and every other known pending-update
   marker are absent. Open no activity, GPS, token, or other personal content.
2. Rehash the local restore source and require exactly 5,120,675 bytes and
   SHA-256
   `ccd2a29c51a41a436111239c7181e1cb0cea1f2fac1c48d600fff6dec103e5da`.
3. Obtain separate exact user approval for this restore write after presenting
   the source, hash, size, destination, full-image erase/program scope, nonzero
   brick risk, and these recovery limits. The current staging guard blocks the
   restore name, path, hash, and mode. A temporary, narrowly scoped restore
   profile must therefore be added and independently audited before use; it may
   enable only this exact artifact and must be removed after the one action.
4. Run that audited profile in dry-run mode. Abort unless it repeats every
   identity, health, absence, size, space, source-hash, and destination check
   above without accessing private files.
5. After approval, create a new temporary sibling file beneath `D:\Garmin`,
   copy the exact restore bytes, flush and close it, and rehash the complete
   temporary destination. Only after its size and SHA-256 match exactly, rename
   it within the same FAT directory to `D:\Garmin\GUPDATE.GCD` with
   create-new/no-overwrite semantics. Reopen the final destination read-only and
   again require the exact size and SHA-256. Never replace an existing update.
6. Flush the volume, request safe eject, verify `D:` is no longer mounted, and
   disconnect the cable. On the watch, proceed only if Garmin's normal update
   UI appears and the device remains responsive; accept/install through the
   Garmin UI using its native top-right START confirmation and wait for the
   update and reboot to finish without interruption.
7. Reconnect after the watch boots. Perform a read-only verification of the
   expected device identity, Healthy/OK FAT volume, reported software/version
   evidence, absence of `GUPDATE.GCD` and pending-update markers, official-code
   watch-face behavior with the N64 overlay absent, and a timestamp-sanitized
   comparison of accessible files against the preserved baseline. Record and
   SHA-256 hash a sanitized receipt without exposing personal data.
8. Remove the temporary restore profile so the staging guard again explicitly
   blocks both N64 artifacts.

Abort before writing on any unexpected identity, volume, pending update,
existing destination, local hash/size, free-space, dry-run, or profile-review
result. Abort after a write failure, short write, flush failure, destination
hash mismatch, rename failure, or eject failure; do not continue to installation
or overwrite/delete an uncertain file without a newly reviewed recovery action.
Abort the on-watch step if the normal update prompt is absent or differs from
the expected Garmin flow. A failed post-boot check is evidence to stop and
investigate, not permission to repeat the update.

This procedure cannot recover a watch that does not enumerate over USB, cannot
reach Garmin's normal updater because of an early-boot/application failure, or
has damaged resident loader/bootloader state. No known nonboot recovery path
exists for those cases.

## Required approval boundary

Before any future staging, the exact candidate hash, size, source,
`D:\Garmin\GUPDATE.GCD` destination, ranges above, brick risk, recovery limits,
and restore procedure must be presented again. Separate exact user approval is
still required. The current staging script explicitly blocks both N64 files,
paths, hashes, and modes.
