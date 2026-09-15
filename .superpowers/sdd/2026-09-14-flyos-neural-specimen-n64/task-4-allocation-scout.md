# Task 4 independent allocation and stack scout

## Verdict

**Fail closed: no additional live/package allocation is proved safe.** The pinned images contain a strong additional erased-space candidate, but the repository still lacks a complete proprietary section/reserved-metadata inventory and an exact Ghidra occupied-unit audit for that new interval. It may be used as the next *offline audit candidate* only; this report does not authorize linking, packaging, staging, or writing a watch.

The strongest conservative candidate is `0x001f70f6..0x001f77ff` (1,802 bytes). Every byte is `0xff` and byte-identical in official 3.10, official 13.70, and the decoded 13.73 installed-candidate image. A stride-one scan finds no exact or Thumb-normalized 32-bit target window in either byte order in any of those decoded images, or in the complete 13.70/13.73 GCD containers. Existing full-tail Ghidra reports show no recovered direct reference to the interval. It lies inside one executable internal-flash memory block and one ordinary `0x02bd` data-record body. Those observations are strong but do not prove semantic ownership.

If an exact read-only Ghidra unit/reference/symbol audit and a recovered metadata exclusion approve this interval, its 1,802 bytes are enough to avoid forcing the current N64 sources into the two installed allocations. The current unlinked freestanding size estimate is about 3,507 bytes after obvious link garbage collection, versus 3,071 usable bytes in the two existing allocations; the third interval would raise capacity to 4,873 bytes.

## Scope and pinned evidence

This scout read local artifacts only. It did not access or modify the USB watch, create or modify firmware, touch quarantine packages, stage an update, or edit shared implementation. The only written file is this report.

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| 3.10 decoded `stream_01_fw_all_bin.bin` | 4,201,216 | `3225c50585503d331a9c0ee8faf342241207dd98825f4f0f9cf3fa23831c54ba` |
| 13.70 decoded `stream_01_fw_all_bin.bin` | 5,079,040 | `b45be1baf98999af10f073bef52b284beb2aea6abbb7cde2ffa59fb6bcedeab6` |
| 13.73 quarantined GCD, read only | 5,120,675 | `4ec78eabd23a880ad5d4e9ff52e688e62397480a32070316b2748b70b771c9d7` |
| 13.73 decoded `0x02bd` stream recovered in memory | 5,079,040 | `3b944f381d33be65ade1d6f27f99ad3d911c32f1a8d4e092455ae581e9584a35` |
| 13.70 broad-tail Ghidra xref export | 992 | `67a10e0ddd1cc5eb5fc71786ed64309ec8e85e6ef6e1aecc8440effeb2bdb0c1` |
| Prior second-allocation evidence | 213,409 | `01a2511202c4b28a2adb9990632d50fe94d8107ae27ae963cf3feeed62417101` |

The 13.70 and 13.73 decoded-image difference count is 2,773 bytes, confined by the existing package evidence to the current hook, current primary/secondary payloads, version, and repair bytes. The new candidates below are unchanged between them.

The internal-flash mapping is decoded offsets `[0,0x1fd000)` to runtime `0x00003000..0x001fffff`. Ghidra marks this containing block initialized, readable, writable, and executable. That is a coarse processor mapping, not a linker-section ownership declaration.

Existing allocated envelopes are:

| Interval | Envelope | Current compiled use | Usable for target code/data |
| --- | ---: | ---: | ---: |
| `0x001f6000..0x001f63ff` | 1,024 | 794 | 1,023; `0x001f63ff` is reserved for additive repair |
| `0x001fa400..0x001fabff` | 2,048 | 2,044 | 2,048 |
| **Total** | **3,072** | **2,838** | **3,071** |

## Search method

The search started at the confirmed 13.70 erased-tail boundary `0x001f5e0c` and ended at `0x001fffff`. It excluded the two current allocations, required byte identity and `0xff` fill in 3.10/13.70/decoded-13.73, and treated every target of every four-byte window at every source offset as occupied. The native scan decoded little-endian values and also cleared bit zero for Thumb aliases. A stricter defensive pass also rejected big-endian-looking windows, although the target CPU is little-endian. Known Ghidra reference destinations were rejected separately.

The existing cross-version Ghidra reports cover references throughout the erased tails. In 13.70 the first recovered reference target after these proposed candidates is `0x001fc07f`; in 3.10 the reported tail references likewise skip both proposed intervals. The current 13.73 target manifest/disassembly has only its reviewed primary/secondary branches, and contains no textual target in either proposed interval. This is evidence of no *observed* direct reference; it cannot exclude computed references.

## Exact candidate intervals

| Candidate | Bytes | Fill/hash in 3.10, 13.70, 13.73 | Pointer windows | Existing Ghidra direct refs | Record/section evidence | Result |
| --- | ---: | --- | --- | ---: | --- | --- |
| `0x001f70f6..0x001f78b3` | 1,982 | all `0xff`; `650093b89c8567b363508f761eae0e5e989d1847c891d800a8733acd83f14602` | 0 native LE; 3 BE windows in 3.10 and 4 in 13.70/13.73 | 0 observed | one internal executable block and one `0x02bd` body | Native-endian maximum, but not preferred because of defensive BE hits and incomplete semantics |
| **`0x001f70f6..0x001f77ff`** | **1,802** | all `0xff`; `091ae94226944c38fcc7e1ad3904e2132bfb32e3033d81ffebea89d39eee7aa7` | **0 LE and 0 BE in all decoded images and both full 13.70/13.73 GCDs** | **0 observed** | one internal executable block and one `0x02bd` body | **Strongest next offline audit candidate; not approved storage** |
| `0x001f98c0..0x001f9d0f` | 1,104 | all `0xff`; `e5b1a2f18106628e4d59578585acbc5c856def7a4d15242e331f9660199fc930` | 0 LE and 0 BE in all decoded images and both full 13.70/13.73 GCDs | 0 observed | one internal executable block and one `0x02bd` body | Fallback offline audit candidate; not approved storage |

The preferred 1,802-byte interval maps as follows in both the 13.70 and 13.73 GCD layouts:

- runtime: `0x001f70f6..0x001f77ff`
- decoded main offsets: `0x001f40f6..0x001f47ff`
- raw GCD offsets: `0x001fe2d8..0x001fe9e1`
- containing record: one ordinary `0x02bd` body of 65,280 bytes; no record header/checkpoint is crossed

The 1,104-byte fallback maps to decoded offsets `0x001f68c0..0x001f6d0f` and raw GCD offsets `0x00200aa2..0x00200ef1`, also wholly inside one ordinary 65,280-byte `0x02bd` body.

Thumb-2 `BL` range checks pass in both directions between the preferred interval and the hook/current allocations. Representative signed displacements range from `-13,134` to `+2,023,054`, well inside the signed 25-bit even-displacement range. Reachability says nothing about ownership.

### Why none is proved

These gaps remain for every new interval:

1. No exact Ghidra audit yet counts overlapping instructions, defined data, functions, and symbols for the interval in both pinned official databases. The full-tail reports establish direct-reference absence, while the exact occupied-unit reports currently cover only `0x001fa400..0x001fabff`.
2. No complete image-bound section or reserved-field map excludes proprietary resource directories, fixed-offset reservations, or opaque boot/update trust metadata. Being in an ordinary `0x02bd` body and coarse executable memory block is insufficient.
3. Pointer-window scans cannot disprove address computation at runtime.
4. The candidate has not been linked with exact assertions or exercised through every inter-segment transfer under Unicorn.

Therefore the maximum **proved additional allocation is 0 bytes**. The maximum **observed-clean offline candidate** is 1,802 bytes under the stricter scan, or 1,982 bytes under native little-endian semantics.

## N64 size feasibility

I compiled the current source snapshots to assembler listings only, using Arm GNU Toolchain 15.2.Rel1, Cortex-M4 Thumb, soft-float, `-Os`, freestanding/no-builtins, function/data sections, and the same unwind exclusions as the installed target. The compiler executable SHA-256 is `8f35ba82ea8983df63614fd8ee4235dae33569d07c64211046f486bf4f738035`.

Pinned source snapshots:

| Source | SHA-256 | Emitted code + read-only data before link GC |
| --- | --- | ---: |
| `flyos/fly/brain64.c` | `99759878d857a2ba047f4ff6c63de49bdcb65a9a8231cf285782e57baf5eada3` | 1,098 bytes |
| `flyos/display/neural_specimen.c` | `2ab33de9fba7b9c55f6077d1729063dd5f5b927fa71b51146288c8387393e282` | 2,227 bytes |
| minimal target wrapper equivalent to the current wrapper, compiled from standard input | ephemeral | 232 bytes |

The raw sum is 3,557 bytes. `fly_brain64_level` and `fly_brain64_state` are not needed by the current renderer/target path and should be removed by `--gc-sections` (50 bytes), giving an estimated linked floor near 3,507 bytes before alignment. That exceeds the existing 3,071-byte usable capacity by about 436 bytes. **The current sources cannot be assumed to fit the two existing intervals.**

Fitting without a third interval is plausible but unproved. Concrete likely savings are procedural 8x8 coordinates instead of the 256-byte point table, procedural/direct contour generation instead of the 104-byte contour table, and a procedural or denser edge description instead of 360 bytes. These three areas expose 720 bytes of read-only data before accounting for replacement instructions. Text/font/string deduplication can add margin. The target implementer must demonstrate an actual bounded ELF/map; source-level arithmetic is not a linker proof.

With the preferred 1,802-byte candidate, total usable capacity becomes 4,873 bytes. The current estimated 3,507-byte N64 payload plus alignment and a four-byte hook would have roughly 1.3 KiB margin, and individual section sizes can be split across three nearby intervals without veneers. This capacity observation remains offline-only until the allocation itself passes the missing evidence gates.

## 384-byte target-owned stack audit

Assembler listings for the current sources show:

| Function/path | Frame including saved registers | Nested path total before wrapper |
| --- | ---: | ---: |
| `fly_brain64_step` | 184 bytes (`push` 36 + `sub sp` 148) | 184 |
| `fly_brain64_reconstruct -> fly_brain64_step` | 16 + 184 | 200 |
| `fly_neural_specimen_render -> unsigned -> text` | 56 + 48 + 48 | 152 |

A minimal realistic wrapper with local `FlyBrain64` (140 bytes), zeroed `FlyBrainInputs` (12 bytes), button/RTC reads, render, dirty call, and original dispatch compiled to 168 bytes (`push` 12 + `sub sp` 156). Calls are sequential, so the maximum modeled target-owned chain is:

`overlay_then_flush` 168 + `fly_brain64_reconstruct` 16 + `fly_brain64_step` 184 = **368 bytes**.

This is under the 384-byte ceiling by only 16 bytes. The renderer path is 320 bytes. Stack feasibility is therefore **possible but fragile**. Any coexistence-state locals, spill change, different compiler behavior, or added adapter can breach the limit. Task 4 must consume compiler `.su` files and disassembly, compute the real call graph, and reject anything over 384. Safer options include keeping the wrapper leaf state minimal and using a bounded framebuffer scratch area for the `FlyBrain64`/inputs after the frame is cleared, provided emulation proves final full-frame ownership and no guard corruption. Interrupt/stock frames remain outside this target-owned accounting, consistent with the existing audit convention.

## Required next evidence before allocation use

1. Run an exact, read-only Ghidra audit for `0x001f70f6..0x001f77ff` against both official 3.10 and 13.70 dual-map projects, including every byte, references, instructions, defined data, functions, symbols, mapped-block hashes, and completion markers.
2. Extend the byte-precise metadata audit to this exact interval and explicitly exclude all identified headers, startup/zero/copy tables, relative tables, update-region tables, checksums, resource directories, and opaque reserved spans. If complete semantic exclusion cannot be established, retain an offline-only status.
3. Link the final target with explicit assertions for every segment, pin all source/evidence hashes, and permit no implicit orphan section.
4. Emulate every inter-segment branch and return, exact read allowlist, framebuffer guards, original dirty/dispatch tail calls, register preservation, critical-screen pass-through, and the 384-byte stack ceiling.

Until all four pass, Task 4 should either optimize into the two already-audited intervals and prove the final ELF, or stop at a host/offline result. It must not treat this scout as package permission.
