# Task 1 Review

SPEC: FAIL

QUALITY: FAIL

1. **HIGH - `flyos/fly/brain64.c:L103`, `L143`, `L200`:** neuron 5 never receives the required RTC-derived circadian phase; `rtc_tick` only perturbs the seed/step count for the whole model, while neuron 5 itself gets leak and noise. Add a deterministic phase drive for ID 5 and a focused phase test.
2. **HIGH - `flyos/tests/test_brain64.c:L74`, `L93`:** validity is tested only with every bit clear or every bit set, so an implementation that enables every optional field whenever any validity bit is set would pass. Test each validity bit independently with nonzero poison values in all invalid fields; the current implementation at `brain64.c:L110-L123` does gate those fields correctly.
3. **MEDIUM - `flyos/tests/test_brain64.c:L57`:** the button test proves each pressed button raises its matching neuron but does not prove independence; a button that also drives the other four button neurons would pass. After one step, assert the four nonmatching button neurons equal the baseline.
4. **MEDIUM - `flyos/tests/test_brain64.c:L122`:** the 10,000-step clamp test does not deliberately force both saturation boundaries, especially the lower boundary. Add one-step cases using extreme positive and negative valid drives and assert exact `16383`/`-16384` results before retaining the long-run invariant.
5. **LOW - `flyos/tests/test_brain64.c:L10`:** the failure format contains `\\n`, so diagnostics print a literal backslash-n. Use `\n`.

No findings for signed-shift correctness or snapshot layout: `fly_brain64_scale_shift` defines negative scaling without signed right shift, and `fly_brain64_step` owns exactly one `int16_t previous[64]` array.

## Fix-round review

SPEC: PASS

QUALITY: PASS

1. **ADDRESSED - circadian phase:** `flyos/fly/brain64.c:L104` adds a bounded deterministic 64-epoch triangular phase, `L189` applies it only to neuron 5, and `flyos/tests/test_brain64.c:L57` verifies both phase signs.
2. **ADDRESSED - independent validity bits:** `flyos/tests/test_brain64.c:L96` exercises each bit separately with all optional fields poisoned and verifies only the selected population changes.
3. **ADDRESSED - independent button drives:** `flyos/tests/test_brain64.c:L74` now verifies every nonmatching button neuron remains byte-equivalent to its baseline after one step.
4. **ADDRESSED - clamp boundaries:** `flyos/tests/test_brain64.c:L156` forces signed HR-delta overflow in both directions and asserts exact `16383` and `-16384` saturation.
5. **ADDRESSED - diagnostic newline:** `flyos/tests/test_brain64.c:L10` now contains `\n` rather than a literal backslash-n sequence.

NEW BREAKAGE: None found in the fixes.
