import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[3]
TOOLS = ROOT / "tools" / "garmin-firmware"
sys.path.insert(0, str(TOOLS))

import gcd_candidate_verify  # noqa: E402
import gcd_inspect  # noqa: E402
import neural_specimen_n64_version_strategy as strategy  # noqa: E402


class NeuralSpecimenN64VersionStrategyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.decision_path = ROOT / strategy.DECISION_RELATIVE_PATH
        cls.decision = json.loads(cls.decision_path.read_text(encoding="utf-8"))
        cls.official = (ROOT / cls.decision["inputs"]["official_gcd"]["path"]).read_bytes()
        cls.hook = (ROOT / cls.decision["target_segments"]["hook"]["path"]).read_bytes()
        cls.primary = (ROOT / cls.decision["target_segments"]["primary"]["path"]).read_bytes()
        cls.secondary = (ROOT / cls.decision["target_segments"]["secondary"]["path"]).read_bytes()
        cls.candidate, cls.restore, cls.report = strategy.construct_pair(ROOT, cls.decision_path)

    @staticmethod
    def stream(data, record_id):
        items = [s for s in gcd_inspect.collect_streams(gcd_inspect.parse_gcd(data)) if s.record_id == record_id]
        if len(items) != 1:
            raise AssertionError(f"expected one stream 0x{record_id:04x}")
        return items[0]

    def test_exact_monotonic_version_chain_and_names(self):
        self.assertEqual((strategy.OFFICIAL_VERSION, strategy.PRIOR_OVERLAY_VERSION), (1370, 1373))
        self.assertEqual((strategy.CANDIDATE_VERSION, strategy.RESTORE_VERSION), (1374, 1375))
        self.assertEqual(strategy.CANDIDATE_VERSION, strategy.PRIOR_OVERLAY_VERSION + 1)
        self.assertEqual(strategy.RESTORE_VERSION, strategy.CANDIDATE_VERSION + 1)
        self.assertEqual(strategy.CANDIDATE_FILENAME, "Forerunner245_1374-flyos-neural-specimen-n64.gcd.analysis-only.DO_NOT_INSTALL")
        self.assertEqual(strategy.RESTORE_FILENAME, "Forerunner245_1375-official-payload-restore-n64.gcd.analysis-only.DO_NOT_INSTALL")

    def test_decision_pins_all_inputs_reviews_and_prior_live_chain(self):
        validated = strategy.load_and_validate_decision(ROOT, self.decision_path)
        self.assertEqual(validated["decision_sha256"], strategy.DECISION_SHA256)
        self.assertGreaterEqual(len(validated["validated_files"]), 50)
        required = {
            "inputs.official_gcd", "inputs.official_main", "inputs.official_helper",
            "inputs.allocation", "inputs.target_manifest", "inputs.evidence_manifest",
            "inputs.runtime_state", "inputs.emulator_source", "inputs.emulator_test",
            "inputs.emulation_report", "version_evidence.prior_overlay_package",
            "version_evidence.prior_package_build", "version_evidence.prior_post_install_check",
            "review_evidence.task_3_review", "review_evidence.task_3_independent_audit",
            "review_evidence.task_4_spec_review", "review_evidence.task_4_emulator_review",
            "review_evidence.task_4_allocation_review", "review_evidence.task_4_report",
        }
        self.assertTrue(required.issubset(validated["validated_files"]))
        self.assertEqual(self.decision["device"]["installed_prior_wrapper_version"], 1373)

    def test_constructs_exact_candidate_and_complete_official_code_restore(self):
        official_main = self.stream(self.official, strategy.MAIN_RECORD_ID)
        candidate_main = self.stream(self.candidate, strategy.MAIN_RECORD_ID)
        restore_main = self.stream(self.restore, strategy.MAIN_RECORD_ID)
        self.assertEqual(candidate_main.software_version, 1374)
        self.assertEqual(restore_main.software_version, 1375)
        self.assertEqual(int.from_bytes(candidate_main.decoded[0x22C:0x22E], "little"), 1374)
        self.assertEqual(int.from_bytes(restore_main.decoded[0x22C:0x22E], "little"), 1375)
        self.assertEqual(candidate_main.decoded[strategy.HOOK_OFFSET:strategy.HOOK_OFFSET + 4], self.hook)
        self.assertEqual(candidate_main.decoded[strategy.PRIMARY_OFFSET:strategy.PRIMARY_OFFSET + len(self.primary)], self.primary)
        self.assertEqual(candidate_main.decoded[strategy.SECONDARY_OFFSET:strategy.SECONDARY_OFFSET + len(self.secondary)], self.secondary)
        self.assertEqual(candidate_main.decoded[strategy.PRIMARY_OFFSET + len(self.primary):strategy.PRIMARY_REPAIR_OFFSET], b"\xff" * 7)
        self.assertEqual(candidate_main.decoded[strategy.SECONDARY_OFFSET + len(self.secondary):strategy.SECONDARY_OFFSET + strategy.SECONDARY_ALLOCATION], b"\xff" * 14)
        self.assertEqual(restore_main.decoded[strategy.HOOK_OFFSET:strategy.HOOK_OFFSET + 4], official_main.decoded[strategy.HOOK_OFFSET:strategy.HOOK_OFFSET + 4])
        self.assertEqual(restore_main.decoded[strategy.PRIMARY_OFFSET:strategy.PRIMARY_OFFSET + strategy.PRIMARY_ALLOCATION], official_main.decoded[strategy.PRIMARY_OFFSET:strategy.PRIMARY_OFFSET + strategy.PRIMARY_ALLOCATION])
        self.assertEqual(restore_main.decoded[strategy.SECONDARY_OFFSET:strategy.SECONDARY_OFFSET + strategy.SECONDARY_ALLOCATION], official_main.decoded[strategy.SECONDARY_OFFSET:strategy.SECONDARY_OFFSET + strategy.SECONDARY_ALLOCATION])
        self.assertTrue(all(self.report["candidate"]["checks"].values()))
        self.assertTrue(all(self.report["restore"]["checks"].values()))

    def test_helper_layout_reconstruction_repairs_and_diff_ranges(self):
        official_helper = self.stream(self.official, strategy.HELPER_RECORD_ID)
        for label, package in (("candidate", self.candidate), ("restore", self.restore)):
            helper = self.stream(package, strategy.HELPER_RECORD_ID)
            item = self.report[label]
            self.assertEqual(len(package), len(self.official))
            self.assertEqual(helper.decoded, official_helper.decoded)
            self.assertTrue(item["helper_stream"]["byte_exact_official"])
            self.assertTrue(item["checks"]["record_layout_exact_official"])
            self.assertTrue(item["checks"]["outer_checkpoints_valid"])
            self.assertTrue(item["checks"]["main_additive_sum_zero"])
            self.assertGreater(len(item["raw_changed_ranges"]), 0)
            self.assertGreater(len(item["decoded_changed_ranges"]), 0)
        exact = strategy.verify_exact(ROOT, self.decision_path, self.candidate, self.restore)
        self.assertEqual(exact["verdict"], "PASS")
        self.assertTrue(all(exact["checks"].values()))

    def test_strict_verification_rejects_any_unexpected_byte(self):
        damaged = bytearray(self.candidate)
        damaged[0x100000] ^= 1
        report = strategy.verify_exact(ROOT, self.decision_path, bytes(damaged), self.restore)
        self.assertEqual(report["verdict"], "FAIL")
        self.assertFalse(report["checks"]["candidate_byte_exact_reconstruction"])

    def test_attestation_bundle_covers_reconstruction_full_image_emulator_diff_risk_and_hashes(self):
        reports = strategy.build_attestation_bundle(ROOT, self.decision_path, self.candidate, self.restore)
        self.assertEqual(
            set(reports),
            {
                strategy.RECONSTRUCTION_REPORT_FILENAME,
                strategy.FULL_IMAGE_REPORT_FILENAME,
                strategy.EMULATOR_REPORT_FILENAME,
                strategy.DIFFERENCE_REPORT_FILENAME,
                strategy.RISK_REPORT_FILENAME,
                strategy.SHA_LEDGER_FILENAME,
            },
        )
        reconstruction = json.loads(reports[strategy.RECONSTRUCTION_REPORT_FILENAME])
        full_image = json.loads(reports[strategy.FULL_IMAGE_REPORT_FILENAME])
        emulator = json.loads(reports[strategy.EMULATOR_REPORT_FILENAME])
        differences = json.loads(reports[strategy.DIFFERENCE_REPORT_FILENAME])
        risk = json.loads(reports[strategy.RISK_REPORT_FILENAME])
        self.assertEqual(reconstruction["verdict"], "PASS")
        self.assertTrue(all(reconstruction["checks"].values()))
        self.assertTrue(full_image["candidate"]["confirmed_full_image_checks_pass"])
        self.assertTrue(full_image["restore"]["confirmed_full_image_checks_pass"])
        self.assertTrue(all(emulator["checks"].values()))
        self.assertTrue(all(differences["checks"].values()))
        self.assertEqual(risk["brick_risk"], "nonzero")
        self.assertFalse(risk["known_nonboot_recovery"])
        ledger = reports[strategy.SHA_LEDGER_FILENAME].decode("utf-8")
        self.assertIn(strategy.sha256(self.candidate), ledger)
        self.assertIn(strategy.sha256(self.restore), ledger)

    def test_generic_verifier_has_opt_in_exact_n64_profiles(self):
        official_path = ROOT / self.decision["inputs"]["official_gcd"]["path"]
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            candidate_path = Path(directory) / strategy.CANDIDATE_FILENAME
            restore_path = Path(directory) / strategy.RESTORE_FILENAME
            candidate_path.write_bytes(self.candidate)
            restore_path.write_bytes(self.restore)
            candidate = gcd_candidate_verify.verify_packages(official_path, candidate_path, profile=gcd_candidate_verify.N64_OVERLAY_PROFILE)
            restore = gcd_candidate_verify.verify_packages(official_path, restore_path, profile=gcd_candidate_verify.N64_RESTORE_PROFILE)
        self.assertEqual(candidate["visible_gate_result"], "PASS")
        self.assertEqual(restore["visible_gate_result"], "PASS")
        self.assertTrue(candidate["profile"]["checks"]["byte_exact_reconstruction"])
        self.assertTrue(restore["profile"]["checks"]["byte_exact_reconstruction"])

    def test_schema_fails_closed_on_policy_version_hash_and_placement_mutations(self):
        mutations = (
            lambda d: d.__setitem__("packaging_allowed", True),
            lambda d: d.__setitem__("live_staging_allowed", True),
            lambda d: d["device"].__setitem__("candidate_version", 1373),
            lambda d: d["device"].__setitem__("restore_version", 1374),
            lambda d: d["target_segments"]["primary"].__setitem__("compiled_size", 1015),
            lambda d: d["target_segments"]["secondary"].__setitem__("runtime_start", 0x001FA402),
        )
        for mutate in mutations:
            decision = copy.deepcopy(self.decision)
            mutate(decision)
            with self.assertRaises((KeyError, ValueError)):
                strategy.validate_decision_document(decision)

    def test_create_new_transaction_cleans_partial_outputs_and_never_overwrites(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            root = Path(directory)
            first = root / "first.bin"
            with self.assertRaises(OSError):
                strategy.write_transaction(((first, b"first"), (root / "missing" / "second.bin", b"second")))
            self.assertFalse(first.exists())
            existing = root / "existing.bin"
            existing.write_bytes(b"preserve")
            with self.assertRaises(FileExistsError):
                strategy.write_transaction(((existing, b"replace"),))
            self.assertEqual(existing.read_bytes(), b"preserve")

    def test_transaction_cleans_write_flush_and_fsync_faults(self):
        class FaultingFile:
            def __init__(self, handle, operation): self.handle, self.operation = handle, operation
            def write(self, data):
                self.handle.write(data[:3])
                if self.operation == "write": raise OSError("write")
                return self.handle.write(data[3:]) + 3
            def flush(self):
                self.handle.flush()
                if self.operation == "flush": raise OSError("flush")
            def fileno(self): return self.handle.fileno()
            def __enter__(self): self.handle.__enter__(); return self
            def __exit__(self, *args): return self.handle.__exit__(*args)
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            root = Path(directory)
            for operation in ("write", "flush", "fsync"):
                target = root / f"{operation}.bin"
                def opener(path, op=operation): return FaultingFile(path.open("xb"), op)
                def fsync(_fd, op=operation):
                    if op == "fsync": raise OSError("fsync")
                with self.assertRaises(OSError): strategy.write_transaction(((target, b"payload"),), _open_file=opener, _fsync=fsync)
                self.assertFalse(target.exists())

    def test_construction_consumes_each_validated_binary_snapshot_once(self):
        tracked = {
            (ROOT / self.decision["inputs"]["official_gcd"]["path"]).resolve(),
            (ROOT / self.decision["target_segments"]["hook"]["path"]).resolve(),
            (ROOT / self.decision["target_segments"]["primary"]["path"]).resolve(),
            (ROOT / self.decision["target_segments"]["secondary"]["path"]).resolve(),
        }
        original = Path.read_bytes
        counts = {path: 0 for path in tracked}

        def mutate_on_reopen(path):
            resolved = path.resolve()
            data = original(path)
            if resolved in counts:
                counts[resolved] += 1
                if counts[resolved] > 1:
                    return bytes([data[0] ^ 1]) + data[1:]
            return data

        with mock.patch.object(Path, "read_bytes", mutate_on_reopen):
            candidate, restore, report = strategy.construct_pair(ROOT, self.decision_path)
        self.assertEqual(set(counts.values()), {1})
        self.assertEqual(strategy.sha256(candidate), "3a4a4af6355c132571c1158667cc43c96bf5da7a67737ab028267930e71134cd")
        self.assertEqual(strategy.sha256(restore), "ccd2a29c51a41a436111239c7181e1cb0cea1f2fac1c48d600fff6dec103e5da")
        self.assertEqual(report["validated_inputs"]["inputs.official_gcd"]["sha256"], strategy.sha256(self.official))

    def test_pure_short_write_is_removed_and_retry_is_safe(self):
        class ShortFile:
            def __init__(self, handle): self.handle = handle
            def write(self, data): self.handle.write(data[:-1]); return len(data) - 1
            def flush(self): self.handle.flush()
            def fileno(self): return self.handle.fileno()
            def __enter__(self): self.handle.__enter__(); return self
            def __exit__(self, *args): return self.handle.__exit__(*args)
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            target = Path(directory) / "short.bin"
            sentinel = Path(directory) / "sentinel.bin"
            sentinel.write_bytes(b"immutable")
            with self.assertRaisesRegex(OSError, "short write"):
                strategy.write_transaction(((target, b"payload"),), _open_file=lambda path: ShortFile(path.open("xb")))
            self.assertFalse(target.exists())
            self.assertEqual(sentinel.read_bytes(), b"immutable")
            strategy.write_transaction(((target, b"payload"),))
            self.assertEqual(target.read_bytes(), b"payload")

    def test_cleanup_unlink_failure_is_fatal_and_does_not_overwrite_then_retry_is_safe(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            root = Path(directory)
            target = root / "partial.bin"
            sentinel = root / "sentinel.bin"
            sentinel.write_bytes(b"immutable")
            with self.assertRaisesRegex(RuntimeError, "cleanup could not be confirmed") as raised:
                strategy.write_transaction(
                    ((target, b"payload"),),
                    _fsync=lambda _fd: (_ for _ in ()).throw(OSError("injected fsync")),
                    _unlink=lambda path: (_ for _ in ()).throw(OSError(f"injected unlink {path.name}")),
                )
            self.assertIn(str(target), str(raised.exception))
            self.assertTrue(target.exists())
            self.assertEqual(sentinel.read_bytes(), b"immutable")
            target.unlink()
            strategy.write_transaction(((target, b"payload"),))
            self.assertEqual(target.read_bytes(), b"payload")

    def test_post_write_readback_mismatch_cleans_output_and_retry_is_safe(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            target = Path(directory) / "readback.bin"
            with self.assertRaisesRegex(OSError, "readback mismatch"):
                strategy.write_transaction(
                    ((target, b"payload"),),
                    _read_back=lambda _path: b"tampered",
                )
            self.assertFalse(target.exists())
            strategy.write_transaction(((target, b"payload"),))
            self.assertEqual(target.read_bytes(), b"payload")

    def test_report_replace_validates_final_paths_and_rolls_back_then_retries(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            root = Path(directory)
            first = root / "first.json"
            second = root / "second.json"
            first.write_bytes(b"old-first")
            second.write_bytes(b"old-second")

            def corrupt_first_install(source, destination):
                os.replace(source, destination)
                if source.name.endswith(".refresh.tmp") and destination == first:
                    destination.write_bytes(b"tampered")

            with self.assertRaisesRegex(OSError, "final report readback mismatch"):
                strategy.replace_reports_transaction(
                    ((first, b"new-first"), (second, b"new-second")),
                    _replace=corrupt_first_install,
                )
            self.assertEqual(first.read_bytes(), b"old-first")
            self.assertEqual(second.read_bytes(), b"old-second")
            self.assertEqual(list(root.glob("*.refresh.*")), [])

            strategy.replace_reports_transaction(
                ((first, b"new-first"), (second, b"new-second"))
            )
            self.assertEqual(first.read_bytes(), b"new-first")
            self.assertEqual(second.read_bytes(), b"new-second")

    def test_output_is_quarantine_only_and_create_new(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            root = Path(directory)
            strategy.validate_output_target(root / strategy.CANDIDATE_FILENAME, root, input_paths=[])
            for bad in (
                root / "wrong.gcd",
                root / "nested" / strategy.CANDIDATE_FILENAME,
                root / "alias" / ".." / strategy.CANDIDATE_FILENAME,
                Path("D:/") / strategy.CANDIDATE_FILENAME,
            ):
                with self.assertRaises(ValueError): strategy.validate_output_target(bad, root, input_paths=[])

            existing = root / strategy.CANDIDATE_FILENAME
            existing.write_bytes(b"preserve")
            with self.assertRaisesRegex(ValueError, "already exists"):
                strategy.validate_output_target(existing, root, input_paths=[])
            self.assertEqual(existing.read_bytes(), b"preserve")
            existing.unlink()

            original = root / "immutable-input.bin"
            original.write_bytes(b"immutable")
            hardlink = root / strategy.RESTORE_FILENAME
            os.link(original, hardlink)
            with self.assertRaises(ValueError):
                strategy.validate_output_target(hardlink, root, input_paths=[original])
            self.assertEqual(original.read_bytes(), b"immutable")

    def test_symlink_alias_is_rejected_or_explicitly_skipped(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            root = Path(directory)
            original = root / "immutable-input.bin"
            original.write_bytes(b"immutable")
            symlink = root / strategy.CANDIDATE_FILENAME
            try:
                os.symlink(original, symlink)
            except OSError as error:
                self.skipTest(f"host does not permit symlink creation: {error}")
            try:
                with self.assertRaisesRegex(ValueError, "reparse points and symlinks"):
                    strategy.validate_output_target(
                        symlink, root, input_paths=[original]
                    )
            finally:
                symlink.unlink(missing_ok=True)

    @unittest.skipUnless(os.name == "nt", "Windows junction coverage")
    def test_windows_junction_alias_is_actually_rejected(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            root = Path(directory)
            target = root / "real-quarantine"
            target.mkdir()
            junction = root / "quarantine-alias"
            created = subprocess.run(
                ["cmd", "/d", "/c", "mklink", "/J", str(junction), str(target)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(
                created.returncode,
                0,
                f"junction setup failed: {created.stdout}{created.stderr}",
            )
            try:
                with self.assertRaisesRegex(ValueError, "reparse points and symlinks"):
                    strategy.validate_output_target(
                        junction / strategy.CANDIDATE_FILENAME,
                        junction,
                        input_paths=[],
                    )
            finally:
                junction.rmdir()

    def test_exact_quarantine_root_rejects_alternate_repository(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            alternate_root = Path(directory)
            (alternate_root / "artifacts/firmware/quarantine").mkdir(parents=True)
            (alternate_root / "artifacts/firmware/analysis").mkdir(parents=True)
            with self.assertRaisesRegex(ValueError, "exact approved root"):
                strategy._validate_exact_roots(alternate_root)

    def test_staging_script_explicitly_blocks_n64_names_hashes_and_modes(self):
        source = (ROOT / "tools/live-proof/stage-gupdate.ps1").read_text(encoding="utf-8")
        self.assertIn(strategy.CANDIDATE_FILENAME, source)
        self.assertIn(strategy.RESTORE_FILENAME, source)
        self.assertIn("NeuralSpecimenN64Overlay1374", source)
        self.assertIn("NeuralSpecimenN64Restore1375", source)
        self.assertIn("BlockedN64Artifacts", source)
        for mode in ("NeuralSpecimenN64Overlay1374", "NeuralSpecimenN64Restore1375"):
            completed = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ROOT / "tools/live-proof/stage-gupdate.ps1"), "-Mode", mode], cwd=ROOT, capture_output=True, text=True, check=False)
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("explicitly blocked", (completed.stdout + completed.stderr).lower())

    def test_staging_script_rejects_future_profile_aliases_by_path_name_and_hash(self):
        script = ROOT / "tools/live-proof/stage-gupdate.ps1"
        source = script.read_text(encoding="utf-8")
        cases = {
            "path": source.replace(
                "artifacts\\firmware\\quarantine\\Forerunner245_1369-matched-fly-visible.gcd.analysis-only.DO_NOT_INSTALL",
                "artifacts\\firmware\\quarantine\\Forerunner245_1374-flyos-neural-specimen-n64.gcd.analysis-only.DO_NOT_INSTALL",
                1,
            ),
            "basename": source.replace(
                "artifacts\\firmware\\quarantine\\Forerunner245_1369-matched-fly-visible.gcd.analysis-only.DO_NOT_INSTALL",
                "safe\\alias\\Forerunner245_1375-official-payload-restore-n64.gcd.analysis-only.DO_NOT_INSTALL",
                1,
            ),
            "hash": source.replace(
                "D89D52CA82586D7CEA003C2F5B65B854790B572246164064FE3DF079FA36CA2F",
                "3A4A4AF6355C132571C1158667CC43C96BF5DA7A67737AB028267930E71134CD",
                1,
            ),
        }
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            for label, mutated in cases.items():
                path = Path(directory) / f"stage-{label}.ps1"
                path.write_text(mutated, encoding="utf-8")
                completed = subprocess.run(
                    ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(path), "-Mode", "Candidate1369"],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertNotEqual(completed.returncode, 0)
                self.assertIn("explicitly blocked", (completed.stdout + completed.stderr).lower(), label)


if __name__ == "__main__":
    unittest.main()
