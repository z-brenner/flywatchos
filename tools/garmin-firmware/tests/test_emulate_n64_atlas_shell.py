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
OLD_EMULATOR = ROOT / "tools" / "garmin-firmware" / "emulate_neural_specimen_n64_controls.py"
SPEC = importlib.util.spec_from_file_location("flyos_n64_atlas_shell_emulator", EMULATOR)
N64 = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = N64
SPEC.loader.exec_module(N64)
OLD_SPEC = importlib.util.spec_from_file_location("flyos_n64_controls_emulator_ref", OLD_EMULATOR)
OLD_N64 = importlib.util.module_from_spec(OLD_SPEC)
sys.modules[OLD_SPEC.name] = OLD_N64
OLD_SPEC.loader.exec_module(OLD_N64)


class ScaffoldTests(unittest.TestCase):
    def test_scaffold_starts_from_exact_controls_sources(self):
        for name in ("hook.S", "overlay.c", "renderer.c", "brain64_packed.c"):
            self.assertEqual((OLD_TARGET / name).read_bytes(), (TARGET / name).read_bytes())


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


class TargetBuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sandbox = tempfile.TemporaryDirectory(prefix="flyos-n64-atlas-shell-focused-")
        cls.build = pathlib.Path(cls.sandbox.name) / "build"
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
             str(TARGET / "build.ps1"), "-BuildRoot", str(cls.build)],
            cwd=ROOT, capture_output=True, text=True,
        )
        if completed.returncode:
            raise RuntimeError(completed.stdout + completed.stderr)
        cls.bundle = N64.load_build(cls.build)

    @classmethod
    def tearDownClass(cls):
        cls.sandbox.cleanup()

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

    def test_segments_are_byte_identical_to_the_old_controls_build(self):
        old_bundle = OLD_N64.load_build(OLD_TARGET / "build")
        self.assertEqual(old_bundle.primary, self.bundle.primary)
        self.assertEqual(old_bundle.secondary, self.bundle.secondary)
        self.assertEqual(old_bundle.hook, self.bundle.hook)
        self.assertEqual(old_bundle.keyhook, self.bundle.keyhook)
        self.assertEqual(old_bundle.manifest["stack_audit"]["stack_bound_bytes"],
                         self.bundle.manifest["stack_audit"]["stack_bound_bytes"])


class DisplayByteIdentityTests(unittest.TestCase):
    """Task 3-5 have not landed yet: emulate_display must behave exactly like
    the old controls target's emulate() for every fixture it still shares."""

    @classmethod
    def setUpClass(cls):
        cls.bundle = N64.load_build(TARGET / "build")
        cls.old_bundle = OLD_N64.load_build(OLD_TARGET / "build")

    def test_display_framebuffers_match_the_old_target_for_every_fixture(self):
        fixtures = [{}, {"pressed_mask": 1}, {"pressed_mask": 2}, {"pressed_mask": 8},
                    {"pressed_mask": 16}, {"usb_state": 3}, {"usb_state": 4},
                    {"battery_bits": 0x42C80000}, {"forced_activation": (56, 700)},
                    {"key_statuses": {1: N64.KEY_OWNED}}, {"key_statuses": {3: N64.KEY_PULSE}}]
        for fixture in fixtures:
            with self.subTest(fixture=fixture):
                new_result = N64.emulate_display(self.bundle, **fixture)
                old_result = OLD_N64.emulate(self.old_bundle, **fixture)
                self.assertEqual(old_result["framebuffer_sha256"], new_result["framebuffer_sha256"])
                self.assertEqual(old_result["dirty_calls"], new_result["dirty_calls"])
                self.assertEqual(old_result["eligible"], new_result["eligible"])

    def test_view_fixtures_match_the_old_home_fixtures(self):
        for view in ("empty", "malformed", "cycle", "too_long", "not_home", "hidden_match",
                     "multiple", "finder_mismatch", "false_first_visible", "root_mutation"):
            with self.subTest(view=view):
                new_result = N64.emulate_display(self.bundle, view=view)
                old_result = OLD_N64.emulate(self.old_bundle, home=view)
                self.assertEqual(old_result["framebuffer_sha256"], new_result["framebuffer_sha256"])
                self.assertEqual(old_result["eligible"], new_result["eligible"])


class KeySequenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = N64.load_build(TARGET / "build")

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
        cls.bundle = N64.load_build(TARGET / "build")

    def test_bare_transition_has_no_hook_site_yet_and_no_queued_redraw(self):
        result = N64.emulate_usb_sequence(self.bundle, [{"from": 3, "to": 2, "view": "valid"}])
        self.assertFalse(result["hook_sites_present"])
        self.assertEqual(1, len(result["steps"]))
        self.assertEqual([], result["steps"][0]["queue_sends"])
        self.assertEqual(0, result["steps"][0]["usb_ms"])
        self.assertTrue(result["steps"][0]["eligible"])

    def test_usb_ms_flag_reflects_mass_storage_states_three_and_four(self):
        for target_state in range(5):
            result = N64.emulate_usb_sequence(self.bundle, [{"from": 0, "to": target_state}])
            self.assertEqual(int(target_state in (3, 4)), result["steps"][0]["usb_ms"])

    def test_multiple_transitions_are_recorded_in_order(self):
        result = N64.emulate_usb_sequence(self.bundle, [
            {"from": 0, "to": 3, "view": "valid"},
            {"from": 3, "to": 2, "view": "valid"},
        ])
        self.assertEqual([(0, 3), (3, 2)],
                         [(step["from"], step["to"]) for step in result["steps"]])

    def test_empty_sequence_is_rejected(self):
        with self.assertRaises(ValueError):
            N64.emulate_usb_sequence(self.bundle, [])


if __name__ == "__main__":
    unittest.main()
