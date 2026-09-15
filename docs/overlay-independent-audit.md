# Independent audit: FR245 scientific-fly executable overlay

Date: 2026-09-14

Scope: offline review of the finalized 13.71 scientific-fly overlay, its
13.72 restore wrapper, the linked Thumb payload, and the guarded staging
profiles. This audit did not access a mounted watch volume and did not stage,
install, reset, or execute either package.

## Verdict

**GO for a bounded, separately approved executable-overlay experiment, with
an unreduced permanent-brick risk.**

The hook, payload ABI, framebuffer writes, display guards, dirty rectangle,
tail dispatch, code placement, decoded/raw package deltas, helper identity,
version metadata, and recovered checksum layers are internally consistent.
No concrete implementation defect remains in the audited artifact.

This verdict is limited to testing whether one new Thumb payload executes
inside GarminOS. It is not a claim that the experiment is safely reversible.
The 13.72 wrapper is a practical restore only while the modified application
still boots far enough to expose normal USB mass storage and process another
GCD. There is no demonstrated FR245 recovery path if the overlay prevents
GarminOS from booting. Standalone FlyOS replacement therefore remains
**NO-GO/unproven** at this stage.

## Pinned artifacts

| Artifact | Size | SHA-256 |
|---|---:|---|
| Official non-Music 13.70 | 5,120,675 | `8ebefacf6bcc00bec0fb271596abfb9618f9a3114d32b3a106fbd27d5a366adc` |
| 13.71 scientific-fly overlay | 5,120,675 | `1f7de5ec5ea224ef337c3934e0f7ebc1445f0c6c7b8cb4201180cbeb1772a469` |
| 13.72 official-code restore wrapper | 5,120,675 | `f0a6b316cab5f941125cbe896e6e260196bc0ba4a02f5b475fa55de241522eb1` |
| Overlay decoded main | 5,079,040 | `5cc69a9045a26996ecabf85cf568d1f46e793ec1aa9a5e2eeb4034a35d39da71` |
| Restore decoded main | 5,079,040 | `cc3a416039ebee24af7b77f9af71877d5bb44f6272d1cd75f22695e64c9a1960` |
| Official helper stream | 37,120 | `f2351f808c0510baba6aae045867d8a366646511da662a411038426107725e46` |
| Four-byte hook | 4 | `49ff680c8b811f58b6747fea531fcbc8b88b3142946a1cad4271e0911f02a362` |
| Linked overlay payload | 451 | `62ea46c67c565f571789d1437de318de785d90a2fef0a79d702b6d2ba6b3dee1` |

The independent machine-readable comparison is
`artifacts/firmware/analysis/overlay-independent-audit-evidence.json`, SHA-256
`66a32c4d8e4caf772cc48a58e060053701d4a7496bdd382da819c00d95ec380e`.

## Hook and control-flow audit

The pinned official wrapper at `0x00009a10` saves four registers, takes the
display-update lock, restores the framebuffer to `r0`, explicitly places zero
in `r1`, and calls the active backend at `0x00009a20`:

```text
00009a10  push {r3,r4,r5,lr}
00009a18  bl   0x00008734       display lock
00009a1c  mov  r0,r4            framebuffer
00009a1e  movs r1,#0
00009a20  04 f0 c0 fb           bl 0x0000e1a4
00009a24  mov  r0,r5
00009a2a  b.w  0x0000874c       display unlock
```

The candidate changes only that four-byte call instruction at this site:

```text
00009a20  ec f1 ee fa           bl 0x001f6000
```

Independent Thumb-2 decoding gives destination `0x001f6000`. The payload
eventually branches through odd address `0x0000e1a5`, selecting Thumb state for
the original dispatcher at even code address `0x0000e1a4`. Its saved `lr`
still points to `0x00009a25`, so the backend returns to the official wrapper,
which releases the display lock exactly as before.

The compiled prologue saves `r0`, `r4..r11`, and `lr`, for 40 bytes total.
The call-site stack is eight-byte aligned, and subtracting 40 preserves that
alignment for the `dirty_add` call. The epilogue discards the saved `r0`,
restores `r4..r11` and `lr`, and tail-branches to the official dispatcher.
Unicorn execution independently confirms preservation of `r4..r11`, exact
stack restoration, the dirty call, and arrival at the dispatcher. The payload
uses no floating-point ABI and has no unresolved symbol.

Ignoring its `original_wait` parameter is safe at this exact hook because the
two bytes immediately before the call set `r1` to zero. The tail dispatch also
passes zero.

## Display and memory-safety audit

Before drawing, the payload requires all three conditions:

1. the framebuffer argument is non-null;
2. RAM word `0x1ffdb754` contains the exact 13.70 backend table
   `0x0000ebfc`;
3. startup byte `0x1fff223c` equals one.

These addresses and values match the recovered 13.70 initializer. When either
initialization guard is false, emulation records no framebuffer write and the
payload still reaches the original dispatcher.

The declared framebuffer is 240 by 240 bytes. Every write is inside rectangle
`x=50..189`, `y=102..123`; its largest linear index is 29,709, below the
57,600-byte bound. The fly occupies `x=54..74`, `y=105..120`. The text occupies
at most `x=185`, `y=119`. The initialized emulation changes exactly 3,080
bytes, with zero changes outside the declared rectangle, then calls:

```text
dirty_add(50, 102, 140, 22)
```

The call occurs while the original display wrapper owns its display lock. The
payload does not access the DMA staging buffer, dirty-list internals, FlexIO,
GPIO, or synchronization objects directly.

The instruction-level emulator intercepts `dirty_add` and the backend
dispatcher at their entries. It does not model GarminOS scheduling, the actual
lock implementations, DMA, FlexIO, or LCD palette conversion. Consequently,
the exact physical colors of byte values `0x00` and `0xff` and hardware timing
remain unproved.

## Placement audit

The selected allocation is exactly `0x001f6000..0x001f63ff`. All 1,024 source
bytes in the official decoded main image are `0xff`. The pinned Ghidra range
report records zero static references whose destination lies in this interval.
The payload occupies `0x001f6000..0x001f61c2`; the allocation's final byte at
`0x001f63ff` carries the main-stream additive repair.

The wider erased tail cannot be treated as unused: a separate report contains
19 static data references at addresses above this allocation. The exact range
report does not count defined instructions or functions, and this audit makes
no such claim. The builder and documentation were corrected to state only the
measured facts: all-`0xff` source bytes and zero static destination references.

Indirect runtime references cannot be excluded by a static-xref report. No
evidence of one was found, but that residual risk is inherent in using an
erased gap in a closed firmware image.

## Package-delta audit

The 13.71 overlay preserves package length and record layout. Its main
descriptor and image header both contain 1371, descriptor field `0x0b` remains
zero, and all four known runtime identity mirrors remain official 13.70. The
helper payload and helper descriptor are byte-identical to the official
package.

Relative to official 13.70, the overlay has 456 changed raw bytes and 454
changed decoded-main bytes. Every decoded change is confined to:

- main header version byte at decoded `0x22c`;
- four-byte hook at decoded `0x6a20..0x6a23`;
- audited overlay allocation at decoded `0x1f3000..0x1f33ff`;
- final main additive-repair byte at decoded `0x4d7fff`.

The decoded main sum is zero modulo 256. All five outer prefix checkpoints and
the recovered full-image application checks pass.

The 13.72 restore wrapper also preserves package length and layout. Its helper
payload and descriptor are official byte-for-byte. Compared with the official
main stream, only decoded header byte `0x22c` and final checksum byte
`0x4d7fff` differ. The original instruction at `0x00009a20` and all 1,024
official bytes in the overlay allocation are restored. At the GCD level, its
only four raw changes are `0xa160`, `0xa392`, `0x4e2299`, and `0x4e229e`.
Every recovered checksum passes.

The restore wrapper is therefore not byte-identical official firmware. It is
official executable code and resources carried with coherent synthetic 13.72
descriptor/header metadata and two additive repairs. That distinction is
material and is represented correctly in `docs/overlay-live-proposal.md`.

## Admission and restore audit

The earlier interpretation of descriptor field `0x0b` as an unconditional
force flag was incorrect. In `FUN_001cd670`, the unconditional scheduling arm
comes from a separate global-mode thunk. Field `0x0b` changes which parsed
version is compared. The retained field-`0x0b=1` candidates are therefore
**NO-GO** and must not be used as an admission or restoration mechanism.

The finalized pair does not depend on that field:

| Transition | Incoming descriptor/header | Recovered numeric relationship |
|---|---:|---|
| Current application to overlay | 1371 / 1371 | 1371 is newer than observed runtime 1370 |
| Overlay to restore wrapper | 1372 / 1372 | 1372 is newer than either 1370 or 1371 |

The live resource proof already demonstrated that this watch accepts modified
main descriptor/header metadata and additive repairs, and that public runtime
reporting can remain 1370 despite an installed 1369 descriptor/header. This
supports using the ordinary numeric comparison with coherent 1371 and 1372
metadata. It does not prove acceptance of these synthetic future versions,
execution of modified code, or absence of another resident-loader policy.

If the overlay boots, the 13.72 wrapper provides a credible normal-updater
route back to Garmin's executable code and resources. If it does not boot far
enough to enumerate or process a GCD, this route is unavailable. Recovery in
that failure state remains unknown.

## Guarded staging audit

Static review confirms `tools/live-proof/stage-gupdate.ps1` has distinct
`ForwardOverlay1371` and `ForwardRestore1372` profiles. They pin the exact
package paths and SHA-256 values above, require the expected FR245 USB disk,
VID/PID ancestry, model `Forerunner 245`, part `006-B3076-00`, healthy GARMIN
FAT volume, reported version 1370, adequate free space, and an absent
`GUPDATE.GCD`. The default path is dry-run; mutation requires explicit
`-Execute`. The writer uses create-new semantics, flushes, and performs a full
watch-side size and SHA-256 check.

This was a static review only. In accordance with the audit assignment, no
staging dry-run was made against the mounted watch.

## Verification performed

- Rebuilt the linked overlay with `test-build.ps1`: pass.
- Ran four package-builder tests and three Unicorn payload tests: 7/7 pass.
- Ran the six version-strategy tests, including one-byte tamper rejection:
  6/6 pass.
- Ran the complete Garmin-firmware test suite after all artifacts settled:
  36/36 pass.
- Independently parsed and compared all three GCDs and both decoded streams.
- Independently ran the recovered full-image validator on 13.71 and 13.72:
  pass for both.
- Confirmed the strict forward-pair verifier reconstructs both files exactly
  and returns `PASS`.

## Residual live risks

1. A modified instruction has not yet crossed the resident-loader boundary.
2. Synthetic 13.71/13.72 admission is strongly motivated but untested.
3. Static xrefs cannot exclude an indirect use of the erased allocation.
4. Emulator interceptions do not model real lock, dirty-list, DMA, FlexIO, or
   panel behavior.
5. Any update rewrites the full internal application and external QSPI
   destination. Interruption or runtime failure can permanently brick the
   watch because nonboot recovery is unknown.
6. The restore wrapper is usable only after a boot that retains normal USB and
   updater service.

The artifact is suitable for the next deliberate arbitrary-code-execution
test only after these exact limits and write targets are disclosed and the
specific 13.71 transfer/install action receives separate approval.
