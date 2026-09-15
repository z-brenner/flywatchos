import sys
import unittest
from pathlib import Path


TOOL_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOL_DIR))

import full_image_validator as validator  # noqa: E402
import gcd_inspect as inspect  # noqa: E402
import gcd_payload_mutation_lab as mutation  # noqa: E402


class FullImageValidatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = Path(
            "artifacts/firmware/originals/Forerunner245_1370_GUPDATE.GCD"
        )
        if not source.exists():
            raise unittest.SkipTest("pinned official 13.70 package is unavailable")
        cls.source = source.read_bytes()

    def test_official_full_image_passes_confirmed_checks(self):
        report = validator.validate_bytes(self.source, "official.gcd")
        self.assertTrue(report["confirmed_full_image_checks_pass"])
        self.assertFalse(report["main_stream"]["gdelta01"])
        self.assertEqual(report["main_stream"]["byte_sum_mod_256"], 0)

    def test_unrepaired_payload_mutation_fails_inner_sum(self):
        gcd = inspect.parse_gcd(self.source)
        stream = next(x for x in inspect.collect_streams(gcd) if x.record_id == 0x02BD)
        changed, _ = mutation.replace_decoded_stream_byte(
            self.source, stream, mutation.TARGET_OFFSET + 4, ord("0"), ord("1")
        )
        report = validator.validate_bytes(changed, "unrepaired.gcd")
        self.assertTrue(report["outer_gcd"]["all_prefix_sums_zero_mod_256"])
        self.assertEqual(report["main_stream"]["byte_sum_mod_256"], 1)
        self.assertFalse(report["confirmed_full_image_checks_pass"])

    def test_repaired_lab_package_passes_confirmed_checks(self):
        package = Path(
            "artifacts/firmware/mutation-lab/Forerunner245_1370_payload-lab.GCD"
        )
        if not package.exists():
            self.skipTest("repaired offline package is unavailable")
        report = validator.validate_bytes(package.read_bytes(), package.name)
        self.assertTrue(report["confirmed_full_image_checks_pass"])
        self.assertEqual(
            report["input_sha256"],
            "d0708d6ca4c2ed0b8c7ea3fecf8798d33d1d060550c2eea846ae5b1ae43270cf",
        )


if __name__ == "__main__":
    unittest.main()
