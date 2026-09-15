import hashlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TOOLS = ROOT / "tools" / "garmin-firmware"
sys.path.insert(0, str(TOOLS))

import build_overlay_candidate as builder
import full_image_validator
import gcd_inspect


class OverlayCandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (
            ROOT
            / "artifacts"
            / "firmware"
            / "originals"
            / "Forerunner245_1370_GUPDATE.GCD"
        ).read_bytes()
        build = ROOT / "flyos" / "target" / "fr245_1370_overlay" / "build"
        cls.hook = (build / "hook.bin").read_bytes()
        cls.payload = (build / "overlay.bin").read_bytes()
        cls.xrefs = (
            ROOT
            / "artifacts"
            / "firmware"
            / "analysis"
            / "code-cave-overlay-xrefs-1370.txt"
        ).read_text(encoding="utf-8")

    def test_linked_hook_targets_overlay_entry(self):
        self.assertEqual(
            builder.decode_thumb_bl(builder.HOOK_VA, self.hook),
            builder.OVERLAY_VA,
        )

    def test_candidate_changes_only_hook_cave_and_outer_checkpoint(self):
        candidate, report = builder.build_candidate(
            self.source, self.hook, self.payload, self.xrefs
        )
        original_streams = gcd_inspect.collect_streams(gcd_inspect.parse_gcd(self.source))
        candidate_streams = gcd_inspect.collect_streams(gcd_inspect.parse_gcd(candidate))
        original_helper = next(s for s in original_streams if s.record_id == 0x0505)
        candidate_helper = next(s for s in candidate_streams if s.record_id == 0x0505)
        candidate_main = next(s for s in candidate_streams if s.record_id == 0x02BD)

        self.assertEqual(original_helper.decoded, candidate_helper.decoded)
        self.assertEqual(sum(candidate_main.decoded) & 0xff, 0)
        self.assertTrue(
            full_image_validator.validate_bytes(candidate)[
                "confirmed_full_image_checks_pass"
            ]
        )
        self.assertEqual(report["patch"]["hook"]["target_va"], "0x001f6000")
        self.assertEqual(report["patch"]["payload"]["length"], len(self.payload))
        self.assertTrue(report["checks"]["helper_stream_byte_identical"])
        self.assertTrue(report["checks"]["descriptor_records_byte_identical"])
        self.assertTrue(report["checks"]["changed_main_bytes_confined"])
        self.assertEqual(
            report["output"]["sha256"], hashlib.sha256(candidate).hexdigest()
        )

    def test_rejects_cave_with_static_references(self):
        with self.assertRaisesRegex(ValueError, "references"):
            builder.build_candidate(
                self.source,
                self.hook,
                self.payload,
                self.xrefs.replace("reference_count=0", "reference_count=1"),
            )

    def test_rejects_wrong_source(self):
        damaged = bytearray(self.source)
        damaged[0] ^= 1
        with self.assertRaisesRegex(ValueError, "pinned official"):
            builder.build_candidate(bytes(damaged), self.hook, self.payload, self.xrefs)


if __name__ == "__main__":
    unittest.main()
