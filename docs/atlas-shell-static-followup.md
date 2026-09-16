# Atlas-shell static follow-up

This follow-up records offline analysis rounds two through five against the
pinned Forerunner 245 non-Music 13.70 MAIN image. The image is 5,079,040 bytes
with SHA-256
`b45be1baf98999af10f073bef52b284beb2aea6abbb7cde2ffa59fb6bcedeab6`.
No connected-watch access, target package, or live write was used.

The overall feasibility result remains **blocked**. One original gate is now
proved, several blockers are narrower, and two proposed shortcuts have direct
counterexamples.

## Gate changes

| Gate or alternative | Result | Evidence boundary |
| --- | --- | --- |
| Bounded tri-state view classifier | **Proved offline** | Two matching, bounded snapshots of the native view list distinguish HOME, NON_HOME, and INVALID while rejecting malformed, cyclic, overlong, or changing lists. |
| Observed update prompt is NON_HOME | **Blocked** | Known update identities all differ from HOME, but no captured native-list fixture identifies the historical Install Now/Later prompt's first-visible node. |
| Five key halfwords untouched for the full lifetime | **False as worded** | C-runtime startup zeros the complete key workspace, including all five proposed words. |
| Post-startup key-halfword ownership | **Blocked** | Scheduler and direct key-manager accesses stop before the pads, but whole-program computed bulk-writer closure is incomplete. |
| Atomic halfword capability | **Proved as a primitive** | A Cortex-M4 probe emits `LDREXH`/`STREXH`; exhaustive host verification covers all 65,536 input words and byte-preserving transitions. The final multi-context target protocol is not implemented. |
| USB state 3/4 convergence | **Blocked** | State 3 can return after 100 ms without reading detach input; readiness depends on external guards. State 4 has one local teardown but not a proved once-per-epoch lifecycle. |
| Post-unlock USB hook and bounded retry | **Blocked** | Candidate callbacks run under source-list or USB mutexes, use an infinite-timeout queue send, or have an unproved lifetime/cadence. |
| Native modal outcome or refresh | **Blocked** | USB observer dispatch includes dynamic callbacks and mutable external targets. No safe generic native repaint or modal-dismiss operation is established. |
| FlyOS-owned charging view | **Rejected** | No recovered USB-family identity is proved charging-only. USB event provenance is also unsafe because F1 cleanup can mutate independently pinned update identity `0x046AA84D`. |
| Automatic display flush after USB detach | **Rejected statically** | USB events reach native view lifecycle processing, but an empty/no-render result skips the conditional path to the display hook at `0x9A20`. |
| Third 1,802-byte payload interval | **Offline candidate only** | `0x001F70F6..0x001F77FF` is entirely `0xFF` with no recovered references, instructions, data, or functions in either 13.70 mapping. Computed references and proprietary metadata ownership remain open. |

## Native view classifier

The native list root is `0x20003E84`. Each node uses predecessor, successor,
identity, and flags at offsets `+0`, `+4`, `+8`, and `+0x50`; flags bit `0x2`
marks a hidden node. HOME identity is `0x0005ADF5`.

A safe classifier does not call Garmin's unbounded list walkers. It captures at
most eight aligned nodes entirely within `0x1FFC0000..0x2003FFAC`, validates
forward and reverse links, rejects cycles and a ninth node, and requires stable
root reads. It repeats the complete capture. Any difference produces INVALID.
Two identical captures produce HOME only when the first visible identity is
`0x0005ADF5`; every other stable first-visible identity is NON_HOME.

This contract detects every modeled malformed or changing list. Like any
lock-free snapshot, it cannot detect a complete ABA mutation restored between
reads. The input policy therefore uses it only for a phase-zero ownership
decision and gives INVALID to Garmin.

## Key workspace boundary

The two embedded scheduler objects in each `0x38`-byte key record are now
closed through insertion, query, dispatch, cancellation, and callbacks. The
generic scheduler reaches only object byte 19; direct key-manager accesses end
at record byte `0x35`. The proposed pads are bytes `0x36..0x37`.

The reset zero loop at `0x1939A..0x193C5` covers
`0x1FFC0000..0x1FFF5AEF`, so it writes every proposed pad. A narrower reset
epoch contract is possible: zero is complement-invalid and selects Garmin;
initialization would use exact CAS16 `0x0000 -> 0xF0F0` only after the key
manager handle at `0x1FFC9A14` becomes nonzero and all other readiness guards
pass. Display initialization alone is insufficient because display hooks can
run before key initialization.

This narrower contract is not yet storage authorization. Software reset can
re-enter startup zeroing, and the remaining proof must exclude post-handoff
computed bulk-memory and DMA destinations.

The recognized K28 eDMA paths resolve to three fixed peripheral destinations:
`0x400DF200`, `0x400DF218`, and `0x400DA154`; none overlaps the workspace.
A broader CPU bulk-memory audit found 1,407 calls across 907 owners. Its
smallest unresolved writer is the external-XIP routine at `0x046DFB08`, whose
path at `0x046DFC04` clears 40 bytes beginning at a caller-supplied pointer
plus `0x58`. Four tail-entry stubs pass that pointer through unchanged, and no
incoming caller or allocation bounds are recoverable. Word-aligned pointer
values can place the clear across the key workspace. Exhaustive direct-branch,
literal-pointer, and Ghidra entry-reference scans narrow this gap but cannot
prove the stubs unreachable. Storage ownership remains unproved.

## USB and redraw boundary

USB teardown clears the cache and publishes event type 4, but it does not call
the display backend. The USB observer maps manager events into native UI events
`0xEE..0xF2`, which are dispatched through the live view list. Native lifecycle
processing calls the display path only when it reports render work; static
control flow includes a no-render path that skips `0x9A20`.

An event bridge can post watch-face event `0xBF`, but its callback executes
while the source-list mutex is held and ultimately sends to a queue with
infinite timeout. The native view timer has variable cadence and an unproved
lifetime through hidden modals and USB detach. Neither is an approved redraw
trigger.

The smallest useful next observation is a bounded, privacy-preserving runtime
trace of the USB UI event, watch-face event `0xBF`, native first-visible
identity/flags, and display hook `0x9A20` across home, charging, USB mass
storage, and detach.

An ignored throwaway probe now establishes the minimum mechanics: two four-byte
hooks at `0x5ADF4` and `0x9A20`, a 932-byte payload at `0x1FA400`, and 940
changed flash bytes total. Unicorn checks cover displaced-instruction replay,
exact resume addresses, stack bounds, the original display call, and a strict
write allowlist. An optional pre-enqueue event hook at `0x54132` increases the
payload to 1,008 bytes and total changes to 1,020 bytes. The probe stores only
sanitized event/timing/lock-state bits and exposes them on screen.

The probe is **not approved for live use** because its ten bytes of volatile
state would occupy the same five key halfwords whose post-startup exclusivity
is still unproved. No GCD, synthetic version, or staging artifact was created.
A live probe remains prohibited until exclusive RAM is proved or the storage
design is replaced, then the exact candidate and official restore receive a
separate write review.

A second ignored throwaway probe removes retained RAM entirely. It hooks only
the display call at `0x9A20`, replacing a four-byte `BL` with a 1,078-byte
payload at `0x1FA400` (1,082 changed flash bytes total). It writes a small
sanitized panel to the existing framebuffer and stack, showing the narrow USB
mass-storage enum, bounded view class, RTC sample, UI-task equality, and
reduced mutex states. Forty-nine Unicorn cases passed exact return, original
display submission once, stack bounds, and read/write allowlists. It is a
replacement for the current overlay, not an add-on, and no package or live
write was made.

On a new visible flush, this stateless panel could distinguish stale USB enum
3/4 from a stable NON_HOME view. A frozen panel is ambiguous: the hook might
not run, a physical transfer might be skipped, or another view might obscure
the panel. This diagnostic does not prove detach convergence or redraw cadence
and has not received an exact live-write review.

## Current decision

Do not scaffold or package the atlas-shell target from these findings. Continue
offline work on volatile-state ownership and computed-writer closure. Preserve
update and recovery views as native pass-through, and do not infer redraw
behavior from USB cache transitions alone.
