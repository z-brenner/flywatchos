# Task 4 report - FR245 13.70 Neural Specimen N64 target

## Result

**Offline target build, emulator, deterministic evidence, and regressions pass.**
No GCD package, quarantine artifact, live staging file, or watch file was created
or modified.

The target uses only the two audited envelopes. Primary uses 1,016/1,023 bytes,
secondary uses 2,034/2,048 bytes, and the payload total is 3,050/3,071 bytes.
The repair byte at `0x001f63ff` and every third-allocation candidate remain
unused. Static call-graph analysis and Unicorn both reach exactly the allowed
384-byte target-owned stack ceiling.

## Review fixes

The former validate-then-vendor-walk implementation was removed. The target now
uses an inline bounded scan twice, with bracketed root reads. Each scan validates
every locally captured `next` before dereference, rejects unaligned/out-of-range
nodes, cycles, and a ninth node, and requires the same first callback match to
be the first visible node in both observations. Detectable root, callback/finder,
or visibility changes return false and preserve all 57,600 framebuffer bytes.

The target has only two indirect external transfers: full-screen dirty
`0x0000f2e9` and original display dispatch `0x0000e1a5`. It never transfers
control to the stock list walkers. The real pinned bodies at image addresses
`0x0005306c` and `0x000530cc` execute only in a separate offline Unicorn oracle.
Stable empty/valid/hidden/missing/multiple fixtures match their semantics.
Malformed, cyclic, and overlong fixtures demonstrate the target's stricter
bounded fail-closed policy; for example, stock can return true when the first
node matches even though a cyclic or ninth-node tail exists, while the target
rejects the full list.

No read-only implementation can prove the list remains unchanged after its
final read without a proved Garmin lock or generation counter. An ABA change
restored before re-observation is also indistinguishable from stable state. The
remaining risk is a transient overlay during that final-read-to-render window;
the mutation cannot cause an unvalidated node dereference or an unexpected
control-flow target.

Rendering now includes exact `MOTION --` and correct battery values including
the full `B 100`. Independent framebuffer tests cover `B 0`, `B 9`, `B 10`,
`B 73`, `B 99`, and `B 100`. The reviewed RGB222 palette is enforced as exactly
`0x00`, `0x0c`, `0x2a`, `0x33`, `0x38`, and `0x3f`; a forced level-3 action-cell
fixture proves 25 amber `0x38` pixels at neuron 56. Default, battery-100, and
saturated PNG/PPM previews are generated deterministically.

The contextual button footers remain explicit within the hard storage limit:
`LIGHT>LUX`, `START>BURST`, `DOWN>CALM`, and `UP>PULSE`. BACK remains the fifth
button and exits before list/sensor reads. Battery uses only the cached binary32
word, and USB indicates only cached mass-storage states 3/4. HR, motion values,
charging, generic attachment, and update pending remain unavailable.

## Evidence and reproducibility

The 19-test focused suite creates a process-private build and process-private
host-oracle directories. It also performs two clean isolated builds and asserts
byte identity for the ELF, hook, both payload segments, build manifest, and SHA
ledger. A separate test generates two evidence directories and asserts every
report/preview byte and manifest hash is identical. The evidence manifest omits
itself by an explicit policy, avoiding a self-hash paradox.

The subsequent housekeeping gate removes the complete generated `oracle/`
tree before retaining the single canonical oracle. `load_build` and
`check_build` now compare every generated file with the manifest allowlist and
reject `oracle/tests` or any other untracked build output. The 14 legacy shared
test-oracle directories were removed; focused emulation continues to compile
only in process-private temporary directories outside the canonical build.

Final sequential validation:

```text
Focused Task 4: Ran 19 tests in 215.159s - OK
Housekeeping/immutable-evidence focus: Ran 2 tests in 54.866s - OK
Seeded legacy-oracle cleanup focus: Ran 1 test in 5.501s - OK
Full firmware-analysis discovery: Ran 137 tests in 538.264s - OK
Shared C/CTest: 7/7 passed
Python py_compile: passed
Evidence manifest: 7 evidence files + 5 build files independently rehashed
```

The full suite covers framebuffer/null/BACK guards, stable and adversarial view
lists, three mutation points, exact reads, all five buttons, battery bit patterns
and glyph regions, USB 0..6, RTC retry/sentinel behavior, framebuffer canaries,
write confinement, registers/LR/SP, dirty/dispatch ABI, all 39 inter-segment
branches, all 64 neuron cells, host Brain64/renderer equivalence, all palette
roles, safe radius, deterministic reconstruction/builds/evidence, no floating
point, no writable static storage, and exact allocation identity.

## Final artifacts and SHA-256

| Artifact | SHA-256 |
| --- | --- |
| `overlay.c` | `90f4b03c4ec9a18c942fb3109776c33f4810c056f96ac7d88b938c7cb25b0ea0` |
| `renderer.c` | `3c8949b768fbd449836095418a595c8518d5507ef395e1656d29967bb5cbbde3` |
| `build.ps1` | `1f8b598f21d49334099157070ed1a46e6d45487af1e288cd96e0397a145c5a91` |
| target `README.md` | `fd0eb7d8abb7f853589ee241e05582671229151bb637c0de43c6d7dc0a405174` |
| emulator | `2b323f5f5c1476da87c19b2a0767d2a20b9466ac4d096b19923f101fa5e49a26` |
| focused tests | `3ad752e6bc9c8e367162dea42aea00fb99465fa1cc004bf8645a9298c71730ed` |
| allocation JSON | `86251e3cbaa39fa46b0986d39a84f48864f9c51fb15b59fafec5b6af3406f4bb` |
| placement document | `0564090a636b3ad2449e7f4663db6c2be587ea93efc2953b484d4ce1cd37a923` |
| build manifest | `b358b89867076e594c545447267819fc92ba1fa8290c2d4c0213c1ec332acfbe` |
| hook binary | `49ff680c8b811f58b6747fea531fcbc8b88b3142946a1cad4271e0911f02a362` |
| primary binary | `fd7e2064e0e513169b6f2aa4643603e0ea1c274a695960a6d436d54dbb2ca282` |
| secondary binary | `f8c7f544f9bbf72fc1dd164852ebdc8c7e1d5f53c52e68f9be83f781ed3d2406` |
| emulator report | `d11609d1bf4536141abb81762e9a973a82c3059aeb649632999ebb05d2323033` |
| default preview PNG | `8703a53cc8baa4fc1e028386e091c43cbd4c20988c524b609d590e2e8333fc51` |
| battery-100 preview PNG | `d4869fec7296887fa7d087c57145090b9f5080d677c8826f7014210b0fde4a98` |
| saturated preview PNG | `d23d5441f0dd2b59b61b05fb6d38f46df99f072d98bc898908654d8dd506cbd1` |
| evidence manifest | `a0cc54142febda3d12033dc8d9a37358022ac871989aca0252ae475b110889ba` |
| build output | `93b4498705331725c6adbfe279ecb9854116ebbb0859c079a6515200c085dcd6` |

The pinned runtime-state SHA-256 remains
`53d05da7623b14772e466118c45dda93fdae482085aa194100bbafeb474a7e5d`.
This offline result does not authorize packaging or a live watch write.
