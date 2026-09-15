# Task 1 report — Fixed-point Brain64 and input contract

## Status

Complete. Brain64 is a host-only, deterministic 64-cell Q5.10 model. It has
the specified public input fields, five physical button drives, validity-gated
optional inputs, a sparse integer topology spanning all specified populations,
and one `int16_t previous[64]` update snapshot. No watch, firmware artifact,
quarantine, live-staging, or target code was modified. The repository has no
Git `HEAD`, so no commit was created.

## TDD evidence

The RED run used the requested command after adding only the CMake test target
and behavioral test. `cmake --build flyos/build; ctest --test-dir flyos/build
-R brain64 --output-on-failure` failed as expected: GCC reported
`fatal error: fly/brain64.h: No such file or directory`; CTest then reported
the Brain64 executable unavailable.

After implementing the public header and model, the same focused command
passed: `1/1 Test #3: flyos-brain64-tests ... Passed`.

The complete host suite then passed: `ctest --test-dir flyos/build
--output-on-failure` reported `100% tests passed, 0 tests failed out of 4`.

## Test coverage

- Exactly 64 activation cells and the public neuron count constant.
- Byte-identical reconstruction for identical seed, tick, buttons, validity,
  and normalized optional inputs.
- Glyph-density thresholds and out-of-range neuron handling.
- Each of LIGHT, START, BACK, DOWN, and UP independently drives IDs 0–4.
- Invalid HR, motion, battery, and charging values make zero contribution.
- Valid HR drives IDs 8–9, motion drives IDs 10–11, and power drives IDs 6–7.
- All 64 cells remain in `[-16384, 16383]` through 10,000 steps.

## Changed files and SHA-256

| File | SHA-256 |
| --- | --- |
| `flyos/fly/brain64.h` | `30382CF16909312FEC3FDB7B2CA16CA47CF342224CA96ED8A546C429A157C9C9` |
| `flyos/fly/brain64.c` | `4D532E357FA88C7FCA552DCE4C417D32FEC571BA69D5485723CB632104FBABAE` |
| `flyos/tests/test_brain64.c` | `F1E6A6E58C4E4D60EA4633EF57CBD04F8DB1EA684A07C957FA8D7131E8519968` |
| `flyos/CMakeLists.txt` | `262F7F7EE3FAEB75CA10FEF235D11105E400575AB2172082D4BEA8D429C817CC` |

## Concerns

Task 1 validates host behavior only. The target-owned stack budget, permitted
hardware reads, and Garmin UI coexistence remain Task 3/4 obligations; no
target integration was attempted here.

## Review fix round

The revised focused Brain64 test was run before the production phase change.
It failed as intended with `check failed: day.activation[5] > 0`, proving that
the existing model did not drive circadian neuron 5 from its RTC-derived epoch.

The fix adds a deterministic Q5.10, 64-epoch triangular phase cycle to neuron
5. Its direct focused test holds activation and RNG state constant at epochs 16
and 48 and verifies positive and negative circadian activity respectively.

The test suite now also verifies that each validity bit independently permits
only its own poisoned optional input population; that each button leaves the
other four button neurons equal to their no-button baseline after one step;
and that maximum and minimum HR delta inputs clamp neuron 9 exactly to 16383
and -16384. The `CHECK` diagnostic now uses an actual newline.

After the fix, `cmake --build flyos/build; ctest --test-dir flyos/build -R
brain64 --output-on-failure` passed 1/1 Brain64 tests. Full CTest then passed:
`100% tests passed, 0 tests failed out of 4`.

## Updated SHA-256 after review fixes

| File | SHA-256 |
| --- | --- |
| `flyos/fly/brain64.h` | `30382CF16909312FEC3FDB7B2CA16CA47CF342224CA96ED8A546C429A157C9C9` |
| `flyos/fly/brain64.c` | `99759878D857A2BA047F4FF6C63DE49BDCB65A9A8231CF285782E57BAF5EADA3` |
| `flyos/tests/test_brain64.c` | `AA39663872B1AA231C3C9F8FAAFD3106CE6C2E5F5A6CB37284992A39398137AA` |
| `flyos/CMakeLists.txt` | `262F7F7EE3FAEB75CA10FEF235D11105E400575AB2172082D4BEA8D429C817CC` |
