"""Missing private evidence may skip; supplied evidence must never be hidden."""

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path


from private_fixtures import require_private_files

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import neural_specimen_n64_version_strategy as custody


class PrivateFixtureTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def test_all_absent_inputs_are_explicit_integration_skip(self):
        with self.assertRaisesRegex(unittest.SkipTest, "private integration fixtures absent"):
            require_private_files(self.root / "firmware.bin", self.root / "receipt.json")

    def test_partial_inputs_are_failure_in_either_order(self):
        present = self.root / "receipt.json"
        present.write_text("{}", encoding="utf-8")
        absent = self.root / "firmware.bin"
        for paths in ((present, absent), (absent, present)):
            with self.subTest(paths=paths), self.assertRaisesRegex(AssertionError, "incomplete"):
                require_private_files(*paths)

    def test_existing_directory_is_failure(self):
        with self.assertRaisesRegex(AssertionError, "regular file"):
            require_private_files(self.root)

    def test_empty_input_is_failure(self):
        path = self.root / "firmware.bin"
        path.write_bytes(b"")
        with self.assertRaisesRegex(AssertionError, "empty"):
            require_private_files(path)

    def test_dangling_symlink_is_failure_not_absence(self):
        path = self.root / "firmware.bin"
        try:
            path.symlink_to(self.root / "absent.bin")
        except (OSError, NotImplementedError) as error:
            self.skipTest(f"host does not permit symlinks: {error}")
        with self.assertRaisesRegex(AssertionError, "regular file"):
            require_private_files(path)

    def test_no_inputs_is_programming_error_not_skip(self):
        with self.assertRaisesRegex(ValueError, "at least one"):
            require_private_files()

    def test_present_input_is_unchanged_and_reaches_content_validation(self):
        path = self.root / "receipt.json"
        raw = b"malformed supplied evidence"
        path.write_bytes(raw)
        try:
            require_private_files(path)
        except unittest.SkipTest as error:
            self.fail(f"supplied malformed evidence was skipped: {error}")
        with self.assertRaises(json.JSONDecodeError):
            json.loads(path.read_bytes())
        self.assertEqual(raw, path.read_bytes())

    def test_wrong_bytes_reach_pinned_hash_validation(self):
        path = self.root / "firmware.bin"
        path.write_bytes(b"wrong bytes")
        try:
            require_private_files(path)
        except unittest.SkipTest as error:
            self.fail(f"supplied wrong bytes were skipped: {error}")
        with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
            custody.load_pinned_snapshot(
                path, expected_sha256=hashlib.sha256(b"pinned bytes").hexdigest()
            )


if __name__ == "__main__":
    unittest.main()
