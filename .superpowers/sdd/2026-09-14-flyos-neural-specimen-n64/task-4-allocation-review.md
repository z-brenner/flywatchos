# Task 4 independent allocation and stack re-review

Date: 2026-09-15. Scope: final FR245 13.70 Neural Specimen N64 hook,
ELF/segments, linker/map/disassembly, allocation and runtime-state evidence,
stack-usage files, emulator, focused tests, evidence publication, and the
previous parallel-oracle finding. The preserved official 13.70 and 3.10 bytes
under both payload envelopes were also read directly.

## Result

**SPEC PASS**  
**QUALITY PASS**

No P0-P3 finding remains. The previous P3 parallel host-oracle collision is
resolved: focused tests use a process-private build, ordinary oracle calls use
unique temporary directories, and retained oracle output is scoped beneath the
caller-supplied private build root. Two builds launched concurrently into
separate empty roots both passed and reproduced the exact same ELF, binaries,
manifest, and SHA ledger.

No target source, firmware image, package, quarantine artifact, staging path,
or watch file was modified during this review. All reviewer builds and oracle
outputs were confined to automatically cleaned temporary directories. This
review file is the only repository artifact changed by the reviewer.

## Exact final placement

| Item | Address/range | Size | SHA-256 |
| --- | --- | ---: | --- |
| Hook | `0x00009a20..0x00009a23` | 4 | `49ff680c8b811f58b6747fea531fcbc8b88b3142946a1cad4271e0911f02a362` |
| Primary | `0x001f6000..0x001f63f7` | 1,016 | `fd7e2064e0e513169b6f2aa4643603e0ea1c274a695960a6d436d54dbb2ca282` |
| Secondary | `0x001fa400..0x001fabf1` | 2,034 | `f8c7f544f9bbf72fc1dd164852ebdc8c7e1d5f53c52e68f9be83f781ed3d2406` |

Payload use is 3,050/3,071 bytes. The 21-byte payload margin is split and is
not fungible: seven usable primary bytes remain at `0x001f63f8..0x001f63fe`,
and fourteen secondary bytes remain at `0x001fabf2..0x001fabff`.
`0x001f63ff` remains reserved for additive repair and is not in `.primary`.

The hook bytes are exactly `ec f1 ee fa`; independent Thumb decoding yields
one `bl 0x001f6000`. `n64_overlay_then_flush` is at that exact target address.
The linker binds the hook and both payload origins, limits primary to `0x3ff`
bytes and secondary to `0x800`, asserts no overlap, and rejects writable static
storage. The link uses `--no-undefined`. Independent ELF inspection found only
the three allocated sections `.hook`, `.primary`, and `.secondary`; `nm -u`
returned no symbol.

The canonical allocation JSON is SHA-256
`86251e3cbaa39fa46b0986d39a84f48864f9c51fb15b59fafec5b6af3406f4bb`.
It declares exactly the two audited payload envelopes, the reserved repair
byte, 3,071 usable bytes, `third_allocation_used: false`,
`packaging_allowed: false`, and `live_write_allowed: false`. No ELF section,
symbol, literal, direct branch, or emulated execution used a third interval.

Direct reads of the official decoded images confirmed the complete allocation
envelopes remain erased in both versions:

| Official image | Image SHA-256 | Primary 1,024 bytes | Secondary 2,048 bytes |
| --- | --- | --- | --- |
| FR245 13.70 | `b45be1baf98999af10f073bef52b284beb2aea6abbb7cde2ffa59fb6bcedeab6` | 1,024 `0xff`; `5f4ecdb7b71c3e403983fe405cddcdc2f2576b655fdb3e80d94a6f7c32e58bc2` | 2,048 `0xff`; `d0ff1b294b5288d1ae1421eadf5b2d38a8752b76d472ff30bed9028e25b1c5b8` |
| FR245 3.10 | `3225c50585503d331a9c0ee8faf342241207dd98825f4f0f9cf3fa23831c54ba` | 1,024 `0xff`; same interval hash | 2,048 `0xff`; same interval hash |

The repair byte is `0xff` in both images.

## Rebuild and evidence integrity

The focused suite performed two clean isolated builds and asserted byte
identity for the ELF, hook, primary, secondary, manifest, and SHA ledger. The
reviewer separately launched two builds concurrently in private empty roots.
Both completed successfully and were byte-identical for those same six files:

| Build artifact | SHA-256 |
| --- | --- |
| ELF | `42fb252f7d238921e3bf84304bbe6bf07ad55bfa73cf6e1d7f1fe561cb3982f5` |
| Hook | `49ff680c8b811f58b6747fea531fcbc8b88b3142946a1cad4271e0911f02a362` |
| Primary | `fd7e2064e0e513169b6f2aa4643603e0ea1c274a695960a6d436d54dbb2ca282` |
| Secondary | `f8c7f544f9bbf72fc1dd164852ebdc8c7e1d5f53c52e68f9be83f781ed3d2406` |
| Manifest | `d65994a443e966b07796e4d560d09225ca6b85439dc521e78a26f468e4b338e6` |
| SHA ledger | `2c254c495b31e2ad864d1b21d740dea53ac86e4f4ce13f454d061666203e1a91` |

All 18 entries in `SHA256SUMS.txt` rehashed successfully. The exact pinned
runtime-state JSON is
`53d05da7623b14772e466118c45dda93fdae482085aa194100bbafeb474a7e5d`,
and the standalone evidence gate accepted both canonical hashes.

The evidence manifest is SHA-256
`18481b1bcc53d29781395e58711141de2f515a61860e997030ffdd82ed9f8e7f`.
All seven evidence files and five referenced build files matched both the size
and hash recorded in it. Its explicit policy intentionally omits the evidence
manifest from its own file map. Key published hashes also match the Task 4
report: emulator report `307b3c724c087ac7459dabbc92a29b53e1205122727d880b3099f4f01eca22a4`,
default PNG `8703a53cc8baa4fc1e028386e091c43cbd4c20988c524b609d590e2e8333fc51`,
battery-100 PNG `d4869fec7296887fa7d087c57145090b9f5080d677c8826f7014210b0fde4a98`,
and saturated PNG `d23d5441f0dd2b59b61b05fb6d38f46df99f072d98bc898908654d8dd506cbd1`.

## Control transfers and palette contract

Independent disassembly scanning found exactly two non-return indirect target
transfers:

| Site | Instruction | Callable pointer | Executed body address | Purpose |
| --- | --- | --- | --- | --- |
| `0x001f6100` | `blx r4` | `0x0000f2e9` | `0x0000f2e8` | full-screen dirty |
| `0x001f6110` | `bx r3` | `0x0000e1a5` | `0x0000e1a4` | original display dispatch |

The odd values are callable Thumb pointers and the even values are instruction
addresses observed by Unicorn. The only other `bx` in the target is the normal
`bx lr` return from `fly_brain64_update_state`. The binary has no literal for
the former vendor walker addresses `0x0005306d` or `0x000530cd`; those bodies
are used only by the separate offline oracle. The target instead uses its
bounded inline `scan_home` twice. It validates every captured next pointer,
rejects malformed, cyclic, and ninth-node lists, and requires both observations
to return the same eligible node.

The static audit declares 39 cross-segment direct transfers. Independent
Unicorn runs for default, battery-100, and all four model-button fixtures
executed the union of all 39. Each render called only dirty and dispatch, in
that order, with body addresses `0x0000f2e8` and `0x0000e1a4`.

The allocation contract fixes native bytes to exactly
`[0x00, 0x0c, 0x2a, 0x33, 0x38, 0x3f]`. The pinned runtime state assigns them
to background, excitatory, scaffold, inhibitory, saturated, and text,
respectively. The evidence gate compares the complete canonical JSON object,
including this exact list, so mutation, addition, removal, or reordering fails
closed. The focused saturated-neuron test observed all six values and checks
the expected 25 amber `0x38` pixels.

## Stack proof

Fresh `.su` files report the deepest target-owned chain as:

```text
flyos_hook_patch                         0
  -> n64_overlay_then_flush            184
    -> fly_brain64_reconstruct          16
      -> fly_brain64_step              184
        -> fly_brain64_update_state      0
                                         ---
                                         384 bytes
```

The instructions independently support those frame sizes: entry saves six
registers (24 bytes) and subtracts 160; reconstruct pushes four registers
(16); step saves nine registers (36) and subtracts 148. Recomputing the full
acyclic manifest call graph gives the same 384-byte chain. Six independent
Unicorn render fixtures each observed exactly 384 bytes, restored SP, and
stayed within the framebuffer/stack write allowlist.

This meets the specification exactly and has zero target-owned stack margin.
Stock dirty/dispatch frames, interrupts, and unknown Garmin task headroom are
outside this accounting.

## Verification run

```text
python -B -m unittest tools.garmin-firmware.tests.test_emulate_neural_specimen_n64 -v
Ran 19 tests in 275.119s
OK

two concurrent powershell build.ps1 -BuildRoot <private-empty-root> invocations
PASS; exact ELF/segment/manifest/SHA-ledger equality

python -B tools/garmin-firmware/emulate_neural_specimen_n64.py --check-evidence
PASS; canonical allocation and runtime-state hashes returned

independent evidence-manifest and SHA256SUMS rehash
PASS; 12/12 manifest references and 18/18 ledger entries matched

independent Unicorn fixture union
PASS; 384-byte maximum, SP restored, 39/39 transfers covered
```

## Prior findings and remaining risks

The former shared `build/oracle/tests/<fixture>/oracle.exe` race is addressed.
No sharing error occurred in the 19-test run, and simultaneous private builds
completed successfully with identical output.

The remaining risks are accepted, documented constraints rather than review
failures:

- Stack use reaches the 384-byte limit with no target-owned margin.
- Payload space has only seven primary and fourteen secondary bytes free.
- Without a proved list lock or generation counter, an ABA mutation or change
  after the final read can cause a transient overlay. The bounded target does
  not dereference an unvalidated pointer or transfer control through the list.
- The result authorizes offline linking and emulation only. Packaging and live
  write remain explicitly disabled, and this review provides no live-watch
  execution evidence.
