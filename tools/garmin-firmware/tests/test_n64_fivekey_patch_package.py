"""Offline package invariants for the exact 13.80 five-key patch."""

from pathlib import Path
import sys
import unittest

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))

import build_overlay_candidate  # noqa: E402
import n64_fivekey_patch_package as package  # noqa: E402


class FiveKeyPackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[3]
        if not (root / package.OFFICIAL_RELATIVE).is_file():
            raise unittest.SkipTest("private original firmware is unavailable")
        if not (root / package.INSTALLED_CANDIDATE_RELATIVE).is_file():
            raise unittest.SkipTest("private 13.76 source is unavailable")
        cls.root = root
        cls.official = (root / package.OFFICIAL_RELATIVE).read_bytes()
        cls.installed = (root / package.INSTALLED_CANDIDATE_RELATIVE).read_bytes()
        cls.candidate, cls.restore, cls.report = package.construct_pair(
            cls.official, cls.installed
        )

    def test_candidate_changes_only_pinned_key_ranges_and_repairs(self):
        _helper, old = build_overlay_candidate._streams(self.installed)
        _helper, new = build_overlay_candidate._streams(self.candidate)
        differences = {i for i, (a, b) in enumerate(zip(old.decoded, new.decoded)) if a != b}
        allowed = (
            set(range(package.KEY_FILTER_OFFSET, package.KEY_FILTER_OFFSET + 16))
            | set(range(package.BACK_GUARD_OFFSET, package.BACK_GUARD_OFFSET + 2))
            | {package.PRIMARY_REPAIR_OFFSET, package.MAIN_HEADER_VERSION_OFFSET,
               package.FINAL_MAIN_REPAIR_OFFSET}
        )
        self.assertTrue(differences)
        self.assertLessEqual(differences, allowed)
        self.assertEqual(new.software_version, 1380)
        self.assertEqual(len(new.decoded), len(old.decoded))

    def test_restore_is_official_code_except_version_and_checksum(self):
        _helper, official = build_overlay_candidate._streams(self.official)
        _helper, restored = build_overlay_candidate._streams(self.restore)
        differences = {i for i, (a, b) in enumerate(zip(official.decoded, restored.decoded)) if a != b}
        self.assertLessEqual(differences, {package.MAIN_HEADER_VERSION_OFFSET,
                                            package.FINAL_MAIN_REPAIR_OFFSET})
        self.assertEqual(restored.software_version, 1381)

    def test_rejects_changed_1376_input(self):
        modified = bytearray(self.installed)
        modified[-123] ^= 1
        with self.assertRaises(ValueError):
            package.construct_pair(self.official, bytes(modified))

    def test_full_image_and_helper_identity(self):
        self.assertTrue(self.report["candidate_full_image_valid"])
        self.assertTrue(self.report["restore_full_image_valid"])
        self.assertTrue(self.report["helper_byte_exact"])
        self.assertEqual(len(self.candidate), len(self.installed))
        self.assertEqual(len(self.restore), len(self.official))

    def test_exact_quarantined_package_hashes(self):
        self.assertEqual(
            package.sha256(self.candidate),
            "2054be63e12531c61c7417156fa208b27db82af70b518dbf9fd0f8df1e2a7dbd",
        )
        self.assertEqual(
            package.sha256(self.restore),
            "b62be4c422dfe03f83fef30139557143ad285abc18b733899801dba16ffd9f5b",
        )


if __name__ == "__main__":
    unittest.main()
