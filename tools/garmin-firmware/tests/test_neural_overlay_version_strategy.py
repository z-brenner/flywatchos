import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
TOOLS = ROOT / "tools" / "garmin-firmware"
sys.path.insert(0, str(TOOLS))

import gcd_inspect  # noqa: E402
import gcd_candidate_verify  # noqa: E402
import neural_overlay_version_strategy as strategy  # noqa: E402


class NeuralOverlayVersionStrategyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.decision_path = (
            ROOT
            / "artifacts"
            / "analysis"
            / "fr245-1370-neural-offline-construction-decision.json"
        )
        cls.decision = json.loads(cls.decision_path.read_text(encoding="utf-8"))
        cls.official = (
            ROOT / cls.decision["inputs"]["official_gcd"]["path"]
        ).read_bytes()
        cls.hook = (ROOT / cls.decision["target_segments"]["hook"]["path"]).read_bytes()
        cls.primary = (
            ROOT / cls.decision["target_segments"]["primary"]["path"]
        ).read_bytes()
        cls.secondary = (
            ROOT / cls.decision["target_segments"]["secondary"]["path"]
        ).read_bytes()
        cls.candidate, cls.restore, cls.build_report = strategy.construct_pair(
            ROOT, cls.decision_path
        )

    @staticmethod
    def stream(data, record_id):
        matches = [
            stream
            for stream in gcd_inspect.collect_streams(gcd_inspect.parse_gcd(data))
            if stream.record_id == record_id
        ]
        if len(matches) != 1:
            raise AssertionError(f"expected one stream 0x{record_id:04x}")
        return matches[0]

    def test_builds_exact_coherent_quarantined_pair(self):
        candidate, restore, report = self.candidate, self.restore, self.build_report
        official_main = self.stream(self.official, strategy.MAIN_RECORD_ID)
        candidate_main = self.stream(candidate, strategy.MAIN_RECORD_ID)
        restore_main = self.stream(restore, strategy.MAIN_RECORD_ID)

        self.assertEqual(candidate_main.software_version, 1373)
        self.assertEqual(
            int.from_bytes(candidate_main.decoded[0x22C:0x22E], "little"), 1373
        )
        self.assertEqual(restore_main.software_version, 1374)
        self.assertEqual(
            int.from_bytes(restore_main.decoded[0x22C:0x22E], "little"), 1374
        )
        self.assertEqual(gcd_inspect._field(candidate_main.fields, "hwid"), 3076)
        self.assertEqual(gcd_inspect._field(restore_main.fields, "hwid"), 3076)

        primary = slice(strategy.PRIMARY_OFFSET, strategy.PRIMARY_OFFSET + 0x400)
        secondary = slice(strategy.SECONDARY_OFFSET, strategy.SECONDARY_OFFSET + 0x800)
        self.assertEqual(candidate_main.decoded[primary.start : primary.start + 794], self.primary)
        self.assertEqual(candidate_main.decoded[primary.stop - 1], report["candidate"]["repairs"]["primary_additive"]["new_byte"])
        self.assertEqual(candidate_main.decoded[secondary.start : secondary.start + 2044], self.secondary)
        self.assertEqual(candidate_main.decoded[secondary.start + 2044 : secondary.stop], b"\xff" * 4)
        self.assertEqual(restore_main.decoded[primary], official_main.decoded[primary])
        self.assertEqual(restore_main.decoded[secondary], official_main.decoded[secondary])
        self.assertEqual(
            restore_main.decoded[strategy.HOOK_OFFSET : strategy.HOOK_OFFSET + 4],
            official_main.decoded[strategy.HOOK_OFFSET : strategy.HOOK_OFFSET + 4],
        )
        self.assertTrue(all(report["candidate"]["checks"].values()))
        self.assertTrue(all(report["restore"]["checks"].values()))
        self.assertFalse(report["policy"]["packaging_allowed"])
        self.assertFalse(report["policy"]["live_staging_allowed"])

    def test_strict_verifier_reconstructs_and_rejects_unexpected_change(self):
        candidate, restore = self.candidate, self.restore
        report = strategy.verify_exact(ROOT, self.decision_path, candidate, restore)
        self.assertEqual(report["verdict"], "PASS")
        self.assertTrue(all(report["checks"].values()))

        damaged = bytearray(candidate)
        damaged[0x100000] ^= 1
        failed = strategy.verify_exact(
            ROOT, self.decision_path, bytes(damaged), restore
        )
        self.assertEqual(failed["verdict"], "FAIL")
        self.assertFalse(failed["checks"]["candidate_byte_exact_reconstruction"])

    def test_generic_verifier_has_opt_in_exact_neural_profiles(self):
        official_path = ROOT / self.decision["inputs"]["official_gcd"]["path"]
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            candidate_path = Path(directory) / strategy.CANDIDATE_FILENAME
            restore_path = Path(directory) / strategy.RESTORE_FILENAME
            candidate_path.write_bytes(self.candidate)
            restore_path.write_bytes(self.restore)
            generic = gcd_candidate_verify.verify_packages(
                official_path, candidate_path
            )
            self.assertEqual(generic["visible_gate_result"], "FAIL")
            candidate = gcd_candidate_verify.verify_packages(
                official_path,
                candidate_path,
                profile=gcd_candidate_verify.NEURAL_OVERLAY_PROFILE,
            )
            restore = gcd_candidate_verify.verify_packages(
                official_path,
                restore_path,
                profile=gcd_candidate_verify.NEURAL_RESTORE_PROFILE,
            )
        self.assertEqual(candidate["visible_gate_result"], "PASS")
        self.assertEqual(restore["visible_gate_result"], "PASS")
        self.assertTrue(candidate["profile"]["checks"]["byte_exact_reconstruction"])
        self.assertTrue(restore["profile"]["checks"]["byte_exact_reconstruction"])

    def test_decision_requires_exact_schema_policy_hwid_and_versions(self):
        cases = (
            ("missing", lambda d: d.pop("offline_quarantine_construction_allowed")),
            ("false", lambda d: d.__setitem__("offline_quarantine_construction_allowed", False)),
            ("packaging", lambda d: d.__setitem__("packaging_allowed", True)),
            ("staging", lambda d: d.__setitem__("live_staging_allowed", True)),
            ("hwid", lambda d: d["device"].__setitem__("hwid", 3075)),
            ("ordering", lambda d: d["device"].__setitem__("restore_version", 1373)),
        )
        for label, mutate in cases:
            with self.subTest(label=label):
                decision = copy.deepcopy(self.decision)
                mutate(decision)
                with self.assertRaises((KeyError, ValueError)):
                    strategy.validate_decision_document(decision)

    def test_decision_file_and_every_referenced_hash_are_pinned(self):
        validated = strategy.load_and_validate_decision(ROOT, self.decision_path)
        self.assertEqual(validated["decision_sha256"], strategy.DECISION_SHA256)
        self.assertGreaterEqual(len(validated["validated_files"]), 40)
        self.assertIn(
            "target_manifest.files.fr245-1370-neural-overlay.elf",
            validated["validated_files"],
        )
        self.assertIn(
            "target_manifest.sources.flyos/fly/brain32.c",
            validated["validated_files"],
        )

    def test_decision_directly_pins_current_emulator_and_focused_test(self):
        expected = {
            "emulator_source": ROOT
            / "tools/garmin-firmware/emulate_neural_overlay_payload.py",
            "emulator_test": ROOT
            / "tools/garmin-firmware/tests/test_emulate_neural_overlay_payload.py",
        }
        validated = strategy.load_and_validate_decision(ROOT, self.decision_path)
        for key, path in expected.items():
            with self.subTest(key=key):
                item = self.decision["inputs"][key]
                data = path.read_bytes()
                self.assertEqual(item["path"], path.relative_to(ROOT).as_posix())
                self.assertEqual(item["size"], len(data))
                self.assertEqual(item["sha256"], strategy.sha256(data))
                self.assertIn(f"inputs.{key}", validated["validated_files"])

        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            changed = Path(directory) / self.decision_path.name
            changed.write_bytes(self.decision_path.read_bytes() + b"\n")
            with self.assertRaisesRegex(ValueError, "decision SHA-256"):
                strategy.load_and_validate_decision(ROOT, changed)

        pinned = self.decision["target_segments"]["primary"]
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            changed = Path(directory) / "primary.bin"
            changed.write_bytes(self.primary[:-1] + bytes([self.primary[-1] ^ 1]))
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                strategy.validate_pinned_file(
                    changed,
                    expected_sha256=pinned["sha256"],
                    expected_size=pinned["compiled_size"],
                )

    def test_transaction_removes_every_created_output_after_failure(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            root = Path(directory)
            first = root / "first.bin"
            impossible = root / "missing" / "second.bin"
            with self.assertRaises(OSError):
                strategy.write_transaction(
                    ((first, b"first"), (impossible, b"second"))
                )
            self.assertFalse(first.exists())
            self.assertFalse(impossible.exists())

    def test_transaction_cleans_current_file_on_write_flush_and_fsync_failure(self):
        class FaultingFile:
            def __init__(self, handle, operation):
                self.handle = handle
                self.operation = operation

            def write(self, data):
                self.handle.write(data[:3])
                if self.operation == "write":
                    raise OSError("injected write failure")
                return self.handle.write(data[3:]) + 3

            def flush(self):
                self.handle.flush()
                if self.operation == "flush":
                    raise OSError("injected flush failure")

            def fileno(self):
                return self.handle.fileno()

            def __enter__(self):
                self.handle.__enter__()
                return self

            def __exit__(self, *args):
                return self.handle.__exit__(*args)

        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            root = Path(directory)
            for operation in ("write", "flush", "fsync"):
                with self.subTest(operation=operation):
                    target = root / f"{operation}.bin"

                    def opener(path, current=operation):
                        return FaultingFile(path.open("xb"), current)

                    def fsync(_descriptor, current=operation):
                        if current == "fsync":
                            raise OSError("injected fsync failure")

                    with self.assertRaisesRegex(OSError, operation):
                        strategy.write_transaction(
                            ((target, b"payload"),),
                            _open_file=opener,
                            _fsync=fsync,
                        )
                    self.assertFalse(target.exists())

    def test_transaction_never_unlinks_preexisting_and_surfaces_cleanup_failure(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            root = Path(directory)
            existing = root / "existing.bin"
            existing.write_bytes(b"preserve")
            with self.assertRaises(FileExistsError):
                strategy.write_transaction(((existing, b"replace"),))
            self.assertEqual(existing.read_bytes(), b"preserve")

            partial = root / "partial.bin"

            def fail_fsync(_descriptor):
                raise OSError("injected fsync failure")

            def fail_unlink(_path):
                raise OSError("injected cleanup failure")

            with self.assertRaisesRegex(RuntimeError, "cleanup could not be confirmed"):
                strategy.write_transaction(
                    ((partial, b"partial"),),
                    _fsync=fail_fsync,
                    _unlink=fail_unlink,
                )
            self.assertTrue(partial.exists())
            partial.unlink()

    def test_report_only_refresh_preserves_existing_package_bytes_and_metadata(self):
        package_paths = (
            strategy.EXACT_QUARANTINE_ROOT / strategy.CANDIDATE_FILENAME,
            strategy.EXACT_QUARANTINE_ROOT / strategy.RESTORE_FILENAME,
        )

        def snapshot(path):
            stat = path.stat()
            data = path.read_bytes()
            return (
                len(data),
                strategy.sha256(data),
                stat.st_ctime_ns,
                stat.st_mtime_ns,
            )

        before = {path: snapshot(path) for path in package_paths}
        result = strategy.refresh_attestation_reports(ROOT, self.decision_path)
        after = {path: snapshot(path) for path in package_paths}
        self.assertEqual(after, before)
        self.assertEqual(result["verdict"], "PASS")
        self.assertTrue(result["package_bytes_and_metadata_unchanged"])

        build = json.loads(
            (
                strategy.EXACT_ANALYSIS_ROOT / strategy.BUILD_REPORT_FILENAME
            ).read_text(encoding="utf-8")
        )
        strict = json.loads(
            (
                strategy.EXACT_ANALYSIS_ROOT / strategy.STRICT_REPORT_FILENAME
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(build["decision_sha256"], strategy.DECISION_SHA256)
        self.assertEqual(strict["build_evidence"]["decision_sha256"], strategy.DECISION_SHA256)
        self.assertTrue(
            build["attestation_refresh"]["package_bytes_and_metadata_unchanged"]
        )

    def test_output_paths_fail_closed(self):
        root = strategy.EXACT_QUARANTINE_ROOT
        expected = root / strategy.CANDIDATE_FILENAME
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            temporary_root = Path(directory)
            strategy.validate_output_target(
                temporary_root / strategy.CANDIDATE_FILENAME,
                temporary_root,
                input_paths=[],
            )
        with self.assertRaisesRegex(ValueError, "already exists"):
            strategy.validate_output_target(expected, root, input_paths=[])

        bad = (
            root / ".." / "escaped" / strategy.CANDIDATE_FILENAME,
            ROOT / "other" / strategy.CANDIDATE_FILENAME,
            Path("D:/") / strategy.CANDIDATE_FILENAME,
            root / "wrong.gcd",
        )
        for path in bad:
            with self.subTest(path=path):
                with self.assertRaises(ValueError):
                    strategy.validate_output_target(path, root, input_paths=[])

        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            alias_root = Path(directory)
            alias = alias_root / strategy.CANDIDATE_FILENAME
            with self.assertRaisesRegex(ValueError, "input"):
                strategy.validate_output_target(alias, alias_root, input_paths=[alias])

        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            existing = Path(directory) / strategy.CANDIDATE_FILENAME
            existing.write_bytes(b"already here")
            with self.assertRaisesRegex(ValueError, "already exists"):
                strategy.validate_output_target(existing, Path(directory), input_paths=[])

            original = Path(directory) / "original.bin"
            original.write_bytes(b"pinned")
            hardlink = Path(directory) / strategy.RESTORE_FILENAME
            os.link(original, hardlink)
            with self.assertRaises(ValueError):
                strategy.validate_output_target(hardlink, Path(directory), input_paths=[original])

    def test_staging_guard_has_no_neural_mode(self):
        script = ROOT / "tools" / "live-proof" / "stage-gupdate.ps1"
        source = script.read_text(encoding="utf-8")
        self.assertNotIn(strategy.CANDIDATE_FILENAME, source)
        self.assertNotIn(strategy.RESTORE_FILENAME, source)
        completed = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(script),
                "-Mode",
                "NeuralOverlay1373",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("ValidateSet", completed.stderr + completed.stdout)


if __name__ == "__main__":
    unittest.main()
