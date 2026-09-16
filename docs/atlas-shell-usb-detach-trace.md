# FlyOS USB-detach runtime-trace diagnostic — design and honest brick-risk

**Status: NO-GO for live use. No candidate package (13.82) was constructed. This
is a BLOCKED outcome with proof, not a shippable artifact.** Everything below is
offline analysis. No watch was touched, no package was staged, `stage-gupdate.ps1`
was not run, and `packaging_allowed:false` / `live_staging_allowed:false` remain
in force.

This document specifies the passive runtime-trace probe that would capture the
three runtime facts `task5-gate-investigation.md` proved static analysis cannot,
and then explains — with offline evidence — why it **cannot be built to a safety
standard that would justify ever flashing it**. The passive capture *stubs* are
individually constructible and are proven passive-correct in emulation; the
*scheme as a whole* is not safe, and the specific reason is structural.

---

## 1. Capture spec (verified against `task5-gate-investigation.md`, not trusted)

| Gate | Site (VA) | Displaced instr (image) | Must record |
| --- | --- | --- | --- |
| 1 | `0x20A8A` | `b.w 0x874C` (`e7 f7 5f be`) | current TCB `*0x1FFC7644`; IPSR/exception number; USB-mutex recursion `(short)*(0x1FFC6EEC+0x18)`; USB-mutex owner `*(0x1FFC6EEC+8)` |
| 2/3 | `0x5ADF4` | `push.w {r4-r11,lr}` (`2d e9 f0 4f`) | watch-face event `0xBF`, tick, sanitized context |
| 2/3 | `0x54132` | `ldr r3,[pc,#0xB4]; movs r1,#0xBF` (`2d 4b bf 21`) | source event `0x49` before enqueue |
| 2/3 | `0x9A20` | `bl 0xE1A4` (`04 f0 c0 fb`) | display-flush hits; task identity; ownership/recursion of `0x1FFDE6CC` (display), `0x1FFDB7F4` (display-wrapper), view/source-list mutexes; home node `0x20003E18` first-visible |

All four displaced instructions were re-read from the pinned image
`stream_01_fw_all_bin.bin` (5,079,040 bytes, SHA-256
`b45be1baf98999af10f073bef52b284beb2aea6abbb7cde2ffa59fb6bcedeab6`) and match the
investigation byte-for-byte (`0x20A8A` SHA-256
`546739c398c7927d8d1bd7a2245e809a9cca4c2396a7d4e79b7f1ac5ca09f544`).

Crucially, **every Gate-1 value is a plain memory or register read** — three
absolute/register-relative loads and one `MRS Rd,IPSR`. None requires taking a
lock, calling a primitive, or asserting on context. So the *values* are
capturable by a passive stub. The problem is not the reads; it is where the
captured bytes must live and where the stub must run.

---

## 2. Probe architecture

Four passive capture stubs write fixed-size records into a persistent RAM ring
buffer; a fifth concern renders the accumulated ring on-screen at the display
flush so a human can photograph it — no USB, filesystem, or queue exfiltration.

```
0x20A8A ── b.w ─▶ gate1_stub ─┐
0x5ADF4 ── b.w ─▶ wf_logger  ─┼─▶ [ RAM ring buffer ]  ──render──▶ 0x9A20 framebuffer
0x54132 ── b.w ─▶ src_logger ─┤        (persistent)                (on-screen readout)
0x9A20  ── bl  ─▶ disp_render ┘
```

### 2.1 Gate-1 stub at `0x20A8A` (built and emulated here)

This is the novel, safety-critical stub — all prior probes in this sequence
(Round 5, 1378, 1380) deliberately hooked **only** the proven-thread `0x9A20`.
The hand-assembled Thumb-2 stub (`tools/garmin-firmware/atlas_shell_trace/trace_stubs.py`)
is **108 bytes**, SHA-256
`887685e868611aadddc26cc5f2c8e5ac165ff300eedcd604222e5350ff2f6754`:

```
push.w  {r1, r2, r3, ip}        ; save scratch; r0/lr/sp untouched
movw/movt ip, RING_HEAD ; ldr r2,[ip]      ; head
and     r3, r2, #0x3f ; lsl r3, r3, #4     ; slot index (bounded, pow2 mask)
movw/movt r1, RING_BASE ; add r3, r1, r3   ; &slot
movw/movt r1, 0x1FFC7644 ; ldr r1,[r1] ; str r1,[r3,#0]   ; current TCB
ldr     r1, [r0, #8]  ; str r1, [r3, #4]                  ; USB-mutex owner
ldrh    r1, [r0, #0x18]                                   ; recursion depth
mrs     ip, ipsr                                          ; exception number
orr.w   r1, r1, ip, lsl #16 ; str r1, [r3, #8]            ; ipsr|recursion
movw    r1, #0x0a8a ; str r1, [r3, #0xc]                  ; site marker
add.w   r2, r2, #1 ; movw/movt ip, RING_HEAD ; str r2,[ip]; advance head
pop.w   {r1, r2, r3, ip}                                  ; restore scratch
b.w     0x874c                                            ; replay displaced original
```

**Safety argument (what is provable offline).** The site is a tail branch: at
`0x20A8A`, `r0 = 0x1FFC6EEC` (the mutex the displaced unlock consumes), `lr` is
the scheduler return, and `r4-r7,lr` are already restored. The stub touches only
`r1/r2/r3/r12`, saves and restores them, leaves `r0`, `lr`, and `sp` exactly as
found, takes no lock, allocates nothing, and ends by replaying the exact
`b.w 0x874C`. It never branches on context, so it is byte-for-byte identical in
thread and exception context. The ring index is masked to a power of two before
use, so even a torn/racing head cannot address outside the buffer.

**Emulation proof** (`emulate_atlas_shell_trace.py`, 8/8 tests): across thread
context (`IPSR=0`) and modelled exception contexts (`IPSR=0x0B/0x30/0xF0`), the
stub captures all four values correctly, preserves `r0/lr/sp`, restores
`r1/r2/r3/r12`, confines every store to the probe stack (4 push words) and the
ring (4 record words + head), never reaches `0x67D8` (queue), `0x8500/0x8734`
(lock), `0x9A10/0xE1A4` (display), or `0x5D2C` (reschedule), and reaches only the
mandatory displaced `0x874C`. A RED baseline (`gate1_stub_null`) with the capture
logic removed fails the correctness assertions, proving they are non-vacuous.

### 2.2 Event/display loggers at `0x5ADF4`, `0x54132`, `0x9A20`

These reuse the design already emulated in Round 4 (49 cases) and Round 5: byte
increments and a bounded framebuffer panel, under locks that are already held, no
new lock/alloc/queue. They were **not** re-assembled here because they are not
the decisive artifact and the verdict below makes exhaustive re-validation of a
probe that must not be flashed unwarranted. Round 4 measured the three-hook
superset at 12 hook bytes + 1,008 payload bytes = **1,020 changed flash bytes**.

### 2.3 Exfiltration: on-screen readout at `0x9A20`

The FlyOS display hook already owns the framebuffer at `0x9A20` in **proven
thread context** (`FUN_00008734` at `0x9A10` would have asserted otherwise), so
rendering the ring there takes no new lock and does no bus I/O. This is the exfil
the brief tells me to "strongly consider," and it does avoid USB/FS/queue
entanglement. **But it carries a hazard the brief asked me to surface (§4.4).**

### 2.4 Capture format

Gate-1 record (16 bytes): `[0]=TCB  [4]=owner TCB  [8]=(ipsr<<16)|recursion
[12]=0x0000_0A8A`. Ring is a power-of-two record array with a single word head
index; render maps each field to the existing 3×5 hex font. Event/display records
follow Round 4's packed-counter layout.

---

## 3. Footprint (measured)

| Item | Value |
| --- | --- |
| Gate-1 hook bytes @ `0x20A8A` | 4 (`b.w <stub>`) |
| Gate-1 payload | 108 bytes, SHA-256 `887685e8…` |
| Gate-1 changed flash | **112 bytes** |
| Gate-1 stack delta | **16 bytes** (`push {r1,r2,r3,r12}`; leaf/tail, no nested call) |
| 3-hook event/display superset (Round 4) | 1,020 changed flash bytes |
| Persistent RAM ring | **has no provably-safe home — see §4.1** |

The 2 KiB secondary cave is **currently occupied by the shipped 1380 five-key
controls build** (1,904 bytes secondary, per Task 3). A trace probe is therefore
a *replacement* experiment, not an add-on — the diagnostic and the controls
cannot coexist in the cave. Flash is not the binding constraint; RAM ownership is.

---

## 4. Honest residual-risk assessment

Model-passivity is **necessary but not sufficient** for flash safety. The
dominant risks are structurally outside what any offline method can reach.

### 4.1 The persistent ring buffer has no statically-safe home (decisive)

`round4-runtime-probe-design.md` performed the exhaustive search for a persistent
volatile store for just **10 bytes** and found exactly one bounded candidate (the
five key-record tail halfwords) whose exclusivity "remains unproved against
computed-pointer and DMA writers." Every alternative — stack (doesn't persist),
framebuffer (native-owned), post-BSS RAM tails (may be heap/task stacks),
allocation (forbidden), CoreSight (not proved available), flash/FS (forbidden) —
was rejected: *"No other statically safe volatile store was found… Without that
proof, do not construct or stage the probe."* A multi-record **ring buffer is
strictly more persistent RAM than those 10 bytes**, so the ownership problem is
worse, not better. And the one marginal candidate is **now occupied by the
shipped 1380 controls** (Round 4 predicted this: "the diagnostic and controls
cannot coexist without a new ownership protocol"). If the ring lands on RAM that
is in fact owned by an allocator, a task stack, or a DMA destination, the writes
corrupt live state → fault. **This cannot be excluded from the pinned image**,
whose RAM ownership `recovery.md` and the investigation both record as
unresolved.

The proven, quarantine-safe pattern encodes exactly this invariant in its linker
script: `ASSERT(SIZEOF(.forbidden) == 0, "writable static storage forbidden")`.
The ring buffer *is* writable static storage. **This probe cannot satisfy the
safety invariant that made every prior buildable probe safe enough to quarantine.**

### 4.2 The Gate-1 context is unknowable offline — and that is a catch-22

`task5-gate-investigation.md` proves `FUN_00020a64` (which contains `0x20A8A`) has
**zero call cross-references**; it is only installed as a scheduler/timer callback
and invoked indirectly, so static evidence "cannot establish `FUN_00005c34() != 0`
there," i.e. **cannot establish whether `0x20A8A` runs in thread or exception
context**, nor when it first fires. My stub is designed to be safe in *either*
context, and emulation supports that — but Unicorn cannot model real NVIC
preemption, so it cannot prove the stub is safe under a genuine ISR that preempts
a thread-context render mid-ring-update, and it cannot tell me whether `0x20A8A`
fires **before USB enumerates** during boot. The single fact that makes the trace
necessary (the context/timing at `0x20A8A` is unknown) is the exact fact that
makes the trace's own safety unprovable offline. You would have to run it to learn
the context, but you cannot prove it is safe to run without knowing the context.

### 4.3 Fault-before-USB-enumerates = potentially permanent brick, no recovery

Per `recovery.md`: there is **no demonstrated FR245 non-boot recovery**; every
restore is conditional on GarminOS still booting, USB still enumerating, and the
updater still working. A fault at `0x20A8A` in a non-preemptible or
pre-enumeration context is scenario 6 ("Device no longer enumerates over USB",
status **Unknown**, high) shading into scenario 4 ("Bootloader damaged",
**Extreme**, likely permanent). The sole public preboot USB recovery tool is
proven only on a GPSMAP 276Cx (HWID 2479) and explicitly treats other region
mappings as untested. There is no numerical brick probability that the evidence
supports — `recovery.md` says so directly — but it is **non-negligible and
offline-unbounded**, and its worst case is unrecoverable.

### 4.4 The on-screen exfil inherits Round 6's NO-GO, worsened

`round6-diagnostic-recovery-review.md` issued a **NO-GO** for a live diagnostic
built on this display hook because the panel "can cover an on-watch update
choice, warning, recovery message, or control hint," and demanded the obscuration
defect be resolved "or abandon the live probe." The 1378 build's fix was to paint
**only on stable HOME**. But a USB-detach trace must render precisely during
NON_HOME / charging / mass-storage views — that is the whole point — i.e. exactly
the states in which a native recovery/update prompt can appear. **HOME-only
gating, the one mitigation that made 1378 quarantine-safe, is incompatible with
this probe's purpose.** Rendering an accumulated multi-line ring obscures *more*
than the Round 5 inset panel, not less.

### 4.5 What Unicorn structurally cannot catch

Enumerated in `emulate_atlas_shell_trace.py::UNMODELLED`: real NVIC
preemption/priority; boot-time ordering (pre-USB-enumeration); ring-buffer RAM
ownership; external-region veneers under the USB mutex (do not decode); flash
controller and real latency; concurrent ring writers under true preemption.
`full_image_validator.py` and `gcd_candidate_verify.py` validate structural and
checksum coherence only; they "do not model resident-loader authentication,
update acceptance, version policy, installation, or recovery," and model neither
RAM ownership nor execution context. A `candidate_full_image_valid:true`
descriptor on a package embedding §4.1–§4.4 would therefore assert coherence the
tool can see while hiding the hazards it cannot — the "shippable-looking artifact"
the brief warns against. **That is why no 13.82 candidate GCD was minted.**

---

## 5. Mapping to `recovery.md` "Preconditions for any future write proposal"

| # | Precondition | Status for this probe |
| --- | --- | --- |
| 1 | exact bytes/artifact + SHA-256 | **Partial.** Gate-1 stub 108 B SHA-256 `887685e8…`; full candidate image intentionally not built, so no image hash exists. |
| 2 | target component/region/expected previous contents | **Known.** App flash `0x3000–0x1FFFFF` + QSPI `0x68617000–0x68916fff`; hook sites' original bytes pinned; ring-buffer RAM target **not identifiable safely (§4.1).** |
| 3 | validation performed by the receiving loader | **Unknown.** Resident-loader authentication/version policy never observed. |
| 4 | predicted behaviour for interruption / checksum / signature failure | **Unknown.** No live rejection or interruption test is justified; K28 dual-bank ≠ proven transactional. |
| 5 | known recovery entry sequence, demonstrated without writing | **NONE.** No demonstrated FR245 non-boot recovery. **Unsatisfiable today.** |
| 6 | exact official restore artifact + SHA-256 | **Satisfied by existing file:** official 13.70 `Forerunner245_1370_GUPDATE.GCD`, SHA-256 `8ebefacf6bcc00bec0fb271596abfb9618f9a3114d32b3a106fbd27d5a366adc` — valid only while the watch still reaches the updater. A synthetic 13.83 wrapper adds no recovery capability the official file lacks; it only adds a forward-version number that matters solely for admission as an update, i.e. for flashing, which is blocked. Not minted. |
| 7 | whether recovery covers application only or also bootloader | **Application only.** Bootloader/prefix `<0x3000`, secondary firmware, calibration/security are not covered. |
| 8 | explicit brick probability with evidence | **Not quantifiable** (`recovery.md`), and its worst case (§4.3) is unrecoverable. Non-negligible, offline-unbounded. |

Preconditions 5 and 8 are unsatisfiable with current evidence; 3, 4, 7 are open;
2 is defeated for the ring-buffer target. This is the disclosure a human needs.

---

## 6. Verdict

The passive capture *stubs* are constructible and emulation-passive; the Gate-1
stub is real, 108 bytes, and proven passive across thread and exception contexts.
But the *diagnostic as a whole* requires (a) owning persistent RAM that has no
statically-safe home (§4.1), (b) executing at a site whose context and boot-time
ordering are provably unknowable offline (§4.2) with an unrecoverable worst case
(§4.3), and (c) an on-screen exfil that reinstates Round 6's obscuration NO-GO in
the one situation HOME-only gating cannot cover (§4.4). None of these is closable
by any offline method, and constructing a validator-passing package would
misrepresent them.

**Recommendation: do not flash; do not build the 13.82 candidate. If these gates
are ever to be closed on hardware, the prerequisite is a hardware-level recovery
path (e.g. an established SWD/JTAG or vendor reflash route) demonstrated
read-only first — not a cleverer passive stub.** An honest negative is the
deliverable here.
