### Task 2: N64 renderer and golden previews

**Files:**
- Create: `flyos/display/neural_specimen.h`
- Create: `flyos/display/neural_specimen.c`
- Create: `flyos/tests/test_neural_specimen.c`
- Create: `flyos/tools/render_neural_specimen_preview.py`
- Modify: `flyos/CMakeLists.txt`

**Interfaces:**
- Consumes: `FlyBrain64` and `FlyBrainInputs` from Task 1.
- Produces: `fly_neural_specimen_points[64]` and `fly_neural_specimen_render(uint8_t framebuffer[57600], const FlyBrain64 *, const FlyBrainInputs *, uint32_t rtc_tick)`.

- [ ] Write failing tests for 64 distinct non-overlapping in-bounds cells, circular safe-area bounds, direct neuron-to-cell change locality, all four density levels, `--` for invalid sensors, physical button cause/effect labels, and full framebuffer ownership.
- [ ] Run the focused renderer test and record RED because the renderer is missing.
- [ ] Implement the centered `PHASE`/`FLYOS // N64` header, one angular head contour, antennae, faceted eye hatching, procedural 8x8 cells, status/event rails, and contextual labels. Use semantic color constants with a monochrome target fallback until Task 3 proves raw values.
- [ ] Generate host previews for quiet, each button, optional-sensor valid/invalid, charging, USB, and update/pass-through states; store PNG/PPM outputs beneath `artifacts/firmware/analysis/n64-previews/` with a SHA-256 manifest.
- [ ] Run the focused test and all CTest tests to GREEN.


