import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
TOOLS = ROOT / "tools" / "garmin-firmware"
sys.path.insert(0, str(TOOLS))

import fr245_button_input as buttons


class Fr245ButtonInputTests(unittest.TestCase):
    def test_all_released_is_zero(self):
        self.assertEqual(buttons.decode_snapshot(0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF), 0)

    def test_each_active_low_input_has_its_own_bit(self):
        released = {
            buttons.GPIOA_PDIR: 0xFFFFFFFF,
            buttons.GPIOC_PDIR: 0xFFFFFFFF,
            buttons.GPIOD_PDIR: 0xFFFFFFFF,
        }
        for index, address, mask in buttons.BUTTONS:
            sample = dict(released)
            sample[address] &= ~mask
            self.assertEqual(
                buttons.decode_snapshot(
                    sample[buttons.GPIOA_PDIR],
                    sample[buttons.GPIOC_PDIR],
                    sample[buttons.GPIOD_PDIR],
                ),
                1 << index,
            )

    def test_combined_buttons(self):
        self.assertEqual(
            buttons.decode_snapshot(
                0xFFFFFFFF & ~(1 << 20) & ~(1 << 22),
                0xFFFFFFFF & ~(1 << 11),
                0xFFFFFFFF,
            ),
            0b11001,
        )

    def test_read_snapshot_reads_only_three_pdir_words_once(self):
        reads = []
        values = {
            buttons.GPIOA_PDIR: 0xFFFFFFFF,
            buttons.GPIOC_PDIR: 0xFFFFFFFF,
            buttons.GPIOD_PDIR: 0xFFFFFFFF & ~(1 << 1),
        }

        def read32(address):
            reads.append(address)
            return values[address]

        self.assertEqual(buttons.read_snapshot(read32), 1 << 2)
        self.assertEqual(
            reads,
            [buttons.GPIOA_PDIR, buttons.GPIOC_PDIR, buttons.GPIOD_PDIR],
        )


if __name__ == "__main__":
    unittest.main()

