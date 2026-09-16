# FlyOS N64 Atlas Shell Design

## Status and scope

This design was approved in chat on 2026-09-15. It defines the next
GarminOS-resident FlyOS revision for the Forerunner 245 non-Music 13.70
application. The revision is intended to address three observed failures in
synthetic version 13.76: ordinary button presses can reach Garmin, USB
disconnect can leave a charging frame on the display, and the 64-neuron
presentation lacks a clear anatomical and interaction model.

This remains an overlay and input interposer inside GarminOS. It does not
replace the resident bootloader, initialize the hardware from reset, prove
arbitrary unsigned boot, or provide nonboot recovery. This design authorizes
offline implementation and verification only. Packaging, staging, and a live
watch write remain separate actions under the project's exact-artifact safety
gate.

## Evidence behind the revision

The installed candidate is pinned by its complete package and segment hashes.
Offline execution of that exact binary reproduces the input failure:

- while cached USB state is `3` or `4`, START, DOWN, and UP are rendered as
  FlyOS inputs while every event phase is also published to Garmin;
- LIGHT and BACK are always published to Garmin;
- a native LIGHT or BACK transition can make a Garmin view first-visible, after
  which later controlled keys also fail open to Garmin; and
- no evidence shows Garmin overwriting FlyOS's ownership halfwords.

The charging report is consistent with a display-lifecycle failure rather than
neural state, but its exact live cause remains unresolved.
The installed renderer has no charging graphic and discards its `usb_ms`
argument. When called on a stable home it clears all 57,600 framebuffer bytes.
Garmin's USB detach path changes the cached state to enum `2` but has no direct
event publication analogous to the attach paths. Because FlyOS executes only
inside Garmin's display-flush path, a removed charging view without a following
flush can leave the old pixels resident in the framebuffer and MIP panel.
Static evidence cannot yet distinguish that case from a charging modal that
remains first-visible, so the implementation must preserve the strict view
gate.

## Feasibility gate

The installed target has only 27 unused primary bytes and four unused
secondary bytes. Before feature implementation, the plan must produce section
size upper bounds and a verified destination for every hook, trampoline,
table, literal, and state value. Implementation proceeds only if replacement
or repacking creates sufficient room inside already proved intervals, or a new
interval passes the complete allocation proof. No candidate package may be
built from a projected-overflow layout.

## Interaction architecture

### Single input owner

At phase zero, FlyOS owns a physical key when two bounded view-list scans agree
that the normal watch-face node is the first visible node. USB cache state does
not change that decision. Every later phase of an owned sequence, including
long, repeat, and release phases, remains FlyOS-owned even if the view changes.
Garmin must receive zero events from that sequence.

At phase zero, an empty, malformed, cyclic, longer-than-eight, changing, or
non-home view selects Garmin ownership. That decision remains latched through
release even if the home subsequently appears. A newly visible critical screen
therefore affects subsequent sequences only. This preserves native update,
recovery, alert, and settings screens without identifying them by framebuffer
contents.

The five final halfwords in Garmin's key records may be used only after the
existing static-access proof is extended to LIGHT and BACK. The implementation
plan must assign every ownership, pulse, chord, pending-mode, system-mode, and
excursion bit to exact audited halfwords; define valid, complement-protected,
and invalid encodings; and prove atomic transitions under concurrent key and
display execution. Unrecognized or partial encodings select Garmin ownership.
Phase-zero stale-sequence cleanup must never erase the global mode latch. No
new writable global data or heap allocation is allowed.

### Deliberate Garmin system mode

LIGHT plus BACK is the only route from a stable FlyOS home to ordinary Garmin
navigation. Both entry-chord sequences remain FlyOS-owned through release.
Holding both keys displays `SYSTEM // HOLD`; a verified long-hold sets
`SYSTEM_PENDING` while both GPIOs remain active. Only after both key sequences
release does the latch become `SYSTEM`, so Garmin can never receive an orphan
repeat or release phase. The target duration is approximately two seconds, but
the implementation must measure and document the pinned Garmin phase timing
rather than assume it.

In `SYSTEM`, every newly started sequence is Garmin-owned through release. The
latch records when a non-home Garmin view has been observed and clears only
after that excursion returns to a two-scan stable home with all keys released.
No chord activation or latch transition changes the owner of an in-progress
sequence. `GARMIN // SYSTEM` is visible while the latch is active and the
stable home is first-visible; non-home Garmin screens remain untouched.
Malformed latch state or reset fails open to Garmin. A native update prompt is
preserved only after a pinned fixture proves that the observed prompt
classifies as a non-home first-visible node.

### FlyOS button meanings

The physical layout uses names rather than diagnostic numbers:

| Physical key | FlyOS action | Model input |
| --- | --- | --- |
| top-left LIGHT | `LUX` | neuron 0, sensory gain |
| top-right START | `BURST` | neuron 1, motor/arousal burst |
| bottom-right BACK | `MODE` | neuron 2, state/view modulation |
| bottom-left DOWN | `CALM` | neuron 3, inhibitory drive |
| middle-left UP | `PULSE` | neuron 4, excitatory drive |

An idle face shows restrained callouts aligned with the physical key heights.
A press highlights its input neuron in amber and replaces the footer with the
explicit cause and effect, for example `START // MOTOR BURST`. No numeric key
labels appear.

## USB detach redraw

The implementation may hook the confirmed USB state-machine transition only
after proving the exact overwritten instructions, trampoline, return address,
control-flow predecessors, and allocation bounds against the pinned image. The
hook must not draw, touch the framebuffer, block, poll hardware, or perform bus
I/O.

On one confirmed `3/4` to non-`3/4` transition, the hook:

1. observes Garmin's cache update;
2. verifies BACK is released;
3. requires two stable-home scans to agree; and
4. attempts one nonblocking event `0x50` submission to the established UI
   queue using ordering proved safe relative to modal teardown.

The hook never draws. If home is unstable, a modal is first-visible, or queue
submission fails, a separately proved UI or timer callback must provide a
bounded, deduplicated retry using audited pending storage. Retry stops after
one successful submission, a new USB epoch, or a fixed attempt limit. At most
one redraw may be successfully queued for each detach edge.

A candidate may claim the disconnect defect fixed only after proving which
observed case occurs. If detach leaves home first-visible, the queued redraw
must replace the complete stale frame. If a charging modal remains
first-visible, implementation requires a separately verified, nonblocking
native modal-dismiss or refresh path; otherwise the candidate is rejected as
not fixing the reported defect. The USB worker never renders directly, and no
modal framebuffer is modified.

This revision does not invent a charging sensor or describe the native page as
authoritative after detach. A custom FlyOS charging icon requires a separately
proven, side-effect-free power-state cache or accessor.

## Drosophila neural atlas

The renderer replaces the generic enclosing polygon and 8-by-8 badge with a
population-based neural atlas. The image uses a broken, angular fly-head
cutaway with antenna roots and lateral eye marks. It has an open inferior edge
and avoids paired rounded lower lobes.

All 64 model neurons remain individually visible and retain a stable mapping:

| IDs | Screen structure |
| ---: | --- |
| 0-11 | sensory, power, cardiac, and motion afferent rim |
| 12-23 | central-complex ring |
| 24-39 | paired mushroom-body columns and association branches |
| 40-47 | modulatory midline cells |
| 48-55 | identity and homeostasis core |
| 56-63 | descending action fan |

The layout may use compact formulas and small coordinate tables, but a host
manifest must record the final `(neuron, x, y)` mapping plus a pairwise-disjoint
dynamic pixel mask for every neuron. With all other state fixed, toggling one
activation may change only that neuron's mask, and every nonzero level must
produce a visible change. Static tracts may not occupy or obscure the dynamic
masks. Fixed gray tracts show the major ring, column, and descending paths;
they are visual scaffold rather than a claim that every simulated edge is
drawn.

Activation magnitude selects dot, cross, outline, or filled glyph density.
Inactive scaffold is gray, positive activation is green/cyan, negative
activation is magenta, and saturated sensory/action activity is amber. Every
meaning remains distinguishable by density if viewed without color.

The one-line header is `FLYOS // N64`. The existing unexplained phase dot is
removed. State names are spelled `REST`, `MOVE`, `AROUSE`, or `QUIET`; invalid
sensor values are omitted rather than rendered as plausible data. The atlas,
callouts, status rail, and animation must stay within a 98-pixel radius around
screen center, leaving two pixels of margin inside the established 100-pixel
limit. The visual build must retain enough flash margin for the input and
detach fixes rather than consuming the entire secondary allocation.

## Runtime data flow

1. The key hook classifies the view at phase zero and latches one owner for the
   complete physical sequence.
2. Owned phases update only the audited key-record halfwords. Press,
   armed-threshold, release acknowledgement, and mode-transition changes may
   post a nonblocking watch-face redraw request; other phases do not flood the
   queue.
3. The display hook executes only on Garmin's normal flush path. It validates
   the framebuffer and first-visible home, samples the proven GPIO/RTC/battery
   caches, reconstructs the deterministic Brain64 state, renders the complete
   FlyOS frame, marks the full frame dirty, and resumes Garmin dispatch.
4. A non-home display flush is passed through without framebuffer writes.
5. The detach hook can request step 3 but cannot execute it directly.

Heart rate, motion, ambient light, and charging remain invalid until each has
an image-bound, side-effect-free cache with explicit freshness semantics. Their
model inputs remain zero. Button and battery inputs continue to use the already
documented validity rules.

## Failure handling and recovery properties

- View-classification uncertainty always selects Garmin ownership and preserves
  the underlying screen.
- A key-event queue failure drops its cosmetic redraw request without blocking
  the key worker. A detach queue failure records only the audited pending state
  used by the bounded UI-context retry; the USB worker still never blocks.
- An owned key sequence cannot change owners mid-press.
- A native sequence cannot become owned mid-press.
- The system chord has a visible armed state, cannot be triggered by either key
  alone, is consumed through both releases, and changes mode only between
  sequences.
- Update and recovery screens proven to classify as non-home remain accessible
  because a non-home first-visible node bypasses both renderer and ownership.
- The official-code restore wrapper remains mandatory for every candidate.
  Recovery still depends on a booting GarminOS because no nonboot recovery path
  is known.

## Verification gates

### Host and model tests

- Preserve deterministic Brain64 parity and all 64 direct neuron mappings.
- Add tests for every key's neural drive and displayed action label.
- Prove color-independent glyph meaning and safe-radius compliance.
- Generate idle, five pressed, chord-armed, system-mode, USB, charging,
  update-pass-through, and malformed-view previews with SHA-256 manifests.
- Require human approval of the generated contact sheet before packaging. The
  manifest must contain IDs `0` through `63` exactly once, pairwise-disjoint
  dynamic masks, a fixed mapping hash, and every possible glyph/callout extent
  inside radius 98.

### Instruction-level emulation

- Exercise every key and every event phase on home, non-home, USB states
  `0/2/3/4`, BACK-held, changing-root, queue-null, and queue-full fixtures.
- Prove a home-owned sequence publishes zero Garmin events and a native
  sequence replays the exact original instructions and events.
- Prove the chord cannot trigger from one key, enters only after the verified
  threshold and both releases, and never publishes a suffix-only or orphan
  event sequence. Prove system mode clears only after a non-home excursion
  returns to stable home with all keys released.
- Prove reset, garbage, complement mismatch, and partial mode-state writes fail
  open without erasing a valid per-sequence owner.
- Seed a framebuffer with charging pixels, perform the detach transition, and
  prove exactly one eligible queue event followed by a complete 57,600-byte
  replacement on the next display hook.
- Cover `3->2`, `4->2`, `3<->4`, non-mass-to-non-mass, duplicate observations,
  modal-at-edge then later-home, queue-full retry, and a strict maximum of one
  successful redraw per detach edge. Non-home and unstable cases must preserve
  the frame byte-for-byte.
- Prove the observed native update prompt is non-home before claiming it is
  preserved by the classifier.
- Constrain all writes to the supplied framebuffer, target stack, and exact
  audited key halfwords. Maintain the existing 384-byte target-owned stack
  ceiling.

### Static placement and packaging

- Re-run erased-byte, instruction, literal, pointer, Ghidra-reference, section,
  metadata, overlap, executed-branch, linker-bound, and full-image checks for
  every changed interval.
- Record exact used and remaining bytes for every section and reject the build
  if the detach trampoline, input state machine, and renderer do not fit wholly
  inside verified intervals without overlap.
- Reconstruct and independently hash the synthetic candidate and official-code
  restore package. Keep both outside the public repository.
- Keep the staging guard locked. A live write requires a separate disclosure of
  exact filenames, sizes, SHA-256 hashes, write location, brick risk, recovery
  limits, and restore procedure.

## Acceptance criteria

1. For every valid two-scan stable-home fixture, each ordinary sequence is
   fully FlyOS-owned and publishes zero Garmin events, whether USB is connected
   or disconnected. Malformed, unstable, and non-home phase-zero fixtures pass
   the exact original sequence to Garmin.
2. Garmin navigation is available through the deliberate long-hold chord and
   through critical screens proved to be native first-visible views.
3. The candidate either proves and fixes the stale-home and surviving-modal
   detach cases, or live evidence excludes one case and the remaining case is
   fixed. It never covers or directly modifies a surviving modal.
4. The face presents 64 uniquely mapped neurons in a recognizable scientific
   fly-neural atlas with clear button feedback and no clipped pixels.
5. All host, emulator, static-placement, stack, package, and restore checks pass
   before any live-write proposal is created.
