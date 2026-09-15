# Forerunner 245 13.70 runtime-state allowlist

## Scope

This document defines the only Garmin runtime state that the N64 FlyOS target
may consume. The result is tied to the Forerunner 245 non-Music 13.70 `fw_all`
image at
`artifacts/firmware/analysis/Forerunner245_1370_GUPDATE/stream_01_fw_all_bin.bin`:

- size: 5,079,040 bytes
- image base: `0x00003000`
- SHA-256: `b45be1baf98999af10f073bef52b284beb2aea6abbb7cde2ffa59fb6bcedeab6`

The analysis is offline and read-only. The reporter does not open the watch,
read live memory, invoke a Garmin function, perform peripheral I/O, or create a
firmware package.

## Decision

| Signal | Status | Safe read | Validity rule | FlyOS behavior |
|---|---|---|---|---|
| Watch face active | Available for Task 4 emulation | Image bodies `0x0005306c`, `0x000530cc`; callable Thumb addresses `0x0005306d`, `0x000530cd`; callback `0x0005adf5`; root `0x20003e84` | Finder returns a non-null node and first-visible predicate returns exactly 1 | Draw only after an affirmative result; fail closed on everything else |
| BACK pass-through | Available | GPIOD PDIR `0x400ff0d0`, bit 1 | Active-low: zero means held | Leave framebuffer byte-identical while held |
| USB mass-storage mode | Available | Byte cache `0x1ffc6f25` | Only enum values 3 and 4 are true | May show `USB MASS STORAGE`; does not imply charging |
| Battery percentage | Available | Binary32 cache `0x1ffcccd8` | Reject `-1.0`, non-finite, and values outside `[0,100]` | Invalid contributes zero and displays `--` |
| Generic USB attached | Unavailable | None | No valid value | Zero / `--` |
| Charging | Unavailable | None | No valid value | Zero / `--`; preserve Garmin's charging page through pass-through |
| Update pending | Unavailable | None | No valid value | No custom prompt; preserve Garmin's stock install modal |
| Heart-rate BPM | Unavailable | None | No valid value | Zero / `HR --` |
| Motion | Unavailable | None | No valid value | Zero / `MOTION --` |
| Exact target palette | Available | Pinned inverse conversion functions and callback table | Canonical RGB components are `00`, `55`, `AA`, `FF`; native values are six-bit RGB222 | Use the six exact role values below |

"Available" here means eligible for the Task 4 target emulator. It is not
permission to install anything. Task 4 still has to bound every dynamic list
read and control-flow target and prove that false/invalid home state or held
BACK causes zero framebuffer writes.

## Watch-face predicate

The update-condition routine contains this sequence at `0x0006bfec`:

```text
load 0x0005adf5
firmware BL resolves to image body 0x0005306c
firmware BL resolves to image body 0x000530cc
compare result with zero
branch to "software update condition not met, not on watch face"
```

The function body at `0x0005306c` starts at list root `0x20003e84`, follows
each node's `+4` next pointer, and compares its `+8` callback with
`0x0005adf5`. The function body at `0x000530cc` walks
the same list, skips nodes whose `+0x50` flags have bit 1 set, and returns one
only when the first unskipped node is the node passed to it. Their pinned
function bodies have loads, comparisons, branches, register moves, CLZ, and
return instructions only. They contain no calls or stores.

The target contract is:

```c
node = ((finder_fn)0x0005306d)((void *)0x0005adf5);
home = node != NULL && ((visible_fn)0x000530cd)(node) == 1;
```

The odd callable addresses set the Cortex-M Thumb bit. The even addresses are
image and disassembly locations only and must never be used as raw function
pointers.

The list is dynamic. Empty lists, missing callbacks, malformed nodes,
unexpected pointers, unexpected control flow, and a false predicate must all
disable rendering. Task 4 must emulate the actual call site and allowlist the
root plus node offsets `+0x04`, `+0x08`, and `+0x50` before integration.

## BACK pass-through

The five-row key table at `0x0000f9bc` is pinned byte-for-byte. Its third row
contains encoded pin `0x61`, which resolves to GPIOD bit 1. Reading PDIR at
`0x400ff0d0` is a single read-only MMIO load. When bit 1 is zero, BACK is held
and overlay rendering must stop before the first framebuffer write.

This override remains independent of the watch-face predicate. It gives the
wearer an immediate way to reveal Garmin-owned screens even if later UI-state
work is wrong.

## USB and charging

The official mapper at `0x00020578` locks a Garmin object, reads the byte at
`0x1ffc6f25`, and groups states 3 and 4 as mass-storage mode. FlyOS must not
call this mapper because it takes locks. It may read the cached byte directly
and treat only 3 and 4 as the narrow `USB MASS STORAGE` condition.

This does not establish cable insertion or charging. Nearby USB-manager bytes
do not have proven cable-present semantics. The charging accessor at
`0x000115c8` calls a function pointer, while other PMIC paths perform bus
transactions. The `Charging` string at `0x00444e64` is resource evidence only.
Generic USB attachment and charging remain unavailable.

## Battery percentage

Two getter front ends at `0x0000bf68` and `0x0000bfb8` load a binary32 value
from object base `0x1ffccc10` plus `0xc8`, yielding cache address
`0x1ffcccd8`. Both compare it with `-1.0`. When the cache equals the sentinel,
the getters branch to a fallback that can call a callback. FlyOS must never
call those getters.

The allowed adapter is one direct 32-bit cache load followed by local
validation. Accept finite values from 0 through 100 inclusive. Treat `-1.0`,
NaN, infinity, and out-of-range values as unavailable.

## Update, heart rate, and motion

The routine at `0x0006beec` evaluates whether conditions permit installing an
update. Eligibility is not evidence that an update is pending. The pinned
`Install Now` and `Install Later` strings provide no stable RAM flag or pure
getter. FlyOS must not display a custom install prompt. Rendering is disabled
off the watch face, so Garmin's own update modal remains visible and the START
button remains Garmin's confirmation key.

The recovered HR condition is a Boolean "broadcasting HR" check. It is not a
BPM value and has no freshness or off-wrist semantics. HR text resources do
not establish a readable state source. HR therefore remains unavailable.

The motion evidence reaches Apollo2 sensor-hub transport and activity
bookkeeping but no side-effect-free normalized motion snapshot. FlyOS must not
perform sensor-hub transactions or walk lock-dependent activity structures.
Motion remains unavailable.

## Framebuffer color

Follow-up static analysis resolved the two inverse color functions and the
callback table that assigns them to the same slots consumed by Garmin's
graphics runtime. The function body at `0x00063020` converts a native byte to
RGB, and its callable Thumb address is `0x00063021`. The function body at
`0x00063054` converts RGB to a native byte, and its callable Thumb address is
`0x00063055`.

The native format is:

```text
native=(R_level<<4)|(G_level<<2)|B_level

component  00  55  AA  FF
level       0   1   2   3
```

Bits 5:4 encode red, bits 3:2 green, and bits 1:0 blue. Offline tests verify
all 64 native bytes against all 64 RGB cube points in both directions.

The N64 target roles are fixed to:

| Role | Native byte | RGB |
|---|---:|---:|
| Background | `0x00` | `#000000` |
| Scaffold | `0x2a` | `#AAAAAA` |
| Text | `0x3f` | `#FFFFFF` |
| Excitatory | `0x0c` | `#00FF00` |
| Inhibitory | `0x33` | `#FF00FF` |
| Saturated | `0x38` | `#FFAA00` |

The static callback table at `0x00064554` contains the RGB-to-native Thumb
pointer `0x00063055` at `+0x0c` and native-to-RGB Thumb pointer `0x00063021`
at `+0x2c`. Setup body `0x00063f1c..0x00063f45` copies exactly `0x48` bytes
from that table before registration. The analyzer pins the full byte hashes of
both conversion functions, the table, and setup body, plus the setup source
literal and both table-slot pointer literals.

The `raw_framebuffer_color_mapping` signal remains unavailable because it is
a runtime-state slot and no runtime read is needed. The resolved static
mapping is exposed separately as the canonical available `target_palette`.

## Reproduce the report

Run from the repository root:

```powershell
python tools/garmin-firmware/fr245_runtime_state.py --image artifacts/firmware/analysis/Forerunner245_1370_GUPDATE/stream_01_fw_all_bin.bin
python -m unittest tools/garmin-firmware/tests/test_fr245_runtime_state.py
```

The first command verifies the exact image SHA-256, all pinned byte-range
hashes, address literals, and resource strings, then emits the canonical JSON
to standard output. The analyzer has no output-path option and performs no
filesystem write. The checked-in JSON contains no timestamp and is
reproducible byte-for-byte. `validate_report` compares every value, field,
list entry, and evidence assertion against a canonical report regenerated
from the pinned local image. Added, removed, reordered, or substituted schema
fields and substituted values are rejected; list order is also canonical.

The reporter pins these evidence classes:

- both watch-face function bodies, their call site, callback literal, list-root
  literal, failure-string pointer, and failure string;
- the USB mapper and its cache-address literal;
- both battery getter front ends and their object-base literal;
- the full five-button table;
- the framebuffer converter mask sequence;
- both inverse RGB222 function bodies, the callback table, the table setup
  function, setup source literal, and both callback pointer slots;
- the `Install Now`, `Install Later`, and `Charging` resource strings.

Any mismatch aborts report generation rather than carrying an address forward
to a different firmware build.
