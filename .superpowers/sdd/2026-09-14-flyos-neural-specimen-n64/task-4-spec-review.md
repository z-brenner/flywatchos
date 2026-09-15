# Task 4 Spec and Behavior Review

SPEC: FAIL

QUALITY: FAIL

1. **HIGH - `flyos/target/fr245_1370_neural_specimen_n64/overlay.c:L25-L47`:** `home_active` validates the live view list and then separately calls both Garmin walkers; a concurrent mutation can redirect those calls outside the validated node set, so malformed state is not guaranteed to pass through and exact read confinement is not proved. Establish an image-bound scheduling invariant that keeps the list immutable across all three walks, or replace the split predicate with an approved bounded equivalent; emulate mutation between validation and each vendor call.
2. **HIGH - `flyos/target/fr245_1370_neural_specimen_n64/renderer.c:L57-L60`:** battery value 100 renders `10` because the `>= 100` branch emits `1`, sets `value` to zero, then emits only one `0`. Emit both trailing zeroes and add an independent framebuffer glyph assertion for `B 100`; the shared target-renderer oracle cannot catch this bug.
3. **MEDIUM - `flyos/target/fr245_1370_neural_specimen_n64/renderer.c:L109-L116`:** the target status rail omits the design-required `MOTION --`; `docs/neural-specimen-n64-placement.md:L95` records the omission as a compact-renderer difference but no spec waiver exists. Restore the unavailable motion label while keeping motion input invalid and zero.
4. **MEDIUM - `tools/garmin-firmware/tests/test_emulate_neural_specimen_n64.py:L139-L142`:** the `six role` test omits saturated `0x38`, and neither the target preview nor generated oracle fixtures contain an amber pixel. Force a level-3 action cell through an independent renderer fixture and assert its exact `0x38` pixels.
5. **MEDIUM - `artifacts/analysis/fr245-1370-n64-allocation.json:L21`, `tools/garmin-firmware/emulate_neural_specimen_n64.py:L123`:** the canonical evidence gate still asserts pixels are only `[0,255]` while the target emits the reviewed six-byte palette. Update the canonical constraint to the exact six native bytes, then repin the allocation and dependent manifests.

Verified without findings: shared 64-neuron state and direct cell mapping; defined palette values in target code; angular head, safe radius, centered unclipped title, and five correctly placed physical edge labels; LIGHT/START/DOWN/UP cause-effect semantics; BACK-first escape; START observation without consumption; integer-only battery validation; narrow USB mass-storage labeling; unavailable HR/charging/update inputs; original dirty/dispatch ABI; two audited allocation envelopes; and the 384-byte target-owned stack ceiling.

Validation: `python -B -m unittest tools/garmin-firmware/tests/test_emulate_neural_specimen_n64.py -v` passed 18/18 tests in 171.847 seconds. Visual inspection of `artifacts/analysis/fr245-1370-n64-preview.png` confirmed the stated layout and exposed the missing motion rail; the default preview contains no saturated amber pixel.

## Final fix-round re-review

SPEC: PASS

QUALITY: PASS

1. **ADDRESSED - bounded home predicate:** `overlay.c:L27-L54` replaces both live vendor calls with two bounded observations. Every dereferenced node is locally range/alignment checked, every captured `next` is checked before use, cycles and a ninth node fail closed, observations must return the same first-visible callback match, and the target has only dirty/dispatch indirect transfers. Stable-list fixtures match the pinned Garmin bodies through a separate offline oracle; mutation fixtures fail closed without an unvalidated read or control-flow target.
2. **ADDRESSED - battery 100:** `renderer.c:L57-L61` emits all three digits, and `test_emulate_neural_specimen_n64.py:L84-L89` independently asserts framebuffer glyphs for `B 0`, `9`, `10`, `73`, `99`, and `100`. The battery-100 preview visibly shows `B 100`.
3. **ADDRESSED - unavailable motion:** `renderer.c:L114-L119` renders exact `MOTION --`; the focused test asserts the glyphs and safe radius, and the default preview shows the label without claiming motion data.
4. **ADDRESSED - saturated palette:** the forced neuron-56/activation-700 fixture asserts the complete 5x5 cell is `0x38`, the framebuffer contains exactly all six reviewed role bytes, and the saturated preview visibly contains the amber cell.
5. **ADDRESSED - allocation palette contract:** allocation evidence and its canonical gate now require exact native bytes `[0,12,42,51,56,63]`; the rebuilt manifest pins the updated allocation SHA-256.

No regression found in shared 64-neuron semantics/direct mapping, angular safe-area layout, centered unclipped `PHASE` and `FLYOS // N64`, exact edge captions, compact documented LIGHT/START/DOWN/UP cause/effect mappings, BACK-first escape, START ownership, battery/USB semantics, unavailable HR/motion/charging/update behavior, non-home pass-through, palette, allocation, ABI, or stack checks.

Remaining risks:

- The dual observation proves memory/control-flow safety, not atomic view ownership. Garmin can change the list after the last read and before or during framebuffer writes; an ABA change can also evade comparison. The bounded target may therefore paint one transient overlay on a newly changed charging/update/other view, but the mutation cannot redirect it to an unvalidated read or branch. Eliminating this freshness race requires a proved Garmin lock, generation counter, or scheduling invariant unavailable in the current read-only evidence.
- The target-owned stack reaches exactly 384 bytes with no margin; Garmin frames, interrupts, and live task headroom remain outside that accounting.
- Battery representation/range is proved, but cache freshness is not. HR, motion values, charging, generic USB attachment, and update pending correctly remain unavailable.
- Validation is offline; no package or live-watch behavior is claimed.

Validation: the final focused suite passed 19/19 tests in 271.541 seconds. Independent visual inspection covered default, battery-100, and saturated PNGs; deterministic PPM/PNG payload checks and evidence-manifest hashes also passed.
