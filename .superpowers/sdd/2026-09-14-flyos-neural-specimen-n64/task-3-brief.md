### Task 3: Read-only Garmin state and color evidence

**Files:**
- Create: `tools/garmin-firmware/fr245_runtime_state.py`
- Create: `tools/garmin-firmware/tests/test_fr245_runtime_state.py`
- Create: `docs/runtime-state.md`
- Create: `artifacts/firmware/analysis/fr245-1370-runtime-state.json`

**Interfaces:**
- Produces an allowlist of image-bound read-only addresses/getters for home view, charging/USB, battery, HR, motion, and update pending; each entry has `status`, `validity_semantics`, and `side_effect_free`.
- Produces raw framebuffer color-role values only if supported by converter/resource evidence.

- [ ] Write failing scanner/report-schema tests requiring every requested signal and rejecting any enabled signal without a pinned address/getter, validity semantics, and side-effect-free evidence.
- [ ] Run the focused Python test and record RED because the analyzer is missing.
- [ ] Decompile the known USB, battery/PMIC, display/view, update, HR, and sensor-hub clusters from the pinned 13.70 Ghidra project. Record unavailable signals honestly; do not substitute peripheral transactions.
- [ ] Implement the reproducible evidence reporter and tests. Only mark a signal enabled when the static path proves a pure getter or stable RAM snapshot and Unicorn can allowlist every read.
- [ ] Recover framebuffer color encoding from the converter and resources. If exact hue mapping remains unproved, emit `target_palette_status: unavailable` and keep the live target monochrome.


