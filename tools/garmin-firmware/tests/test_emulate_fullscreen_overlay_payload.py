import hashlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TOOLS = ROOT / "tools" / "garmin-firmware"
sys.path.insert(0, str(TOOLS))

import emulate_fullscreen_overlay_payload as emulator


class FullscreenOverlayEmulationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload = (
            ROOT
            / "flyos"
            / "target"
            / "fr245_1370_fullscreen_overlay"
            / "build"
            / "overlay.bin"
        ).read_bytes()

    def test_payload_fits_audited_allocation(self):
        self.assertGreater(len(self.payload), 0)
        self.assertLessEqual(len(self.payload), 0x400)
        self.assertEqual(len(self.payload), 974)
        self.assertEqual(
            hashlib.sha256(self.payload).hexdigest(),
            "358d71190321f7dd9d51de8ac3c913e370b0fc23a25e7541d072d2ac83941ffb",
        )

    def test_all_pixels_are_owned_and_deterministic(self):
        first = emulator.emulate(self.payload, initialized=True, fill=0x2A)
        second = emulator.emulate(self.payload, initialized=True, fill=0xA5)
        self.assertEqual(first["framebuffer"], second["framebuffer"])
        self.assertEqual(
            first["framebuffer_sha256"],
            "15f644334fa872b0d44dec173b74e302c862eedbbc47c6c8ba285d2ba4881722",
        )
        self.assertEqual(first["input_sentinel_remaining"], 0)
        self.assertEqual(second["input_sentinel_remaining"], 0)
        self.assertEqual(len(first["framebuffer"]), 57_600)
        self.assertTrue(first["all_pixels_monochrome"])
        self.assertGreater(first["foreground_zero_bytes"], 2_000)
        self.assertGreater(first["background_ff_bytes"], 40_000)

    def test_full_screen_dirty_rect_abi_and_bounds(self):
        result = emulator.emulate(self.payload, initialized=True)
        self.assertEqual(result["dirty_calls"], [[0, 0, 240, 240]])
        self.assertEqual(result["dispatch_calls"], [[emulator.FRAMEBUFFER, 0]])
        self.assertTrue(result["guard_before_unchanged"])
        self.assertTrue(result["guard_after_unchanged"])
        self.assertTrue(result["callee_saved_registers_preserved"])
        self.assertTrue(result["stack_pointer_restored"])
        self.assertEqual(
            result["peripheral_reads"],
            [
                [emulator.GPIOA_PDIR, 4],
                [emulator.GPIOC_PDIR, 4],
                [emulator.GPIOD_PDIR, 4],
            ],
        )
        self.assertEqual(result["peripheral_writes"], [])

    def test_each_active_low_button_changes_only_its_marker(self):
        released = emulator.emulate(self.payload, initialized=True, pressed_mask=0)
        hashes = set()
        for key in range(5):
            pressed = emulator.emulate(
                self.payload, initialized=True, pressed_mask=1 << key
            )
            hashes.add(pressed["framebuffer_sha256"])
            differences = [
                index
                for index, (before, after) in enumerate(
                    zip(released["framebuffer"], pressed["framebuffer"])
                )
                if before != after
            ]
            self.assertGreater(len(differences), 0)
            left = 42 + key * 36
            self.assertTrue(
                all(
                    left <= index % 240 < left + 12
                    and 214 <= index // 240 < 226
                    for index in differences
                )
            )
            self.assertEqual(pressed["peripheral_writes"], [])
        self.assertEqual(len(hashes), 5)

    def test_uninitialized_display_skips_repaint_but_dispatches(self):
        result = emulator.emulate(self.payload, initialized=False, fill=0x2A)
        self.assertEqual(result["dirty_calls"], [])
        self.assertEqual(result["dispatch_calls"], [[emulator.FRAMEBUFFER, 0]])
        self.assertEqual(result["framebuffer"], bytes([0x2A]) * 57_600)
        self.assertTrue(result["guard_before_unchanged"])
        self.assertTrue(result["guard_after_unchanged"])
        self.assertTrue(result["callee_saved_registers_preserved"])
        self.assertTrue(result["stack_pointer_restored"])
        self.assertEqual(result["peripheral_reads"], [])
        self.assertEqual(result["peripheral_writes"], [])


if __name__ == "__main__":
    unittest.main()
