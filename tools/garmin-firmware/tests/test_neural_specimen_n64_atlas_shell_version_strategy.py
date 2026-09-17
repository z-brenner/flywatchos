import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TOOLS = ROOT / "tools" / "garmin-firmware"
sys.path.insert(0, str(TOOLS))

import gcd_inspect  # noqa: E402
import neural_specimen_n64_atlas_shell_version_strategy as strategy  # noqa: E402


class NeuralSpecimenN64AtlasShellVersionStrategyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inputs = strategy.load_inputs(ROOT)
        cls.candidate, cls.restore, cls.report = strategy.construct_pair(ROOT)

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

    def test_monotonic_versions_and_analysis_only_names(self):
        self.assertEqual(
            (
                strategy.PRIOR_CANDIDATE_VERSION,
                strategy.PRIOR_RESTORE_VERSION,
                strategy.CANDIDATE_VERSION,
                strategy.RESTORE_VERSION,
            ),
            (1376, 1377, 1382, 1383),
        )
        self.assertLess(strategy.PRIOR_CANDIDATE_VERSION, strategy.CANDIDATE_VERSION)
        self.assertLess(strategy.CANDIDATE_VERSION, strategy.RESTORE_VERSION)
        self.assertTrue(strategy.CANDIDATE_FILENAME.endswith(strategy.REQUIRED_SUFFIX))
        self.assertTrue(strategy.RESTORE_FILENAME.endswith(strategy.REQUIRED_SUFFIX))
        self.assertIn("atlas-shell", strategy.CANDIDATE_FILENAME)
        self.assertIn("atlas-shell", strategy.RESTORE_FILENAME)

    def test_manifest_and_four_segments_are_pinned(self):
        self.assertEqual(self.inputs.manifest_sha256, strategy.TARGET_MANIFEST_SHA256)
        self.assertEqual(
            set(self.inputs.segments), {"hook", "keyhook", "primary", "secondary"}
        )
        self.assertEqual(len(self.inputs.segments["hook"]), 4)
        self.assertEqual(len(self.inputs.segments["keyhook"]), 6)
        self.assertEqual(len(self.inputs.segments["primary"]), 856)
        self.assertEqual(len(self.inputs.segments["secondary"]), 1904)
        self.assertLessEqual(len(self.inputs.segments["primary"]), 0x3FF)
        self.assertLessEqual(len(self.inputs.segments["secondary"]), 0x800)

    def test_candidate_patches_both_hooks_and_both_allocations(self):
        main = self.stream(self.candidate, strategy.MAIN_RECORD_ID)
        self.assertEqual(main.software_version, 1382)
        self.assertEqual(
            int.from_bytes(
                main.decoded[
                    strategy.MAIN_HEADER_VERSION_OFFSET : strategy.MAIN_HEADER_VERSION_OFFSET
                    + 2
                ],
                "little",
            ),
            1382,
        )
        # Display hook branches to the primary entry, key hook to flyos_key_event.
        self.assertEqual(
            strategy.build_overlay_candidate.decode_thumb_bl(
                strategy.DISPLAY_HOOK_VA, self.inputs.segments["hook"]
            ),
            strategy.PRIMARY_VA,
        )
        expected = {
            "hook": strategy.DISPLAY_HOOK_OFFSET,
            "keyhook": strategy.KEY_HOOK_OFFSET,
            "primary": strategy.PRIMARY_OFFSET,
            "secondary": strategy.SECONDARY_OFFSET,
        }
        for name, offset in expected.items():
            segment = self.inputs.segments[name]
            self.assertEqual(main.decoded[offset : offset + len(segment)], segment)
        # Padding between the payload and the additive repair byte stays erased.
        self.assertEqual(
            main.decoded[
                strategy.PRIMARY_OFFSET + len(self.inputs.segments["primary"]) :
                strategy.PRIMARY_REPAIR_OFFSET
            ],
            b"\xff"
            * (
                strategy.PRIMARY_REPAIR_OFFSET
                - strategy.PRIMARY_OFFSET
                - len(self.inputs.segments["primary"])
            ),
        )
        self.assertEqual(
            main.decoded[
                strategy.SECONDARY_OFFSET + len(self.inputs.segments["secondary"]) :
                strategy.SECONDARY_OFFSET + strategy.SECONDARY_ALLOCATION
            ],
            b"\xff"
            * (strategy.SECONDARY_ALLOCATION - len(self.inputs.segments["secondary"])),
        )

    def test_restore_is_complete_official_application_and_resources(self):
        official_main = self.stream(self.inputs.official, strategy.MAIN_RECORD_ID)
        restore_main = self.stream(self.restore, strategy.MAIN_RECORD_ID)
        official_helper = self.stream(self.inputs.official, strategy.HELPER_RECORD_ID)
        restore_helper = self.stream(self.restore, strategy.HELPER_RECORD_ID)
        expected = bytearray(official_main.decoded)
        expected[
            strategy.MAIN_HEADER_VERSION_OFFSET : strategy.MAIN_HEADER_VERSION_OFFSET + 2
        ] = strategy.RESTORE_VERSION.to_bytes(2, "little")
        expected[-1] = restore_main.decoded[-1]
        self.assertEqual(restore_main.decoded, bytes(expected))
        self.assertEqual(restore_main.software_version, 1383)
        self.assertEqual(restore_helper.decoded, official_helper.decoded)
        self.assertEqual(restore_helper.fields, official_helper.fields)
        for offset, length in (
            (strategy.DISPLAY_HOOK_OFFSET, strategy.DISPLAY_HOOK_SIZE),
            (strategy.KEY_HOOK_OFFSET, strategy.KEY_HOOK_SIZE),
            (strategy.PRIMARY_OFFSET, strategy.PRIMARY_ALLOCATION),
            (strategy.SECONDARY_OFFSET, strategy.SECONDARY_ALLOCATION),
        ):
            self.assertEqual(
                restore_main.decoded[offset : offset + length],
                official_main.decoded[offset : offset + length],
            )

    def test_reports_prove_checksums_layout_and_offline_policy(self):
        self.assertEqual(self.report["verdict"], "PASS_OFFLINE_CONSTRUCTION")
        self.assertFalse(self.report["policy"]["packaging_allowed"])
        self.assertFalse(self.report["policy"]["live_staging_allowed"])
        self.assertTrue(all(self.report["candidate"]["checks"].values()))
        self.assertTrue(all(self.report["restore"]["checks"].values()))
        exact = strategy.verify_exact(ROOT, self.candidate, self.restore)
        self.assertEqual(exact["verdict"], "PASS")
        self.assertTrue(all(exact["checks"].values()))

    def test_exact_verifier_rejects_one_byte_tamper(self):
        damaged = bytearray(self.candidate)
        damaged[0x100000] ^= 1
        report = strategy.verify_exact(ROOT, bytes(damaged), self.restore)
        self.assertEqual(report["verdict"], "FAIL")
        self.assertFalse(report["checks"]["candidate_byte_exact_reconstruction"])

    def test_manifest_hash_and_placement_mutations_fail_closed(self):
        build = ROOT / strategy.TARGET_BUILD_RELATIVE_PATH
        manifest_path = build / "manifest.json"
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            changed_path = Path(directory) / "manifest.json"
            changed = json.loads(manifest_path.read_text(encoding="utf-8"))
            changed["segments"]["keyhook"]["start"] += 2
            changed_path.write_text(json.dumps(changed), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                strategy.base_strategy.load_pinned_snapshot(
                    changed_path,
                    expected_sha256=strategy.TARGET_MANIFEST_SHA256,
                )
            with self.assertRaisesRegex(ValueError, "keyhook placement"):
                strategy._validate_manifest(changed)

    def test_atlas_decision_policy_and_version_mutations_fail_closed(self):
        decision_path = ROOT / strategy.ATLAS_DECISION_RELATIVE_PATH
        decision = json.loads(decision_path.read_text(encoding="utf-8"))
        changed = json.loads(json.dumps(decision))
        changed["live_staging_allowed"] = True
        with self.assertRaisesRegex(ValueError, "policy changed"):
            strategy._validate_atlas_decision(changed)
        changed = json.loads(json.dumps(decision))
        changed["device"]["candidate_version"] = 1377
        with self.assertRaisesRegex(ValueError, "version chain changed"):
            strategy._validate_atlas_decision(changed)

    def test_build_outputs_are_fixed_create_new_local_paths(self):
        quarantine, analysis = strategy._exact_roots(ROOT)
        with self.assertRaisesRegex(ValueError, "unexpected offline artifact filename"):
            strategy._require_new_fixed_output(
                quarantine / "GUPDATE.GCD",
                quarantine,
                {strategy.CANDIDATE_FILENAME, strategy.RESTORE_FILENAME},
            )
        self.assertNotEqual(quarantine, analysis)


if __name__ == "__main__":
    unittest.main()
