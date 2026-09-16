import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/garmin-firmware"))
import neural_specimen_n64_version_strategy as custody  # noqa: E402
import stateless_home_diagnostic_package as package  # noqa: E402


class StatelessHomeDiagnosticPackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.before = {str(path): package.sha(package._snapshot(ROOT, path)) for path in package.PINNED}
        cls.candidate, cls.restore, cls.report = package.construct_pair(ROOT)

    @classmethod
    def tearDownClass(cls):
        after = {str(path): package.sha(package._snapshot(ROOT, path)) for path in package.PINNED}
        assert cls.before == after, "original inputs changed during package tests"

    def test_complete_official_reconstruction_and_key_restoration(self):
        official = package._snapshot(ROOT, package.OFFICIAL)
        base = package._stream(official, 0x02BD).decoded
        candidate = package._stream(self.candidate, 0x02BD)
        restore = package._stream(self.restore, 0x02BD)
        self.assertEqual((candidate.software_version, restore.software_version), (1378, 1379))
        self.assertEqual(candidate.decoded[package.KEY:package.KEY + 6], base[package.KEY:package.KEY + 6])
        self.assertEqual(candidate.decoded[package.PRIMARY:package.REPAIR], base[package.PRIMARY:package.REPAIR])
        self.assertEqual(candidate.decoded[package.SECONDARY + 1066:package.SECONDARY + 2048], base[package.SECONDARY + 1066:package.SECONDARY + 2048])
        expected_restore = bytearray(base)
        expected_restore[package.HEADER_VERSION:package.HEADER_VERSION + 2] = (1379).to_bytes(2, "little")
        expected_restore[package.FINAL_REPAIR] = restore.decoded[package.FINAL_REPAIR]
        self.assertEqual(restore.decoded, expected_restore)
        self.assertTrue(all(self.report["candidate"]["checks"].values()))
        self.assertTrue(all(self.report["restore"]["checks"].values()))

    def test_native_invalid_and_null_pass_through_receipt(self):
        results = json.loads(package._snapshot(ROOT, package.RUN / "unicorn-results-home-seeded.json"))["results"]
        native = [r for r in results if r.get("class") in ("N", "I")]
        self.assertGreaterEqual(len(native), 10)
        self.assertTrue(all(r["fb_writes"] == 0 and r["flush_calls"] == 1 for r in native))
        self.assertEqual(next(r for r in results if r["name"] == "null_framebuffer")["fb_writes"], 0)

    def test_one_byte_tamper_fails_exact_reconstruction(self):
        damaged = bytearray(self.candidate)
        damaged[0x100000] ^= 1
        report = package.verify_exact(bytes(damaged), self.restore, ROOT, rebuild=False)
        self.assertEqual(report["verdict"], "FAIL")
        self.assertFalse(report["checks"]["candidate_byte_exact"])

    def test_source_hash_and_missing_receipt_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
            custody.load_pinned_snapshot(ROOT / package.SRC / "probe.c", expected_sha256="0" * 64)
        with self.assertRaisesRegex(ValueError, "pinned input is absent"):
            custody.load_pinned_snapshot(ROOT / "missing-unicorn-receipt.json", expected_sha256="0" * 64)

    def test_output_collision_and_wrong_root_rejected(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
            root = Path(temporary)
            first = root / package.CANDIDATE_NAME
            package._require_new_output(first, root)
            first.write_bytes(b"occupied")
            with self.assertRaisesRegex(ValueError, "collision"):
                package._require_new_output(first, root)
            with self.assertRaisesRegex(ValueError, "escaped"):
                package._require_new_output(root / "elsewhere" / package.CANDIDATE_NAME, root)

    def test_transaction_cleans_new_files_on_readback_error(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
            root = Path(temporary)
            first, second = root / "first", root / "second"
            def corrupt_second(path):
                return b"bad" if path == second else path.read_bytes()
            with self.assertRaisesRegex(OSError, "readback mismatch"):
                custody.write_transaction(((first, b"first"), (second, b"second")), _read_back=corrupt_second)
            self.assertFalse(first.exists())
            self.assertFalse(second.exists())

    def test_locked_staging_and_offline_names(self):
        source = package._snapshot(ROOT, package.STAGE).decode("utf-8")
        self.assertNotIn(package.CANDIDATE_NAME, source)
        self.assertNotIn(package.RESTORE_NAME, source)
        self.assertNotIn(package.sha(self.candidate).upper(), source)
        self.assertNotIn(package.sha(self.restore).upper(), source)
        self.assertTrue(package.CANDIDATE_NAME.endswith(package.SUFFIX))
        self.assertTrue(package.RESTORE_NAME.endswith(package.SUFFIX))
        self.assertFalse(self.report["policy"]["live_staging_allowed"])


if __name__ == "__main__":
    unittest.main()
