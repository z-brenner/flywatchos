# Offline GarminOS FlyOS overlay candidate

## Result

An offline 13.70 package now contains a linked 451-byte Thumb payload that
draws a framed scientific specimen plate with a 21 by 16 pixel dorsal fly
silhouette and `FLY LIVES` into GarminOS's live 240 by 240 framebuffer, marks
the rectangle dirty, and resumes the official display flush. It has not been
transferred to or executed by the watch. The earlier text-only candidate is
preserved under its original filename.

This is an in-app arbitrary-code-execution candidate, not the standalone
FlyOS target. It deliberately keeps Garmin's clocks, scheduler, power setup,
display conversion, locks, DMA, and FlexIO driver active.

## Hook and payload

The exact 13.70 display wrapper at `0x00009a10` owns Garmin's display lock. Its
four-byte call at `0x00009a20` originally dispatches the framebuffer in `r0`
to `0x0000e1a4`. The candidate replaces only that instruction:

```text
original: 04 f0 c0 fb    bl 0x0000e1a4
patched:  ec f1 ee fa    bl 0x001f6000
```

The payload at `0x001f6000`:

1. verifies the framebuffer is non-null;
2. verifies the active backend pointer at `0x1ffdb754` is `0x0000ebfc`;
3. verifies startup-complete byte `0x1fff223c` is one;
4. writes only rectangle `(50,102)` through `(189,123)` in the framebuffer;
5. calls dirty-rectangle function Thumb address `0x0000f2e9` with
   `(50,102,140,22)`;
6. tail-dispatches the original flush through Thumb address `0x0000e1a5`.

The linked disassembly preserves AAPCS callee-saved registers and eight-byte
stack alignment. The tail call retains the original wrapper's lock/unlock and
return behavior.

## Placement evidence

The selected allocation is the 1,024-byte interval
`0x001f6000..0x001f63ff`. In the pinned official main image every byte in this
interval is erased value `0xff`, and Ghidra reports zero static references into
the exact allocation. The range-reference report does not measure defined
instructions or functions. The wider erased tail contains 19 data references
at higher addresses, so the builder and report intentionally make no claim that
the entire tail is free.

Evidence report:

```text
artifacts/firmware/analysis/code-cave-overlay-xrefs-1370.txt
SHA-256 760721bee4bdf216b7064adf5f5d23507e0d5f2995610dbcc7cba27bf8fe31f2
```

## Artifact and checks

| Artifact | SHA-256 |
|---|---|
| Overlay package | `7af3031b222e472f9fab54e148112c56d41a93b30340d5a55899be57c818c9df` |
| Decoded candidate main | `5a96be19bcb96080cab1f47fee57ea663bb93b0ee92197edc49229bcd93950d8` |
| Hook binary | `49ff680c8b811f58b6747fea531fcbc8b88b3142946a1cad4271e0911f02a362` |
| Payload binary | `62ea46c67c565f571789d1437de318de785d90a2fef0a79d702b6d2ba6b3dee1` |
| Candidate report | `274f9112d4b53005b70b9c5c8c6138d0a8196e76cb901b6d516867e32650604c` |
| Emulator report | `c0b2e3b6c9e54d79a97da99d7bfbe743d81b32c78661eb9748844c2afad9820c` |
| 240 by 240 PGM preview | `f2d849d46204d942d94f41099206eaee4c6f92a989d4ac398211676f640d31a2` |

The quarantined package is
`artifacts/firmware/quarantine/Forerunner245_1370_flyos-scientific-fly-overlay.gcd.analysis-only.DO_NOT_INSTALL`.
It has 452 changed main-stream bytes, all confined to the four-byte hook and
the audited 1 KiB allocation. The official helper and both descriptors remain
byte-identical; the main additive sum and every outer checkpoint pass.

`flyos/target/fr245_1370_overlay/test-build.ps1` verifies the linked addresses,
section sizes, hook encoding, payload calls, and forbidden undefined symbols.
The Python builder verifies the pinned inputs, exact erased allocation, exact
zero-reference report, branch target, payload bounds, diff confinement,
helper/descriptor identity, and both confirmed checksum layers.

## Remaining risk

The candidate is not ready for the first live experiment. Its package version
remains 13.70, so normal restoration with official 13.70 is skipped. The
resident loader may reject modified code, and a late rejection or interrupted
full-image rewrite can leave the application unbootable. Pixel values `0x00`
and `0xff` are expected to contrast but their exact panel colors are not yet
proven.

The resource-only matched-13.69 candidate has now been accepted and boots, but
the watch still reports 13.70. This executable payload remains version-neutral
offline material. A separate packaging analysis must establish a viable
same-version admission and restoration strategy before any live overlay trial.
