import importlib.util
import itertools
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[3]
OLD_TARGET = ROOT / "flyos" / "target" / "fr245_1370_neural_specimen_n64_controls"
TARGET = ROOT / "flyos" / "target" / "fr245_1370_n64_atlas_shell"
EMULATOR = ROOT / "tools" / "garmin-firmware" / "emulate_n64_atlas_shell.py"
SPEC = importlib.util.spec_from_file_location("flyos_n64_atlas_shell_emulator", EMULATOR)
N64 = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = N64
SPEC.loader.exec_module(N64)

EXPECTED_BUTTON_LABELS = {1: "LIGHT // LUX", 2: "START // MOTOR BURST",
                          4: "BACK // MODE", 8: "DOWN // CALM", 16: "UP // PULSE"}
EXPECTED_IDLE_CALLOUTS = ("LUX", "MOTOR", "MODE", "CALM", "PULSE")

# Measured linked sizes of the two pinned payload envelopes (limits 1023 and
# 2048), down from the 996 + 2044 byte controls baseline this target forked.
# Re-baselined by the five-key ownership work: addressing the audited halfword
# as two complement-protected bytes, and keeping every stored state value a
# compile-time constant, made the state machine smaller than the three-key one
# it replaced.
PINNED_PRIMARY = 856
PINNED_SECONDARY = 1904

# Module-level build fixture: the target's build/ directory is generated,
# gitignored output (see .gitignore's **/build/) -- a clean checkout has none,
# and nothing else in this task produces flyos/target/.../build/.  Build the
# target exactly once, into its own temp sandbox via -BuildRoot, and share the
# resulting Bundle across every TestCase below rather than depending on (or
# repeatedly rebuilding into) an in-tree build directory.
NEW_SANDBOX = None
NEW_BUILD = None


def _build_sandbox(target_dir, prefix):
    sandbox = tempfile.TemporaryDirectory(prefix=prefix)
    build = pathlib.Path(sandbox.name) / "build"
    completed = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
         str(target_dir / "build.ps1"), "-BuildRoot", str(build)],
        cwd=ROOT, capture_output=True, text=True,
    )
    if completed.returncode:
        sandbox.cleanup()
        raise RuntimeError(completed.stdout + completed.stderr)
    return sandbox, build


def setUpModule():
    global NEW_SANDBOX, NEW_BUILD
    NEW_SANDBOX, NEW_BUILD = _build_sandbox(TARGET, "flyos-n64-atlas-shell-suite-")


def tearDownModule():
    if NEW_SANDBOX is not None:
        NEW_SANDBOX.cleanup()


class ScaffoldTests(unittest.TestCase):
    def test_hook_and_packed_brain_are_still_the_exact_controls_sources(self):
        for name in ("hook.S", "brain64_packed.c"):
            self.assertEqual((OLD_TARGET / name).read_bytes(), (TARGET / name).read_bytes())

    def test_renderer_and_overlay_have_diverged_for_the_atlas(self):
        # The fork was byte-identical at task 2; the atlas renderer and its
        # ui_flags call site are this task's deliberate divergence.
        for name in ("renderer.c", "overlay.c"):
            self.assertNotEqual((OLD_TARGET / name).read_bytes(),
                                (TARGET / name).read_bytes())
        self.assertIn(b"FLY_UI_USB", (TARGET / "overlay.c").read_bytes())


class StateCodecTests(unittest.TestCase):
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

    def test_the_word_is_exactly_its_two_complement_protected_bytes(self):
        # The target writes the local nibble and the mode nibble as two
        # independent byte stores rather than composing a halfword.  That is
        # only legitimate if the two bytes are exactly state.h's word, so pin
        # the decomposition across every valid combination.
        for local, mode in itertools.product(range(4), range(7)):
            word = N64.pack_state(local, mode)
            self.assertEqual(word & 0xFF, N64.state_byte(local))
            self.assertEqual(word >> 8, N64.state_byte(mode))
            self.assertEqual(word, N64.state_byte(local) | (N64.state_byte(mode) << 8))

    def test_every_recognised_cold_or_legacy_byte_fails_the_complement_check(self):
        # 0x00 reset, 0xFF erased, and the low bytes of the three legacy 13.76
        # encodings must all read as INVALID, which is what lets phase zero
        # normalise them without ever overwriting a real FlyOS state.
        for stale in (0x00, 0xFF, 0xA1, 0xA2):
            self.assertEqual(N64.STATE_INVALID, N64.read_state_byte(stale), hex(stale))
        for valid in range(16):
            self.assertEqual(valid, N64.read_state_byte(N64.state_byte(valid)))

    def test_unpack_round_trips_every_valid_local_and_mode_combination(self):
        for local, mode in itertools.product(range(4), range(7)):
            word = N64.pack_state(local, mode)
            self.assertEqual((local, mode), N64.unpack_state(word))

    def test_unpack_rejects_every_single_corrupted_nibble(self):
        word = N64.pack_state(N64.FLY_PULSE, N64.SYSTEM_PENDING)
        for shift in (0, 4, 8, 12):
            for delta in range(1, 16):
                corrupt = word ^ (delta << shift)
                if corrupt == word:
                    continue
                local_ok = N64.read_local(corrupt) != N64.STATE_INVALID
                mode_ok = N64.read_mode(corrupt) != N64.STATE_INVALID
                if shift in (0, 4):
                    self.assertFalse(local_ok, hex(corrupt))
                else:
                    self.assertFalse(mode_ok, hex(corrupt))

    def test_c_and_python_codec_agree_for_every_local_mode_pair(self):
        for local, mode in itertools.product(range(16), range(16)):
            word = N64.pack_state(local, mode)
            self.assertEqual(word, N64.state_oracle_pack(local, mode))

    def test_c_and_python_readers_agree_on_a_sample_of_words(self):
        samples = [0x0000, 0xFF00, 0xFFFF, 0xF0F0, 0xF0E1, 0xE1F0, 0xB4F0,
                   N64.pack_state(N64.GARMIN_HELD, N64.SYSTEM_EXCURSION),
                   N64.pack_state(N64.FLY_HELD, N64.DETACH_EXHAUSTED)]
        for word in samples:
            expected = (N64.read_local(word), N64.read_mode(word))
            self.assertEqual(expected, N64.state_oracle_unpack(word), hex(word))


class VendorViewOracleTests(unittest.TestCase):
    """vendor_view_oracle has no on_read hook of its own, so it cannot model
    the mid-scan mutations finder_mismatch/false_first_visible/root_mutation
    -- it must reject those fixtures rather than silently running them as a
    plain "valid" scan under the wrong name."""

    def test_rejects_fixtures_the_hookless_oracle_cannot_model(self):
        for view in ("finder_mismatch", "false_first_visible", "root_mutation"):
            with self.subTest(view=view):
                with self.assertRaisesRegex(ValueError, "unknown vendor fixture"):
                    N64.vendor_view_oracle(view)

    def test_accepts_every_real_vendor_fixture(self):
        for view in N64.VENDOR_FIXTURES:
            with self.subTest(view=view):
                result = N64.vendor_view_oracle(view)
                self.assertIn("status", result)


class TargetBuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build = NEW_BUILD
        cls.bundle = N64.load_build(cls.build)

    def test_exact_layout_hooks_stack_and_state_header_are_recorded(self):
        manifest = self.bundle.manifest
        self.assertEqual("flyos.fr245.n64-atlas-shell-target.v1", manifest["schema"])
        self.assertEqual({"hook", "keyhook", "primary", "secondary"}, set(manifest["segments"]))
        self.assertEqual((N64.HOOK, 4),
                         (manifest["segments"]["hook"]["start"], manifest["segments"]["hook"]["size"]))
        self.assertEqual((N64.KEY_HOOK, 6),
                         (manifest["segments"]["keyhook"]["start"], manifest["segments"]["keyhook"]["size"]))
        self.assertLessEqual(manifest["segments"]["primary"]["size"], 1023)
        self.assertLessEqual(manifest["segments"]["secondary"]["size"], 2048)
        self.assertEqual(0x1F63FF, manifest["repair_byte"])
        self.assertEqual(384, manifest["stack_audit"]["stack_bound_bytes"])
        self.assertFalse(manifest["packaging_allowed"])
        self.assertIn("flyos/target/fr245_1370_n64_atlas_shell/state.h", manifest["sources"])
        self.assertEqual(N64.sha256((TARGET / "state.h").read_bytes()),
                         manifest["sources"]["flyos/target/fr245_1370_n64_atlas_shell/state.h"])

    def test_build_is_clean_and_freestanding(self):
        N64.assert_build_clean(self.bundle.build, self.bundle.manifest)
        sections, _ = N64.read_elf(self.bundle.build / N64.ELF_NAME)
        self.assertTrue(".forbidden" not in sections or sections[".forbidden"]["size"] == 0)

    def test_both_payload_segments_still_fit_their_proved_allocation(self):
        primary = self.bundle.manifest["segments"]["primary"]["size"]
        secondary = self.bundle.manifest["segments"]["secondary"]["size"]
        self.assertLessEqual(primary, 1023)
        self.assertLessEqual(secondary, 2048)
        # The atlas rewrite is a size reduction against the 996 + 2044 byte
        # controls baseline, and the freed flash is what a later task's state
        # machine has to fit into.  Pin the measured sizes exactly so giving
        # any of it back has to be a conscious re-baseline, not a silent drift.
        self.assertEqual((PINNED_PRIMARY, PINNED_SECONDARY), (primary, secondary))
        self.assertLessEqual(primary + secondary, PINNED_PRIMARY + PINNED_SECONDARY)


class AtlasMappingTests(unittest.TestCase):
    """The mapping manifest is derived from the linked binary, not declared."""

    @classmethod
    def setUpClass(cls):
        cls.bundle = N64.load_build(NEW_BUILD)
        cls.manifest = N64.build_atlas_manifest(cls.bundle)

    def test_linked_target_has_64_disjoint_direct_neuron_masks(self):
        manifest = self.manifest
        self.assertEqual("flyos.n64-atlas-mapping.v1", manifest["schema"])
        self.assertEqual(list(range(64)), [item["id"] for item in manifest["neurons"]])
        self.assertTrue(manifest["checks"]["masks_disjoint"])
        self.assertTrue(manifest["checks"]["static_clear"])
        self.assertTrue(manifest["checks"]["radius_98"])
        self.assertTrue(manifest["checks"]["masks_match_declared_layout"])
        self.assertTrue(manifest["checks"]["populations"])
        self.assertEqual(64, len(manifest["mapping_sha256"]))

    def test_every_derived_mask_is_a_five_by_five_block_of_its_own(self):
        seen = set()
        for item in self.manifest["neurons"]:
            mask = set(item["mask"])
            self.assertEqual(25, len(mask), item["id"])
            self.assertEqual({(item["y"] + row) * 240 + item["x"] + column
                              for row in range(5) for column in range(5)}, mask)
            self.assertFalse(mask & seen, item["id"])
            seen |= mask
        self.assertEqual(64 * 25, len(seen))

    def test_density_alone_carries_magnitude_for_every_neuron(self):
        self.assertTrue(self.manifest["checks"]["densities"])
        for item in self.manifest["neurons"]:
            self.assertEqual([1, 9, 16, 25, 25], item["density"], item["id"])
            self.assertEqual([1, 9, 16, 25, 25],
                             [len(item["lit"][str(activation)])
                              for activation in N64.ATLAS_ACTIVATIONS], item["id"])

    def test_only_the_descending_action_fan_saturates_amber(self):
        for item in self.manifest["neurons"]:
            expected = [N64.GREEN, N64.MAGENTA]
            if item["population"] == 5:
                expected = sorted(expected + [N64.AMBER])
            self.assertEqual(expected, item["colours"], item["id"])
            self.assertEqual(item["id"] >= 56, N64.AMBER in item["colours"], item["id"])

    def test_populations_own_exactly_the_declared_identifier_ranges(self):
        ranges = {0: range(0, 12), 1: range(12, 24), 2: range(24, 40),
                  3: range(40, 48), 4: range(48, 56), 5: range(56, 64)}
        for item in self.manifest["neurons"]:
            self.assertIn(item["id"], ranges[item["population"]])

    def test_geometry_only_renders_exactly_what_the_audited_path_renders(self):
        # Every one of the 257 renders behind build_atlas_manifest uses the
        # geometry_only path, which drops the per-instruction allowlist, the
        # stack tracking and both memory hooks for speed.  Pin it to the fully
        # hooked render, which is itself compared against the native host
        # oracle -- that is the check that would have caught the Unicorn
        # IT-block write-hook divergence immediately.
        for fixture in ({}, {"pressed_mask": 2}, {"forced_activation": (56, 700)}):
            with self.subTest(fixture=fixture):
                audited = N64.emulate_display(self.bundle, **fixture)
                fast = N64.emulate_display(self.bundle, geometry_only=True, **fixture)
                self.assertEqual(audited["framebuffer"], fast["framebuffer"])
                self.assertEqual(audited["eligible"], fast["eligible"])
                self.assertEqual(audited["activation"], fast["activation"])

    def test_deriving_the_mapping_again_reproduces_the_same_hash(self):
        # Drop the memo so this really re-runs all 257 emulations rather than
        # handing back the manifest the class already holds.
        N64._ATLAS_MANIFESTS.clear()
        again = N64.build_atlas_manifest(self.bundle)
        self.assertEqual(self.manifest["mapping_sha256"], again["mapping_sha256"])
        self.assertEqual(self.manifest["neurons"], again["neurons"])


class VisualLabelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = N64.load_build(NEW_BUILD)

    def frame(self, **fixture):
        return N64.emulate_display(self.bundle, **fixture)["framebuffer"]

    def assert_target_text(self, framebuffer, text):
        hits = N64.find_text(framebuffer, text)
        self.assertEqual(1, len(hits), f"{text!r} appeared {len(hits)} times")
        return hits[0]

    def test_clear_button_feedback_and_system_labels(self):
        for mask, text in EXPECTED_BUTTON_LABELS.items():
            self.assert_target_text(self.frame(forced_buttons=mask), text)
        self.assert_target_text(self.frame(ui_flags=N64.FLY_UI_CHORD_ARMED), "SYSTEM//HOLD")
        self.assert_target_text(self.frame(ui_flags=N64.FLY_UI_SYSTEM), "GARMIN//SYSTEM")

    def test_every_physically_reachable_key_shows_its_callout(self):
        # All five keys belong to FlyOS on a stable home now, so BACK renders
        # its own callout instead of passing the frame through to Garmin.
        for mask, text in EXPECTED_BUTTON_LABELS.items():
            with self.subTest(mask=mask):
                result = N64.emulate_display(self.bundle, pressed_mask=mask)
                self.assertTrue(result["eligible"])
                self.assertEqual(mask, result["buttons"])
                self.assert_target_text(result["framebuffer"], text)

    def test_idle_frame_names_every_key_at_its_physical_height(self):
        idle = self.frame()
        layout = N64.atlas_layout()
        for key, word in enumerate(EXPECTED_IDLE_CALLOUTS):
            self.assertEqual([tuple(layout["callouts"][key])],
                             N64.find_text(idle, word), word)

    def test_title_and_the_full_state_name_are_rendered(self):
        names = ("REST", "MOVE", "AROUSE", "QUIET")
        result = N64.emulate_display(self.bundle)
        idle = result["framebuffer"]
        self.assert_target_text(idle, "FLYOS // N64")
        self.assert_target_text(idle, names[result["state"]])
        for other in set(names) - {names[result["state"]]}:
            self.assertEqual([], N64.find_text(idle, other), other)
        self.assertEqual([], N64.find_text(idle, "SYSTEM//HOLD"))
        self.assertEqual([], N64.find_text(idle, "LIGHT // LUX"))

    def test_system_session_outranks_a_held_chord_and_a_pressed_key(self):
        both = self.frame(pressed_mask=1, ui_flags=N64.FLY_UI_SYSTEM | N64.FLY_UI_CHORD_ARMED)
        self.assert_target_text(both, "GARMIN//SYSTEM")
        self.assertEqual([], N64.find_text(both, "SYSTEM//HOLD"))
        self.assertEqual([], N64.find_text(both, "LIGHT // LUX"))

    def test_usb_mass_storage_has_no_presentation_of_its_own_yet(self):
        # Task 5 owns USB detach; FLY_UI_USB is wired through but must not
        # silently invent a label here.
        self.assertEqual(N64.sha256(self.frame()),
                         N64.sha256(self.frame(ui_flags=N64.FLY_UI_USB)))
        self.assertEqual(1, N64.emulate_display(self.bundle, usb_state=3)["ui_flags"])

    def test_every_rendered_pixel_stays_inside_the_98_pixel_safe_circle(self):
        for fixture in ({}, {"pressed_mask": 2}, {"ui_flags": N64.FLY_UI_SYSTEM},
                        {"forced_activation": (56, 700)}):
            with self.subTest(fixture=fixture):
                result = N64.emulate_display(self.bundle, **fixture)
                self.assertTrue(result["safe_radius"])
                self.assertTrue(result["all_pixels_reviewed_palette"])
                self.assertEqual(64, result["verified_neuron_cells"])


class KeySequenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = N64.load_build(NEW_BUILD)

    def test_every_owned_sequence_walks_held_then_pulse_and_skips_garmin(self):
        for key in range(5):
            with self.subTest(key=key):
                result = N64.emulate_key_sequence(self.bundle, [
                    {"key": key, "phase": 0, "tick_ms": 5000},
                    {"key": key, "phase": 2, "tick_ms": 5200},
                    {"key": key, "phase": 3, "tick_ms": 5400},
                    {"key": key, "phase": 1, "tick_ms": 5600},
                ])
                self.assertEqual([], result["published"])
                self.assertEqual(["FLY_HELD", "FLY_HELD", "FLY_HELD", "FLY_PULSE"],
                                 [case["local_states"][key] for case in result["cases"]])
                self.assertLessEqual(result["maximum_runtime_stack_bytes"], 384)

    def test_gpio_mask_never_blocks_ownership_on_a_stable_home(self):
        # 13.76 failed open whenever BACK's line was down; no GPIO combination
        # may do that now.
        for mask in (0, 0b00100, 0b11011, 0b11111):
            with self.subTest(mask=bin(mask)):
                result = N64.emulate_key_sequence(self.bundle, [
                    {"key": 4, "phase": 0, "gpio_mask": mask},
                    {"key": 4, "phase": 1, "gpio_mask": mask},
                ])
                self.assertEqual([], result["published"])
                self.assertEqual("FLY_PULSE", result["final_local_states"][4])

    def test_tick_ms_is_returned_by_the_0x7fa4_getter_and_stamped_at_record_offset_zero(self):
        result = N64.emulate_key_sequence(self.bundle, [
            {"key": 1, "phase": 0, "tick_ms": 0x11223344},
            {"key": 1, "phase": 2, "tick_ms": 0x99999999},
            {"key": 1, "phase": 1, "tick_ms": 0x88888888},
        ])
        self.assertEqual(0x11223344, result["cases"][0]["record_timestamp"])
        # Only a fresh phase-0 press restamps offset zero; later phases of the
        # same physical sequence must not disturb it.
        self.assertEqual(0x11223344, result["cases"][1]["record_timestamp"])
        self.assertEqual(0x11223344, result["cases"][2]["record_timestamp"])

    def test_view_fixture_still_gates_ownership_under_the_new_name(self):
        for view in ("empty", "malformed", "not_home"):
            with self.subTest(view=view):
                result = N64.emulate_key_sequence(self.bundle, [{"key": 3, "phase": 0, "view": view}])
                self.assertEqual([{"type": 15, "key": 3, "state": 0}], result["published"])
                self.assertEqual("GARMIN_HELD", result["final_local_states"][3])


class ViewClassifierTests(unittest.TestCase):
    """The tri-state classifier is read out of the linked stable_view itself."""

    @classmethod
    def setUpClass(cls):
        cls.bundle = N64.load_build(NEW_BUILD)

    def frame(self, **fixture):
        return N64.emulate_display(self.bundle, **fixture)

    def test_view_classifier_distinguishes_home_nonhome_and_invalid(self):
        self.assertEqual("HOME", self.frame(view="valid")["view_class"])
        self.assertEqual("NON_HOME", self.frame(view="update_prompt")["view_class"])
        for view in ("empty", "malformed", "cycle", "too_long", "root_mutation"):
            with self.subTest(view=view):
                self.assertEqual("INVALID", self.frame(view=view)["view_class"])

    def test_a_hidden_home_node_is_non_home_and_a_trailing_node_is_still_home(self):
        # hidden_match: the watch face exists but something else is first
        # visible.  multiple: the watch face is first visible and another node
        # trails it.  Both lists are structurally sound, so neither is INVALID.
        self.assertEqual("NON_HOME", self.frame(view="hidden_match")["view_class"])
        self.assertEqual("HOME", self.frame(view="multiple")["view_class"])

    def test_a_list_that_changes_under_the_scan_is_invalid_not_non_home(self):
        for view in ("finder_mismatch", "false_first_visible"):
            with self.subTest(view=view):
                self.assertEqual("INVALID", self.frame(view=view)["view_class"])

    def test_update_prompt_fixture_is_labelled_an_unproved_placeholder(self):
        # Task 1's observed_update_prompt_non_home gate FAILED: no callback
        # identity was ever proved.  This fixture must therefore be visibly a
        # placeholder in the code, never presented as a proved Task 1 value.
        source = (ROOT / "tools" / "garmin-firmware" / "emulate_n64_atlas_shell.py").read_text()
        self.assertIn("UNPROVED_UPDATE_PROMPT_CALLBACK", source)
        self.assertNotEqual(N64.VIEW_CALLBACK, N64.UNPROVED_UPDATE_PROMPT_CALLBACK)
        controls = (ROOT / "docs" / "atlas-shell-controls.md").read_text()
        self.assertIn("observed_update_prompt_non_home", controls)


class FiveKeyOwnershipTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = N64.load_build(NEW_BUILD)

    def test_all_five_home_sequences_are_owned_for_every_usb_state(self):
        phases = (0, 2, 4, 3, 1)
        for usb in (0, 2, 3, 4):
            for key in range(5):
                with self.subTest(usb=usb, key=key):
                    result = N64.emulate_key_sequence(
                        self.bundle,
                        [{"key": key, "phase": phase, "tick_ms": 1000 + i * 200,
                          "view": "valid", "usb": usb} for i, phase in enumerate(phases)],
                    )
                    self.assertEqual([], result["published"])
                    self.assertEqual("FLY_PULSE", result["final_local_states"][key])

    def test_usb_mass_storage_no_longer_escapes_ownership(self):
        # The installed 13.76 behaviour published every phase to Garmin while
        # cached USB state was 3 or 4.  That escape is gone.
        for usb in (3, 4):
            result = N64.emulate_key_sequence(self.bundle, [
                {"key": 1, "phase": 0, "usb": usb}, {"key": 1, "phase": 1, "usb": usb}])
            self.assertEqual([], result["published"], f"usb={usb}")

    def test_back_held_no_longer_forces_garmin_ownership(self):
        # 13.76 failed open whenever BACK's GPIO was down.  BACK is a FlyOS key
        # now, so holding it must not hand the other four keys to Garmin.
        BACK_BIT = 1 << 2
        for key in range(5):
            with self.subTest(key=key):
                result = N64.emulate_key_sequence(self.bundle, [
                    {"key": key, "phase": 0, "gpio_mask": BACK_BIT}])
                self.assertEqual([], result["published"])
                self.assertEqual("FLY_HELD", result["final_local_states"][key])

    def test_a_native_owner_is_latched_through_a_later_home(self):
        # Phase zero saw a non-home view, so every later phase of that physical
        # sequence belongs to Garmin even once the watch face comes back.
        result = N64.emulate_key_sequence(self.bundle, [
            {"key": 4, "phase": 0, "view": "not_home"},
            {"key": 4, "phase": 2, "view": "valid"},
            {"key": 4, "phase": 1, "view": "valid"},
        ])
        self.assertEqual([{"type": 15, "key": 4, "state": phase} for phase in (0, 2, 1)],
                         result["published"])
        self.assertEqual("GARMIN_HELD", result["cases"][0]["local_states"][4])

    def test_a_flyos_owner_is_latched_through_a_later_non_home_view(self):
        result = N64.emulate_key_sequence(self.bundle, [
            {"key": 0, "phase": 0, "view": "valid"},
            {"key": 0, "phase": 2, "view": "not_home"},
            {"key": 0, "phase": 4, "view": "malformed"},
            {"key": 0, "phase": 1, "view": "not_home"},
        ])
        self.assertEqual([], result["published"])

    def test_every_invalid_or_non_home_phase_zero_replays_the_exact_prologue(self):
        for view in ("empty", "malformed", "cycle", "too_long", "not_home", "update_prompt"):
            for key in range(5):
                with self.subTest(view=view, key=key):
                    result = N64.emulate_key_sequence(self.bundle, [
                        {"key": key, "phase": 0, "view": view},
                        {"key": key, "phase": 2, "view": view},
                        {"key": key, "phase": 1, "view": view},
                    ])
                    self.assertEqual([{"type": 15, "key": key, "state": phase}
                                      for phase in (0, 2, 1)], result["published"])
                    self.assertEqual("GARMIN_HELD", result["final_local_states"][key])
                    # A Garmin-owned press is not ours to redraw for.
                    self.assertEqual([], result["queue_sends"])

    def test_reset_garbage_and_legacy_words_are_normalised_at_phase_zero(self):
        # 0x0000 reset, 0xFFFF erased, and the three legacy 13.76 encodings all
        # fail the complement check.  A press at a stable home must recover the
        # key rather than leaving it stuck.
        stale_words = (0x0000, 0xFFFF, N64.LEGACY_IDLE, N64.LEGACY_OWNED,
                       N64.LEGACY_PULSE, 0x1234)
        # Every GPIO down as well as none: the design no longer needs an "all
        # GPIOs released" guard around this cleanup, because phase zero rewrites
        # only this key's own ownership byte and can therefore never reach a
        # global latch or another key's in-progress sequence.  Pin that rather
        # than just asserting it.
        for stale in stale_words:
            for mask in (0, 0b11111):
                with self.subTest(stale=hex(stale), gpio_mask=bin(mask)):
                    result = N64.emulate_key_sequence(self.bundle, [
                        {"key": 2, "phase": 0, "gpio_mask": mask,
                         "initial_words": {2: stale}},
                        {"key": 2, "phase": 1, "gpio_mask": mask},
                    ])
                    self.assertEqual([], result["published"])
                    self.assertEqual("FLY_PULSE", result["final_local_states"][2])

    def test_normalising_one_key_never_disturbs_another_keys_sequence(self):
        # DOWN is mid-press and FlyOS-owned.  Pressing BACK, whose word is
        # garbage and gets normalised, must leave DOWN's latch alone.
        result = N64.emulate_key_sequence(self.bundle, [
            {"key": 3, "phase": 0},
            {"key": 2, "phase": 0, "gpio_mask": 0b01100, "initial_words": {2: 0x1234}},
            {"key": 3, "phase": 1, "gpio_mask": 0b00100},
        ])
        self.assertEqual([], result["published"])
        self.assertEqual("FLY_PULSE", result["final_local_states"][3])
        self.assertEqual("FLY_HELD", result["final_local_states"][2])

    def test_a_garbage_word_still_fails_open_when_the_view_is_not_home(self):
        result = N64.emulate_key_sequence(self.bundle, [
            {"key": 2, "phase": 0, "view": "not_home", "initial_words": {2: 0x1234}},
            {"key": 2, "phase": 1, "view": "not_home"},
        ])
        self.assertEqual([{"type": 15, "key": 2, "state": phase} for phase in (0, 1)],
                         result["published"])

    def test_queue_null_and_every_queue_result_leave_ownership_alone(self):
        for code in (0, 2, 3):
            with self.subTest(queue_result=code):
                result = N64.emulate_key_sequence(self.bundle, [
                    {"key": 1, "phase": 0, "queue_result": code},
                    {"key": 1, "phase": 1, "queue_result": code}])
                self.assertEqual([], result["published"])
                self.assertEqual("FLY_PULSE", result["final_local_states"][1])
        result = N64.emulate_key_sequence(self.bundle, [
            {"key": 1, "phase": 0, "queue_uninitialized": True},
            {"key": 1, "phase": 1, "queue_uninitialized": True}])
        self.assertEqual([], result["published"])
        self.assertEqual([], result["queue_sends"])
        self.assertEqual("FLY_PULSE", result["final_local_states"][1])

    def test_ownership_writes_only_ever_touch_the_local_byte(self):
        # Every write the key worker makes must be one byte at record +0x36.
        # The mode byte at +0x37 belongs to the system/detach subsystems.
        result = N64.emulate_key_sequence(self.bundle, [
            {"key": key, "phase": phase} for key in range(5) for phase in (0, 2, 1)])
        self.assertTrue(result["padding_writes"])
        for address, size, _value in result["padding_writes"]:
            self.assertEqual(1, size)
            self.assertIn(address, N64.KEY_PADS)

    def test_a_display_pulse_clear_only_moves_the_local_nibble(self):
        held = N64.pack_state(N64.FLY_PULSE, N64.SYSTEM_HOME)
        result = N64.emulate_display(self.bundle, key_words={0: held})
        self.assertTrue(result["eligible"])
        # local cleared to IDLE, LIGHT's system-mode nibble untouched.
        self.assertEqual(N64.pack_state(N64.IDLE, N64.SYSTEM_HOME),
                         result["key_statuses"][0])

    def test_every_display_write_to_a_key_record_is_one_local_byte(self):
        # Mirror of test_ownership_writes_only_ever_touch_the_local_byte for the
        # display path.  A two-byte write at +0x36 would reach the +0x37 mode
        # byte, which carries the system session (LIGHT) and the detach state
        # (START) and must stay out of this path's reach entirely.
        result = N64.emulate_display(
            self.bundle,
            key_words={key: N64.pack_state(N64.FLY_PULSE, N64.NORMAL) for key in range(5)})
        self.assertTrue(result["eligible"])
        self.assertEqual({"framebuffer", "stack", "key_padding"},
                         set(result["write_counts"]))
        # Five keys, each retiring its pulse with exactly one single-byte store.
        self.assertEqual(5, result["write_counts"]["key_padding"])
        for key in range(5):
            self.assertEqual(N64.pack_state(N64.IDLE, N64.NORMAL),
                             result["key_statuses"][key], key)

    def test_a_pulse_clear_loses_the_race_against_a_new_press(self):
        # The display hook retires PULSE -> IDLE while a key worker may be
        # latching a fresh press into the same byte.  The exclusive store must
        # fail and the compare-exchange give up, leaving the new owner intact.
        for key in range(5):
            for racer, expected in ((N64.state_byte(N64.FLY_HELD), "FLY_HELD"),
                                    (N64.state_byte(N64.GARMIN_HELD), "GARMIN_HELD")):
                with self.subTest(key=key, racer=expected):
                    race = N64.emulate_pulse_clear_race(self.bundle, key, racer)
                    self.assertTrue(race["injected_before_store"])
                    self.assertEqual(expected, race["final_local"])
                    self.assertEqual(racer, race["final_byte"])

    def test_an_unopposed_pulse_clear_still_retires_the_pulse(self):
        # Control for the race test: with no competing write the same code path
        # must succeed, so the assertion above is about the race and not about
        # clear_key_pulse being inert.
        race = N64.emulate_pulse_clear_race(self.bundle, 0,
                                            N64.state_byte(N64.FLY_PULSE))
        self.assertEqual("IDLE", race["final_local"])
        self.assertEqual(N64.pack_state(N64.IDLE, N64.NORMAL), race["final_word"])

    def test_a_late_phase_after_release_is_never_leaked_to_garmin(self):
        result = N64.emulate_key_sequence(self.bundle, [
            {"key": 3, "phase": 0}, {"key": 3, "phase": 1}, {"key": 3, "phase": 1}])
        self.assertEqual([], result["published"])

    def test_an_owned_release_keeps_its_latch_whatever_the_view_became(self):
        # The view can go non-home or unclassifiable during the release itself
        # -- one mutation is enough to make stable_view() disagree with itself.
        # The sequence is still FlyOS's, so it must end in a terminal owned
        # state, never IDLE: an IDLE key matches neither FLY_HELD nor FLY_PULSE
        # and would send the next phase straight to Garmin as an orphan release
        # with no matching press.
        for view in ("not_home", "empty", "malformed", "cycle", "too_long",
                     "root_mutation", "finder_mismatch", "update_prompt"):
            for key in range(5):
                with self.subTest(view=view, key=key):
                    result = N64.emulate_key_sequence(self.bundle, [
                        {"key": key, "phase": 0, "view": "valid"},
                        {"key": key, "phase": 1, "view": view},
                        {"key": key, "phase": 1, "view": view},
                        {"key": key, "phase": 4, "view": "valid"},
                    ])
                    self.assertEqual([], result["published"])
                    self.assertEqual("FLY_PULSE", result["final_local_states"][key])

    def test_an_owned_release_away_from_home_asks_for_no_redraw(self):
        result = N64.emulate_key_sequence(self.bundle, [
            {"key": 2, "phase": 0, "view": "valid"},
            {"key": 2, "phase": 1, "view": "not_home"},
        ])
        self.assertEqual([], result["published"])
        # One redraw for the press on home, none for the release away from it.
        self.assertEqual(1, len(result["queue_sends"]))

    def test_the_runtime_key_path_stays_inside_the_pinned_stack_ceiling(self):
        result = N64.emulate_key_sequence(self.bundle, [
            {"key": key, "phase": phase} for key in range(5) for phase in (0, 2, 4, 3, 1)])
        self.assertLessEqual(result["maximum_runtime_stack_bytes"], 384)


class UsbSequenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = N64.load_build(NEW_BUILD)

    def test_single_transition_reflects_a_real_emulated_display_flush(self):
        # usb_ms/eligible are read back from the actual n64_render capture
        # (see emulate_display), not declared -- a real regression in the
        # underlying display emulation would flip these.
        result = N64.emulate_usb_sequence(self.bundle, [{"from": 3, "to": 2, "view": "valid"}],
                                          initial_state=3)
        self.assertEqual(1, len(result["steps"]))
        self.assertEqual(0, result["steps"][0]["usb_ms"])
        self.assertTrue(result["steps"][0]["eligible"])

    def test_usb_ms_flag_reflects_mass_storage_states_three_and_four(self):
        for target_state in range(5):
            result = N64.emulate_usb_sequence(self.bundle, [{"from": 0, "to": target_state}])
            self.assertEqual(int(target_state in (3, 4)), result["steps"][0]["usb_ms"])

    def test_coherent_chain_is_accepted_and_recorded_in_order(self):
        result = N64.emulate_usb_sequence(self.bundle, [
            {"from": 0, "to": 3, "view": "valid"},
            {"from": 3, "to": 2, "view": "valid"},
        ])
        self.assertEqual([(0, 3), (3, 2)],
                         [(step["from"], step["to"]) for step in result["steps"]])

    def test_incoherent_chain_is_rejected(self):
        # step 1's "from" (9) does not match step 0's "to" (3): the sequence
        # does not describe one continuous device history and must be
        # rejected rather than silently recorded.
        with self.assertRaisesRegex(ValueError, "incoherent usb transition"):
            N64.emulate_usb_sequence(self.bundle, [{"from": 0, "to": 3}, {"from": 9, "to": 2}])

    def test_step_zero_from_must_match_declared_initial_state(self):
        with self.assertRaisesRegex(ValueError, "incoherent usb transition"):
            N64.emulate_usb_sequence(self.bundle, [{"from": 3, "to": 2}])  # default initial_state=0
        # Passing the matching initial_state explicitly is accepted.
        result = N64.emulate_usb_sequence(self.bundle, [{"from": 3, "to": 2}], initial_state=3)
        self.assertEqual(1, len(result["steps"]))

    def test_unknown_transition_field_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unknown usb transition field"):
            N64.emulate_usb_sequence(self.bundle, [{"from": 0, "to": 3, "queue_result": 0}])

    def test_empty_sequence_is_rejected(self):
        with self.assertRaises(ValueError):
            N64.emulate_usb_sequence(self.bundle, [])


if __name__ == "__main__":
    unittest.main()
