# Forerunner 245 full-screen FlyOS overlay and recovery proposal

## Status

The exact 13.72 package in this document was installed through the normal
Garmin updater after the bounded 13.71 overlay succeeded. The user reported
that the restarted watch's whole screen showed `FLY LIVES` and the fly. The
13.73 recovery wrapper remains offline and has not been staged or installed.

The intended prerequisite is a successfully booted 13.71 bounded overlay with
normal GarminOS menus and USB mass storage. The full-screen overlay advances
the coherent main descriptor/header metadata to synthetic version 13.72. Its
recovery wrapper advances them again to synthetic 13.73 while carrying Garmin's
official 13.70 executable code and resources.

Versions 13.72 and 13.73 are synthetic admission metadata. They are not Garmin
releases.

## Live result (2026-09-14)

The installed file was exactly 5,120,675 bytes with SHA-256
`6394fd73cc3e7a5660a6fe9cde3cc0b6617c21f8a24f2b6319b328882d662713`.
The reported full-screen `FLY LIVES` and fly output is unique to the custom
974-byte Thumb renderer reached by the changed branch at `0x00009a20`. This
demonstrates that the normal Garmin update/boot chain accepted the tested code
changes, executed the custom Thumb body, and gave it control of the complete
240-by-240 logical framebuffer.

This remains a GarminOS-resident overlay. GarminOS still boots first and
provides display initialization, the framebuffer, locking, dirty-rectangle
tracking, and final display dispatch. The result does not demonstrate a
standalone FlyOS boot or independent hardware initialization. Read-only
post-install inspection found USB status OK, a healthy volume, model/part
Forerunner 245 `006-B3076-00`, software version 1370, and neither
`GUPDATE.GCD` nor `force.tmp`. Subsequent live observation mapped top-left `L`
to LIGHT, middle-left `4` to UP, bottom-left `3` to DOWN, top-right `1` to
START/STOP, and bottom-right `2` to BACK. All five markers agree with the
active-low GPIO model.

## Exact artifacts

| Artifact | Size | SHA-256 |
|---|---:|---|
| Official non-Music 13.70 source | 5,120,675 | `8ebefacf6bcc00bec0fb271596abfb9618f9a3114d32b3a106fbd27d5a366adc` |
| Button-enabled full-screen payload | 974 | `358d71190321f7dd9d51de8ac3c913e370b0fc23a25e7541d072d2ac83941ffb` |
| Four-byte display hook | 4 | `49ff680c8b811f58b6747fea531fcbc8b88b3142946a1cad4271e0911f02a362` |
| **13.72 full-screen overlay package** | **5,120,675** | **`6394fd73cc3e7a5660a6fe9cde3cc0b6617c21f8a24f2b6319b328882d662713`** |
| 13.72 decoded main | 5,079,040 | `6e2108d1091c2e017ea284e90aca46466c0b39ea8767efbc21b9c89f0b3ab4cf` |
| **13.73 official-code recovery wrapper** | **5,120,675** | **`869d62ab829ac7b75a079effd4d7d0b1e71a5e8a0d1c7d2c94fa686d907aa4e6`** |
| 13.73 decoded main | 5,079,040 | `532d4a161ef8455f853cc4bd3d6f5e329e2985eb905658defaf532e3d6bfe957` |
| Official helper stream used by both | 37,120 | `f2351f808c0510baba6aae045867d8a366646511da662a411038426107725e46` |

Paths:

- `artifacts/firmware/quarantine/Forerunner245_1372-flyos-fullscreen-overlay.gcd.analysis-only.DO_NOT_INSTALL`
- `artifacts/firmware/quarantine/Forerunner245_1373-official-payload-restore.gcd.analysis-only.DO_NOT_INSTALL`

## Resulting watch face

On each eligible GarminOS display flush, the payload owns and deterministically
repaints the complete 240-by-240, byte-per-pixel logical framebuffer. The face
contains:

- large `FLY LIVES` title;
- centered dorsal fly specimen;
- `STATE QUIET`;
- `AGE 01:42:32`;
- five 12-by-12 raw button markers labelled `L 1 2 3 4`.

Two emulated executions beginning with different framebuffer values produce
the same final 57,600-byte frame, SHA-256
`15f644334fa872b0d44dec173b74e302c862eedbbc47c6c8ba285d2ba4881722`.
All pixels are either `0x00` or `0xff`, no source sentinel remains, and 64-byte
canaries on both sides of the framebuffer remain unchanged.

The hook is the same experimentally reviewed instruction replacement:

```text
0x00009a20  04 f0 c0 fb  bl 0x0000e1a4   official
0x00009a20  ec f1 ee fa  bl 0x001f6000   candidate
```

The payload first checks the framebuffer pointer, active backend pointer
`0x1ffdb754 == 0x0000ebfc`, and startup-complete byte
`0x1fff223c == 1`. It then repaints, calls
`dirty_add(0,0,240,240)` through Thumb address `0x0000f2e9`, restores its
stack and AAPCS callee-saved registers, and tail-dispatches the original flush
through Thumb address `0x0000e1a5`.

The instruction-level run executes 224,968 instructions on the released path.
That is a functional instruction count, not a hardware cycle or power estimate.
The full repaint may increase display latency and energy use compared with the
bounded overlay.

## Read-only button input

After the display initialization guards pass, the payload makes exactly one
32-bit volatile read from each of these K28F input registers:

| Marker | Register | Mask | Physical label confidence |
|---|---:|---:|---|
| `L` | `GPIOC_PDIR 0x400ff090` | `0x00000800` | LIGHT/power strongly inferred |
| `1` | `GPIOD_PDIR 0x400ff0d0` | `0x00000400` | unresolved |
| `2` | `GPIOD_PDIR 0x400ff0d0` | `0x00000002` | unresolved |
| `3` | `GPIOA_PDIR 0x400ff010` | `0x00100000` | unresolved |
| `4` | `GPIOA_PDIR 0x400ff010` | `0x00400000` | unresolved |

The inputs are strongly inferred active-low. The compiled-payload emulator
records the ordered reads from GPIOA, GPIOC, and GPIOD and records no write in
the GPIO peripheral page. Pulling each emulated input low changes only its own
12-by-12 marker. With the startup guard false, the payload performs no GPIO
read and no framebuffer write.

The indicators update when GarminOS requests a redraw; they are not a complete
independent input loop. Switch bounce and the physical labels for keys 1 to 4
remain unresolved.

## Placement and package differences

The payload occupies 974 bytes at `0x001f6000..0x001f63cd` inside the audited
1,024-byte allocation `0x001f6000..0x001f63ff`. In the official image every
source byte in that allocation is `0xff`, and the Ghidra range report contains
zero static destination references into that exact interval. The final
allocation byte at `0x001f63ff` is used for the stream additive repair. The
wider erased tail contains known references and is not considered free.

The 13.72 package differs from official 13.70 at 972 raw bytes and 970 decoded
main bytes. Every decoded change is confined to:

- main header version at decoded `0x22c`, 1370 to 1372;
- four-byte display hook at decoded `0x6a20..0x6a23`;
- audited allocation at decoded `0x1f3000..0x1f33ff`;
- final main additive repair at decoded `0x4d7fff`.

The GCD main descriptor is also 1372. Descriptor field `0x0b` remains zero.
All known runtime identity constants and strings remain official 13.70, which
matches the behavior observed after the earlier descriptor/header mutation.
The helper payload and helper descriptor are byte-identical to official 13.70.

The main stream sums to zero modulo 256, every outer checkpoint passes, and
the recovered application full-image validator passes.

## Admission strategy

The normal recovered selector admits a numerically newer incoming component.
Synthetic 13.72 is newer than both the preceding 13.71 overlay metadata and
the watch's observed public/runtime 13.70 value. This avoids the rejected
descriptor-field-`0x0b` force hypothesis.

The live experiments now demonstrate acceptance of controlled descriptor,
header, resource, hook, new-code, and additive-checksum changes. Exact
synthetic 13.72 was accepted and its 974-byte Thumb body executed. This does
not prove that every image/component is unauthenticated or that code can run
before GarminOS.

## Recovery wrapper

The 13.73 wrapper is numerically newer than 13.72 and uses the same ordinary
admission path with descriptor field `0x0b` zero. It removes the custom hook
and restores every byte of the audited allocation to its official value.

Relative to the official GCD, the wrapper changes exactly four raw bytes:

| Raw offset | Official | Wrapper | Meaning |
|---:|---:|---:|---|
| `0xa160` | `0x5a` | `0x5d` | main descriptor 1370 to 1373 |
| `0xa392` | `0x5a` | `0x5d` | main header 1370 to 1373 |
| `0x4e2299` | `0xc4` | `0xc1` | final main additive repair |
| `0x4e229e` | `0xf7` | `0xf4` | outer checkpoint repair |

The resulting decoded main is official 13.70 code and resources except for
decoded header byte `0x22c` and final checksum byte `0x4d7fff`. All known
runtime version mirrors remain official 13.70. This is a bounded wrapper around
official code; it is not a byte-identical official Garmin package.

Recovery is available only if the 13.72 application boots far enough to expose
normal USB mass storage and run the GarminOS updater. A processor fault before
that point, interrupted full-image rewrite, or other nonboot failure cannot be
recovered using the wrapper. No FR245-specific nonboot recovery mechanism has
been demonstrated.

## Write and brick exposure

Installation of either file is a full system update. GarminOS stages the
37,120-byte helper in QSPI type `0x05` at
`0x68103000..0x68117fff` and the 5,079,040-byte main stream in type `0x0e` at
`0x68118000..0x68616fff`. The helper erases and rewrites compound destination
type `0xaf`:

- internal application flash `0x00003000..0x001fffff`;
- external QSPI `0x68617000..0x68916fff`.

The resident prefix `0x00000000..0x00002fff` is excluded, but its recovery
behavior is unknown. An interrupted update or bad runtime assumption can leave
GarminOS and normal USB unavailable and can permanently brick the watch.

## Reproducible validation

The exact builder/verifier is
`tools/garmin-firmware/fullscreen_version_strategy.py`.

Build:

```powershell
python tools/garmin-firmware/fullscreen_version_strategy.py build `
  --official artifacts/firmware/originals/Forerunner245_1370_GUPDATE.GCD `
  --hook flyos/target/fr245_1370_fullscreen_overlay/build/hook.bin `
  --payload flyos/target/fr245_1370_fullscreen_overlay/build/overlay.bin `
  --xref-report artifacts/firmware/analysis/code-cave-overlay-xrefs-1370.txt `
  --overlay artifacts/firmware/quarantine/Forerunner245_1372-flyos-fullscreen-overlay.gcd.analysis-only.DO_NOT_INSTALL `
  --restore artifacts/firmware/quarantine/Forerunner245_1373-official-payload-restore.gcd.analysis-only.DO_NOT_INSTALL `
  --report artifacts/firmware/analysis/fullscreen-forward-version-candidates.json
```

Verify:

```powershell
python tools/garmin-firmware/fullscreen_version_strategy.py verify `
  --official artifacts/firmware/originals/Forerunner245_1370_GUPDATE.GCD `
  --hook flyos/target/fr245_1370_fullscreen_overlay/build/hook.bin `
  --payload flyos/target/fr245_1370_fullscreen_overlay/build/overlay.bin `
  --xref-report artifacts/firmware/analysis/code-cave-overlay-xrefs-1370.txt `
  --overlay artifacts/firmware/quarantine/Forerunner245_1372-flyos-fullscreen-overlay.gcd.analysis-only.DO_NOT_INSTALL `
  --restore artifacts/firmware/quarantine/Forerunner245_1373-official-payload-restore.gcd.analysis-only.DO_NOT_INSTALL `
  --report artifacts/firmware/analysis/fullscreen-forward-version-strict-verification.json
```

Validation artifacts:

| Report | SHA-256 | Result |
|---|---|---|
| Candidate build | `5ad84b7f3929e4540bb0fc8f53f2e5643632f7c0388dc09d84fe97bb1a5e503b` | exact bounds and package checks pass |
| Strict pair verification | `00f8940e28be433e4734cbb462715f2e5d171684616227405446c0eaf4d6e2c1` | `PASS` |
| Full-screen payload emulation | `06bb4a3ceee46546d9208c45abebcf73bbff3612b1111883aeb75614bd70c085` | framebuffer, ABI, GPIO, dirty and dispatch checks pass |
| 13.72 full-image validation | `ccfd3c92f88f8f5eed854babe827740eed220311d11dceb0ccd8747df4059a8b` | `PASS` |
| 13.73 full-image validation | `d56653a2873919301575168b0c41a4be2b49469cd05000447c3c422c265083e1` | `PASS` |
| Exact code-cave xrefs | `760721bee4bdf216b7064adf5f5d23507e0d5f2995610dbcc7cba27bf8fe31f2` | zero static destination references |

The live staging guard has two new pinned modes:

```powershell
powershell -ExecutionPolicy Bypass -File tools/live-proof/stage-gupdate.ps1 `
  -Mode FullscreenOverlay1372

powershell -ExecutionPolicy Bypass -File tools/live-proof/stage-gupdate.ps1 `
  -Mode FullscreenRestore1373
```

Both commands are read-only dry runs unless `-Execute` is supplied. The guard
requires a healthy, identified non-Music FR245 reporting 1370, an absent
`GUPDATE.GCD`, adequate free space, and the exact pinned source hash.

The completed 13.72 action does not authorize a further write. In particular,
the 13.73 recovery wrapper remains uninstalled and requires separate approval.

After the payload and package hashes were frozen, the complete
`tools/garmin-firmware/tests` suite passed **49/49** tests. The final payload
rebuild reproduced its pinned SHA-256, and the staging script passed a
PowerShell parser check plus a static check for both exact profile hashes.

## Decision

**LIVE GO RESULT: the exact 13.72 full-screen overlay booted and produced the
intended full-screen `FLY LIVES` and fly display.**

This is demonstrated persistent custom Thumb execution within GarminOS, not a
standalone FlyOS boot. Feasibility remains **YELLOW** because safe
reversibility, direct hardware initialization, persistent neural state, and
recovery without GarminOS are not established. USB health and all five
physical button markers are now verified.
