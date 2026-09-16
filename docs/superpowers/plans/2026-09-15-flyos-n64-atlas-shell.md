# FlyOS N64 Atlas Shell Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and verify an offline Forerunner 245 13.70 FlyOS candidate that owns all five buttons on its stable home, provides a deliberate Garmin system session, reliably refreshes after USB detach, and renders a safe-area 64-neuron Drosophila atlas.

**Architecture:** A new immutable target fork keeps the installed synthetic 13.76 source reproducible. A tri-state view classifier and complement-protected key-record words provide one owner per physical sequence; separate mode nibbles hold the system-session and detach-retry state. Two proved USB hook sites request a redraw only after Garmin teardown has unlocked, while the display hook remains the only code that touches the framebuffer. The renderer derives every neuron mask and preview from the final linked ARM binary.

**Tech Stack:** Cortex-M4 Thumb-2/soft-float C and assembly, ARM GNU Toolchain 15.2, PowerShell, Python `unittest`, Unicorn, Capstone, Ghidra 12.1.3, CMake/CTest, existing Garmin GCD reconstruction and verification tools.

**Spec:** `docs/superpowers/specs/2026-09-15-flyos-n64-atlas-shell-design.md`

## Global Constraints

- Start and remain offline/read-only with respect to the watch until a separately disclosed exact live artifact receives explicit approval.
- Preserve `flyos/target/fr245_1370_neural_specimen_n64_controls/` and the installed 13.76 package as immutable reference inputs.
- Target only the pinned Forerunner 245 non-Music 13.70 application image.
- Do not use a third flash interval unless it passes the complete erased-byte, instruction, literal, pointer, Ghidra-reference, section, metadata, overlap, and full-image proof.
- Keep target-owned stack use at or below 384 bytes.
- Permit no writable static storage, heap allocation, direct peripheral-bus transaction, framebuffer write from a key/USB worker, or blocking queue call.
- Invalid optional HR, motion, light, and charging inputs contribute zero; do not fabricate charging telemetry.
- Preserve native frames whenever the first-visible view is proved non-home; malformed or changing view state fails open to Garmin.
- Keep every generated candidate and restore package under `artifacts/firmware/quarantine/`, SHA-256 hash it, and mark it analysis-only.
- Keep `tools/live-proof/stage-gupdate.ps1` locked against every new candidate and restore until the later exact-artifact approval gate.
- Work against private evidence in `C:\Users\zgbre`; copy only public-safe source, tests, and documentation to `C:\Users\zgbre\flywatchos-publish` for commits. Never copy firmware, watch files, identifiers, history, tokens, or proprietary package payloads into Git.

## File Structure

- `flyos/target/fr245_1370_n64_atlas_shell/`: new immutable target fork; hooks, input policy, compact renderer, packed Brain64, linker script, and reproducible build.
- `flyos/display/n64_atlas_layout.h`: header-only authoritative neuron-to-screen layout shared by host and target tests.
- `tools/garmin-firmware/fr245_key_workspace_audit.py`: reproducible proof for all five final key-record halfwords and pinned phase timing.
- `tools/garmin-firmware/fr245_usb_detach.py`: USB transition, observer, lock, hook-site, queue-ordering, retry-context, and modal outcome analyzer.
- `tools/garmin-firmware/atlas_shell_feasibility.py`: fail-closed composition of the key, USB, update-view, storage, and flash-budget proofs.
- `tools/garmin-firmware/emulate_n64_atlas_shell.py`: exact linked-binary display, key, system-mode, USB-hook, retry, and evidence emulator.
- `tools/garmin-firmware/neural_specimen_n64_atlas_shell_version_strategy.py`: offline-only 13.78 candidate/13.79 official-code restore constructor.
- `tools/garmin-firmware/tests/test_*.py`: focused analyzer, emulator, and package tests.
- `docs/atlas-shell-*.md`: human-readable feasibility, placement, controls, detach, and package findings.
- `artifacts/firmware/analysis/`: private hashed decompilation and verification reports.
- `artifacts/analysis/fr245-1370-n64-atlas-shell-visual-audit/`: target-derived previews, masks, contact sheet, and hashes safe for selective publication after review.

---

### Task 1: Prove feasibility before feature implementation

**Files:**
- Create: `tools/garmin-firmware/fr245_key_workspace_audit.py`
- Create: `tools/garmin-firmware/fr245_usb_detach.py`
- Create: `tools/garmin-firmware/atlas_shell_feasibility.py`
- Create: `tools/garmin-firmware/ghidra_scripts/UsbDetachReport.java`
- Create: `tools/garmin-firmware/tests/test_fr245_key_workspace_audit.py`
- Create: `tools/garmin-firmware/tests/test_fr245_usb_detach.py`
- Create: `tools/garmin-firmware/tests/test_atlas_shell_feasibility.py`
- Create: `docs/atlas-shell-feasibility.md`
- Create privately: `artifacts/firmware/analysis/fr245-1370-key-workspace.json`
- Create privately: `artifacts/firmware/analysis/fr245-1370-usb-detach.json`
- Create privately: `artifacts/firmware/analysis/fr245-1370-atlas-shell-feasibility.json`

**Interfaces:**
- Produces `audit_key_workspace(root: Path) -> dict[str, Any]`.
- Produces `analyze_usb_detach(root: Path) -> dict[str, Any]`.
- Produces `evaluate_feasibility(root: Path) -> dict[str, Any]` with `go: bool` and a complete list of failed gates.
- Later tasks may proceed only when `go` is `true`; a false report ends implementation without creating a target package.

- [ ] **Step 1: Write failing key-workspace proof tests**

```python
def test_all_five_final_halfwords_have_complete_static_proof(self):
    report = audit.audit_key_workspace(ROOT)
    self.assertEqual(
        [0x1FFDBBFE, 0x1FFDBC36, 0x1FFDBC6E, 0x1FFDBCA6, 0x1FFDBCDE],
        [item["address"] for item in report["records"]],
    )
    self.assertTrue(all(item["max_stock_offset"] <= 0x35 for item in report["records"]))
    self.assertEqual(
        [0xF840, 0xFA3C, 0xFA80, 0xFB0C, 0xFCA0, 0xFCD0, 0xFD00],
        report["workspace_base_literal_vas"],
    )
    self.assertTrue(report["scheduled_object_span_excludes_0x36_0x37"])
    self.assertTrue(report["phase_timing"]["phase4_max_period_ms"] <= 200)
```

- [ ] **Step 2: Run the key-workspace tests and verify RED**

Run:

```powershell
python -B -m unittest -v tools/garmin-firmware/tests/test_fr245_key_workspace_audit.py
```

Expected: FAIL because `fr245_key_workspace_audit.py` and its proof report do not exist.

- [ ] **Step 3: Implement the key-workspace audit**

Pin the base-literal sites `0xF840`, `0xFA3C`, `0xFA80`, `0xFB0C`, `0xFCA0`, `0xFCD0`, and `0xFD00`; the explicit owners `0xF7E4`, `0xFA18`, `0xFA48`, `0xFAA4`, `0xFB34`, `0xFCAC`, and `0xFCD8`; and scheduled-object helpers `0x8844` and `0x8B04`. Hash every extracted function and reject any workspace access that reaches record offsets `0x36` or `0x37`.

```python
RECORD_BASE = 0x1FFDBBC8
RECORD_STRIDE = 0x38
FINAL_HALFWORD = 0x36
REQUIRED_OWNERS = (0xF7E4, 0xFA18, 0xFA48, 0xFAA4, 0xFB34,
                   0xFCAC, 0xFCD8, 0x8844, 0x8B04)

def audit_key_workspace(root: Path) -> dict[str, Any]:
    """Return only hashes, addresses, decoded offsets, and timing evidence."""
```

Record the pinned timing semantics: phase 0 immediate; first deferred work 750 ms for LIGHT and 500 ms for other keys; phase 4 at no more than 200 ms intervals; phase 2 at about 1000/500 ms; phase 3 after the later 5000 ms window.

- [ ] **Step 4: Write failing USB transition and lock-order tests**

```python
def test_detach_route_is_unique_unlocked_and_retryable(self):
    report = usb.analyze_usb_detach(ROOT)
    self.assertEqual("2f9c2ca2710dae634ce952ba48ae34789e83fb902106e39869c0d9d36f93020a",
                     report["state_machine"]["sha256"])
    self.assertTrue(report["edges"]["3_to_detach"]["proved"])
    self.assertTrue(report["edges"]["4_to_detach"]["proved"])
    self.assertEqual(1, report["teardown"]["calls_per_detach_epoch"])
    self.assertEqual("unlocked", report["queue_site"]["mutex_state"])
    self.assertEqual("back", report["queue_site"]["ordering"])
    self.assertTrue(report["retry_context"]["bounded"])
    self.assertIn(report["modal_outcome"]["kind"], {"home_after_observers", "proved_native_refresh"})
```

- [ ] **Step 5: Run the USB tests and verify RED**

Run:

```powershell
python -B -m unittest -v tools/garmin-firmware/tests/test_fr245_usb_detach.py
```

Expected: FAIL because the USB analyzer and canonical transition report do not exist.

- [ ] **Step 6: Implement and run the USB/Ghidra analysis**

The analyzer must enumerate every direct and computed access to cache byte `0x1FFC6F25`, reconstruct the complete state graph for `0x20858..0x20A3F`, trace observer list `0x1FFC8AA0`, and prove the calling context and mutex state at both candidate hook sites.

```python
USB_STATE_MACHINE = (0x20858, 0x20A3F)
USB_WORKER = (0x20A64, 0x20AB7)
TEARDOWN_CALL = 0x2093E       # ff f7 37 ff: bl 0x207b0
UNSCHEDULED_TAIL = 0x20A8A    # e7 f7 5f be: b.w 0x874c
USB_CACHE = 0x1FFC6F25
USB_OBSERVERS = 0x1FFC8AA0

def analyze_usb_detach(root: Path) -> dict[str, Any]:
    """Fail unless both 3/4 detach paths, observers, hooks, retry, and modal outcome are proved."""
```

Run the new Ghidra report against project `FR245_1370_CODE`, program `stream_01_fw_all_bin.bin`, and store its console output and SHA-256 beside the JSON report. Prove that no queue operation occurs while mutex `0x1FFC6EEC` is held. Pin the safe post-unlock retry callback and show that its cadence is bounded.

- [ ] **Step 7: Write the composed feasibility test**

```python
def test_feasibility_is_fail_closed_and_budget_complete(self):
    report = feasibility.evaluate_feasibility(ROOT)
    self.assertEqual([], report["failed_gates"])
    self.assertTrue(report["go"])
    self.assertEqual({"primary": 1023, "secondary": 2048}, report["section_limits"])
    self.assertTrue(report["update_prompt"]["proved_non_home"])
    self.assertTrue(report["storage"]["five_key_words_and_modes_fit"])
    self.assertTrue(report["projected_sections"]["fit_without_repair_byte"])
```

- [ ] **Step 8: Implement the feasibility composition and projection**

```python
REQUIRED_GATES = (
    "five_key_halfwords",
    "phase_timing",
    "tri_state_view_classifier",
    "observed_update_prompt_non_home",
    "usb_3_and_4_detach_convergence",
    "post_unlock_hook_site",
    "bounded_retry_context",
    "modal_outcome_or_native_refresh",
    "atomic_storage_map",
    "projected_flash_fit",
)

def evaluate_feasibility(root: Path) -> dict[str, Any]:
    """Return go=false with named failed gates; never infer missing evidence."""
```

The projected storage map is exact: the LIGHT pad mode nibble holds `NORMAL=0`, `CHORD_HOLD=1`, `SYSTEM_PENDING=2`, `SYSTEM_HOME=3`, `SYSTEM_EXCURSION=4`; the START pad mode nibble holds `DETACH_NONE=0`, `PENDING=1`, `RETRY1=2`, `RETRY2=3`, `RETRY3=4`, `QUEUED=5`, `EXHAUSTED=6`; BACK, DOWN, and UP require mode zero. All words use the complement encoding defined in Task 2.

The flash projection must measure replacement code, not add new functions to the current 996/2044-byte payload. Record exact projected upper bounds for every hook, trampoline, function group, table, and literal. Do not invent a spare-byte minimum; require only exact non-overlap within 1023 primary bytes and 2048 secondary bytes while preserving repair byte `0x1F63FF`.

- [ ] **Step 9: Run the complete feasibility gate**

Run:

```powershell
python -B -m unittest -v tools/garmin-firmware/tests/test_fr245_key_workspace_audit.py
python -B -m unittest -v tools/garmin-firmware/tests/test_fr245_usb_detach.py
python -B -m unittest -v tools/garmin-firmware/tests/test_atlas_shell_feasibility.py
python -B tools/garmin-firmware/atlas_shell_feasibility.py --root . --write-private-report artifacts/firmware/analysis/fr245-1370-atlas-shell-feasibility.json
```

Expected: all tests PASS and the final command prints `"go": true`. If it prints false, stop this plan and report the named blockers; do not scaffold the target or package.

- [ ] **Step 10: Document and commit the public-safe evidence method**

Copy only the three analyzers, their tests, the Ghidra script, and `docs/atlas-shell-feasibility.md` into the curated public repository. Exclude private decompilation output and firmware-derived blobs.

```powershell
git -C C:\Users\zgbre\flywatchos-publish add tools/garmin-firmware docs/atlas-shell-feasibility.md
git -C C:\Users\zgbre\flywatchos-publish diff --cached --check
git -C C:\Users\zgbre\flywatchos-publish commit -m "research: prove atlas shell feasibility"
```

---

### Task 2: Create the immutable target and exact emulator contract

**Files:**
- Create: `flyos/target/fr245_1370_n64_atlas_shell/` by copying the public source files from `fr245_1370_neural_specimen_n64_controls/`, excluding `build/`
- Create: `flyos/target/fr245_1370_n64_atlas_shell/state.h`
- Create: `tools/garmin-firmware/emulate_n64_atlas_shell.py`
- Create: `tools/garmin-firmware/tests/test_emulate_n64_atlas_shell.py`
- Modify: `flyos/target/fr245_1370_n64_atlas_shell/build.ps1`
- Modify: `flyos/target/fr245_1370_n64_atlas_shell/linker.ld`

**Interfaces:**
- Produces `pack_state(local, mode) -> uint16_t` and validated local/mode readers shared in semantics between C and Python.
- Produces `emulate_display(bundle: Bundle, **kwargs: Any) -> dict[str, Any]`, `emulate_key_sequence(bundle: Bundle, events: list[dict[str, Any]]) -> dict[str, Any]`, and `emulate_usb_sequence(bundle: Bundle, transitions: list[dict[str, Any]]) -> dict[str, Any]` against the new linked ELF.
- Preserves byte identity with the old controls target until later tasks intentionally change behavior.

- [ ] **Step 1: Copy the immutable source scaffold and add a preservation test**

```python
def test_scaffold_starts_from_exact_controls_sources(self):
    for name in ("hook.S", "overlay.c", "renderer.c", "brain64_packed.c"):
        self.assertEqual((OLD_TARGET / name).read_bytes(), (TARGET / name).read_bytes())
```

Run the test once before the copy to observe RED, then copy only source and documentation files. Never copy the old `build/` directory.

- [ ] **Step 2: Write failing state-codec tests**

```python
def test_complement_protected_state_words(self):
    self.assertEqual(0xF0F0, N64.pack_state(N64.IDLE, N64.NORMAL))
    self.assertEqual(0xF0E1, N64.pack_state(N64.FLY_HELD, N64.NORMAL))
    self.assertEqual(0xF0D2, N64.pack_state(N64.FLY_PULSE, N64.NORMAL))
    self.assertEqual(0xF0C3, N64.pack_state(N64.GARMIN_HELD, N64.NORMAL))
    self.assertEqual(0xE1F0, N64.pack_state(N64.IDLE, N64.CHORD_HOLD))
    self.assertEqual(0xD2F0, N64.pack_state(N64.IDLE, N64.SYSTEM_PENDING))
    self.assertEqual(0xC3F0, N64.pack_state(N64.IDLE, N64.SYSTEM_HOME))
    self.assertEqual(0xB4F0, N64.pack_state(N64.IDLE, N64.SYSTEM_EXCURSION))
    self.assertIsNone(N64.unpack_state(0x0000))
    self.assertIsNone(N64.unpack_state(0xFF00))
```

- [ ] **Step 3: Implement the exact C and Python state encoding**

```c
enum FlyLocalState { FLY_IDLE=0, FLY_HELD=1, FLY_PULSE=2, GARMIN_HELD=3 };
enum FlySystemMode { NORMAL=0, CHORD_HOLD=1, SYSTEM_PENDING=2,
                     SYSTEM_HOME=3, SYSTEM_EXCURSION=4 };
enum FlyDetachMode { DETACH_NONE=0, DETACH_PENDING=1, DETACH_RETRY1=2,
                     DETACH_RETRY2=3, DETACH_RETRY3=4,
                     DETACH_QUEUED=5, DETACH_EXHAUSTED=6 };

static inline uint16_t fly_state_word(uint8_t local, uint8_t mode) {
    return (uint16_t)(local | ((local ^ 15u) << 4) |
                      ((uint16_t)mode << 8) | ((uint16_t)(mode ^ 15u) << 12));
}
```

Only LIGHT's mode nibble represents `FlySystemMode`; only START's represents `FlyDetachMode`; the other three modes must be zero. Every writer uses aligned 16-bit compare/exchange and preserves the nibble owned by the other subsystem.

- [ ] **Step 4: Extend the emulator API before changing target behavior**

```python
def emulate_key_sequence(bundle: Bundle, events: list[dict[str, Any]]) -> dict[str, Any]:
    """Each event accepts key, phase, tick_ms, gpio_mask, view, usb, and queue_result."""

def emulate_usb_sequence(bundle: Bundle, transitions: list[dict[str, Any]]) -> dict[str, Any]:
    """Execute both proved USB hook sites plus the bounded retry callback."""
```

Model record-offset-zero press timestamps, per-event tick values at `0x7FA4`, all five GPIOs, tri-state views, the two new hook patches, queue return codes `0/2/3`, mutex state, and complete initial framebuffers. Continue rejecting every unallowlisted read, write, and control transfer.

- [ ] **Step 5: Build the unchanged fork and verify exact baseline behavior**

Run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File flyos/target/fr245_1370_n64_atlas_shell/build.ps1 -BuildRoot artifacts/analysis/fr245-1370-atlas-shell-baseline
python -B -m unittest -v tools/garmin-firmware/tests/test_emulate_n64_atlas_shell.py
```

Expected: scaffold/codec/harness tests PASS; behavior assertions introduced in Tasks 3-5 are not added yet.

- [ ] **Step 6: Commit the scaffold**

Copy the new target source, emulator, and focused test into the curated repository, omitting generated build output.

```powershell
git -C C:\Users\zgbre\flywatchos-publish add flyos/target/fr245_1370_n64_atlas_shell tools/garmin-firmware/emulate_n64_atlas_shell.py tools/garmin-firmware/tests/test_emulate_n64_atlas_shell.py
git -C C:\Users\zgbre\flywatchos-publish diff --cached --check
git -C C:\Users\zgbre\flywatchos-publish commit -m "test: scaffold atlas shell target"
```

---

### Task 3: Implement five-key ownership and the Garmin system session

**Files:**
- Modify: `flyos/target/fr245_1370_n64_atlas_shell/overlay.c`
- Modify: `flyos/target/fr245_1370_n64_atlas_shell/state.h`
- Modify: `tools/garmin-firmware/emulate_n64_atlas_shell.py`
- Modify: `tools/garmin-firmware/tests/test_emulate_n64_atlas_shell.py`
- Create: `docs/atlas-shell-controls.md`

**Interfaces:**
- Produces `enum FlyViewClass { FLY_VIEW_INVALID, FLY_VIEW_HOME, FLY_VIEW_NON_HOME }`.
- Produces `flyos_key_event(uint32_t key, uint32_t phase)` with a phase-zero owner latched through release.
- Produces UI flags `FLY_UI_CHORD_ARMED=2` and `FLY_UI_SYSTEM=4` for the renderer.

- [ ] **Step 1: Write failing tri-state classifier tests**

```python
def test_view_classifier_distinguishes_home_nonhome_and_invalid(self):
    self.assertEqual("HOME", self.frame(view="valid")["view_class"])
    self.assertEqual("NON_HOME", self.frame(view="update_prompt")["view_class"])
    for view in ("empty", "malformed", "cycle", "too_long", "root_mutation"):
        self.assertEqual("INVALID", self.frame(view=view)["view_class"])
```

The `update_prompt` fixture must use the callback identity proved in Task 1 rather than generic `0x12345`.

- [ ] **Step 2: Write failing all-five-key ownership tests**

```python
def test_all_five_home_sequences_are_owned_for_every_usb_state(self):
    phases = (0, 2, 4, 3, 1)
    for usb in (0, 2, 3, 4):
        for key in range(5):
            result = N64.emulate_key_sequence(
                self.bundle,
                [{"key": key, "phase": phase, "tick_ms": 1000 + i * 200,
                  "view": "valid", "usb": usb} for i, phase in enumerate(phases)],
            )
            self.assertEqual([], result["published"])
            self.assertEqual("FLY_PULSE", result["final_local_states"][key])
```

Add separate tests for a native owner latched through a later home, a FlyOS owner latched through a later non-home view, invalid/complement state, cold/legacy initialization only at stable home with all GPIOs released, queue null/full, concurrent pulse clear, and exact Garmin prologue replay.

- [ ] **Step 3: Run the ownership tests and verify RED**

Run:

```powershell
python -B -m unittest -v -k ownership tools/garmin-firmware/tests/test_emulate_n64_atlas_shell.py
```

Expected: FAIL because the copied target still passes LIGHT/BACK and USB states `3/4` to Garmin.

- [ ] **Step 4: Implement the tri-state classifier and atomic owner latch**

Refactor the bounded list scan to return stable `HOME(node)`, `NON_HOME`, or `INVALID`. At phase zero, initialize recognized cold values only in stable home with every GPIO released, then atomically set `FLY_HELD` for all five normal-home keys. In `NON_HOME`, `INVALID`, corrupted mode, or system mode, atomically set `GARMIN_HELD` and replay the original event. Every later phase consults only the local state.

```c
struct FlyViewResult { uint32_t home; uint8_t kind; };
static struct FlyViewResult stable_view(void);
static uint8_t cas_local(volatile uint16_t *word, uint8_t expected,
                         uint8_t desired, uint8_t required_mode);
```

Remove the USB `3/4` ownership escape and the unconditional LIGHT/BACK pass-through. Pulse clearing must change only the local nibble.

- [ ] **Step 5: Write failing chord/system-session tests**

Cover both key orders, either key alone, release at 1999 ms, phase 4 at 2000 ms, both-release commit, zero orphan events, system navigation, stable non-home excursion, return-home clearing, reset, garbage, complement mismatch, and in-progress owners across mode transitions.

```python
def test_chord_commits_system_only_after_two_second_hold_and_both_releases(self):
    result = N64.emulate_key_sequence(self.bundle, chord_sequence(hold_ms=2000))
    self.assertEqual([], result["published"])
    self.assertEqual("SYSTEM_HOME", result["final_system_mode"])
    self.assertTrue(result["both_release_barrier_observed"])
```

- [ ] **Step 6: Implement the chord and system-session state machine**

Use the stock LIGHT/BACK record timestamps at offset zero and tick getter `0x7FA4`:

```c
static uint8_t chord_elapsed(uint32_t now, uint32_t light_down,
                             uint32_t back_down) {
    uint32_t oldest_elapsed = (now - light_down) < (now - back_down) ?
                              (now - light_down) : (now - back_down);
    return oldest_elapsed >= 2000u;
}
```

Transition `NORMAL -> CHORD_HOLD -> SYSTEM_PENDING -> SYSTEM_HOME`; consume both chord sequences through release. In the display hook, transition `SYSTEM_HOME -> SYSTEM_EXCURSION` only for a stable non-home view, and `SYSTEM_EXCURSION -> NORMAL` only for stable home with all five GPIOs released. Invalid views change no valid mode. Never rewrite an in-progress local owner while changing mode.

- [ ] **Step 7: Run focused and full target tests**

```powershell
python -B -m unittest -v -k ownership tools/garmin-firmware/tests/test_emulate_n64_atlas_shell.py
python -B -m unittest -v -k chord tools/garmin-firmware/tests/test_emulate_n64_atlas_shell.py
python -B -m unittest -v -k system_mode tools/garmin-firmware/tests/test_emulate_n64_atlas_shell.py
powershell -NoProfile -ExecutionPolicy Bypass -File flyos/target/fr245_1370_n64_atlas_shell/build.ps1
python -B -m unittest -v tools/garmin-firmware/tests/test_emulate_n64_atlas_shell.py
```

Expected: all five keys publish zero events on stable home for USB `0/2/3/4`; native and invalid sequences replay exact event phases; chord/system tests PASS; stack remains at most 384 bytes.

- [ ] **Step 8: Document and commit controls**

```powershell
git -C C:\Users\zgbre\flywatchos-publish add flyos/target/fr245_1370_n64_atlas_shell tools/garmin-firmware/emulate_n64_atlas_shell.py tools/garmin-firmware/tests/test_emulate_n64_atlas_shell.py docs/atlas-shell-controls.md
git -C C:\Users\zgbre\flywatchos-publish diff --cached --check
git -C C:\Users\zgbre\flywatchos-publish commit -m "feat: give FlyOS exclusive home controls"
```

---

### Task 4: Build the 64-neuron Drosophila atlas renderer

**Files:**
- Create: `flyos/display/n64_atlas_layout.h`
- Modify: `flyos/display/neural_specimen.h`
- Modify: `flyos/display/neural_specimen.c`
- Modify: `flyos/tests/test_neural_specimen.c`
- Modify: `flyos/tests/test_neural_specimen_preview_roles.c`
- Modify: `flyos/CMakeLists.txt`
- Modify: `flyos/target/fr245_1370_n64_atlas_shell/renderer.c`
- Create: `flyos/target/fr245_1370_n64_atlas_shell/renderer.h`
- Modify: `flyos/target/fr245_1370_n64_atlas_shell/overlay.c`
- Modify: `tools/garmin-firmware/emulate_n64_atlas_shell.py`
- Modify: `tools/garmin-firmware/tests/test_emulate_n64_atlas_shell.py`

**Interfaces:**
- Produces `FlyN64AtlasPoint fly_n64_atlas_point(unsigned neuron)` and `uint8_t fly_n64_atlas_population(unsigned neuron)`.
- Keeps `n64_render(uint8_t *, const FlyBrain64 *, const FlyBrainInputs *, uint32_t, uint8_t ui_flags)`.
- Defines `FLY_UI_USB=1`, `FLY_UI_CHORD_ARMED=2`, and `FLY_UI_SYSTEM=4`; there is no charging flag.
- Produces a target-derived atlas mapping manifest with 64 pairwise-disjoint dynamic masks.

- [ ] **Step 1: Write failing atlas-layout tests**

```c
static void test_atlas_masks(void) {
    uint8_t occupancy[240 * 240] = {0};
    for (unsigned neuron = 0; neuron < 64; ++neuron) {
        FlyN64AtlasPoint point = fly_n64_atlas_point(neuron);
        TEST_ASSERT_TRUE((point.x - 120) * (point.x - 120) +
                         (point.y - 120) * (point.y - 120) <= 98 * 98);
        for (unsigned y = point.y; y < point.y + 5; ++y)
            for (unsigned x = point.x; x < point.x + 5; ++x)
                TEST_ASSERT_EQUAL_UINT8(0, occupancy[y * 240 + x]++);
    }
}
```

Test exact populations `0-11`, `12-23`, `24-39`, `40-47`, `48-55`, and `56-63`; 5x5 maximum masks; density counts `1/9/16/25`; static tracts disjoint from dynamic masks; all callouts within radius 98; and 4,704 byte-exact shared-vs-packed Brain64 fixtures.

- [ ] **Step 2: Run the host tests and verify RED**

```powershell
cmake -S flyos -B flyos/build-atlas
cmake --build flyos/build-atlas --config Release
ctest --test-dir flyos/build-atlas -C Release --output-on-failure
```

Expected: the new atlas layout tests FAIL because the existing renderer uses an 8x8 grid and looser radius limits.

- [ ] **Step 3: Implement the header-only atlas layout and host renderer**

```c
typedef struct { uint8_t x; uint8_t y; } FlyN64AtlasPoint;
static inline FlyN64AtlasPoint fly_n64_atlas_point(unsigned neuron);
static inline uint8_t fly_n64_atlas_population(unsigned neuron);
```

Arrange the sensory rim, central ring, paired mushroom-body columns, modulatory midline, identity core, and descending action fan. Render a broken angular head cutaway with an open inferior edge, antenna roots, lateral eye marks, and fixed gray tracts that do not overlap neuron masks. Use RGB222 gray `0x2A`, white `0x3F`, green `0x0C`, cyan `0x0F`, magenta `0x33`, and amber `0x38`; density alone must communicate magnitude.

- [ ] **Step 4: Write failing target-derived mask and label tests**

```python
def test_linked_target_has_64_disjoint_direct_neuron_masks(self):
    manifest = N64.build_atlas_manifest(self.bundle)
    self.assertEqual(list(range(64)), [item["id"] for item in manifest["neurons"]])
    self.assertTrue(manifest["checks"]["masks_disjoint"])
    self.assertTrue(manifest["checks"]["static_clear"])
    self.assertTrue(manifest["checks"]["radius_98"])

def test_clear_button_feedback_and_system_labels(self):
    for mask, text in EXPECTED_BUTTON_LABELS.items():
        self.assert_target_text(self.frame(pressed_mask=mask), text)
    self.assert_target_text(self.frame(ui_flags=N64.FLY_UI_CHORD_ARMED), "SYSTEM//HOLD")
    self.assert_target_text(self.frame(ui_flags=N64.FLY_UI_SYSTEM), "GARMIN//SYSTEM")
```

- [ ] **Step 5: Port and compact the target renderer**

Keep the packed 3x5 font. Replace repeated Bresenham calls and large strings with a compact stroke display list, a small direction interpreter, and indexed label fragments. Remove the old enclosing polygon, phase dot, numeric/cryptic state labels, unreachable `BACK>SYSTEM` footer, and 8x8 grid.

```c
void n64_render(uint8_t *framebuffer, const FlyBrain64 *brain,
                const FlyBrainInputs *inputs, uint32_t tick,
                uint8_t ui_flags);
```

Render `FLYOS // N64`, full state names `REST/MOVE/AROUSE/QUIET`, physical-height idle callouts, and press labels `LIGHT // LUX`, `START // MOTOR BURST`, `BACK // MODE`, `DOWN // CALM`, and `UP // PULSE`.

- [ ] **Step 6: Derive the mapping manifest from the linked binary**

Extend `emulate_display()` to render activations `0`, `128`, `256`, `512`, and `-512` one neuron at a time. Compute each dynamic mask from framebuffer differences, reject overlap with every other dynamic mask and every static stroke, and record a canonical `mapping_sha256`.

```python
def build_atlas_manifest(bundle: Bundle) -> dict[str, Any]:
    return {"schema": "flyos.n64-atlas-mapping.v1",
            "neurons": neurons,
            "mapping_sha256": mapping_sha256,
            "checks": checks}
```

- [ ] **Step 7: Run host, target, geometry, and flash checks**

```powershell
cmake --build flyos/build-atlas --config Release
ctest --test-dir flyos/build-atlas -C Release --output-on-failure
powershell -NoProfile -ExecutionPolicy Bypass -File flyos/target/fr245_1370_n64_atlas_shell/build.ps1
python -B -m unittest -v -k atlas tools/garmin-firmware/tests/test_emulate_n64_atlas_shell.py
python -B -m unittest -v -k visual tools/garmin-firmware/tests/test_emulate_n64_atlas_shell.py
```

Expected: all pixels and callouts lie within radius 98; 64 IDs and masks are exact/disjoint; target and host model states match; both linked sections remain within their proved bounds.

- [ ] **Step 8: Commit the atlas renderer**

```powershell
git -C C:\Users\zgbre\flywatchos-publish add flyos/display flyos/tests flyos/CMakeLists.txt flyos/target/fr245_1370_n64_atlas_shell tools/garmin-firmware/emulate_n64_atlas_shell.py tools/garmin-firmware/tests/test_emulate_n64_atlas_shell.py
git -C C:\Users\zgbre\flywatchos-publish diff --cached --check
git -C C:\Users\zgbre\flywatchos-publish commit -m "feat: render the FlyOS neural atlas"
```

---

### Task 5: Implement detach marking, post-unlock redraw, and bounded retry

**Files:**
- Modify: `flyos/target/fr245_1370_n64_atlas_shell/hook.S`
- Modify: `flyos/target/fr245_1370_n64_atlas_shell/overlay.c`
- Modify: `flyos/target/fr245_1370_n64_atlas_shell/state.h`
- Modify: `flyos/target/fr245_1370_n64_atlas_shell/linker.ld`
- Modify: `flyos/target/fr245_1370_n64_atlas_shell/build.ps1`
- Modify: `tools/garmin-firmware/emulate_n64_atlas_shell.py`
- Modify: `tools/garmin-firmware/tests/test_emulate_n64_atlas_shell.py`
- Create: `docs/atlas-shell-usb-detach.md`

**Interfaces:**
- Produces `void flyos_usb_teardown_mark(void)`, which calls the original helper and atomically records pending state without queueing.
- Produces `void flyos_usb_worker_unlocked(uint32_t mutex)`, which performs the original unlock before any view scan or queue request.
- Produces `void flyos_detach_retry(void)`, callable only from the bounded context proved in Task 1.
- Uses START's mode nibble for `DETACH_NONE/PENDING/RETRY1/RETRY2/RETRY3/QUEUED/EXHAUSTED` while preserving START's local owner.

- [ ] **Step 1: Write failing hook ABI and ordering tests**

```python
def test_detach_hooks_preserve_original_calls_and_unlock_before_queue(self):
    result = N64.emulate_usb_sequence(self.bundle, [{"from": 3, "to": 2, "view": "valid"}])
    self.assertEqual(1, result["original_teardown_calls"])
    self.assertLess(result["unlock_instruction_index"], result["first_view_read_index"])
    self.assertLess(result["unlock_instruction_index"], result["first_queue_call_index"])
    self.assertEqual(0, result["queue_sends"][0]["front"])
    self.assertEqual(0, result["queue_sends"][0]["timeout"])
```

Test exact patched bytes at the Task 1-approved sites, every predecessor/return, callee-saved registers, stack restoration, mutex state, and exact restoration of the official instructions.

- [ ] **Step 2: Write failing transition/retry tests**

Cover `3->2`, `4->2`, `3<->4`, non-mass transitions, duplicate observations, queue returns `0/2/3`, modal-at-edge then later-home, new attach canceling pending work, retry exhaustion, malformed/cyclic/changing views, and strictly one successful event per detach epoch.

```python
def test_modal_edge_retries_only_after_later_stable_home(self):
    result = N64.emulate_usb_sequence(self.bundle, [
        {"from": 4, "to": 2, "view": "charging_modal", "queue_result": 0},
        {"retry": 1, "view": "valid", "queue_result": 0},
    ])
    self.assertEqual([], result["steps"][0]["queue_sends"])
    self.assertEqual(1, len(result["steps"][1]["queue_sends"]))
    self.assertEqual("DETACH_QUEUED", result["final_detach_mode"])
    self.assertEqual(1, result["successful_redraws"])
```

- [ ] **Step 3: Run detach tests and verify RED**

```powershell
python -B -m unittest -v -k detach tools/garmin-firmware/tests/test_emulate_n64_atlas_shell.py
python -B -m unittest -v -k retry tools/garmin-firmware/tests/test_emulate_n64_atlas_shell.py
```

Expected: FAIL because the new hook sites and detach state machine are absent.

- [ ] **Step 4: Implement the two-site hook structure**

Use only addresses approved by the Task 1 report. The expected evidence candidates are the four-byte `bl 0x207B0` at `0x2093E` and four-byte `b.w 0x874C` at `0x20A8A`; abort if the report selects different sites or bytes.

```c
static void detach_mark_pending(void);
static void detach_after_unlock(void);
static void detach_retry_from_ui(void);
```

The first wrapper calls the exact original teardown helper, then CAS-marks pending. The second calls the exact original unlock, then scans and queues at the back (`front=0`, `timeout=0`). Neither wrapper draws or performs bus I/O. Save and restore every register required by the proved ABI.

- [ ] **Step 5: Implement bounded retry and modal behavior**

Only the callback proved in Task 1 may call `detach_retry_from_ui`. Each distinct callback opportunity advances START's detach mode from pending through at most three retry states. Success stores `DETACH_QUEUED`; a fourth failed opportunity stores `DETACH_EXHAUSTED`; a new confirmed `3/4` attach resets to `DETACH_NONE`. The callback queues only for stable home. If Task 1 proved a native nonblocking modal refresh path, call that exact path for the surviving-modal case; otherwise feasibility should already have stopped the plan.

- [ ] **Step 6: Prove complete stale-frame replacement**

Seed all 57,600 bytes with a recognizable native charging pattern. Execute detach and the eligible display flush. Assert that every byte is replaced by the FlyOS frame, dirty is called with `(0,0,240,240)`, and the USB/key workers made zero framebuffer writes. Seed a surviving modal and assert byte-for-byte preservation until the proved native refresh or later home retry.

- [ ] **Step 7: Run the focused and complete emulator suites**

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File flyos/target/fr245_1370_n64_atlas_shell/build.ps1
python -B -m unittest -v -k detach tools/garmin-firmware/tests/test_emulate_n64_atlas_shell.py
python -B -m unittest -v -k retry tools/garmin-firmware/tests/test_emulate_n64_atlas_shell.py
python -B -m unittest -v tools/garmin-firmware/tests/test_emulate_n64_atlas_shell.py
```

Expected: all detach edges, lock ordering, deduplication, retry, modal preservation, write confinement, cross-segment branch coverage, and 384-byte stack checks PASS.

- [ ] **Step 8: Document and commit detach recovery**

```powershell
git -C C:\Users\zgbre\flywatchos-publish add flyos/target/fr245_1370_n64_atlas_shell tools/garmin-firmware/emulate_n64_atlas_shell.py tools/garmin-firmware/tests/test_emulate_n64_atlas_shell.py docs/atlas-shell-usb-detach.md
git -C C:\Users\zgbre\flywatchos-publish diff --cached --check
git -C C:\Users\zgbre\flywatchos-publish commit -m "fix: refresh FlyOS after USB detach"
```

---

### Task 6: Integrate, generate exact visual evidence, and obtain visual approval

**Files:**
- Modify: `flyos/target/fr245_1370_n64_atlas_shell/build.ps1`
- Modify: `flyos/target/fr245_1370_n64_atlas_shell/linker.ld`
- Modify: `tools/garmin-firmware/emulate_n64_atlas_shell.py`
- Modify: `tools/garmin-firmware/tests/test_emulate_n64_atlas_shell.py`
- Create: `docs/atlas-shell-placement.md`
- Create privately: `artifacts/analysis/fr245-1370-n64-atlas-shell-visual-audit/`

**Interfaces:**
- Produces a linked manifest with exact section/function sizes, remaining bytes, stack/call graph, branch coverage, state encodings, and source/evidence hashes.
- Produces exactly 12 labeled target-derived previews and a 4x3 contact sheet.
- Packaging remains blocked until the user approves the exact contact sheet.

- [ ] **Step 1: Write failing manifest/evidence tests**

```python
def test_integrated_manifest_and_visual_evidence_are_complete(self):
    manifest = self.bundle.manifest
    self.assertLessEqual(manifest["segments"]["primary"]["size"], 1023)
    self.assertLessEqual(manifest["segments"]["secondary"]["size"], 2048)
    self.assertEqual(384, manifest["stack_audit"]["maximum_allowed_bytes"])
    evidence = N64.publish_evidence(self.bundle.build, self.output)
    self.assertEqual(12, len(evidence["previews"]))
    self.assertIn("contact-sheet.png", evidence["files"])
    self.assertTrue(evidence["atlas_mapping"]["checks"]["radius_98"])
```

- [ ] **Step 2: Add exact linker and build accounting**

Add linker symbols around input, renderer, packed model, USB wrappers, tables, and trampolines. Record exact used and remaining bytes for every verified interval. Continue rejecting `.data`, `.bss`, COMMON, repair-byte use, unapproved external transfers, and any branch not exercised by the emulator suite.

- [ ] **Step 3: Generate the 12 target-derived fixtures**

Generate and label: idle, LIGHT, START, BACK, DOWN, UP, chord armed, Garmin system mode, USB mass-storage, native charging pass-through, observed-update pass-through, and malformed-view pass-through. Charging/update/malformed fixtures use seeded native frames and must remain byte-identical; they do not depict invented FlyOS data.

```python
PREVIEW_FIXTURES = (
    "idle", "light", "start", "back", "down", "up",
    "chord-armed", "system-mode", "usb", "charging-passthrough",
    "update-passthrough", "malformed-passthrough",
)
```

Build a labeled 4x3 contact sheet, save PNG and PPM files, hash every file, and include the atlas mapping manifest and framebuffer hashes in the evidence manifest.

- [ ] **Step 4: Run focused, full, and host verification once**

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File flyos/target/fr245_1370_n64_atlas_shell/build.ps1 -BuildRoot artifacts/analysis/fr245-1370-n64-atlas-shell-build -EvidenceRoot artifacts/analysis/fr245-1370-n64-atlas-shell-visual-audit
python -B -m unittest -v tools/garmin-firmware/tests/test_emulate_n64_atlas_shell.py
python -B -m unittest discover -s tools/garmin-firmware/tests -p "test_*.py" -v
cmake --build flyos/build-atlas --config Release
ctest --test-dir flyos/build-atlas -C Release --output-on-failure
```

Expected: all suites PASS without rerunning unchanged checks; manifest records exact remaining bytes and all cross-segment branches are covered.

- [ ] **Step 5: Self-review the integrated evidence**

Verify the contact sheet has no clipped pixels, no numeric button labels, no rounded paired-lobe silhouette, readable callouts, 64 visible neurons, and distinct chord/system states. Verify the evidence manifest hashes every preview and the mapping IDs are exactly `0..63` once each.

- [ ] **Step 6: Present the exact contact sheet for user approval**

Show `artifacts/analysis/fr245-1370-n64-atlas-shell-visual-audit/contact-sheet.png` and report the linked primary/secondary sizes and remaining bytes. Stop before Task 7 until the user approves this exact integrated visual. Visual revisions return to Task 4 and rerun Task 6 once.

- [ ] **Step 7: Commit the approved integrated source and public-safe evidence**

Copy the target, emulator, tests, placement document, contact sheet, mapping manifest, and hash manifest to the curated repository. Exclude firmware-derived binaries and private decompilation.

```powershell
git -C C:\Users\zgbre\flywatchos-publish add flyos tools/garmin-firmware docs/atlas-shell-placement.md artifacts/analysis
git -C C:\Users\zgbre\flywatchos-publish diff --cached --check
git -C C:\Users\zgbre\flywatchos-publish commit -m "feat: integrate the FlyOS atlas shell"
git -C C:\Users\zgbre\flywatchos-publish push origin main
```

---

### Task 7: Build the quarantined 13.78 candidate and 13.79 restore pair

**Files:**
- Create: `tools/garmin-firmware/neural_specimen_n64_atlas_shell_version_strategy.py`
- Create: `tools/garmin-firmware/tests/test_neural_specimen_n64_atlas_shell_version_strategy.py`
- Create privately: `artifacts/firmware/quarantine/Forerunner245_1378_FlyOS_N64_Atlas_Shell.analysis-only.DO_NOT_INSTALL`
- Create privately: `artifacts/firmware/quarantine/Forerunner245_1379_Official_Code_Restore.analysis-only.DO_NOT_INSTALL`
- Create privately: `artifacts/firmware/analysis/neural-specimen-n64-atlas-shell-package-build-1378-1379.json`
- Create privately: `artifacts/firmware/analysis/neural-specimen-n64-atlas-shell-package-strict-verification-1378-1379.json`
- Create privately: `artifacts/firmware/analysis/neural-specimen-n64-atlas-shell-package-SHA256SUMS.txt`
- Modify: `docs/atlas-shell-placement.md`
- Modify: `docs/investigation-log.md`
- Modify: `docs/session-report.md`

**Interfaces:**
- Produces `construct_pair(repo_root: Path) -> tuple[bytes, bytes, dict[str, Any]]`.
- Produces an offline-only synthetic 13.78 candidate and complete official-code 13.79 restore wrapper.
- Produces no enabled staging profile.

- [ ] **Step 1: Write failing package tests**

```python
def test_candidate_and_restore_versions_and_ranges(self):
    candidate, restore, report = strategy.construct_pair(ROOT)
    self.assertEqual(1378, report["candidate"]["software_version"])
    self.assertEqual(1379, report["restore"]["software_version"])
    self.assertEqual(strategy.ALLOWED_PATCH_RANGES,
                     report["candidate"]["changed_decoded_ranges"])
    self.assertTrue(report["restore"]["complete_official_restore"])
    self.assertFalse(report["policy"]["live_staging_allowed"])
```

Test exact display/key/USB hook bytes, primary/secondary payloads, repair byte, unchanged helper/resources, additive/checkpoint validity, exact reconstruction, create-new semantics, cleanup faults, immutable inputs, and rejection by the locked staging script.

- [ ] **Step 2: Run package tests and verify RED**

```powershell
python -B -m unittest -v tools/garmin-firmware/tests/test_neural_specimen_n64_atlas_shell_version_strategy.py
```

Expected: FAIL because the 13.78/13.79 strategy does not exist.

- [ ] **Step 3: Implement the offline-only strategy**

Base it on the existing controls strategy but accept only the final Task 6 manifest and exact source/evidence hashes. Patch only the version fields, approved hooks, two payload allocations, and one additive repair byte. The restore reconstructs the full official 13.70 application/resources with coherent synthetic version 13.79.

```python
CANDIDATE_VERSION = 1378
RESTORE_VERSION = 1379
CANDIDATE_FILENAME = "Forerunner245_1378_FlyOS_N64_Atlas_Shell.analysis-only.DO_NOT_INSTALL"
RESTORE_FILENAME = "Forerunner245_1379_Official_Code_Restore.analysis-only.DO_NOT_INSTALL"
```

- [ ] **Step 4: Build the pair only in quarantine and hash it**

```powershell
python -B tools/garmin-firmware/neural_specimen_n64_atlas_shell_version_strategy.py --repo-root . --build-quarantine
python -B tools/garmin-firmware/neural_specimen_n64_atlas_shell_version_strategy.py --repo-root . --verify-written-pair
Get-FileHash -Algorithm SHA256 artifacts/firmware/quarantine/*1378* , artifacts/firmware/quarantine/*1379*
```

Expected: both files are newly created, verification is true, and `tools/live-proof/stage-gupdate.ps1` rejects both names and hashes.

- [ ] **Step 5: Run complete package and runtime verification**

```powershell
python -B -m unittest -v tools/garmin-firmware/tests/test_neural_specimen_n64_atlas_shell_version_strategy.py
python -B -m unittest -v tools/garmin-firmware/tests/test_emulate_n64_atlas_shell.py
python -B -m unittest discover -s tools/garmin-firmware/tests -p "test_*.py" -v
ctest --test-dir flyos/build-atlas -C Release --output-on-failure
```

Run exact reconstruction, generic GCD validation, full-image validation, checksum ledger, packaged-binary emulation, and restore-byte comparison once. Record every result and SHA-256 in the strict report.

- [ ] **Step 6: Document and commit only public-safe tooling**

```powershell
git -C C:\Users\zgbre\flywatchos-publish add tools/garmin-firmware/neural_specimen_n64_atlas_shell_version_strategy.py tools/garmin-firmware/tests/test_neural_specimen_n64_atlas_shell_version_strategy.py docs/atlas-shell-placement.md docs/investigation-log.md docs/session-report.md
git -C C:\Users\zgbre\flywatchos-publish diff --cached --check
git -C C:\Users\zgbre\flywatchos-publish commit -m "build: add quarantined atlas shell package"
git -C C:\Users\zgbre\flywatchos-publish push origin main
```

Do not add the candidate, restore, package reports containing proprietary bytes, or private firmware evidence to Git.

---

### Task 8: Independent review and exact live-write proposal

**Files:**
- Create privately: `artifacts/firmware/analysis/n64-atlas-shell-independent-review.json`
- Create: `docs/atlas-shell-live-proposal.md`
- Modify: `docs/recovery.md`
- Modify: `docs/investigation-log.md`
- Modify: `docs/session-report.md`

**Interfaces:**
- Produces an independent review of specification compliance, allocation, stack, input atomicity, USB locking/retry, renderer masks, package reconstruction, and recovery risk.
- Produces a reviewable live-write proposal; it performs no staging or watch write.

- [ ] **Step 1: Dispatch independent source/spec and binary/safety reviews**

One reviewer compares implementation to every spec acceptance criterion. A separate reviewer starts from the final ELF/package reports and checks hook bytes, ABI, lock ordering, writes, stack, allocations, reconstruction, restore, and staging lock without trusting the implementation narrative.

- [ ] **Step 2: Resolve all Critical and Important findings**

For each accepted finding, add a failing regression test, observe RED, implement the smallest correction, rerun the focused test, and then rerun only the affected broader gate. Rebuild/re-hash the package pair after any binary change.

- [ ] **Step 3: Verify recovery facts and staging lock**

Confirm the restore remains a complete official-code wrapper, normal GarminOS/USB update service is still required, and no nonboot recovery path is known. Prove the stage script rejects both 13.78 and 13.79 while the lock file retains its recorded SHA-256.

- [ ] **Step 4: Write the exact live proposal**

`docs/atlas-shell-live-proposal.md` must state:

```text
candidate filename, size, SHA-256, synthetic version, destination
restore filename, size, SHA-256, synthetic version, destination
every changed hook and payload range
what each range contains
known brick scenarios and nonboot-recovery limitation
normal restore procedure while GarminOS still enumerates
all test/review/contact-sheet evidence
```

End with an explicit statement that the artifacts remain quarantined and have not been copied to the watch.

- [ ] **Step 5: Commit and push the public proposal**

```powershell
git -C C:\Users\zgbre\flywatchos-publish add docs/atlas-shell-live-proposal.md docs/recovery.md docs/investigation-log.md docs/session-report.md
git -C C:\Users\zgbre\flywatchos-publish diff --cached --check
git -C C:\Users\zgbre\flywatchos-publish commit -m "docs: propose reviewed atlas shell install"
git -C C:\Users\zgbre\flywatchos-publish push origin main
```

- [ ] **Step 6: Present the exact write for separate approval and stop**

Present the two artifact hashes, exact watch destination, write mechanics, brick risk, recovery limitations, and restore steps. Do not unlock staging, copy a GCD to the watch, reboot for installation, or write any watch storage until the user explicitly approves that exact candidate action after this disclosure.
