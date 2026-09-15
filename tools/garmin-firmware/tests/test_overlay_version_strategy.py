import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
TOOLS = ROOT / "tools" / "garmin-firmware"
sys.path.insert(0, str(TOOLS))

import gcd_inspect  # noqa: E402
import overlay_version_strategy as strategy  # noqa: E402


class OverlayVersionStrategyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.official = (
            ROOT / "artifacts/firmware/originals/Forerunner245_1370_GUPDATE.GCD"
        ).read_bytes()
        build = ROOT / "flyos/target/fr245_1370_overlay/build"
        cls.hook = (build / "hook.bin").read_bytes()
        cls.payload = (build / "overlay.bin").read_bytes()
        cls.xrefs = (
            ROOT / "artifacts/firmware/analysis/code-cave-overlay-xrefs-1370.txt"
        ).read_text(encoding="utf-8")

    @staticmethod
    def stream(data, record_id):
        return next(
            s
            for s in gcd_inspect.collect_streams(gcd_inspect.parse_gcd(data))
            if s.record_id == record_id
        )

    def test_force_restore_wraps_exact_official_payloads(self):
        candidate, report = strategy.build_force_restore(self.official)
        self.assertEqual(self.stream(candidate, 0x02BD).decoded, self.stream(self.official, 0x02BD).decoded)
        self.assertEqual(self.stream(candidate, 0x0505).decoded, self.stream(self.official, 0x0505).decoded)
        self.assertEqual(self.stream(candidate, 0x02BD).erase_flag, 1)
        self.assertTrue(all(report["checks"].values()))
        self.assertEqual(report["raw_changed_offsets"], ["0xa152", "0x4e229e"])

    def test_force_overlay_keeps_versions_coherent_and_pins_payload(self):
        candidate, report = strategy.build_force_overlay(
            self.official, self.hook, self.payload, self.xrefs
        )
        main = self.stream(candidate, 0x02BD)
        self.assertEqual(main.software_version, 1370)
        self.assertEqual(int.from_bytes(main.decoded[0x22C:0x22E], "little"), 1370)
        self.assertEqual(main.erase_flag, 1)
        self.assertEqual(
            main.decoded[strategy.build_overlay_candidate.OVERLAY_OFFSET:
                         strategy.build_overlay_candidate.OVERLAY_OFFSET + len(self.payload)],
            self.payload,
        )
        self.assertTrue(all(report["checks"].values()))

    def test_exact_verifier_rejects_one_byte_tamper(self):
        restore, _ = strategy.build_force_restore(self.official)
        overlay, _ = strategy.build_force_overlay(
            self.official, self.hook, self.payload, self.xrefs
        )
        if "TO_BE_FILLED" in (
            strategy.FORCE_RESTORE_SHA256,
            strategy.FORCE_OVERLAY_SHA256,
            strategy.FORCE_OVERLAY_MAIN_SHA256,
        ):
            self.skipTest("exact hashes not pinned yet")
        report = strategy.verify_exact(
            self.official, restore, overlay, self.hook, self.payload, self.xrefs
        )
        self.assertEqual(report["verdict"], "PASS")
        damaged = bytearray(overlay)
        damaged[0x448D1A] ^= 1
        report = strategy.verify_exact(
            self.official, restore, bytes(damaged), self.hook, self.payload, self.xrefs
        )
        self.assertEqual(report["verdict"], "FAIL")
        self.assertFalse(report["checks"]["force_overlay_byte_exact_reconstruction"])

    def test_forward_restore_carries_official_runtime_identity(self):
        candidate, report = strategy.build_forward_restore(self.official)
        main = self.stream(candidate, 0x02BD)
        official_main = self.stream(self.official, 0x02BD)
        self.assertEqual(main.software_version, 1372)
        self.assertEqual(int.from_bytes(main.decoded[0x22C:0x22E], "little"), 1372)
        self.assertEqual(main.decoded[0x370F06:0x370F08], official_main.decoded[0x370F06:0x370F08])
        self.assertEqual(main.decoded[0x370F34:0x370F3C], b" V13.70\x00")
        self.assertTrue(all(report["checks"].values()))

    def test_forward_overlay_and_restore_have_strict_exact_profiles(self):
        restore, _ = strategy.build_forward_restore(self.official)
        overlay, _ = strategy.build_forward_overlay(
            self.official, self.hook, self.payload, self.xrefs
        )
        report = strategy.verify_forward_exact(
            self.official, restore, overlay, self.hook, self.payload, self.xrefs
        )
        self.assertEqual(report["verdict"], "PASS")
        self.assertTrue(all(report["checks"].values()))

    def test_forward_overlay_is_1371_and_uses_no_field0b_hypothesis(self):
        candidate, report = strategy.build_forward_overlay(
            self.official, self.hook, self.payload, self.xrefs
        )
        main = self.stream(candidate, 0x02BD)
        self.assertEqual(main.software_version, 1371)
        self.assertEqual(int.from_bytes(main.decoded[0x22C:0x22E], "little"), 1371)
        self.assertEqual(main.erase_flag, 0)
        self.assertTrue(all(report["checks"].values()))


if __name__ == "__main__":
    unittest.main()
