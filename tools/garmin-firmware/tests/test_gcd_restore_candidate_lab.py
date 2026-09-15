import hashlib
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

import gcd_inspect  # noqa: E402
import gcd_restore_candidate_lab  # noqa: E402


class GcdRestoreCandidateLabTests(unittest.TestCase):
    def test_builds_exact_payload_only_restore_hypothesis(self):
        source = Path("artifacts/firmware/originals/Forerunner245_1370_GUPDATE.GCD")
        if not source.exists():
            self.skipTest("pinned official package unavailable")
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "candidate.gcd"
            report = gcd_restore_candidate_lab.build_candidate(source, output)
            official = gcd_inspect.parse_gcd(source.read_bytes())
            candidate = gcd_inspect.parse_gcd(output.read_bytes())
            official_streams = gcd_inspect.collect_streams(official)
            candidate_streams = gcd_inspect.collect_streams(candidate)
            official_helper = next(x for x in official_streams if x.record_id == 0x0505)
            candidate_helper = next(x for x in candidate_streams if x.record_id == 0x0505)
            official_main = next(x for x in official_streams if x.record_id == 0x02BD)
            candidate_main = next(x for x in candidate_streams if x.record_id == 0x02BD)
            output_hash = hashlib.sha256(output.read_bytes()).hexdigest()

        self.assertEqual(candidate_helper.decoded, official_helper.decoded)
        self.assertEqual(candidate_helper.fields, official_helper.fields)
        self.assertEqual(candidate_main.fields, official_main.fields)
        self.assertEqual(candidate_main.decoded[0x22C:0x22E], b"\x59\x05")
        self.assertEqual(candidate_main.decoded[0x43EAA4:0x43EAB4], b"FLY LIVES 2ALIVE")
        self.assertEqual(sum(candidate_main.decoded) & 0xFF, 0)
        self.assertTrue(all(x["valid"] for x in gcd_inspect._checkpoint_results(candidate)))
        self.assertEqual(report["changed_decoded_offsets"], ["0x22c", "0x43eaa4..0x43eab3", "0x4d7fff"])
        self.assertEqual(report["output_sha256"], output_hash)

    def test_can_match_only_main_descriptor_to_13_69(self):
        source = Path("artifacts/firmware/originals/Forerunner245_1370_GUPDATE.GCD")
        if not source.exists():
            self.skipTest("pinned official package unavailable")
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "candidate.gcd"
            report = gcd_restore_candidate_lab.build_candidate(
                source, output, match_main_descriptor=True
            )
            official = gcd_inspect.parse_gcd(source.read_bytes())
            candidate = gcd_inspect.parse_gcd(output.read_bytes())
            official_helper = next(x for x in gcd_inspect.collect_streams(official) if x.record_id == 0x0505)
            candidate_helper = next(x for x in gcd_inspect.collect_streams(candidate) if x.record_id == 0x0505)
            candidate_main = next(x for x in gcd_inspect.collect_streams(candidate) if x.record_id == 0x02BD)

        self.assertEqual(candidate_helper.decoded, official_helper.decoded)
        self.assertEqual(candidate_helper.fields, official_helper.fields)
        self.assertEqual(candidate_main.software_version, 1369)
        self.assertEqual(candidate_main.decoded[0x22C:0x22E], b"\x59\x05")
        self.assertEqual(report["main_descriptor_software_version"], 1369)
        self.assertEqual(report["main_descriptor_raw_offset"], "0xa160")
        self.assertFalse(any("paired with a 13.69 main header" in x for x in report["limitations"]))
        self.assertTrue(all(x["valid"] for x in gcd_inspect._checkpoint_results(candidate)))


if __name__ == "__main__":
    unittest.main()
