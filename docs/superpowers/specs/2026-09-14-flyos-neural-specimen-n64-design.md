# FlyOS Neural Specimen N64 Design

## Scope

This revision replaces the installed GarminOS-resident 32-neuron face with a design-forward 64-neuron FlyOS home face. It fixes the clipped title, removes diagnostic button numbers, replaces the ambiguous paired-lobe outline, adds restrained color, and preserves Garmin system screens so charging and update prompts remain usable.

This is still a GarminOS overlay. It does not replace the bootloader, initialize hardware from reset, intercept Garmin button events, or write persistent state. All package construction remains offline and quarantined. A live watch write is a separate action under the original exact-approval rule.

## Visual system

The face is named **NEURAL SPECIMEN / N64**. All content must remain inside a conservative circular safe area. No top-row content begins left of x=60 or ends right of x=180.

- `PHASE` is centered at y=14 until RTC-to-wall-time conversion is proved.
- `FLYOS // N64` is centered below it.
- A single angular fly-head contour occupies x=54..186, y=48..166. Faceted lateral eye wedges and antennae make the subject clearly insect-like. The contour has no center seam and no paired rounded lower lobes.
- Exactly 64 neuron cells form an 8x8 neural window inside the head. Screen cell `i` always renders model neuron `i`.
- The status rail shows model state plus `HR --`, `MOTION --`, `B --`, or verified values. Invalid optional inputs always display `--` and contribute zero.
- Physical edge captions replace `L1234`: top-left `LUX`, middle-left `WAKE`, bottom-left `CALM`, top-right `PULSE`, bottom-right `SYS`. A held key replaces the footer with its real cause/effect, such as `START > MOTOR BURST`.

Activation magnitude selects glyph density: `.`, `+`, `o`, `@`. Population/sign selects a restrained color role: scaffold, text, excitatory, inhibitory, saturated. The target may bind color roles to raw framebuffer bytes only after offline firmware evidence supports the mapping. Monochrome density remains a complete fallback.

## Neural model

The model contains exactly 64 signed Q5.10 neurons, clamped to `[-16384, 16383]`:

| IDs | Population | Role |
| ---: | --- | --- |
| 0-4 | buttons | LIGHT, START, BACK, DOWN, UP |
| 5 | circadian | RTC-derived phase |
| 6-7 | power | charging/USB and battery drive |
| 8-9 | cardiac | heart-rate tonic and transient |
| 10-11 | motion | movement and stillness |
| 12-23 | central complex | 12-node heading/attention ring |
| 24-39 | mushroom-body association | sparse sensory integration |
| 40-47 | modulation | approach, avoidance, arousal, rest, novelty, circadian, comfort, stress |
| 48-55 | identity/homeostasis | slow identity and memory-like motif |
| 56-63 | action | left, right, forward, pause, seek, groom, sleep, alert |

Updates use integer adds, defined signed shifts, comparisons, and xorshift32. The topology is sparse and deterministic. Identical identity seed, epoch, validity mask, normalized inputs, and buttons must produce byte-identical state. Optional HR, motion, charging, USB, and battery channels remain disabled until each has an image-bound, side-effect-free GarminOS accessor or stable RAM snapshot with validity semantics.

The implementation preserves one 64-element previous-activation copy and commits one target at a time. It must keep the complete target-owned call chain at or below the existing 384-byte stack ceiling.

## Garmin UI coexistence

The current overlay hides every Garmin page because it repaints on every display flush. N64 must render only on a positively identified home/watch-face state or a narrower home-face hook. Menus, alerts, USB/charging screens, and update prompts pass through byte-for-byte unchanged. Framebuffer fingerprinting alone is insufficient for critical-screen detection.

Until home-state detection is proved, holding BACK must suppress FlyOS painting for that flush and reveal the underlying Garmin framebuffer. START remains Garmin's native confirmation key; FlyOS only observes it. A custom update modal may be added only when a verified pending-update signal exists. Garmin's stock update screen is the required fallback.

## Sensor safety

The only live-proven target inputs are the five active-low GPIO PDIR bits and bounded reads of RTC seconds/prescaler. Direct MAX86141, Apollo2, PMIC, I2C, SPI, USB-controller, storage, or flash transactions are prohibited in this revision. Sensor adapters expose values plus validity. Invalid, stale, off-wrist, or unavailable data contributes zero and displays `--`.

## Target and packaging gates

The current secondary allocation has four spare bytes, so N64 requires major size reduction or a newly audited immutable allocation. Every used interval must pass erased-byte, instruction, literal, pointer, Ghidra-reference, section, metadata, overlap, linker-bound, full-image, and executed-branch checks against the pinned 13.70 image.

Unicorn must prove all writes stay in the supplied framebuffer or target stack; all hardware reads use an explicit allowlist; guards preserve the original dispatch behavior; non-home frames are unchanged; all 64 cells correspond to their neurons; and stack use remains at most 384 bytes. The quarantined candidate and official-code restore wrapper must be exactly reconstructed, hashed, independently reviewed, and excluded from the live staging script.

## Acceptance criteria

1. Host tests prove deterministic 64-neuron behavior, valid-mask semantics, clamping, and button drives.
2. Golden previews show the new safe-area layout, 64 unique cells, clearer fly-head shape, contextual key labels, charging/USB/update/pass-through states, and unavailable sensors.
3. Color roles have proven raw values or the target remains monochrome while host previews retain intended colors.
4. Garmin critical screens pass through unchanged under a proved state signal; BACK pass-through also works.
5. Target builds and emulation pass with at most 384 target-owned stack bytes and no unapproved reads/writes.
6. Offline package/restore artifacts pass the complete reconstruction and validation suite.
7. Nothing is copied to the watch until the exact final write is separately approved.
