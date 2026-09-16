# Forerunner 245 13.70 N64 controls target

## Scope

This target is an offline link-and-emulation experiment for the pinned
Forerunner 245 non-Music 13.70 application. It does not replace GarminOS or the
resident loader. The build script cannot create or stage a GCD and does not
access the connected watch.

The target fixes two observed problems in the installed synthetic 13.74 N64
overlay:

- START, DOWN, and UP events continued into Garmin's event publisher and could
  navigate away from the FlyOS face; and
- the earlier rectangular neural field and peripheral labels did not make the
  round-screen boundary or button effects clear enough.

## Placement

| Segment | Runtime range | Used | Spare | Purpose |
| --- | --- | ---: | ---: | --- |
| Display hook | `0x00009a20..0x00009a23` | 4 bytes | 0 | one Thumb `BL` |
| Key hook | `0x0000fa48..0x0000fa4d` | 6 bytes | 0 | one Thumb `B.W` plus `NOP` |
| Primary | `0x001f6000..0x001f63e3` | 996 bytes | 27 | entry, bounded view scan, key policy, compact primitives |
| Repair byte | `0x001f63ff` | 0 bytes | reserved | package checksum repair only |
| Secondary | `0x001fa400..0x001fabfb` | 2,044 bytes | 4 | trampoline, queue adapter, packed Brain64, renderer and tables |

The display hook keeps the installed target's previously audited location.
The key hook replaces the first six bytes of the pinned key-event builder at
`0x0000fa48`. Those original bytes are exactly:

```text
30 b5 c0 eb c0 02
```

They decode as `push {r4,r5,lr}` followed by
`rsb.w r2,r0,r0,lsl #3`. The pass-through trampoline replays both instructions
and transfers to Thumb address `0x0000fa4f`, which resumes at image offset
`0x0000fa4e`.

## Why interception occurs before publication

Static analysis of the pinned application found 13 independent subscribers to
the Garmin key event. Their callback return values are ignored by the
publisher, so consuming an event in a view callback cannot prevent other
Garmin subscribers from acting on it. The new hook therefore makes its decision
at the key-event builder before publication.

LIGHT and BACK always pass through the original builder. START, DOWN, and UP
are owned only when all of the following are true at press phase zero:

1. two bounded scans agree that the normal watch-face node is the first visible
   view;
2. BACK is not physically held; and
3. the cached USB state is neither confirmed mass-storage value 3 nor 4.

Ownership is latched for the complete press/long/repeat/release sequence. A
sequence that begins outside the home view remains Garmin-owned even if the
home view later appears. A sequence that begins on the home view remains
FlyOS-owned even if a modal view appears before release. Holding BACK while
pressing a controlled key is an explicit escape chord that leaves the sequence
to Garmin.

Every new phase-zero press clears a prior owned or acknowledgement value before
the home/USB/BACK decision. This prevents an interrupted or stale sequence from
causing later phases of a native Garmin press to be consumed.

## State storage and redraw

The pinned key workspace begins at `0x1ffdbbc8` and contains five `0x38`-byte
records. Static access analysis found the final halfword of each record unused
by the stock image. The target uses only those exact halfwords:

| Key | Physical control | Status address |
| ---: | --- | ---: |
| 0 | LIGHT | `0x1ffdbbfe` |
| 1 | START | `0x1ffdbc36` |
| 2 | BACK | `0x1ffdbc6e` |
| 3 | DOWN | `0x1ffdbca6` |
| 4 | UP | `0x1ffdbcde` |

Only keys 1, 3, and 4 are written. The exact 16-bit values are `0xff00` idle,
`0x5ea1` owned, and `0x5da2` one-frame acknowledgement. The renderer clears an
acknowledgement with an atomic compare-exchange, so it cannot erase a concurrent
new press.

An owned press or visible release posts event `0x50` to the watch face through
the existing UI queue. The call is equivalent to the pinned stock helper's
`FUN_67D8(queue, &message, 1, 0)`: it requests front insertion with a zero
timeout and cannot block the key worker if the queue is full. The key worker
never renders directly or accesses the framebuffer.

## Display geometry

The renderer clears the full 240 by 240 framebuffer and draws a compact
scientific specimen within a strict 100-pixel radius around screen center. Its
64 cells form a tapered 8 by 8 field inside an angular fly-head contour. Each
simulated neuron maps directly to one unique 6 by 6 cell region; magnitude
selects dot, cross, outline, or filled form.

The reviewed native RGB222 bytes are black `0x00`, gray `0x2a`, white `0x3f`,
green `0x0c`, magenta `0x33`, and amber `0x38`. Excitatory activity is green,
inhibitory activity is magenta, and saturated input/action neurons are amber.

The centered footer reports the active control in the same frame:

| Button | Footer | Neural meaning | Garmin ownership |
| --- | --- | --- | --- |
| LIGHT | `LIGHT>LUX` | light stimulus placeholder | always passes through |
| START | `START>BURST` | strong input burst | FlyOS on stable home |
| BACK | `BACK>SYSTEM` | system escape indicator | always passes through |
| DOWN | `DOWN>CALM` | calming input | FlyOS on stable home |
| UP | `UP>PULSE` | arousal pulse | FlyOS on stable home |

The GPIO-derived button sample and the latched event status are ORed before the
Brain64 step. This makes a physical hold and a short captured press drive the
same model input.

## Remaining limits

This remains a GarminOS-resident overlay. Garmin continues to own LIGHT, BACK,
non-home screens, USB/update handling, display dispatch, scheduling, and boot.
Heart-rate, accelerometer, ambient-light, and charging telemetry are not yet
bound because their safe cache locations and update semantics have not been
proved. The display does not claim those signals.

The official-code recovery wrapper still depends on a booting GarminOS and its
normal USB updater. There is no known nonboot recovery path. Any future live
write therefore retains nonzero brick risk and requires a separately reviewed,
exact package and restore pair.

## Verification

The static call graph gives a 384-byte maximum target-owned stack chain. The
Unicorn suite observes the stack pointer at every executed instruction and
rejects any larger use. It also confines writes to the framebuffer, stack, and
the three exact controlled-key status halfwords; verifies the original key
publisher replay for native events; and exercises every cross-segment branch.

The focused controls suite contains 19 tests. It covers malformed and changing
view lists, all ownership and escape paths, stale status recovery, queue-full
and uninitialized-queue behavior, short-tap acknowledgement, exact hook bytes,
all 64 direct neuron cells, the six-color allowlist, and every rendered button
state inside the 100-pixel safe radius.
