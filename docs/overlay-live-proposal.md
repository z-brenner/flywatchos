# Forerunner 245 executable-overlay admission and restore proposal

## Status

This document is an offline proposal. Neither package described here has been
copied to the watch, staged, installed, or executed. The connected watch volume
was not accessed while preparing these artifacts.

The successful resource experiment is the controlling evidence. The watch
accepted the matched-13.69 package, booted, rendered `FLY LIVES 2ALIVE`, and
returned with normal USB mass storage. Afterward, `GarminDevice.xml` still
reported software version 1370. This proves acceptance of the tested
descriptor, header, resource, and additive-checksum mutations. It does not
prove execution of changed instructions. It also disproves the earlier restore
assumption that lowering only the descriptor and image-header versions makes
official 13.70 a normal forward update.

## Version-policy correction

`FUN_001cd670` in the 13.70 application admits a component when a global mode
returned by `thunk_EXT_FUN_04779634()` is nonzero or when a selected incoming
version is greater than the current component version. Descriptor-derived byte
`param_2+0x0d` changes which parsed version (`local_68[0]` or `local_62`) is
used on the right side of that comparison. It is not the unconditional force
condition in the recovered function.

The GCD parser labels descriptor field `0x0b` as `erase_flag`. Setting it to one
may affect the selector, but static evidence does not show that it activates
the global unconditional branch. Accordingly, the field-`0x0b` packages are
retained only as rejected offline hypotheses. They are not the recommended
admission or restore mechanism.

Evidence files:

- `artifacts/firmware/analysis/gcd-recovery-version-policy-1370.txt`
- `artifacts/firmware/analysis/decompile-version-provider-1370.txt`
- `artifacts/firmware/analysis/overlay-version-xrefs-1370.txt`

## Compared strategies

| Strategy | Admission from observed 13.70 | Restore consequence | Assessment |
|---|---|---|---|
| Existing descriptor/header 13.70 overlay, field `0x0b=0` | The visible comparison treats it as same-version and is expected to skip it | Official 13.70 is also same-version | Reject |
| Descriptor 13.70/header 13.69 mismatch | Incoming descriptor is still 13.70, so lowering only the header does not make it newer to the visible selector | Live evidence shows this header change does not lower the public version; mismatch adds loader uncertainty | Reject |
| Matched descriptor/header 13.69 plus field `0x0b=1` | Depends on an unproved interpretation of field `0x0b` | The public/current version remained 13.70 in the live matched-13.69 experiment, so stock 13.70 still is not established as forward restore | Reject |
| Field-`0x0b=1` restore wrapper | Payload can be official, but same-version scheduling depends on the same unproved field interpretation | May simply be skipped; cannot be called a force restore | Retain only as an offline hypothesis |
| Descriptor/header 13.71 overlay | 13.71 is numerically newer than the observed 13.70 and uses the ordinary recovered comparison | Needs a package newer than 13.71 for deterministic normal-path restore | Recommended admission strategy |
| Descriptor/header 13.71 plus patched runtime identity 13.69 | Likely admitted, but the public/current-version source is still not traced completely | Could make official 13.70 newer, but could also leave hidden/persisted state at 13.71 | Reject as unsupported |
| Descriptor/header 13.71 overlay plus descriptor/header 13.72 official-code wrapper | Both transitions use increasing, coherent metadata and the ordinary comparison | 13.72 wrapper removes the overlay using official Garmin code/resources; public runtime mirrors remain 13.70 | Recommended pair |

Versions 13.71 and 13.72 are synthetic admission metadata, not Garmin
releases. The live proof supports mutable descriptor/header versions, but it
does not prove that every synthetic value is accepted or that a resident
anti-rollback rule is absent.

## Recommended overlay artifact

Path:

`artifacts/firmware/quarantine/Forerunner245_1371-flyos-scientific-fly-overlay.gcd.analysis-only.DO_NOT_INSTALL`

- Size: 5,120,675 bytes
- Package SHA-256: `1f7de5ec5ea224ef337c3934e0f7ebc1445f0c6c7b8cb4201180cbeb1772a469`
- Main-stream SHA-256: `5cc69a9045a26996ecabf85cf568d1f46e793ec1aa9a5e2eeb4034a35d39da71`
- Helper SHA-256: `f2351f808c0510baba6aae045867d8a366646511da662a411038426107725e46`
- Main descriptor version: 1371
- Main image-header version at decoded `0x22c`: 1371
- Descriptor field `0x0b`: zero
- Runtime identity mirrors: unchanged official 13.70 values

The candidate changes 456 raw bytes relative to official 13.70. The significant
groups are:

- raw `0xa160`: main descriptor 1370 to 1371;
- raw `0xa392`: main image header 1370 to 1371;
- raw `0x10b86..0x10b89`: display-update call hook;
- decoded main allocation `0x1f3000..0x1f33ff`, installed at
  `0x001f6000..0x001f63ff`: 451-byte scientific-fly renderer, erased fill,
  and its additive repair byte;
- raw `0x4e2299`: main additive repair;
- raw `0x4e229e`: outer checkpoint repair.

The hook at `0x00009a20` changes `04 f0 c0 fb` to `ec f1 ee fa`, branching to
`0x001f6000`. The payload draws a limited-palette scientific fly plate in the
live framebuffer, marks its rectangle dirty, and tail-dispatches Garmin's
original display flush. The exact 1 KiB allocation is erased in the official
image and has zero Ghidra static references. This proves placement and static
control flow, not safe execution on hardware.

## Recommended restore artifact

Path:

`artifacts/firmware/quarantine/Forerunner245_1372-official-payload-restore.gcd.analysis-only.DO_NOT_INSTALL`

- Size: 5,120,675 bytes
- Package SHA-256: `f0a6b316cab5f941125cbe896e6e260196bc0ba4a02f5b475fa55de241522eb1`
- Main-stream SHA-256: `cc3a416039ebee24af7b77f9af71877d5bb44f6272d1cd75f22695e64c9a1960`
- Helper SHA-256: `f2351f808c0510baba6aae045867d8a366646511da662a411038426107725e46`
- Main descriptor version: 1372
- Main image-header version: 1372
- Descriptor field `0x0b`: zero
- Known runtime version tuple, display string, product string, event constant,
  code, and resources: official 13.70 values

Relative to official 13.70, it changes exactly four raw bytes:

| Raw offset | Official | Wrapper | Meaning |
|---:|---:|---:|---|
| `0xa160` | `0x5a` | `0x5c` | Main descriptor 1370 to 1372 |
| `0xa392` | `0x5a` | `0x5c` | Main header 1370 to 1372 |
| `0x4e2299` | `0xc4` | `0xc2` | Main additive repair |
| `0x4e229e` | `0xf7` | `0xf5` | Outer checkpoint repair |

After a successful restore, destination bytes are the official 13.70 decoded
main image except for decoded header byte `0x22c` and the final additive repair
byte. These install at internal address `0x0000322c` and external QSPI address
`0x68916fff`, respectively. The overlay hook and cave payload are absent. All known executable code,
resources, and runtime identity mirrors are official. Based on the live result,
the watch is expected to report 13.70 after boot; that report behavior has not
been tested with the 13.72 wrapper.

The wrapper is not a byte-identical Garmin package and must not be described as
official firmware. Its payload provenance and exact differences are bounded.

## Strict verification and reproduction

The builder and exact verifier are
`tools/garmin-firmware/overlay_version_strategy.py`. Its forward profiles
reconstruct every candidate byte from the pinned official 13.70 package, the
pinned hook, the pinned 451-byte renderer, and the exact code-cave report. The
strict report is:

`artifacts/firmware/analysis/overlay-forward-version-strict-verification.json`

SHA-256: `45210c672081695f681e2d30f86935aa6c1da8deb275496cb3f1b82f41c7c3f9`

The report returns `PASS` only when both complete package hashes and both
decoded main-stream hashes match the pinned constants. The dedicated six-test
suite passes, including one-byte tamper rejection. Both packages also pass the
recovered outer checkpoint and full-image additive checks.

Independent full-image validator reports:

- 13.71 overlay:
  `artifacts/firmware/analysis/flyos-forward-overlay-full-image-validation-1371.json`,
  SHA-256 `6706daf2cec93ae6cc5d9aa3c265d2719693d82daf5fe0cbad82d76171c75638`;
- 13.72 restore wrapper:
  `artifacts/firmware/analysis/official-code-forward-restore-full-image-validation-1372.json`,
  SHA-256 `98f8b50849c70d36f698ea6f718fbfc0eb30550c1851fb9d35a59acc6390cabd`.

Build:

```powershell
python tools/garmin-firmware/overlay_version_strategy.py build-forward `
  --official artifacts/firmware/originals/Forerunner245_1370_GUPDATE.GCD `
  --hook flyos/target/fr245_1370_overlay/build/hook.bin `
  --payload flyos/target/fr245_1370_overlay/build/overlay.bin `
  --xref-report artifacts/firmware/analysis/code-cave-overlay-xrefs-1370.txt `
  --forward-overlay-output artifacts/firmware/quarantine/Forerunner245_1371-flyos-scientific-fly-overlay.gcd.analysis-only.DO_NOT_INSTALL `
  --forward-restore-output artifacts/firmware/quarantine/Forerunner245_1372-official-payload-restore.gcd.analysis-only.DO_NOT_INSTALL `
  --report artifacts/firmware/analysis/overlay-forward-version-candidates.json
```

Verify:

```powershell
python tools/garmin-firmware/overlay_version_strategy.py verify-forward `
  --official artifacts/firmware/originals/Forerunner245_1370_GUPDATE.GCD `
  --hook flyos/target/fr245_1370_overlay/build/hook.bin `
  --payload flyos/target/fr245_1370_overlay/build/overlay.bin `
  --xref-report artifacts/firmware/analysis/code-cave-overlay-xrefs-1370.txt `
  --forward-overlay artifacts/firmware/quarantine/Forerunner245_1371-flyos-scientific-fly-overlay.gcd.analysis-only.DO_NOT_INSTALL `
  --forward-restore artifacts/firmware/quarantine/Forerunner245_1372-official-payload-restore.gcd.analysis-only.DO_NOT_INSTALL `
  --report artifacts/firmware/analysis/overlay-forward-version-strict-verification.json
```

The staging guard contains dry-run profiles `ForwardOverlay1371` and
`ForwardRestore1372`, each pinned to the exact package hash and an observed
device report of 1370. They were not executed or dry-run against the watch
during this offline task.

## Write and brick exposure

Either package is a full system update. Normal processing stages the official
37,120-byte helper through type `0x05` at
`0x68103000..0x68117fff` and the 5,079,040-byte main stream through type `0x0e`
at `0x68118000..0x68616fff`. The helper then erases and rewrites compound
destination `0xaf`:

- internal application flash `0x00003000..0x001fffff`;
- external QSPI `0x68617000..0x68916fff`.

The resident prefix `0x00000000..0x00002fff` is excluded from this copy, but no
Forerunner-245 recovery protocol through that prefix is established. An
interruption after destination erase, a bad hook assumption, a processor fault
in the renderer, or a failed checksum handoff can leave GarminOS and normal USB
unavailable. In that state, the 13.72 wrapper cannot be delivered. Recovery is
unknown and permanent brick is possible.

The 13.72 wrapper is a practical restore only if the 13.71 overlay boots far
enough to provide the normal filesystem updater. It does not reduce the
nonboot failure risk.

## Recommended exact sequence

If the executable experiment is separately approved, the least speculative
admission sequence currently available is:

1. Reverify the connected watch reports 1370 and has no `GUPDATE.GCD`.
2. Rebuild and strictly verify both pinned artifacts offline.
3. Stage only the 13.71 overlay with the guarded `ForwardOverlay1371` profile,
   verify the complete watch-side SHA-256, eject, and accept the update.
4. If it boots, verify the fly, buttons, system menus, and USB read-only before
   any further write.
5. If restoration is desired while normal GarminOS still works, stage the
   13.72 official-code wrapper using `ForwardRestore1372`, verify its complete
   watch-side SHA-256, eject, and accept it.

The safest next experiment overall remains offline emulation or acquisition of
a nonboot recovery path. The sequence above is the safest exact live overlay
strategy found from the evidence currently available; it is not reversible if
the overlay prevents GarminOS from booting.
