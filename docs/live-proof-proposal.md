# Proposed first live FlyOS proof

## Status

**Not executed. Candidate is complete, but recovery is not demonstrated and an
independent audit rates the live experiment NO-GO under a reversibility
standard.**

The proposed experiment is a deliberately small test of whether the Forerunner
245 accepts a modified full system image. It is not the standalone FlyOS target
and does not demonstrate arbitrary code execution. If accepted, GarminOS 13.70
would still boot and its System -> About page is expected to show the label
`FLY LIVES 2ALIVE` in place of `Software Version`.

## Exact candidate

| Property | Value |
|---|---|
| Local artifact | `artifacts/firmware/quarantine/Forerunner245_1369-matched-fly-visible.gcd.analysis-only.DO_NOT_INSTALL` |
| Size | 5,120,675 bytes |
| SHA-256 | `d89d52ca82586d7cea003c2f5b65b854790b572246164064fe3df079fa36ca2f` |
| Official source SHA-256 | `8ebefacf6bcc00bec0fb271596abfb9618f9a3114d32b3a106fbd27d5a366adc` |
| Changed bytes | Exactly 20, enumerated below |
| Visible change | decoded main `0x43eaa4`: `Software Version` -> `FLY LIVES 2ALIVE` |
| Code changes | None |
| Main version | descriptor and installed-image header both 13.69 |
| Temporary helper | Byte-identical to Garmin 13.70 |

The exact raw changes are:

| Raw offset | Original | Candidate | Purpose |
|---:|---:|---:|---|
| `0x00a160` | `0x5a` | `0x59` | main GCD descriptor 13.70 -> 13.69 |
| `0x00a392` | `0x5a` | `0x59` | installed main header 13.70 -> 13.69 |
| `0x448d1a..0x448d29` | 16-byte original label | 16-byte FlyOS label | visible proof |
| `0x4e2299` | `0xc4` | `0xc5` | main-image additive checksum repair |
| `0x4e229e` | `0xf7` | `0xf8` | final outer additive checkpoint repair |

The old and new text have the same byte sum modulo 256. The record layout,
main length, helper payload and descriptor, all executable instructions, and
every byte outside the table above remain unchanged. The main descriptor and
installed main header are coherently 13.69; the 13.70 helper payload and its
descriptor remain mutually consistent. The full-image validator and exact
`flyos-visible-proof-matched1369` verifier profile pass. These checks cover the
validation visible in the acquired GarminOS application. The missing resident
loader may still authenticate or reject the image using an unknown mechanism.

## Exact write that would be requested

The host action would run
`tools/live-proof/stage-gupdate.ps1 -Mode Candidate1369 -Execute`. The script
would copy those 5,120,675 bytes to the currently absent path
`D:\Garmin\GUPDATE.GCD`, read the destination back, and require its SHA-256 to
equal `d89d52ca82586d7cea003c2f5b65b854790b572246164064fe3df079fa36ca2f`.
No other watch path would be created, replaced, renamed, or deleted during a
successful staging run. If copying, flushing, or verification fails while the
volume remains accessible, the script removes only the newly created
`GUPDATE.GCD`. If the volume disappears during staging, PowerShell is forcibly
terminated, the host crashes, or USB/power is lost, cleanup may not run or
cannot be confirmed; a partial `GUPDATE.GCD` may remain for the next mount.
The path must be inspected before disconnecting or restarting after any such
failure. A safe eject/disconnect would then allow the watch to discover a
successfully verified package. Accepting an update prompt on the watch would
start a separate device-side write.

Static analysis predicts the following device-side targets if the package is
accepted:

| Stage | Target |
|---|---|
| Temporary update helper | External staging region `0x68103000..0x68117fff`, then SRAM_L at `0x1ffc0000` |
| Composite main staging | External QuadSPI `0x68118000..0x68616fff` |
| Installed internal application | K28F flash `0x00003000..0x001fffff` |
| Installed external resources/code | QuadSPI `0x68617000..0x68916fff` |
| Resident prefix | `0x00000000..0x00002fff`, excluded from the helper's normal destination |

The helper erases and rewrites the full application and external region even
though the candidate changes only 20 package bytes: 16 label bytes, two version
bytes, and two checksum-repair bytes.

## Brick risk and recovery

The brick risk is **material and not quantifiable from current evidence**.

- If the missing resident loader rejects the altered image before erasing the
  installed application, the likely result is a safe rejection. That ordering
  has not been observed on this model.
- If validation or power fails after application erase begins, the watch may
  stop booting or enumerating over USB.
- A resource-only edit is less likely to crash after a successful install than
  a code hook, but installation still replaces the complete application image.
- The resident prefix appears excluded from the normal copy target, but no
  Forerunner-245 recovery protocol has been demonstrated through it.

The preserved official 13.70 package is byte-identical to Garmin's artifact.
Its main descriptor is numerically newer than this candidate's matched 13.69
main descriptor and header. If the candidate boots, reports 13.69, and retains
normal update service, the intended restoration is to dry-run and then execute
`tools/live-proof/stage-gupdate.ps1 -Mode Official1370`, verify the official
SHA-256, disconnect, and accept the normal forward update. That would rewrite
the original Garmin 13.70 main bytes.

This is a credible restore hypothesis, not a demonstrated recovery path. The
installed-version reader has not been proven to source header `0x22c`, and the
resident loader's descriptor/header rules remain absent. If the candidate
stops normal USB enumeration, no 245-specific recovery method is known. This
exact action therefore cannot truthfully be described as reversible.

## Evidence this experiment would and would not provide

A visible changed label would prove that this watch installed and executed a
modified system payload through the normal update chain. It would falsify a
simple hypothesis that every payload byte is covered by an enforced
cryptographic signature. It would not yet prove an executable code hook,
standalone boot, working FlyOS display drivers, or arbitrary firmware
execution.

The next candidate after this acceptance test is an in-app framebuffer hook at
13.70 application address `0x00009a20`. Its payload would draw a fly while
Garmin's initialized display stack and locks remain active. That candidate
must pass code-cave, branch, ABI, disassembly, and offline execution checks
before it is considered for a live proposal.
