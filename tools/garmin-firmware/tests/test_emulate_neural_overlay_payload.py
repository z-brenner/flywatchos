"""Execute the real linked shared-C target, including bounded peripheral sampling."""

import importlib.util
from dataclasses import replace
import hashlib
import json
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TOOLS = ROOT / "tools" / "garmin-firmware"
BUILD = ROOT / "flyos" / "target" / "fr245_1370_neural_overlay" / "build"
sys.path.insert(0, str(TOOLS))


class NeuralOverlayEmulationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.find_spec("emulate_neural_overlay_payload")
        cls.emulator = None
        if spec is not None:
            import emulate_neural_overlay_payload
            cls.emulator = emulate_neural_overlay_payload

    def module(self):
        self.assertIsNotNone(self.emulator, "the neural target emulator is required")
        return self.emulator

    def run_target(self, **kwargs):
        emulator = self.module()
        self.assertTrue((BUILD / "primary.bin").is_file(), "split payload must be built")
        return emulator.emulate(emulator.load_build(BUILD), **kwargs)

    def test_split_layout_and_stack_bound(self):
        emulator = self.module()
        bundle = emulator.load_build(BUILD)
        self.assertGreater(len(bundle.primary), 0)
        self.assertLessEqual(len(bundle.primary), 0x3FF)
        self.assertGreater(len(bundle.secondary), 0)
        self.assertLessEqual(len(bundle.secondary), 0x800)
        self.assertEqual(emulator.decode_hook(bundle.hook), 0x1F6000)
        self.assertLessEqual(bundle.manifest["stack_bound_bytes"], 384)
        self.assertFalse(bundle.manifest["packaging_allowed"])

    def test_all_pixels_owned_and_abi_preserved(self):
        result = self.run_target(fill=0x2A)
        self.module().validate_result(result)
        self.assertEqual(result["framebuffer_bytes_written"], 57600)
        self.assertEqual(result["input_sentinel_remaining"], 0)
        self.assertEqual(result["dirty_calls"], [[0, 0, 240, 240]])
        self.assertEqual(result["dispatch_calls"], [[self.emulator.FRAMEBUFFER, 0]])
        self.assertEqual(result["outside_writes"], [])
        self.assertEqual(result["peripheral_writes"], [])
        self.assertTrue(result["callee_saved_registers_preserved"])
        self.assertTrue(result["stack_pointer_restored"])
        self.assertTrue(result["guard_before_unchanged"])
        self.assertTrue(result["guard_after_unchanged"])

    def test_each_guard_false_does_not_access_framebuffer_or_peripherals(self):
        for options in ({"framebuffer_null": True}, {"backend": 0}, {"startup": 0}, {"startup": 2}):
            with self.subTest(**options):
                result = self.run_target(**options)
                self.emulator.validate_result(result)
                self.assertEqual(result["framebuffer_accesses"], 0)
                self.assertEqual(result["peripheral_reads"], [])
                self.assertEqual(result["dirty_calls"], [])
                self.assertEqual(result["framebuffer"], bytes([0x2A]) * 57600)

    def test_released_and_each_single_active_low_button(self):
        hashes = set()
        for mask in (0, 1, 2, 4, 8, 16):
            with self.subTest(mask=mask):
                result = self.run_target(pressed_mask=mask)
                self.emulator.validate_result(result)
                self.assertEqual(result["captured_buttons"], mask)
                self.assertEqual(result["peripheral_reads"][:3], [[0x400FF010, 4], [0x400FF090, 4], [0x400FF0D0, 4]])
                hashes.add(result["framebuffer_sha256"])
        self.assertEqual(len(hashes), 6)

    def test_deterministic_fixture_and_tick_evolution(self):
        first = self.run_target(pressed_mask=3, rtc_samples=[(123, 0xA005, 123)])
        repeat = self.run_target(pressed_mask=3, rtc_samples=[(123, 0xA005, 123)], fill=0xA5)
        later = self.run_target(pressed_mask=3, rtc_samples=[(123, 0xA006, 123)])
        self.assertEqual(first["framebuffer"], repeat["framebuffer"])
        self.assertNotEqual(first["framebuffer"], later["framebuffer"])
        self.assertNotEqual(first["activation"], later["activation"])
        self.assertEqual(first["captured_tick"], (123 << 15) | 0x2005)

    def test_rtc_rollover_retries_once_and_second_mismatch_terminates(self):
        for samples, expected_tick in (
            ([(100, 0xFFFF, 101), (101, 3, 101)], (101 << 15) | 3),
            ([(100, 0xFFFF, 101), (101, 0x8004, 102)], 0xFFFFFFFF),
        ):
            with self.subTest(samples=samples):
                result = self.run_target(rtc_samples=samples)
                self.emulator.validate_result(result)
                self.assertEqual(result["captured_tick"], expected_tick)
                self.assertEqual(result["peripheral_reads"][3:], [[0x4003D000, 4], [0x4003D004, 4], [0x4003D000, 4]] * 2)
                self.assertLess(result["instruction_count"], self.emulator.INSTRUCTION_CAP)

    def test_all_32_cells_match_captured_shared_c_activations(self):
        result = self.run_target(pressed_mask=31)
        self.assertEqual(len(result["activation"]), 32)
        self.assertEqual(result["verified_neuron_cells"], 32)
        self.assertEqual(len(set(map(tuple, result["neuron_points"]))), 32)
        self.assertTrue(all(0 <= x <= 231 and 0 <= y <= 233 for x, y in result["neuron_points"]))

    def test_target_matches_host_compiled_shared_c_oracle(self):
        report = ROOT / "artifacts/firmware/analysis/neural-overlay-emulation-1370.json"
        evidence = json.loads(report.read_text())["host_shared_c_oracle"]
        retained = [report, BUILD / "SHA256SUMS.txt",
                    report.parent / "neural-overlay-SHA256SUMS.txt"]
        retained += [ROOT / name for name in evidence.get("artifacts", {})]
        # Also catches the legacy shared oracle names before the isolation fix.
        retained += [BUILD / name for name in ("host-oracle.c", "host-oracle.exe", "host-oracle.bin")
                     if (BUILD / name).exists()]
        before = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in retained}
        result = self.run_target(pressed_mask=3, rtc_samples=[(123, 0xA005, 123)])
        oracle = self.module().host_oracle(BUILD, result["captured_tick"], 3)
        self.assertEqual(result["framebuffer"], oracle["framebuffer"])
        self.assertEqual(result["activation"], oracle["activation"])
        self.assertEqual(before, {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in retained})
        executable = ROOT / oracle["executable_path"]
        pe = executable.read_bytes()
        pe_offset = struct.unpack_from("<I", pe, 0x3C)[0]
        self.assertEqual(struct.unpack_from("<I", pe, pe_offset + 8)[0], 0)
        self.assertIn("-Wl,--no-insert-timestamp", oracle["command"])
        # Tests use a different namespace even for the report's exact fixture.
        same_fixture = self.module().host_oracle(BUILD, 0x003DA005, 0)
        self.assertTrue(set(same_fixture["artifacts"]).isdisjoint(evidence.get("artifacts", {})))
        self.assertEqual(before, {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in retained})
        # Removing only test artifacts forces a fresh compile without retained writes.
        for name in oracle["artifacts"]:
            path = (ROOT / name).resolve()
            self.assertTrue(path.is_relative_to((BUILD / "oracle/tests").resolve()))
            path.unlink()
        rebuilt = self.module().host_oracle(BUILD, result["captured_tick"], 3)
        self.assertEqual(oracle["artifacts"], rebuilt["artifacts"])

    def test_mismatched_placement_hash_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "Placement evidence SHA256 mismatch"):
            self.module().placement_gate(expected_sha256="0" * 64)

    def test_wrong_hook_length_or_instruction_is_rejected(self):
        for hook in (b"", b"\x00\xbf", b"\x00\xbf\x00\xbf"):
            with self.subTest(hook=hook), self.assertRaisesRegex(ValueError, "four-byte Thumb BL"):
                self.module().decode_hook(hook)

    def test_target_write_to_framebuffer_canary_is_rejected(self):
        emulator = self.module()
        bundle = emulator.load_build(BUILD)
        # subs r0,#4; str r1,[r0] writes immediately before the supplied frame.
        corrupted = replace(bundle, primary=b"\x04\x38\x01\x60" + bundle.primary[4:])
        with self.assertRaisesRegex(ValueError, "write outside framebuffer/stack"):
            emulator.emulate(corrupted)

    def test_unapproved_gpio_register_read_is_rejected(self):
        emulator = self.module()
        bundle = emulator.load_build(BUILD)
        # ldr r0,[pc,#0]; ldr r0,[r0]; .word 0x400ff014 (not an approved PDIR).
        corrupted = replace(bundle, primary=b"\x00\x48\x00\x68\x14\xf0\x0f\x40" + bundle.primary[8:])
        with self.assertRaisesRegex(ValueError, "Unapproved peripheral read"):
            emulator.emulate(corrupted)


if __name__ == "__main__":
    unittest.main()
