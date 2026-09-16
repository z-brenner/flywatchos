# FR245 Neural Specimen N64 controls live-write proposal

Status: **OFFLINE ONLY — NOT APPROVED FOR LIVE STAGING**

This document describes a possible future write. It does not authorize it.
The candidate is a GarminOS-resident overlay, not a replacement bootloader or
standalone FlyOS image.

## Exact candidate

- Source: `artifacts/firmware/quarantine/Forerunner245_1376-flyos-neural-specimen-n64-controls.gcd.analysis-only.DO_NOT_INSTALL`
- Size: 5,120,675 bytes
- SHA-256: `9dc61b99cebacc50f121b9145ddfab21445344fac6f70a4ab68dde205fcf84de`
- Possible destination after exact approval: `D:\Garmin\GUPDATE.GCD`
- Wrapper: synthetic 13.76, HWID 3076, based on the byte-pinned official 13.70 package
- Official source SHA-256: `8ebefacf6bcc00bec0fb271596abfb9618f9a3114d32b3a106fbd27d5a366adc`

The decoded application changes these target areas:

| Purpose | Runtime range | Bytes written |
| --- | ---: | ---: |
| Display hook | `0x00009a20..0x00009a23` | 4 |
| Pre-publisher key hook | `0x0000fa48..0x0000fa4d` | 6 |
| Controls primary payload | `0x001f6000..0x001f63e3` | 996 |
| Primary padding | `0x001f63e4..0x001f63fe` | 27 |
| Primary additive repair | `0x001f63ff` | 1 |
| Controls secondary payload | `0x001fa400..0x001fabfb` | 2,044 |
| Secondary padding | `0x001fabfc..0x001fabff` | 4 |
| Coherent header version | decoded main offset `0x22c` | 1 changed byte |
| Final main additive repair | decoded main offset `0x4d7fff` | 1 |

The raw GCD also changes its coherent descriptor/checkpoint bytes. Every changed
range is enumerated in the offline build report. Exact reconstruction, official
helper identity, record layout, additive sum, five outer checkpoints, both hook
decoders, segment placement, and confirmed application-side full-image checks
pass offline.

This remains a full-image Garmin update. The recovered official helper erases
internal application flash `0x00003000..0x001fffff` and external QSPI
`0x68617000..0x68916fff`. The main stream programs the internal application and
external `0x68617000..0x688f1fff`; the erased external tail is not populated by
the main stream. The resident prefix `0x00000000..0x00002fff` is outside the
observed helper rewrite, but loader-owned state is not fully acquired.

## Resulting controls

- START, DOWN, and UP are captured only when two bounded scans agree that the
  Garmin watch face is the first visible view.
- LIGHT and BACK always keep their Garmin behavior.
- Holding BACK while pressing START, DOWN, or UP forces the complete sequence
  through to GarminOS.
- USB mass-storage states and every non-home or malformed view pass the press
  to Garmin.
- Ownership is latched from press through release, and every new press clears a
  stale ownership value before making a new decision.
- An owned press posts the watch face's normal redraw event through the existing
  nonblocking UI queue. A short release remains visible for one frame.

The face shows a tapered 64-neuron field inside an angular fly-head contour.
All foreground pixels fit within a strict 100-pixel radius. START, DOWN, and UP
produce distinct neural states and the exact footers `START>BURST`,
`DOWN>CALM`, and `UP>PULSE`; LIGHT produces `LIGHT>LUX` while held. BACK is the
system escape and does not fabricate a FlyOS acknowledgement frame.

## Risk and recovery

Brick risk is nonzero. Offline validation proves the known package structure,
checksums, placements, stack bound, instruction paths, and emulated behavior.
It does not prove the resident loader's complete policy, live task headroom, or
behavior under every interrupt and power-loss timing.

There is no known nonboot recovery. If GarminOS or the normal USB update service
does not boot, the prepared restore cannot be installed by the known method.

The prepared restore is:

- Source: `artifacts/firmware/quarantine/Forerunner245_1377-official-payload-restore-n64-controls.gcd.analysis-only.DO_NOT_INSTALL`
- Size: 5,120,675 bytes
- SHA-256: `724c8fe8bdafd6857116cbb28951e9f2934badab09616a716e450e6676fb3c4d`

It is a synthetic 13.77 wrapper carrying the complete official 13.70
application, resources, hook/allocation contents, and official helper stream.
Only coherent 13.77 version/checksum metadata differs from official 13.70. It
is not byte-identical official firmware.

### Conditional restore procedure

Restoration is possible only while GarminOS boots normally and its USB
mass-storage updater still enumerates.

1. Reconnect the watch and perform a read-only preflight. Require the expected
   non-Music Forerunner 245 identity, HWID 3076 / part `006-B3076-00`, Garmin
   USB VID/PID `091e:2c04`, a Healthy/OK `GARMIN` FAT volume, sufficient free
   space, and no existing `GUPDATE.GCD`, `force.tmp`, or other pending marker.
2. Rehash the local restore and require the exact size and SHA-256 above.
3. Obtain separate exact approval for the restore write. The staging guard must
   be temporarily changed to allow only this exact source name, size, hash, and
   destination, then independently checked in dry-run mode.
4. Create a new temporary sibling under `D:\Garmin`, write and flush the exact
   bytes, rehash the complete temporary file, and rename it to `GUPDATE.GCD`
   only with create-new/no-overwrite semantics. Reopen and rehash the final
   destination. Never replace an existing update.
5. Flush the volume, request safe eject, verify that the volume is no longer
   mounted, disconnect, and use Garmin's native update UI only if it appears
   normally and the watch remains responsive.
6. After reboot, reconnect and perform a read-only identity, filesystem,
   version, pending-file, behavior, and sanitized accessible-file comparison.
   Re-enable the staging denylist immediately.

This procedure cannot recover a watch that no longer enumerates over USB, that
cannot reach Garmin's normal updater, or that has damaged resident loader state.

## Approval boundary

Before staging, present the exact candidate source, size, hash, destination,
full-image erase/program scope, nonzero brick risk, recovery limits, and restore
procedure again. The current staging tool explicitly blocks the candidate and
restore by mode, name, path, and hash. A separate exact approval is required
before enabling a one-use candidate profile or writing the watch.
