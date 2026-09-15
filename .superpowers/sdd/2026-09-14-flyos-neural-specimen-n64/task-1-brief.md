### Task 1: Fixed-point Brain64 and input contract

**Files:**
- Create: `flyos/fly/brain64.h`
- Create: `flyos/fly/brain64.c`
- Create: `flyos/tests/test_brain64.c`
- Modify: `flyos/CMakeLists.txt`

**Interfaces:**
- Produces: `FlyBrainInputs`, `FlyBrain64`, `fly_brain64_seed`, `fly_brain64_step`, `fly_brain64_reconstruct`, `fly_brain64_level`, `fly_brain64_state`.

- [ ] Write tests that require exactly 64 activations, deterministic reconstruction, clamping over 10,000 steps, five independent button drives, zero contribution from invalid optional channels, and changed cardiac/motion/power populations when their validity bits are set.
- [ ] Run `cmake --build flyos/build; ctest --test-dir flyos/build -R brain64 --output-on-failure` and record the expected RED failure because the Brain64 API does not exist.
- [ ] Implement the public input structure with `buttons`, `valid_mask`, `heart_rate_bpm`, `heart_rate_delta`, `motion`, `battery_percent`, and `charging`; implement the population layout from the spec using one `int16_t previous[64]` snapshot and deterministic sparse integer connections.
- [ ] Rebuild and run the focused test to GREEN, then run all CTest tests.


