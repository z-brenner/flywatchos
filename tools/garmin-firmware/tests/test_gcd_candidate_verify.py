import hashlib
import struct
import tempfile
import unittest
from pathlib import Path


import sys


ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

import gcd_candidate_verify  # noqa: E402
import gcd_mutation_lab  # noqa: E402


def record(record_id: int, body: bytes) -> bytes:
    return struct.pack("<HH", record_id, len(body)) + body


def descriptor(record_id: int, payload: bytes) -> bytes:
    field_types = bytes((0x0B, 0x00, 0x0A, 0x00, 0x0A, 0x10,
                         0x15, 0x20, 0x09, 0x10, 0x0D, 0x10,
                         0x03, 0x50))
    values = struct.pack("<BBHIHH", 0, 0, record_id, len(payload), 0x0C04, 1370)
    return record(0x0006, field_types) + record(0x0007, values) + record(record_id, payload)


def package(helper: bytes, main: bytes) -> bytes:
    data = b"GARMIN" + struct.pack("<H", 100)
    data += record(0x0001, b"\x00")
    data += descriptor(0x0505, helper)
    data += descriptor(0x02BD, main)
    data += record(0x0001, b"\x00") + record(0xFFFF, b"")
    return gcd_mutation_lab.recompute_checkpoints(data)


class GcdCandidateVerifyTests(unittest.TestCase):
    def write_pair(self, root: Path, official: bytes, candidate: bytes):
        official_path = root / "official.gcd"
        candidate_path = root / "candidate.gcd"
        official_path.write_bytes(official)
        candidate_path.write_bytes(candidate)
        return official_path, candidate_path

    def test_accepts_only_sum_preserving_main_stream_changes(self):
        official = package(b"\x01\xff", b"\x10\x20\xd0")
        candidate = package(b"\x01\xff", b"\x11\x20\xcf")
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            official_path, candidate_path = self.write_pair(root, official, candidate)
            report = gcd_candidate_verify.verify_packages(
                official_path,
                candidate_path,
                expected_official_sha256=hashlib.sha256(official).hexdigest(),
            )

        self.assertEqual(report["visible_gate_result"], "PASS")
        self.assertTrue(report["gates"]["helper_0x0505_byte_identical"])
        self.assertTrue(report["gates"]["changes_only_in_0x02bd_payload"])
        self.assertTrue(report["gates"]["main_stream_sum_mod_256_zero"])
        self.assertEqual(report["changed_byte_count"], 2)
        self.assertEqual(
            [item["decoded_stream_offset"] for item in report["changed_bytes"]],
            ["0x0", "0x2"],
        )
        self.assertEqual(report["restore_artifact"]["sha256"], hashlib.sha256(official).hexdigest())

    def test_rejects_a_changed_helper_even_when_its_sum_is_preserved(self):
        official = package(b"\x01\xff", b"\x10\x20\xd0")
        candidate = package(b"\x02\xfe", b"\x11\x20\xcf")
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            official_path, candidate_path = self.write_pair(root, official, candidate)
            report = gcd_candidate_verify.verify_packages(
                official_path,
                candidate_path,
                expected_official_sha256=hashlib.sha256(official).hexdigest(),
            )

        self.assertEqual(report["visible_gate_result"], "FAIL")
        self.assertFalse(report["gates"]["helper_0x0505_byte_identical"])
        self.assertFalse(report["gates"]["changes_only_in_0x02bd_payload"])

    def test_rejects_a_nonzero_main_stream_checksum(self):
        official = package(b"\x01\xff", b"\x10\x20\xd0")
        candidate = bytearray(official)
        parsed = gcd_candidate_verify.gcd_inspect.parse_gcd(official)
        main_record = next(item for item in parsed.records if item.record_id == 0x02BD)
        candidate[main_record.offset + 4] ^= 1
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            official_path, candidate_path = self.write_pair(root, official, bytes(candidate))
            report = gcd_candidate_verify.verify_packages(
                official_path,
                candidate_path,
                expected_official_sha256=hashlib.sha256(official).hexdigest(),
            )

        self.assertEqual(report["visible_gate_result"], "FAIL")
        self.assertFalse(report["gates"]["main_stream_sum_mod_256_zero"])
        self.assertFalse(report["gates"]["outer_checkpoints_valid"])

    def test_exact_visible_proof_profile_accepts_only_pinned_candidate(self):
        official_path = Path(
            "artifacts/firmware/originals/Forerunner245_1370_GUPDATE.GCD"
        )
        candidate_path = Path(
            "artifacts/firmware/quarantine/"
            "Forerunner245_1370_fly-visible.gcd.analysis-only.DO_NOT_INSTALL"
        )
        if not official_path.exists() or not candidate_path.exists():
            self.skipTest("pinned visible-proof artifacts are unavailable")
        report = gcd_candidate_verify.verify_packages(
            official_path,
            candidate_path,
            profile=gcd_candidate_verify.VISIBLE_PROOF_PROFILE,
        )
        self.assertEqual(report["visible_gate_result"], "PASS")
        self.assertTrue(report["gates"]["profile_exact_match"])
        self.assertTrue(all(report["profile"]["checks"].values()))

    def test_exact_visible_proof_profile_rejects_another_valid_main_patch(self):
        official_path = Path(
            "artifacts/firmware/originals/Forerunner245_1370_GUPDATE.GCD"
        )
        candidate_path = Path(
            "artifacts/firmware/mutation-lab/Forerunner245_1370_payload-lab.GCD"
        )
        if not official_path.exists() or not candidate_path.exists():
            self.skipTest("pinned firmware-lab artifacts are unavailable")
        report = gcd_candidate_verify.verify_packages(
            official_path,
            candidate_path,
            profile=gcd_candidate_verify.VISIBLE_PROOF_PROFILE,
        )
        self.assertEqual(report["visible_gate_result"], "FAIL")
        self.assertFalse(report["gates"]["profile_exact_match"])

    def test_reports_restore_version_policy_from_main_image_header(self):
        official_main = bytearray(0x240)
        official_main[0x22C:0x22E] = struct.pack("<H", 1370)
        official_main[-1] = (-sum(official_main)) & 0xFF
        candidate_main = bytearray(official_main)
        candidate_main[0x22C:0x22E] = struct.pack("<H", 1369)
        candidate_main[-1] = (-sum(candidate_main[:-1])) & 0xFF
        official = package(b"\x01\xff", bytes(official_main))
        candidate = package(b"\x01\xff", bytes(candidate_main))
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            official_path, candidate_path = self.write_pair(root, official, candidate)
            report = gcd_candidate_verify.verify_packages(
                official_path,
                candidate_path,
                expected_official_sha256=hashlib.sha256(official).hexdigest(),
            )

        policy = report["version_policy"]
        self.assertEqual(policy["official_main_descriptor_version"], 1370)
        self.assertEqual(policy["candidate_main_descriptor_version"], 1370)
        self.assertEqual(policy["official_main_image_header_version"], 1370)
        self.assertEqual(policy["candidate_main_image_header_version"], 1369)
        self.assertTrue(policy["official_descriptor_newer_than_candidate_header"])
        self.assertEqual(
            policy["official_13_70_application_restore_assessment"],
            "CONDITIONALLY_ELIGIBLE_BY_VISIBLE_VERSION_COMPARISON",
        )

    def test_exact_restore_hypothesis_profile_accepts_only_pinned_candidate(self):
        official_path = Path(
            "artifacts/firmware/originals/Forerunner245_1370_GUPDATE.GCD"
        )
        candidate_path = Path(
            "artifacts/firmware/quarantine/"
            "Forerunner245_1370_fly-visible-restore1369.gcd.analysis-only.DO_NOT_INSTALL"
        )
        if not official_path.exists() or not candidate_path.exists():
            self.skipTest("pinned restore-hypothesis artifacts are unavailable")
        report = gcd_candidate_verify.verify_packages(
            official_path,
            candidate_path,
            profile=gcd_candidate_verify.RESTORE_HYPOTHESIS_PROFILE,
        )
        self.assertEqual(report["visible_gate_result"], "PASS")
        self.assertTrue(report["gates"]["profile_exact_match"])
        self.assertTrue(all(report["profile"]["checks"].values()))
        self.assertEqual(
            report["profile"]["expected_candidate_sha256"],
            gcd_candidate_verify.RESTORE_HYPOTHESIS_CANDIDATE_SHA256,
        )
        self.assertEqual(report["changed_byte_count"], 18)
        self.assertEqual(
            report["version_policy"]["official_13_70_application_restore_assessment"],
            "CONDITIONALLY_ELIGIBLE_BY_VISIBLE_VERSION_COMPARISON",
        )

    def test_exact_matched_13_69_profile_accepts_only_pinned_candidate(self):
        official_path = Path(
            "artifacts/firmware/originals/Forerunner245_1370_GUPDATE.GCD"
        )
        candidate_path = Path(
            "artifacts/firmware/quarantine/"
            "Forerunner245_1369-matched-fly-visible.gcd.analysis-only.DO_NOT_INSTALL"
        )
        if not official_path.exists() or not candidate_path.exists():
            self.skipTest("pinned matched-version artifact is unavailable")
        report = gcd_candidate_verify.verify_packages(
            official_path,
            candidate_path,
            profile=gcd_candidate_verify.MATCHED_13_69_PROFILE,
        )
        self.assertEqual(report["visible_gate_result"], "PASS")
        self.assertEqual(report["changed_byte_count"], 20)
        self.assertNotIn("changes_only_in_0x02bd_payload", report["gates"])
        self.assertNotIn("main_descriptor_unchanged", report["gates"])
        self.assertTrue(report["gates"]["changes_confined_to_exact_matched_profile"])
        self.assertTrue(report["gates"]["main_descriptor_matches_13_69_header"])
        self.assertTrue(all(report["profile"]["checks"].values()))


if __name__ == "__main__":
    unittest.main()
