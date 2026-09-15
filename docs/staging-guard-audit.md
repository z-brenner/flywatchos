# Staging guard audit

Date: 2026-09-13

## Verdict

**PASS for the narrow host-side staging guard after remediation.** This does
not change the separate **NO-GO** conclusion for installing the candidate: the
resident-loader acceptance policy and nonboot recovery path remain unknown.

The review covered `tools/live-proof/stage-gupdate.ps1` and the write and
recovery statements in `docs/live-proof-proposal.md`. No invocation used
`-Execute`; no file was created, changed, renamed, or deleted on `D:`.

## Controls verified

- Only two fixed profiles are accepted. Each resolves from `PSScriptRoot` to a
  fixed repository-relative source and must match its pinned SHA-256 before the
  device is inspected.
- The drive-letter input is one letter and all device paths are fixed literal
  paths below that volume. There is no caller-controlled filename or relative
  destination component.
- The selected logical disk must map through exactly one partition to exactly
  one physical disk. The disk must be a present USB `Garmin FR245 Flash USB
  Device`, its `USBSTOR` identity must name Garmin/FR245, and its actual PNP
  parent must be present with VID `091E` and PID `2C04`.
- The volume must be healthy, labeled `GARMIN`, formatted as FAT, have the
  required free-space margin, contain a model/version XML identifying part
  `006-B3076-00`, and report the profile's exact prerequisite version.
- Any existing `Garmin/GUPDATE.GCD` causes refusal. The write path independently
  uses `FileMode.CreateNew`, closing the check-to-open replacement race rather
  than overwriting an existing path.
- A successful write is flushed, closed, measured, and hashed. Both destination
  size and SHA-256 must equal the already pinned source.
- After the destination has been newly created, any catchable copy, flush,
  close, readback, size, or hash failure enters cleanup. Cleanup removes only
  that destination and verifies its absence. Loss of the volume or failed
  deletion is reported as unconfirmed cleanup.

## Findings remediated during review

1. The original nested `try/finally` disposed streams but allowed a copy or
   flush exception to skip the later verification/removal block, leaving a
   partial `GUPDATE.GCD`. The write and verification path is now enclosed by a
   catch that cleans up only after this invocation successfully used
   `CreateNew`.
2. The original identity check trusted only a `GARMIN` FAT label and mutable
   `GarminDevice.xml`. It now binds the selected drive through CIM associations
   to the present FR245 USB disk and verifies the disk node's actual Garmin USB
   VID/PID parent.
3. The proposal described only a successful copy and hash-mismatch cleanup. It
   now documents catchable copy/flush/readback cleanup and the possibility of a
   partial file after process termination, host failure, or USB/power loss.
4. The proposal said the candidate changed 16 source bytes. It now accurately
   accounts for all 20 changed package bytes: 16 label bytes, two version bytes,
   and two checksum repairs.

## Verification performed

- PowerShell parser: no syntax errors.
- Candidate dry run on the connected watch: passed all source hash, storage,
  USB identity, model, part-number, version 10.40, free-space, and destination
  absence checks; output remained `execute: false`.
- Official-restore dry run on the current 10.40 watch: refused because that
  profile requires a reported version of 13.69.
- Candidate dry run against drive `C:`: refused because it is not the expected
  GARMIN FAT volume.
- `D:/Garmin/GUPDATE.GCD` was absent after every dry-run check.
- Candidate size/hash: 5,120,675 bytes,
  `d89d52ca82586d7cea003c2f5b65b854790b572246164064fe3df079fa36ca2f`.
- Official restore size/hash: 5,120,675 bytes,
  `8ebefacf6bcc00bec0fb271596abfb9618f9a3114d32b3a106fbd27d5a366adc`.

## Residual limits

The execution-only branch was not dynamically exercised because doing so would
write to the watch. Its failure cleanup was verified by source and parser
review, not by a live fault injection. Forced termination, an OS crash, or
USB/power loss can prevent any process cleanup; the proposal now requires
inspection of `GUPDATE.GCD` before disconnect or restart after such a failure.

The official 13.70 restore profile is deliberately fail-closed and cannot run
while the watch reports 10.40. Its usefulness after the candidate depends on
the unproven assumption that the watch boots, reports 13.69, continues to
enumerate normally, and accepts official 13.70 as a forward update. These are
recovery limitations, not host-side staging-guard defects.
