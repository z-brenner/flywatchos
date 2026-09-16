# FR245 atlas-shell controls

How the FlyOS overlay decides who owns a button press on the pinned FR245
13.70 application image. Everything here is proved offline, by emulating the
exact linked binary in `tools/garmin-firmware/emulate_n64_atlas_shell.py`. No
statement here was obtained from a watch, and nothing here authorizes a write
to one.

## The five keys

Garmin's key worker dispatches a key index and a phase. The physical order is:

| Index | Key | FlyOS action | Model input |
| ---: | --- | --- | --- |
| 0 | top-left LIGHT | `LUX` | neuron 0, sensory gain |
| 1 | top-right START | `BURST` | neuron 1, motor/arousal burst |
| 2 | bottom-right BACK | `MODE` | neuron 2, state/view modulation |
| 3 | bottom-left DOWN | `CALM` | neuron 3, inhibitory drive |
| 4 | middle-left UP | `PULSE` | neuron 4, excitatory drive |

Phases are `0` press, `1` release, `2` long, `3` very long, `4` repeat.

## What changed from the installed 13.76 image

The installed candidate owned only START, DOWN and UP, and leaked in three
ways. All three are now closed:

- **Cached USB state `3`/`4` no longer escapes ownership.** 13.76 rendered
  those presses as FlyOS input *and* published every phase to Garmin.
- **LIGHT and BACK are no longer passed through unconditionally.**
- **A held BACK line no longer vetoes ownership**, nor blanks the FlyOS face.
  BACK is a FlyOS key, so holding it shows its own callout.

## One owner per physical sequence

At phase zero, and only at phase zero, the overlay classifies the view and
latches one owner for the whole sequence:

- a **stable home** gives the key to FlyOS (`FLY_HELD`);
- **anything else** gives it to Garmin (`GARMIN_HELD`) and replays the original
  event.

Every later phase consults only the latched byte. A sequence that started as
Garmin's stays Garmin's even if the watch face reappears mid-press, and a
sequence that started as FlyOS's stays FlyOS's even if the view changes.
Garmin receives either every phase of a sequence or none of them, never a
suffix.

On release from a stable home the byte becomes `FLY_PULSE`, which lights that
key's callout for exactly one rendered frame; the display hook then clears it
back to `FLY_IDLE`. A late or duplicated phase arriving after release is
swallowed rather than leaked.

## The tri-state view classifier

`stable_view()` runs the bounded scan twice, bracketed by root reads, and both
observations must agree. It returns one of three things:

| Result | Meaning |
| --- | --- |
| `FLY_VIEW_INVALID` (0) | empty, malformed, cyclic, longer than eight nodes, or changing under the scan |
| `VIEW_NON_HOME` (1) | a structurally sound list whose first visible node is not the watch face |
| anything else | the first-visible watch-face node itself |

`INVALID` means *unknown*, never *not home*, and it always fails open to
Garmin. Returning the node as the third case avoids a struct return entirely:
real nodes are four-byte aligned and far above 1, so the sentinels cannot
collide with one.

### The `update_prompt` fixture is an unproved placeholder

The design says a native update prompt is preserved only once a pinned fixture
proves the observed prompt classifies as a non-home first-visible node. **That
proof does not exist.** Task 1's `observed_update_prompt_non_home` gate FAILED;
its recorded evidence is literally `{"proved_non_home": false,
"observed_callback": null}`.

The emulator's `update_prompt` fixture therefore uses
`UNPROVED_UPDATE_PROMPT_CALLBACK`, a deliberately synthetic, grep-able constant.
It exists only to give the classifier a structurally valid NON_HOME list to
classify; the exact callback value is immaterial to that assertion. **It is not
a proved identity for the real update prompt and must never be cited as one.**
Preservation of real native screens rests on the classifier's general
behaviour, not on this fixture.

## Where the state lives

Each key's audited final halfword at record `+0x36` is two independent
complement-protected bytes (`state.h`):

| Byte | Owner | Values |
| --- | --- | --- |
| `+0x36` local | this task | `FLY_IDLE`, `FLY_HELD`, `FLY_PULSE`, `GARMIN_HELD` |
| `+0x37` mode | LIGHT only: `FlySystemMode`. START only: `FlyDetachMode` (Task 5). Others must be zero. | |

Each byte holds its value in bits 0-3 and the one's complement in bits 4-7, so
`fly_state_word(local, mode) == fly_state_byte(local) | (fly_state_byte(mode) << 8)`.
The two bytes are addressed separately, which is what makes the subsystems
independent: ownership writes `+0x36`, the system session writes LIGHT's
`+0x37`, and neither performs a read-modify-write of the other's nibble. An
aligned byte store is atomic on this core. Task 5's detach state at START's
`+0x37` is never addressed by this task at all.

Every value the target stores is a compile-time constant, so the complement
encoding folds to an immediate and costs no code. Validation is a comparison
against the whole expected byte, which is stricter than decoding a nibble and
checking its complement separately.

### Reset, garbage and legacy encodings

A phase-zero press rewrites its own ownership byte before deciding anything, so
a reset (`0x00`), erased (`0xFF`), garbage, or legacy 13.76 word
(`0xFF00`/`0x5EA1`/`0x5DA2` — all of which fail the complement check) is
normalised by the next press on that key. Because only that one byte is
touched, this cleanup can never erase a global latch or disturb another key's
in-progress sequence.

## Constraints this path holds

- No writable static storage, no heap, no peripheral-bus transaction, no
  framebuffer write from the key worker, and no blocking queue call. The key
  worker's only writes are its own stack and one audited byte.
- A queue that is null, full, or returns any result code never changes
  ownership; the cosmetic redraw request is simply dropped.
- Target-owned stack stays at or below the pinned 384 bytes. The deepest chain
  is `n64_overlay_then_flush` -> `fly_brain64_reconstruct` -> `fly_brain64_step`
  and is *exactly* 384, so the display hook has no slack: physical GPIO lines
  and owned bits are merged in one `button_bits()` callee specifically to keep
  its frame at 184 bytes. Any change to the display hook must re-check
  `overlay.su`, not just the section sizes.
