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
PINNED_PRIMARY = 944
PINNED_SECONDARY = 1928

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
        # Holding BACK is the Garmin escape chord, so this overlay passes that
        # frame straight through and BACK's own callout is not reachable until
        # five-key ownership lands; the other four are pressed for real here.
        for mask, text in EXPECTED_BUTTON_LABELS.items():
            result = N64.emulate_display(self.bundle, pressed_mask=mask)
            if mask == 4:
                self.assertFalse(result["eligible"])
                self.assertTrue(result["framebuffer_unchanged"])
                continue
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

    def test_owned_start_down_up_sequences_never_reach_garmin_publisher(self):
        for key in (1, 3, 4):
            result = N64.emulate_key_sequence(self.bundle, [
                {"key": key, "phase": 0, "tick_ms": 5000},
                {"key": key, "phase": 2, "tick_ms": 5200},
                {"key": key, "phase": 3, "tick_ms": 5400},
                {"key": key, "phase": 1, "tick_ms": 5600},
            ])
            self.assertEqual([], result["published"])
            self.assertEqual([N64.KEY_OWNED, N64.KEY_OWNED, N64.KEY_OWNED, N64.KEY_PULSE],
                             [case["statuses"][key] for case in result["cases"]])
            self.assertLessEqual(result["maximum_runtime_stack_bytes"], 384)

    def test_light_and_back_replay_original_publisher_with_new_field_names(self):
        for key in (0, 2):
            result = N64.emulate_key_sequence(self.bundle, [
                {"key": key, "phase": 0}, {"key": key, "phase": 2}, {"key": key, "phase": 1},
            ])
            self.assertEqual([{"type": 15, "key": key, "state": phase}
                              for phase in (0, 2, 1)], result["published"])
            self.assertEqual([], result["queue_sends"])

    def test_gpio_mask_back_bit_forces_garmin_ownership_like_old_back_held(self):
        BACK_BIT = 1 << 2
        result = N64.emulate_key_sequence(self.bundle, [
            {"key": 3, "phase": 0, "gpio_mask": BACK_BIT},
        ])
        self.assertEqual([{"type": 15, "key": 3, "state": 0}], result["published"])
        self.assertEqual([], result["queue_sends"])
        self.assertEqual(N64.KEY_IDLE, result["final_statuses"][3])

    def test_gpio_mask_other_bits_do_not_block_ownership(self):
        LIGHT_START_DOWN_UP = (1 << 0) | (1 << 1) | (1 << 3) | (1 << 4)
        result = N64.emulate_key_sequence(self.bundle, [
            {"key": 4, "phase": 0, "gpio_mask": LIGHT_START_DOWN_UP},
            {"key": 4, "phase": 1, "gpio_mask": LIGHT_START_DOWN_UP},
        ])
        self.assertEqual([], result["published"])
        self.assertEqual(N64.KEY_PULSE, result["final_statuses"][4])

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
            result = N64.emulate_key_sequence(self.bundle, [{"key": 3, "phase": 0, "view": view}])
            self.assertEqual([{"type": 15, "key": 3, "state": 0}], result["published"])
            self.assertEqual(N64.KEY_IDLE, result["final_statuses"][3])

    def test_queue_result_codes_do_not_change_ownership(self):
        for code in (0, 2, 3):
            result = N64.emulate_key_sequence(self.bundle, [
                {"key": 1, "phase": 0, "queue_result": code},
                {"key": 1, "phase": 1, "queue_result": code},
            ])
            self.assertEqual([], result["published"])
            self.assertEqual(N64.KEY_PULSE, result["final_statuses"][1])


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
