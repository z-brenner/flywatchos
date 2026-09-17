# Atlas-shell 13.82 flash candidate (offline analysis inputs)

This document maps the offline-constructed **13.82 atlas-shell candidate** and its
matched **13.83 official-code restore** to the eight write-proposal preconditions
in [`recovery.md`](recovery.md). It is disclosure material for a flash the
project owner performs manually and separately. Nothing here authorizes,
stages, or performs a write.

The two packages are quarantined analysis objects: `packaging_allowed:false`,
`live_staging_allowed:false`, and both filenames carry the
`.gcd.analysis-only.DO_NOT_INSTALL` suffix. They are the direct successor to the
13.76/13.77 N64-controls pair and were built, validated, and hashed with the
same proven pipeline.

## Package identity

| Package | Version metadata | Size | SHA-256 |
|---|---|---|---|
| Candidate (atlas-shell overlay) | synthetic 13.82 | 5,120,675 | `7bcfc380c2d6eb9ceb136ae03d19b016981bf484e8bc559455adcd958e8df4f9` |
| Restore (official 13.70 code) | synthetic 13.83 | 5,120,675 | `63461f57daa5f238100a8ee9dda6531fbbcbd3bc2103b54de308154615795c37` |

The candidate is the official non-Music 13.70 image (`8ebefacf…`) with four
patched regions and the checkpoint/version repairs that change entails; the
restore is the same official 13.70 application and resources carried behind
synthetic 13.83 forward-version metadata (only four raw bytes differ from the
version-only rewrite of the official main).

## Preconditions (recovery.md §"Preconditions for any future write proposal")

**1. Exact bytes/artifact and SHA-256.** As tabled above. The candidate's decoded
main stream is `cef71ca3…`; the restore's is `488dbfc6…`. Both decode back
byte-for-byte to their inputs: the candidate to the atlas-shell payload plus the
official base, the restore to the official 13.70 main with only the version
field (and its trailing additive byte) changed.

**2. Target component, region, partition, expected previous contents.** The
candidate patches only the GarminOS **application** main stream (`0x02bd`):
- display hook at `0x00009a20` (4 bytes; official `04f0c0fb` → branch to the FlyOS entry),
- pre-publisher key hook at `0x0000fa48` (6 bytes; official `30b5c0ebc002` → branch to `flyos_key_event`, ending in a Thumb `NOP`),
- primary code envelope at `0x001f6000` (856 bytes into a 1 KiB erased allocation),
- secondary code envelope at `0x001fa400` (1904 bytes into a 2 KiB erased allocation),
plus one additive-repair byte at `0x001f63ff` and the descriptor/header version
words. The two envelopes were `0xFF`-erased in the official image; the helper
`0x0505` stream is byte-identical to the official. When the resident helper
copies the staged payload (type `0x0e` → destination type `0xaf`), the updater
rewrites internal application flash `0x00003000..0x001fffff` and external QuadSPI
`0x68617000..0x68916fff`. The resident prefix below `0x00003000` (the bootloader)
is **not** part of this copy target. Region membership was reconfirmed against
this package with `gcd_candidate_verify.py`.

**3. Validation performed by the receiving loader.** Only the GarminOS
**application-side full-image checks** are reproduced offline and confirmed
passing: identical record layout to the official package, unchanged main-stream
declared length, main-stream byte sum ≡ 0 (mod 256), all five outer GCD
checkpoints valid (prefix sums ≡ 0 mod 256), and a full-image (non-`GDELTA01`)
payload. The **resident loader** that authenticates, applies version policy,
installs, and launches the image is not available and is **not** modeled; a
passing offline report is not evidence of device acceptance or code execution.

**4. Predicted behavior for interruption, checksum failure, signature failure.**
- *Interruption:* an interrupted application copy leaves the internal/external
  application regions partially written; recovery.md records this as an
  **unresolved** recovery risk with no demonstrated nonboot recovery path.
- *Checksum failure:* the modeled application-side additive checks are all
  satisfied, so this package should not be rejected by those checks; a package
  that failed them would be rejected before any write.
- *Signature failure:* no blocking signature check on this MAIN application
  package class was observed, and four in-class overlays (13.72–13.76) were
  accepted and ran. This is empirical, not a proof that the resident loader
  performs no signature validation; that path is unmodeled.

**5. Known entry sequence for recovery, demonstrated without writing.** None
newly demonstrated here. Recovery still depends on GarminOS and the normal USB
update service remaining reachable so the restore package can be offered as a
forward-version update. No preboot/nonboot entry sequence is demonstrated.

**6. Exact official restore artifact and its SHA-256.** The matched rollback is
the **13.83 official-code restore** (`63461f57…`), which carries the official
13.70 application and resources. Its underlying official artifact is
`Forerunner245_1370_GUPDATE.GCD` (5,120,675 bytes, SHA-256
`8ebefacf6bcc00bec0fb271596abfb9618f9a3114d32b3a106fbd27d5a366adc`). The restore
is byte-identical to the official code behind synthetic 13.83 metadata so that a
watch still on the normal updater treats it as the newest image.

**7. Application only, or also bootloader.** **Application only.** The copy
target is internal application flash `0x00003000..0x001fffff` plus external
QuadSPI `0x68617000..0x68916fff`. The resident bootloader below `0x00003000` is
not written. No restore artifact here can repair a damaged resident bootloader,
option bytes, or identity/calibration data.

**8. Explicit brick probability with evidence and unresolved assumptions.** This
candidate is **in-class with four prior overlays (13.72, 13.73, 13.74, 13.76)
that were flashed and ran**, hooks only the same display and key sites, and
contains no Task-5 USB-detach hooks or any other elevated-risk context.
However, recovery.md still records **no demonstrated nonboot recovery** for this
device: if the resident loader rejects, or an application copy is interrupted in
a way the surviving loader cannot re-drive, the outcome could range from a
settings-level recovery to a non-enumerating watch. The residual brick risk is
**low but not zero and not eliminable with current evidence**; the safety of
prior flashes is encouraging precedent, not a recovery guarantee. Do not
overstate it.

## What this build does and does not deliver (behavioral)

Confirmed by Unicorn emulation of the exact linked payload:

- **Yes — 64-neuron atlas renderer.** All 64 neuron cells verified (disjoint 5×5
  masks inside the 98 px safe circle, exact densities/colours, nothing else lit);
  runtime stack bound 384 bytes.
- **Yes — five-key FlyOS button ownership** on a stable HOME. All five keys
  (LIGHT, START, BACK, DOWN, UP) belong to FlyOS when two bounded scans agree the
  normal watch face is the first visible Garmin view; each owned press posts the
  face's normal `0x50` redraw.
- **No — Garmin system chord / system session.** The overlay never sets
  `FLY_UI_CHORD_ARMED` or `FLY_UI_SYSTEM`; nothing on this image arms a chord or
  opens a system session.
- **No — USB-detach redraw fix.** Only `FLY_UI_USB` is set from cached USB state;
  the delayed post-detach redraw (>10 s) is **not** fixed and persists.
- **Button behaviour changes vs the installed 13.76 controls overlay.** The
  installed 13.76 build owned three keys (START/DOWN/UP) and left LIGHT/BACK to
  Garmin. This 13.82 build owns all five keys on a stable HOME, so LIGHT's
  backlight and BACK's Garmin navigation are unavailable while FlyOS owns them.

## Boundary

These are offline analysis inputs only. The actual write is a separate manual
act by the project owner; this repository does not stage or perform it, and
`tools/live-proof/stage-gupdate.ps1` is not part of producing or validating these
packages.
