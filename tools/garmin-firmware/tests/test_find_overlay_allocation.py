"""Conservative placement must never promote incomplete evidence to permission."""

import copy
import hashlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import find_overlay_allocation as scanner


class AllocationTests(unittest.TestCase):
    def setUp(self):
        self.image = bytes([0xFF]) * 1024
        self.base = 0x1000
        common = {
            "image_sha256": hashlib.sha256(self.image).hexdigest(),
            "image_base": self.base,
            "image_length": len(self.image),
            "coverage": [[0x1000, 0x13FF]],
            "complete": True,
            "source": "synthetic complete audit fixture",
        }
        self.inputs = {
            "protected_ranges": dict(common, ranges=[[0x1000, 0x103F]]),
            "reference_targets": dict(common, targets=[]),
            "decoded_ranges": dict(common, ranges=[]),
            "section_metadata": dict(
                common, ranges=[], boundaries=[], sections=[[0x1000, 0x13FF]]
            ),
        }

    def scan(self, **changes):
        args = dict(
            image=self.image, base=self.base, minimum_length=0x100,
            candidate_ranges=[[0x1100, 0x12FF]], fill_byte=0xFF,
            branch_anchors=[0x1000], **self.inputs,
        )
        args.update(changes)
        return scanner.scan_allocation(**args)

    def assert_rejected(self, report, reason):
        self.assertIsNone(report["selected_interval"])
        self.assertFalse(report["packaging_allowed"])
        self.assertIn(reason, " ".join(report["rejected_candidates"][0]["reasons"]))

    def test_accepts_exact_synthetic_interval_without_packaging_permission(self):
        report = self.scan()
        self.assertEqual(report["selected_interval"], {
            "start": "0x00001100", "end": "0x000012ff", "length": 512,
            "fill_byte": "0xff",
        })
        self.assertFalse(report["packaging_allowed"])
        self.assertEqual(report["rejected_candidates"], [])

    def test_missing_each_evidence_input(self):
        for name in self.inputs:
            with self.subTest(name=name):
                self.assert_rejected(self.scan(**{name: None}), "missing_evidence:" + name)

    def test_missing_required_evidence_fields(self):
        for name, block in self.inputs.items():
            for key in block:
                with self.subTest(name=name, key=key):
                    broken = copy.deepcopy(block)
                    del broken[key]
                    self.assert_rejected(self.scan(**{name: broken}), "evidence:")

    def test_incomplete_evidence_is_not_truthy_permission(self):
        for value in [False, 1, "true", None]:
            broken = dict(self.inputs["reference_targets"], complete=value)
            self.assert_rejected(self.scan(reference_targets=broken), "not_complete")

    def test_wrong_image_hash_base_length_and_empty_source(self):
        for key, value in [("image_sha256", "0" * 64), ("image_base", 0),
                           ("image_length", 1000), ("source", "")]:
            broken = dict(self.inputs["reference_targets"], **{key: value})
            self.assert_rejected(self.scan(reference_targets=broken), "evidence:")

    def test_coverage_must_cover_entire_image_not_only_candidate(self):
        for coverage in [[], [[0x1100, 0x12FF]], [[0x1000, 0x11FF], [0x1201, 0x13FF]],
                         [[0x1000, 0x1400]], [[0x13FF, 0x1000]]]:
            broken = dict(self.inputs["reference_targets"], coverage=coverage)
            self.assert_rejected(self.scan(reference_targets=broken), "coverage")

    def test_adjacent_complete_coverage_is_accepted(self):
        broken = dict(self.inputs["reference_targets"], coverage=[[0x1200, 0x13FF], [0x1000, 0x11FF]])
        self.assertIsNotNone(self.scan(reference_targets=broken)["selected_interval"])

    def test_nonfill_at_first_middle_or_last_byte(self):
        for address in [0x1100, 0x11FF, 0x12FF]:
            image = bytearray(self.image)
            image[address - self.base] = 0
            evidence = copy.deepcopy(self.inputs)
            for block in evidence.values():
                block["image_sha256"] = hashlib.sha256(image).hexdigest()
            self.assert_rejected(self.scan(image=bytes(image), **evidence), "non_fill_byte")

    def test_references_at_every_byte_and_thumb_alias_boundary(self):
        for address in range(0x1100, 0x1301):
            # Odd 0x1301 aliases the excluded next byte, so is not included here.
            if address == 0x1300:
                continue
            refs = dict(self.inputs["reference_targets"], targets=[address])
            self.assert_rejected(self.scan(reference_targets=refs), "reference_target")
        refs = dict(self.inputs["reference_targets"], targets=[0x1301])
        self.assertIsNotNone(self.scan(reference_targets=refs)["selected_interval"])
        self.assert_rejected(self.scan(candidate_ranges=[[0x1100, 0x12FE]],
            reference_targets=dict(self.inputs["reference_targets"], targets=[0x12FF])), "reference_target")

    def test_raw_pointer_scan_includes_unaligned_and_last_possible_word(self):
        for offset in [1, len(self.image) - 4]:
            for target in [0x1100, 0x11A5, 0x12FF]:
                image = bytearray(self.image)
                image[offset:offset + 4] = target.to_bytes(4, "little")
                evidence = copy.deepcopy(self.inputs)
                for block in evidence.values():
                    block["image_sha256"] = hashlib.sha256(image).hexdigest()
                self.assert_rejected(self.scan(image=bytes(image), **evidence), "raw_pointer")

    def test_occupied_and_protected_ranges_including_touching_bytes(self):
        for name in ["protected_ranges", "decoded_ranges", "section_metadata"]:
            for interval in [[0x10FF, 0x1100], [0x11AA, 0x11AB], [0x12FF, 0x1300]]:
                block = dict(self.inputs[name], ranges=[interval])
                self.assert_rejected(self.scan(**{name: block}), name + "_overlap")

    def test_section_boundaries_including_candidate_endpoints(self):
        for address in [0x1100, 0x1200, 0x12FF]:
            block = dict(self.inputs["section_metadata"], boundaries=[address])
            self.assert_rejected(self.scan(section_metadata=block), "section_boundary")

    def test_candidate_must_be_inside_one_complete_section(self):
        for sections in [[], [[0x1000, 0x11FF], [0x1200, 0x13FF]], [[0x1000, 0x13FE]],
                         [[0x1000, 0x13FF], [0x1100, 0x12FF]]]:
            block = dict(self.inputs["section_metadata"], sections=sections)
            self.assert_rejected(self.scan(section_metadata=block), "section")

    def test_malformed_evidence_lists_fail_closed(self):
        for name, key, value in [
            ("reference_targets", "targets", [True]),
            ("reference_targets", "targets", ["0x1100"]),
            ("decoded_ranges", "ranges", [[2, 1]]),
            ("protected_ranges", "ranges", "none"),
            ("section_metadata", "boundaries", [None]),
        ]:
            block = dict(self.inputs[name], **{key: value})
            self.assert_rejected(self.scan(**{name: block}), "evidence:")

    def test_truncated_image_out_of_bounds_and_short_candidate(self):
        self.assert_rejected(self.scan(image=self.image[:-1]), "image_length")
        for interval, reason in [([0x0FFE, 0x1100], "outside_image"),
                                 ([0x1300, 0x1400], "outside_image"),
                                 ([0x1100, 0x110F], "too_short"),
                                 ([0x1101, 0x12FF], "unaligned_start")]:
            self.assert_rejected(self.scan(candidate_ranges=[interval]), reason)

    def test_branch_evidence_and_unreachable_or_invalid_anchors(self):
        for anchors in [None, [], [0x1001], [0x2000000], [-2], [True], [0xFFFFFFFE]]:
            self.assert_rejected(self.scan(branch_anchors=anchors), "branch")

    def test_thumb_branch_exact_architectural_limits(self):
        self.assertTrue(scanner.thumb_bl_reachable(0x2000000, 0x1000004))
        self.assertFalse(scanner.thumb_bl_reachable(0x2000000, 0x1000002))
        self.assertTrue(scanner.thumb_bl_reachable(0x2000000, 0x3000002))
        self.assertFalse(scanner.thumb_bl_reachable(0x2000000, 0x3000004))
        self.assertFalse(scanner.thumb_bl_reachable(0xFFFFFFFE, 0))

    def test_one_two_and_three_byte_candidates_cannot_hold_thumb_bl(self):
        for length in [1, 2, 3]:
            with self.subTest(length=length):
                report = self.scan(minimum_length=1, candidate_ranges=[[0x1100, 0x1100 + length - 1]])
                self.assert_rejected(report, "cannot_fit_thumb_bl")
                self.assertEqual(report["rejected_candidates"][0]["branch_checks"], [])

    def test_four_byte_candidate_has_only_wholly_contained_outgoing_branch(self):
        report = self.scan(minimum_length=1, candidate_ranges=[[0x1100, 0x1103]])
        self.assertEqual(report["selected_interval"]["length"], 4)
        self.assertFalse(report["packaging_allowed"])
        outgoing = [check for check in report["accepted_candidates"][0]["branch_checks"]
                    if check["target"] == "0x00001000"]
        self.assertEqual(outgoing, [{"source": "0x00001100", "target": "0x00001000", "reachable": True}])

    def test_all_rejected_candidates_are_reported_and_selection_is_deterministic(self):
        report = self.scan(candidate_ranges=[[0x1100, 0x110F], [0x1200, 0x12FF], [0x1100, 0x11FF]])
        self.assertEqual(len(report["rejected_candidates"]), 1)
        self.assertEqual(len(report["accepted_candidates"]), 2)
        self.assertEqual(report["selected_interval"]["start"], "0x00001100")
        reordered = self.scan(candidate_ranges=[[0x1100, 0x11FF], [0x1200, 0x12FF], [0x1100, 0x110F]])
        self.assertEqual(scanner.json_text(report), scanner.json_text(reordered))
        self.assertEqual(json.loads(scanner.json_text(report)), report)

    def test_missing_candidates_and_invalid_parameters_raise(self):
        for changes in [dict(candidate_ranges=[]), dict(candidate_ranges=[[5, 4]]),
                        dict(minimum_length=0), dict(base=-1), dict(fill_byte=256),
                        dict(image=b""), dict(base=True), dict(minimum_length=True)]:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.scan(**changes)

    def test_cli_rejects_overwriting_inputs_or_emitting_firmware(self):
        for output in ["image.json", "evidence.json", "candidate.GCD", "image.bin"]:
            args = ["--image", "image.json", "--base", "0x1000", "--minimum-length", "256",
                    "--fill-byte", "255", "--candidate", "0x1100:0x12ff",
                    "--branch-anchor", "0x1000", "--evidence", "evidence.json", "--output", output]
            with self.subTest(output=output), patch("sys.stdout", new_callable=io.StringIO) as stdout, \
                    patch.object(Path, "read_bytes") as read, patch.object(Path, "write_text") as write:
                self.assertEqual(scanner.main(args), 2)
                report = json.loads(stdout.getvalue())
                self.assertFalse(report["packaging_allowed"])
                self.assertIsNone(report["selected_interval"])
                read.assert_not_called()
                write.assert_not_called()

    def test_cli_rejects_existing_hardlink_to_either_input_before_writing(self):
        for target_name in ["image.bin", "evidence.json"]:
            with self.subTest(target=target_name), tempfile.TemporaryDirectory(
                    dir=Path(__file__).resolve().parent) as directory:
                folder = Path(directory)
                image = folder / "image.bin"
                evidence = folder / "evidence.json"
                output = folder / "output.json"
                image.write_bytes(self.image)
                evidence.write_text(json.dumps(self.inputs), encoding="utf-8")
                output.hardlink_to(folder / target_name)
                originals = {path: path.read_bytes() for path in [image, evidence]}
                args = ["--image", str(image), "--base", "0x1000", "--minimum-length", "256",
                        "--fill-byte", "255", "--candidate", "0x1100:0x12ff",
                        "--branch-anchor", "0x1000", "--evidence", str(evidence), "--output", str(output)]
                with patch("sys.stdout", new_callable=io.StringIO) as stdout, \
                        patch.object(Path, "write_text") as write:
                    self.assertEqual(scanner.main(args), 2)
                    report = json.loads(stdout.getvalue())
                    self.assertIsNone(report["selected_interval"])
                    self.assertFalse(report["packaging_allowed"])
                    write.assert_not_called()
                for path, original in originals.items():
                    self.assertEqual(path.read_bytes(), original)

    def test_cli_allows_new_and_existing_distinct_json_output(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as directory:
            folder = Path(directory)
            image, evidence, output = folder / "image.bin", folder / "evidence.json", folder / "output.json"
            image.write_bytes(self.image)
            evidence.write_text(json.dumps(self.inputs), encoding="utf-8")
            originals = {path: path.read_bytes() for path in [image, evidence]}
            args = ["--image", str(image), "--base", "0x1000", "--minimum-length", "256",
                    "--fill-byte", "255", "--candidate", "0x1100:0x12ff",
                    "--branch-anchor", "0x1000", "--evidence", str(evidence), "--output", str(output)]
            for existing in [False, True]:
                with self.subTest(existing=existing):
                    self.assertEqual(output.exists(), existing)
                    self.assertEqual(scanner.main(args), 0)
                    report = json.loads(output.read_text())
                    self.assertIsNotNone(report["selected_interval"])
                    self.assertFalse(report["packaging_allowed"])
                    for path, original in originals.items():
                        self.assertEqual(path.read_bytes(), original)

    def test_cli_fails_closed_if_existing_output_identity_cannot_be_checked(self):
        args = ["--image", "image.bin", "--base", "0x1000", "--minimum-length", "256",
                "--fill-byte", "255", "--candidate", "0x1100:0x12ff",
                "--branch-anchor", "0x1000", "--evidence", "evidence.json", "--output", "output.json"]
        with patch.object(Path, "exists", return_value=True), \
                patch.object(Path, "samefile", side_effect=PermissionError("identity unavailable")), \
                patch.object(Path, "read_bytes") as read, patch.object(Path, "write_text") as write, \
                patch("sys.stdout", new_callable=io.StringIO) as stdout:
            self.assertEqual(scanner.main(args), 2)
            self.assertIn("identity unavailable", json.loads(stdout.getvalue())["input_error"])
            read.assert_not_called()
            write.assert_not_called()


if __name__ == "__main__":
    unittest.main()
