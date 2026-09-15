# Task 2 — N64 renderer and golden previews

## Status

Complete after review remediation. Golden PPMs now originate from `fly_neural_specimen_render` or its explicit `fly_neural_specimen_render_if_home` gate through the compiled `flyos-neural-specimen-preview-exporter`; the Python tool only invokes that exporter and hashes its files. The USB/update pass-through previews seed deterministic representative frames and prove that a false home gate leaves every byte unchanged; they do not claim to reproduce Garmin UI appearance or detect either state. The inspection-only `quiet-view.png` was removed.

Target roles use only `0x00` and the live-proven contrasting `0xff`; byte `0x01` is not used or claimed. The exporter compiles the same C renderer with a host-only semantic palette: positive non-action cells are excitatory, negative cells inhibitory, and high action cells saturated. `rtc_tick` moves the PHASE marker. The renderer no longer uses `snprintf` or `memset`.

## Tests

- RED: `flyos-neural-specimen-preview-role-tests` failed because the former role aliases could not distinguish excitatory from inhibitory.
- RED: the upgraded preview test failed before the exporter argument/implementation existed.
- `ctest --test-dir flyos/build --output-on-failure` — PASS, 7/7 tests.

The renderer test sweeps all 64 neurons for direct cell locality, asserts the exact five physical cause/effect labels, and checks every rendered non-black pixel against the explicit 114-pixel circular safe radius. The role test verifies host colors for positive, negative, and action populations. Preview tests require exactly eleven C-exported PPMs, valid headers, a complete manifest, matching SHA-256 values, and no unmanifested files.

## Files

- `flyos/display/neural_specimen.[ch]`
- `flyos/tests/test_neural_specimen.c`
- `flyos/tests/test_neural_specimen_preview_roles.c`
- `flyos/tools/render_neural_specimen_preview.c`
- `flyos/tools/render_neural_specimen_preview.py`
- `flyos/tests/test_render_neural_specimen_preview.py`
- `flyos/CMakeLists.txt`
- `artifacts/firmware/analysis/n64-previews/SHA256SUMS`

Current artifact hashes:

```text
788fd9c99f241a3de6f2e5a6fa2a04bb05b74d0df6c5a4e8ff091a7697412a71  back.ppm
2eaa6fecef34dd20fbafc9185084dd6f38752d7d816a16d04c1cd1206d663405  charging.ppm
b9ff590896767bfbc711d4709c1cb4f5217041632ba5bd9b4b5e307069556e6a  down.ppm
7ae55dbccbb5c44a9ff5f671478165718df0825b16a280ac25051dddfee01aac  light.ppm
b71f04fbda0eede0fe6e5724c7806ccf39548f475aaaa49aea9f166647cc8521  quiet.ppm
171b64a8dbd0378c23f9478791347fe850f5a6c355b978d8a5b4faf490b9de2b  sensors-invalid.ppm
2ab107590d2a9294bcdb33a1d9b3356aa6ee8f4222db5a27a3fbe64714bd8ef4  sensors-valid.ppm
06a0ce67d7b8e8ebdaff8244961f1ea9de6d6178328890e2d77687289afc9675  start.ppm
73e3796c45b9c08406a656bd4fd4ffe4be87bd8fff891b532af850ec10b6c387  up.ppm
```

## Concerns

Second re-review remediation: fly_neural_specimen_render_if_home is the explicit Task4-facing gate. A zero gate leaves all 57,600 incoming bytes unchanged; USB/update golden PPMs seed deterministic representative base frames and exercise that same no-op path. They prove byte-preserving behavior only, not Garmin UI appearance or any USB/update detection. The sentinel ownership assertion now requires every enabled-render byte to be exactly 0x00 or 0xff; unavailable labels are exposed and asserted verbatim; quiet export leaves action neurons below saturation.

The manifest was regenerated after this remediation and now covers 11 PPMs, including usb-pass-through.ppm (c9d4a68a1f00693d6b89b1c868860ad62c342190d0ccaeab71b5a315744f6090) and update-pass-through.ppm (54e1ed21c3dd007ff630e812dbd113e9289056b1c14e2ab1fb3a878d36288f15). The authoritative complete list is artifacts/firmware/analysis/n64-previews/SHA256SUMS.

- Exact Garmin pass-through remains a later integration gate requiring a proved home-state signal. The two pass-through artifacts prove only the byte-preserving false-gate behavior; they make no unsupported state-detection claim.
- No watch, quarantine firmware, live staging, package construction, or commit was touched.
