# Forerunner 245 13.70 N64 target placement

## Scope

This is an offline link-and-emulation target. It does not create a Garmin update,
stage a file, or access the connected watch. `packaging_allowed` and
`live_write_allowed` are both false in the allocation evidence and generated
manifest.

## Placement

| Segment | Allowed range | Used | Spare |
| --- | --- | ---: | ---: |
| Hook | `0x00009a20..0x00009a23` | 4 | 0 |
| Primary | `0x001f6000..0x001f63fe` | 1,016 | 7 |
| Repair byte | `0x001f63ff` | 0 | reserved |
| Secondary | `0x001fa400..0x001fabff` | 2,034 | 14 |
| Payload total | two audited envelopes | 3,050 | 21 |

The linker rejects an altered hook, primary or secondary overflow, overlap,
consumption of the repair byte, writable static storage, and undefined symbols.
The independent third-allocation candidates are not linked or referenced.

The primary segment contains the entry, bounded home-list validator, compact
text/line primitives, selected Brain64 functions, and the 52-byte alphabet.
The secondary contains the Brain64 step and edge table plus the N64 renderer,
remaining glyph data, strings, state codes, and angular contour.

## Runtime gate

The entry returns to Garmin's original display dispatch for every path. A frame
is replaced only when all of these conditions hold:

1. framebuffer is non-null;
2. BACK (GPIOD PDIR bit 1, active low) is not held;
3. two bounded observations see a list that terminates within eight unique,
   aligned SRAM nodes; and
4. in both observations the first node with callback `0x0005adf5` is the same
   node and is also the first visible node.

An empty list, invalid address, unaligned link, cycle, ninth node, missing
callback, hidden match, different first visible node, changed root, changed
finder result, or changed visibility result leaves the framebuffer byte-for-byte intact.
BACK is checked before the root or any sensor cache and therefore remains a
direct escape to Garmin UI. This is how charging and update screens coexist:
Garmin owns those non-home views and START retains its native update-confirm
meaning.

The target never calls Garmin's live walkers. It confines dynamic node reads to
offsets `+0x04`, `+0x08`, and `+0x50` in aligned nodes from
`0x1ffc0000..0x2003ffac`, validates every locally captured `next` before
dereference, detects cycles, and rejects a ninth node. The pinned stock bodies
at image addresses `0x0005306c` and `0x000530cc` run only in the offline emulator
as the stable-list semantic oracle. The two target observations and bracketed
root reads make detectable changes fail closed.

No read-only predicate can prove that Garmin will not mutate the list after the
final target read and before framebuffer writes without a proved lock or
generation counter. An ABA mutation restored before re-observation is likewise
indistinguishable from stable state. The remaining consequence is a possible
transient overlay on a newly changed view; it cannot redirect the bounded target
to an unvalidated address or external control-flow target.

## Inputs

| Input | Exact source | Target behavior |
| --- | --- | --- |
| LIGHT | GPIOC PDIR bit 11 | neuron input and `LIGHT>LUX` footer |
| START | GPIOD PDIR bit 10 | neuron input and `START>BURST` footer |
| BACK | GPIOD PDIR bit 1 | unconditional pass-through |
| DOWN | GPIOA PDIR bit 20 | neuron input and `DOWN>CALM` footer |
| UP | GPIOA PDIR bit 22 | neuron input and `UP>PULSE` footer |
| RTC | `0x4003d000/+4` | bounded stable sample, two attempts maximum |
| Battery | cached binary32 at `0x1ffcccd8` | integer-bit validation and truncated percent |
| USB mass storage | byte `0x1ffc6f25` | true only for exact values 3 or 4 |

Battery accepts finite `[0,100]`, including both signed zeros, and rejects the
`-1.0` sentinel, other negative values, NaN, infinity, and values above 100.
There are no floating-point instructions or helper calls. Generic USB attach,
charging, update pending, HR BPM, and motion remain unavailable and do not drive
the model. The face shows exact `HR --` and `MOTION --` labels and labels USB
strictly as `MS`.

## Rendering and semantic oracle

Every neuron `n` maps directly to one unique 5x5 cell at:

```text
x = 96 + (n & 7) * 6
y = 79 + (n >> 3) * 8
```

The target compiles the reviewed shared `brain64.c` unchanged. For every
emulated rendering case its complete 140-byte brain state equals the MinGW host
Brain64 oracle, and its framebuffer equals an independently compiled host build
of the target renderer. The test also checks each of the 64 cell patterns from
the captured activation array.

The compact renderer deliberately differs from the larger host design renderer:

- 3x5 type replaces 5x7 type;
- the 8x8 field is generated procedurally rather than from a point table;
- the angular contour uses 13 byte-coordinate vertices;
- the state uses `STATE R/M/A/Q`;
- unavailable motion is shown exactly as `MOTION --`; and
- button footers remove cosmetic spaces and use compact cause labels to meet the hard limit.

Those differences are presentation-only. Neuron count, level thresholds, sign,
action-cell saturation, model state, button meaning, battery validity, and USB
mass-storage semantics are unchanged.

The reviewed RGB222 native bytes are `0x00` black, `0x2a` gray scaffold,
`0x3f` white text, `0x0c` green excitation, `0x33` magenta inhibition, and
`0x38` amber saturation. Every non-background pixel remains within the
114-pixel circular safe radius.

## Stack and external calls

Compiler `.su` files and the disassembly call graph give an exact maximum owned
chain of 384 bytes: hook 0 + entry 184 + reconstruct 16 + step 184. Unicorn
also observes SP at every instruction and rejects more than 384 bytes. Stock
dirty/dispatch frames, interrupt frames, and unknown live Garmin task headroom
are outside this bound.

Only two indirect transfers are permitted: full-screen dirty `0x0000f2e9` and
original dispatch `0x0000e1a5`. The emulator separately executes the real
pinned watch-face instructions as an offline oracle, checks every
inter-segment branch, preserves R4-R11 and the original hook return, and permits
target writes only to the supplied framebuffer and mapped stack.
