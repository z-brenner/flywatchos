import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
TOOLS = ROOT / "tools" / "garmin-firmware"
sys.path.insert(0, str(TOOLS))

import build_overlay_candidate  # noqa: E402
import fullscreen_version_strategy as strategy  # noqa: E402
import gcd_inspect  # noqa: E402


class FullscreenVersionStrategyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.official = (
            ROOT / "artifacts/firmware/originals/Forerunner245_1370_GUPDATE.GCD"
        ).read_bytes()
        build = ROOT / "flyos/target/fr245_1370_fullscreen_overlay/build"
        cls.hook = (build / "hook.bin").read_bytes()
        cls.payload = (build / "overlay.bin").read_bytes()
        cls.xrefs = (
            ROOT / "artifacts/firmware/analysis/code-cave-overlay-xrefs-1370.txt"
        ).read_text(encoding="utf-8")

    @staticmethod
    def stream(data, record_id):
        return next(
            stream
            for stream in gcd_inspect.collect_streams(gcd_inspect.parse_gcd(data))
            if stream.record_id == record_id
        )

    def test_overlay_is_coherent_1372_and_uses_normal_forward_path(self):
        overlay, report = strategy.build_overlay(
            self.official, self.hook, self.payload, self.xrefs
        )
        main = self.stream(overlay, 0x02BD)
        self.assertEqual(main.software_version, 1372)
        self.assertEqual(int.from_bytes(main.decoded[0x22C:0x22E], "little"), 1372)
        self.assertEqual(main.erase_flag, 0)
        self.assertEqual(
            main.decoded[
                build_overlay_candidate.OVERLAY_OFFSET :
                build_overlay_candidate.OVERLAY_OFFSET + len(self.payload)
            ],
            self.payload,
        )
        self.assertTrue(all(report["checks"].values()))

    def test_restore_is_coherent_1373_and_removes_all_custom_code(self):
        restore, report = strategy.build_restore(self.official)
        official_main = self.stream(self.official, 0x02BD)
        main = self.stream(restore, 0x02BD)
        self.assertEqual(main.software_version, 1373)
        self.assertEqual(int.from_bytes(main.decoded[0x22C:0x22E], "little"), 1373)
        self.assertEqual(main.erase_flag, 0)
        self.assertEqual(
            main.decoded[
                build_overlay_candidate.HOOK_OFFSET : build_overlay_candidate.HOOK_OFFSET + 4
            ],
            official_main.decoded[
                build_overlay_candidate.HOOK_OFFSET : build_overlay_candidate.HOOK_OFFSET + 4
            ],
        )
        self.assertEqual(
            main.decoded[
                build_overlay_candidate.OVERLAY_OFFSET :
                build_overlay_candidate.OVERLAY_OFFSET + build_overlay_candidate.OVERLAY_ALLOCATION
            ],
            official_main.decoded[
                build_overlay_candidate.OVERLAY_OFFSET :
                build_overlay_candidate.OVERLAY_OFFSET + build_overlay_candidate.OVERLAY_ALLOCATION
            ],
        )
        self.assertTrue(all(report["checks"].values()))

    def test_exact_verifier_accepts_only_pinned_pair(self):
        overlay, _ = strategy.build_overlay(
            self.official, self.hook, self.payload, self.xrefs
        )
        restore, _ = strategy.build_restore(self.official)
        report = strategy.verify_exact(
            self.official, overlay, restore, self.hook, self.payload, self.xrefs
        )
        self.assertEqual(report["verdict"], "PASS")

        damaged = bytearray(overlay)
        damaged[0x10B86] ^= 1
        report = strategy.verify_exact(
            self.official,
            bytes(damaged),
            restore,
            self.hook,
            self.payload,
            self.xrefs,
        )
        self.assertEqual(report["verdict"], "FAIL")
        self.assertFalse(report["checks"]["overlay_byte_exact_reconstruction"])

    def test_rejects_stale_or_changed_payload(self):
        damaged = bytearray(self.payload)
        damaged[-1] ^= 1
        with self.assertRaisesRegex(ValueError, "pinned button-enabled"):
            strategy.build_overlay(
                self.official, self.hook, bytes(damaged), self.xrefs
            )


if __name__ == "__main__":
    unittest.main()
