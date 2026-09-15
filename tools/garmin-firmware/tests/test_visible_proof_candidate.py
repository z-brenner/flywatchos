import hashlib
import sys
import unittest
from pathlib import Path


TOOL_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOL_DIR))

import build_visible_proof_candidate as proof  # noqa: E402


class VisibleProofCandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = Path(
            "artifacts/firmware/originals/Forerunner245_1370_GUPDATE.GCD"
        )
        if not source.exists():
            raise unittest.SkipTest("pinned official 13.70 package is unavailable")
        cls.source = source.read_bytes()

    def test_fixed_candidate_has_exact_expected_diff_and_hash(self):
        source_hash_before = hashlib.sha256(self.source).hexdigest()
        candidate, report = proof.build_candidate(self.source)

        self.assertEqual(source_hash_before, proof.SOURCE_SHA256)
        self.assertEqual(hashlib.sha256(self.source).hexdigest(), source_hash_before)
        self.assertEqual(
            report["output"]["sha256"],
            "b6e61518890d8082d96baf9bd89dcb131317f40060136093c9250e343a8ab4ba",
        )
        self.assertEqual(
            report["output"]["main_stream_sha256"],
            "f6224af2283bca90ad17cea11366c92ed7b00be567da633f15b50d2432d2346f",
        )
        self.assertEqual(report["patch"]["raw_file_offset"], "0x448d1a")
        self.assertEqual(report["patch"]["changed_byte_count"], 16)
        self.assertEqual(
            [item["raw_offset"] for item in report["patch"]["changed_bytes"]],
            [f"0x{offset:x}" for offset in range(0x448D1A, 0x448D2A)],
        )
        self.assertEqual(candidate[0x448D1A:0x448D2A], proof.REPLACEMENT)
        self.assertTrue(report["checks"]["confirmed_application_full_image_checks_pass"])
        self.assertEqual(report["checks"]["main_stream_byte_sum_mod_256"], 0)
        self.assertTrue(
            report["display_evidence"]["source_context_checks"][
                "about_field_cluster_unique"
            ]
        )
        self.assertTrue(
            report["display_evidence"]["source_context_checks"][
                "system_menu_cluster_unique"
            ]
        )


if __name__ == "__main__":
    unittest.main()
