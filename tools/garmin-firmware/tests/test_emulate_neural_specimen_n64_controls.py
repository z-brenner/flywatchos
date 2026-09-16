import importlib.util
import json
import pathlib
import re
import struct
import subprocess
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[3]
TARGET = ROOT / "flyos" / "target" / "fr245_1370_neural_specimen_n64_controls"
EMULATOR = ROOT / "tools" / "garmin-firmware" / "emulate_neural_specimen_n64_controls.py"
RUNTIME = ROOT / "artifacts" / "firmware" / "analysis" / "fr245-1370-runtime-state.json"
BUTTON_DOC = ROOT / "docs" / "button-overlay-input.md"
RTC_DOC = ROOT / "docs" / "neural-overlay-placement.md"
SPEC = importlib.util.spec_from_file_location("flyos_n64_controls_emulator", EMULATOR)
N64 = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = N64
SPEC.loader.exec_module(N64)

LETTERS = (
    0x5BEA, 0x6BAE, 0x3923, 0x6B6E, 0x79A7, 0x49A7, 0x3B63,
    0x5BED, 0x7497, 0x2A49, 0x5BAD, 0x7924, 0x5BFD, 0x5FFD,
    0x2B6A, 0x49AE, 0x3F6A, 0x5BAE, 0x62A3, 0x2497, 0x7B6D,
    0x2B6D, 0x5FED, 0x5AAD, 0x24AD, 0x788F,
)
DIGITS = (0x7B6F, 0x74B2, 0x788E, 0x628E, 0x13ED,
          0x63A7, 0x7BE3, 0x248F, 0x7BEF, 0x63EF)


def glyph(character):
    if "A" <= character <= "Z":
        return LETTERS[ord(character) - ord("A")]
    if "0" <= character <= "9":
        return DIGITS[ord(character) - ord("0")]
    return {"-": 0x01C0, "/": 0x4889, ">": 0x4454, " ": 0}[character]


class NeuralSpecimenN64ControlsTargetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sandbox = tempfile.TemporaryDirectory(prefix="flyos-n64-controls-focused-")
        cls.build = pathlib.Path(cls.sandbox.name) / "build"
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
             str(TARGET / "build.ps1"), "-BuildRoot", str(cls.build)],
            cwd=ROOT, capture_output=True, text=True,
        )
        if completed.returncode:
            raise RuntimeError(completed.stdout + completed.stderr)
        cls.bundle = N64.load_build(cls.build)
        cls._frames = {}

    @classmethod
    def tearDownClass(cls):
        cls.sandbox.cleanup()

    @classmethod
    def frame(cls, **kwargs):
        key = json.dumps(kwargs, sort_keys=True, separators=(",", ":"))
        if key not in cls._frames:
            cls._frames[key] = N64.emulate(cls.bundle, **kwargs)
        return cls._frames[key]

    def assert_text(self, framebuffer, x, y, value):
        for index, character in enumerate(value):
            bits = glyph(character)
            for row in range(5):
                for column in range(3):
                    source_column = 2 - column
                    expected = 0x3F if bits & (1 << (row * 3 + source_column)) else 0
                    self.assertEqual(expected,
                                     framebuffer[(y + row) * 240 + x + index * 4 + column],
                                     (value, character, row, column))
                self.assertEqual(0, framebuffer[(y + row) * 240 + x + index * 4 + 3])

    @staticmethod
    def cell(framebuffer, neuron):
        row = neuron >> 3
        bases = (93, 93, 89, 89, 89, 89, 93, 93)
        gaps = (7, 7, 8, 8, 8, 8, 7, 7)
        x, y = bases[row] + (neuron & 7) * gaps[row], 76 + row * 9
        return bytes(framebuffer[(y + dy) * 240 + x + dx]
                     for dy in range(6) for dx in range(6))

    def test_exact_layout_hooks_stack_and_original_key_prologue(self):
        manifest = self.bundle.manifest
        self.assertEqual("flyos.fr245.n64-controls-target.v1", manifest["schema"])
        self.assertEqual({"hook", "keyhook", "primary", "secondary"}, set(manifest["segments"]))
        self.assertEqual((N64.HOOK, 4),
                         (manifest["segments"]["hook"]["start"], manifest["segments"]["hook"]["size"]))
        self.assertEqual((N64.KEY_HOOK, 6),
                         (manifest["segments"]["keyhook"]["start"], manifest["segments"]["keyhook"]["size"]))
        primary = manifest["segments"]["primary"]["size"]
        secondary = manifest["segments"]["secondary"]["size"]
        self.assertLessEqual(primary, 1023)
        self.assertLessEqual(secondary, 2048)
        self.assertLessEqual(primary + secondary, 3071)
        self.assertEqual(0x1F63FF, manifest["repair_byte"])
        self.assertEqual(384, manifest["stack_audit"]["stack_bound_bytes"])
        self.assertFalse(manifest["packaging_allowed"])
        self.assertEqual(N64.PRIMARY, N64.decode_hook(self.bundle.hook))
        self.assertEqual(manifest["symbols"]["flyos_key_event"]["address"],
                         N64.decode_key_hook(self.bundle.keyhook))
        image = N64.IMAGE.read_bytes()
        offset = N64.KEY_HOOK - 0x3000
        self.assertEqual(bytes.fromhex("30b5c0ebc002"), image[offset:offset + 6])
        owners = {item["function"] for item in manifest["stack_audit"]["external_transfers"]}
        self.assertLessEqual(owners, {"n64_overlay_then_flush", "flyos_key_event",
                                      "flyos_key_pass", "request_redraw"})

    def test_build_is_clean_freestanding_and_uses_only_reviewed_sections(self):
        N64.assert_build_clean(self.bundle.build, self.bundle.manifest)
        self.assertFalse((self.bundle.build / "oracle" / "tests").exists())
        self.assertEqual(1, len(list((self.bundle.build / "oracle" / "retained").glob("*"))))
        listing = (self.bundle.build /
                   "fr245-1370-neural-specimen-n64-controls.disassembly.txt").read_text().lower()
        for token in ("vadd", "vsub", "vmul", "vdiv", "vcvt", "__aeabi_f"):
            self.assertNotIn(token, listing)
        sections, _ = N64.read_elf(self.bundle.build / N64.ELF_NAME)
        self.assertTrue(".forbidden" not in sections or sections[".forbidden"]["size"] == 0)

    def test_home_gate_mutations_back_and_null_fail_closed(self):
        for home in ("empty", "malformed", "cycle", "too_long", "not_home", "hidden_match",
                     "finder_mismatch", "false_first_visible", "root_mutation"):
            with self.subTest(home=home):
                result = self.frame(home=home, fill=0x6D)
                self.assertFalse(result["eligible"])
                self.assertTrue(result["framebuffer_unchanged"])
                self.assertEqual([], result["dirty_calls"])
        for home in ("valid", "multiple", "malformed"):
            result = self.frame(home=home, pressed_mask=4, fill=0x37)
            self.assertFalse(result["eligible"])
            self.assertTrue(result["framebuffer_unchanged"])
            self.assertEqual([[N64.GPIOD, 4]], result["data_reads"])
        null = self.frame(framebuffer_null=True)
        self.assertEqual([], null["data_reads"])
        self.assertEqual([[0, 0]], null["dispatch_calls"])

    def test_display_call_abi_memory_confinement_and_exact_reads(self):
        result = self.frame(home="multiple")
        self.assertEqual([[0, 0, 240, 240]], result["dirty_calls"])
        self.assertEqual([[N64.FRAMEBUFFER, 0]], result["dispatch_calls"])
        self.assertEqual([N64.DIRTY, N64.DISPATCH], result["external_targets"])
        for invariant in ("callee_saved_preserved", "sp_restored",
                          "guard_before_unchanged", "guard_after_unchanged"):
            self.assertTrue(result[invariant])
        self.assertLessEqual(result["maximum_runtime_stack_bytes"], 384)
        self.assertEqual([], result["outside_writes"])
        fixed = {N64.VIEW_ROOT, N64.GPIOD, N64.GPIOA, N64.GPIOC, N64.BATTERY,
                 N64.USB_MS, N64.RTC_SECONDS, N64.RTC_PRESCALER, *N64.KEY_PADS}
        nodes = {0x20001000, 0x20001100}
        for address, size in result["data_reads"]:
            expected_size = 1 if address == N64.USB_MS else 2 if address in N64.KEY_PADS else 4
            self.assertEqual(expected_size, size)
            self.assertTrue(address in fixed or any(address == node + offset for node in nodes
                                                    for offset in (4, 8, 0x50)))

    def test_round_geometry_is_inside_strict_radius_100_for_every_ui_fixture(self):
        fixtures = [
            {}, {"battery_bits": 0x42C80000}, {"battery_bits": 0x7FC00000},
            {"usb_state": 3}, {"forced_activation": (56, 700)},
            *({"pressed_mask": mask} for mask in (1, 2, 8, 16, 1 | 2 | 8 | 16)),
            {"key_statuses": {1: N64.KEY_OWNED}}, {"key_statuses": {3: N64.KEY_PULSE}},
        ]
        for fixture in fixtures:
            with self.subTest(fixture=fixture):
                result = self.frame(**fixture)
                foreground = [(index % 240, index // 240)
                              for index, value in enumerate(result["framebuffer"]) if value]
                self.assertTrue(result["safe_radius"])
                self.assertLessEqual(max((x - 120) ** 2 + (y - 120) ** 2
                                         for x, y in foreground), 10000)

    def test_exact_header_status_battery_and_centered_button_footers(self):
        base = self.frame()
        self.assert_text(base["framebuffer"], 110, 22, "FLYOS")
        self.assert_text(base["framebuffer"], 99, 32, "SPECIMEN 64")
        self.assert_text(base["framebuffer"], 64, 185, "STATE")
        self.assert_text(base["framebuffer"], 112, 185, "B")
        self.assert_text(base["framebuffer"], 98, 204, " PRESS>KEYS")
        expected = {1: " LIGHT>LUX ", 2: "START>BURST", 8: " DOWN>CALM ", 16: "  UP>PULSE "}
        for mask, footer in expected.items():
            self.assert_text(self.frame(pressed_mask=mask)["framebuffer"], 98, 204, footer)
        for value in (0, 9, 10, 73, 99, 100):
            bits = struct.unpack("<I", struct.pack("<f", float(value)))[0]
            result = self.frame(battery_bits=bits)
            self.assertEqual((4, value), (result["valid_mask"], result["battery"]))
            self.assert_text(result["framebuffer"], 120, 185, str(value))
        invalid_bits = struct.unpack("<I", struct.pack("<f", float("nan")))[0]
        invalid = self.frame(battery_bits=invalid_bits)
        self.assertEqual((0, 0), (invalid["valid_mask"], invalid["battery"]))
        self.assert_text(invalid["framebuffer"], 120, 185, "--")

    def test_four_buttons_have_distinct_visuals_and_direct_amber_input_cells(self):
        baseline = self.frame()
        mapping = {1: 0, 2: 1, 8: 3, 16: 4}
        hashes = set()
        for mask, neuron in mapping.items():
            result = self.frame(pressed_mask=mask)
            hashes.add(result["framebuffer_sha256"])
            self.assertEqual(mask, result["buttons"])
            self.assertGreaterEqual(result["activation"][neuron], 512)
            self.assertEqual(bytes([0x38]) * 36, self.cell(result["framebuffer"], neuron))
            for other in set(mapping.values()) - {neuron}:
                self.assertEqual(self.cell(baseline["framebuffer"], other),
                                 self.cell(result["framebuffer"], other))
            self.assertEqual(64, result["verified_neuron_cells"])
        self.assertEqual(4, len(hashes))

    def test_owned_and_pulse_padding_drive_one_frame_without_gpio_hold(self):
        for key, mask in ((1, 2), (3, 8), (4, 16)):
            owned = self.frame(key_statuses={key: N64.KEY_OWNED})
            self.assertEqual(mask, owned["buttons"])
            self.assertEqual(N64.KEY_OWNED, owned["key_statuses"][key])
            pulse = self.frame(key_statuses={key: N64.KEY_PULSE})
            self.assertEqual(mask, pulse["buttons"])
            self.assertEqual(N64.KEY_IDLE, pulse["key_statuses"][key])
            self.assertEqual(2, pulse["write_counts"]["key_padding"])

    def test_owned_start_down_up_sequences_never_reach_garmin_publisher(self):
        for key in (1, 3, 4):
            result = N64.emulate_key_sequence(self.bundle, [
                {"key": key, "state": 0}, {"key": key, "state": 2},
                {"key": key, "state": 3}, {"key": key, "state": 1},
            ])
            self.assertEqual([], result["published"])
            self.assertEqual([N64.KEY_OWNED, N64.KEY_OWNED, N64.KEY_OWNED, N64.KEY_PULSE],
                             [case["statuses"][key] for case in result["cases"]])
            self.assertEqual(2, len(result["queue_sends"]))
            for call in result["queue_sends"]:
                self.assertEqual({"queue": 0x20002000, "node": 0x20001000,
                                  "event": 0x50, "front": 1, "timeout": 0}, call)
            self.assertEqual([[N64.KEY_PADS[key], 2, N64.KEY_IDLE],
                              [N64.KEY_PADS[key], 2, N64.KEY_OWNED],
                              [N64.KEY_PADS[key], 2, N64.KEY_PULSE]], result["padding_writes"])
            self.assertLessEqual(result["maximum_runtime_stack_bytes"], 384)

    def test_light_back_and_unowned_release_replay_original_publisher(self):
        for key in (0, 2):
            result = N64.emulate_key_sequence(self.bundle, [
                {"key": key, "state": 0}, {"key": key, "state": 2}, {"key": key, "state": 1},
            ])
            self.assertEqual([{"type": 15, "key": key, "state": state}
                              for state in (0, 2, 1)], result["published"])
            self.assertEqual([], result["queue_sends"])
            self.assertEqual([], result["padding_writes"])
        release = N64.emulate_key_sequence(self.bundle, [{"key": 1, "state": 1}])
        self.assertEqual([{"type": 15, "key": 1, "state": 1}], release["published"])
        self.assertEqual(N64.KEY_IDLE, release["final_statuses"][1])

    def test_controlled_press_fails_closed_before_publisher_on_every_escape(self):
        fixtures = ([{"home": home} for home in
                     ("empty", "malformed", "cycle", "too_long", "not_home", "hidden_match",
                      "finder_mismatch", "false_first_visible", "root_mutation")]
                    + [{"usb": 3}, {"usb": 4}, {"back_held": True}])
        for key in (1, 3, 4):
            for fixture in fixtures:
                event = {"key": key, "state": 0, **fixture}
                result = N64.emulate_key_sequence(self.bundle, [event])
                self.assertEqual([{"type": 15, "key": key, "state": 0}], result["published"])
                self.assertEqual([], result["queue_sends"])
                self.assertEqual(N64.KEY_IDLE, result["final_statuses"][key])

    def test_phase_zero_clears_stale_owned_and_pulse_before_every_failed_gate(self):
        gates = ({"home": "not_home"}, {"usb": 3}, {"usb": 4}, {"back_held": True})
        for key in (1, 3, 4):
            for stale in (N64.KEY_OWNED, N64.KEY_PULSE):
                for gate in gates:
                    event = {"key": key, "state": 0, "initial_statuses": {key: stale}, **gate}
                    result = N64.emulate_key_sequence(self.bundle, [event])
                    self.assertEqual([{"type": 15, "key": key, "state": 0}], result["published"])
                    self.assertEqual(N64.KEY_IDLE, result["final_statuses"][key])
                    self.assertIn([N64.KEY_PADS[key], 2, N64.KEY_IDLE], result["padding_writes"])

    def test_sequence_ownership_is_latched_at_press(self):
        starts_outside = N64.emulate_key_sequence(self.bundle, [
            {"key": 1, "state": 0, "home": "not_home"},
            {"key": 1, "state": 1, "home": "valid"},
        ])
        self.assertEqual([{"type": 15, "key": 1, "state": 0},
                          {"type": 15, "key": 1, "state": 1}], starts_outside["published"])
        starts_home = N64.emulate_key_sequence(self.bundle, [
            {"key": 1, "state": 0, "home": "valid"},
            {"key": 1, "state": 2, "home": "not_home"},
            {"key": 1, "state": 1, "home": "not_home"},
        ])
        self.assertEqual([], starts_home["published"])
        self.assertEqual(N64.KEY_IDLE, starts_home["final_statuses"][1])
        self.assertEqual(1, len(starts_home["queue_sends"]))

    def test_nonblocking_redraw_queue_failure_does_not_change_ownership(self):
        uninitialized = N64.emulate_key_sequence(self.bundle, [
            {"key": 3, "state": 0, "queue_uninitialized": True},
            {"key": 3, "state": 1, "queue_uninitialized": True},
        ])
        self.assertEqual([], uninitialized["published"])
        self.assertEqual([], uninitialized["queue_sends"])
        self.assertEqual(N64.KEY_PULSE, uninitialized["final_statuses"][3])
        full = N64.emulate_key_sequence(self.bundle, [
            {"key": 4, "state": 0, "queue_result": 7},
            {"key": 4, "state": 1, "queue_result": 7},
        ])
        self.assertEqual([], full["published"])
        self.assertEqual(2, len(full["queue_sends"]))
        self.assertEqual(N64.KEY_PULSE, full["final_statuses"][4])

    def test_rtc_usb_and_io_addresses_remain_evidence_bound(self):
        stable = self.frame(rtc_samples=[(7, 0x8123, 7)])
        retry = self.frame(rtc_samples=[(7, 9, 8), (8, 0xFFFF, 8)])
        failed = self.frame(rtc_samples=[(7, 9, 8), (8, 10, 9)])
        self.assertEqual(((7 << 15) | 0x123, 3), (stable["tick"], stable["rtc_reads"]))
        self.assertEqual(((8 << 15) | 0x7FFF, 6), (retry["tick"], retry["rtc_reads"]))
        self.assertEqual((0xFFFFFFFF, 6), (failed["tick"], failed["rtc_reads"]))
        for state in range(7):
            self.assertEqual(int(state in (3, 4)), self.frame(usb_state=state)["usb_ms"])
        runtime = json.loads(RUNTIME.read_text())
        overlay = (TARGET / "overlay.c").read_text().lower()
        signals = runtime["signals"]
        evidenced = [signals["back_button_pass_through"]["source"]["pinned_addresses"][0],
                     signals["battery_percent"]["source"]["pinned_addresses"][0],
                     signals["usb_mass_storage"]["source"]["pinned_addresses"][0],
                     signals["watch_face_active"]["source"]["list_root"]]
        evidenced += re.findall(r"0x400ff0(?:10|90|d0)|0x(?:00000800|00000400|00000002|00100000|00400000)",
                                BUTTON_DOC.read_text(encoding="utf-8").lower())
        evidenced += re.findall(r"0x4003d00[04]", RTC_DOC.read_text(encoding="utf-8").lower())
        for value in set(evidenced) - {"0x4003d004"}:
            self.assertIn("2u" if value == "0x00000002" else value, overlay)

    def test_host_oracle_palette_and_all_64_cells_match(self):
        result = self.frame(pressed_mask=2, battery_bits=0x42C80000, usb_state=4)
        oracle = N64.host_oracle(self.bundle.build, result["tick"], 2, 1, 100, 1)
        self.assertEqual(oracle["brain"], result["brain"])
        self.assertEqual(oracle["target_framebuffer"], result["framebuffer"])
        self.assertEqual(64, N64.verify_cells(result["framebuffer"], result["activation"]))
        saturated = self.frame(forced_activation=(56, 700))
        self.assertTrue(saturated["all_pixels_reviewed_palette"])
        self.assertEqual({0, 12, 42, 51, 56, 63}, set(saturated["framebuffer"]))
        self.assertEqual(bytes([0x38]) * 36, self.cell(saturated["framebuffer"], 56))

    def test_display_and_key_fixtures_execute_every_cross_segment_branch(self):
        expected = {tuple(pair) for pair in self.bundle.manifest["stack_audit"]["cross_segment_branches"]}
        seen = set()
        for fixture in ({}, {"battery_bits": 0x42C80000},
                        *({"pressed_mask": bit} for bit in (1, 2, 8, 16)),
                        {"key_statuses": {1: N64.KEY_PULSE}}):
            seen.update(map(tuple, self.frame(**fixture)["executed_cross_segment_branches"]))
        for events in ([{"key": 1, "state": 0}, {"key": 1, "state": 1}],
                       [{"key": 0, "state": 0}],
                       [{"key": 1, "state": 0, "home": "not_home"}]):
            result = N64.emulate_key_sequence(self.bundle, events)
            seen.update(map(tuple, result["executed_cross_segment_branches"]))
        self.assertEqual(expected, seen)

    def test_evidence_names_are_controls_specific_and_cover_keyhook(self):
        with tempfile.TemporaryDirectory(prefix="flyos-n64-controls-evidence-") as directory:
            output = pathlib.Path(directory)
            manifest = N64.publish_evidence(self.bundle.build, output)
            self.assertEqual("flyos.fr245.n64-controls-evidence.v1", manifest["schema"])
            report_path = output / f"{N64.ARTIFACT_PREFIX}-emulator-report.json"
            self.assertTrue(report_path.exists())
            self.assertTrue((output / f"{N64.ARTIFACT_PREFIX}-evidence-manifest.json").exists())
            self.assertIn("keyhook.bin", manifest["build_files"])
            report = json.loads(report_path.read_text())
            self.assertEqual("flyos.fr245.n64-controls-emulation.v1", report["schema"])
            self.assertEqual({"1", "3", "4"}, set(report["controls"]))
            for name, item in manifest["files"].items():
                self.assertEqual(item["sha256"], N64.sha256((output / name).read_bytes()))

    def test_allocation_policy_mutation_fails_closed(self):
        original = N64.ALLOCATION
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "allocation.json"
            data = json.loads(original.read_text())
            data["third_allocation_used"] = True
            path.write_text(json.dumps(data))
            N64.ALLOCATION = path
            try:
                with self.assertRaisesRegex(ValueError, "canonical"):
                    N64.evidence_gate()
            finally:
                N64.ALLOCATION = original


if __name__ == "__main__":
    unittest.main()
