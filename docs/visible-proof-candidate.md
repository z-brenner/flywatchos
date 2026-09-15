# Offline visible-proof candidate

## Scope

This experiment changes one English text resource in a local copy of the
official non-Music 13.70 update. It does not replace startup code, initialize
hardware, or execute custom code. It was built and checked without accessing
the watch. The resulting file is quarantined analysis material and is not
approved for installation.

## Why this resource was selected

The decoded type-`0x02bd` main stream contains exactly one ASCII
`Software Version` string at file offset `0x43eaa4`, mapped by the established
external segment mapping to runtime address `0x04841aa4`. It appears in this
contiguous resource context:

```text
Cancel\0\0Software Version\0\0\0\0Unit ID\0Bluetooth MAC Address\0
```

The same image contains exactly one `About` string at file offset `0x442524`
(runtime `0x04845524`) in this System-settings label cluster:

```text
Backlight ... Data Recording ... Reset ... Disable Logging\0About\0\0\0Smart ... USB Mode ...
```

Garmin's Forerunner 245 manual documents the route **watch face -> hold UP ->
System -> About** and says that page presents the unit ID and software version.
The unique label, its neighboring fields, the System-menu `About` label, and
the manual's field list align. This is strong evidence that changing this
resource changes a label visible on the About page while leaving Garmin's
existing renderer and display initialization in place.

The non-Music 3.10 main stream independently contains the same unique
`Software Version`/`Unit ID`/`Bluetooth MAC Address` sequence at `0x3dca88`
and a unique `About` label at `0x3dec8c`. Its SHA-256 is
`3225c50585503d331a9c0ee8faf342241207dd98825f4f0f9cf3fa23831c54ba`.
This cross-version stability supports the resource classification.

The exact indirect localization lookup and rendering call site has not been
recovered. Consequently, the display result is strongly inferred rather than
confirmed by execution or a direct code xref. The experiment does not claim
that the string is shown at boot; it is expected only after navigating to the
documented About page.

Source: [Garmin, Viewing Device Information](https://www8.garmin.com/manuals/webhelp/forerunner245/EN-US/GUID-E131EDC8-BB20-4F2B-AF7B-E6EC45B107E0.html).

## Exact patch

The input is
`artifacts/firmware/originals/Forerunner245_1370_GUPDATE.GCD`, size 5,120,675
bytes, SHA-256
`8ebefacf6bcc00bec0fb271596abfb9618f9a3114d32b3a106fbd27d5a366adc`.
Its decoded main stream hashes to
`b45be1baf98999af10f073bef52b284beb2aea6abbb7cde2ffa59fb6bcedeab6`.

The fixed edit is:

| Property | Original | Candidate |
|---|---:|---:|
| ASCII | `Software Version` | `FLY LIVES 2ALIVE` |
| Length | 16 bytes | 16 bytes |
| Byte sum | 1,617 | 1,105 |
| Byte sum modulo 256 | 81 | 81 |

`FLY LIVES 2ALIVE` is intentionally odd. The visible prefix states the proof,
while the suffix makes the additive low byte equal to the original string.
That preserves both confirmed modulo-256 check layers without modifying a
second, semantically unknown byte.

All 16 bytes at raw GCD offsets `0x448d1a..0x448d29` change. The terminating
NUL and every byte outside that 16-byte allocation remain identical. No
descriptor, version field, record size, checkpoint byte, executable
instruction, or other payload byte changes. The candidate remains version
13.70; no effective-version value was guessed or reduced.

## Quarantined artifact

The reproducible output is deliberately named with an unrecognized suffix:

```text
artifacts/firmware/quarantine/Forerunner245_1370_fly-visible.gcd.analysis-only.DO_NOT_INSTALL
```

Its SHA-256 is
`b6e61518890d8082d96baf9bd89dcb131317f40060136093c9250e343a8ab4ba`.
The mutated decoded main stream SHA-256 is
`f6224af2283bca90ad17cea11366c92ed7b00be567da633f15b50d2432d2346f`.
Do not rename this file to `GUPDATE.GCD`, copy it to the watch, or submit it to
Garmin software.

The complete byte-diff report is
`artifacts/firmware/quarantine/visible-proof-report.json`, SHA-256
`6874e052a16de2c59513a5f0c26a73d9d11865ad3c32f29025de183d9d4fb259`.
The independent full-image validation report is
`artifacts/firmware/quarantine/visible-proof-validation.json`, SHA-256
`938f66109a7eac2e51e33bc2c1b80369e93fd24093a60ace1e06ce72f29a5e0a`.
The independent package-layout/diff verifier report is
`artifacts/firmware/quarantine/visible-proof-candidate-verification.json`,
SHA-256
`8112702ac52b2ca8bce861734741c98608bd83d3dda255464fad413b90f40653`.

## Reproduction and checks

```powershell
python tools/garmin-firmware/build_visible_proof_candidate.py `
  artifacts/firmware/originals/Forerunner245_1370_GUPDATE.GCD `
  artifacts/firmware/quarantine/Forerunner245_1370_fly-visible.gcd.analysis-only.DO_NOT_INSTALL `
  --report artifacts/firmware/quarantine/visible-proof-report.json

python tools/garmin-firmware/full_image_validator.py `
  artifacts/firmware/quarantine/Forerunner245_1370_fly-visible.gcd.analysis-only.DO_NOT_INSTALL `
  --report artifacts/firmware/quarantine/visible-proof-validation.json

python tools/garmin-firmware/gcd_candidate_verify.py `
  artifacts/firmware/quarantine/Forerunner245_1370_fly-visible.gcd.analysis-only.DO_NOT_INSTALL `
  --official artifacts/firmware/originals/Forerunner245_1370_GUPDATE.GCD `
  --report artifacts/firmware/quarantine/visible-proof-candidate-verification.json
```

The builder refuses any source other than the pinned official package and
asserts the source main-stream hash, resource offset, resource uniqueness,
both resource contexts, output directory, and filename suffix. It verifies:

- unchanged file length and unchanged bytes outside the 16-byte target;
- byte-identical outer checkpoint records and valid outer prefix sums;
- a non-delta main image whose additive low byte remains zero;
- the confirmed GarminOS application-side full-image checks pass;
- the replacement occurs exactly once and the original label is absent.

These checks do not model the resident loader, authentication, version policy,
installation behavior, rollback, or recovery. Passing them does not show that
the watch would accept the package and does not demonstrate arbitrary code
execution. A device-side test would be a firmware write and needs a separate,
exact approval under the project's safety rules.
