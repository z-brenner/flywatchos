import hashlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TOOLS = ROOT / "tools" / "garmin-firmware"
sys.path.insert(0, str(TOOLS))

import emulate_overlay_payload as emulator


class OverlayEmulationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload = (
            ROOT
            / "flyos"
            / "target"
            / "fr245_1370_overlay"
            / "build"
            / "overlay.bin"
        ).read_bytes()

    def test_payload_and_render_are_byte_exact(self):
        self.assertEqual(
            hashlib.sha256(self.payload).hexdigest(),
            "62ea46c67c565f571789d1437de318de785d90a2fef0a79d702b6d2ba6b3dee1",
        )
        result = emulator.emulate(self.payload, initialized=True)
        self.assertEqual(
            result["draw_region_sha256"],
            "8a49cb9767e998ca3834b7be2a68b3a5b1495aa59288be120f3f019241a5fbb8",
        )

    def test_initialized_display_draws_bounded_text_and_dispatches(self):
        result = emulator.emulate(self.payload, initialized=True)
        self.assertEqual(result["dirty_calls"], [[50, 102, 140, 22]])
        self.assertEqual(result["dispatch_calls"], [[emulator.FRAMEBUFFER, 0]])
        self.assertEqual(result["outside_draw_region_changed_bytes"], 0)
        self.assertGreater(result["fly_foreground_zero_bytes"], 80)
        self.assertGreater(result["text_foreground_zero_bytes"], 300)
        self.assertGreater(result["background_ff_bytes"], 0)
        self.assertTrue(result["plate_border_complete"])
        self.assertTrue(result["callee_saved_registers_preserved"])
        self.assertTrue(result["stack_pointer_restored"])

    def test_uninitialized_display_skips_draw_but_preserves_dispatch(self):
        result = emulator.emulate(self.payload, initialized=False)
        self.assertEqual(result["dirty_calls"], [])
        self.assertEqual(result["dispatch_calls"], [[emulator.FRAMEBUFFER, 0]])
        self.assertEqual(result["framebuffer_changed_bytes"], 0)
        self.assertTrue(result["callee_saved_registers_preserved"])
        self.assertTrue(result["stack_pointer_restored"])


if __name__ == "__main__":
    unittest.main()
