### Task 4: N64 target integration, coexistence, allocation, and emulation

Implement Task 4 from `docs/superpowers/plans/2026-09-14-flyos-neural-specimen-n64.md` after Task 3 review is clean.

#### Hard storage and stack gates

- Use only the two existing audited envelopes: primary `0x001f6000..0x001f63ff` and secondary `0x001fa400..0x001fabff`.
- Reserve primary byte `0x001f63ff` for additive repair, leaving exactly 3,071 usable bytes total.
- Do not use the unproved third-allocation candidates in `task-4-allocation-scout.md`.
- Linker assertions must reject overflow, segment overlap, hook changes, undefined symbols, or use of the repair byte.
- The complete target-owned call chain must be at most 384 bytes by `.su`, disassembly, and Unicorn runtime observation. Fail closed if size or stack does not fit.

#### Runtime inputs and pass-through

- Consume `artifacts/firmware/analysis/fr245-1370-runtime-state.json` and reject any image/hash or allowlist mismatch.
- The overlay may render only after an affirmative, bounded inline watch-face predicate that implements the stable-list semantics proved from pinned 13.70 image bodies `0x0005306c`/`0x000530cc`, callback `0x0005adf5`, and root `0x20003e84`. The target must not call the vendor walkers after a separate validation pass; the real routines serve as the offline equivalence oracle. Null, malformed, cyclic, too-long, concurrently inconsistent, unexpected, or false state must pass through byte-for-byte.
- The target's only indirect external transfers are the pinned dirty routine and original display dispatch. The inline predicate validates each locally captured `next` before dereference, bounds/cycle-checks both observations, and rejects any detectable root/finder/visibility disagreement. Without a proved lock or generation counter, an ABA change or mutation after the final read is observationally irreducible; it may cause a transient overlay but cannot redirect a target read or control transfer outside the allowlist.
- BACK held (active-low GPIOD PDIR `0x400ff0d0`, bit 1) always forces pass-through.
- Other buttons remain the proved PDIR reads: LIGHT C11, START D10, DOWN A20, UP A22.
- Battery may read only cached binary32 at `0x1ffcccd8`, accepting finite `[0,100]` and rejecting `-1.0`; no floating-point instructions/runtime helpers are allowed, so validate/convert by integer bit logic.
- USB may expose only the narrow mass-storage state from byte `0x1ffc6f25`, where values 3/4 are true. Do not call it generic attachment or charging.
- Charging, update pending, HR BPM, motion, and target color mapping remain invalid/unavailable. Garmin's own non-home charging/update screens must pass through; START remains Garmin's native update confirmation.
- The independently reviewed Task 3 palette supersedes the former monochrome fallback. Use exact RGB222 native bytes: background `0x00`, scaffold `0x2a`, text `0x3f`, excitatory `0x0c`, inhibitory `0x33`, saturated `0x38`. Pin runtime-state JSON SHA-256 `53d05da7623b14772e466118c45dda93fdae482085aa194100bbafeb474a7e5d` and reject any change.

#### Behavior and compactness

- Preserve exact 64-neuron direct mapping and N64 model semantics. Use procedural 8x8 coordinates and compact procedural/table encodings for contours, font, labels, and edges to fit. Do not silently reduce neuron count or fake optional sensors.
- Preserve the redesigned angular fly-head layout and centered unclipped `FLYOS // N64`/`PHASE` presentation within the 114-pixel circular safe radius.
- Preserve contextual physical-edge behavior labels and held-button cause/effect footer.
- Call the original dirty routine and original display dispatch exactly as the proven live hook requires, preserving callee-saved registers and SP.

#### TDD/emulation deliverables

- Create the planned target directory, emulator, tests, allocation JSON, placement doc, build manifest, map, disassembly, `.su` files, hashes, emulator report, and rendered oracle/preview evidence.
- Start with failing tests. Cover all display guards, empty/malformed/valid/multiple view-list cases, exact allowlisted reads/control flow, all five buttons, BACK override, battery valid/invalid bit patterns, USB states, RTC rollover, unchanged non-home/critical frames, framebuffer canaries, no writes outside framebuffer/stack, every inter-segment branch, original dirty/dispatch calls, all 64 cell correspondence, register/SP preservation, deterministic reconstruction, and stack/size ceilings.
- Cross-check target output against the host Brain64/renderer semantics. Any deliberate compact-target rendering difference must be enumerated and independently testable.
- Do not create or modify GCD packages, quarantine artifacts, live staging profiles, or watch files.

Write `task-4-report.md` with RED/GREEN evidence, exact hashes, size/stack figures, and unresolved risks.
